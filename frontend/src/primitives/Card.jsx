import React from 'react';
import SeverityRail from './SeverityRail';

// Card — a restrained surface (ink-base, hairline border, r-md radius) that
// optionally carries a SeverityRail down its left edge. Interactive only
// when `onClick` is passed (renders as a real <button> for keyboard access
// and an explicit cursor affordance); otherwise a plain, non-interactive
// container (correct: not every card is a click target, and a fake
// pointer cursor on a static card would be exactly the kind of decorative
// misdirection this system is trying to avoid).
export default function Card({
  children,
  severity,
  confidence,
  approved,
  onClick,
  className = '',
  ...rest
}) {
  const hasRail = severity != null;
  const content = (
    <>
      {hasRail && (
        <SeverityRail severity={severity} confidence={confidence} approved={approved} />
      )}
      <div className="cc-card-body">{children}</div>
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        className={`cc-card cc-card-interactive ${className}`}
        onClick={onClick}
        data-cursor="hover"
        {...rest}
      >
        {content}
      </button>
    );
  }

  return (
    <div className={`cc-card ${className}`} {...rest}>
      {content}
    </div>
  );
}
