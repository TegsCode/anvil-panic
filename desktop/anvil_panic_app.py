"""ANVIL PANIC - desktop shell around anvil_panic.html.

A windowed app with no browser chrome: pywebview drives Edge's WebView2, so the
game renders exactly as it does in a browser. The HTML lives next to the exe
(or inside it when frozen), the icon is anvil.ico, and the window geometry is
remembered between runs so it opens where you left it.
"""

from __future__ import annotations

import ctypes
import json
import sys
import time
import traceback
from pathlib import Path

import webview

APP_TITLE = "ANVIL PANIC"
APP_ID = "PureGold.AnvilPanic"
MUTEX_NAME = "Local\\AnvilPanicWindow"
DEFAULT_SIZE = (1152, 700)
MIN_SIZE = (640, 400)
BG = "#08070d"

SELFTEST = "--selftest" in sys.argv


def base_dir() -> Path:
    """Folder that holds the exe (frozen) or this script (dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def bundled(name: str) -> Path:
    """Look inside the PyInstaller bundle first, then next to the exe."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidate = Path(meipass) / name
            if candidate.exists():
                return candidate
    return base_dir() / name


STATE_FILE = base_dir() / "anvil_window.json"
BEST_FILE = base_dir() / "anvil_best.json"
BEST_AT_LAUNCH = 0
CHAR_AT_LAUNCH = "honored"
BEST_LOG = []
GAME = bundled("anvil_panic.html")
ICON = bundled("anvil.ico")

CHAR_DEFAULT = "honored"
CHAR_IDS = {"honored", "ninja", "titan", "volt", "merc", "bat"}
_PREFS = None


# ------------------------------------------------------------ saved prefs
def _read_prefs() -> dict:
    """Best score + selected character, tolerating old files and junk."""
    try:
        data = json.loads(BEST_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    try:
        best = max(0, int(data.get("best", 0)))
    except (TypeError, ValueError):
        best = 0
    char = data.get("char", CHAR_DEFAULT)
    if char not in CHAR_IDS:
        char = CHAR_DEFAULT
    return {"best": best, "char": char}


def _prefs() -> dict:
    """One in-memory copy, so rapid bridge calls cannot clobber each other."""
    global _PREFS
    if _PREFS is None:
        _PREFS = _read_prefs()
    return _PREFS


def _write_prefs(prefs: dict) -> None:
    try:
        BEST_FILE.write_text(json.dumps(prefs), encoding="utf-8")
    except Exception:
        pass


def load_best() -> int:
    """The saved best, or 0 if the file is missing or unreadable."""
    return _prefs()["best"]


def save_best(value) -> int:
    """Store a best score. Never raises: a read-only folder just fails quietly."""
    try:
        n = max(0, int(value))
    except (TypeError, ValueError):
        return load_best()
    prefs = _prefs()
    prefs["best"] = n
    _write_prefs(prefs)
    if SELFTEST:
        BEST_LOG.append((round(time.time(), 2), n))
    return n


def load_char() -> str:
    return _prefs()["char"]


def save_char(value) -> str:
    char = str(value or "")
    if char not in CHAR_IDS:
        return load_char()
    prefs = _prefs()
    prefs["char"] = char
    _write_prefs(prefs)
    return char


# ------------------------------------------------------------------ one copy
_mutex = None


def claim_instance() -> bool:
    """True if we are the first copy. The mutex dies with the process."""
    global _mutex
    try:
        kernel32 = ctypes.windll.kernel32
        _mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        return kernel32.GetLastError() != 183   # ERROR_ALREADY_EXISTS
    except Exception:
        return True


def focus_existing() -> None:
    """Second launch: raise the window that is already open instead."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, APP_TITLE)
        if hwnd:
            user32.ShowWindow(hwnd, 9)          # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


# ------------------------------------------------------------------ geometry
def load_geometry():
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    try:
        w = int(data.get("w", DEFAULT_SIZE[0]))
        h = int(data.get("h", DEFAULT_SIZE[1]))
        x, y = data.get("x"), data.get("y")
        x = int(x) if x is not None else None
        y = int(y) if y is not None else None
    except (TypeError, ValueError):
        return None
    w = max(MIN_SIZE[0], min(w, 6000))
    h = max(MIN_SIZE[1], min(h, 4000))
    return {"w": w, "h": h, "x": x, "y": y}


def save_geometry(geo: dict) -> None:
    """Persist the last sane window rectangle (events keep it fresh; a
    minimised window reports 160x28 at -32000, which we never want to store)."""
    if SELFTEST:
        return                      # a test run must not clobber the real window spot
    if geo.get("w", 0) < MIN_SIZE[0] or geo.get("h", 0) < MIN_SIZE[1]:
        return
    try:
        STATE_FILE.write_text(json.dumps(geo), encoding="utf-8")
    except Exception:
        pass


def on_screen(x, y, w, h) -> bool:
    """Keep a remembered position only if a chunk of the window lands on a display."""
    try:
        user32 = ctypes.windll.user32
        vx = user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
        vy = user32.GetSystemMetrics(77)
        vw = user32.GetSystemMetrics(78)
        vh = user32.GetSystemMetrics(79)
    except Exception:
        return False
    return (x + w > vx + 60 and x < vx + vw - 60 and y + h > vy + 40 and y < vy + vh - 40)


# ---------------------------------------------------------------------- api
class Api:
    # NOTE: exposed attrs must stay underscore-prefixed - pywebview introspects
    # every public attribute of this object when it builds the JS bridge, and
    # walking a Window's .native .NET object recurses until Python gives up.
    def __init__(self) -> None:
        self._window = None
        self._full = False

    def attach(self, window) -> None:
        self._window = window

    def toggle_fullscreen(self) -> bool:
        try:
            self._window.toggle_fullscreen()
            self._full = not self._full
        except Exception:
            pass
        return self._full

    def quit(self) -> None:
        try:
            self._window.destroy()
        except Exception:
            pass

    # the page asks for these when localStorage is unavailable (file:// / private)
    def get_best(self) -> int:
        return load_best()

    def set_best(self, value) -> int:
        return save_best(value)

    def get_char(self) -> str:
        return load_char()

    def set_char(self, value) -> str:
        return save_char(value)


def on_loaded(window, api: Api) -> None:
    """Small shell niceties the browser build does not need."""
    try:
        window.evaluate_js(
            """
            (() => {
              if (window.__shell) return;
              window.__shell = true;
              window.addEventListener('keydown', (e) => {
                if (e.code === 'F11') {
                  e.preventDefault();
                  window.pywebview?.api?.toggle_fullscreen?.();
                }
              }, true);
              // keep keyboard focus on the canvas so arrows never scroll anything
              const c = document.getElementById('c');
              if (c) c.focus();
            })();
            """
        )
    except Exception:
        pass


# --------------------------------------------------------------------- main
def run_selftest(window) -> None:
    """Build smoke test: drive the real page and write what we saw, then quit."""
    import threading
    import time

    def work() -> None:
        result = {"ok": False}
        time.sleep(2.4)
        previous_best = BEST_AT_LAUNCH
        try:
            result["boot"] = window.evaluate_js(
                """
                (() => {
                  const c = document.querySelector('canvas');
                  const P = window.__panic;
                  if (!P || !c) return JSON.stringify({error: 'no canvas or hook'});
                  return JSON.stringify({
                    status: P.status,
                    dodged: P.dodged,
                    canvas: [c.width, c.height],
                    scale: +P.view.s.toFixed(4),
                    title: document.title,
                    best: P.best,
                    storedBest: P.storedBest,
                    character: P.character,
                    chips: P.chips.length,
                    storage: (() => { try { localStorage.setItem('__t', '1'); localStorage.removeItem('__t'); return 'localStorage'; } catch (e) { return 'blocked'; } })()
                  });
                })()
                """
            )
            try:
                boot = json.loads(result["boot"])
                result["bestPulled"] = boot.get("best") == BEST_AT_LAUNCH + 111
                result["charPulled"] = boot.get("character") == "ninja"
                result["rosterChips"] = boot.get("chips")
            except Exception:
                result["bestPulled"] = False
                result["charPulled"] = False
            result["run"] = window.evaluate_js(
                """
                (() => {
                  const P = window.__panic;
                  P.pause(true); P.clearObjects();
                  if (P.status === 'dead') { P.step(0.2); P.restart(); P.clearObjects(); }
                  const px0 = P.playerX;
                  P.setKeys(true, false); P.step(0.4); P.setKeys(false, false);
                  const moved = Math.round(px0 - P.playerX);
                  P.step(0.3);
                  P.squash();
                  const dead = P.status;
                  P.step(0.2); P.restart();
                  return JSON.stringify({
                    movedLeft: moved,
                    dead: dead,
                    afterRestart: P.status,
                    dodged: P.dodged,
                    best: P.best
                  });
                })()
                """
            )
            # the new verbs: dash, donuts, shield, i-frames, bounces, taunts
            result["features"] = window.evaluate_js(
                """
                (() => {
                  const P = window.__panic;
                  const out = {};
                  P.pause(true);
                  if (P.status === 'dead') P.restart();
                  P.stall(600);                       // no random junk during the test
                  P.clearObjects(); P.clearSnacks(); P.clearPointer(); P.setKeys(false, false);

                  // dash covers real distance and hands out i-frames
                  const x0 = P.playerX;
                  out.dashStarted = P.dash(1);
                  P.step(0.2);
                  out.dashTravel = Math.round(P.playerX - x0);
                  out.iframeAfterDash = +P.iframe.toFixed(2);
                  out.dashCd = +P.dashCd.toFixed(2);
                  P.step(0.8);

                  // two donuts, then the third makes a shield
                  P.giveDonut(2);
                  out.donutsBefore = P.donuts;
                  P.giveDonut(1);
                  out.shieldAfterDonuts = P.shield;
                  out.donutsAfter = P.donuts;

                  // a shield eats one direct hit instead of you
                  P.clearObjects();
                  const beforeHit = P.dodged;
                  P.drop(P.playerX, 'anvil');
                  P.step(1.4);
                  out.statusAfterShieldHit = P.status;
                  out.shieldSpent = (P.shield === 0);
                  out.dodgedGained = P.dodged - beforeHit;

                  // i-frames survive a direct hit; a dash is what grants them
                  P.clearObjects();
                  P.setIframe(2);
                  const beforeWhoosh = P.dodged;
                  P.drop(P.playerX, 'safe');
                  P.step(1.4);
                  out.statusAfterDashHit = P.status;
                  out.iframeSaved = P.dodged > beforeWhoosh;
                  out.iframeSpent = (P.iframe === 0);

                  // late-game bounce: force the clock past the threshold, then
                  // drop enough junk that the 32% hop is a certainty
                  P.clearObjects();
                  P.step(23);
                  P.stall(0.01);
                  P.setPointer(20); P.step(2.6); P.clearPointer();   // park the blob at the left wall
                  const parked = Math.round(P.playerX);
                  for (let i = 0; i < 26 && P.bounces === 0; i++) {
                    P.drop(340 + ((i * 97) % 500), 'anvil');
                    P.step(1.1);
                  }
                  out.bounces = P.bounces;
                  out.bounceParkedAt = parked;
                  out.bounceStatus = P.status;

                  // taunt picks something by killer, and the best score sticks
                  P.squash('piano');
                  out.taunt = P.taunt;
                  P.setBest(37);
                  out.best = P.best;
                  out.storedBest = P.storedBest;
                  out.recordedBest = P.setBest(0) === 0;
                  P.restart();
                  P.setBest(37);
                  P.stall(2);
                  return JSON.stringify(out);
                })()
                """
            )
            # the roster: passives, actives, chatter and the two-part death taunt
            result["characters"] = window.evaluate_js(
                """
                (() => {
                  const P = window.__panic;
                  const out = {};
                  P.pause(true);
                  P.stall(600); P.clearObjects(); P.clearSnacks();
                  P.clearPointer(); P.setKeys(false, false);

                  out.count = P.chips.length;
                  out.chipIds = P.chips.map(c => c.id);
                  out.start = P.character;

                  // titan begins every run with a shield
                  P.setChar('titan'); P.reset();
                  out.titanShield = P.shield;

                  // ninja's dash comes back faster than the base 1.05
                  P.setChar('ninja'); P.reset(); P.clearObjects();
                  P.dash(1);
                  out.ninjaDashCd = +P.dashCd.toFixed(2);
                  P.step(1.2);

                  // honored: Infinity refuses one direct hit, then recharges
                  P.setChar('honored'); P.reset(); P.clearObjects();
                  out.infinityBefore = P.passiveReady;
                  P.drop(P.playerX, 'anvil');
                  P.step(1.4);
                  out.infinitySaved = P.status === 'playing';
                  out.infinityAfter = P.passiveReady;
                  P.clearObjects();

                  // merc: exactly one free death, then the second one sticks
                  P.setChar('merc'); P.reset(); P.clearObjects();
                  P.drop(P.playerX, 'safe'); P.step(1.4);
                  out.mercRevived = P.status === 'playing';
                  out.mercRegenSpent = !P.passiveReady;
                  P.clearObjects(); P.step(1.8);      // let the revive i-frames expire
                  P.drop(P.playerX, 'safe'); P.step(1.4);
                  out.mercSecondHit = P.status;

                  // every active fires, starts a cooldown, and clears its targets
                  out.abilities = {};
                  for (const id of ['honored', 'ninja', 'titan', 'volt', 'merc', 'bat']) {
                    P.setChar(id); P.reset(); P.clearObjects();
                    P.drop(P.playerX - 24, 'anvil');
                    P.drop(P.playerX + 24, 'piano');
                    out.abilities[id] = {
                      used: P.useAbility(),
                      cd: +P.abilityCd.toFixed(1),
                      name: P.ability
                    };
                    P.step(0.2);
                    out.abilities[id].left = P.objects.filter(o => !o.landed).length;
                  }
                  out.abilityBlocked = !P.useAbility();   // bat is still cooling down

                  // each character actually paints its own body colour on screen
                  out.pixelsByChar = {};
                  const rgb = h => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
                  for (const id of ['honored', 'ninja', 'titan', 'volt', 'merc', 'bat']) {
                    P.setChar(id); P.reset(); P.clearObjects(); P.clearSnacks();
                    P.setKeys(false, false); P.clearPointer();
                    P.setShield(0);                 // the gold bubble tints the body
                    P.step(0.05); P.draw();
                    const b = rgb(P.palette.body);
                    let hits = 0, samples = 0;
                    for (let dx = -22; dx <= 22; dx += 2) {
                      for (let dy = -46; dy <= -4; dy += 2) {
                        const px = P.pixelAt(P.playerX + dx, 452 + dy);
                        samples++;
                        if (px && Math.abs(px[0] - b[0]) < 16 &&
                            Math.abs(px[1] - b[1]) < 16 && Math.abs(px[2] - b[2]) < 16) hits++;
                      }
                    }
                    out.pixelsByChar[id] = { body: P.palette.body, hits: hits, samples: samples };
                  }

                  // chatter lands, and death produces character line + object/score line
                  P.setChar('honored'); P.reset(); P.clearObjects();
                  out.chatterFired = P.chatter('testing, testing');
                  out.chatterText = P.chatterText;
                  P.squash('piano');
                  out.deathMain = P.tauntMain;
                  out.deathSub = P.taunt;
                  out.deathSplit = P.tauntMain.length > 0 && P.taunt.includes('\\u00b7');

                  // leave the machine on the launch character, mid-run
                  P.setChar('honored');
                  P.reset();
                  return JSON.stringify(out);
                })()
                """
            )
            # what the canvas actually contains right now (colour census, not vibes).
            # Set the scene, draw it explicitly (rAF is throttled in a hidden
            # window), then look at the pixels.
            window.evaluate_js(
                """
                (() => {
                  const P = window.__panic;
                  P.pause(true); P.clearObjects(); P.clearPointer(); P.setKeys(false, false);
                  P.giveShield();
                  P.step(0.4);
                  P.draw();
                  return P.shield;
                })()
                """
            )
            time.sleep(0.2)
            result["pixels"] = window.evaluate_js(
                """
                (() => {
                  const P = window.__panic;
                  const c = document.getElementById('c');
                  const g = c.getContext('2d');
                  const d = g.getImageData(0, 0, c.width, c.height).data;
                  let cream = 0, ink = 0, gold = 0, total = 0;
                  for (let i = 0; i < d.length; i += 4 * 7) {   // sample every 7th px
                    const r = d[i], gr = d[i + 1], b = d[i + 2];
                    total++;
                    if (r > 235 && gr > 225 && b > 200 && b < 240) cream++;
                    if (r < 40 && gr < 40 && b < 55) ink++;
                    if (r > 210 && gr > 170 && gr < 225 && b < 130) gold++;
                  }
                  return JSON.stringify({w: c.width, h: c.height, sampled: total, cream, ink, gold,
                                         shield: P.shield, frames: P.frames, err: P.lastError});
                })()
                """
            )
            # a small PNG of the canvas so the shell can be eyeballed later
            data_url = window.evaluate_js(
                """
                (() => {
                  const c = document.getElementById('c');
                  const t = document.createElement('canvas');
                  t.width = 480; t.height = Math.round(480 * c.height / c.width);
                  t.getContext('2d').drawImage(c, 0, 0, t.width, t.height);
                  return t.toDataURL('image/png');
                })()
                """
            )
            if isinstance(data_url, str) and data_url.startswith("data:image/png;base64,"):
                import base64
                raw = base64.b64decode(data_url.split(",", 1)[1])
                (base_dir() / "anvil_selftest_canvas.png").write_bytes(raw)
                result["canvas_png_bytes"] = len(raw)

            # the Python side of the best score, after the bridge call has landed
            time.sleep(0.8)
            result["bestFile"] = load_best()
            window.evaluate_js(
                f"window.__panic.setBest({previous_best});"
                f"window.__panic.setChar('{CHAR_AT_LAUNCH}')"
            )
            time.sleep(0.4)
            result["bestRestored"] = load_best()
            result["charRestored"] = load_char() == CHAR_AT_LAUNCH
            result["bestLog"] = BEST_LOG
            result["bestRaw"] = BEST_FILE.read_text(encoding="utf-8")
            result["ok"] = True
        except Exception as exc:                     # pragma: no cover - diagnostics
            result["error"] = repr(exc)
        try:
            (base_dir() / "anvil_selftest.json").write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
        except Exception:
            pass
        try:
            window.destroy()
        except Exception:
            pass

    threading.Thread(target=work, daemon=True).start()


def main() -> int:
    if not SELFTEST and not claim_instance():
        focus_existing()
        return 0

    if not GAME.exists():
        ctypes.windll.user32.MessageBoxW(
            None, f"anvil_panic.html is missing next to the app:\n{GAME}", APP_TITLE, 0x10
        )
        return 1

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass

    geo = load_geometry() or {}
    w = geo.get("w", DEFAULT_SIZE[0])
    h = geo.get("h", DEFAULT_SIZE[1])
    x, y = geo.get("x"), geo.get("y")
    if x is not None and y is not None and not on_screen(x, y, w, h):
        x = y = None

    api = Api()
    window = webview.create_window(
        APP_TITLE,
        url=GAME.as_uri(),
        js_api=api,
        width=w,
        height=h,
        x=x,
        y=y,
        min_size=MIN_SIZE,
        resizable=True,
        background_color=BG,
        text_select=False,
        zoomable=False,
        easy_drag=False,
        confirm_close=False,
        focus=True,
    )
    api.attach(window)

    tracked = {"w": w, "h": h, "x": x, "y": y}

    def on_resized(width, height):
        if width >= MIN_SIZE[0] and height >= MIN_SIZE[1]:
            tracked["w"], tracked["h"] = int(width), int(height)

    def on_moved(px, py):
        if px > -10000 and py > -10000:
            tracked["x"], tracked["y"] = int(px), int(py)

    window.events.resized += on_resized
    window.events.moved += on_moved
    window.events.loaded += lambda: on_loaded(window, api)
    window.events.closing += lambda: save_geometry(tracked)
    if SELFTEST:
        window.events.loaded += lambda: run_selftest(window)

    if SELFTEST:
        # write a known best + roster pick before the page boots, so the test
        # can prove the bridge hands the saved state back to the game on launch
        global BEST_AT_LAUNCH, CHAR_AT_LAUNCH
        BEST_AT_LAUNCH = load_best()
        CHAR_AT_LAUNCH = load_char()
        save_best(BEST_AT_LAUNCH + 111)
        save_char("ninja")

    webview.start(icon=str(ICON) if ICON.exists() else None, private_mode=True)
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception:
        try:
            (base_dir() / "anvil_error.log").write_text(traceback.format_exc(), encoding="utf-8")
        except Exception:
            pass
        raise
    sys.exit(code)
