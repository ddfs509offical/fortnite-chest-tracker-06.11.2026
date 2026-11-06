"""Entry point: tray icon, F1 hotkey, localhost bridge and overlay wiring."""

from __future__ import annotations

import argparse
import os
import sys

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from . import icons

APP_NAME = "Fortnite Chest Tracker"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _data_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    for path in (os.path.join(base, "FortniteChestTracker"), os.path.join(ROOT, "data")):
        try:
            os.makedirs(path, exist_ok=True)
            return path
        except OSError:
            continue
    return ROOT


def _tray_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.setDevicePixelRatio(2.0)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(18, 18, 20))
    p.drawEllipse(QRectF(1, 1, 30, 30))
    icons.draw_chest(p, QRectF(5, 6, 22, 22), QColor("#ffc457"))
    p.end()
    return QIcon(pm)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--demo", action="store_true", help="simulate chests for a visual test")
    parser.add_argument("--preview", action="store_true", help="opaque background (screenshots)")
    parser.add_argument("--snapshot", default="", help="save a PNG of the island and exit")
    parser.add_argument("--port", type=int, default=4783, help="localhost bridge port")
    parser.add_argument("--no-bridge", action="store_true", help="do not open the bridge")
    parser.add_argument("--no-tray", action="store_true", help="skip the tray icon")
    parser.add_argument("--start-hidden", action="store_true",
                        help="start with the island hidden (last state still remembered)")
    args = parser.parse_args(argv)

    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    data = _data_dir()

    from .tracker import Tracker

    tracker = Tracker(os.path.join(data, "settings.json"))

    from .events import Bridge
    from .hook import VK_F1, VK_NUMPAD_ADD, KeyHook
    from .overlay import OverlayWindow, PreviewWindow

    window = PreviewWindow(tracker) if args.preview else OverlayWindow(tracker)
    app.aboutToQuit.connect(lambda: tracker.settings_store.save(tracker.settings))

    # ---------------------------------------------------------------- bridge
    hud_path = os.path.join(ROOT, "hud.html")
    hud_html = None
    if os.path.isfile(hud_path):
        with open(hud_path, "rb") as fh:
            hud_html = fh.read()
    bridge = None
    bridge_ok = False
    if not args.no_bridge:
        bridge = Bridge(tracker, port=args.port, hud_html=hud_html)
        bridge_ok = bridge.start()

    # ---------------------------------------------------------------- F1
    key_flags = set()          # filled by the hook thread, consumed by the UI

    def on_key(vk: int) -> None:
        key_flags.add(vk)

    hotkey = KeyHook(on_key)
    hotkey_ok = hotkey.start()

    keys_timer = QTimer()
    keys_timer.setInterval(40)
    keys_timer.setTimerType(Qt.TimerType.CoarseTimer)

    def _consume_keys() -> None:
        hotkey.poll()          # reads key state only; installs no hook
        while key_flags:
            vk = key_flags.pop()
            if vk == VK_F1:
                tracker.toggle()
                window.island.snap()
            elif vk == VK_NUMPAD_ADD:
                window.cycle_position()

    keys_timer.timeout.connect(_consume_keys)
    keys_timer.start()

    # ---------------------------------------------------------------- drain
    drain = QTimer()
    drain.setInterval(50)
    drain.setTimerType(Qt.TimerType.CoarseTimer)

    def _drain() -> None:
        if tracker.drain():
            window.update()
        if tracker.shutdown_requested:
            drain.stop()
            app.quit()

    drain.timeout.connect(_drain)
    drain.start()

    # ---------------------------------------------------------------- demo
    if args.demo:
        import random

        tiers = ["common", "uncommon", "rare", "epic", "legendary"]

        def _demo_tick() -> None:
            if not tracker.enabled:
                return
            roll = random.random()
            if roll < 0.06:
                tracker.connected_event()
            elif roll < 0.10:
                tracker.disconnected_event()
            else:
                tracker.chest(random.choice(tiers))

        demo = QTimer()
        demo.setInterval(2400)
        demo.timeout.connect(_demo_tick)
        demo.start()
        tracker.connected_event()

    # ---------------------------------------------------------------- tray
    if not args.preview and not args.no_tray and QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon(_tray_icon(), app)
        menu = QMenu()
        act_toggle = QAction("Pause (F1)", menu)
        act_show = QAction("Hide island", menu)
        act_quit = QAction("Quit", menu)
        menu.addAction(act_toggle)
        menu.addAction(act_show)
        menu.addSeparator()
        menu.addAction(act_quit)

        def _sync() -> None:
            act_toggle.setText("Resume (F1)" if not tracker.enabled else "Pause (F1)")
            act_show.setText("Hide island" if window.isVisible() else "Show island")

        def _toggle() -> None:
            tracker.toggle_now()
            _sync()

        def _show() -> None:
            window.set_visible(not window.isVisible())
            tracker.settings["visible"] = window.isVisible()
            _sync()

        act_toggle.triggered.connect(_toggle)
        act_show.triggered.connect(_show)
        act_quit.triggered.connect(app.quit)
        tray.setContextMenu(menu)
        tray.setToolTip(APP_NAME + " — F1 on/off")
        tray.show()
        tracker.listeners.append(_sync)
        _sync()
    else:
        tray = None

    visible = bool(tracker.settings.get("visible", True)) and not args.start_hidden
    window.set_visible(visible)
    window.update()

    # ---------------------------------------------------------------- hints
    if not hotkey_ok:
        QTimer.singleShot(
            1200,
            lambda: QMessageBox.information(
                None,
                APP_NAME,
                "Не удалось начать отслеживание F1 — используйте пункт «Pause (F1)» в трее.",
            ),
        )

    if args.snapshot:
        def _shoot() -> None:
            window.grab().save(args.snapshot)
            app.quit()

        QTimer.singleShot(1200, _shoot)

    try:
        code = app.exec()
    finally:
        hotkey.stop()
        if bridge is not None:
            bridge.stop()
        if tray is not None:
            tray.hide()
    print(f"bridge={'on:' + str(bridge.port) if bridge_ok else 'off'} hotkey={'hook' if hotkey_ok else 'none'}")
    return code
