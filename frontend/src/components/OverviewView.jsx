import React from 'react';

export default function OverviewView({ stats, incidents, onSelectIncident, onTriggerDetection, isDetecting }) {
  const activeIncidents = incidents.filter(inc => inc.status !== 'resolved');
  const resolvedIncidents = incidents.filter(inc => inc.status === 'resolved');
  const totalExposure = activeIncidents.reduce((sum, inc) => sum + (inc.potential_exposure || 0), 0);
  const totalFailed = activeIncidents.reduce((sum, inc) => sum + (inc.evidence?.failed_payments_count || inc.affected_payments || 0), 0);

  return (
    <div className="view-container" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* Data provenance subtitle — mirrors the Data page notice so this isn't hidden behind a tab click */}
      <div style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }} title="Real = live Razorpay Test Mode API data. Incident Lab = labeled synthetic scenarios used for anomaly-detection evaluation. Never blended into one number.">
        <span style={{ opacity: 0.7 }}>ⓘ</span>
        <span>Metrics below combine live Razorpay Test Mode data and labeled Incident Lab simulation data — see the Data tab for the per-source breakdown.</span>
      </div>

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
              const failureRate = inc.evidence?.failure_rate_pct ?? (inc.failure_rate ? (inc.failure_rate * 100).toFixed(2) : '0.00');
              const peerRate = inc.evidence?.peer_failure_rate_pct ?? (inc.peer_failure_rate ? (inc.peer_failure_rate * 100).toFixed(2) : '0.00');
              const ratio = inc.evidence?.failure_rate_ratio ?? (Number(peerRate) > 0 ? (Number(failureRate) / Number(peerRate)).toFixed(2) : '1.0');
              const failedCount = inc.evidence?.failed_payments_count ?? inc.affected_payments ?? 0;

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
                      style={{ 
                        padding: '10px 20px', 
                        fontWeight: '700', 
                        fontSize: '13px', 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: '8px' 
                      }}
                    >
                      ⚡ Investigate
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
                    <div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>FAILURE RATE</div>
                      <div style={{ fontSize: '16px', fontWeight: '700', color: '#f87171' }}>
                        {failureRate}% <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 'normal' }}>({ratio}x baseline)</span>
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>PEER BASELINE</div>
                      <div style={{ fontSize: '16px', fontWeight: '700', color: 'var(--text)' }}>
                        {peerRate}%
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>AFFECTED PAYMENTS</div>
                      <div style={{ fontSize: '16px', fontWeight: '700', color: 'var(--text)' }}>
                        {failedCount} failures
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>POTENTIAL EXPOSURE</div>
                      <div style={{ fontSize: '16px', fontWeight: '700', color: '#f87171' }}>
                        ₹{(inc.potential_exposure || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </div>
                    </div>
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
            Closed incidents kept as case-memory precedent for similarity retrieval during live investigations. Not counted as active.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {resolvedIncidents.map((inc) => (
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
                  <span className="badge" style={{ fontSize: '10px', fontWeight: '700', color: '#10b981', background: 'rgba(16, 185, 129, 0.1)', padding: '2px 8px', borderRadius: '10px' }}>
                    RESOLVED
                  </span>
                  <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'monospace' }}>{inc.incident_id}</span>
                  <span style={{ fontSize: '13px', color: 'var(--text)' }}>{inc.title}</span>
                </div>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{inc.source || 'incident_lab'}</span>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}
