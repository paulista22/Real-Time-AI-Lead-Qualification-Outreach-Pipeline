/**
 * Notifications.gs – Real-Time Alerting
 * Sends a Telegram notification when interest_score >= HOT_LEAD_THRESHOLD.
 */

/**
 * Evaluates a lead's score and fires a Telegram alert if it is a Hot Lead.
 */
function notifyIfHotLead(lead, insights) {
  // Read threshold from Config or default to 80
  const threshold = CONFIG.HOT_LEAD_THRESHOLD() || 80;

  if (insights.interest_score < threshold) return false;

  Logger.log("[Notifications] Hot lead detected: " + lead.contactName + " (Score: " + insights.interest_score + ")");

  const message = _buildTelegramMessage(lead, insights, threshold);
  return _sendTelegramMessage(message);
}

// ---------------------------------------------------------------------------
// Telegram API Logic
// ---------------------------------------------------------------------------

function _sendTelegramMessage(message) {
  const token = CONFIG.TELEGRAM_BOT_TOKEN();
  const chatId = CONFIG.TELEGRAM_CHAT_ID();

  if (!token || !chatId) {
    Logger.log("⚠️ Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing in Script Properties.");
    return false;
  }

  const url = `https://api.telegram.org/bot${token}/sendMessage`;

  const payload = {
    chat_id: chatId,
    text: message,
    parse_mode: "Markdown",
    disable_web_page_preview: true,
  };

  const options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  };

  try {
    const response = UrlFetchApp.fetch(url, options);
    if (response.getResponseCode() !== 200) {
      Logger.log("❌ Telegram API Error: " + response.getContentText());
      return false;
    }
    Logger.log("[Notifications] Telegram alert sent successfully.");
    return true;
  } catch (err) {
    Logger.log("❌ Telegram Exception: " + err.message);
    return false;
  }
}

// ---------------------------------------------------------------------------
// Message Formatting
// ---------------------------------------------------------------------------

function _buildTelegramMessage(lead, insights, threshold) {
  const scoreBar = _buildScoreBar(insights.interest_score);
  
  // Adjusted to Mazatlán Timezone (GMT-7)
  const callDate = lead.callDateObj
    ? Utilities.formatDate(lead.callDateObj, "America/Mazatlan", "yyyy-MM-dd HH:mm")
    : "N/A";

  // Data cleaning to prevent Markdown parsing errors
  const name = _cleanForMarkdown(lead.contactName);
  const agent = _cleanForMarkdown(lead.agentName);
  const phone = _cleanForMarkdown(lead.contactPhone || "No Phone");
  const summary = _cleanForMarkdown(insights.ai_summary_markdown || "No summary available.");

  return (
    "🔥 *HOT LEAD ALERT* (Score: " + insights.interest_score + ")\n\n" +
    "👤 *Contact:* " + name + "\n" +
    "📞 *Phone:* " + phone + "\n" + 
    "👔 *Agent:* " + agent + "\n" +
    "🏠 *Product:* " + (insights.product_type || "Unknown") + "\n" +
    "📊 *Score:* " + insights.interest_score + "/100 " + scoreBar + "\n" +
    "🌍 *Country/Region:* " + (insights.country_region || "N/A") + "\n" +
    "⏰ *Date:* " + callDate + "\n" +
    "⚠️ *Urgency:* " + (insights.urgency_indicators || "—") + "\n\n" +
    "📋 *AI Summary:*\n" + summary
  );
}

/**
 * Builds a visual progress bar for the Telegram message.
 */
function _buildScoreBar(score) {
  const filledCount = Math.min(Math.max(Math.round(score / 10), 0), 10);
  return "▓".repeat(filledCount) + "░".repeat(10 - filledCount);
}

/**
 * Escapes characters that break Telegram's Markdown parsing.
 */
function _cleanForMarkdown(text) {
  if (!text) return "";
  return String(text).replace(/[*_`\[]/g, ""); 
}