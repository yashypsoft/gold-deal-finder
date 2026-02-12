# run.py
import uvicorn
import webbrowser
from pathlib import Path
import sys
import os

def setup_directories():
    """Create necessary directories"""
    Path("static").mkdir(exist_ok=True)
    Path("data").mkdir(exist_ok=True)
    Path("templates").mkdir(exist_ok=True)
    Path("cache").mkdir(exist_ok=True)
    
    # Create sample data if no scans exist
    data_dir = Path("data")
    if len(list(data_dir.glob("*.json"))) == 0:
        print("📁 No scan data found. Creating sample data...")
        try:
            from sample_data import create_sample_scans
            create_sample_scans(5)
        except ImportError:
            print("⚠️ Could not create sample data. Run sample_data.py manually.")

def open_browser():
    """Open browser after server starts"""
    import time
    time.sleep(2)
    webbrowser.open("http://localhost:8000")

if __name__ == "__main__":
    setup_directories()
    
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║                                                                  ║
    ║     🏆  GOLD DEAL FINDER - HISTORICAL DATA DASHBOARD  🏆        ║
    ║                                                                  ║
    ║   📊 View all products ever scanned                             ║
    ║   📈 Historical analytics and trends                            ║
    ║   🔍 Advanced filtering and search                              ║
    ║   💾 Automatic caching for fast performance                     ║
    ║                                                                  ║
    ║   🚀 Server: http://localhost:8000                             ║
    ║   📚 API Docs: http://localhost:8000/docs                     ║
    ║   💾 Data directory: ./data/                                   ║
    ║                                                                  ║
    ║   Press Ctrl+C to stop the server                              ║
    ║                                                                  ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)
    
    # Open browser
    import threading
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run server
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )