# -*- coding: utf-8 -*-
"""
science-cli Plot Gallery Web Server (server.py)
A lightweight pure python standard library server for multi-project switching,
memristor crossbars, material segmentation, and interactive lightbox analytics.
"""

import sys
import os
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import api

PORT = 3000

class ScienceCliHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        # Allow CORS for easy visualization in frontends
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'X-Project-Override, Content-Type')
        BaseHTTPRequestHandler.end_headers(self)

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def get_project_param(self, query_params):
        """
        Extracts active project choosing either from query parameter or headers
        """
        proj = query_params.get("project", [None])[0]
        if not proj:
            proj = self.headers.get("X-Project-Override", None)
        if not proj or proj not in api.PROJECTS:
            proj = "res_internship" # fallback default
        return proj

    def do_GET(self):
        # Parse query parameters safely
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        # Resolve project override state or session
        project_name = self.get_project_param(query_params)
        
        # 1. API: GET /api/projects
        if path == "/api/projects":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = api.get_projects_list()
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        # 2. API: GET /api/project
        elif path == "/api/project":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = api.get_project_summary(project_name)
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        # 3. API: GET /api/protocol/<name>/files
        elif path.startswith("/api/protocol/") and path.endswith("/files"):
            # Format: /api/protocol/<protocol_name>/files
            parts = path.split("/")
            if len(parts) >= 5:
                proto = urllib.parse.unquote(parts[3])
                res_data = api.get_protocol_files(project_name, proto)
                if res_data is not None:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(res_data).encode("utf-8"))
                    return
            self.send_error(404, "Protocol files not found")
            return

        # 4. API: GET /api/protocol/<name>/summary
        elif path.startswith("/api/protocol/") and path.endswith("/summary"):
            parts = path.split("/")
            if len(parts) >= 5:
                proto = urllib.parse.unquote(parts[3])
                res_data = api.get_protocol_summary(project_name, proto)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(res_data).encode("utf-8"))
                return
            self.send_error(404, "Protocol summary not found")
            return

        # 5. API: GET /api/protocol/<name>/heatmap
        elif path.startswith("/api/protocol/") and path.endswith("/heatmap"):
            parts = path.split("/")
            if len(parts) >= 5:
                proto = urllib.parse.unquote(parts[3])
                metric = query_params.get("metric", ["ratio"])[0]
                material = query_params.get("material", [""])[0]
                res_data = api.get_heatmap_data(project_name, proto, metric, material)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(res_data).encode("utf-8"))
                return
            self.send_error(404, "Heatmap not found")
            return

        # 6. API: GET /api/protocol/<name>/device/<cell>/iv
        elif path.startswith("/api/protocol/") and "/device/" in path and path.endswith("/iv"):
            # Format: /api/protocol/<proto>/device/<cell>/iv
            parts = path.split("/")
            if len(parts) >= 7:
                proto = urllib.parse.unquote(parts[3])
                cell_id = urllib.parse.unquote(parts[5])
                res_data = api.get_device_iv(project_name, proto, cell_id)
                if res_data is not None:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(res_data).encode("utf-8"))
                    return
            self.send_error(404, "Device I-V statistics not found")
            return

        # 7. API: GET /api/protocol/<name>/histograms
        elif path.startswith("/api/protocol/") and path.endswith("/histograms"):
            parts = path.split("/")
            if len(parts) >= 5:
                proto = urllib.parse.unquote(parts[3])
                res_data = api.get_protocol_histograms(project_name, proto)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(res_data).encode("utf-8"))
                return
            self.send_error(404, "Histograms not found")
            return

        # 8. Files endpoint: GET /files/<path>
        elif path.startswith("/files/"):
            sub_path = path[7:] # strip '/files/'
            full_path = os.path.join(api.get_workspace_dir(), sub_path)
            if os.path.exists(full_path) and os.path.isfile(full_path):
                self.send_response(200)
                if full_path.endswith(".svg"):
                    self.send_header("Content-Type", "image/svg+xml")
                elif full_path.endswith(".pdf"):
                    self.send_header("Content-Type", "application/pdf")
                else:
                    self.send_header("Content-Type", "image/png")
                self.end_headers()
                with open(full_path, "rb") as f:
                    self.wfile.write(f.read())
                return
            self.send_error(404, "File not found")
            return

        # 9. Serve static frontend index if requested (e.g. root or /index.html)
        elif path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            # Standard SPA html loader (or our generated premium standalone dashboard)
            dashboard_html = os.path.join(os.getcwd(), "index_standalone.html")
            if not os.path.exists(dashboard_html):
                dashboard_html = os.path.join(os.getcwd(), "index.html")
                
            if os.path.exists(dashboard_html):
                with open(dashboard_html, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(b"<h1>Science-CLI Plot Gallery active</h1>")
            return

        # Serve other local files (dashboard.css, dashboard.js, etc.)
        else:
            local_file = os.path.join(os.getcwd(), path.lstrip("/"))
            if os.path.exists(local_file) and os.path.isfile(local_file):
                self.send_response(200)
                if local_file.endswith(".css"):
                    self.send_header("Content-Type", "text/css")
                elif local_file.endswith(".js"):
                    self.send_header("Content-Type", "application/javascript")
                self.end_headers()
                with open(local_file, "rb") as f:
                    self.wfile.write(f.read())
                return

        self.send_error(404, "Endpoint not matched")

def run_server():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, ScienceCliHandler)
    print("science-cli serving workspace '{0}' on port {1}...".format(api.get_workspace_dir(), PORT))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping science-cli server.")
        sys.exit(0)

if __name__ == "__main__":
    run_server()
