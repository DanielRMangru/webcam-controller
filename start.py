#!/usr/bin/env python3
"""
Webcam Controller Launcher for Ubuntu 24.04
"""

import os
import sys
import webbrowser
import uvicorn
import time
import threading

def open_browser():
    time.sleep(1.0)
    webbrowser.open("http://127.0.0.1:8765")

if __name__ == "__main__":
    app_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(app_dir)

    print("=" * 60)
    print("  🎥 Linux Webcam Controller - Ubuntu 24.04")
    print("  Starting server on http://127.0.0.1:8765")
    print("=" * 60)

    # Launch browser thread if running interactively
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run("backend.server:app", host="127.0.0.1", port=8765, log_level="info")
