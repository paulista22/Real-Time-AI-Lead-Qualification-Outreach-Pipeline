function testTelegram() {
  const token = CONFIG.TELEGRAM_BOT_TOKEN();
  const chatId = CONFIG.TELEGRAM_CHAT_ID();
  const url = `https://api.telegram.org/bot${token}/sendMessage?chat_id=${chatId}&text=Hello Pau! The connection is working.`;
  UrlFetchApp.fetch(url);
}