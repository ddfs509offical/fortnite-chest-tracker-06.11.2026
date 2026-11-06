"""Centred tracker and all state the island renders.

Thread model: bridge / hook threads only enqueue events (``pending``), the Qt
thread drains them 20x per second and repaints. No locks, no cross-thread
widget access.
"""

from __future__ import annotations

import json
import os
import queue
import time


class TrackerSettings:
    def __init__(self, path: str = "") -> None:
        self.path = path

    def load(self) -> dict:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save(self, data: dict) -> None:
        try:
            folder = os.path.dirname(self.path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)     # never leave a half-written file
        except Exception:
            pass


class Tracker:
    def __init__(self, settings_path: str = "") -> None:
        self.settings_store = TrackerSettings(settings_path)
        self.settings = {
            "visible": True,
            "position": "top",
            "opacity": 1.0,
            "chests_total": 0,          # survives restarts
            "open_delay": 10.0,         # seconds after Fortnite starts
        }
        self.settings.update(self.settings_store.load())

        self.enabled = True            # F1 master switch
        self.connected = False         # island says "Connected"
        try:
            self.chests = max(0, int(self.settings.get("chests_total", 0) or 0))
        except (TypeError, ValueError):
            self.chests = 0
        self.session_chests = 0
        self.last_tier = ""
        self.last_chest_at = 0.0
        self.session_started = time.monotonic()
        self.last_event_at = 0.0
        self.show_disconnected = False   # red pill stays visible after a session
        self.pop_tier = ""
        self.pop_at = 0.0

        # Fortnite process state (set from the Qt thread by the game watcher)
        self.toggle_key_name = "F1"     # shown in the OFF hint; set by the app from the bindings
        self.require_game = True       # False: island is always shown (--always / demo)
        self.force_show = False        # tray switch "Show without Fortnite"
        self.game_running = False
        self.game_since: float | None = None

        self.pending: queue.Queue = queue.Queue()
        self.listeners: list = []
        self.shutdown_requested = False

    # ------------------------------------------------------------------ sources
    def chest(self, tier: str = "common") -> None:
        if not self.enabled:
            return
        self.pending.put(("chest", (tier or "common").lower()))

    def adjust(self, delta: int) -> None:
        """Manual correction (+1 / -1), only while tracking is on."""
        if not self.enabled:
            return
        self.pending.put(("adjust", int(delta)))

    def connected_event(self) -> None:
        self.pending.put(("connected", None))

    def disconnected_event(self) -> None:
        self.pending.put(("disconnected", None))

    def toggle(self) -> None:
        self.pending.put(("toggle", None))

    def reset(self) -> None:
        self.pending.put(("reset", None))

    def request_shutdown(self) -> None:
        self.shutdown_requested = True

    def handle(self, payload) -> bool:
        """Bridge entry point: JSON posted by the in-game HUD."""
        if isinstance(payload, list):
            return all(self.handle(item) for item in payload)
        if not isinstance(payload, dict):
            return False
        kind = str(payload.get("type") or payload.get("event") or "").lower()
        if kind in ("chest", "open", "opened"):
            if self.enabled:
                self.chest(str(payload.get("tier") or payload.get("rarity") or "common").lower())
            return True
        if kind in ("undo", "remove"):
            self.adjust(-1)
            return True
        if kind in ("connected", "connect", "session_start"):
            self.connected_event()
            return True
        if kind in ("disconnected", "disconnect", "session_end"):
            self.disconnected_event()
            return True
        if kind in ("toggle", "f1"):
            self.toggle()
            return True
        if kind == "reset":
            self.reset()
            return True
        if "tier" in payload or "rarity" in payload:
            # tier-only payload ({"tier":"rare"}) — the common island format
            if self.enabled:
                self.chest(str(payload.get("tier") or payload.get("rarity")).lower())
            return True
        return kind in ("ping", "hello")

    def status_bytes(self) -> bytes:
        return json.dumps(
            {
                "ok": True,
                "enabled": self.enabled,
                "connected": self.connected,
                "chests": self.chests,
                "session": int(self.play_seconds()),
            }
        ).encode()

    # ------------------------------------------------------------------ ui thread
    def drain(self) -> bool:
        touched = False
        changed = False
        while True:
            try:
                kind, value = self.pending.get_nowait()
            except queue.Empty:
                break
            touched = True
            now = time.monotonic()
            if kind == "chest":
                self.chests += 1
                self.session_chests += 1
                self.last_tier = value
                self.last_chest_at = now
                self.pop_tier = value
                self.pop_at = now
            elif kind == "connected":
                self.connected = True
                self.show_disconnected = False
                self.session_started = now
                self.session_chests = 0
                self.last_event_at = now
            elif kind == "disconnected":
                self.connected = False
                self.show_disconnected = True
                self.last_event_at = now
            elif kind == "adjust":
                self.chests = max(0, self.chests + int(value))
                if value > 0:
                    self.pop_tier = "common"
                    self.pop_at = now
                changed = True
            elif kind == "reset":
                self.chests = 0
                self.session_chests = 0
                self.last_tier = ""
                changed = True
            elif kind == "toggle":
                self.enabled = not self.enabled
            if kind == "chest":
                changed = True
        if changed:
            self.persist()
        if touched:
            for cb in self.listeners:
                cb()
        return touched

    def persist(self) -> None:
        """Write the running total so it survives restarts."""
        self.settings["chests_total"] = self.chests
        self.settings_store.save(self.settings)

    def set_game_running(self, running: bool) -> None:
        if running and not self.game_running:
            self.game_since = time.monotonic()
        elif not running:
            self.game_since = None
        self.game_running = running

    def panel_open(self) -> bool:
        """True once Fortnite has been running for ``open_delay`` seconds."""
        if not self.require_game or self.force_show:
            return True
        if not self.game_running or self.game_since is None:
            return False
        try:
            delay = float(self.settings.get("open_delay", 10.0))
        except (TypeError, ValueError):
            delay = 10.0
        return time.monotonic() - self.game_since >= delay

    def toggle_now(self) -> None:
        self.enabled = not self.enabled
        for cb in self.listeners:
            cb()

    # ------------------------------------------------------------------ derived
    def play_seconds(self) -> float:
        return max(0.0, time.monotonic() - self.session_started)

    def has_session(self) -> bool:
        return self.connected or self.session_chests > 0 or self.show_disconnected
