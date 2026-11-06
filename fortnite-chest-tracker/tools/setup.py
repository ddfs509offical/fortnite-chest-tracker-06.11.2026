"""One-shot setup: download the portable CPython + PySide6 wheels and build
``runtime/`` (python + site-packages). Needs any Python 3.8+ to run.

    python tools/setup.py
"""

import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WHEELS = os.path.join(HERE, "wheels")
RUNTIME = os.path.join(ROOT, "runtime")

FILES = {
    "python.tar.gz": (
        "https://github.com/astral-sh/python-build-standalone/releases/download/"
        "20250626/cpython-3.12.11+20250626-x86_64-pc-windows-msvc-install_only.tar.gz"
    ),
    "pyside6_essentials-6.12.0-cp310-abi3-win_amd64.whl": (
        "https://files.pythonhosted.org/packages/03/61/9a7e32a37b224f68506785bfb0f288d516098"
        "ec71681782d72b695a6c95d/pyside6_essentials-6.12.0-cp310-abi3-win_amd64.whl"
    ),
    "shiboken6-6.12.0-cp310-abi3-win_amd64.whl": (
        "https://files.pythonhosted.org/packages/2a/b6/bee97e7a2edeab72aafabb46ee5adc939790a"
        "638d107860b4cad7a20e407/shiboken6-6.12.0-cp310-abi3-win_amd64.whl"
    ),
}
HASHES = {
    "python.tar.gz": "36c5db0f7cf0340286fe322795cb0ee80fd92443851f8ccf8a87720a767178c7",
    "pyside6_essentials-6.12.0-cp310-abi3-win_amd64.whl":
        "c9a95102aa23c1f86516a30d5a9be37552d324eee7e567eb7508973f1218cb42",
    "shiboken6-6.12.0-cp310-abi3-win_amd64.whl":
        "a1906cb8116869178c64b6bab52623bbc8b4ceed7b30bfc3c9aa0f6e67f6438e",
}


def fetch(name: str) -> str:
    import hashlib

    path = os.path.join(WHEELS, name)
    if os.path.isfile(path):
        with open(path, "rb") as fh:
            if hashlib.sha256(fh.read()).hexdigest() == HASHES[name]:
                return path
    print("downloading", name)
    req = urllib.request.Request(FILES[name], headers={"User-Agent": "setup"})
    with urllib.request.urlopen(req, timeout=600) as resp, open(path + ".part", "wb") as out:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    os.replace(path + ".part", path)
    return path


def main() -> int:
    os.makedirs(WHEELS, exist_ok=True)
    for name in FILES:
        fetch(name)
    if os.path.isdir(RUNTIME):
        import shutil

        shutil.rmtree(RUNTIME)
    import assemble_runtime  # same folder

    sys.argv = ["assemble", WHEELS, RUNTIME]
    assemble_runtime.src, assemble_runtime.dest = WHEELS, RUNTIME
    assemble_runtime.main()
    print("runtime ready:", RUNTIME)
    return 0


if __name__ == "__main__":
    sys.exit(main())
