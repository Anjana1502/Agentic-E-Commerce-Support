"""Zero-dependency web chat UI for the e-commerce support agent.

Serves a single-page chat app and a JSON API over Python's stdlib HTTP server,
so the whole demo runs without pip-installing anything:

    python ui/web.py          ->  http://127.0.0.1:8000
"""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ecomagent.agent import Agent
from ecomagent.memory import Session

HOST = "127.0.0.1"
PORT = 8000
ROOT = Path(__file__).resolve().parent
AGENT = Agent()
SESSIONS = {}
LOCK = threading.Lock()


def get_session(sid):
    with LOCK:
        return SESSIONS.setdefault(sid, Session())


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send_json(self, payload, code=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            self._serve_file(ROOT / "static" / "index.html", "text/html; charset=utf-8")
        elif path == "/api/health":
            self._send_json({"ok": True, "agent": "ecommerce-support-v1"})
        else:
            self.send_response(204)
            self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/chat":
            self._send_json({"error": "not found"}, 404)
            return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {}
        message = (payload.get("message") or "").strip()
        sid = payload.get("sid") or "default"
        if not message:
            self._send_json({"reply": "Please type a message.", "trace": [], "intent": "none"})
            return
        session = get_session(sid)
        try:
            result = AGENT.chat(message, session)
        except Exception as exc:  # noqa: BLE001 - surface gracefully in a demo
            result = {"reply": f"Sorry, something went wrong: {exc}", "trace": [], "intent": "error"}
        self._send_json(result)

    def _serve_file(self, path, content_type):
        try:
            body = path.read_bytes()
        except OSError:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Agentic e-commerce support demo running at  http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")


if __name__ == "__main__":
    main()