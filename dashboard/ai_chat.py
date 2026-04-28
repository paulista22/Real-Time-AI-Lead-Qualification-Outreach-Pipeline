"""
ai_chat.py – Gemini-powered "Talk to your Data" assistant.
Synchronized with Google Sheets columns and optimized for mortgage sales intelligence.
"""

import json
import os
from typing import Optional
import pandas as pd
from google import genai
from google.genai import types

# ── Gemini configuration ──────────────────────────────────────────────────────

GEMINI_MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = """You are an expert mortgage sales intelligence assistant embedded in a BI dashboard.
Your goal is to analyze lead data and provide actionable insights for mortgage managers.

Knowledge Base (Non-QM Products):
- DSCR: Investment property loans based on rental income.
- ITIN: Loans for borrowers using an ITIN instead of an SSN.
- Foreign National: Mortgages for non-US residents/citizens.
- Bank Statement/Alt Doc: Loans for self-employed using alternative documentation.

Guidelines:
1. Interpret queries semantically: "investors" = DSCR, "foreigners" = Foreign National, etc.
2. Provide concise, professional answers using Markdown formatting.
3. If specific figures (Loan Amounts, Scores) are requested, extract them accurately from the data.
"""

def create_chat_response(
    question: str,
    df: pd.DataFrame,
    api_key: str,
    chat_history: Optional[list] = None,
) -> str:
    """Generates a Gemini AI response based on the leads DataFrame context."""
    
    if not api_key:
        return "⚠️ Error: GEMINI_API_KEY not found in .env file."

    client = genai.Client(api_key=api_key)

    # Build the compact data context (JSON summary)
    data_context = _build_data_context(df)

    # Compose the prompt with data context and user question
    prompt = f"""## Current Leads Data Summary
{data_context}

## Manager Question
{question}"""

    # Handle conversation history for context-aware chat
    history: list[types.Content] = []
    if chat_history:
        for role, text in chat_history[:-1]:
            history.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=text)],
                )
            )

    try:
        chat = client.chats.create(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.3, # Low temperature for higher factual accuracy
                max_output_tokens=1024,
            ),
            history=history,
        )
        response = chat.send_message(prompt)
        return response.text
    except Exception as exc:
        return f"⚠️ AI assistant error: {exc}"


def _build_data_context(df: pd.DataFrame) -> str:
    """Builds a compact JSON summary of the DataFrame for prompt injection."""
    
    if df.empty:
        return "No data available yet."

    # These columns MUST match the mapping in your data_loader.py
    safe_cols = [
        "Contact Name", "Agent Name", "Call Date", 
        "Product Type", "Interest Score", "Intent Level", 
        "Loan Amount", "Country/Region", "Email Status"
    ]
    
    # Filter only existing columns to avoid KeyErrors
    available = [c for c in safe_cols if c in df.columns]
    subset = df[available].copy()

    # Clean dates for JSON serialization
    for col in subset.select_dtypes(include=["datetime64[ns]", "datetimetz"]):
        subset[col] = subset[col].dt.strftime("%Y-%m-%d").fillna("N/A")

    # Limit to 150 records to stay within token limits while providing context
    subset_sample = subset.tail(150)

    # Safe Date Range calculation
    try:
        valid_dates = df["Call Date"].dropna()
        date_from = str(valid_dates.min().date()) if not valid_dates.empty else "N/A"
        date_to = str(valid_dates.max().date()) if not valid_dates.empty else "N/A"
    except:
        date_from, date_to = "N/A", "N/A"

    summary = {
        "total_records": len(df),
        "date_range": {
            "from": date_from,
            "to": date_to,
        },
        "score_stats": {
            "mean": round(df["Interest Score"].mean(), 1) if "Interest Score" in df.columns else 0,
            "max": int(df["Interest Score"].max()) if "Interest Score" in df.columns else 0,
        },
        "product_distribution": df["Product Type"].value_counts().to_dict() if "Product Type" in df.columns else {},
        "intent_distribution": df["Intent Level"].value_counts().to_dict() if "Intent Level" in df.columns else {},
        "records_sample": json.loads(subset_sample.to_json(orient="records")),
    }

    return json.dumps(summary, indent=2, default=str)