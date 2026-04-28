"""
app.py – Streamlit BI Dashboard (Phase 4)
Automated Lead Scoring & Outreach System

Pages:
  1. 📊 KPI Dashboard & Conversion Funnel
  2. 🏆 Agent Performance
  3. 📋 Lead Explorer
  4. 🤖 Talk to your Data (AI Assistant)

Configuration via .env or Streamlit Secrets:
  SPREADSHEET_ID          – Google Sheets document ID
  GEMINI_API_KEY          – Google AI Studio API key
  GOOGLE_SERVICE_ACCOUNT_JSON – Service account credentials (JSON string)
"""

import os
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from ai_chat import create_chat_response
from data_loader import compute_agent_performance, compute_kpis, load_leads_cached

# ── Environment ───────────────────────────────────────────────────────────────

load_dotenv()

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Lead Scoring & Call Analytics Dashboard",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Helper: load config ───────────────────────────────────────────────────────

def _get_config() -> dict:
    """Reads configuration from Streamlit secrets or environment variables."""
    try:
        spreadsheet_id = st.secrets.get("SPREADSHEET_ID") or os.environ.get("SPREADSHEET_ID", "")
        gemini_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
        sa_json = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON") or os.environ.get(
            "GOOGLE_SERVICE_ACCOUNT_JSON", ""
        )
    except Exception:
        spreadsheet_id = os.environ.get("SPREADSHEET_ID", "")
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")

    # Inject service account into env so data_loader.py picks it up
    if sa_json and not os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"):
        os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"] = sa_json

    return {"spreadsheet_id": spreadsheet_id, "gemini_key": gemini_key}


# ── Helper: load data ─────────────────────────────────────────────────────────
@st.cache_data(ttl=900)  # Refresh every 15 minutes
def _load_data(spreadsheet_id: str) -> pd.DataFrame:
    # 1. Load raw data from the script that connects to Google Sheets
    df = load_leads_cached(spreadsheet_id)
    
    # 2. COLUMN MAPPING (Based on actual Google Sheets column names)
    # Left: Exact column name in Google Sheets | Right: Name used by app.py
    column_map = {
        'Intent Level': 'Intent Level',   # In your sheet this column is "Intent Level"
        'Interest Score': 'Interest Score', 
        'Product': 'Product Type',       # In your sheet this column is "Product"
        'Contact Name': 'Contact Name',
        'Agent': 'Agent Name',           # In your sheet this column is "Agent"
        'Loan Amount': 'Loan Amount',
        'AI Summary': 'AI Summary',
        'Urgency': 'Urgency Indicators',
        'Email Status': 'Email Sent',
        'Subject': 'Email Subject',
    }
    
    # Create aliases only when the target column is missing.
    # This keeps original names required by data_loader KPI functions.
    for source_col, target_col in column_map.items():
        if source_col in df.columns and target_col not in df.columns:
            df[target_col] = df[source_col]

    # Ensure core columns exist so dashboard pages never crash on missing fields.
    required_defaults = {
        "Call Date": pd.NaT,
        "Interest Score": 0,
        "Loan Amount": 0,
        "Intent Level": "Low",
        "Product Type": "Unknown",
        "Agent Name": "Unknown",
        "Contact Name": "Unknown",
        "Country/Region": "N/A",
    }
    for col, default_value in required_defaults.items():
        if col not in df.columns:
            df[col] = default_value

    # 3. DATA CLEANUP (Essential to prevent chart errors)
    if not df.empty:
        # Asegurar fechas y números...
        df['Call Date'] = pd.to_datetime(df['Call Date'], errors='coerce')
        df['Interest Score'] = pd.to_numeric(df['Interest Score'], errors='coerce').fillna(0)
        df['Loan Amount'] = pd.to_numeric(df['Loan Amount'], errors='coerce').fillna(0)
        
        # ELIMINAR ESPACIOS EN BLANCO Y ESTANDARIZAR FORMATO PARA QUE NO FALLE EL CONTEO
        if 'Intent Level' in df.columns:
            df['Intent Level'] = df['Intent Level'].astype(str).str.strip().str.title()

    return df


# ── Sidebar ───────────────────────────────────────────────────────────────────

def _render_sidebar(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.image(
        "https://img.icons8.com/fluency/96/bank-building.png",
        width=60,
    )
    st.sidebar.title("Lead Scoring & Call Analytics Dashboard")
    st.sidebar.caption("Non-QM Mortgage Intelligence")
    st.sidebar.divider()

    # Date range filter
    st.sidebar.subheader("📅 Date Range")
    min_date = df["Call Date"].min() if not df.empty else datetime.today() - timedelta(days=30)
    max_date = df["Call Date"].max() if not df.empty else datetime.today()

    if pd.isna(min_date):
        min_date = datetime.today() - timedelta(days=30)
    if pd.isna(max_date):
        max_date = datetime.today()

    date_from = st.sidebar.date_input("From", value=min_date)
    date_to = st.sidebar.date_input("To", value=max_date)

    # Product filter
    st.sidebar.subheader("🏷️ Product Type")
    products = ["All"] + sorted(df["Product Type"].dropna().unique().tolist()) if not df.empty else ["All"]
    selected_product = st.sidebar.selectbox("Select product", products)

    # Agent filter
    st.sidebar.subheader("👤 Agent")
    agents = ["All"] + sorted(df["Agent Name"].dropna().unique().tolist()) if not df.empty else ["All"]
    selected_agent = st.sidebar.selectbox("Select agent", agents)

    # Intent filter
    st.sidebar.subheader("🎯 Intent Level")
    intents = st.sidebar.multiselect(
        "Select intent levels",
        options=["Hot", "High", "Medium", "Low"], # <--- Your actual intent categories
        default=["Hot", "High", "Medium", "Low"],
    )

    st.sidebar.divider()
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.caption(f"Last refresh: {datetime.now().strftime('%H:%M:%S')}")

    # Apply filters
    filtered = df.copy()
    if not df.empty:
        filtered = filtered[
            (filtered["Call Date"].dt.date >= date_from) &
            (filtered["Call Date"].dt.date <= date_to)
        ]
        if selected_product != "All":
            filtered = filtered[filtered["Product Type"] == selected_product]
        if selected_agent != "All":
            filtered = filtered[filtered["Agent Name"] == selected_agent]
        if intents:
            filtered = filtered[filtered["Intent Level"].isin(intents)]

    return filtered


# ── Page 1: KPI Dashboard ─────────────────────────────────────────────────────

def _page_kpi_dashboard(df: pd.DataFrame):
    st.header("📊 KPI Dashboard & Conversion Funnel")

    kpis = compute_kpis(df)

    # ── KPI metric cards ──
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total Leads", kpis["total_leads"])
    col2.metric("🔥 Hot Leads", kpis["hot_leads"])
    col3.metric("🌡️ Warm Leads", kpis["warm_leads"])
    col4.metric("❄️ Cold/Lukewarm", kpis["cold_leads"])
    col5.metric("Avg Score", f"{kpis['avg_score']}/100")
    col6.metric("Emails Sent/Drafted", kpis["emails_sent"])

    st.divider()

    if df.empty:
        st.info("No data available for the selected filters.")
        return

    col_left, col_right = st.columns(2)

    # ── Conversion Funnel ──
    with col_left:
        st.subheader("Conversion Funnel")
        funnel_data = pd.DataFrame({
            "Stage": ["All Calls", "Lukewarm+", "Warm+", "Hot Leads"],
            "Count": [
                kpis["total_leads"],
                kpis["total_leads"] - kpis["cold_leads"],
                kpis["warm_leads"] + kpis["hot_leads"],
                kpis["hot_leads"],
            ],
        })
        fig_funnel = go.Figure()
        fig_funnel.add_trace(
            go.Funnel(
                y=funnel_data["Stage"],
                x=funnel_data["Count"],
                textposition="inside",
                textinfo="value+percent initial",
                marker={"color": ["#1a73e8", "#0d9488", "#f59e0b", "#ef4444"]},
            )
        )
        fig_funnel.update_layout(
            height=350, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_funnel, use_container_width=True)

    # ── Score Distribution ──
    with col_right:
        st.subheader("Interest Score Distribution")
        fig_hist = px.histogram(
            df,
            x="Interest Score",
            nbins=20,
            color_discrete_sequence=["#1a73e8"],
            labels={"Interest Score": "Score (0–100)"},
        )
        fig_hist.add_vline(
            x=80, line_dash="dash", line_color="#ef4444",
            annotation_text="Hot Lead threshold", annotation_position="top right"
        )
        fig_hist.update_layout(
            height=350, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    st.divider()

    col_l2, col_r2 = st.columns(2)

    # ── Product Type Distribution ──
    with col_l2:
        st.subheader("Leads by Product Type")
        product_counts = df["Product Type"].value_counts().reset_index()
        product_counts.columns = ["Product", "Count"]
        fig_pie = px.pie(
            product_counts,
            names="Product",
            values="Count",
            color_discrete_sequence=px.colors.qualitative.Set2,
            hole=0.4,
        )
        fig_pie.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)

    # ── Leads Over Time ──
    with col_r2:
        st.subheader("Leads Processed Over Time")
        df_time = df.copy()
        df_time["Call Date"] = df_time["Call Date"].dt.date
        daily = df_time.groupby(["Call Date", "Intent Level"]).size().reset_index(name="Count")
        fig_line = px.bar(
            daily,
            x="Call Date",
            y="Count",
            color="Intent Level",
            color_discrete_map={
                "Hot": "#ef4444",    # Rojo para Hot
                "High": "#f59e0b",   # Naranja para High
                "Medium": "#3b82f6", # Azul para Medium
                "Low": "#6b7280",    # Gris para Low
            },
            barmode="stack",
        )
        fig_line.update_layout(
            height=350, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_line, use_container_width=True)

    st.divider()

    st.subheader("Outbound Calls by Outcome")
    desired_outcomes = ["Busy", "Connected", "No Answer", "Wrong Number"]

    if "Outcome" in df.columns:
        outcome_series = (
            df["Outcome"]
            .astype(str)
            .str.strip()
            .replace({"": "Unknown"})
        )

        outcome_counts = (
            outcome_series
            .value_counts()
            .reindex(desired_outcomes, fill_value=0)
            .reset_index()
        )
        outcome_counts.columns = ["Outcome", "Count"]

        fig_outcome = px.bar(
            outcome_counts,
            x="Outcome",
            y="Count",
            color="Outcome",
            text="Count",
            color_discrete_map={
                "Busy": "#6b7280",
                "Connected": "#10b981",
                "No Answer": "#f59e0b",
                "Wrong Number": "#ef4444",
            },
        )
        fig_outcome.update_traces(textposition="outside")
        fig_outcome.update_layout(
            height=320,
            margin=dict(l=0, r=0, t=10, b=0),
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_outcome, use_container_width=True)
    else:
        st.info("Outcome column not available in current data.")


# ── Page 2: Agent Performance ─────────────────────────────────────────────────

def _page_agent_performance(df: pd.DataFrame):
    st.header("🏆 Agent Performance")

    if df.empty:
        st.info("No data available for the selected filters.")
        return

    agent_df = compute_agent_performance(df)

    if agent_df.empty:
        st.info("Not enough data to compute agent performance.")
        return

    # Scorecard table
    st.subheader("Agent Scorecard")
    st.dataframe(
        agent_df.rename(columns={
            "Agent Name": "Agent",
            "Total_Calls": "Total Calls",
            "Avg_Score": "Avg Score",
            "Hot_Leads": "Hot Leads",
            "Warm_Leads": "Warm Leads",
            "Products": "Top Product",
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Average Score by Agent")
        fig_bar = px.bar(
            agent_df.sort_values("Avg_Score"),
            x="Avg_Score",
            y="Agent Name",
            orientation="h",
            color="Avg_Score",
            color_continuous_scale=["#6b7280", "#f59e0b", "#ef4444"],
            labels={"Avg_Score": "Average Score", "Agent Name": ""},
        )
        fig_bar.update_layout(
            height=max(300, len(agent_df) * 40),
            margin=dict(l=0, r=0, t=10, b=0),
            coloraxis_showscale=False,
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col2:
        st.subheader("Hot Lead Conversion by Agent")
        agent_df["Conversion Rate"] = (
            (agent_df["Hot_Leads"] / agent_df["Total_Calls"]) * 100
        ).round(1)
        fig_conv = px.bar(
            agent_df.sort_values("Conversion Rate"),
            x="Conversion Rate",
            y="Agent Name",
            orientation="h",
            color="Conversion Rate",
            color_continuous_scale=["#6b7280", "#f59e0b", "#ef4444"],
            labels={"Conversion Rate": "Hot Lead Rate (%)", "Agent Name": ""},
        )
        fig_conv.update_layout(
            height=max(300, len(agent_df) * 40),
            margin=dict(l=0, r=0, t=10, b=0),
            coloraxis_showscale=False,
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_conv, use_container_width=True)

    # Score trend over time per agent
    st.subheader("Score Trend Over Time")
    df_trend = df.copy()
    df_trend["Week"] = df_trend["Call Date"].dt.to_period("W").astype(str)
    trend = df_trend.groupby(["Week", "Agent Name"])["Interest Score"].mean().reset_index()
    trend.columns = ["Week", "Agent", "Avg Score"]
    fig_trend = px.line(
        trend,
        x="Week",
        y="Avg Score",
        color="Agent",
        markers=True,
        labels={"Avg Score": "Average Interest Score"},
    )
    fig_trend.update_layout(
        height=400,
        margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_trend, use_container_width=True)


# ── Page 3: Lead Explorer ─────────────────────────────────────────────────────

def _page_lead_explorer(df: pd.DataFrame):
    st.header("📋 Lead Explorer")

    if df.empty:
        st.info("No leads match your current filters.")
        return

    # Compact search
    search = st.text_input("🔍 Search by name, product, state, or notes", "")
    if search:
        mask = df.apply(
            lambda row: any(
                search.lower() in str(val).lower()
                for val in [row.get("Contact Name", ""), row.get("Product Type", ""),
                            row.get("Country/Region", ""), row.get("Raw Notes", "")]
            ),
            axis=1,
        )
        df = df[mask]

    # Display columns
    display_cols = [
        "Contact Name", "Agent Name", "Call Date", "Product Type",
        "Interest Score", "Intent Level", "Loan Amount", "Country/Region",
        "Email Sent",
    ]
    available_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(
        df[available_cols].sort_values("Interest Score", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

    st.caption(f"Showing {len(df)} leads")

    # Detail expander
    st.subheader("Lead Detail")
    if not df.empty:
        selected_name = st.selectbox(
            "Select a lead to view full details",
            df["Contact Name"].tolist(),
        )
        lead_row = df[df["Contact Name"] == selected_name].iloc[0]

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Interest Score", f"{lead_row.get('Interest Score', 0)}/100")
            st.write(f"**Product:** {lead_row.get('Product Type', 'N/A')}")
            st.write(f"**Intent:** {lead_row.get('Intent Level', 'N/A')}")
            st.write(f"**Agent:** {lead_row.get('Agent Name', 'N/A')}")
            st.write(f"**Loan Amount:** {lead_row.get('Loan Amount', 'N/A')}")
            st.write(f"**Country/Region:** {lead_row.get('Country/Region', 'N/A')}")
            st.write(f"**Urgency Signals:** {lead_row.get('Urgency Indicators', 'N/A')}")
        with col2:
            st.write("**AI Summary:**")
            st.markdown(lead_row.get("AI Summary", "_No summary available_"))
            st.write("**Email Status:**", lead_row.get("Email Sent", "N/A"))
            st.write("**Email Subject:**", lead_row.get("Email Subject", "N/A"))

        with st.expander("📞 Raw Call Notes"):
            st.write(lead_row.get("Raw Notes", "No notes available."))


# ── Page 4: AI Chat ───────────────────────────────────────────────────────────

def _page_ai_chat(df: pd.DataFrame, gemini_key: str):
    st.header("🤖 Talk to your Data – AI Assistant")
    st.caption(
        "Ask natural language questions about your leads. "
        "The AI understands mortgage concepts semantically – "
        "try asking about 'loans for foreigners' or 'self-employed investors'."
    )

    if not gemini_key:
        st.error(
            "GEMINI_API_KEY is not configured. "
            "Add it to your .env file or Streamlit secrets to enable the AI assistant."
        )
        return

    # Initialise chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Render existing messages
    for role, message in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(message)

    # Suggested questions
    if not st.session_state.chat_history:
        st.subheader("💡 Try asking:")
        suggestions = [
            "How many hot leads do we have this week?",
            "Which agent has the highest average score?",
            "Show me all loans for foreigners",
            "What products are most popular in Texas?",
            "Which DSCR leads have the highest urgency?",
        ]
        cols = st.columns(len(suggestions))
        for i, suggestion in enumerate(suggestions):
            if cols[i].button(suggestion, key=f"suggest_{i}"):
                _process_chat_message(suggestion, df, gemini_key)
                st.rerun()

    # Chat input
    user_input = st.chat_input("Ask a question about your leads...")
    if user_input:
        _process_chat_message(user_input, df, gemini_key)
        st.rerun()

    if st.button("🗑️ Clear chat history"):
        st.session_state.chat_history = []
        st.rerun()


def _process_chat_message(message: str, df: pd.DataFrame, gemini_key: str):
    """Adds a user message, calls the AI, and stores the response."""
    st.session_state.chat_history.append(("user", message))

    with st.spinner("Thinking..."):
        response = create_chat_response(
            question=message,
            df=df,
            api_key=gemini_key,
            chat_history=st.session_state.chat_history,
        )

    st.session_state.chat_history.append(("assistant", response))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    config = _get_config()

    # ── Configuration check ──
    if not config["spreadsheet_id"]:
        st.error(
            "⚠️ **SPREADSHEET_ID is not configured.**\n\n"
            "Create a `.env` file in the `dashboard/` directory with:\n"
            "```\n"
            "SPREADSHEET_ID=your_google_sheet_id\n"
            "GEMINI_API_KEY=your_gemini_api_key\n"
            "GOOGLE_SERVICE_ACCOUNT_JSON={...}\n"
            "```\n"
            "Or configure Streamlit secrets for cloud deployment."
        )
        st.stop()

    # ── Load data ──
    with st.spinner("Loading leads data..."):
        try:
            df = _load_data(config["spreadsheet_id"])
        except Exception as e:
            st.error(f"❌ Failed to load data: {e}")
            st.info(
                "Check that your Google credentials are correctly configured "
                "and the service account has read access to the spreadsheet."
            )
            st.stop()

    # ── Sidebar filters ──
    filtered_df = _render_sidebar(df)

    # ── Navigation tabs ──
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 KPI Dashboard",
        "🏆 Agent Performance",
        "📋 Lead Explorer",
        "🤖 AI Assistant",
    ])

    with tab1:
        _page_kpi_dashboard(filtered_df)
    with tab2:
        _page_agent_performance(filtered_df)
    with tab3:
        _page_lead_explorer(filtered_df)
    with tab4:
        _page_ai_chat(filtered_df, config["gemini_key"])


if __name__ == "__main__":
    main()
