/**
 * Main.gs – Real-Time Streaming Orchestrator
 * Optimized version for log visibility and data persistence.
 */

function doPost(e) {
  const ss = SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID());
  
  // 1. Create or fetch a dedicated sheet for errors/logs
  let logSheet = ss.getSheetByName("System_Logs");
  if (!logSheet) {
    logSheet = ss.insertSheet("System_Logs");
    logSheet.appendRow(["Timestamp", "Event", "Details"]); // Log headers
  }

  try {
    const contents = JSON.parse(e.postData.contents);
    const event = contents[0]; 
    const engagementId = event.objectId;

    // Write the log to the new sheet, not the main one
    logSheet.appendRow([new Date(), "Webhook Received", "ID: " + engagementId]);

    processSingleEvent(event); 

    return ContentService.createTextOutput("Success").setMimeType(ContentService.MimeType.TEXT);

  } catch (err) {
    logSheet.appendRow([new Date(), "ERROR", err.message]);
    return ContentService.createTextOutput("Error").setMimeType(ContentService.MimeType.TEXT);
  }
}

function processSingleEvent(event) {
  const engagementId = String(event.objectId);
  console.log("Processing Call ID: " + engagementId);

  // ==========================================
  // ⚡ SUPER-FAST LOCK (CacheService) to prevent Race Conditions
  // ==========================================
  const cache = CacheService.getScriptCache();
  // Check if there is already a "processing" sign for this ID
  if (cache.get(engagementId) === "processing") {
    console.log("[Skip] Call ID " + engagementId + " is currently executing. Ignoring HubSpot impatience.");
    return;
  }
  // Immediately put up the "processing" sign for 10 minutes (600 seconds)
  cache.put(engagementId, "processing", 600);

  // ==========================================
  // 🛡️ THE MAGIC: Deduplication (Sheet Check for older records)
  // ==========================================
  if (checkIfExists(engagementId)) {
    console.log("[Skip] Call ID " + engagementId + " already processed in Sheet. Ignoring.");
    // Remove the lock just in case
    cache.remove(engagementId);
    return; 
  }
  
  console.log("New call detected. Starting normal process...");
  // ==========================================

  // Wait a bit longer for HubSpot to sync contact names
  console.log("Waiting for HubSpot synchronization...");
  Utilities.sleep(6000); 

  let lead = fetchSingleLeadFromHubSpot(engagementId); 

  // Security check: if the name is Unknown, use the ID to prevent blocking
  if (lead && lead.contactName === "Unknown Contact") {
    console.warn("Unknown contact temporarily, using ID as name.");
    lead.contactName = "ID: " + lead.contactId;
  }

  if (!lead) {
    console.error("CRITICAL: fetchSingleLeadFromHubSpot returned NULL for ID: " + engagementId);
    cache.remove(engagementId); // Clean lock on error
    return;
  }

  // Connection Logic
  const isConnected = String(lead.callOutcome || "").toLowerCase() === "connected";
  console.log("Call status: " + (isConnected ? "CONNECTED" : "NOT CONNECTED"));

  const insights = isConnected ? scoreLeadWithGemini(lead) : _buildNotAnalyzedInsights();

  let outreach = null;
  if (isConnected && shouldSendOutreach(lead, insights)) {
    outreach = sendFollowUpEmail(lead, insights);
  }

  // PERSISTENCE - This is where it gets appended to the Sheet
  try {
    console.log("Attempting to append row to Google Sheets...");
    appendLeadRow(lead, insights, outreach);
    console.log("SUCCESS! Lead saved: " + lead.contactName);
  } catch (sheetErr) {
    console.error("ERROR SAVING TO SHEET: " + sheetErr.message);
  }

  // Optional notification
  if (isConnected) {
    notifyIfHotLead(lead, insights);
  }
}

function _buildNotAnalyzedInsights() {
  return {
    product_type: "N/A",
    interest_score: 0,
    intent_level: "No connection",
    loan_amount: "N/A",
    ai_summary_markdown: "Call not connected. Basic logging performed.",
    suggested_email_body: ""
  };
}