"""Minimal local JSON API for the extension. Standard library only.

    POST /suggest  {"messages": [{"role": "prospect"|"rep", "text": "..."}]}  -> suggestions
    GET  /health

Binds to localhost by default. CORS is open to the extension's requests; if you host this,
add authentication first: thread contents are customer data.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from copilot_api.suggest import LLM, suggest_reply


def make_server(playbook: dict, host: str = "127.0.0.1", port: int = 8787, llm: LLM | None = None):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: dict) -> None:
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self):
            if self.path == "/health":
                self._send(200, {"status": "ok", "won": playbook["stats"]["won"], "lost": playbook["stats"]["lost"]})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/suggest":
                return self._send(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length) or b"{}")
                thread = payload["messages"]
                assert isinstance(thread, list) and all({"role", "text"} <= m.keys() for m in thread)
            except (ValueError, KeyError, AssertionError):
                return self._send(400, {"error": "body must be {messages: [{role, text}]}"})
            self._send(200, suggest_reply(playbook, thread, llm))

        def log_message(self, *args):  # keep customer text out of server logs
            pass

    return ThreadingHTTPServer((host, port), Handler)
