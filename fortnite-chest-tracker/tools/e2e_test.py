"""End-to-end: launch the real app (pythonw), talk to the bridge, measure, quit."""

import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PYW = os.path.join(ROOT, "runtime", "python", "pythonw.exe")
PORT = 4811
BASE = f"http://127.0.0.1:{PORT}"


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wt.DWORD),
        ("PageFaultCount", wt.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def mem(pid):
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x0410, False, pid)
    pmc = PROCESS_MEMORY_COUNTERS()
    pmc.cb = ctypes.sizeof(pmc)
    ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), ctypes.sizeof(pmc))
    k32.CloseHandle(h)
    return pmc.WorkingSetSize / 1048576, pmc.PagefileUsage / 1048576


def post(payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(BASE + "/event", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status


def ping():
    with urllib.request.urlopen(BASE + "/ping", timeout=5) as r:
        return json.loads(r.read().decode())


def main():
    log = open(os.path.join(ROOT, "preview", "e2e.log"), "wb")
    env = dict(os.environ)
    env.pop("QT_QPA_PLATFORM", None)
    proc = subprocess.Popen([PYW, os.path.join(ROOT, "run.py"), "--port", str(PORT)],
                            cwd=ROOT, env=env, stdout=log, stderr=log)
    ok = True
    try:
        time.sleep(5)
        print("ping:", ping())
        post({"type": "connected"})
        for tier in ("rare", "epic", "legendary"):
            post({"type": "chest", "tier": tier})
        time.sleep(0.4)
        st = ping()
        print("after 3 chests:", st)
        ok &= st["chests"] == 3 and st["connected"] is True

        post({"type": "toggle"})
        time.sleep(0.3)
        st = ping()
        print("toggle -> ", st)
        ok &= st["enabled"] is False

        post({"type": "disconnected"})
        time.sleep(0.3)
        print("disconnect:", ping())
        ok &= ping()["connected"] is False

        post({"type": "toggle"})
        time.sleep(0.3)
        ok &= ping()["enabled"] is True

        ws, priv = mem(proc.pid)
        print(f"RAM: working set {ws:.1f} MB, private {priv:.1f} MB")
    except Exception as exc:  # noqa: BLE001
        print("FAIL:", type(exc).__name__, exc)
        ok = False
    finally:
        try:
            urllib.request.urlopen(urllib.request.Request(BASE + "/shutdown", data=b"{}", method="POST"),
                                   timeout=5)
            proc.wait(timeout=10)
            print("clean exit:", proc.returncode)
        except Exception as exc:  # noqa: BLE001
            print("shutdown problem:", exc)
            ok = False
        if proc.poll() is None:
            proc.kill()
        log.close()
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
