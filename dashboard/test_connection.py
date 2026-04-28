import os
import json
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# 1. Load environment variables from the .env file
load_dotenv()

def test_google_sheets():
    print("🚀 Starting connection test...")
    
    try:
        # 2. Extract JSON credentials and Spreadsheet ID from .env
        env_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        spreadsheet_id = os.getenv("SPREADSHEET_ID")
        
        if not env_json or not spreadsheet_id:
            print("❌ Error: Missing credentials in .env file.")
            return

        service_account_info = json.loads(env_json)
        
        # 3. Define the access scopes (Read-only as requested)
        scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        
        # 4. Authenticate using the Service Account info
        creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
        client = gspread.authorize(creds)
        
        # 5. Attempt to open the spreadsheet
        # .sheet1 opens the first tab (usually 'Sheet1')
        sheet = client.open_by_key(spreadsheet_id).worksheet("Leads")
        
        # 6. Fetch all records into a Pandas DataFrame
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        print("✅ Connection Successful!")
        print(f"📊 Total records found: {len(df)}")
        print("\n👀 Preview of the first 5 leads:")
        print(df.head())
        
    except Exception as e:
        print(f"❌ Test Failed: {e}")
        print("\n💡 Quick Tip: Double-check that you shared your Google Sheet with the 'client_email' found in your JSON.")

if __name__ == "__main__":
    test_google_sheets()