#!/usr/bin/env python3
"""
Redacted - Hardware Analysis Tool
Snapdragon Edition v0.1

Entry point - starts the backend server and launches the GUI.
"""

import sys
import os
import threading
import webbrowser
import time

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from backend.server import start_server
from backend.adb import ADBManager

PORT = 9420

def main():
    print("""
██████████ REDACTED v0.1
Hardware Analysis Tool - Snapdragon Edition
==========================================
    """)

    # Check ADB
    adb = ADBManager()
    if not adb.check_adb():
        print("[!] ADB not found. Please install platform-tools.")
        print("    https://developer.android.com/tools/releases/platform-tools")
        sys.exit(1)

    print("[*] Starting backend server...")

    # Start server in background thread
    server_thread = threading.Thread(
        target=start_server,
        args=(PORT,),
        daemon=True
    )
    server_thread.start()

    # Wait for server to be ready
    time.sleep(1)

    print(f"[*] Backend running on http://localhost:{PORT}")
    print("[*] Opening Redacted UI...")

    # Open browser (or Electron/WebView in final version)
    webbrowser.open(f"http://localhost:{PORT}")

    print("[*] Redacted is running. Press Ctrl+C to exit.")
    print("")

    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Shutting down Redacted...")
        sys.exit(0)

if __name__ == "__main__":
    main()
