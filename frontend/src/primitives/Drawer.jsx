import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { usePrefersReducedMotion } from '../hooks/useMotionGuards';

const FOCUSABLE_SELECTOR = 'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

// Drawer — slide-in panel + backdrop, with real keyboard/focus behavior:
//   - Escape closes it.
//   - Focus moves into the drawer on open (first focusable element, or the
//     panel itself as a fallback) and is trapped inside it (Tab/Shift+Tab
//     cycle within the drawer rather than escaping to the page behind the
//     backdrop) — a background page with a modal drawer open should not be
//     keyboard-reachable at all.
//   - Focus returns to whatever triggered the drawer when it closes.
// Reduced motion: the slide becomes an instant show/hide (still a backdrop
// fade, since a fade is not the kind of directional motion reduced-motion
// users are opting out of, but the panel itself does not slide).
export default function Drawer({ open, onClose, title, children, side = 'right' }) {
  const panelRef = useRef(null);
  const triggerRef = useRef(null);
  const prefersReducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    if (!open) return undefined;

    triggerRef.current = document.activeElement;

    const focusables = () => Array.from(panelRef.current?.querySelectorAll(FOCUSABLE_SELECTOR) || []);
    const first = focusables()[0];
    (first || panelRef.current)?.focus();

    const onKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key === 'Tab') {
        const items = focusables();
        if (items.length === 0) return;
        const firstEl = items[0];
        const lastEl = items[items.length - 1];
        if (e.shiftKey && document.activeElement === firstEl) {
          e.preventDefault();
          lastEl.focus();
        } else if (!e.shiftKey && document.activeElement === lastEl) {
          e.preventDefault();
          firstEl.focus();
        }
      }
    };

    document.addEventListener('keydown', onKeyDown, true);
    return () => {
      document.removeEventListener('keydown', onKeyDown, true);
      // Return focus to whatever opened the drawer.
      if (triggerRef.current instanceof HTMLElement) triggerRef.current.focus();
    };
  }, [open, onClose]);

  const slideFrom = side === 'right' ? 24 : -24;

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="cc-drawer-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.16 }}
            onClick={onClose}
            aria-hidden="true"
          />
          <motion.div
            ref={panelRef}
            className={`cc-drawer cc-drawer-${side}`}
            role="dialog"
            aria-modal="true"
            aria-label={title || 'Panel'}
            tabIndex={-1}
            initial={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, x: slideFrom }}
            animate={{ opacity: 1, x: 0 }}
            exit={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, x: slideFrom }}
            transition={{ duration: prefersReducedMotion ? 0.12 : 0.24, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="cc-drawer-header">
              {title && <h2 className="cc-drawer-title">{title}</h2>}
              <button
                type="button"
                className="cc-drawer-close"
                onClick={onClose}
                aria-label="Close panel"
                data-cursor="hover"
              >
                ✕
              </button>
            </div>
            <div className="cc-drawer-body">{children}</div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
