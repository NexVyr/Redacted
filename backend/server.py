"""
server.py - Backend HTTP server for Redacted
Serves the frontend and exposes REST API for device communication.
"""

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.adb import ADBManager

adb = ADBManager()

class RedactedHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Suppress default HTTP logs, we handle our own
        pass

    def send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: str):
        ext = os.path.splitext(path)[1]
        mime = {
            ".html": "text/html",
            ".js":   "application/javascript",
            ".jsx":  "application/javascript",
            ".css":  "text/css",
            ".png":  "image/png",
            ".svg":  "image/svg+xml",
        }.get(ext, "text/plain")

        try:
            with open(path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path

        # ── Serve frontend ──────────────────────────────
        if path == "/" or path == "/index.html":
            frontend_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "frontend", "index.html"
            )
            self.send_file(frontend_path)
            return

        # ── API Routes ──────────────────────────────────

        # GET /api/devices - list connected devices
        if path == "/api/devices":
            adb_devices      = adb.get_devices()
            fastboot_devices = adb.get_fastboot_devices()
            self.send_json({
                "adb":      adb_devices,
                "fastboot": fastboot_devices,
                "total":    len(adb_devices) + len(fastboot_devices)
            })
            return

        # GET /api/device/info - full device info
        if path == "/api/device/info":
            try:
                info = adb.get_device_info()
                self.send_json({"success": True, "data": info})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)
            return

        # GET /api/device/props - all properties
        if path == "/api/device/props":
            try:
                props = adb.get_all_props()
                self.send_json({"success": True, "data": props})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)
            return

        # GET /api/drivers - loaded kernel modules
        if path == "/api/drivers":
            try:
                modules = adb.get_loaded_modules()
                self.send_json({"success": True, "data": modules})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)
            return

        # GET /api/dmesg - kernel log
        if path == "/api/dmesg":
            try:
                log = adb.get_dmesg()
                self.send_json({"success": True, "data": log})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)
            return

        # GET /api/partitions - partition table
        if path == "/api/partitions":
            try:
                parts = adb.get_partitions()
                self.send_json({"success": True, "data": parts})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)
            return

        # GET /api/fastboot/info - fastboot variables
        if path == "/api/fastboot/info":
            try:
                info = adb.get_fastboot_info()
                self.send_json({"success": True, "data": info})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)
            return

        # 404
        self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed  = urlparse(self.path)
        path    = parsed.path
        length  = int(self.headers.get("Content-Length", 0))
        body    = json.loads(self.rfile.read(length)) if length else {}

        # POST /api/shell - run ADB shell command
        if path == "/api/shell":
            command = body.get("command", "")
            if not command:
                self.send_json({"error": "No command provided"}, 400)
                return
            try:
                result = adb.shell(command)
                self.send_json({"success": True, "data": result})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)
            return

        # POST /api/device/select - select device by serial
        if path == "/api/device/select":
            serial = body.get("serial", "")
            adb.select_device(serial)
            self.send_json({"success": True, "serial": serial})
            return

        # POST /api/reboot - reboot device
        if path == "/api/reboot":
            mode = body.get("mode", "normal")
            if mode == "fastboot":
                ok = adb.reboot_fastboot()
            elif mode == "recovery":
                ok = adb.reboot_recovery()
            else:
                ok = adb.reboot()
            self.send_json({"success": ok})
            return

        self.send_json({"error": "Not found"}, 404)


def start_server(port: int = 9420):
    """Start the Redacted HTTP server."""
    server = HTTPServer(("localhost", port), RedactedHandler)
    print(f"[*] Redacted backend listening on http://localhost:{port}")
    server.serve_forever()
