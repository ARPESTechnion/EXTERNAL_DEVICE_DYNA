"""
Simple launcher for the v3 GUI.

Two ways to choose mock vs real mode:

  1. Edit Use_MockUp below and SAVE this file, then rbrun it.
  2. Use a command-line flag (overrides the line below):
         python v3/run_app.py --mockup
         python v3/run_app.py --real
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from v3.gui.app import main

# ===========================================================
#  Easy startup toggle  (remember to SAVE the file!)
#  True  -> mock instruments (no hardware needed)
#  False -> real instruments
# ===========================================================
Use_MockUp = True
#Use_MockUp = False


def _resolve_mockup_flag() -> bool:
    """CLI flags (--mockup / --real) override the file-level toggle."""
    if "--mockup" in sys.argv:
        return True
    if "--real" in sys.argv:
        return False
    return Use_MockUp


if __name__ == "__main__":
    use_mockup = _resolve_mockup_flag()
    print(f"Starting v3 GUI -- MockUp={use_mockup}")
    main(use_mockup=use_mockup)
