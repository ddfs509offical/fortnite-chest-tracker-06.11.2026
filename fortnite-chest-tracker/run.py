"""Bootstrap: run the tracker with the bundled Python + PySide6 runtime.

Usage:  runtime\\python\\python.exe run.py [--demo] [--no-bridge] ...
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "runtime", "site")
if os.path.isdir(SITE) and SITE not in sys.path:
    sys.path.insert(0, SITE)

from chest_tracker.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
