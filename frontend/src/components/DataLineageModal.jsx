import React from 'react';
import { X, Database, ArrowRight, ShieldCheck, Cpu, GitCommit, FileText, CheckCircle2, AlertTriangle, Layers } from 'lucide-react';

export default function DataLineageModal({ isOpen, onClose, incident, investigation }) {
  if (!isOpen || !incident) return null;

  const lineageStages = [
    {
      stage: "1. Data Origin",
      icon: Database,
      color: "#38bdf8",
      source: incident.source === "razorpay_test" ? "Razorpay Test Mode" : "MoneyOps Incident Laboratory (Synthetic)",
      details: `Origin: ${incident.source.toUpperCase()} | Target: ${incident.target_entity_id || incident.primary_gateway || 'gw_Gateway_X'}`
    },
    {
      stage: "2. Raw Ingestion Layer",
      icon: Layers,
      color: "#a855f7",
      source: "raw_external_events (SQLite)",
      details: "Raw JSON payload preserved with HMAC-SHA256 signature verification & deduplication"
    },
    {
      stage: "3. Canonical Normalization",
      icon: GitCommit,
      color: "#f59e0b",
      source: "canonical_events model",
      details: `Entity Type: ${incident.type} | Amount: ₹${incident.potential_exposure.toLocaleString('en-IN')}`
    },
    {
      stage: "4. ML Anomaly Detection",
      icon: Cpu,
      color: "#ef4444",
      source: "scikit-learn Isolation Forest",
      details: `Anomaly Score: ${(incident.anomaly_score * 100).toFixed(1)}% | 8 Features Extracted`
    },
    {
      stage: "5. Money Graph Traversal",
      icon: Layers,
      color: "#34d399",
      source: "NetworkX Directed Graph",
      details: `Scope: ${incident.affected_merchants} merchants, ${incident.affected_transactions} transactions across ${incident.primary_gateway || 'Gateway'}`
    },
    {
      stage: "6. Dense Case Memory",
      icon: FileText,
      color: "#ec4899",
      source: "SentenceTransformer (all-MiniLM-L6-v2)",
      details: "Dense neural semantic search via pure mathematical cosine similarity"
    },
    {
      stage: "7. AI Reasoning & Governance",
      icon: ShieldCheck,
      color: "#10b981",
      source: "Provider-Agnostic ReAct + 3-Tier Governor",
      details: `Governed Action: ${investigation?.action_name || 'pause_gateway_refund_retries'} (RED Tier: Human Authorization Enforced)`
    },
    {
      stage: "8. Immutable Audit Record",
      icon: CheckCircle2,
      color: "#6366f1",
      source: "audit_logs table",
      details: "Permanent cryptographic forensic log with unique Audit ID & operator metadata"
    }
  ];

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(5, 8, 15, 0.85)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '20px'
    }}>
      <div className="glass-panel" style={{
        width: '100%',
        maxWidth: '850px',
        maxHeight: '90vh',
        overflowY: 'auto',
        borderRadius: '16px',
        border: '1px solid var(--border-glow)',
        padding: '28px',
        position: 'relative'
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                End-to-End Data Lineage & Forensic Trace
              </span>
              <span className={`badge ${incident.source === 'razorpay_test' ? 'badge-info' : 'badge-warning'}`}>
                {incident.source === 'razorpay_test' ? 'RAZORPAY TEST MODE' : 'SYNTHETIC INCIDENT LAB'}
              </span>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              Incident: <strong style={{ color: '#ffffff' }}>{incident.incident_id}</strong> — {incident.title}
            </p>
          </div>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
            <X size={22} />
          </button>
        </div>

        {/* Lineage Timeline Flow */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {lineageStages.map((stage, idx) => {
            const Icon = stage.icon;
            return (
              <div key={idx} style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '16px',
                padding: '14px 18px',
                borderRadius: '10px',
                background: 'rgba(15, 23, 42, 0.6)',
                border: '1px solid rgba(255, 255, 255, 0.05)',
                position: 'relative'
              }}>
                <div style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '8px',
                  background: `${stage.color}20`,
                  border: `1px solid ${stage.color}40`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0
                }}>
                  <Icon size={18} color={stage.color} />
                </div>

                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {stage.stage}
                    </span>
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, color: stage.color, fontFamily: 'var(--font-mono)' }}>
                      {stage.source}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                    {stage.details}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div style={{ marginTop: '24px', textAlign: 'right' }}>
          <button className="btn btn-secondary" onClick={onClose} style={{ padding: '8px 20px' }}>
            Close Forensic Trace
          </button>
        </div>
      </div>
    </div>
  );
}
