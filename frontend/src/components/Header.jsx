import React from 'react';

export default function Header({ activeTab, onTabChange, stats, aiStatus, incidentsCount, onRefresh }) {
  const isGemini = aiStatus?.configured;
  const geminiModel = aiStatus?.model || 'gemini-3.5-flash-lite';

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
        
        {/* Left: Branding */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '34px',
            height: '34px',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #6366f1 0%, #4338ca 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 12px rgba(99, 102, 241, 0.4)',
            color: '#fff',
            fontWeight: '800',
            fontSize: '16px'
          }}>
            M
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.1rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#fff' }}>
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
                V2
              </span>
            </div>
            <p style={{ fontSize: '11px', color: 'var(--text-muted)', margin: 0, fontWeight: 500 }}>
              AI Payment Incident Investigator
            </p>
          </div>
        </div>

        {/* Middle: 3 Primary Navigation Tabs */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'rgba(0, 0, 0, 0.25)', padding: '4px', borderRadius: '8px', border: '1px solid var(--border)' }}>
          <button
            onClick={() => onTabChange('overview')}
            style={{
              padding: '7px 18px',
              borderRadius: '6px',
              border: 'none',
              background: activeTab === 'overview' ? 'var(--primary)' : 'transparent',
              color: activeTab === 'overview' ? '#fff' : 'var(--text-muted)',
              fontSize: '13px',
              fontWeight: '700',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s ease'
            }}
          >
            <span>📊</span>
            <span>Overview</span>
          </button>

          <button
            onClick={() => onTabChange('data')}
            style={{
              padding: '7px 18px',
              borderRadius: '6px',
              border: 'none',
              background: activeTab === 'data' ? 'var(--primary)' : 'transparent',
              color: activeTab === 'data' ? '#fff' : 'var(--text-muted)',
              fontSize: '13px',
              fontWeight: '700',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s ease'
            }}
          >
            <span>📦</span>
            <span>Data</span>
          </button>

          <button
            onClick={() => onTabChange('investigation')}
            style={{
              padding: '7px 18px',
              borderRadius: '6px',
              border: 'none',
              background: activeTab === 'investigation' ? 'var(--primary)' : 'transparent',
              color: activeTab === 'investigation' ? '#fff' : 'var(--text-muted)',
              fontSize: '13px',
              fontWeight: '700',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s ease'
            }}
          >
            <span>🔍</span>
            <span>Investigation</span>
            {incidentsCount > 0 && (
              <span style={{
                padding: '1px 6px',
                borderRadius: '10px',
                background: '#ef4444',
                color: '#fff',
                fontSize: '10px',
                fontWeight: '800'
              }}>
                {incidentsCount}
              </span>
            )}
          </button>
        </nav>

        {/* Right: Status Indicators & Refresh */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          
          {/* Razorpay Indicator */}
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
            <span>Razorpay: <strong>Test Mode</strong></span>
          </div>

          {/* PostgreSQL Indicator */}
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
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981' }}></span>
            <span>PostgreSQL: <strong>{stats?.payments ? `${stats.payments} txs` : 'Connected'}</strong></span>
          </div>

          {/* Gemini Indicator */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '5px 12px',
            borderRadius: '20px',
            background: isGemini ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
            border: `1px solid ${isGemini ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
            fontSize: '11px',
            fontWeight: '700',
            color: isGemini ? '#10b981' : '#f87171'
          }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: isGemini ? '#10b981' : '#f87171' }}></span>
            <span>AI: {isGemini ? `Gemini (${geminiModel})` : 'AI OFFLINE'}</span>
          </div>

          {/* Refresh Trigger */}
          <button 
            onClick={onRefresh}
            title="Refresh All Data"
            style={{
              padding: '6px 10px',
              borderRadius: '6px',
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid var(--border)',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: '12px'
            }}
          >
            ↻
          </button>

        </div>

      </div>
    </header>
  );
}
