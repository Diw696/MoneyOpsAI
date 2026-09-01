import React from 'react';

// Skeleton — matches the geometry of the content it's standing in for,
// rather than a single generic gray rectangle. `variant="text"` renders a
// stack of lines with a realistic last-line width (text never fills its
// container evenly); `variant="block"` is a single box for a card, avatar,
// chart, etc. via explicit width/height. The shimmer is a single soft
// sweep (not a pulsing glow) and is pure CSS, so it obeys the sitewide
// prefers-reduced-motion rule already in index.css with zero extra code
// here — reduced motion leaves a static, still-legible placeholder shape.
export default function Skeleton({ variant = 'text', lines = 3, width, height, borderRadius, className = '' }) {
  if (variant === 'text') {
    return (
      <div className={`cc-skeleton-text-group ${className}`} aria-hidden="true">
        {Array.from({ length: lines }).map((_, i) => (
          <div
            key={i}
            className="cc-skeleton cc-skeleton-line"
            style={{ width: i === lines - 1 ? '62%' : '100%' }}
          />
        ))}
      </div>
    );
  }

  return (
    <div
      className={`cc-skeleton ${className}`}
      style={{ width: width || '100%', height: height || '80px', borderRadius: borderRadius || 'var(--r-md)' }}
      aria-hidden="true"
    />
  );
}
