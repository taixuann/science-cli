"""sci serve — Python stdlib HTTP server for the AI Studio frontend."""

from __future__ import annotations

import http.server
import json
import logging
import os
import re
import traceback
import urllib.parse
from pathlib import Path

logger = logging.getLogger(__name__)


# Resolve the frontend/ directory relative to this file
FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"

# CORS headers for dev mode
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


class SciServeHandler(http.server.SimpleHTTPRequestHandler):
    project_override: str | None = None
    dev_mode: bool = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        # Intercept dynamic project context override from query string or headers
        project_param = qs.get("project", [None])[0]
        if not project_param:
            project_param = self.headers.get("X-Project-Override", None)

        if project_param:
            self.project_override = project_param

        try:
            if path == "/api/projects":
                self._api_projects()
                return

            if path == "/api/project":
                self._api_project()
                return

            if path == "/api/gallery":
                self._api_gallery()
                return

            m = re.match(r"^/api/protocol/([^/]+)/files$", path)
            if m:
                self._api_protocol_files(m.group(1))
                return

            m = re.match(r"^/api/protocol/([^/]+)/summary$", path)
            if m:
                self._api_protocol_summary(m.group(1))
                return

            m = re.match(r"^/api/protocol/([^/]+)/heatmap$", path)
            if m:
                metric = qs.get("metric", ["ratio"])[0]
                material = qs.get("material", [""])[0]
                self._api_heatmap(m.group(1), metric, material)
                return

            m = re.match(r"^/api/protocol/([^/]+)/device/([^/]+)/iv$", path)
            if m:
                self._api_device_iv(m.group(1), m.group(2))
                return

            m = re.match(r"^/api/protocol/([^/]+)/histograms$", path)
            if m:
                self._api_histograms(m.group(1))
                return

            if path == "/":
                self.path = "/index.html"
                return super().do_GET()

            # Serve files from project's protocol/ directory
            m = re.match(r"^/files/(.+)$", path)
            if m:
                self._serve_project_file(m.group(1))
                return

            super().do_GET()

        except Exception:
            self._send_error(500, "Internal server error")
            traceback.print_exc()
            logger.exception("Request handler error")

    def do_OPTIONS(self):
        if self.dev_mode:
            self._add_cors()
            self.send_response(204)
            self.end_headers()

    def log_message(self, fmt, *args):
        if self.dev_mode or os.environ.get("SCI_SERVE_VERBOSE"):
            super().log_message(fmt, *args)

    def _add_cors(self):
        for key, val in CORS_HEADERS.items():
            self.send_header(key, val)

    def _send_json(self, data: dict | list, status: int = 200):
        body = json.dumps(data, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if self.dev_mode:
            self._add_cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str):
        self._send_json({"error": message}, status)

    def _get_project_path(self) -> Path | None:
        from science_cli.serve.api import _resolve_project
        return _resolve_project(self.project_override)

    def _api_projects(self):
        from science_cli.serve.api import get_projects_list
        data = get_projects_list()
        self._send_json(data)

    def _api_project(self):
        proj = self._get_project_path()
        if not proj:
            return self._send_json({
                "project_name": "(no project open)",
                "project_path": "",
                "protocols": [],
                "stats": {"total_protocols": 0, "total_files": 0, "total_cells_measured": 0, "overall_yield": 0.0},
            })
        from science_cli.serve.api import get_project_data
        data = get_project_data(proj)
        self._send_json(data)

    def _api_gallery(self):
        proj = self._get_project_path()
        if not proj:
            return self._send_error(404, "no project open — use 'sci open -m project <name>' first")
        from science_cli.serve.api import get_gallery_data
        data = get_gallery_data(proj)
        self._send_json(data)

    def _api_protocol_summary(self, protocol_name: str):
        proj = self._get_project_path()
        if not proj:
            return self._send_error(404, "no project open")
        from science_cli.serve.api import get_protocol_summary
        data = get_protocol_summary(proj, protocol_name)
        if "error" in data:
            return self._send_error(404, data["error"])
        self._send_json(data)

    def _api_heatmap(self, protocol_name: str, metric: str, material: str):
        proj = self._get_project_path()
        if not proj:
            return self._send_error(404, "no project open")
        from science_cli.serve.api import get_heatmap_data
        data = get_heatmap_data(proj, protocol_name, metric, material)
        if data is None or "error" in data:
            return self._send_error(404, "protocol not found or no data available")
        self._send_json(data)

    def _api_device_iv(self, protocol_name: str, cell_id: str):
        proj = self._get_project_path()
        if not proj:
            return self._send_error(404, "no project open")
        from science_cli.serve.api import get_device_iv
        data = get_device_iv(proj, protocol_name, cell_id)
        if "error" in data:
            return self._send_error(404, data["error"])
        self._send_json(data)

    def _api_histograms(self, protocol_name: str):
        proj = self._get_project_path()
        if not proj:
            return self._send_error(404, "no project open")
        from science_cli.serve.api import get_histograms
        data = get_histograms(proj, protocol_name)
        self._send_json(data)

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            for index in self.index_pages or ("index.html", "index.htm"):
                index_path = os.path.join(path, index)
                if os.path.exists(index_path):
                    path = index_path
                    break
            else:
                return self.list_directory(path)

        ctype = self.guess_type(path)
        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None

        try:
            fs = os.fstat(f.fileno())
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(fs[6]))
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            if self.dev_mode:
                self._add_cors()
            self.end_headers()
            return f
        except Exception:
            f.close()
            raise


class SciServeServer:
    def __init__(
        self,
        port: int = 8000,
        project_override: str | None = None,
        dev_mode: bool = False,
    ):
        self.port = port
        self.project_override = project_override
        self.dev_mode = dev_mode

    def serve_forever(self):
        handler = self._make_handler()
        try:
            httpd = http.server.ThreadingHTTPServer(
                ("0.0.0.0", self.port), handler
            )
        except OSError as e:
            print(f"[ERROR] Cannot start server: {e}")
            print(f"        Port {self.port} may already be in use.")
            print(f"        Try: sci serve --port {self.port + 1}")
            raise SystemExit(1) from e

        print(f"[OK] sci serve started on http://localhost:{self.port}")
        print(f"     Frontend: {FRONTEND_DIR}")
        if self.project_override:
            print(f"     Project:  {self.project_override}")
        with httpd:
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\n[OK] Server stopped.")

    def _make_handler(self):
        server = self

        class BoundHandler(SciServeHandler):
            project_override = server.project_override
            dev_mode = server.dev_mode

        return BoundHandler
