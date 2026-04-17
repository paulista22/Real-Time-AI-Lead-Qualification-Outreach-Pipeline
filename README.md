# 🚀 Real Time AI Lead Qualification and Outreach Pipeline

A high-performance, event-driven automation pipeline for mortgage broker lead qualification. This system transitions from legacy polling to **Real-Time Streaming** using HubSpot Webhooks and Google Apps Script (GAS) to provide instant AI scoring and outreach. ⚡📈
---

## 🎯 Project Overview
This project automates the journey from a **HubSpot** engagement to a qualified sales opportunity in seconds. 

Unlike traditional time-based triggers, this architecture is **Data-Driven**: the moment a call is logged or a lead is updated in HubSpot, a Webhook triggers the pipeline.

The pipeline ingests call data, normalizes notes, scores and classifies leads with **Gemini AI**, stores structured outputs in **Google Sheets**, sends hot-lead alerts via **Telegram**, and creates **Gmail** follow-up drafts for qualified opportunities before the recruiter or agent even closes the CRM tab. 🤖

A **Streamlit** dashboard provides KPI tracking, outbound call outcome analysis, and a conversational AI interface for natural language queries. 📊

---

## 💼 Business Problem

High-volume mortgage sales teams need a repeatable way to process and prioritize broker calls. 📈

Manual handling causes:
- ⏳ **Delayed qualification** of high-intent opportunities.
- ⚖️ **Inconsistent lead scoring** and follow-up decisions.
- 🔔 **Slow manager visibility** for urgent leads.
- 📉 **Limited analytics** for product demand, agent performance, and call outcomes.

This solution standardizes and accelerates the process with AI-assisted scoring and automated workflow orchestration. ✅

---

## 🏗️ Architecture

The pipeline follows a modern "Push" architecture:

1.  **Event (HubSpot):** A call is completed or a contact property changes.
2.  **Webhook (Transport):** HubSpot sends a real-time JSON payload to a dedicated GAS Endpoint.
3.  **Ingestion Layer (`doPost`):** Google Apps Script receives the stream, parses the data, and validates the event.
4.  **Intelligence Layer (Gemini):** Real-time NLP analysis for interest scoring and product matching.
5.  **Action Layer:** Instant Telegram notifications and automated Gmail drafting.
6.  **Analytics and Decision Layer**: An interactive Business Intelligence Dashboard with an AI assistant. 

---

## 🖼️ Project Diagram 

![Project Workflow](https://github.com/user-attachments/assets/0f352955-a7b9-4b89-8912-3ce705e3cee2)

---

## 🛠️ Methodology: The Data-Driven Shift

### 🔹 Phase 1: Real-Time Ingestion (The `doPost` Engine)
*Trigger: HTTP POST Webhook (Instant).* 🚀

- **Endpoint:** Deployed Google Apps Script Web App.
- **Function:** `doPost(e)` acts as a listener for HubSpot's server-side events.
- **Payload Parsing:** Extracts `objectId`, `propertyName`, and `propertyValue` dynamically.
- **Zero Latency:** Eliminates the 15-minute wait time, ensuring "Hot Leads" are handled while they are still on the mind of the agent.

### 🔹 Phase 2: Conditional AI Processing
*Model: Gemini 2.5 Flash.* 🧠

The pipeline uses conditional logic to ensure API efficiency:
- **Interaction Filter:** Only "Connected" or "Meaningful" status updates trigger the Gemini LLM.
- **Expert Analysis:** The model acts as a **Non-QM Mortgage Expert**, classifying leads into:
    - 🔥 **Hot (80-100):** Immediate transaction intent.
    - ⚡ **Warm (60-79):** Strong product fit.
    - 🌱 **Interested (30-59):** Future potential.

### 🔹 Phase 3: Instant Outreach & Persistence
- **Telegram Alert:** Dispatched in **<2 seconds** for scores >= 80.
- **Gmail Automation:** Smart drafts created for scores >= 40 using personalized AI templates.
- **Data Log:** Every event is streamed into **Google Sheets** for historical record-keeping and ETL processing.

### 🔹 Phase 4: Analytics and Visualization
*Dashboard layer: Streamlit (Python).* 💻
<img width="1906" height="923" alt="a94d1d17-fec8-4ff6-b7be-81b3639e362b" src="https://github.com/user-attachments/assets/3b5b2348-0628-4524-a399-b805f85c249e" />


**KPI Dashboard:**
- 📌 Live KPI's; `Total Leads`, `Hot/Warm/Cold` distribution, `Average Interest Score`, and `Automation Volume` (Emails drafted/sent).
- 📈 Lead conversion funnel (calls -> qualified -> hot).
- 📊 Interest score distribution, Leads Proces Over Time and Product demand pie charts.
- 📞 Outbound Calls by Outcome analysis.

---

## 🧰 Skills and Tools Applied

| Category | Tool/Framework | Purpose |
|---|---|---|
| **Streaming** | HubSpot Webhooks | Event-driven data source |
| **Orchestration** | GAS (`doPost` Method) | Real-time middleware & ETL |
| **AI/ML** | Gemini 2.5 Flash API | Lead scoring and NLP |
| **Messaging** | Telegram Bot API | Instant "Hot Lead" notifications |
| **Email** | Gmail API | Draft/send follow-up emails |
| **Database** | Google Sheets | Central repository |
| **Dashboard** | Streamlit (Python) | Interactive KPI visualization |

---

## 🔐 Security and Data Governance

- **Credentials:** Managed via Apps Script Script Properties and environment variables. 🛡️
- **Confidentiality:** Data processed through this API is **not** used to train public Google models. 🔒
- **Resilience:** Built-in error handling (try-catch) and Mazatlan timezone (GMT-7) support. 🕒

---

## 🏆 Results

This pipeline delivers:
- ✅ **Scalability** The doPost architecture handles concurrent events without manual triggers.
- ✅ **Faster identification** of high-intent leads.
- ✅ **Consistent** and auditable scoring decisions.
- ✅ **Immediate visibility** through real-time alerting.
- ✅ **Higher efficiency** via AI-generated outreach drafts.
- ✅ **Centralized tracking** and analytics in one dashboard.

---

## 🔗 Dashboard Link

- 🌐 **Dashboard URL:** `https://mlk6lubyq5heayck77lego.streamlit.app/ `

---

## 📄 License
MIT
