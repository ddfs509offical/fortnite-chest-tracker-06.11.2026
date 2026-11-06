"""Trim the bundled runtime to what the overlay needs (~87 MB instead of ~345).

Deletes Qt QML/Quick/docs/dev files, Python's debug symbols, Tcl/Tk and pip —
none of them are loaded by the app. Run tools/restore_runtime.py (then this,
if needed) if you ever remove too much; both are idempotent.
"""

import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RUNTIME = os.path.join(ROOT, "runtime")
SITE = os.path.join(RUNTIME, "site")
PKG = os.path.join(SITE, "PySide6")
SHIBOKEN = os.path.join(SITE, "shiboken6")
PY = os.path.join(RUNTIME, "python")

SITE_DIRS = (
    "doc include lib metatypes qml scripts translations typesystems glue support resources "
    "plugins/designer plugins/generic plugins/sqldrivers plugins/qmltooling "
    "plugins/vectorimageformats plugins/styles plugins/iconengines plugins/imageformats "
    "plugins/networkinformation plugins/platforminputcontexts plugins/tls "
    "plugins/multimedia plugins/webview"
).split()

MODULES = {"QtCore", "QtGui", "QtWidgets", "QtDBus", "QtNetwork", "QtSvg", "QtConcurrent"}

KEEP_PY = {
    "__init__.py", "_config.py", "_git_pyside_version.py", "_git_shiboken_module_version.py",
    "py.typed", "PySide6_Essentials.json", "_feature_.pyi",
}
KEEP_DLLS = {
    "Qt6Core.dll", "Qt6Gui.dll", "Qt6Widgets.dll", "Qt6DBus.dll", "Qt6Network.dll", "Qt6Svg.dll",
    "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll", "msvcp140_codecvt_ids.dll",
    "concrt140.dll", "vcruntime140.dll", "vcruntime140_1.dll", "vcamp140.dll",
    "vccorlib140.dll", "vcomp140.dll",
}
KEEP_PLUGINS = {"qwindows.dll", "qoffscreen.dll"}

PY_DIRS = [
    "python/Lib/test", "python/Lib/idlelib", "python/Lib/tkinter", "python/Lib/turtledemo",
    "python/Lib/ensurepip", "python/Lib/lib2to3", "python/Lib/pydoc_data",
    "python/Lib/site-packages/pip", "python/tcl",
]
PY_DLLS = ["python/DLLs/tcl86t.dll", "python/DLLs/tk86t.dll", "python/DLLs/_tkinter.pyd"]


def rm(path: str) -> None:
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def main() -> int:
    if not os.path.isdir(PKG):
        print("runtime/site/PySide6 not found — run tools/setup.py first")
        return 1

    for d in SITE_DIRS:
        rm(os.path.join(PKG, d.replace("/", os.sep)))
    for extra in ("include", "lib"):
        rm(os.path.join(SHIBOKEN, extra))

    for name in os.listdir(PKG):
        path = os.path.join(PKG, name)
        if not os.path.isfile(path):
            continue
        if name.endswith((".exe", ".lib")):
            rm(path)
        elif name.endswith(".dll") and name not in KEEP_DLLS:
            rm(path)
        elif name.endswith(".pyd"):
            stem = name.split(".")[0]
            if stem not in MODULES and stem != "pyside6":
                rm(path)
        elif name.endswith(".pyi"):
            if name.lstrip("_").split(".")[0] not in MODULES:
                rm(path)
        elif name not in KEEP_PY and not name.endswith(".py"):
            rm(path)

    plat = os.path.join(PKG, "plugins", "platforms")
    if os.path.isdir(plat):
        for name in os.listdir(plat):
            if name not in KEEP_PLUGINS:
                rm(os.path.join(plat, name))

    for d in PY_DIRS:
        rm(os.path.join(RUNTIME, d.replace("/", os.sep)))
    for f in PY_DLLS:
        rm(os.path.join(RUNTIME, f.replace("/", os.sep)))
    for root, _dirs, files in os.walk(RUNTIME):
        for f in files:
            if f.endswith(".pdb"):
                rm(os.path.join(root, f))

    total = 0
    for root, _dirs, files in os.walk(RUNTIME):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    print(f"runtime: {total / 1048576:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
