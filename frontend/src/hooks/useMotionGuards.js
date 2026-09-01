import { useEffect, useState } from 'react';

// Shared, live-updating reads of the two media features the shell's motion
// features (route progress, page transitions, custom cursor) all need to
// respect. Live via matchMedia 'change' listeners rather than read-once, so
// e.g. toggling OS-level reduced-motion mid-session takes effect immediately.
export function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(mq.matches);
    mq.addEventListener('change', update);
    return () => mq.removeEventListener('change', update);
  }, []);
  return reduced;
}

export function useIsFinePointer() {
  const [fine, setFine] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(pointer: fine)').matches
  );
  useEffect(() => {
    const mq = window.matchMedia('(pointer: fine)');
    const update = () => setFine(mq.matches);
    mq.addEventListener('change', update);
    return () => mq.removeEventListener('change', update);
  }, []);
  return fine;
}
