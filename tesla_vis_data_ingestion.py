#!/usr/bin/env python3
"""
Tesla Data Ingestion Script
This script fetches data from TeslaFi API and stores it in the database.
Can be run as a standalone script or scheduled via cron/systemd.
"""

import os
import sys
import json
import time
import requests
import schedule
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class TeslaDataIngester:
    def __init__(self):
        self.teslafi_token = os.environ.get('TESLAFI_API_TOKEN')
        # Always default to Railway URL for production
        self.flask_app_url = os.environ.get('FLASK_APP_URL', 'https://tesla-dashboard-production.up.railway.app')
        self.ingestion_interval = int(os.environ.get('INGESTION_INTERVAL_MINUTES', '5'))
        
        if not self.teslafi_token:
             self.teslafi_token = 'e0a2c46fd7a566c742ecda940b7532db52087c9a2e8e2d352c82f215da3262a7'
            #raise ValueError("TESLAFI_API_TOKEN environment variable is required")
    
    def fetch_tesla_data(self):
        """Fetch latest data from TeslaFi API"""
        try:
            # TeslaFi API endpoint for latest data
            url = f"https://www.teslafi.com/feed.php?token={self.teslafi_token}&command=lastGood"
            
            print(f"[{datetime.now()}] Fetching data from TeslaFi...")
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                print(f"[{datetime.now()}] Successfully fetched data (data_id: {data.get('data_id', 'unknown')})")
                return data
            else:
                print(f"[{datetime.now()}] Failed to fetch data: HTTP {response.status_code}")
                return None
                
        except requests.RequestException as e:
            print(f"[{datetime.now()}] Request error: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"[{datetime.now()}] JSON decode error: {e}")
            return None
        except Exception as e:
            print(f"[{datetime.now()}] Unexpected error fetching data: {e}")
            return None
    
    def store_data(self, data):
        """Store data in Flask app database via API"""
        try:
            # Post to our ingest endpoint
            ingest_url = f"{self.flask_app_url}/api/ingest"
            print(f"[{datetime.now()}] Posting to: {ingest_url}")
            
            ingest_response = requests.post(ingest_url, json=data, timeout=30)
            
            print(f"[{datetime.now()}] Storage API response: {ingest_response.status_code}")
            print(f"[{datetime.now()}] Storage API headers: {dict(ingest_response.headers)}")
            
            if ingest_response.status_code == 200:
                result = ingest_response.json()
                if result.get('status') == 'success':
                    print(f"[{datetime.now()}] Data stored successfully")
                    return True
                elif result.get('status') == 'duplicate':
                    print(f"[{datetime.now()}] Data already exists (duplicate)")
                    return True
                else:
                    print(f"[{datetime.now()}] Storage failed: {result.get('message', 'unknown error')}")
                    return False
            else:
                print(f"[{datetime.now()}] Storage API error: HTTP {ingest_response.status_code}")
                print(f"[{datetime.now()}] Response text: {ingest_response.text}")
                return False
                
        except requests.RequestException as e:
            print(f"[{datetime.now()}] Storage request error: {e}")
            return False
        except Exception as e:
            print(f"[{datetime.now()}] Unexpected storage error: {e}")
            return False
    
    def ingest_data_once(self):
        """Fetch and store data once"""
        print(f"[{datetime.now()}] Starting data ingestion...")
        
        # Fetch data from TeslaFi
        data = self.fetch_tesla_data()
        if not data:
            print(f"[{datetime.now()}] No data to process")
            return False
        
        # Store data in database
        success = self.store_data(data)
        
        if success:
            print(f"[{datetime.now()}] Data ingestion completed successfully")
        else:
            print(f"[{datetime.now()}] Data ingestion failed")
        
        return success
    
    def start_scheduled_ingestion(self):
        """Start scheduled data ingestion"""
        print(f"[{datetime.now()}] Starting scheduled ingestion every {self.ingestion_interval} minutes")
        
        # Schedule the job
        schedule.every(self.ingestion_interval).minutes.do(self.ingest_data_once)
        
        # Run once immediately
        self.ingest_data_once()
        
        # Keep running
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    def export_data_to_csv(self, output_file='tesla_data_export.csv'):
        """Export stored data to CSV for analysis"""
        try:
            url = f"{self.flask_app_url}/api/data/history?days=365"  # Get last year of data
            
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if data:
                    import pandas as pd
                    df = pd.DataFrame(data)
                    df.to_csv(output_file, index=False)
                    print(f"[{datetime.now()}] Data exported to {output_file} ({len(data)} records)")
                    return True
                else:
                    print(f"[{datetime.now()}] No data to export")
                    return False
            else:
                print(f"[{datetime.now()}] Export failed: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"[{datetime.now()}] Export error: {e}")
            return False

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python tesla_ingestion.py once          # Run data ingestion once")
        print("  python tesla_ingestion.py schedule      # Start scheduled ingestion")
        print("  python tesla_ingestion.py export        # Export data to CSV")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    try:
        ingester = TeslaDataIngester()
        
        if command == 'once':
            success = ingester.ingest_data_once()
            sys.exit(0 if success else 1)
            
        elif command == 'schedule':
            ingester.start_scheduled_ingestion()
            
        elif command == 'export':
            output_file = sys.argv[2] if len(sys.argv) > 2 else 'tesla_data_export.csv'
            success = ingester.export_data_to_csv(output_file)
            sys.exit(0 if success else 1)
            
        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print(f"\n[{datetime.now()}] Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"[{datetime.now()}] Fatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

def fetch_and_store_tesla_data():
    """Standalone function for automatic data ingestion from tesla_vis.py"""
    try:
        ingester = TeslaDataIngester()
        return ingester.ingest_data_once()
    except Exception as e:
        print(f"[{datetime.now()}] Automatic data ingestion failed: {e}")
        return False
