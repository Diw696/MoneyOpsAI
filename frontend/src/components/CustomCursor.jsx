import React, { useEffect, useRef } from 'react';
import { usePrefersReducedMotion, useIsFinePointer } from '../hooks/useMotionGuards';

// Phase 2.1 — reconciled against the original §3.3 state table exactly:
//
//   default   — 26px ring (lerp 0.16/frame follow), 5px dot (zero-lag follow)
//   hover     — button/nav/chip: ring snaps to the element's real bounding
//               box + border-radius, dot disappears, element gets a magnetic
//               translate(dx*0.18, dy*0.18) capped at 6px, smooth restore
//   row       — table row: ring becomes a full-width horizontal line + an
//               18px crosshair centered exactly on the cursor
//   text      — ring fades out completely, dot becomes a 2x18px caret
//   disabled  — ring border -> --cc-text-disabled, dot becomes a 1px slash
//   mousedown — ring scales to 0.86, dot scales to 1.6, springs back on up
//   primary   — one-shot ripple (26px -> 64px, fades over 420ms) on a
//               primary-action click; fires exactly once per click
//
// The earlier "danger" state from the first Phase 2 pass is REMOVED here:
// audited via grep across every component file and it had zero real usages
// (no page file ever set data-cursor="danger") — it wasn't part of this
// spec and had no legitimate semantic use, so it's deleted rather than
// renamed into one of the states above.
// button/a/[role=button]/select are matched as a baseline (real semantic
// interactive elements, not an "incidental class name"); [data-cursor="hover"]
// is the explicit opt-in the Phase 3 primitives declare themselves — Chip,
// Card, SegmentedControl option, Toast dismiss, and Drawer close all carry
// it even though most of them are real <button>s anyway, so the affordance
// doesn't silently depend on which tag a future primitive happens to render.
const INTERACTIVE_SELECTOR = 'button, a, [role="button"], select, [data-cursor="hover"]';
const TEXT_SELECTOR = 'input[type="text"], input[type="search"], input:not([type]), textarea, [contenteditable="true"]';
const DISABLED_SELECTOR = '[disabled], [aria-disabled="true"]';
const ROW_SELECTOR = 'tbody tr';

const RING_DEFAULT_SIZE = 26;
const DOT_DEFAULT_SIZE = 5;
const CROSSHAIR_SIZE = 18;
const RING_LERP = 0.16;
const MAGNETIC_STRENGTH = 0.18;
const MAGNETIC_MAX = 6;
const RIPPLE_START = 26;
const RIPPLE_END = 64;
const RIPPLE_DURATION = 420;

// "Primary-action click" is detected two ways: the app's existing
// `.btn-primary` class (used consistently across every current page for
// its one loud CTA per view: Ask, Investigate with Gemini, Run Anomaly
// Scan, Upload Financial Data, Review, etc.) for backward compatibility,
// and the Phase 3 primitive Button's explicit `data-cursor="primary"` —
// the preferred, non-incidental affordance new primitives should use going
// forward. (An earlier draft tried detecting via computed backgroundColor
// matching --cc-accent, but .btn-primary renders a gradient — a
// background-image, not a background-color — so that never matched
// anything; checking the marker directly is what's actually reliable.)
const PRIMARY_ACTION_SELECTOR = '.btn-primary, [data-cursor="primary"]';

export default function CustomCursor({ enabled }) {
  const isFinePointer = useIsFinePointer();
  const prefersReducedMotion = usePrefersReducedMotion();
  const active = enabled && isFinePointer && !prefersReducedMotion;

  const dotRef = useRef(null);
  const ringRef = useRef(null);
  const crosshairHRef = useRef(null);
  const crosshairVRef = useRef(null);

  // Raw cursor position (zero-lag) and the ring's own lerped position —
  // both refs, never React state, so mousemove causes zero re-renders.
  const mouseRef = useRef({ x: -100, y: -100 });
  const ringPosRef = useRef({ x: -100, y: -100 });
  const stateRef = useRef('default');
  const pressedRef = useRef(false);
  // Eased toward their target each frame (not snapped) so release reads as
  // a spring rather than an instant jump — avoids CSS-transitioning
  // `transform` itself, which would also fight the every-frame position
  // updates above (translate3d) and reintroduce lag where the spec wants
  // zero lag or an exact snap.
  const ringScaleRef = useRef(1);
  const dotScaleRef = useRef(1);
  const hoveredMagneticElRef = useRef(null);
  const rafRef = useRef(null);

  useEffect(() => {
    if (!active) return undefined;

    document.documentElement.classList.add('cc-custom-cursor-active');

    const dot = dotRef.current;
    const ring = ringRef.current;
    const chH = crosshairHRef.current;
    const chV = crosshairVRef.current;

    const resetRingShape = () => {
      ring.style.width = `${RING_DEFAULT_SIZE}px`;
      ring.style.height = `${RING_DEFAULT_SIZE}px`;
      ring.style.borderRadius = '50%';
      ring.style.opacity = '1';
    };

    // No CSS margin-based centering anywhere (see index.css) — every
    // transform below explicitly computes its own centering offset, since
    // hover/row need TOP-LEFT alignment to a real element rect while every
    // other state needs the shape CENTERED on the cursor point, and the
    // shapes themselves change size per state.
    const center = (px, py, w, h) => `translate3d(${px - w / 2}px, ${py - h / 2}px, 0)`;

    const tick = () => {
      const state = stateRef.current;
      const pressed = pressedRef.current;
      const { x: mx, y: my } = mouseRef.current;

      // Eased toward the pressed target every frame — this is what gives
      // "spring back on release" its feel, rather than an instant snap.
      const ringScaleTarget = pressed ? 0.86 : 1;
      const dotScaleTarget = pressed ? 1.6 : 1;
      ringScaleRef.current += (ringScaleTarget - ringScaleRef.current) * 0.3;
      dotScaleRef.current += (dotScaleTarget - dotScaleRef.current) * 0.3;

      if (state === 'hover') {
        // Snapped to the hovered element's real box — no lerp, updated every
        // frame in case the element itself moves (e.g. under scroll).
        const el = hoveredMagneticElRef.current;
        dot.style.opacity = '0';
        chH.style.opacity = '0';
        chV.style.opacity = '0';
        if (el && el.isConnected) {
          const r = el.getBoundingClientRect();
          const cs = getComputedStyle(el);
          ring.style.width = `${r.width}px`;
          ring.style.height = `${r.height}px`;
          ring.style.borderRadius = cs.borderRadius && cs.borderRadius !== '0px' ? cs.borderRadius : '6px';
          ring.style.opacity = '1';
          ring.style.borderColor = 'var(--cc-accent)';
          ring.style.transformOrigin = 'top left';
          ring.style.transform = `translate3d(${r.left}px, ${r.top}px, 0) scale(${ringScaleRef.current})`;
        }
      } else if (state === 'row') {
        const el = hoveredMagneticElRef.current;
        dot.style.opacity = '0';
        if (el && el.isConnected) {
          const r = el.getBoundingClientRect();
          ring.style.width = `${r.width}px`;
          ring.style.height = '2px';
          ring.style.borderRadius = '1px';
          ring.style.opacity = '1';
          ring.style.borderColor = 'var(--cc-accent)';
          ring.style.transformOrigin = 'top left';
          const y = Math.min(Math.max(my, r.top), r.bottom);
          ring.style.transform = `translate3d(${r.left}px, ${y - 1}px, 0)`;
        }
        // 18px crosshair, zero-lag, centered exactly on the raw cursor.
        chH.style.opacity = '1';
        chV.style.opacity = '1';
        chH.style.transform = center(mx, my, CROSSHAIR_SIZE, 1);
        chV.style.transform = center(mx, my, 1, CROSSHAIR_SIZE);
      } else {
        chH.style.opacity = '0';
        chV.style.opacity = '0';

        if (state === 'default') {
          dot.style.opacity = '1';
          dot.style.width = `${DOT_DEFAULT_SIZE}px`;
          dot.style.height = `${DOT_DEFAULT_SIZE}px`;
          dot.style.borderRadius = '50%';
          dot.style.transform = `${center(mx, my, DOT_DEFAULT_SIZE, DOT_DEFAULT_SIZE)} scale(${dotScaleRef.current})`;

          resetRingShape();
          // Ring follows with lerp 0.16/frame — the one state that actually
          // trails the cursor rather than snapping.
          ringPosRef.current.x += (mx - ringPosRef.current.x) * RING_LERP;
          ringPosRef.current.y += (my - ringPosRef.current.y) * RING_LERP;
          // See the long comment on .cc-cursor-ring in index.css: this used
          // to be --line-solid, which is nearly invisible against the page
          // background (1.62:1 measured contrast) — --cc-text-tertiary
          // clears 4.77:1, so the idle ring is now actually visible.
          ring.style.borderColor = 'var(--cc-text-tertiary)';
          ring.style.background = 'rgba(255, 255, 255, 0.02)';
          ring.style.transform = `${center(ringPosRef.current.x, ringPosRef.current.y, RING_DEFAULT_SIZE, RING_DEFAULT_SIZE)} scale(${ringScaleRef.current})`;
        } else if (state === 'text') {
          // Ring fades out completely; dot becomes a 2x18px caret.
          ring.style.opacity = '0';
          dot.style.opacity = '1';
          dot.style.width = '2px';
          dot.style.height = '18px';
          dot.style.borderRadius = '1px';
          dot.style.transform = center(mx, my, 2, 18);
        } else if (state === 'disabled') {
          resetRingShape();
          ring.style.borderColor = 'var(--cc-text-disabled)';
          ringPosRef.current.x += (mx - ringPosRef.current.x) * RING_LERP;
          ringPosRef.current.y += (my - ringPosRef.current.y) * RING_LERP;
          ring.style.transform = center(ringPosRef.current.x, ringPosRef.current.y, RING_DEFAULT_SIZE, RING_DEFAULT_SIZE);
          // 1px slash instead of the round dot.
          dot.style.opacity = '1';
          dot.style.width = '1px';
          dot.style.height = '14px';
          dot.style.borderRadius = '0';
          dot.style.transform = `${center(mx, my, 1, 14)} rotate(45deg)`;
        }
      }

      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);

    const onMove = (e) => {
      mouseRef.current.x = e.clientX;
      mouseRef.current.y = e.clientY;

      // Magnetic pull on whatever's currently hovered (button/nav/chip only).
      const el = hoveredMagneticElRef.current;
      if (el && stateRef.current === 'hover') {
        const r = el.getBoundingClientRect();
        const cx = r.left + r.width / 2;
        const cy = r.top + r.height / 2;
        const dx = Math.max(-MAGNETIC_MAX, Math.min(MAGNETIC_MAX, (e.clientX - cx) * MAGNETIC_STRENGTH));
        const dy = Math.max(-MAGNETIC_MAX, Math.min(MAGNETIC_MAX, (e.clientY - cy) * MAGNETIC_STRENGTH));
        el.style.transition = 'none';
        el.style.transform = `translate(${dx}px, ${dy}px)`;
      }
    };

    const clearMagnetic = (el) => {
      if (!el) return;
      el.style.transition = 'transform 220ms var(--ease-out)';
      el.style.transform = 'translate(0px, 0px)';
      const cleanup = () => { el.style.transition = ''; el.removeEventListener('transitionend', cleanup); };
      el.addEventListener('transitionend', cleanup);
    };

    const onOver = (e) => {
      const target = e.target;
      if (!(target instanceof Element)) return;

      const prevMagnetic = hoveredMagneticElRef.current;

      const disabled = target.closest(DISABLED_SELECTOR);
      const text = target.closest(TEXT_SELECTOR);
      const row = target.closest(ROW_SELECTOR);
      const interactive = target.closest(INTERACTIVE_SELECTOR);

      let nextState = 'default';
      let nextMagneticEl = null;

      if (disabled) {
        nextState = 'disabled';
      } else if (text) {
        nextState = 'text';
      } else if (interactive) {
        nextState = 'hover';
        nextMagneticEl = interactive;
      } else if (row) {
        nextState = 'row';
        nextMagneticEl = row; // reused as the "hovered rect" source for the row line
      }

      if (prevMagnetic && prevMagnetic !== nextMagneticEl && stateRef.current === 'hover') {
        clearMagnetic(prevMagnetic);
      }

      stateRef.current = nextState;
      hoveredMagneticElRef.current = nextMagneticEl;
    };

    const onDown = (e) => {
      pressedRef.current = true;

      // Primary-action ripple: fires exactly once, only on a real
      // .btn-primary click (see PRIMARY_ACTION_SELECTOR above).
      const target = e.target;
      if (target instanceof Element && target.closest(PRIMARY_ACTION_SELECTOR)) {
        spawnRipple(e.clientX, e.clientY);
      }
    };
    const onUp = () => { pressedRef.current = false; };

    window.addEventListener('mousemove', onMove, { passive: true });
    document.addEventListener('mouseover', onOver, true);
    window.addEventListener('mousedown', onDown, true);
    window.addEventListener('mouseup', onUp);

    return () => {
      document.documentElement.classList.remove('cc-custom-cursor-active');
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseover', onOver, true);
      window.removeEventListener('mousedown', onDown, true);
      window.removeEventListener('mouseup', onUp);
      if (hoveredMagneticElRef.current) clearMagnetic(hoveredMagneticElRef.current);
    };
  }, [active]);

  if (!active) return null;

  return (
    <>
      <div ref={dotRef} className="cc-cursor-dot" aria-hidden="true" />
      <div ref={ringRef} className="cc-cursor-ring" aria-hidden="true" />
      <div ref={crosshairHRef} className="cc-cursor-crosshair cc-cursor-crosshair-h" aria-hidden="true" />
      <div ref={crosshairVRef} className="cc-cursor-crosshair cc-cursor-crosshair-v" aria-hidden="true" />
    </>
  );
}

// One-shot ripple, created fresh per click and self-removed via the Web
// Animations API's onfinish — there is no loop and nothing left mounted
// after it plays, so it can never trigger continuously.
function spawnRipple(x, y) {
  const el = document.createElement('div');
  el.className = 'cc-cursor-ripple';
  el.style.left = `${x}px`;
  el.style.top = `${y}px`;
  document.body.appendChild(el);

  const scaleEnd = RIPPLE_END / RIPPLE_START;
  const anim = el.animate(
    [
      { transform: 'translate(-50%, -50%) scale(1)', opacity: 0.9 },
      { transform: `translate(-50%, -50%) scale(${scaleEnd})`, opacity: 0 }
    ],
    { duration: RIPPLE_DURATION, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' }
  );
  anim.onfinish = () => el.remove();
}
