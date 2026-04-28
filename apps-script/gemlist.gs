function listMyModels() {
  const apiKey = CONFIG.GEMINI_API_KEY();
  const url = `https://generativelanguage.googleapis.com/v1beta/models?key=${apiKey}`;
  
  const response = UrlFetchApp.fetch(url);
  const json = JSON.parse(response.getContentText());
  
  // This will print all available models to the console
  json.models.forEach(m => Logger.log("Available model: " + m.name));
}