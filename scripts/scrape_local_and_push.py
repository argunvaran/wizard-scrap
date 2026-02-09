
import requests
import json
import logging
import sys
import os

# Ensure scraper module can be imported
sys.path.append(os.path.join(os.getcwd(), 'web_app'))

try:
    from web_app.scraper.bilyoner import BilyonerScraper
except ImportError:
    print("Please run this script from the root c:\\Code\\web_scraper_0 folder")
    print("Example: python scripts/scrape_local_and_push.py")
    sys.exit(1)

# CONFIGURATION
REMOTE_API_URL = "http://YOUR_AWS_IP_OR_DOMAIN/analysis/api/push-bulletin/" 
# OR "http://localhost:8000/analysis/api/push-bulletin/" for testing
SECRET = "WFM_PRO_2026_SECURE_SYNC"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('local_pusher')

def main():
    print("--- HYBRID SCRAPER: LOCAL TO REMOTE ---")
    print(f"DEBUG LOGS: {os.path.abspath('scraper_debug.log')}")
    print(f"Target API: {REMOTE_API_URL}")
    
    # 1. Scrape Locally (Using your home IP which is trusted)
    print("Starting Local Scraper...")
    scraper = BilyonerScraper()
    matches = scraper.scrape()
    
    if not matches:
        print("Scraping returned 0 matches. Aborting push.")
        return

    print(f"Captured {len(matches)} matches.")
    
    # 2. Push to Remote Server
    payload = {
        "secret": SECRET,
        "matches": matches
    }
    
    print(" pushing to server...")
    try:
        # Check if user updated the URL
        if "YOUR_AWS_IP" in REMOTE_API_URL:
             print("ERROR: Please edit this script and update REMOTE_API_URL with your actual AWS domain/IP!")
             return

        response = requests.post(REMOTE_API_URL, json=payload, timeout=30)
        
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("success"):
                print(f"SUCCESS! Server saved {res_json.get('count')} matches.")
            else:
                print(f"Server Error: {res_json.get('error')}")
        else:
            print(f"HTTP Error: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Network Error: {e}")

if __name__ == "__main__":
    main()
