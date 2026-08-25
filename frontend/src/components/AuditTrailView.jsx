import React, { useState } from 'react';
import { FileText, ShieldCheck, CheckCircle2, XCircle, Search, Layers, Clock } from 'lucide-react';
import { formatINR } from './OperationsKPIs';

export default function AuditTrailView({ auditLogs }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedAudit, setSelectedAudit] = useState(null);

  const filtered = (auditLogs || []).filter(log => {
    const term = searchTerm.toLowerCase();
    return log.audit_id.toLowerCase().includes(term) ||
           log.incident_id.toLowerCase().includes(term) ||
           log.action_name.toLowerCase().includes(term) ||
           log.actor.toLowerCase().includes(term);
  });

  return (
    <div className="glass-panel animate-fade-in" style={{ padding: '24px' }}>
      
      {/* View Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <FileText size={20} color="#38bdf8" />
            <h1 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-primary)' }}>
              Governed Incident Audit Trail
            </h1>
          </div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Tamper-evident forensic record of all AI investigations, human approvals, policy checks, and simulated execution logs.
          </p>
        </div>

        {/* Search */}
        <div style={{ position: 'relative' }}>
          <Search size={14} color="var(--text-muted)" style={{ position: 'absolute', left: '10px', top: '10px' }} />
          <input
            type="text"
            placeholder="Search audit ID, actor, incident..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              background: 'rgba(15, 20, 31, 0.8)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '8px',
              padding: '6px 12px 6px 30px',
              fontSize: '0.8rem',
              color: 'var(--text-primary)',
              outline: 'none',
              width: '260px'
            }}
          />
        </div>
      </div>

      {/* Audit Log Table */}
      {filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)' }}>
          <ShieldCheck size={36} style={{ marginBottom: '12px', opacity: 0.5 }} />
          <p>No audit log entries recorded yet. Investigate and approve an incident to generate forensic records.</p>
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                <th style={{ padding: '12px 14px' }}>AUDIT ID</th>
                <th style={{ padding: '12px 14px' }}>INCIDENT</th>
                <th style={{ padding: '12px 14px' }}>TIMESTAMP (UTC)</th>
                <th style={{ padding: '12px 14px' }}>ACTION NAME</th>
                <th style={{ padding: '12px 14px' }}>ACTOR</th>
                <th style={{ padding: '12px 14px' }}>STATUS</th>
                <th style={{ padding: '12px 14px' }}>EXPOSURE</th>
                <th style={{ padding: '12px 14px' }}>DETAILS</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((log) => {
                const isApproved = log.approval_status === 'approved';
                return (
                  <tr
                    key={log.audit_id}
                    style={{
                      borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                      transition: 'background 0.2s ease'
                    }}
                  >
                    <td style={{ padding: '12px 14px' }}>
                      <span className="mono" style={{ fontWeight: 700, color: '#38bdf8' }}>{log.audit_id}</span>
                    </td>

                    <td style={{ padding: '12px 14px' }}>
                      <span className="mono" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{log.incident_id}</span>
                    </td>

                    <td style={{ padding: '12px 14px', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                      {new Date(log.timestamp).toLocaleTimeString()} {new Date(log.timestamp).toLocaleDateString()}
                    </td>

                    <td style={{ padding: '12px 14px' }}>
                      <span className="mono" style={{ fontSize: '0.75rem', color: '#f8fafc' }}>
                        {log.action_name}
                      </span>
                    </td>

                    <td style={{ padding: '12px 14px', color: 'var(--text-secondary)' }}>
                      {log.actor}
                    </td>

                    <td style={{ padding: '12px 14px' }}>
                      {isApproved ? (
                        <span className="badge badge-resolved" style={{ fontSize: '0.65rem' }}>
                          <CheckCircle2 size={11} /> Approved
                        </span>
                      ) : (
                        <span className="badge badge-critical" style={{ fontSize: '0.65rem' }}>
                          <XCircle size={11} /> Rejected
                        </span>
                      )}
                    </td>

                    <td style={{ padding: '12px 14px', fontWeight: 600, color: '#f87171' }}>
                      {formatINR(log.financial_exposure)}
                    </td>

                    <td style={{ padding: '12px 14px' }}>
                      <button
                        onClick={() => setSelectedAudit(selectedAudit?.audit_id === log.audit_id ? null : log)}
                        className="btn btn-ghost"
                        style={{ padding: '4px 10px', fontSize: '0.72rem' }}
                      >
                        {selectedAudit?.audit_id === log.audit_id ? "Hide" : "Inspect"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Selected Audit Log Forensic Drawer */}
      {selectedAudit && (
        <div className="animate-fade-in" style={{
          marginTop: '20px',
          padding: '16px 20px',
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-accent)',
          borderRadius: '10px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#38bdf8' }}>
              Audit Record: {selectedAudit.audit_id} ({selectedAudit.action_name})
            </span>
            <button onClick={() => setSelectedAudit(null)} className="btn btn-ghost" style={{ padding: '2px 8px', fontSize: '0.7rem' }}>
              Close
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', fontSize: '0.78rem' }}>
            <div>
              <div style={{ color: 'var(--text-muted)', marginBottom: '4px' }}>SIMULATED EXECUTION RESULT:</div>
              <div style={{ color: '#34d399', background: 'rgba(0,0,0,0.3)', padding: '8px 12px', borderRadius: '6px', lineHeight: 1.4 }}>
                {selectedAudit.simulated_action_result}
              </div>
            </div>

            <div>
              <div style={{ color: 'var(--text-muted)', marginBottom: '4px' }}>ROOT CAUSE IDENTIFIED:</div>
              <div style={{ color: 'var(--text-secondary)', background: 'rgba(0,0,0,0.3)', padding: '8px 12px', borderRadius: '6px', lineHeight: 1.4 }}>
                {selectedAudit.root_cause}
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
