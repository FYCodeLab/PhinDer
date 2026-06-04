import streamlit as st
import pandas as pd
import requests
import unicodedata
import re
import time

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

def normalize(s):
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))

def clean_whitespace(name):
    return re.sub(r"\s+", " ", name).strip()

def split_asked_name(name):
    parts = name.split()
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]

def search_theses(name):
    r = requests.get(
        BASE_URL,
        params={"q": f'"{name}"', "nombre": 100},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30
    )
    r.raise_for_status()
    return r.json()

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

def process_name(name):
    first_asked, last_asked = split_asked_name(name)
    data = search_theses(name)
    theses = data.get("theses", [])

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

    return rows, data.get("totalHits", 0), len(theses)

# ============================================================
# STREAMLIT APP
# ============================================================

st.set_page_config(
    page_title="Theses.fr API Extraction",
    layout="wide"
)

st.title("Theses.fr API Extraction")
st.caption("Paste names, run the extraction, and watch the table fill live.")

names_input = st.text_area(
    "Names, one per line",
    placeholder="Frank Yates\nHéloïse Castiglione\nThomas Lemonnier\nIsabel Calvente",
    height=220
)

col_a, col_b = st.columns([1, 1])

with col_a:
    sleep_time = st.number_input(
        "Pause between API calls, seconds",
        min_value=0.0,
        max_value=5.0,
        value=0.2,
        step=0.1
    )

with col_b:
    show_not_found = st.checkbox(
        "Keep NOT FOUND rows",
        value=True
    )

start_button = st.button("Start extraction", type="primary")

if "rows" not in st.session_state:
    st.session_state.rows = []

if start_button:

    raw_names = [
        clean_whitespace(line)
        for line in names_input.splitlines()
        if clean_whitespace(line)
    ]

    if not raw_names:
        st.error("No names provided.")
        st.stop()

    st.session_state.rows = []

    total = len(raw_names)

    progress_bar = st.progress(0)

    metric_1, metric_2, metric_3, metric_4 = st.columns(4)

    current_placeholder = st.empty()
    log_placeholder = st.empty()
    table_placeholder = st.empty()

    logs = []

    for index, name in enumerate(raw_names, start=1):

        progress_bar.progress(index / total)

        current_placeholder.info(
            f"Currently processing {index}/{total}: {name}"
        )

        try:
            rows, total_hits, downloaded = process_name(name)

            if not show_not_found:
                rows = [
                    r for r in rows
                    if r[-1] == "SUCCESS"
                ]

            st.session_state.rows.extend(rows)

            success_count = sum(
                1 for r in rows
                if r[-1] == "SUCCESS"
            )

            logs.append(
                f"{index}/{total} | {name} | API hits: {total_hits} | downloaded: {downloaded} | added: {len(rows)} | success: {success_count}"
            )

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

            logs.append(
                f"{index}/{total} | {name} | ERROR: {e}"
            )

        df_current = pd.DataFrame(
            st.session_state.rows,
            columns=COLUMNS
        )

        with metric_1:
            st.metric("Processed", index)

        with metric_2:
            st.metric("Total", total)

        with metric_3:
            st.metric("Rows", len(df_current))

        with metric_4:
            st.metric(
                "Success rows",
                len(df_current[df_current["Pipeline Status Tracking"] == "SUCCESS"])
                if not df_current.empty else 0
            )

        log_placeholder.code("\n".join(logs[-12:]))

        table_placeholder.dataframe(
            df_current,
            use_container_width=True,
            height=520
        )

        time.sleep(sleep_time)

    current_placeholder.success("Extraction completed.")

    df_final = pd.DataFrame(
        st.session_state.rows,
        columns=COLUMNS
    )

    st.subheader("Final results")

    st.dataframe(
        df_final,
        use_container_width=True,
        height=700
    )

    st.download_button(
        "Download results as CSV",
        data=df_final.to_csv(index=False).encode("utf-8-sig"),
        file_name="these_results.csv",
        mime="text/csv"
    )
