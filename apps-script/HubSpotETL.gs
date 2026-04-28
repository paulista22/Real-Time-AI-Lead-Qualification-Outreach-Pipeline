/**
 * HubSpotETL.gs – Streaming Version
 * Processes individual records in real-time via Webhook IDs.
 */

/**
 * Main entry point called by Main.gs
 * @param {string} engagementId The ID provided by the HubSpot Webhook payload.
 * @return {Object|null} Normalised lead object or null if invalid.
 */
function fetchSingleLeadFromHubSpot(engagementId) {
  console.log("[HubSpotETL] Fetching specific call ID: " + engagementId); // Cambiado a console

  const callRecord = _fetchSingleCall(engagementId);
  
  if (!callRecord) {
    console.error("[HubSpotETL] Call record not found or API error.");
    return null;
  }

  try {
    const lead = _normaliseCallRecord(callRecord);
    
    if (lead) { 
      console.log("[HubSpotETL] Lead successfully normalised: " + lead.contactName);
      return lead;
    }
  } catch (err) {
    console.error("[HubSpotETL] ❌ Error normalising: " + err.message);
  }

  return null;
}

// --- API FUNCTIONS FOR STREAMING ---

/**
 * Fetches a single call object from HubSpot CRM.
 */
function _fetchSingleCall(callId) {
  const url = `https://api.hubapi.com/crm/v3/objects/calls/${callId}?properties=hs_call_body,hubspot_owner_id,hs_timestamp,hs_call_outcome,hs_call_status,createdate,hs_call_disposition`;
  const response = UrlFetchApp.fetch(url, { 
    method: "get", 
    headers: _hubspotHeaders(), 
    muteHttpExceptions: true 
  });
  
  if (response.getResponseCode() === 200) {
    return JSON.parse(response.getContentText());
  } else {
    Logger.log("[HubSpotETL] API Error " + response.getResponseCode() + ": " + response.getContentText());
    return null;
  }
}

// --- NORMALISATION LOGIC ---

/**
 * Cleans raw HubSpot data into a structured Lead object.
 */
function _normaliseCallRecord(callRecord) {
  const props = callRecord.properties || {};
  
  // 1. NOTES CLEANING
  const noteBody = (props.hs_call_body || "")
    .replace(/<[^>]*>/g, " ").replace(/&nbsp;/g, " ").replace(/\s+/g, " ").trim();

  if (!noteBody) return null;

  // 2. OUTCOME TRANSLATOR
  const outcomeMap = {
    "f240bbac-87c9-4f6e-bf70-924b57d47db7": "Connected",
    "f240bbac-87c9-4f6e-90ed-7c5583d581a3": "Connected",
    "9d9162e7-6cf3-493a-a189-911b519163fe": "Busy",
    "a4c4c304-7bc9-4984-9c46-7359ab43343c": "No Answer",
    "b2cf591d-910a-474b-871d-7d78664426a1": "Wrong Number",
    "73a0d4c6-5d1a-4c17-8d95-ee02f9318153": "Left Voicemail"
  };

  let rawOutcome = (props.hs_call_outcome || props.hs_call_disposition || "").toLowerCase();
  let outcome = outcomeMap[rawOutcome] || "";

  if (!outcome) {
    if (rawOutcome === "" || rawOutcome === "no outcome set") {
      outcome = "No Option Selected";
    } else {
      outcome = rawOutcome.charAt(0).toUpperCase() + rawOutcome.slice(1).replace(/_/g, " ");
    }
  }

  // 3. CONTACT DATA & NAME NORMALISATION
  let contactName = "Unknown Contact", contactEmail = "N/A", contactPhone = "N/A", contactId = "", countryRegion = "N/A";
  const associatedIds = _fetchCallAssociations(callRecord.id);
  
  if (associatedIds && associatedIds.length > 0) {
    contactId = associatedIds[0];
    const contactProps = _fetchContactDetails(contactId);
    if (contactProps) {
      let rawFullName = `${contactProps.firstname || ""} ${contactProps.lastname || ""}`.trim();
      contactName = _toTitleCase(rawFullName) || "Unknown Contact";
      contactEmail = contactProps.email || "N/A";
      contactPhone = contactProps.phone || "N/A";
      countryRegion = contactProps.country || contactProps.hs_country_region || "N/A";
    }
  }

  // 4. DATE CORRECTION
  let callDate;
  let rawTs = props.hs_timestamp || props.createdate;
  if (rawTs) {
    let tsNum = Number(rawTs);
    callDate = isNaN(tsNum) ? new Date(rawTs) : new Date(tsNum);
  } else {
    callDate = new Date();
  }

  return {
    engagementId: callRecord.id,
    contactId: contactId,
    contactName: contactName,
    contactEmail: contactEmail,
    contactPhone: contactPhone,
    agentName: _toTitleCase(_fetchOwnerName(props.hubspot_owner_id)),
    callDateObj: callDate,
    callOutcome: outcome,
    rawNotes: noteBody,
    countryRegion: countryRegion
  };
}

// --- API HELPERS ---

function _fetchCallAssociations(callId) {
  const url = `https://api.hubapi.com/crm/v3/objects/calls/${callId}/associations/contacts`;
  const response = UrlFetchApp.fetch(url, { method: "get", headers: _hubspotHeaders(), muteHttpExceptions: true });
  return (JSON.parse(response.getContentText()).results || []).map(r => r.id);
}

function _fetchContactDetails(contactId) {
  const url = `https://api.hubapi.com/crm/v3/objects/contacts/${contactId}?properties=firstname,lastname,email,phone,country,hs_country_region`;
  const response = UrlFetchApp.fetch(url, { method: "get", headers: _hubspotHeaders(), muteHttpExceptions: true });
  return response.getResponseCode() === 200 ? JSON.parse(response.getContentText()).properties : null;
}

function _fetchOwnerName(ownerId) {
  if (!ownerId) return "System Bot";
  const url = `https://api.hubapi.com/crm/v3/owners/${ownerId}`;
  const response = UrlFetchApp.fetch(url, { method: "get", headers: _hubspotHeaders(), muteHttpExceptions: true });
  if (response.getResponseCode() === 200) {
    const data = JSON.parse(response.getContentText());
    return `${data.firstName || ""} ${data.lastName || ""}`.trim();
  }
  return "Agent: " + ownerId;
}

function _hubspotHeaders() {
  return { 
    "Authorization": "Bearer " + CONFIG.HUBSPOT_ACCESS_TOKEN(), 
    "Content-Type": "application/json" 
  };
}

/**
 * Helper to normalise strings to Title Case.
 */
function _toTitleCase(str) {
  if (!str) return "";
  return str.toLowerCase().split(' ').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');

  /**
 * Fetches a single call by its ID. 
 * This is the bridge between the Webhook and your normalization logic.
 */
function fetchSingleLeadFromHubSpot(engagementId) {
  console.log("[HubSpotETL] Fetching details for specific Call ID: " + engagementId);

  const url = `https://api.hubapi.com/crm/v3/objects/calls/${engagementId}?properties=hs_call_body,hubspot_owner_id,hs_timestamp,hs_call_outcome,hs_call_status,createdate,hs_call_disposition`;
  
  try {
    const response = UrlFetchApp.fetch(url, {
      method: "get",
      headers: _hubspotHeaders(),
      muteHttpExceptions: true
    });

    if (response.getResponseCode() !== 200) {
      console.error("[HubSpotETL] Error fetching call " + engagementId + ": " + response.getContentText());
      return null;
    }

    const callRecord = JSON.parse(response.getContentText());
    
    // REUTILIZAMOS tu lógica de normalización que ya funciona en el Pulling
    const lead = _normaliseCallRecord(callRecord);
    
    if (lead) {
      console.log("[HubSpotETL] Lead successfully retrieved: " + lead.contactName);
      return lead;
    }
  } catch (err) {
    console.error("[HubSpotETL] Fatal error in fetchSingleLead: " + err.message);
  }
  
  return null;
}
}
