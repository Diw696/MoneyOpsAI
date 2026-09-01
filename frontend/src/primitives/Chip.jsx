import React from 'react';

// Chip — compact, information-dense, restrained. Deliberately NOT the
// "generic rounded colorful badge" pattern already overused elsewhere in
// this app (full-saturation filled pill backgrounds) — a Chip here is a
// thin-bordered, small-radius, text-forward label. A `tone` only changes a
// 2px left accent bar and the text color, never the whole fill — so a
// screen full of chips stays quiet even when several tones are present at
// once.
const TONE_VAR = {
  neutral: null,
  accent: '--cc-accent',
  critical: '--sev-critical',
  high: '--sev-high',
  medium: '--sev-medium',
  low: '--sev-low',
  verified: '--state-verified',
};

export default function Chip({ children, tone = 'neutral', interactive = false, onClick, className = '' }) {
  const toneVar = TONE_VAR[tone];
  const style = toneVar ? { '--chip-accent': `var(${toneVar})` } : undefined;

  const inner = (
    <>
      {toneVar && <span className="cc-chip-accent" aria-hidden="true" />}
      <span className="cc-chip-label">{children}</span>
    </>
  );

  if (interactive) {
    return (
      <button
        type="button"
        className={`cc-chip cc-chip-interactive ${className}`}
        style={style}
        onClick={onClick}
        data-cursor="hover"
      >
        {inner}
      </button>
    );
  }

  return (
    <span className={`cc-chip ${className}`} style={style}>
      {inner}
    </span>
  );
}
