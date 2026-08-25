import React from 'react';
import { TrendingUp, AlertOctagon, Zap, DollarSign, ShieldAlert, CheckCircle2 } from 'lucide-react';

export function formatINR(val) {
  if (val === null || val === undefined) return "₹0";
  if (val >= 10000000) return `₹${(val / 10000000).toFixed(2)}Cr`;
  if (val >= 100000) return `₹${(val / 100000).toFixed(2)}L`;
  return `₹${Number(val).toLocaleString('en-IN')}`;
}

export default function OperationsKPIs({ stats }) {
  if (!stats) return null;

  const kpis = [
    {
      label: "Canonical Events",
      value: stats.events_processed !== undefined ? stats.events_processed.toLocaleString('en-IN') : "0",
      change: stats.stream_status === "streaming" ? "Live Stream Ingesting" : "Pipeline Ready",
      icon: TrendingUp,
      color: "#38bdf8",
      bgGlow: "rgba(56, 189, 248, 0.15)"
    },
    {
      label: "Active Incidents",
      value: stats.active_incidents || 0,
      change: stats.active_incidents > 0 ? "Requires FinOps Investigation" : "All Nominal",
      icon: AlertOctagon,
      color: stats.active_incidents > 0 ? "#ef4444" : "#10b981",
      bgGlow: stats.active_incidents > 0 ? "rgba(239, 68, 68, 0.15)" : "rgba(16, 185, 129, 0.15)"
    },
    {
      label: "Anomalies Evaluated",
      value: stats.anomalies_detected || 0,
      change: "Isolation Forest Model",
      icon: Zap,
      color: "#f59e0b",
      bgGlow: "rgba(245, 158, 11, 0.15)"
    },
    {
      label: "Potential Exposure",
      value: formatINR(stats.potential_exposure),
      change: "At Risk (Open Incidents)",
      icon: DollarSign,
      color: "#f87171",
      bgGlow: "rgba(248, 113, 113, 0.15)"
    },
    {
      label: "Recoverable Exposure",
      value: formatINR(stats.recoverable_exposure),
      change: "Governed Action Target",
      icon: ShieldAlert,
      color: "#34d399",
      bgGlow: "rgba(52, 211, 153, 0.15)"
    },
    {
      label: "Audited Actions",
      value: stats.audited_actions_count || 0,
      change: "Immutable Ledger Logged",
      icon: CheckCircle2,
      color: "#a855f7",
      bgGlow: "rgba(168, 85, 247, 0.15)"
    }
  ];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
      {kpis.map((kpi, idx) => {
        const Icon = kpi.icon;
        return (
          <div key={idx} className="glass-panel" style={{ padding: '16px 20px', position: 'relative', overflow: 'hidden' }}>
            <div style={{
              position: 'absolute',
              top: '-15px',
              right: '-15px',
              width: '60px',
              height: '60px',
              borderRadius: '50%',
              background: kpi.bgGlow,
              filter: 'blur(20px)',
              pointerEvents: 'none'
            }} />
            
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                {kpi.label}
              </span>
              <div style={{
                width: '28px',
                height: '28px',
                borderRadius: '6px',
                background: kpi.bgGlow,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <Icon size={16} color={kpi.color} />
              </div>
            </div>

            <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '4px', letterSpacing: '-0.02em' }}>
              {kpi.value}
            </div>

            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 500 }}>
              {kpi.change}
            </div>
          </div>
        );
      })}
    </div>
  );
}
