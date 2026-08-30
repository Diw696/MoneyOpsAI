import React from 'react';

export default function Header({ activeTab, onTabChange, health, stats, aiStatus, pendingInvestigationCount, investigatedCount, onRefresh }) {
  const isRazorpayConfigured = Boolean(health?.razorpay_configured);
  const isPostgresHealthy = health?.status === 'healthy' || health?.database === 'PostgreSQL';
  const isGeminiConfigured = Boolean(health?.gemini_configured ?? aiStatus?.configured);
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
        
        {/* Left: Branding & Tagline */}
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
                MoneyOps AI
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
              Financial Incident Investigator
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
            title={`${pendingInvestigationCount} active/pending, ${investigatedCount} resolved or rejected (final counts, matching Overview and the Investigation workspace exactly)`}
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
            {pendingInvestigationCount > 0 && (
              <span style={{
                padding: '1px 6px',
                borderRadius: '10px',
                background: '#ef4444',
                color: '#fff',
                fontSize: '10px',
                fontWeight: '800'
              }}>
                {pendingInvestigationCount} pending
              </span>
            )}
            {investigatedCount > 0 && (
              <span style={{
                padding: '1px 6px',
                borderRadius: '10px',
                background: 'rgba(52, 211, 153, 0.2)',
                color: '#34d399',
                fontSize: '10px',
                fontWeight: '800'
              }}>
                {investigatedCount} done
              </span>
            )}
          </button>

          <button
            onClick={() => onTabChange('copilot')}
            style={{
              padding: '7px 18px',
              borderRadius: '6px',
              border: 'none',
              background: activeTab === 'copilot' ? 'var(--primary)' : 'transparent',
              color: activeTab === 'copilot' ? '#fff' : 'var(--text-muted)',
              fontSize: '13px',
              fontWeight: '700',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s ease'
            }}
          >
            <span>💬</span>
            <span>Financial Copilot</span>
          </button>

          <button
            onClick={() => onTabChange('audit')}
            style={{
              padding: '7px 18px',
              borderRadius: '6px',
              border: 'none',
              background: activeTab === 'audit' ? 'var(--primary)' : 'transparent',
              color: activeTab === 'audit' ? '#fff' : 'var(--text-muted)',
              fontSize: '13px',
              fontWeight: '700',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s ease'
            }}
          >
            <span>📝</span>
            <span>Audit Log</span>
          </button>
        </nav>



        {/* Right: Live Connection Indicators */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          
          {/* Live status: dot + plain text, no per-item colored box — three of these
              side by side previously competed for attention as three separate chips. */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--text-muted)' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: isRazorpayConfigured ? '#3b82f6' : '#f59e0b', flexShrink: 0 }}></span>
            <span>Razorpay: <strong style={{ color: isRazorpayConfigured ? 'var(--text)' : '#fbbf24' }}>{isRazorpayConfigured ? 'Test Mode' : 'Keys Needed'}</strong></span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--text-muted)' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: isPostgresHealthy ? '#10b981' : '#ef4444', flexShrink: 0 }}></span>
            <span>PostgreSQL: <strong style={{ color: 'var(--text)' }}>{stats?.payments ? `${stats.payments} txs` : (isPostgresHealthy ? 'Connected' : 'Offline')}</strong></span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--text-muted)' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: isGeminiConfigured ? '#10b981' : '#f87171', flexShrink: 0 }}></span>
            <span>Gemini: <strong style={{ color: 'var(--text)' }}>{isGeminiConfigured ? geminiModel : 'Offline'}</strong></span>
          </div>

          {/* Refresh Button */}
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
