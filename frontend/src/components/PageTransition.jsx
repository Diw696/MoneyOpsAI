import React from 'react';
import { motion } from 'framer-motion';
import { usePrefersReducedMotion } from '../hooks/useMotionGuards';

// A small, consistent fade+rise applied to whichever view is currently
// mounted. Deliberately NOT an AnimatePresence exit/enter crossfade: this
// app already fully unmounts the previous view via conditional rendering in
// App.jsx, so an exit animation would just delay the next view's first
// paint for no visual benefit — the instruction is explicit that this must
// never make the app feel slower. `key={routeKey}` re-triggers the enter
// animation on every tab switch even though `children` itself doesn't
// change identity in a way React would otherwise treat as a remount.
export default function PageTransition({ routeKey, children }) {
  const prefersReducedMotion = usePrefersReducedMotion();

  if (prefersReducedMotion) {
    return <>{children}</>;
  }

  return (
    <motion.div
      key={routeKey}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
