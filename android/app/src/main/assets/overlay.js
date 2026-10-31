/*
 * ANVIL PANIC — Android control layer.
 *
 * Injected into the WebView after the game loads. It never touches the game's
 * code: the game already listens for ArrowLeft / ArrowRight / ShiftLeft, so the
 * pads and the tilt both just dispatch those.
 *
 * Three modes, cycled from the pill in the top-right:
 *   BTN    on-screen pads
 *   TILT   accelerometer (fed from MainActivity)
 *   TOUCH  nothing drawn; the game's own tap-hold / swipe / double-tap steering
 *
 * The chosen mode is remembered on the device.
 */
(() => {
  if (window.__ap) return;
  const STORE = 'ap.controls';
  const INK = '#151020';
  const CREAM = '#f7eddc';
  const CORAL = '#ff6b6b';

  let mode = 'buttons';
  try { mode = localStorage.getItem(STORE) || 'buttons'; } catch (e) { /* private mode */ }

  const hold = { left: false, right: false };

  // A synthetic KeyboardEvent still reaches the game's window listener. `repeat`
  // is set on hold-starts so the game does not read a held pad as a double-tap
  // and dash the player across the screen.
  function key(code, down, repeat) {
    const ev = new KeyboardEvent(down ? 'keydown' : 'keyup', {
      code, key: code, bubbles: true, cancelable: true, repeat: !!repeat
    });
    window.dispatchEvent(ev);
  }

  function press(dirName, on) {
    if (hold[dirName] === on) return;
    hold[dirName] = on;
    key(dirName === 'left' ? 'ArrowLeft' : 'ArrowRight', on, on);
  }

  function releaseAll() {
    press('left', false);
    press('right', false);
  }

  function dash() {
    key('ShiftLeft', true, false);
    setTimeout(() => key('ShiftLeft', false, false), 30);
  }

  // ------------------------------------------------------------------- markup
  const css = document.createElement('style');
  css.textContent = `
    #ap-ui { position: fixed; inset: 0; pointer-events: none; z-index: 9999;
             font-family: ui-monospace, "Roboto Mono", monospace; }
    #ap-ui .pad, #ap-ui .dash {
      position: absolute; display: grid; place-items: center;
      background: rgba(21,16,32,.55); color: ${CREAM};
      border: 3px solid rgba(247,237,220,.30); border-radius: 26px;
      pointer-events: auto; user-select: none; -webkit-user-select: none;
      -webkit-tap-highlight-color: transparent; touch-action: none;
      transition: background .07s linear, transform .07s linear;
    }
    #ap-ui .pad { width: 118px; height: 118px; bottom: 20px; }
    #ap-ui .pad.left  { left: 20px; }
    #ap-ui .pad.right { right: 20px; }
    #ap-ui .dash { width: 78px; height: 78px; left: 50%; margin-left: -39px;
                   bottom: 26px; border-radius: 50%; font-size: 22px; letter-spacing: 1px; }
    #ap-ui .pad svg { width: 46px; height: 46px; }
    #ap-ui .press { background: rgba(255,107,107,.55); transform: scale(.96);
                    border-color: ${CORAL}; }
    #ap-ui #ap-mode {
      position: absolute; top: 14px; right: 16px; pointer-events: auto;
      padding: 7px 13px; border-radius: 999px; font-size: 12px; letter-spacing: 2px;
      font-weight: 800; color: ${CREAM}; background: rgba(21,16,32,.62);
      border: 2px solid rgba(247,237,220,.28); -webkit-tap-highlight-color: transparent;
      user-select: none; -webkit-user-select: none;
    }
    #ap-ui #ap-hint {
      position: absolute; left: 50%; transform: translateX(-50%); bottom: 118px;
      color: ${CREAM}; font-size: 12px; letter-spacing: 1.6px;
      background: rgba(21,16,32,.55); padding: 6px 12px; border-radius: 999px;
      opacity: 0; transition: opacity .5s linear;
    }
    #ap-ui.touch .pad, #ap-ui.tilt .pad, #ap-ui.touch .dash { display: none; }
  `;
  document.head.appendChild(css);

  const ui = document.createElement('div');
  ui.id = 'ap-ui';
  ui.innerHTML = `
    <div class="pad left" data-dir="left" aria-label="move left">
      <svg viewBox="0 0 24 24" fill="none" stroke="${CREAM}" stroke-width="3"
           stroke-linecap="round" stroke-linejoin="round"><path d="M15 5 L8 12 L15 19"/></svg>
    </div>
    <div class="pad right" data-dir="right" aria-label="move right">
      <svg viewBox="0 0 24 24" fill="none" stroke="${CREAM}" stroke-width="3"
           stroke-linecap="round" stroke-linejoin="round"><path d="M9 5 L16 12 L9 19"/></svg>
    </div>
    <div class="dash" aria-label="dash">DASH</div>
    <div id="ap-mode"></div>
    <div id="ap-hint">HOLD TO MOVE · SWIPE · DOUBLE-TAP TO DASH</div>
  `;
  document.body.appendChild(ui);

  const modeEl = ui.querySelector('#ap-mode');
  const hintEl = ui.querySelector('#ap-hint');
  const LABEL = { buttons: 'BTN', tilt: 'TILT', touch: 'TOUCH' };

  function applyMode() {
    ui.className = mode === 'buttons' ? 'buttons' : mode;
    modeEl.textContent = LABEL[mode] || 'BTN';
    if (mode !== 'buttons') releaseAll();
    if (mode !== 'tilt') tiltDir = 0;
    try { localStorage.setItem(STORE, mode); } catch (e) { /* fine */ }
  }

  // ------------------------------------------------------------------- pads
  for (const pad of ui.querySelectorAll('.pad')) {
    const dir = pad.dataset.dir;
    const down = (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (mode !== 'buttons') return;
      pad.classList.add('press');
      press(dir, true);
    };
    const up = (e) => {
      e.preventDefault();
      e.stopPropagation();
      pad.classList.remove('press');
      press(dir, false);
    };
    pad.addEventListener('pointerdown', down);
    pad.addEventListener('pointerup', up);
    pad.addEventListener('pointercancel', up);
    pad.addEventListener('pointerleave', (e) => { if (e.buttons === 0) up(e); });
    pad.addEventListener('contextmenu', (e) => e.preventDefault());
  }

  const dashEl = ui.querySelector('.dash');
  dashEl.addEventListener('pointerdown', (e) => {
    e.preventDefault(); e.stopPropagation();
    if (mode !== 'buttons') return;
    dashEl.classList.add('press');
    dash();
  });
  for (const ev of ['pointerup', 'pointercancel', 'pointerleave']) {
    dashEl.addEventListener(ev, () => dashEl.classList.remove('press'));
  }

  // -------------------------------------------------------------------- mode
  let tiltDir = 0;

  modeEl.addEventListener('pointerdown', (e) => {
    e.preventDefault(); e.stopPropagation();
    const order = ['buttons', 'tilt', 'touch'];
    mode = order[(order.indexOf(mode) + 1) % order.length];
    applyMode();
  });

  applyMode();

  // First run gets the hint once, then never again.
  let seen = false;
  try { seen = localStorage.getItem('ap.hint') === '1'; } catch (e) { /* fine */ }
  if (!seen) {
    hintEl.style.opacity = '1';
    setTimeout(() => { hintEl.style.opacity = '0'; }, 5200);
    try { localStorage.setItem('ap.hint', '1'); } catch (e) { /* fine */ }
  }

  // -------------------------------------------------------------- public API
  window.__ap = {
    tilt(dir) {
      if (mode !== 'tilt') { if (tiltDir) { tiltDir = 0; releaseAll(); } return; }
      if (dir === tiltDir) return;
      tiltDir = dir;
      releaseAll();
      if (dir === -1) press('left', true);
      if (dir === 1) press('right', true);
    },
    mode(next) {
      if (next) { mode = next; applyMode(); }
      return mode;
    },
    releaseAll
  };

  // Losing focus must not leave a key stuck down.
  window.addEventListener('blur', releaseAll);
  document.addEventListener('visibilitychange', () => { if (document.hidden) releaseAll(); });
})();
