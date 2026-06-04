import streamlit as st
import pandas as pd
import requests
import unicodedata
import re
import io
import zipfile
import time

# ============================================================
# CONFIG
# ============================================================

BASE_URL = "https://theses.fr/api/v1/theses/recherche/"

COLUMNS = [
    "First name asked",
    "Last name asked",
    "First name extracted",
    "Last name extracted",
    "Thesis Title",
    "Defense Date",
    "Start Date (Uncompleted)",
    "Organization",
    "University",
    "Doctoral School",
    "URL",
    "Thesis Status",
    "Pipeline Status Tracking"
]

# ============================================================
# HELPERS
# ============================================================

def normalize(s):
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s


def clean_whitespace(name):
    return re.sub(r"\s+", " ", name).strip()


def split_asked_name(name):
    parts = name.split()

    if len(parts) == 1:
        return parts[0], ""

    return " ".join(parts[:-1]), parts[-1]


def search_theses(name, log):
    log(f"Calling theses.fr API for: `{name}`")

    r = requests.get(
        BASE_URL,
        params={
            "q": f'"{name}"',
            "nombre": 100
        },
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30
    )

    r.raise_for_status()
    data = r.json()

    theses = data.get("theses", [])

    log(f"API total hits: **{data.get('totalHits', 'unknown')}**")
    log(f"Candidate records downloaded: **{len(theses)}**")

    return theses


def is_author(thesis, first_asked, last_asked):
    target = normalize(f"{first_asked} {last_asked}")

    for a in thesis.get("auteurs", []):
        first = a.get("prenom", "")
        last = a.get("nom", "")

        full = normalize(f"{first} {last}")

        if target == full or target in full:
            return first, last

    return None, None


def extract_doctoral_school(thesis):
    value = "; ".join(
        ed.get("nom", "")
        for ed in thesis.get("ecolesDoctorale", [])
        if ed.get("nom")
    )

    return value or "NON ACCESSIBLE"


def extract_organization(thesis):
    value = "; ".join(
        p.get("nom", "")
        for p in thesis.get("partenairesDeRecherche", [])
        if p.get("nom")
    )

    return value or "NON ACCESSIBLE"


def extract_row(name, thesis, first_extracted, last_extracted):
    first_asked, last_asked = split_asked_name(name)
    thesis_id = thesis.get("id", "")

    return [
        first_asked,
        last_asked,
        first_extracted or "NON ACCESSIBLE",
        last_extracted or "NON ACCESSIBLE",
        thesis.get("titrePrincipal", "NON ACCESSIBLE"),
        thesis.get("dateSoutenance") or "NON ACCESSIBLE",
        thesis.get("datePremiereInscriptionDoctorat") or "NON ACCESSIBLE",
        extract_organization(thesis),
        thesis.get("etabSoutenanceN", "NON ACCESSIBLE"),
        extract_doctoral_school(thesis),
        f"https://www.theses.fr/{thesis_id}" if thesis_id else "",
        thesis.get("status", "NON ACCESSIBLE"),
        "SUCCESS"
    ]


def process_name(name, log):
    first_asked, last_asked = split_asked_name(name)
    theses = search_theses(name, log)

    rows = []

    for thesis in theses:
        first_extracted, last_extracted = is_author(
            thesis,
            first_asked,
            last_asked
        )

        if first_extracted:
            rows.append(
                extract_row(
                    name,
                    thesis,
                    first_extracted,
                    last_extracted
                )
            )

    if not rows:
        rows.append([
            first_asked,
            last_asked,
            "NOT FOUND",
            "NOT FOUND",
            "NON ACCESSIBLE",
            "NON ACCESSIBLE",
            "NON ACCESSIBLE",
            "NON ACCESSIBLE",
            "NON ACCESSIBLE",
            "NON ACCESSIBLE",
            "",
            "NON ACCESSIBLE",
            "NO AUTHOR THESIS FOUND"
        ])

    return rows


def make_zip_from_chunks(chunk_files):
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for filename, df_chunk in chunk_files:
            csv_data = df_chunk.to_csv(index=False).encode("utf-8-sig")
            zip_file.writestr(filename, csv_data)

    zip_buffer.seek(0)
    return zip_buffer


# ============================================================
# STREAMLIT UI
# ============================================================

st.set_page_config(
    page_title="Theses.fr API Extraction",
    layout="wide"
)

st.title("Theses.fr API Extraction")
st.caption("API-only version. No Selenium, no scraping, no XML parsing.")

with st.sidebar:
    st.header("Settings")

    batch_size = st.number_input(
        "Chunk size",
        min_value=1,
        max_value=100,
        value=10
    )

    sleep_time = st.number_input(
        "Pause between API calls, seconds",
        min_value=0.0,
        max_value=5.0,
        value=0.2,
        step=0.1
    )

    st.markdown("Files will be named:")
    st.code("these_1-10.csv\nthese_11-20.csv\nthese_ALL.csv")

names_input = st.text_area(
    "Paste names, one per line",
    placeholder="Frank Yates\nHéloïse Castiglione\nThomas Lemonnier\nIsabel Calvente",
    height=220
)

start_button = st.button("Start extraction", type="primary")

if "rows" not in st.session_state:
    st.session_state.rows = []

if "chunk_files" not in st.session_state:
    st.session_state.chunk_files = []

if start_button:

    st.session_state.rows = []
    st.session_state.chunk_files = []

    raw_names = [
        clean_whitespace(line)
        for line in names_input.splitlines()
        if clean_whitespace(line)
    ]

    if not raw_names:
        st.error("No names provided.")
        st.stop()

    total = len(raw_names)

    st.info(f"{total} name(s) loaded.")

    progress = st.progress(0)
    metrics_area = st.empty()
    table_area = st.empty()
    log_area = st.container()

    current_batch_rows = []
    current_batch_start = 1

    with st.status("Extraction running", expanded=True) as status:

        def log(msg):
            status.write(msg)

        for index, name in enumerate(raw_names, start=1):

            progress.progress(index / total)

            log("")
            log("=" * 60)
            log(f"Processing **{index}/{total}**: `{name}`")

            try:
                person_rows = process_name(name, log)

                st.session_state.rows.extend(person_rows)
                current_batch_rows.extend(person_rows)

                successes = sum(
                    1 for row in person_rows
                    if row[-1] == "SUCCESS"
                )

                log(f"Rows added: **{len(person_rows)}**")
                log(f"Successful thesis rows: **{successes}**")

            except Exception as e:
                first, last = split_asked_name(name)

                error_row = [
                    first,
                    last,
                    "ERROR",
                    "ERROR",
                    "NON ACCESSIBLE",
                    "NON ACCESSIBLE",
                    "NON ACCESSIBLE",
                    "NON ACCESSIBLE",
                    "NON ACCESSIBLE",
                    "NON ACCESSIBLE",
                    "",
                    "NON ACCESSIBLE",
                    f"ERROR: {e}"
                ]

                st.session_state.rows.append(error_row)
                current_batch_rows.append(error_row)

                log(f"Error: `{e}`")

            df_current = pd.DataFrame(st.session_state.rows, columns=COLUMNS)

            table_area.dataframe(
                df_current,
                use_container_width=True,
                height=420
            )

            metrics_area.metric(
                label="Rows collected so far",
                value=len(df_current)
            )

            if index % batch_size == 0 or index == total:
                chunk_start = current_batch_start
                chunk_end = index

                chunk_filename = f"these_{chunk_start}-{chunk_end}.csv"

                df_chunk = pd.DataFrame(
                    current_batch_rows,
                    columns=COLUMNS
                )

                st.session_state.chunk_files.append(
                    (chunk_filename, df_chunk)
                )

                log(f"Saved chunk in memory: `{chunk_filename}`")
                log(f"Rows in chunk: **{len(df_chunk)}**")

                current_batch_rows = []
                current_batch_start = index + 1

            time.sleep(sleep_time)

        status.update(
            label="Extraction finished",
            state="complete",
            expanded=False
        )

    df_final = pd.DataFrame(st.session_state.rows, columns=COLUMNS)

    st.success("Extraction completed.")

    st.subheader("Final table")
    st.dataframe(df_final, use_container_width=True, height=500)

    st.download_button(
        "Download these_ALL.csv",
        data=df_final.to_csv(index=False).encode("utf-8-sig"),
        file_name="these_ALL.csv",
        mime="text/csv"
    )

    zip_buffer = make_zip_from_chunks(st.session_state.chunk_files)

    st.download_button(
        "Download chunked CSV files as ZIP",
        data=zip_buffer.getvalue(),
        file_name="these_chunks.zip",
        mime="application/zip"
    )
