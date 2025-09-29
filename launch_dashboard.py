#!/usr/bin/env python3
"""
Dashboard Launcher
Opens the dashboard in the default web browser
"""

import webbrowser
import time
import os
from pathlib import Path

def main():
    print("🚀 Launching Bengaluru Tech Summit Chatbot Dashboard")
    print("=" * 60)
    
    # Check if dashboard file exists
    dashboard_file = Path("dashboard.html")
    if not dashboard_file.exists():
        print("❌ dashboard.html not found!")
        print("Please make sure the dashboard file exists in the current directory.")
        return
    
    # Get absolute path to dashboard
    dashboard_path = dashboard_file.absolute()
    dashboard_url = f"file://{dashboard_path}"
    
    print(f"📊 Dashboard file: {dashboard_path}")
    print(f"🌐 URL: {dashboard_url}")
    print()
    print("⚠️  Make sure your FastAPI server is running:")
    print("   python -m uvicorn qa_api:app --host 0.0.0.0 --port 8000 --reload")
    print()
    print("🔗 Opening dashboard in your default browser...")
    
    # Open dashboard in browser
    try:
        webbrowser.open(dashboard_url)
        print("✅ Dashboard opened successfully!")
        print()
        print("📋 Dashboard Features:")
        print("   • Real-time interaction monitoring")
        print("   • Token usage analytics")
        print("   • Cost tracking")
        print("   • Document usage statistics")
        print("   • Filtering and search capabilities")
        print()
        print("🔄 The dashboard will auto-refresh every 30 seconds")
        print("📱 You can also access it directly at: dashboard.html")
        
    except Exception as e:
        print(f"❌ Failed to open dashboard: {e}")
        print(f"📁 Please manually open: {dashboard_path}")

if __name__ == "__main__":
    main() 