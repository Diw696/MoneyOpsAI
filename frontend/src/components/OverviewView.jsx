import React, { useEffect, useRef, useState } from 'react';
import { animate } from 'framer-motion';
import { Info, AlertTriangle, RefreshCw, CheckCircle2, ChevronRight } from 'lucide-react';
import { Card, Metric, Button } from '../primitives';
import { usePrefersReducedMotion } from '../hooks/useMotionGuards';

// Derives the SeverityRail's confidence fill from real evidence already
// shown elsewhere on the card (the anomaly ratio vs. baseline, or a
// concentration percentage) — never a fabricated number, never presented as
// an API field. An incident with no evidence recorded yet gets 0%, same
// "explicit empty state, not a fake value" rule the rest of this component
// already follows.
function deriveConfidence(inc) {
  const ev = inc.evidence || {};
  if (ev.failure_rate_ratio != null) return Math.min(100, Math.round(ev.failure_rate_ratio * 33));
  if (ev.refund_rate_ratio != null) return Math.min(100, Math.round(ev.refund_rate_ratio * 33));
  if (ev.duplicate_refund_payments != null && ev.total_refunds) {
    return Math.min(100, Math.round((ev.duplicate_refund_payments / ev.total_refunds) * 100));
  }
  if (ev.webhook_failure_rate_pct != null) return Math.min(100, Math.round(ev.webhook_failure_rate_pct));
  return 0;
}

const SEVERITY_LABEL_COLOR = {
  critical: 'var(--sev-critical)',
  high: 'var(--sev-high)',
  medium: 'var(--sev-medium)',
  low: 'var(--sev-low)',
};

// Animates the hero exposure figure from its previous displayed value to
// the new one whenever real data changes (initial load included) — never a
// fabricated number, just an eased transition to the same real value this
// page already computes. Skipped entirely under prefers-reduced-motion,
// per the sitewide motion rule.
function useCountUp(target, prefersReducedMotion) {
  const [display, setDisplay] = useState(target);
  const prevTarget = useRef(target);

  useEffect(() => {
    if (prefersReducedMotion) {
      setDisplay(target);
      prevTarget.current = target;
      return undefined;
    }
    const controls = animate(prevTarget.current, target, {
      duration: 0.9,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => setDisplay(v),
    });
    prevTarget.current = target;
    return () => controls.stop();
  }, [target, prefersReducedMotion]);

  return display;
}

const relativeTime = (isoStr) => {
  if (!isoStr) return null;
  const diffMs = Date.now() - new Date(isoStr).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
};

export default function OverviewView({ stats, sourceStats, incidents, onSelectIncident, onTriggerDetection, isDetecting }) {
  const prefersReducedMotion = usePrefersReducedMotion();

  // Pending-investigation incidents surface first — a reviewer scanning this list
  // should see what still needs attention before what's already been handled,
  // rather than whatever was most recently re-confirmed by a detection re-run.
  // Active/Pending = genuinely unresolved work only. 'rejected' is a final
  // human decision, same as 'resolved' — it must leave this list immediately,
  // not linger just because no simulation ever executed for it.
  const activeIncidents = incidents
    .filter(inc => inc.status !== 'resolved' && inc.status !== 'rejected')
    .slice()
    .sort((a, b) => {
      const aPending = a.investigation_status !== 'investigated' ? 0 : 1;
      const bPending = b.investigation_status !== 'investigated' ? 0 : 1;
      if (aPending !== bPending) return aPending - bPending;
      return new Date(b.detected_at) - new Date(a.detected_at);
    });
  const resolvedIncidents = incidents
    .filter(inc => inc.status === 'resolved' || inc.status === 'rejected')
    .slice()
    .sort((a, b) => new Date(b.detected_at) - new Date(a.detected_at));
  const totalExposure = activeIncidents.reduce((sum, inc) => sum + (inc.potential_exposure || 0), 0);
  const totalFailed = activeIncidents.reduce((sum, inc) => sum + (inc.evidence?.failed_payments_count || inc.affected_payments || 0), 0);
  const detectionVolume = sourceStats?.detection_volume || null;

  const mostRecentDetectedAt = incidents.length > 0
    ? incidents.reduce((latest, inc) => new Date(inc.detected_at) > new Date(latest) ? inc.detected_at : latest, incidents[0].detected_at)
    : null;

  const animatedExposure = useCountUp(totalExposure, prefersReducedMotion);

  return (
    <div className="cc-page">

      {/* PAGE CONTEXT */}
      <div className="cc-page-header">
        <h1 className="text-page-title">Overview</h1>
        <p className="cc-page-desc">What's happening right now, across every connected banking node and merchant channel.</p>
      </div>

      {/* SYSTEM STATE — one quiet strip, not two stacked notices. Instrument
          chrome (what data this is, whether it's trustworthy), not a
          marketing alert. */}
      <div className="cc-system-strip">
        <Info size={13} strokeWidth={2} className="cc-icon" />
        <span>Live Razorpay Test Mode + Incident Lab simulation data.</span>
        {detectionVolume && !detectionVolume.razorpay_test_sufficient_for_detection && (
          <>
            <span className="cc-system-strip-sep">·</span>
            <AlertTriangle size={13} strokeWidth={2} className="cc-icon" style={{ color: 'var(--sev-medium)' }} />
            <span style={{ color: 'var(--sev-medium)' }}>
              {detectionVolume.razorpay_test_payment_count} real payment attempt{detectionVolume.razorpay_test_payment_count === 1 ? '' : 's'} — below the {detectionVolume.min_sample_size}+ threshold for reliable detection.
            </span>
          </>
        )}
        {mostRecentDetectedAt && (
          <>
            <span className="cc-system-strip-sep">·</span>
            <span>Last incident detected {relativeTime(mostRecentDetectedAt)}</span>
          </>
        )}
      </div>

      {/* HERO — one dominant number. Everything else on this page is
          context for this figure, not a peer to it. */}
      <div className="cc-hero">
        <p className="cc-hero-label">Potential exposure</p>
        <div className="cc-hero-value text-hero cc-numeric">
          ₹{animatedExposure.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </div>
        <div className="cc-hero-context">
          <span className="cc-hero-active" style={{ color: activeIncidents.length > 0 ? 'var(--sev-critical)' : 'var(--state-verified)' }}>
            {activeIncidents.length} active incident{activeIncidents.length === 1 ? '' : 's'}
          </span>
          <span className="cc-hero-quiet">
            {(stats?.payments || 0).toLocaleString('en-IN')} transactions logged · {activeIncidents.length > 0 ? totalFailed.toLocaleString('en-IN') : 0} failed payments flagged
          </span>
        </div>
      </div>

      {/* ACTIVE INCIDENTS — the centerpiece. Each entry is a case to enter,
          not a dashboard card with a repeated CTA: the whole row is the
          click target (Card's onClick), a chevron appears on hover as the
          only interaction affordance, and severity is carried by the rail
          plus a plain colored text label — never a bordered pill. */}
      <section>
        <div className="cc-section-header">
          <h2 className="text-card-title">Active</h2>
          <Button
            tier="secondary"
            onClick={onTriggerDetection}
            state={isDetecting ? 'loading' : 'idle'}
            loadingLabel="Scanning"
          >
            <RefreshCw size={13} strokeWidth={2} style={{ marginRight: 6 }} />
            Run anomaly scan
          </Button>
        </div>

        {activeIncidents.length === 0 ? (
          <div style={{ padding: '40px 0', color: 'var(--cc-text-tertiary)' }}>
            <CheckCircle2 size={20} strokeWidth={1.5} style={{ color: 'var(--state-verified)', marginBottom: 10 }} />
            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--cc-text-primary)' }}>No active incidents</div>
            <div style={{ fontSize: '13px', marginTop: '4px' }}>
              MoneyOps is not currently detecting abnormal payment behavior across any banking node or merchant channel.
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {activeIncidents.map((inc) => {
              const ev = inc.evidence || {};
              const exposureStr = `₹${(inc.potential_exposure || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
              const severity = inc.severity || 'critical';

              // Each anomaly family carries a genuinely different evidence shape
              // (a duplicate-refund incident has no "failure rate" at all — it
              // never had one to report, not a rate of 0%). Determine which
              // shape this incident's evidence actually is and render only the
              // metrics that are real for it, falling back to an explicit
              // empty-state rather than a fabricated 0.00% for anything absent.
              let cardMetrics;
              if (ev.duplicate_refund_payments != null) {
                const dup = ev.duplicate_refund_payments;
                const totalRefunds = ev.total_refunds ?? null;
                const concentrationPct = totalRefunds ? ((dup / totalRefunds) * 100).toFixed(2) : null;
                cardMetrics = [
                  { label: 'Duplicate refunds', value: totalRefunds != null ? `${dup} / ${totalRefunds}` : String(dup) },
                  { label: 'Concentration', value: concentrationPct != null ? `${concentrationPct}%` : '—', empty: concentrationPct == null },
                  { label: 'Refund / event count', value: totalRefunds != null ? totalRefunds : '—', empty: totalRefunds == null },
                  { label: 'Potential exposure', value: exposureStr }
                ];
              } else if (ev.failure_rate_pct != null) {
                cardMetrics = [
                  { label: 'Failure rate', value: `${ev.failure_rate_pct}%`, sub: `${ev.failure_rate_ratio ?? '1.0'}x baseline` },
                  { label: 'Peer baseline', value: `${ev.peer_failure_rate_pct ?? 0}%` },
                  { label: 'Affected payments', value: ev.failed_payments_count ?? inc.affected_payments ?? '—' },
                  { label: 'Potential exposure', value: exposureStr }
                ];
              } else if (ev.actual_refund_rate_pct != null) {
                cardMetrics = [
                  { label: 'Refund rate', value: `${ev.actual_refund_rate_pct}%`, sub: `${ev.refund_rate_ratio ?? '1.0'}x baseline` },
                  { label: "Merchant's baseline", value: `${ev.baseline_refund_rate_pct ?? 0}%` },
                  { label: 'Refunds / events', value: ev.total_refunds ?? '—' },
                  { label: 'Potential exposure', value: exposureStr }
                ];
              } else if (ev.webhook_failure_rate_pct != null) {
                cardMetrics = [
                  { label: 'Webhook failure rate', value: `${ev.webhook_failure_rate_pct}%` },
                  { label: 'Peer baseline', value: `${ev.peer_failure_rate_pct ?? 0}%` },
                  { label: 'Failed deliveries', value: ev.webhook_failed ?? '—' },
                  { label: 'Potential exposure', value: exposureStr }
                ];
              } else {
                cardMetrics = [
                  { label: 'Primary metric', value: '—', empty: true },
                  { label: 'Baseline', value: '—', empty: true },
                  { label: 'Affected payments', value: inc.affected_payments ?? '—' },
                  { label: 'Potential exposure', value: exposureStr }
                ];
              }

              return (
                <Card
                  key={inc.incident_id}
                  severity={severity}
                  confidence={deriveConfidence(inc)}
                  onClick={() => onSelectIncident(inc)}
                  title="Open this incident's investigation"
                >
                  <div className="cc-incident-head">
                    <div style={{ minWidth: 0 }}>
                      <div className="cc-incident-eyebrow">
                        <span style={{ color: SEVERITY_LABEL_COLOR[severity] || SEVERITY_LABEL_COLOR.critical, fontWeight: 700 }}>
                          {severity.toUpperCase()}
                        </span>
                        <span className="cc-system-strip-sep">·</span>
                        <span className="text-data">{inc.incident_id}</span>
                        <span className="cc-system-strip-sep">·</span>
                        <span className="text-data">{relativeTime(inc.detected_at)}</span>
                        {inc.investigation_status === 'investigated' && (
                          <>
                            <span className="cc-system-strip-sep">·</span>
                            <span className="text-data" style={{ color: 'var(--state-verified)' }}>Investigated</span>
                          </>
                        )}
                      </div>
                      <h3 className="text-card-title" style={{ margin: '4px 0 0' }}>{inc.title}</h3>
                    </div>
                    <ChevronRight size={18} strokeWidth={2} className="cc-incident-chevron" />
                  </div>

                  <div className="cc-incident-metrics">
                    {cardMetrics.map((m, mi) => (
                      <Metric
                        key={mi}
                        size={mi === 0 ? 'md' : 'sm'}
                        className={mi === 0 ? '' : 'cc-metric-secondary'}
                        label={m.label}
                        value={m.value}
                        tone={m.empty ? undefined : (mi === 0 ? 'critical' : undefined)}
                        sub={m.sub ? m.sub : (m.empty ? 'No evidence recorded' : undefined)}
                      />
                    ))}
                  </div>

                  {inc.primary_signal && (
                    <p className="cc-incident-signal">{inc.primary_signal}</p>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </section>

      {/* HISTORY — quiet case memory, not a second incident section. */}
      {resolvedIncidents.length > 0 && (
        <section>
          <p className="cc-section-eyebrow" style={{ marginBottom: '10px' }}>
            Case memory — {resolvedIncidents.length} resolved historically
          </p>
          <div className="cc-row-list">
            {resolvedIncidents.map((inc) => {
              const isRejected = inc.status === 'rejected';
              return (
                <div key={inc.incident_id} className="cc-row cc-row-quiet">
                  <div className="cc-row-main">
                    <span style={{ color: isRejected ? 'var(--cc-text-disabled)' : 'var(--state-verified)', fontSize: '11px', fontWeight: 600, flexShrink: 0 }}>
                      {isRejected ? 'Rejected' : 'Resolved'}
                    </span>
                    <span className="cc-row-title" style={{ color: 'var(--cc-text-secondary)' }}>{inc.title}</span>
                  </div>
                  <span className="cc-row-meta">{inc.incident_id}</span>
                </div>
              );
            })}
          </div>
        </section>
      )}

    </div>
  );
}
