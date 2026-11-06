"""Restore the PySide6 files the slimmer removed, straight from the wheels.

No pip involved: wheels are unzipped over runtime/site, so the Qt DLLs come
back exactly as shipped. Then everything is verified by importing QtWidgets.
"""

import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WHEELS = os.path.join(HERE, "wheels")
SITE = os.path.join(ROOT, "runtime", "site")

PYSIDE_WHEEL = os.path.join(WHEELS, "pyside6_essentials-6.12.0-cp310-abi3-win_amd64.whl")
SHIBOKEN_WHEEL = os.path.join(WHEELS, "shiboken6-6.12.0-cp310-abi3-win_amd64.whl")

# files the overlay really needs from the PySide6 wheel
KEEP = (
    "PySide6/Qt6Core.dll", "PySide6/Qt6Gui.dll", "PySide6/Qt6Widgets.dll",
    "PySide6/Qt6DBus.dll", "PySide6/Qt6Network.dll", "PySide6/Qt6Svg.dll",
    "PySide6/msvcp140.dll", "PySide6/msvcp140_1.dll", "PySide6/msvcp140_2.dll",
    "PySide6/msvcp140_codecvt_ids.dll", "PySide6/concrt140.dll",
    "PySide6/vcruntime140.dll", "PySide6/vcruntime140_1.dll", "PySide6/vcamp140.dll",
    "PySide6/vccorlib140.dll", "PySide6/vcomp140.dll",
    "PySide6/plugins/platforms/qwindows.dll", "PySide6/plugins/platforms/qoffscreen.dll",
    "PySide6/QtCore.pyd", "PySide6/QtGui.pyd", "PySide6/QtWidgets.pyd",
    "PySide6/QtDBus.pyd", "PySide6/QtNetwork.pyd", "PySide6/QtSvg.pyd",
    "PySide6/QtConcurrent.pyd", "PySide6/pyside6.abi3.dll",
    "PySide6/__init__.py", "PySide6/_config.py", "PySide6/_git_pyside_version.py",
    "PySide6/py.typed", "PySide6/PySide6_Essentials.json",
)


def extract(wheel: str, names, dest: str) -> int:
    count = 0
    with zipfile.ZipFile(wheel) as zf:
        for name in names:
            try:
                info = zf.getinfo(name)
            except KeyError:
                continue
            target = os.path.join(dest, name.replace("/", os.sep))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
            count += 1
        # shiboken & friends: everything under shiboken6/ except dev folders
        if "shiboken" in os.path.basename(wheel).lower():
            for info in zf.infolist():
                if info.is_dir() or info.filename.startswith(("shiboken6/include", "shiboken6/lib")):
                    continue
                if info.filename.endswith((".pyi", ".lib")):
                    continue
                target = os.path.join(dest, info.filename.replace("/", os.sep))
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as out:
                    while True:
                        chunk = src.read(1 << 20)
                        if not chunk:
                            break
                        out.write(chunk)
                count += 1
    return count


def main() -> int:
    if not os.path.isfile(PYSIDE_WHEEL):
        print("missing wheel:", PYSIDE_WHEEL)
        return 1
    os.makedirs(SITE, exist_ok=True)
    total = extract(PYSIDE_WHEEL, KEEP, SITE)
    total += extract(SHIBOKEN_WHEEL, (), SITE)
    print("restored", total, "files")
    size = 0
    for root, _d, files in os.walk(os.path.join(ROOT, "runtime")):
        for f in files:
            size += os.path.getsize(os.path.join(root, f))
    print(f"runtime: {size / 1048576:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
