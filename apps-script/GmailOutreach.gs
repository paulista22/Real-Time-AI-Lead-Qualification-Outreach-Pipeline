/**
 * GmailOutreach.gs – Phase 3: Automated Email Outreach
 */

/**
 * GmailOutreach.gs – Versión con Personalización Automática
 */

function sendFollowUpEmail(lead, insights) {
  if (!lead.contactEmail || lead.contactEmail === "N/A") {
    Logger.log("[GmailOutreach] No email for contact: " + lead.contactName + ". Skipping.");
    return { status: "skipped_no_email", subject: "" };
  }

  // 1. OBTENEMOS EL CUERPO GENERADO POR GEMINI
  let emailBody = insights.suggested_email_body;
  const emailSubject = `Follow-up: Your ${insights.product_type || "Mortgage"} Inquiry`;

  if (!emailBody || emailBody === "No email drafted") {
    return { status: "skipped_empty_body", subject: emailSubject };
  }

  // 2. --- AUTOMATIC REPLACEMENT LOGIC (MAIL MERGE) ---
  // Replace client name placeholders
  emailBody = emailBody.replace(/\[Broker Name\]/gi, lead.contactName);
  emailBody = emailBody.replace(/\[Contact Name\]/gi, lead.contactName);
  emailBody = emailBody.replace(/\[Customer Name\]/gi, lead.contactName);

  // Replace agent name placeholder
  const myName = lead.agentName || "Lending Team";
  emailBody = emailBody.replace(/\[Your Name\]/gi, myName);
  emailBody = emailBody.replace(/\[Agent Name\]/gi, myName);

  // 3. SEND CONFIGURATION
  const draftMode = CONFIG.GMAIL_DRAFT_MODE(); 
  const senderEmail = Session.getActiveUser().getEmail();

  const options = {
    name: "Lending Team",
    replyTo: senderEmail
  };

  try {
    if (draftMode) {
      GmailApp.createDraft(lead.contactEmail, emailSubject, emailBody, options);
      Logger.log("[GmailOutreach] Draft saved for: " + lead.contactEmail);
      return { status: "draft", subject: emailSubject, body: emailBody };
    } else {
      GmailApp.sendEmail(lead.contactEmail, emailSubject, emailBody, options);
      Logger.log("[GmailOutreach] Email sent to: " + lead.contactEmail);
      return { status: "sent", subject: emailSubject, body: emailBody };
    }
  } catch (err) {
    Logger.log("[GmailOutreach] Error in outreach: " + err.message);
    return { status: "error", subject: emailSubject };
  }
}

/**
 * Eligibility filter: Only contact leads with real interest (Score > 40)
 */
function shouldSendOutreach(lead, insights) {
  const hasEmail = lead.contactEmail && lead.contactEmail.includes("@");
  // Adjust this threshold to control outreach aggressiveness
  const isInterested = (insights.interest_score >= 40); 
  
  return hasEmail && isInterested;
}