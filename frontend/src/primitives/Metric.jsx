import React from 'react';

// Metric — a financial/forensic number with a clear label -> value -> delta
// hierarchy. The value always renders in IBM Plex Mono with tabular-nums +
// the ss02/zero features (via .text-metric / .cc-numeric, already
// established in Phase 1), so a column of these never jitters and a zero
// is never mistaken for a letter O. The label is small, muted, uppercase —
// always identifies what the number IS before the number itself is read.
// The delta (optional) is the only place color carries meaning here: it's
// literally --state-verified (improvement) or --sev-critical (regression),
// never a decorative tint.
export default function Metric({ label, value, delta, deltaDirection, sub, size = 'md', tone, className = '' }) {
  const deltaTone = deltaDirection === 'up' ? 'var(--state-verified)' : deltaDirection === 'down' ? 'var(--sev-critical)' : 'var(--cc-text-tertiary)';
  const deltaArrow = deltaDirection === 'up' ? '↑' : deltaDirection === 'down' ? '↓' : '';
  const valueColor = tone === 'critical' ? 'var(--sev-critical)' : tone === 'verified' ? 'var(--state-verified)' : undefined;

  return (
    <div className={`cc-metric cc-metric-${size} ${className}`}>
      <div className="cc-metric-label">{label}</div>
      <div className="cc-metric-value-row">
        <span className="cc-metric-value text-metric cc-numeric" style={valueColor ? { color: valueColor } : undefined}>{value}</span>
        {delta != null && (
          <span className="cc-metric-delta" style={{ color: deltaTone }}>
            {deltaArrow} {delta}
          </span>
        )}
      </div>
      {sub && <div className="cc-metric-sub">{sub}</div>}
    </div>
  );
}
