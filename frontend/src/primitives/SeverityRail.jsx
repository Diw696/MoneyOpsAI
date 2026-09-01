import React from 'react';

const SEVERITY_VAR = {
  critical: '--sev-critical',
  high: '--sev-high',
  medium: '--sev-medium',
  low: '--sev-low',
};

// SeverityRail — the signature primitive. A vertical rail on a Card's edge
// that encodes two real, independent pieces of state as two real visual
// properties, and nothing decorative beyond that:
//
//   - hue      = severity (critical/high/medium/low) — never an arbitrary
//                color; always one of the four --sev-* tokens.
//   - fill     = confidence (0-100), the rail's actual filled height —
//                not a flat color block. An unconfident critical incident
//                and a fully-confident critical incident look different.
//
// Interaction: the rail widens subtly on hover (2px -> 3px, Phase 3.1) as a
// hint that there's a real value behind it, not a static decoration — it
// stays a thin forensic/status indicator, never a colored border.
//
// On approval (`approved=true`): the fill visibly transitions/drains to
// --state-verified over 500ms (Phase 3.1) — both the height and the color
// animate together, directionally, rather than snapping — severity stops
// mattering once a human has approved the incident, so the color itself
// changes to reflect that, rather than staying red/amber forever after
// the fact. See the dedicated 500ms transition on
// .cc-severity-rail-approved .cc-severity-rail-fill in index.css (distinct
// from the generic --dur-slow token, since this duration was spec'd
// explicitly at 500ms).
export default function SeverityRail({ severity = 'medium', confidence = 0, approved = false }) {
  const clampedConfidence = Math.max(0, Math.min(100, confidence));
  const hueVar = SEVERITY_VAR[severity] || SEVERITY_VAR.medium;

  return (
    <div
      className={`cc-severity-rail ${approved ? 'cc-severity-rail-approved' : ''}`}
      style={{ '--rail-hue': `var(${hueVar})` }}
      role="img"
      aria-label={
        approved
          ? 'Severity rail: approved, verified'
          : `Severity rail: ${severity} severity, ${clampedConfidence}% confidence`
      }
    >
      <div
        className="cc-severity-rail-fill"
        style={{ height: `${approved ? 100 : clampedConfidence}%` }}
      />
    </div>
  );
}
