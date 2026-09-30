import os
import sys
from pathlib import Path

from gui import run

if getattr(sys, "frozen", False):
    BASE = Path(sys.executable).parent
    os.chdir(BASE)

if __name__ == "__main__":
    run()