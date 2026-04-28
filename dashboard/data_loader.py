"""
data_loader.py – Google Sheets reader for the BI dashboard.

Reads processed lead data from the centralized Google Sheets database
and returns it as a pandas DataFrame for visualization in Streamlit.

Authentication options (checked in order):
  1. GOOGLE_SERVICE_ACCOUNT_JSON env var  – JSON string of service account credentials
  2. service_account.json file in the dashboard directory
  3. ~/.config/gspread/credentials.json   – OAuth credentials (for local dev)
"""

import json
import os
from datetime import datetime
from typing import Optional

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

# ── Constants ─────────────────────────────────────────────────────────────────

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

SHEET_COLUMNS = [
    "Timestamp", "Contact ID", "Call ID", "Contact Name", "Email", "Phone",
    "Country/Region", "Agent", "Call Date", "Outcome", "Raw Notes",
    "Product", "Interest Score", "Intent Level", "Loan Amount",
    "Urgency", "AI Summary", "Is Hot Lead",
    "Email Body", "Email Status", "Subject", "Email Time"
]

NUMERIC_COLS = ["Interest Score", "Loan Amount"]

DATE_COLS = ["Timestamp", "Call Date", "Email Time"]

# ── Main loader ───────────────────────────────────────────────────────────────

def load_leads(spreadsheet_id: str, sheet_name: str = "Leads") -> pd.DataFrame:
    """
    Fetches all lead records from the Google Sheets database.

    Parameters
    ----------
    spreadsheet_id : str
        The Google Sheets document ID (from the URL).
    sheet_name : str
        The worksheet tab name (default: "Leads").

    Returns
    -------
    pd.DataFrame
        Cleaned and typed DataFrame of all processed leads.
    """
    client = _get_gspread_client()
    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.worksheet(sheet_name)

    data = worksheet.get_all_values()
    if len(data) < 2:
        return pd.DataFrame(columns=SHEET_COLUMNS)

    headers = data[0]
    rows = data[1:]
    df = pd.DataFrame(rows, columns=headers)

    return _clean_dataframe(df)


def load_leads_cached(spreadsheet_id: str, sheet_name: str = "Leads") -> pd.DataFrame:
    """
    Streamlit-cache-aware wrapper around load_leads().
    Call this from app.py so Streamlit only re-fetches every 5 minutes.
    """
    return load_leads(spreadsheet_id, sheet_name)


# ── Derived metrics ───────────────────────────────────────────────────────────
def compute_kpis(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "total_leads": 0,
            "hot_leads": 0,
            "warm_leads": 0,
            "cold_leads": 0,
            "avg_score": 0.0,
            "emails_sent": 0,
        }

    intent_col = "Intent Level" if "Intent Level" in df.columns else "Level Intent"
    email_col = "Email Status" if "Email Status" in df.columns else "Email Sent"

    intent = df[intent_col].fillna("").astype(str).str.strip().str.lower()
    hot_mask = intent.str.contains(r"\bhot\b", regex=True)
    warm_mask = intent.str.contains(r"\b(high|medium|warm|lukewarm)\b", regex=True)

    hot_count = int(hot_mask.sum())
    warm_count = int((~hot_mask & warm_mask).sum())
    cold_count = int((~hot_mask & ~warm_mask).sum())

    emails = df[email_col].fillna("").astype(str).str.lower().isin(["sent", "draft"])

    return {
        "total_leads": len(df),
        "hot_leads": hot_count,
        "warm_leads": warm_count,
        "cold_leads": cold_count,
        "avg_score": round(df["Interest Score"].mean(), 1),
        "emails_sent": int(emails.sum()),
    }


def compute_agent_performance(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    agent_col = "Agent Name" if "Agent Name" in df.columns else "Agent"
    intent_col = "Intent Level" if "Intent Level" in df.columns else "Level Intent"
    product_col = "Product Type" if "Product Type" in df.columns else "Product"

    agg = (
        df.groupby(agent_col)
        .agg(
            Total_Calls=("Call ID", "count"),
            Avg_Score=("Interest Score", "mean"),
            Hot_Leads=(intent_col, lambda x: x.fillna("").astype(str).str.lower().str.contains(r"\bhot\b").sum()),
            Warm_Leads=(intent_col, lambda x: x.fillna("").astype(str).str.lower().isin(["high", "medium", "warm", "lukewarm"]).sum()),
            Products=(product_col, lambda x: x.mode().iloc[0] if not x.mode().empty else "N/A"),
        )
        .reset_index()
    )
    agg = agg.rename(columns={agent_col: "Agent Name"})
    agg["Avg_Score"] = agg["Avg_Score"].round(1)
    return agg.sort_values("Avg_Score", ascending=False)


# ── Authentication ─────────────────────────────────────────────────────────────

def _get_gspread_client() -> gspread.Client:
    """Resolves Google credentials and returns an authenticated gspread client."""
    # Option 1: environment variable (for Streamlit Cloud secrets)
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if sa_json:
        creds_dict = json.loads(sa_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        return gspread.authorize(creds)

    # Option 2: local service_account.json file
    local_sa = os.path.join(os.path.dirname(__file__), "service_account.json")
    if os.path.exists(local_sa):
        creds = Credentials.from_service_account_file(local_sa, scopes=SCOPES)
        return gspread.authorize(creds)

    # Option 3: OAuth flow (local dev)
    return gspread.oauth()


# ── Cleaning helpers ───────────────────────────────────────────────────────────

def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Coerces dtypes and fills NaNs for a clean, ready-to-use DataFrame."""
    # Ensure all expected columns are present
    df.columns = df.columns.str.strip()
    for col in SHEET_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[SHEET_COLUMNS].copy()

    # Numeric coercion
    for col in NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # Date coercion
    for col in DATE_COLS:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    # Drop fully empty rows
    df = df.dropna(how="all")
    df['Product Type'] = df.get('Product Type', df.get('Product', ''))
    df['Agent Name'] = df.get('Agent Name', df.get('Agent', ''))
    df['Country/Region'] = df['Country/Region']
    
    return df

