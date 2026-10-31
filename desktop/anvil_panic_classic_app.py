"""ANVIL PANIC (CLASSIC) - desktop entry point for the pre-character build.

Same window shell as the current game, pointed at anvil_panic_classic.html and
at its own saved-score file, so both builds can sit side by side without
overwriting each other's numbers or fighting over the single-instance mutex.
"""

from __future__ import annotations

import sys
import traceback

import anvil_panic_app as shell

shell.APP_TITLE = "ANVIL PANIC (CLASSIC)"
shell.APP_ID = "PureGold.AnvilPanic.Classic"
shell.MUTEX_NAME = "Local\\AnvilPanicClassicWindow"
shell.STATE_FILE = shell.base_dir() / "anvil_window_classic.json"
shell.BEST_FILE = shell.base_dir() / "anvil_best_classic.json"
shell._PREFS = None
shell.GAME = shell.bundled("anvil_panic_classic.html")


if __name__ == "__main__":
    try:
        code = shell.main()
    except Exception:
        try:
            (shell.base_dir() / "anvil_classic_error.log").write_text(
                traceback.format_exc(), encoding="utf-8"
            )
        except Exception:
            pass
        code = 1
    sys.exit(code)
