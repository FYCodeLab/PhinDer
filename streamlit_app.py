import streamlit as st
import pandas as pd
import requests
import unicodedata
import re
import time

BASE_URL = "https://theses.fr/api/v1/theses/recherche/"

COLUMNS = [
    "First Name in file",
    "Last Name in file",
    "First Name in Theses.fr (Auteur)",
    "Last Name in Theses.fr (Auteur)",
    "Identifiant auteur",
    "Titre",
    "Nom du Directeur de these",
    "Discipline",
    "Nom de l'Université",
    "Nom du laboratoire",
    "Ville",
    "Ecole doctorale",
    "Date de premiere inscription en doctorat",
    "Date de soutenance",
    "Identifiant de la these",
    "Thesis URL",
    "Pipeline Status Tracking"
]


def normalize(s):
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def clean_whitespace(name):
    return re.sub(r"\s+", " ", str(name)).strip()


def split_asked_name(name):
    parts = clean_whitespace(name).split()

    if len(parts) == 1:
        return parts[0], ""

    return parts[0], " ".join(parts[1:])


def safe(value):
    return value if value not in [None, "", []] else "NON ACCESSIBLE"


def search_theses(full_name):
    r = requests.get(
        BASE_URL,
        params={
            "q": f'"{full_name}"',
            "nombre": 100
        },
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
            author_id = (
                a.get("idref")
                or a.get("id")
                or a.get("identifiant")
                or a.get("personneId")
                or "NON ACCESSIBLE"
            )

            return first, last, author_id

    return None, None, None


def extract_doctoral_school(thesis):
    value = "; ".join(
        ed.get("nom", "")
        for ed in thesis.get("ecolesDoctorale", [])
        if ed.get("nom")
    )

    return value or "NON ACCESSIBLE"


def extract_laboratory(thesis):
    labs = []

    for p in thesis.get("partenairesDeRecherche", []):
        nom = p.get("nom", "")
        typ = normalize(p.get("type", ""))

        if nom and (
            "laboratoire" in typ
            or "unite" in typ
            or "research" in typ
        ):
            labs.append(nom)

    if not labs:
        labs = [
            p.get("nom", "")
            for p in thesis.get("partenairesDeRecherche", [])
            if p.get("nom")
        ]

    return "; ".join(labs) if labs else "NON ACCESSIBLE"


def extract_directors(thesis):
    directors = []

    for key in ["directeursThese", "directeurs", "directeurThese"]:
        value = thesis.get(key, [])

        if isinstance(value, dict):
            value = [value]

        for d in value:
            first = d.get("prenom", "")
            last = d.get("nom", "")
            full = clean_whitespace(f"{first} {last}")

            if full:
                directors.append(full)

    return "; ".join(directors) if directors else "NON ACCESSIBLE"


def extract_city(thesis):
    for key in ["ville", "villeSoutenance", "etabSoutenanceVille"]:
        if thesis.get(key):
            return thesis.get(key)

    etab = thesis.get("etablissementSoutenance", {})

    if isinstance(etab, dict):
        return etab.get("ville", "NON ACCESSIBLE")

    return "NON ACCESSIBLE"


def extract_discipline(thesis):
    value = thesis.get("discipline") or thesis.get("disciplineThese")

    if isinstance(value, list):
        return "; ".join(value)

    return value or "NON ACCESSIBLE"


def extract_row(first_file, last_file, thesis, first_author, last_author, author_id):
    thesis_id = thesis.get("id", "")
    thesis_url = f"https://www.theses.fr/{thesis_id}" if thesis_id else ""

    return [
        safe(first_file),
        safe(last_file),
        safe(first_author),
        safe(last_author),
        safe(author_id),
        safe(thesis.get("titrePrincipal")),
        extract_directors(thesis),
        extract_discipline(thesis),
        safe(thesis.get("etabSoutenanceN")),
        extract_laboratory(thesis),
        extract_city(thesis),
        extract_doctoral_school(thesis),
        safe(thesis.get("datePremiereInscriptionDoctorat")),
        safe(thesis.get("dateSoutenance")),
        safe(thesis_id),
        thesis_url,
        "SUCCESS"
    ]


def process_person(first_file, last_file):
    full_name = clean_whitespace(f"{first_file} {last_file}")

    data = search_theses(full_name)
    theses = data.get("theses", [])

    rows = []

    for thesis in theses:
        first_author, last_author, author_id = is_author(
            thesis,
            first_file,
            last_file
        )

        if first_author:
            rows.append(
                extract_row(
                    first_file,
                    last_file,
                    thesis,
                    first_author,
                    last_author,
                    author_id
                )
            )

    if not rows:
        rows.append([
            safe(first_file),
            safe(last_file),
            "NOT FOUND",
            "NOT FOUND",
            "NON ACCESSIBLE",
            "NON ACCESSIBLE",
            "NON ACCESSIBLE",
            "NON ACCESSIBLE",
            "NON ACCESSIBLE",
            "NON ACCESSIBLE",
            "NON ACCESSIBLE",
            "NON ACCESSIBLE",
            "NON ACCESSIBLE",
            "NON ACCESSIBLE",
            "NON ACCESSIBLE",
            "",
            "NO AUTHOR THESIS FOUND"
        ])

    return rows, data.get("totalHits", 0), len(theses)


st.set_page_config(
    page_title="Phinder",
    layout="wide"
)

st.title("Phinder")
st.caption("Theses.fr API extraction")

st.markdown(
    """
    <div style="font-size:0.85rem; opacity:0.75; margin-top:-0.5rem;">
        🔎 Created by 
        <a href="https://github.com/FYCodeLab" target="_blank">FYCodeLab</a>
    </div>
    """,
    unsafe_allow_html=True
)

with st.sidebar:
    st.header("Settings")

    sleep_time = st.number_input(
        "Pause between API calls (seconds)",
        min_value=0.0,
        max_value=5.0,
        value=0.2,
        step=0.1
    )

    show_not_found = st.checkbox(
        "Show NOT FOUND entries",
        value=True
    )


names_input = st.text_area(
    "Names, one per line",
    placeholder="John Doe\nJane Doe\nPaul Dupont",
    height=240
)

start_button = st.button(
    "Start extraction",
    type="primary"
)


if start_button:

    input_rows = []

    if names_input.strip():
        for line in names_input.splitlines():
            name = clean_whitespace(line)

            if name:
                first, last = split_asked_name(name)

                input_rows.append({
                    "First Name in file": first,
                    "Last Name in file": last
                })
    else:
        st.error("No names provided.")
        st.stop()

    total = len(input_rows)
    all_rows = []
    logs = []

    st.subheader("Progress")

    progress_bar = st.progress(0)
    status_box = st.empty()
    summary_box = st.empty()

    with st.expander("Live log", expanded=False):
        log_box = st.empty()

    table_box = st.empty()

    start_time = time.time()

    for index, person in enumerate(input_rows, start=1):

        first_file = person["First Name in file"]
        last_file = person["Last Name in file"]
        display_name = clean_whitespace(f"{first_file} {last_file}")

        progress_bar.progress(index / total)

        status_box.info(
            f"Processing {index}/{total} — {display_name}"
        )

        try:
            person_rows, total_hits, downloaded = process_person(
                first_file,
                last_file
            )

            if not show_not_found:
                person_rows = [
                    r for r in person_rows
                    if r[-1] == "SUCCESS"
                ]

            all_rows.extend(person_rows)

            success_count = sum(
                1 for row in person_rows
                if row[-1] == "SUCCESS"
            )

            logs.append(
                f"✓ {display_name} | API hits: {total_hits} | downloaded: {downloaded} | added: {len(person_rows)} | success: {success_count}"
            )

        except Exception as e:
            all_rows.append([
                safe(first_file),
                safe(last_file),
                "ERROR",
                "ERROR",
                "NON ACCESSIBLE",
                "NON ACCESSIBLE",
                "NON ACCESSIBLE",
                "NON ACCESSIBLE",
                "NON ACCESSIBLE",
                "NON ACCESSIBLE",
                "NON ACCESSIBLE",
                "NON ACCESSIBLE",
                "NON ACCESSIBLE",
                "NON ACCESSIBLE",
                "NON ACCESSIBLE",
                "",
                f"ERROR: {e}"
            ])

            logs.append(
                f"✗ {display_name} | ERROR: {e}"
            )

        df_current = pd.DataFrame(
            all_rows,
            columns=COLUMNS
        )

        elapsed = round(time.time() - start_time, 1)

        success_total = len(
            df_current[
                df_current["Pipeline Status Tracking"] == "SUCCESS"
            ]
        ) if not df_current.empty else 0

        summary_box.markdown(
            f"""
**Processed:** {index}/{total}  
**Rows collected:** {len(df_current)}  
**Successful theses:** {success_total}  
**Elapsed time:** {elapsed} seconds
"""
        )

        log_box.code(
            "\n".join(logs[-20:]),
            language=None
        )

        table_box.dataframe(
            df_current,
            use_container_width=True,
            height=520
        )

        time.sleep(sleep_time)

    progress_bar.progress(1.0)

    status_box.success(
        f"Completed — {total} names processed"
    )

    df_final = pd.DataFrame(
        all_rows,
        columns=COLUMNS
    )

    st.divider()

    st.subheader("Final results")

    st.dataframe(
        df_final,
        use_container_width=True,
        height=700
    )

    st.download_button(
        "Download CSV",
        data=df_final.to_csv(index=False).encode("utf-8-sig"),
        file_name="phinder_results.csv",
        mime="text/csv"
    )
