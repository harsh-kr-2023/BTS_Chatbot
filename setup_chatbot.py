#!/usr/bin/env python3
"""
Setup script for Bengaluru Tech Summit Chatbot
This script helps you set up the environment and start the chatbot.
"""

import os
import sys
import subprocess
from pathlib import Path
import sqlite3

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True

def check_dependencies():
    """Check if required dependencies are installed"""
    required_packages = [
        'fastapi', 'uvicorn', 'google-generativeai', 'sentence-transformers',
        'scikit-learn', 'beautifulsoup4', 'markdown', 'requests',
        'lxml', 'html2text', 'tiktoken', 'numpy', 'python-dotenv'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package}")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n📦 Installing missing packages: {', '.join(missing_packages)}")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing_packages)
            print("✅ All dependencies installed successfully")
        except subprocess.CalledProcessError:
            print("❌ Failed to install dependencies")
            return False
    
    return True

def check_env_file():
    """Check if .env file exists and has Gemini API key"""
    env_file = Path('.env')
    
    if not env_file.exists():
        print("❌ .env file not found")
        print("📝 Creating .env file...")
        
        api_key = input("Enter your Gemini API key: ").strip()
        if not api_key:
            print("❌ Gemini API key is required")
            return False
        
        with open(env_file, 'w') as f:
            f.write(f"GEMINI_API_KEY={api_key}\n")
        print("✅ .env file created")
    else:
        print("✅ .env file found")
        
        # Check if API key is set
        with open(env_file, 'r') as f:
            content = f.read()
            if 'GEMINI_API_KEY=' in content and not 'your_gemini_api_key_here' in content:
                print("✅ Gemini API key configured")
            else:
                print("❌ Gemini API key not properly configured")
                return False
    
    return True

def check_data_files():
    """Check if required data files exist"""
    required_files = [
        'catalog.json',
        'markdown_embeddings.pkl',
        'markdown_files/'
    ]
    
    missing_files = []
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path}")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n⚠️  Missing data files: {', '.join(missing_files)}")
        print("Please run the data processing pipeline first:")
        print("1. python url_fetcher.py")
        print("2. python html_fetcher.py")
        print("3. python html_cleaner.py")
        print("4. python html_to_markdown.py")
        print("5. python generate_md_catalog.py")
        print("6. python generate_embeddings.py")
        return False
    
    return True

def start_server():
    """Start the FastAPI server"""
    print("\n🚀 Starting FastAPI server...")
    print("📱 Open chatbot.html in your browser to test the chatbot")
    print("🔗 API will be available at: http://localhost:8000")
    print("📚 API documentation at: http://localhost:8000/docs")
    print("\nPress Ctrl+C to stop the server")
    
    try:
        subprocess.run([
            sys.executable, '-m', 'uvicorn', 
            'qa_api:app', 
            '--host', '0.0.0.0', 
            '--port', '8000',
            '--reload'
        ])
    except KeyboardInterrupt:
        print("\n👋 Server stopped")

def init_db():
    db_path = "chatbot.db"
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            last_updated TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def main():
    print("🤖 Bengaluru Tech Summit Chatbot Setup")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        return
    
    print("\n📦 Checking dependencies...")
    if not check_dependencies():
        return
    
    print("\n🔑 Checking environment configuration...")
    if not check_env_file():
        return
    
    print("\n📁 Checking data files...")
    if not check_data_files():
        return
    
    print("\n✅ Setup complete! All requirements met.")
    
    # Ask if user wants to start the server
    start_now = input("\n🚀 Start the server now? (y/n): ").strip().lower()
    if start_now in ['y', 'yes']:
        start_server()
    else:
        print("\n📋 To start the server manually, run:")
        print("python -m uvicorn qa_api:app --host 0.0.0.0 --port 8000 --reload")
        print("\n📱 Then open chatbot.html in your browser")

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
    main()