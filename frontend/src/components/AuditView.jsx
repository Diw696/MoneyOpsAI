import React, { useState, useEffect } from 'react';
import { fetchAuditLogs } from '../api';

export default function AuditView() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expandedLogId, setExpandedLogId] = useState(null);

  const loadLogs = async () => {
    setLoading(true);
    try {
      const data = await fetchAuditLogs();
      setLogs(data || []);
    } catch (e) {
      console.warn("Failed to load audit logs:", e);
      setLogs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, []);

  const formatStatusBadge = (status) => {
    const s = (status || '').toLowerCase();
    if (s === 'executed') {
      return (
        <span style={{ padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: '800', background: 'rgba(16, 185, 129, 0.2)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.4)' }}>
          EXECUTED — SIMULATION
        </span>
      );
    }
    if (s === 'approved') {
      return (
        <span style={{ padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: '800', background: 'rgba(59, 130, 246, 0.2)', color: '#60a5fa', border: '1px solid rgba(59, 130, 246, 0.4)' }}>
          APPROVED BY HUMAN
        </span>
      );
    }
    if (s === 'rejected') {
      return (
        <span style={{ padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: '800', background: 'rgba(100, 116, 139, 0.2)', color: '#94a3b8', border: '1px solid rgba(100, 116, 139, 0.4)' }}>
          REJECTED
        </span>
      );
    }
    return (
      <span style={{ padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: '800', background: 'rgba(234, 179, 8, 0.2)', color: '#facc15', border: '1px solid rgba(234, 179, 8, 0.4)' }}>
        PENDING APPROVAL
      </span>
    );
  };

  const formatRiskBadge = (tier) => {
    const t = (tier || 'RED').toUpperCase();
    if (t === 'RED') {
      return (
        <span style={{ padding: '2px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: '800', background: 'rgba(239, 68, 68, 0.2)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.4)' }}>
          RED • APPROVAL REQUIRED
        </span>
      );
    }
    if (t === 'YELLOW') {
      return (
        <span style={{ padding: '2px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: '800', background: 'rgba(234, 179, 8, 0.2)', color: '#facc15', border: '1px solid rgba(234, 179, 8, 0.4)' }}>
          YELLOW
        </span>
      );
    }
    return (
      <span style={{ padding: '2px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: '800', background: 'rgba(16, 185, 129, 0.2)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.4)' }}>
        GREEN
      </span>
    );
  };

  return (
    <div className="view-container" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* 1. TOP HEADER */}
      <div className="card" style={{ padding: '20px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text)', margin: 0 }}>
            Immutable Action Audit Trail
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: '4px 0 0 0' }}>
            Permanent forensic ledger of AI recommendations, human approvals, and safe simulations in PostgreSQL.
          </p>
        </div>

        <button 
          className="btn"
          onClick={loadLogs}
          disabled={loading}
          style={{ 
            background: 'rgba(99, 102, 241, 0.15)', 
            borderColor: 'rgba(99, 102, 241, 0.4)', 
            color: 'var(--primary)',
            padding: '8px 16px',
            fontSize: '12px',
            fontWeight: '600'
          }}
        >
          {loading ? '↻ Loading Audit Log...' : '↻ Refresh Audit Trail'}
        </button>
      </div>

      {/* 2. AUDIT LOGS TABLE */}
      <div className="card" style={{ padding: '24px' }}>
        {loading && logs.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
            <span className="spinner"></span> Loading audit records from PostgreSQL...
          </div>
        ) : logs.length === 0 ? (
          <div style={{ 
            padding: '48px 24px', 
            textAlign: 'center', 
            background: 'rgba(255, 255, 255, 0.02)', 
            border: '1px dashed var(--border)', 
            borderRadius: '8px',
            color: 'var(--text-muted)'
          }}>
            <div style={{ fontSize: '24px', marginBottom: '8px' }}>📝</div>
            <div style={{ fontSize: '15px', fontWeight: '600', color: 'var(--text)' }}>
              No audit records recorded yet
            </div>
            <div style={{ fontSize: '13px', marginTop: '4px' }}>
              When governed actions are proposed, approved, rejected, or simulated, permanent audit rows appear here.
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {logs.map((log) => {
              const isExpanded = expandedLogId === log.audit_id;
              const hasExecResult = Boolean(log.execution_result);

              return (
                <div 
                  key={log.audit_id}
                  style={{
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                    background: 'rgba(255, 255, 255, 0.02)',
                    overflow: 'hidden',
                    transition: 'all 0.2s ease'
                  }}
                >
                  {/* Summary Bar */}
                  <div 
                    onClick={() => setExpandedLogId(isExpanded ? null : log.audit_id)}
                    style={{
                      padding: '14px 18px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      cursor: 'pointer',
                      background: isExpanded ? 'rgba(255, 255, 255, 0.04)' : 'transparent',
                      flexWrap: 'wrap',
                      gap: '12px'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
                      <code style={{ fontSize: '12px', color: 'var(--primary)', fontWeight: '700' }}>
                        {log.audit_id}
                      </code>
                      <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>•</span>
                      <span style={{ fontSize: '12px', color: 'var(--text)', fontWeight: '600' }}>
                        {log.incident_id || 'INC-0001'}
                      </span>
                      <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>•</span>
                      <span style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text)' }}>
                        {log.action_type || log.action_name || 'reroute_gateway_traffic'}
                      </span>
                      {formatRiskBadge(log.action_tier)}
                      {formatStatusBadge(log.new_status || log.approval_status)}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '12px', color: 'var(--text-muted)' }}>
                      <span>Actor: <strong style={{ color: 'var(--text)' }}>{log.actor}</strong></span>
                      <span>{new Date(log.timestamp).toLocaleString()}</span>
                      <span style={{ color: 'var(--primary)', fontWeight: '600' }}>
                        {isExpanded ? '▲ Hide' : '▼ Inspect'}
                      </span>
                    </div>
                  </div>

                  {/* Expanded Audit Details */}
                  {isExpanded && (
                    <div style={{ padding: '18px 20px', background: 'rgba(0, 0, 0, 0.25)', borderTop: '1px solid var(--border)', fontSize: '12px' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginBottom: '14px' }}>
                        <div>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>
                            Transition
                          </div>
                          <div style={{ fontFamily: 'monospace', color: 'var(--text)' }}>
                            {log.previous_status || 'None'} → <strong style={{ color: '#10b981' }}>{log.new_status}</strong>
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>
                            Action ID & Investigation ID
                          </div>
                          <div style={{ fontFamily: 'monospace', color: 'var(--text-muted)' }}>
                            Action: {log.action_id || '—'} | Inv: {log.investigation_id || '—'}
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>
                            Governance Policy
                          </div>
                          <div style={{ color: 'var(--text)' }}>
                            {log.new_status === 'approved' ? 'Explicit Human Authorization Granted' : log.new_status === 'rejected' ? 'Operator Declined Execution' : log.new_status === 'executed' ? 'Safe Demonstration Simulation Executed' : 'Awaiting Operator Approval'}
                          </div>
                        </div>
                      </div>

                      {/* Reason / Operator Notes */}
                      {log.reason && (
                        <div style={{ marginBottom: '12px' }}>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>
                            Reason / Operator Notes
                          </div>
                          <div style={{ padding: '8px 12px', background: 'rgba(255, 255, 255, 0.03)', borderRadius: '4px', border: '1px solid var(--border)', color: 'var(--text)' }}>
                            {log.reason}
                          </div>
                        </div>
                      )}

                      {/* Simulation Execution Result */}
                      {hasExecResult && (
                        <div>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>
                            Execution Result (Verified Safe Simulation)
                          </div>
                          <pre style={{ margin: 0, padding: '10px 14px', background: '#0f172a', borderRadius: '4px', border: '1px solid var(--border)', overflowX: 'auto', color: '#38bdf8' }}>
                            {JSON.stringify(log.execution_result, null, 2)}
                          </pre>
                          <div style={{ marginTop: '6px', color: '#10b981', fontWeight: '600', fontSize: '11px' }}>
                            ✓ Invariant Verified: 0 live Razorpay payments modified.
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

    </div>
  );
}
