import streamlit as st
import pandas as pd
import io
import zipfile
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# =====================================================================
# 1. WEB DRIVER & SYSTEM SETUP
# =====================================================================

def get_driver():
    """Sets up a headless Chromium driver compatible with Streamlit Cloud."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # Standard location for Chromium on Debian/Streamlit Cloud
    options.binary_location = "/usr/bin/chromium"
    
    return webdriver.Chrome(options=options)

# =====================================================================
# 2. SCRAPING & UTILITY HELPER FUNCTIONS
# =====================================================================
# Note: Ensure these functions match your target website's layout (e.g., theses.fr)

def clean_whitespace(text):
    """Cleans up tabs, newlines, and trailing spaces from input text."""
    return " ".join(text.split())

def split_asked_name(name):
    """Splits a full name string into a tentative First and Last name."""
    parts = name.strip().split(maxsplit=1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return name, ""

def get_first_person_id(driver, name, log_callback):
    """Searches for a person and returns their unique ID."""
    log_callback(f"🔍 Searching for researcher ID: {name}...")
    # TODO: Add your Selenium code to search the site and extract the person ID
    # Example return: "012345678"
    return None 

def get_thesis_id_from_person_page(driver, person_id, log_callback):
    """Navigates to a person's page to extract their thesis ID."""
    log_callback(f"📄 Checking researcher profile {person_id}...")
    # TODO: Add your Selenium code to extract the thesis ID from their profile page
    return None

def get_fallback_thesis_id(driver, name, log_callback):
    """Fallback search strategy if direct profile lookup fails."""
    log_callback(f"⚠️ Direct profile not found. Trying fallback search for: {name}...")
    # TODO: Add your fallback Selenium search logic here
    return None

def get_xml_from_thesis_id(thesis_id):
    """Fetches metadata XML using the thesis ID via an API or HTTP request."""
    # TODO: Replace with your actual URL/API structure if fetching metadata XML
    try:
        url = f"https://theses.fr/{thesis_id}.xml"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.text
    except Exception:
        pass
    return None

def extract_fields_from_xml(xml_text, name, thesis_id):
    """Parses the XML string and maps data into the final row format."""
    # TODO: Replace with your actual XML parsing logic (e.g., using BeautifulSoup or ElementTree)
    first_asked, last_asked = split_asked_name(name)
    
    # Placeholder structure mapping to your columns layout
    return [
        first_asked,           # First name asked
        last_asked,            # Last name asked
        "ExtractedFirst",      # First name extracted (Parsed from XML)
        "ExtractedLast",       # Last name extracted (Parsed from XML)
        "Sample Thesis Title", # Thesis Title
        "2026-06-02",          # Defense Date
        "Ongoing",             # Start Date
        "Sample Org",          # Organization
        "Sample University",   # University
        f"https://theses.fr/{thesis_id}", # URL
        "Success (XML Parsed)" # Pipeline Status Tracking
    ]

# =====================================================================
# 3. USER INTERFACE (STREAMLIT)
# =====================================================================

st.title("🎓 Thesis Extraction Pipeline")
st.markdown("Use this tool to automatically look up metadata from student name lists.")

# A large text box for copying and pasting names directly
names_input = st.text_area(
    label="📋 Paste your students list here (One student per line)",
    placeholder="Jean Dupont\nMarie Martin\nPierre Durand",
    height=250
)

if names_input.strip():
    # Split the pasted text line-by-line, discarding empty lines
    raw_names = [line.strip() for line in names_input.splitlines() if line.strip()]
    total = len(raw_names)
    
    st.info(f"📋 Detected **{total}** names ready for extraction.")
    
    if st.button("🚀 Start Web Scraping Pipeline"):
        rows = []
        columns = [
            "First name asked", "Last name asked", "First name extracted", "Last name extracted",
            "Thesis Title", "Defense Date", "Start Date (Uncompleted)", "Organization", "University", "URL", "Pipeline Status Tracking"
        ]
        
        # Setup UI placeholders
        progress_bar = st.progress(0)
        status_text = st.empty()
        log_box = st.empty()
        
        # In-memory zip storage to hold CSV chunks
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            
            status_text.text("Launching background browser context...")
            
            try:
                driver = get_driver()
            except Exception as driver_err:
                st.error(f"Failed to launch Chromium: {driver_err}")
                st.stop()
            
            try:
                for index, raw_name in enumerate(raw_names, start=1):
                    # clean_whitespace takes care of tabs (\t) and multiple spaces
                    name = clean_whitespace(raw_name)
                    progress_bar.progress(index / total)
                    status_text.markdown(f"**Processing ({index}/{total}):** {name}")
                    
                    def log_to_screen(msg):
                        log_box.markdown(msg)

                    try:
                        first_asked, last_asked = split_asked_name(name)
                        person_id = get_first_person_id(driver, name, log_to_screen)

                        thesis_id = None
                        if person_id:
                            thesis_id = get_thesis_id_from_person_page(driver, person_id, log_to_screen)

                        if not thesis_id:
                            thesis_id = get_fallback_thesis_id(driver, name, log_to_screen)

                        if not thesis_id:
                            rows.append([first_asked, last_asked, "NOT FOUND", "NOT FOUND", "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", "", "NOT FOUND"])
                            continue

                        xml_text = get_xml_from_thesis_id(thesis_id)
                        if not xml_text:
                            rows.append([first_asked, last_asked, "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", f"https://theses.fr/{thesis_id}", "To be verified by hand (Case 3: XML empty)"])
                            continue

                        row = extract_fields_from_xml(xml_text, name, thesis_id)
                        rows.append(row)

                    except Exception as e:
                        first_asked, last_asked = split_asked_name(name)
                        rows.append([first_asked, last_asked, "ERROR", str(e), "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", "NON ACCESSIBLE", "", f"FATAL ERROR: {str(e)}"])

                    # LIVE CHUNK ZIP GENERATION (Every 20 entries or absolute end)
                    if index % 20 == 0 or index == total:
                        start_num = ((index - 1) // 20) * 20 + 1
                        end_num = index
                        chunk_rows = rows[start_num - 1 : end_num]
                        
                        df_chunk = pd.DataFrame(chunk_rows, columns=columns)
                        csv_data = df_chunk.to_csv(index=False).encode('utf-8')
                        
                        # Pack the CSV chunk straight into the zip container
                        zip_file.writestr(f"extracted {start_num}-{end_num}.csv", csv_data)
                        st.toast(f"Saved package: extracted {start_num}-{end_num}.csv")

            finally:
                driver.quit()
                
        status_text.success("🎉 Extraction complete!")
        progress_bar.empty()
        log_box.empty()
        
        # Show a master preview of everything extracted
        df_all = pd.DataFrame(rows, columns=columns)
        st.dataframe(df_all)
        
        # Download button for the zipped split packages
        st.download_button(
            label="📥 Download Extracted CSVs (ZIP File)",
            data=zip_buffer.getvalue(),
            file_name="theses_extracted_batches.zip",
            mime="application/zip"
        )
else:
    st.warning("👈 Please copy and paste your student names into the text field above to unlock the extraction pipeline.")
