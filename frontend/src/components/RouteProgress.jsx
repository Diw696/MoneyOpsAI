import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { usePrefersReducedMotion } from '../hooks/useMotionGuards';

// A very subtle top-of-page bar that appears only while switching between
// the app's five views, then unmounts itself unconditionally on a timer —
// it can never get stuck on screen, even if `routeKey` changes again mid
// animation (each change just resets the same timer).
export default function RouteProgress({ routeKey }) {
  const [visible, setVisible] = useState(false);
  const timerRef = useRef(null);
  const isFirstRender = useRef(true);
  const prefersReducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    // Don't show it for the initial page load — only for actual route
    // changes after the app is already up.
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    if (prefersReducedMotion) return; // no motion at all when requested

    setVisible(true);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setVisible(false), 380);

    return () => clearTimeout(timerRef.current);
  }, [routeKey, prefersReducedMotion]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="route-progress"
          initial={{ scaleX: 0, opacity: 1 }}
          animate={{ scaleX: 1, opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ scaleX: { duration: 0.32, ease: [0.22, 1, 0.36, 1] }, opacity: { duration: 0.15 } }}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            height: '2px',
            transformOrigin: '0% 50%',
            background: 'var(--cc-accent)',
            zIndex: 300,
            pointerEvents: 'none'
          }}
        />
      )}
    </AnimatePresence>
  );
}
