# -*- coding: utf-8 -*-
"""
YouTube Extractor - Desktop Application
Launches the Flask app in a native Windows window using PyWebView
"""
import webview
import threading
import sys
import os

# Ensure we can find the app module
if getattr(sys, 'frozen', False):
    # Running as compiled exe
    BASE_DIR = sys._MEIPASS
    os.chdir(os.path.dirname(sys.executable))
else:
    # Running as script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Add base dir to path
sys.path.insert(0, BASE_DIR)

# Import Flask app
from app import app, load_history, DEFAULT_DOWNLOAD_FOLDER

def start_flask():
    """Start Flask server in background thread"""
    import logging
    # Suppress Flask logs in production
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    # Create download folder
    os.makedirs(DEFAULT_DOWNLOAD_FOLDER, exist_ok=True)
    
    # Load history
    load_history()
    
    # Run Flask (without debug for production)
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False, threaded=True)


def main():
    """Main entry point for desktop app"""
    # Start Flask in background thread
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    
    # Wait for Flask to start
    import time
    time.sleep(1)
    
    # Create native window
    window = webview.create_window(
        title='YouTube Extractor',
        url='http://127.0.0.1:5000',
        width=1200,
        height=800,
        resizable=True,
        min_size=(800, 600),
        text_select=True,
    )
    
    # Start webview
    webview.start()


if __name__ == '__main__':
    main()
