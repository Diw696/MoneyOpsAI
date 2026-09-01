import React, { createContext, useCallback, useContext, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { usePrefersReducedMotion } from '../hooks/useMotionGuards';

// Toast — minimal, non-intrusive. A single line (icon + message), thin
// left accent bar for success/error/info, auto-dismissing, stacked
// top-right. Deliberately capped in size via CSS (max-width, single-line
// clamp) so it can never grow into an oversized floating notification
// card — that's a hard ceiling, not a style suggestion a consumer can
// override by passing a long message.
const ToastContext = createContext(null);

const TONE_ICON = {
  success: '✓',
  error: '✕',
  info: 'i',
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const idRef = useRef(0);
  const prefersReducedMotion = usePrefersReducedMotion();

  const dismiss = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const push = useCallback((message, tone = 'info', duration = 3200) => {
    const id = ++idRef.current;
    setToasts(prev => [...prev, { id, message, tone }]);
    if (duration > 0) {
      setTimeout(() => dismiss(id), duration);
    }
    return id;
  }, [dismiss]);

  return (
    <ToastContext.Provider value={{ push, dismiss }}>
      {children}
      <div className="cc-toast-stack" aria-live="polite" aria-atomic="false">
        <AnimatePresence>
          {toasts.map(t => (
            <motion.div
              key={t.id}
              layout
              initial={prefersReducedMotion ? false : { opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              exit={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, x: 16 }}
              transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
              className={`cc-toast cc-toast-${t.tone}`}
              role="status"
            >
              <span className="cc-toast-icon" aria-hidden="true">{TONE_ICON[t.tone] || TONE_ICON.info}</span>
              <span className="cc-toast-message">{t.message}</span>
              <button
                type="button"
                className="cc-toast-dismiss"
                aria-label="Dismiss notification"
                onClick={() => dismiss(t.id)}
                data-cursor="hover"
              >
                ✕
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within a ToastProvider');
  return ctx;
}
