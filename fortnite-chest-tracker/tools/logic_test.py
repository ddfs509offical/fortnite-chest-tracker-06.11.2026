"""In-app logic test: F1 flags, numpad moves the island, bridge answers."""

import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "runtime", "site"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

out = open(os.path.join(ROOT, "preview", "logic.txt"), "w", encoding="utf-8")


def p(*a):
    out.write(" ".join(str(x) for x in a) + "\n")
    out.flush()


results = []

try:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    from chest_tracker.events import Bridge
    from chest_tracker.hook import VK_F1, VK_NUMPAD_ADD, KeyHook
    from chest_tracker.overlay import PreviewWindow
    from chest_tracker.tracker import Tracker

    tracker = Tracker(os.path.join(ROOT, "preview", "settings_test.json"))
    tracker.settings["position"] = "top"
    window = PreviewWindow(tracker)
    window.show()

    flags = set()
    hook = KeyHook(flags.add)
    results.append(("hook installed", hook.start()))

    bridge = Bridge(tracker, port=4821)
    results.append(("bridge listening", bridge.start() and bridge.port == 4821))

    import urllib.request

    req = urllib.request.Request("http://127.0.0.1:4821/event", data=b'{"type":"connected"}',
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        results.append(("bridge post 200", r.status == 200))

    drain = QTimer()
    drain.setInterval(50)
    drain.timeout.connect(tracker.drain)
    drain.start()

    def on_key(vk):
        if vk == VK_F1:
            tracker.toggle()
            window.island.snap()
        elif vk == VK_NUMPAD_ADD:
            window.cycle_position()

    keys = QTimer()
    keys.setInterval(40)

    def consume():
        while flags:
            on_key(flags.pop())

    keys.timeout.connect(consume)
    keys.start()

    def step1():
        results.append(("bridge marked connected", tracker.connected))
        for t in ("rare", "epic", "legendary"):
            tracker.chest(t)

    def step2():
        results.append(("chests counted", tracker.chests == 3))
        flags.add(VK_F1)

    def step3():
        results.append(("F1 paused", tracker.enabled is False))
        before = tracker.chests
        tracker.chest("rare")
        results.append(("paused ignores chests", tracker.chests == before or f"bad:{tracker.chests} before={before}"))

    def step4():
        flags.add(VK_F1)

    def step5():
        results.append(("F1 resumed", tracker.enabled is True))
        tracker.chest("common")

    def step6():
        results.append(("counts after resume", tracker.chests == 4))
        flags.add(VK_NUMPAD_ADD)

    def step7():
        results.append(("numpad -> middle", tracker.settings["position"] == "middle"))
        centered = abs(window.island.island_rect().center().y() - window.island.screen_h / 2) < 2
        results.append(("island centered", centered))

    def finish():
        for name, value in results:
            p(f"{name}: {value}")
        ok = all(v is True for _, v in results)
        p("RESULT:", "PASS" if ok else "FAIL")
        bridge.stop()
        hook.stop()
        app.quit()
        os._exit(0)

    for ms, fn in [(800, step1), (950, step2), (1100, step3), (1250, step4),
                   (1400, step5), (1550, step6), (1700, step7)]:
        QTimer.singleShot(ms, fn)
    QTimer.singleShot(2600, finish)
    app.exec()
except BaseException:
    p("EXC", traceback.format_exc())
    os._exit(2)
