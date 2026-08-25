import React from 'react';
import { ShieldCheck, Activity, Database, FileText, Cpu, RotateCcw, AlertTriangle } from 'lucide-react';

export default function Header({ activeTab, setActiveTab, onReset, isResetting, onOpenWebhookModal }) {
  return (
    <header style={{
      borderBottom: '1px solid var(--border-subtle)',
      background: 'rgba(15, 20, 31, 0.85)',
      backdropFilter: 'blur(16px)',
      position: 'sticky',
      top: 0,
      zIndex: 100
    }}>
      <div className="container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: '70px' }}>
        
        {/* Left: Branding & Tagline */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{
            width: '42px',
            height: '42px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 16px rgba(59, 130, 246, 0.4)'
          }}>
            <ShieldCheck size={24} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.25rem', fontWeight: 800, letterSpacing: '-0.02em', background: 'linear-gradient(to right, #ffffff, #93c5fd)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                MONEYOPS AI
              </span>
              <span className="badge badge-critical" style={{ fontSize: '0.65rem', padding: '2px 6px' }}>
                FinOps Intelligence
              </span>
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>
              When money doesn't add up, MoneyOps finds out why.
            </p>
          </div>
        </div>

        {/* Center: Navigation Tabs */}
        <nav style={{ display: 'flex', gap: '6px', background: 'rgba(0, 0, 0, 0.3)', padding: '4px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
          <button
            onClick={() => setActiveTab('operations')}
            className="btn btn-ghost"
            style={{
              padding: '6px 14px',
              fontSize: '0.8rem',
              background: activeTab === 'operations' ? 'var(--bg-card-hover)' : 'transparent',
              color: activeTab === 'operations' ? '#38bdf8' : 'var(--text-secondary)',
              borderColor: activeTab === 'operations' ? 'var(--border-accent)' : 'transparent'
            }}
          >
            <Activity size={15} />
            Operations Control
          </button>

          <button
            onClick={() => setActiveTab('merchants')}
            className="btn btn-ghost"
            style={{
              padding: '6px 14px',
              fontSize: '0.8rem',
              background: activeTab === 'merchants' ? 'var(--bg-card-hover)' : 'transparent',
              color: activeTab === 'merchants' ? '#38bdf8' : 'var(--text-secondary)',
              borderColor: activeTab === 'merchants' ? 'var(--border-accent)' : 'transparent'
            }}
          >
            <Database size={15} />
            Merchant Behavioral Memory
          </button>

          <button
            onClick={() => setActiveTab('audit')}
            className="btn btn-ghost"
            style={{
              padding: '6px 14px',
              fontSize: '0.8rem',
              background: activeTab === 'audit' ? 'var(--bg-card-hover)' : 'transparent',
              color: activeTab === 'audit' ? '#38bdf8' : 'var(--text-secondary)',
              borderColor: activeTab === 'audit' ? 'var(--border-accent)' : 'transparent'
            }}
          >
            <FileText size={15} />
            Audit Trail
          </button>

          <button
            onClick={() => setActiveTab('architecture')}
            className="btn btn-ghost"
            style={{
              padding: '6px 14px',
              fontSize: '0.8rem',
              background: activeTab === 'architecture' ? 'var(--bg-card-hover)' : 'transparent',
              color: activeTab === 'architecture' ? '#38bdf8' : 'var(--text-secondary)',
              borderColor: activeTab === 'architecture' ? 'var(--border-accent)' : 'transparent'
            }}
          >
            <Cpu size={15} />
            Architecture & Evaluation
          </button>
        </nav>

        {/* Right: Live Telemetry Status & Webhook Console & Reset */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={() => onOpenWebhookModal()}
            className="btn btn-ghost"
            style={{ padding: '6px 12px', fontSize: '0.75rem', borderColor: 'rgba(6, 182, 212, 0.4)', color: '#06b6d4' }}
            title="Open Razorpay Webhook Ingestion Console"
          >
            <Activity size={13} />
            Razorpay Webhooks
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 12px', background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.25)', borderRadius: '8px' }}>
            <div className="pulse-dot live" />
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#34d399' }}>
              Stream Ingesting
            </span>
          </div>

          <button
            onClick={onReset}
            disabled={isResetting}
            className="btn btn-ghost"
            style={{ padding: '6px 12px', fontSize: '0.75rem' }}
            title="Reset system to fresh demo state"
          >
            <RotateCcw size={14} className={isResetting ? "animate-spin" : ""} />
            {isResetting ? "Resetting..." : "Reset Demo"}
          </button>
        </div>

      </div>
    </header>
  );
}
