import streamlit as st
import pandas as pd
import io
import zipfile
import requests
import time
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# =====================================================================
# 1. WEB DRIVER SETUP
# =====================================================================

def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.binary_location = "/usr/bin/chromium"
    return webdriver.Chrome(options=options)

# =====================================================================
# 2. SCRAPING & UTILITY HELPER FUNCTIONS
# =====================================================================

def clean_whitespace(name):
    cleaned = name.expandtabs(1)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()

def split_asked_name(name):
    parts = name.split(' ')
    if len(parts) == 0 or parts == ['']:
        return "", ""
    elif len(parts) == 1:
        return parts[0], ""
    else:
        first_name = " ".join(parts[:-1])
        last_name = parts[-1]
        return first_name, last_name

def get_first_person_id(driver, name, log_callback):
    log_callback(f"🌐 Accessing theses.fr registry for: **{name}**...")
    query = name.replace(" ", "+")
    search_url = f"https://theses.fr/resultats?q={query}&page=1&nb=10&tri=pertinence&domaine=personnes"
    driver.get(search_url)

    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(1.5)
    except:
        return None

    html_source = driver.page_source
    soup = BeautifulSoup(html_source, "html.parser")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.match(r"^/\d{9}$", href):
            person_id = href[1:]
            log_callback(f"🎯 **Success:** Person Profile found ID `[{person_id}]`")
            return person_id

    idref_matches = re.findall(r'"idRef"\s*:\s*"(\d{9})"', html_source) or re.findall(r'/(\d{9})', html_source)
    if idref_matches:
        person_id = idref_matches[0]
        log_callback(f"🎯 **Success:** Profile mapped from payload string `[{person_id}]`")
        return person_id

    return None

def get_fallback_thesis_id(driver, name, log_callback):
    log_callback("🔍 *Trying ongoing PhD fallback strategy...*")
    query = name.replace(" ", "+")
    search_url = f"https://theses.fr/resultats?q={query}&page=1&nb=10&tri=pertinence"
    driver.get(search_url)

    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(1.5)
    except:
        return None

    soup = BeautifulSoup(driver.page_source, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.match(r"^/s\d{6}$", href) or re.match(r"^/\d{4}[A-Z0-9]{6,10}$", href):
            thesis_id = href[1:]
            log_callback(f"📂 **Success:** Tracked active Project ID `[{thesis_id}]`")
            return thesis_id

    log_callback("⚠️ *Warning: No reference matches found.*")
    return None

def get_thesis_id_from_person_page(driver, person_id, log_callback):
    log_callback(f"📄 Fetching historical links for profile ID: `{person_id}`...")
    person_url = f"https://www.theses.fr/{person_id}"
    driver.get(person_url)
    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(1.5)
    except:
        return None

    html = driver.page_source
    matches = re.findall(r'"(\d{4}[A-Z0-9]{6,10})"\s*,\s*"Auteur\s*/\s*Autrice"', html) or \
              re.findall(r'"(s\d{6})"\s*,\s*"Auteur\s*/\s*Autrice"', html) or \
              re.findall(r'"(\d{4}[A-Z0-9]{6,10})"', html) or \
              re.findall(r'"(s\d{6})"', html)

    if matches:
        clean_matches = list(dict.fromkeys(matches))
        clean_matches = [m for m in clean_matches if m != person_id]
        if clean_matches:
            thesis_id = clean_matches[0]
            log_callback(f"🔗 Connected Profile to Thesis Document: `[{thesis_id}]`")
            return thesis_id

    log_callback("⚠️ *Warning: No internal links mapped.*")
    return None

def get_xml_from_thesis_id(thesis_id, log_callback):
    log_callback(f"📡 Connecting to remote XML dataset for `[{thesis_id}]`...")
    xml_url = f"https://theses.fr/api/v1/export/xml/{thesis_id}"
    try:
        response = requests.get(xml_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if response.status_code != 200 or not response.text.strip():
            return None
        return response.text
    except:
        return None

def extract_fields_from_xml(xml_text, asked_name, thesis_id, log_callback):
    soup = BeautifulSoup(xml_text, "xml")
    first_name_asked, last_name_asked = split_asked_name(asked_name)

    extracted_full_name = "NON ACCESSIBLE"
    thesis_title = "NON ACCESSIBLE"
    defense_date = "NON ACCESSIBLE"
    start_date = "NON ACCESSIBLE"
    university = "NON ACCESSIBLE"
    organization = "NON ACCESSIBLE"

    title_tag = soup.find("dc:title") or soup.find("dcterms:title")
    if title_tag:
        thesis_title = title_tag.get_text(strip=True)

    author_block = soup.find("marcrel:aut") or soup.find("marcrel:dis")
    if author_block:
        name_tag = author_block.find("foaf:name")
        if name_tag:
            extracted_full_name = name_tag.get_text(strip=True)

    if extracted_full_name == "NON ACCESSIBLE":
        vignette_author = soup.find("vignette:auteur") or soup.find("vignette:biographie")
        if vignette_author:
            name_tag = vignette_author.find("foaf:name") or vignette_author.find("dc:creator")
            if name_tag:
                extracted_full_name = name_tag.get_text(strip=True)

    if "," in extracted_full_name:
        last_name_extracted, first_name_extracted = [x.strip() for x in extracted_full_name.split(",", 1)]
    else:
        name_parts = extracted_full_name.split(" ")
        if len(name_parts) > 1:
            first_name_extracted = " ".join(name_parts[:-1])
            last_name_extracted = name_parts[-1]
        else:
            first_name_extracted = extracted_full_name
            last_name_extracted = ""

    date_accepted_tag = soup.find("dcterms:dateAccepted")
    created_tag = soup.find("dcterms:created")

    if date_accepted_tag:
        defense_date = date_accepted_tag.get_text(strip=True)
    elif created_tag:
        start_date = created_tag.get_text(strip=True)
        if "T" in start_date:
            start_date = start_date.split("T")[0]

    dgg_tags = soup.find_all("marcrel:dgg")
    if len(dgg_tags) >= 1:
        u_name = dgg_tags[0].find("foaf:name")
        if u_name:
            university = u_name.get_text(strip=True)
    if len(dgg_tags) >= 2:
        o_name = dgg_tags[1].find("foaf:name")
        if o_name:
            organization = o_name.get_text(strip=True)

    url = f"https://theses.fr/{thesis_id}"
    return [
        first_name_asked, last_name_asked,
        first_name_extracted, last_name_extracted,
        thesis_title, defense_date, start_date,
        organization, university, url, "SUCCESS"
    ]

# =====================================================================
# 3. USER INTERFACE (STREAMLIT ENGINE)
# =====================================================================

st.set_page_config(page_title="Thesis Extraction Pipeline", layout="wide")
st.title("🎓 Theses.fr Metadata Extraction Pipeline")

# We manage state so data stays visible if the user presses "Stop"
if "scraped_rows" not in st.session_storage:
    st.session_storage["scraped_rows"] = []

with st.form("unlocked_pipeline_form"):
    names_input = st.text_area(
        label="📋 Paste student name directory here (One entry per line)",
        placeholder="Frank Yates\nJean Dupont\nMarie Martin",
        height=200
    )
    BATCH_SIZE = st.number_input("Batch packaging file split size", min_value=1, max_value=100, value=10)
    submit_button = st.form_submit_button("🚀 Start Web Scraping Pipeline")

# Add a prominent stop toggle option outside the input form
stop_pipeline = st.checkbox("🛑 Emergency Stop Processing Loop")

if submit_button and names_input.strip():
    # Reset storage on a fresh submit
    st.session_storage["scraped_rows"] = []
    
    raw_names = [line.strip() for line in names_input.splitlines() if line.strip()]
    total = len(raw_names)
    
    st.info(f"📋 Verification complete: **{total}** targets loaded successfully.")
    
    columns = [
        "First name asked", "Last name asked",
        "First name extracted", "Last name extracted",
        "Thesis Title", "Defense Date", "Start Date (Uncompleted)",
        "Organization", "University", "URL", "Pipeline Status Tracking"
    ]
    
    progress_bar = st.progress(0)
    
    # Placeholders for live updates
    status_msg = st.empty()
    table_placeholder = st.empty()  # This houses the LIVE expanding table data
    
    with st.status("🕵️‍♂️ Extraction Engine Activity Terminal...", expanded=True) as status_container:
        status_container.write("Initializing secure cloud browser instance...")
        try:
            driver = get_driver()
            status_container.write("✔️ Browser runtime initialized.")
        except Exception as driver_err:
            st.error(f"Failed to launch native container driver: {driver_err}")
            st.stop()
        
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            try:
                for index, raw_name in enumerate(raw_names, start=1):
                    # Check if user flipped the Stop checkbox mid-execution loop
                    if stop_pipeline:
                        status_container.write("🛑 **Pipeline manually stopped by user request!**")
                        break
                        
                    name = clean_whitespace(raw_name)
                    progress_bar.progress(index / total)
                    status_container.write(f"⚙️ **[{index}/{total}] Processing Target:** `{name}`")
                    
                    def log_to_terminal(msg):
                        status_container.write(msg)

                    try:
                        first_asked, last_asked = split_asked_name(name)
                        person_id = get_first_person_id(driver, name, log_to_terminal)
                        thesis_id = None
                        
                        if person_id:
                            thesis_id = get_thesis_id_from_person_page(driver, person_id, log_to_terminal)
                        if not thesis_id:
                            thesis_id = get_fallback_thesis_id(driver, name, log_to_terminal)

                        if not thesis_id:
                            log_to_terminal(f"❌ Record `{name}` could not be found.")
                            current_row = [
                                first_asked, last_asked, "NOT FOUND", "NOT FOUND",
                                "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE",
                                "NON ACCESSIBLE", "NON ACCESSIBLE", "", "NOT FOUND"
                            ]
                        else:
                            xml_text = get_xml_from_thesis_id(thesis_id, log_to_terminal)
                            if not xml_text:
                                current_row = [
                                    first_asked, last_asked, "NON ACCESSIBLE", "NON ACCESSIBLE",
                                    "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE",
                                    "NON ACCESSIBLE", "NON ACCESSIBLE", f"https://theses.fr/{thesis_id}",
                                    "To be verified by hand (Case 3: XML empty)"
                                ]
                            else:
                                current_row = extract_fields_from_xml(xml_text, name, thesis_id, log_to_terminal)
                                log_to_terminal(f"✔️ Mapping successful for `{name}`.")
                        
                        # Save inside persistent app storage
                        st.session_storage["scraped_rows"].append(current_row)

                    except Exception as item_err:
                        log_to_terminal(f"💥 Pipeline Error: {item_err}")
                        error_row = [
                            first_asked, last_asked, "ERROR", str(item_err),
                            "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE",
                            "NON ACCESSIBLE", "NON ACCESSIBLE", "", f"FATAL ERROR: {str(item_err)}"
                        ]
                        st.session_storage["scraped_rows"].append(error_row)

                    # --- LIVE EXPANDING TABLE DISPLAY UPDATE ---
                    df_current = pd.DataFrame(st.session_storage["scraped_rows"], columns=columns)
                    table_placeholder.dataframe(df_current, use_container_width=True)

                    # --- IN-MEMORY ZIP BATCH PACKAGING ---
                    if index % BATCH_SIZE == 0 or index == total:
                        start_num = ((index - 1) // BATCH_SIZE) * BATCH_SIZE + 1
                        end_num = len(st.session_storage["scraped_rows"])
                        chunk_rows = st.session_storage["scraped_rows"][start_num - 1 : end_num]
                        
                        if chunk_rows:
                            df_chunk = pd.DataFrame(chunk_rows, columns=columns)
                            csv_data = df_chunk.to_csv(index=False).encode('utf-8')
                            filename = f"extracted {start_num}-{end_num}.csv"
                            zip_file.writestr(filename, csv_data)

            finally:
                status_container.write("🔒 Terminating driver pipeline context...")
                driver.quit()
        
        status_container.update(label="🎉 System run finalized.", state="complete", expanded=False)
        
    # Once finished or stopped, provide download buttons
    if st.session_storage["scraped_rows"]:
        st.success("🏁 Run terminated or completed. Your files are compiled below.")
        
        # Display the final data structure
        df_final = pd.DataFrame(st.session_storage["scraped_rows"], columns=columns)
        table_placeholder.dataframe(df_final, use_container_width=True)
        
        # Immediate active download button
        st.download_button(
            label="📥 Download Extracted CSV Batches (ZIP File)",
            data=zip_buffer.getvalue(),
            file_name="theses_extracted_batches.zip",
            mime="application/zip"
        )
