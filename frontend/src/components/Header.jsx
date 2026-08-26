import React from 'react';

export default function Header({ stats, aiStatus, onRefresh }) {
  const isGemini = aiStatus?.configured;

  return (
    <header style={{
      borderBottom: '1px solid var(--border)',
      background: 'rgba(15, 23, 42, 0.95)',
      backdropFilter: 'blur(12px)',
      position: 'sticky',
      top: 0,
      zIndex: 100,
      padding: '0 24px'
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '64px',
        maxWidth: '1600px',
        margin: '0 auto'
      }}>
        
        {/* Left: Branding & Tagline */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #6366f1 0%, #4338ca 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 12px rgba(99, 102, 241, 0.4)',
            color: '#fff',
            fontWeight: '800',
            fontSize: '18px'
          }}>
            M
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.15rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#fff' }}>
                MONEYOPS AI
              </span>
              <span style={{ 
                fontSize: '10px', 
                padding: '2px 8px', 
                borderRadius: '12px', 
                background: 'rgba(99, 102, 241, 0.15)', 
                color: 'var(--primary)',
                fontWeight: '700'
              }}>
                V2 • Phase C
              </span>
            </div>
            <p style={{ fontSize: '11px', color: 'var(--text-muted)', margin: 0, fontWeight: 500 }}>
              Autonomous Financial Incident Investigator for Razorpay Payment Operations
            </p>
          </div>
        </div>

        {/* Right: Observability Badges & Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          {/* Database Badge */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '5px 10px',
            borderRadius: '6px',
            background: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid var(--border)',
            fontSize: '11px',
            color: 'var(--text-muted)'
          }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#3b82f6' }}></span>
            <span>PostgreSQL: <strong>{stats?.payments || 2501}</strong> payments</span>
          </div>

          {/* AI Connection Badge */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '5px 12px',
            borderRadius: '20px',
            background: isGemini ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
            border: `1px solid ${isGemini ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
            fontSize: '11px',
            fontWeight: '600',
            color: isGemini ? '#10b981' : '#f87171'
          }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: isGemini ? '#10b981' : '#f87171' }}></span>
            <span>AI: {isGemini ? `Gemini (${aiStatus.model || '2.0-flash'}) ● Connected` : 'AI OFFLINE (Missing Key)'}</span>
          </div>

          {/* Refresh Button */}
          <button 
            onClick={onRefresh}
            style={{
              background: 'none',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              padding: '5px 10px',
              color: 'var(--text-muted)',
              fontSize: '12px',
              cursor: 'pointer'
            }}
            title="Refresh state"
          >
            ↻
          </button>
        </div>

      </div>
    </header>
  );
}
