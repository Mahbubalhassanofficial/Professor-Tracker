import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json

st.title("🔍 Google Sheets Connection Debugger")

try:
    # Load secrets from Streamlit Cloud
    secrets = st.secrets["gcp_service_account"]
    st.write("✅ Secrets loaded successfully.")

    # Show basic fields (not the private key)
    st.write({
        "project_id": secrets["project_id"],
        "client_email": secrets["client_email"]
    })

    # Define scope and credentials
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(dict(secrets), scopes=scope)
    client = gspread.authorize(creds)

    # Your Sheet ID
    SHEET_ID = "1ZB-8UBXCznqP9XzFZdeFYmEzTrDJrO0qrKdy6rVOeF0"
    sheet = client.open_by_key(SHEET_ID)
    worksheet = sheet.sheet1
    st.success(f"✅ Successfully connected! First worksheet: {worksheet.title}")

except Exception as e:
    st.error("❌ Connection failed.")
    st.exception(e)
