import React from 'react';
import { AlertCircle, AlertTriangle, ArrowRight, ShieldCheck, CheckCircle2, Clock, Zap } from 'lucide-react';
import { formatINR } from './OperationsKPIs';

export default function IncidentQueue({ incidents, selectedIncidentId, onSelectIncident, isInvestigating }) {
  return (
    <div className="glass-panel" style={{ padding: '20px', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <AlertCircle size={18} color="#ef4444" />
          <h2 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            Active Financial Incidents
          </h2>
        </div>
        <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>
          {incidents.length} Detected
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: 'calc(100vh - 280px)', overflowY: 'auto', paddingRight: '4px' }}>
        {incidents.map((inc) => {
          const isSelected = inc.incident_id === selectedIncidentId;
          const isResolved = inc.status === 'resolved';
          
          let badgeClass = 'badge-medium';
          let borderGlow = 'var(--border-subtle)';
          if (inc.severity === 'critical') {
            badgeClass = 'badge-critical';
            borderGlow = isSelected ? '#ef4444' : 'rgba(239, 68, 68, 0.2)';
          } else if (inc.severity === 'high') {
            badgeClass = 'badge-high';
            borderGlow = isSelected ? '#f97316' : 'rgba(249, 115, 22, 0.2)';
          }

          if (isResolved) {
            badgeClass = 'badge-resolved';
          }

          return (
            <div
              key={inc.incident_id}
              onClick={() => onSelectIncident(inc.incident_id)}
              style={{
                background: isSelected ? 'var(--bg-surface)' : 'rgba(20, 27, 42, 0.6)',
                border: `1px solid ${isSelected ? borderGlow : 'var(--border-subtle)'}`,
                boxShadow: isSelected ? `0 0 16px ${inc.severity === 'critical' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(59, 130, 246, 0.15)'}` : 'none',
                borderRadius: '10px',
                padding: '14px 16px',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                position: 'relative'
              }}
            >
              {/* Header: ID + Badge + Status */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="mono" style={{ fontSize: '0.8rem', fontWeight: 700, color: '#38bdf8' }}>
                    {inc.incident_id}
                  </span>
                  <span className={`badge ${badgeClass}`}>
                    {inc.severity}
                  </span>
                </div>
                
                {isResolved ? (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.72rem', color: '#34d399', fontWeight: 600 }}>
                    <CheckCircle2 size={13} />
                    Resolved
                  </span>
                ) : (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.72rem', color: '#fbbf24', fontWeight: 500 }}>
                    <Clock size={12} />
                    Open
                  </span>
                )}
              </div>

              {/* Title */}
              <h3 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px', lineHeight: 1.3 }}>
                {inc.title}
              </h3>

              {/* Description preview */}
              <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '12px', lineHeight: 1.4 }}>
                {inc.description}
              </p>

              {/* Impact stats pill */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '8px', borderTop: '1px solid rgba(255, 255, 255, 0.05)' }}>
                <div style={{ display: 'flex', gap: '12px', fontSize: '0.75rem' }}>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Exposure: </span>
                    <span style={{ fontWeight: 700, color: '#f87171' }}>{formatINR(inc.potential_exposure)}</span>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Merchants: </span>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{inc.affected_merchants}</span>
                  </div>
                </div>

                <button
                  className={isSelected ? "btn btn-primary" : "btn btn-ghost"}
                  style={{ padding: '4px 10px', fontSize: '0.72rem', height: '26px' }}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectIncident(inc.incident_id);
                  }}
                >
                  Investigate
                  <ArrowRight size={13} />
                </button>
              </div>

            </div>
          );
        })}
      </div>
    </div>
  );
}
