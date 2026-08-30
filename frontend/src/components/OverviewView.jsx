import React from 'react';

export default function OverviewView({ stats, sourceStats, incidents, onSelectIncident, onTriggerDetection, isDetecting }) {
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
  const pendingCount = activeIncidents.filter(inc => inc.investigation_status !== 'investigated').length;

  const mostRecentDetectedAt = incidents.length > 0
    ? incidents.reduce((latest, inc) => new Date(inc.detected_at) > new Date(latest) ? inc.detected_at : latest, incidents[0].detected_at)
    : null;

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

  return (
    <div className="view-container" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* Operational pulse — real, derived-from-data signals only (no fabricated
          "last batch"/"last scan" timers not actually backed by fetched state). */}
      <div style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '14px' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }} title="Real = live Razorpay Test Mode API data. Incident Lab = labeled synthetic scenarios used for anomaly-detection evaluation. Never blended into one number.">
          <span style={{ opacity: 0.7 }}>ⓘ</span>
          <span>Combines live Razorpay Test Mode data and Incident Lab simulation data — see the Data tab for the per-source breakdown.</span>
        </span>
        {mostRecentDetectedAt && (
          <span>• Most recent incident detected <strong style={{ color: 'var(--text)' }}>{relativeTime(mostRecentDetectedAt)}</strong></span>
        )}
        <span>• <strong style={{ color: activeIncidents.length > 0 ? '#f87171' : 'var(--text)' }}>{activeIncidents.length}</strong> active</span>
        {pendingCount > 0 && <span>• <strong style={{ color: '#facc15' }}>{pendingCount}</strong> pending investigation</span>}
        {resolvedIncidents.length > 0 && <span>• <strong style={{ color: '#34d399' }}>{resolvedIncidents.length}</strong> resolved historically</span>}
      </div>

      {detectionVolume && !detectionVolume.razorpay_test_sufficient_for_detection && (
        <div style={{ fontSize: '12px', color: '#fbbf24', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ opacity: 0.8 }}>⚠</span>
          <span>Razorpay Test Mode: {detectionVolume.razorpay_test_payment_count} payment attempt{detectionVolume.razorpay_test_payment_count === 1 ? '' : 's'} — insufficient volume for reliable anomaly detection (needs {detectionVolume.min_sample_size}+). No incidents are raised from real data below that floor.</span>
        </div>
      )}

      {/* 1. TOP 4 CORE OPERATIONAL METRICS */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
        
        {/* Card 1: Transactions */}
        <div className="card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Transactions
          </div>
          <div style={{ fontSize: '28px', fontWeight: '800', color: 'var(--text)', marginTop: '8px' }}>
            {(stats?.payments || 0).toLocaleString('en-IN')}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Across connected datasets in PostgreSQL
          </div>
        </div>


        {/* Card 2: Failed Payments */}
        <div className="card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Failed Payments
          </div>
          <div style={{ fontSize: '28px', fontWeight: '800', color: activeIncidents.length > 0 ? '#f87171' : 'var(--text)', marginTop: '8px' }}>
            {activeIncidents.length > 0 ? totalFailed.toLocaleString('en-IN') : 0}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            {activeIncidents.length > 0 ? 'Anomalous failure volume' : 'Within normal operational baselines'}
          </div>
        </div>

        {/* Card 3: Active Incidents */}
        <div className="card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Active Incidents
          </div>
          <div style={{ fontSize: '28px', fontWeight: '800', color: activeIncidents.length > 0 ? '#f87171' : '#10b981', marginTop: '8px' }}>
            {activeIncidents.length}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            {activeIncidents.length > 0 ? 'Discovered by IsolationForest' : 'All systems operating normally'}
            {resolvedIncidents.length > 0 && ` · ${resolvedIncidents.length} resolved (historical)`}
          </div>
        </div>

        {/* Card 4: Potential Exposure */}
        <div className="card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Potential Exposure
          </div>
          <div style={{ fontSize: '28px', fontWeight: '800', color: totalExposure > 0 ? '#f87171' : 'var(--text)', marginTop: '8px' }}>
            ₹{totalExposure.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Unresolved transaction value
          </div>
        </div>

      </div>

      {/* 2. ACTIVE INCIDENTS SECTION */}
      <div className="card" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text)', margin: 0 }}>
              Active Incidents
            </h2>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: '4px 0 0 0' }}>
              Incidents discovered via dynamic feature extraction and IsolationForest anomaly detection.
            </p>
          </div>

          <button 
            className="btn"
            onClick={onTriggerDetection}
            disabled={isDetecting}
            style={{ 
              background: 'rgba(99, 102, 241, 0.15)', 
              borderColor: 'rgba(99, 102, 241, 0.4)', 
              color: 'var(--primary)',
              padding: '8px 16px',
              fontSize: '12px',
              fontWeight: '600'
            }}
          >
            {isDetecting ? '↻ Scanning PostgreSQL ML...' : '↻ Run Anomaly Scan'}
          </button>
        </div>

        {/* Incident List / Clean Empty State */}
        {activeIncidents.length === 0 ? (
          <div style={{ 
            padding: '48px 24px', 
            textAlign: 'center', 
            background: 'rgba(255, 255, 255, 0.02)', 
            border: '1px dashed var(--border)', 
            borderRadius: '8px',
            color: 'var(--text-muted)'
          }}>
            <div style={{ fontSize: '24px', marginBottom: '8px' }}>✓</div>
            <div style={{ fontSize: '15px', fontWeight: '600', color: 'var(--text)' }}>
              No active incidents
            </div>
            <div style={{ fontSize: '13px', marginTop: '4px' }}>
              MoneyOps is not currently detecting abnormal payment behavior across any banking node or merchant channel.
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {activeIncidents.map((inc) => {
              const ev = inc.evidence || {};
              const exposureStr = `₹${(inc.potential_exposure || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

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
                  { label: 'DUPLICATE REFUNDS', value: totalRefunds != null ? `${dup} / ${totalRefunds}` : String(dup) },
                  { label: 'CONCENTRATION', value: concentrationPct != null ? `${concentrationPct}%` : '—', empty: concentrationPct == null },
                  { label: 'REFUND / EVENT COUNT', value: totalRefunds != null ? totalRefunds : '—', empty: totalRefunds == null },
                  { label: 'POTENTIAL EXPOSURE', value: exposureStr }
                ];
              } else if (ev.failure_rate_pct != null) {
                cardMetrics = [
                  { label: 'FAILURE RATE', value: `${ev.failure_rate_pct}%`, sub: `${ev.failure_rate_ratio ?? '1.0'}x baseline` },
                  { label: 'PEER BASELINE', value: `${ev.peer_failure_rate_pct ?? 0}%` },
                  { label: 'AFFECTED PAYMENTS', value: ev.failed_payments_count ?? inc.affected_payments ?? '—' },
                  { label: 'POTENTIAL EXPOSURE', value: exposureStr }
                ];
              } else if (ev.actual_refund_rate_pct != null) {
                cardMetrics = [
                  { label: 'REFUND RATE', value: `${ev.actual_refund_rate_pct}%`, sub: `${ev.refund_rate_ratio ?? '1.0'}x baseline` },
                  { label: "MERCHANT'S BASELINE", value: `${ev.baseline_refund_rate_pct ?? 0}%` },
                  { label: 'REFUNDS / EVENTS', value: ev.total_refunds ?? '—' },
                  { label: 'POTENTIAL EXPOSURE', value: exposureStr }
                ];
              } else if (ev.webhook_failure_rate_pct != null) {
                cardMetrics = [
                  { label: 'WEBHOOK FAILURE RATE', value: `${ev.webhook_failure_rate_pct}%` },
                  { label: 'PEER BASELINE', value: `${ev.peer_failure_rate_pct ?? 0}%` },
                  { label: 'FAILED DELIVERIES', value: ev.webhook_failed ?? '—' },
                  { label: 'POTENTIAL EXPOSURE', value: exposureStr }
                ];
              } else {
                // No evidence recorded yet for this incident's anomaly type —
                // an explicit empty state, never a fabricated zero.
                cardMetrics = [
                  { label: 'PRIMARY METRIC', value: '—', empty: true },
                  { label: 'BASELINE', value: '—', empty: true },
                  { label: 'AFFECTED PAYMENTS', value: inc.affected_payments ?? '—' },
                  { label: 'POTENTIAL EXPOSURE', value: exposureStr }
                ];
              }

              const invPill = {
                not_investigated: { label: 'PENDING INVESTIGATION', color: '#94a3b8', bg: 'rgba(148, 163, 184, 0.12)' },
                investigating: { label: 'INVESTIGATING', color: '#60a5fa', bg: 'rgba(96, 165, 250, 0.12)' },
                investigated: { label: 'INVESTIGATED', color: '#34d399', bg: 'rgba(52, 211, 153, 0.12)' },
                investigation_failed: { label: 'INVESTIGATION FAILED', color: '#f87171', bg: 'rgba(248, 113, 113, 0.12)' }
              }[inc.investigation_status || 'not_investigated'];

              return (
                <div 
                  key={inc.incident_id}
                  style={{
                    padding: '20px 24px',
                    background: 'rgba(239, 68, 68, 0.02)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    borderRadius: '10px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '14px',
                    transition: 'all 0.2s ease'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                        <span className={`badge badge-${inc.severity || 'critical'}`} style={{ fontSize: '11px', fontWeight: '700' }}>
                          {inc.severity?.toUpperCase() || 'CRITICAL'}
                        </span>
                        <span style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '4px', background: invPill.bg, color: invPill.color, fontWeight: '700' }}>
                          {invPill.label}
                        </span>
                        <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                          {inc.incident_id}
                        </span>
                        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>•</span>
                        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                          Detected: {new Date(inc.detected_at).toLocaleString()}
                        </span>
                      </div>
                      <h3 style={{ fontSize: '17px', fontWeight: '700', color: 'var(--text)', margin: 0 }}>
                        {inc.title}
                      </h3>
                    </div>

                    <button
                      className="btn btn-primary"
                      onClick={() => onSelectIncident(inc)}
                      title="Opens the Investigation tab to review this incident. Does not itself run the Gemini investigation — that's a separate, deliberate action on that page."
                      style={{
                        padding: '10px 20px',
                        fontWeight: '700',
                        fontSize: '13px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px'
                      }}
                    >
                      🔍 Review
                    </button>
                  </div>

                  {/* Metrics Row */}
                  <div style={{ 
                    display: 'grid', 
                    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', 
                    gap: '12px', 
                    padding: '12px 16px', 
                    background: 'rgba(0, 0, 0, 0.2)', 
                    borderRadius: '6px',
                    border: '1px solid var(--border)'
                  }}>
                    {cardMetrics.map((m, mi) => (
                      <div key={mi}>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{m.label}</div>
                        <div style={{ fontSize: '16px', fontWeight: '700', color: m.empty ? 'var(--text-muted)' : (m.label === 'POTENTIAL EXPOSURE' || mi === 0 ? '#f87171' : 'var(--text)') }}>
                          {m.value}
                          {m.sub && <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 'normal' }}> ({m.sub})</span>}
                        </div>
                        {m.empty && <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>No evidence recorded</div>}
                      </div>
                    ))}
                  </div>

                  {/* Primary Signal */}
                  {inc.primary_signal && (
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: '1.4' }}>
                      <strong style={{ color: 'var(--text)' }}>Signal:</strong> {inc.primary_signal}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 3. RESOLVED / HISTORICAL INCIDENTS (case-memory precedent, not active) */}
      {resolvedIncidents.length > 0 && (
        <div className="card" style={{ padding: '24px' }}>
          <h2 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-muted)', margin: 0 }}>
            Resolved / Historical Incidents ({resolvedIncidents.length})
          </h2>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '4px 0 16px 0' }}>
            Previously handled incidents — executed simulations and human-rejected recommendations alike — kept as case-memory precedent for future investigations. Not counted as active.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {resolvedIncidents.map((inc) => {
              const isRejected = inc.status === 'rejected';
              return (
                <div
                  key={inc.incident_id}
                  style={{
                    padding: '12px 16px',
                    background: 'rgba(255, 255, 255, 0.02)',
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: '12px',
                    flexWrap: 'wrap'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span className="badge" style={{
                      fontSize: '10px', fontWeight: '700', padding: '2px 8px', borderRadius: '10px',
                      color: isRejected ? '#94a3b8' : '#10b981',
                      background: isRejected ? 'rgba(148, 163, 184, 0.12)' : 'rgba(16, 185, 129, 0.1)'
                    }}>
                      {isRejected ? 'REJECTED BY HUMAN' : 'RESOLVED'}
                    </span>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'monospace' }}>{inc.incident_id}</span>
                    <span style={{ fontSize: '13px', color: 'var(--text)' }}>{inc.title}</span>
                  </div>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{inc.source || 'incident_lab'}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

    </div>
  );
}
