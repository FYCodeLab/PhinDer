# 🎓 Theses.fr Metadata Extraction Pipeline

An automated web scraping application built with **Streamlit** and **Selenium WebDriver** designed to extract researcher profiles and thesis metadata from the official French thesis registry 

This pipeline takes a raw list of student/researcher names, performs real-time browser automation searches, extracts structured XML metadata payloads, and provides partitioned batch downlinks for easy data manipulation.

---

## 🚀 Live Demo
The application is configured for deployment and can be accessed on **Streamlit Community Cloud** via your deployment URL.
[![Phinder App](https://img.shields.io/badge/Phinder-Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://phinder.streamlit.app/)

---

## ✨ Features

- **Form-Secured Input Grid:** Prevents accidental triggers or premature pipeline starts (completely disables unwanted `Ctrl + Enter` text field evaluations).
- **Live Activity Log Terminal:** Displays step-by-step background browser status sequences (navigating links, evaluating IDs, tracing fallbacks) right on the screen using modern `st.status`.
- **Dynamic Live Data Table:** Renders matching results in an updating structured row layout *instantaneously* as names complete parsing.
- **On-the-Fly Emergency Stop:** A master toggle checkbox lets you kill active browser operations gracefully mid-loop without sacrificing data already collected.
- **Automated Chunk Processing:** Automatically aggregates, packages, and compresses tables into batch-partitioned CSV files wrapped in a high-speed `.zip` archive.

---

## 🛠️ Repository File Architecture

To function accurately on Streamlit Cloud containers, your repository must contain these three core components:

```text
├── streamlit_app.py      # The master Streamlit dashboard & core Selenium logic
├── packages.txt          # Defines system-level headless Debian Linux binaries
└── README.md             # Project documentation and pipeline guide
