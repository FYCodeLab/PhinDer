import streamlit as st
import pandas as pd
import io
import zipfile
import requests
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# =====================================================================
# 1. WEB DRIVER SETUP
# =====================================================================

def get_driver():
    """Sets up a headless Chromium driver compatible with Streamlit Cloud."""
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

def clean_whitespace(text):
    return " ".join(text.split())

def split_asked_name(name):
    parts = name.strip().split(maxsplit=1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return name, ""

def get_first_person_id(driver, name, log_callback):
    log_callback(f"🌐 Navigating to search engine for: **{name}**...")
    time.sleep(1) # Simulating browser delay
    
    # --- YOUR ACTUAL SELENIUM SEARCH CODE GOES HERE ---
    # Example: driver.get(f"https://theses.fr/results?q={name}")
    
    log_callback(f"🤔 Analyzing search results for **{name}**...")
    
    # If it fails to find "Yates", this is where the logic is dropping it.
    if "Yates" in name:
        log_callback("❌ Specific check failed: No matching profile found for 'Yates'.")
        return None
        
    return None 

def get_thesis_id_from_person_page(driver, person_id, log_callback):
    log_callback(f"📄 Loading profile page ID: {person_id}...")
    return None

def get_fallback_thesis_id(driver, name, log_callback):
    log_callback(f"🔄 Trying backup keyword search string for: {name}...")
    return None

def get_xml_from_thesis_id(thesis_id):
    try:
        url = f"https://theses.fr/{thesis_id}.xml"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.text
    except Exception:
        pass
    return None

def extract_fields_from_xml(xml_text, name, thesis_id):
    first_asked, last_asked = split_asked_name(name)
    return [
        first_asked, last_asked, "ExtractedFirst", "ExtractedLast",
        "Sample Thesis Title", "2026-06-02", "Ongoing", "Sample Org", "Sample University",
        f"https://theses.fr/{thesis_id}", "Success"
    ]

# =====================================================================
# 3. USER INTERFACE (STREAMLIT)
# =====================================================================

st.title("🎓 Thesis Extraction Pipeline")
st.markdown("Paste your list below. The application will log its background actions live.")

# Use a Form to completely disable Ctrl+Enter auto-submission
with st.form("student_input_form"):
    names_input = st.text_area(
        label="📋 Paste your students list here (One student per line)",
        placeholder="Jean Dupont\nMarie Martin\nFrank Yates",
        height=250
    )
    
    # This button controls the submission of the form explicitly
    submit_button = st.form_submit_button("🚀 Start Web Scraping Pipeline")

# Check if the user pressed the explicit form button
if submit_button and names_input.strip():
    raw_names = [line.strip() for line in names_input.splitlines() if line.strip()]
    total = len(raw_names)
    
    st.info(f"📋 Loaded **{total}** names for processing.")
    
    rows = []
    columns = [
        "First name asked", "Last name asked", "First name extracted", "Last name extracted",
        "Thesis Title", "Defense Date", "Start Date (Uncompleted)", "Organization", "University", "URL", "Pipeline Status Tracking"
    ]
    
    progress_bar = st.progress(0)
    
    # Create a live status container that stays open while running
    with st.status("🕵️‍♂️ Scraping Pipeline Activity Log...", expanded=True) as status_container:
        
        status_container.write("Initializing secure virtual browser environment...")
        try:
            driver = get_driver()
            status_container.write("✔️ Browser successfully initialized.")
        except Exception as driver_err:
            st.error(f"Failed to launch Chromium: {driver_err}")
            st.stop()
        
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            try:
                for index, raw_name in enumerate(raw_names, start=1):
                    name = clean_whitespace(raw_name)
                    progress_bar.progress(index / total)
                    
                    status_container.write(f"--- 👤 Processing ({index}/{total}): **{name}** ---")
                    
                    # This internal helper function prints lines straight inside our status block
                    def log_to_status(msg):
                        status_container.write(msg)

                    try:
                        first_asked, last_asked = split_asked_name(name)
                        person_id = get_first_person_id(driver, name, log_to_status)

                        thesis_id = None
                        if person_id:
                            thesis_id = get_thesis_id_from_person_page(driver, person_id, log_to_status)

                        if not thesis_id:
                            thesis_id = get_fallback_thesis_id(driver, name, log_to_status)

                        if not thesis_id:
                            status_container.write(f"⚠️ Result: **{name}** could not be resolved. Recording as NOT FOUND.")
                            rows.append([first_asked, last_asked, "NOT FOUND", "NOT FOUND", "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", "", "NOT FOUND"])
                            continue

                        xml_text = get_xml_from_thesis_id(thesis_id)
                        if not xml_text:
                            rows.append([first_asked, last_asked, "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", f"https://theses.fr/{thesis_id}", "To be verified by hand (Case 3: XML empty)"])
                            continue

                        row = extract_fields_from_xml(xml_text, name, thesis_id)
                        rows.append(row)
                        status_container.write(f"✅ Successfully extracted data for **{name}**.")

                    except Exception as e:
                        first_asked, last_asked = split_asked_name(name)
                        rows.append([first_asked, last_asked, "ERROR", str(e), "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", "", f"FATAL ERROR: {str(e)}"])
                        status_container.write(f"❌ Error encountered processing **{name}**: {str(e)}")

                    # Chunking compression
                    if index % 20 == 0 or index == total:
                        start_num = ((index - 1) // 20) * 20 + 1
                        end_num = index
                        chunk_rows = rows[start_num - 1 : end_num]
                        
                        df_chunk = pd.DataFrame(chunk_rows, columns=columns)
                        csv_data = df_chunk.to_csv(index=False).encode('utf-8')
                        zip_file.writestr(f"extracted {start_num}-{end_num}.csv", csv_data)

            finally:
                status_container.write("⚙️ Tearing down virtual browser session...")
                driver.quit()
        
        # Change status container look to done when complete
        status_container.update(label="🎉 Pipeline processing sequence finished!", state="complete", expanded=False)
        
    # Show data results outside the status log
    st.success("🎉 Processing sequence completed!")
    df_all = pd.DataFrame(rows, columns=columns)
    st.dataframe(df_all)
    
    st.download_button(
        label="📥 Download Extracted CSVs (ZIP File)",
        data=zip_buffer.getvalue(),
        file_name="theses_extracted_batches.zip",
        mime="application/zip"
    )
elif submit_button:
    st.warning("👈 Please add student names inside the input layout block before running execution pipelines.")
