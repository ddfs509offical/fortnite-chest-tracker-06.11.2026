"""Event sources that feed the tracker.

The practical source is the local HUD bridge: an island loaded inside Fortnite
Creative posts JSON to http://127.0.0.1:<port>/event and we count it. Nothing
here reads game memory or injects into the game process.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterable

MAX_BODY = 64 * 1024

_hud_html: bytes = b""


class _Handler(BaseHTTPRequestHandler):
    tracker = None  # type: ignore[assignment]
    server_version = "ChestTracker/1.0"

    def log_message(self, fmt, *args):  # keep the console quiet
        return

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Cache-Control", "no-store")

    def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8") -> None:
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, b"")

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/ping", "/health"):
            self._send(200, self.tracker.status_bytes())
        elif path in ("/hud.html", "/hud"):
            self._send(200, _hud_html or b"<h1>hud.html missing</h1>", "text/html; charset=utf-8")
        else:
            self._send(404, b'{"ok":false,"error":"not found"}')

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/shutdown":
            # answer first, then ask the tracker to quit. The tracker only
            # flags it; the UI thread runs the actual quit from its timer,
            # because app.quit() must not run inside a request handler.
            self._send(200, b'{"ok":true}')
            self.tracker.request_shutdown()
            return
        if path not in ("/event", "/chest", "/hud"):
            self._send(404, b'{"ok":false,"error":"not found"}')
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            self._send(400, b'{"ok":false,"error":"bad length"}')
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8", "replace"))
        except Exception:
            self._send(400, b'{"ok":false,"error":"bad json"}')
            return
        ok = bool(self.tracker.handle(payload))
        self._send(200 if ok else 400, b'{"ok":true}' if ok else b'{"ok":false}')


class Bridge:
    """Localhost HTTP listener used by the in-game HUD island."""

    def __init__(self, tracker, port: int = 4783, hud_html: bytes | None = None):
        global _hud_html
        if hud_html is not None:
            _hud_html = hud_html
        self.tracker = tracker
        self.port = port
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> bool:
        _Handler.tracker = self.tracker
        candidates = [self.port] + list(range(self.port + 1, self.port + 12))
        for candidate in candidates:
            try:
                self.httpd = ThreadingHTTPServer(("127.0.0.1", candidate), _Handler)
                self.port = candidate
                break
            except OSError:
                continue
        if self.httpd is None:
            return False
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="bridge", daemon=True)
        self.thread.start()
        return True

    def stop(self) -> None:
        if self.httpd is not None:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
            self.httpd = None


# -------------------------------------------------------------- log tailer --
def find_fortnite_logs() -> list[str]:
    """Best-effort locations of FortniteGame.log (informational only)."""
    cands: list[str] = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        cands.append(os.path.join(local, "FortniteGame", "Saved", "Logs", "FortniteGame.log"))
    for drive in "CDEFGH":
        cands.append(f"{drive}:\\Fortnite\\FortniteGame\\Saved\\Logs\\FortniteGame.log")
    return [p for p in cands if os.path.isfile(p)]


class LogTailer(threading.Thread):
    """Optional source: follow a text file and emit chest events from JSON lines.

    The in-game HUD can also write lines such as ``{"tier":"rare"}`` to a file;
    this tailer turns them into events without network sockets — handy when an
    island cannot do HTTP.
    """

    def __init__(self, tracker, path: str, patterns: Iterable[str] = ()):
        super().__init__(name="logtail", daemon=True)
        import re

        self.tracker = tracker
        self.path = path
        self.rx = []
        for raw in patterns:
            try:
                self.rx.append(re.compile(raw))
            except re.error:
                continue
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    @staticmethod
    def _tier_from_line(line: str) -> str | None:
        start, end = line.find("{"), line.rfind("}")
        if 0 <= start < end:
            try:
                obj = json.loads(line[start : end + 1])
            except Exception:
                return None
            for key in ("tier", "chest", "rarity"):
                value = obj.get(key)
                if isinstance(value, str):
                    return value.lower()
            if str(obj.get("type", "")).lower() in ("chest", "open", "opened"):
                return "common"
        return None

    def run(self) -> None:
        import time

        while not self._stop.is_set():
            if not os.path.isfile(self.path):
                time.sleep(1.0)
                continue
            try:
                with open(self.path, "r", encoding="utf-8", errors="replace") as fh:
                    fh.seek(0, os.SEEK_END)
                    while not self._stop.is_set():
                        line = fh.readline()
                        if not line:
                            if os.path.getsize(self.path) < fh.tell():
                                break
                            time.sleep(0.25)
                            continue
                        tier = None
                        for rx in self.rx:
                            m = rx.search(line)
                            if m:
                                tier = (m.groupdict().get("tier") or "common").lower()
                                break
                        if tier is None:
                            tier = self._tier_from_line(line)
                        if tier:
                            self.tracker.chest(tier)
            except Exception:
                time.sleep(1.0)
