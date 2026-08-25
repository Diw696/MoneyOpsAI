import React, { useState } from 'react';
import { Database, Search, AlertTriangle, CheckCircle2, TrendingUp, Filter } from 'lucide-react';
import { formatINR } from './OperationsKPIs';

export default function MerchantBaselinesView({ merchants }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [filterAnomalous, setFilterAnomalous] = useState(false);

  const filtered = (merchants || []).filter(m => {
    const matchesSearch = m.merchant_name.toLowerCase().includes(searchTerm.toLowerCase()) || m.merchant_id.toLowerCase().includes(searchTerm.toLowerCase());
    if (filterAnomalous) return matchesSearch && m.is_anomalous;
    return matchesSearch;
  });

  return (
    <div className="glass-panel animate-fade-in" style={{ padding: '24px' }}>
      
      {/* View Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <Database size={20} color="#38bdf8" />
            <h1 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-primary)' }}>
              Merchant Financial Behavioral Memory
            </h1>
          </div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Rolling behavioral profiles comparing individual baseline refund rates & retries against real-time operational deviations.
          </p>
        </div>

        {/* Search & Filter */}
        <div style={{ display: 'flex', gap: '10px' }}>
          <div style={{ position: 'relative' }}>
            <Search size={14} color="var(--text-muted)" style={{ position: 'absolute', left: '10px', top: '10px' }} />
            <input
              type="text"
              placeholder="Search merchant..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{
                background: 'rgba(15, 20, 31, 0.8)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '8px',
                padding: '6px 12px 6px 30px',
                fontSize: '0.8rem',
                color: 'var(--text-primary)',
                outline: 'none'
              }}
            />
          </div>

          <button
            onClick={() => setFilterAnomalous(!filterAnomalous)}
            className="btn btn-ghost"
            style={{
              padding: '6px 12px',
              fontSize: '0.8rem',
              background: filterAnomalous ? 'rgba(239, 68, 68, 0.15)' : 'transparent',
              color: filterAnomalous ? '#f87171' : 'var(--text-secondary)',
              borderColor: filterAnomalous ? 'rgba(239, 68, 68, 0.4)' : 'var(--border-subtle)'
            }}
          >
            <Filter size={14} />
            {filterAnomalous ? "Showing Anomalies Only" : "Filter Anomalies"}
          </button>
        </div>
      </div>

      {/* Merchants Table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', textAlign: 'left' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
              <th style={{ padding: '12px 14px' }}>MERCHANT</th>
              <th style={{ padding: '12px 14px' }}>CATEGORY</th>
              <th style={{ padding: '12px 14px' }}>BASELINE REFUND %</th>
              <th style={{ padding: '12px 14px' }}>CURRENT REFUND %</th>
              <th style={{ padding: '12px 14px' }}>PAYMENT SUCCESS</th>
              <th style={{ padding: '12px 14px' }}>AVG TICKET</th>
              <th style={{ padding: '12px 14px' }}>STATUS</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((m) => {
              const baseRef = (m.baseline_refund_rate * 100).toFixed(1);
              const curRef = (m.current_refund_rate * 100).toFixed(1);
              const isDeviating = m.is_anomalous;

              return (
                <tr
                  key={m.merchant_id}
                  style={{
                    borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                    background: isDeviating ? 'rgba(239, 68, 68, 0.04)' : 'transparent',
                    transition: 'background 0.2s ease'
                  }}
                >
                  <td style={{ padding: '12px 14px' }}>
                    <div style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{m.merchant_name}</div>
                    <div className="mono" style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{m.merchant_id}</div>
                  </td>

                  <td style={{ padding: '12px 14px', textTransform: 'capitalize', color: 'var(--text-secondary)' }}>
                    {m.category?.replace('_', ' ')}
                  </td>

                  <td style={{ padding: '12px 14px', fontWeight: 600, color: 'var(--text-secondary)' }}>
                    {baseRef}%
                  </td>

                  <td style={{ padding: '12px 14px' }}>
                    <span style={{ fontWeight: 700, color: isDeviating ? '#f87171' : 'var(--text-primary)' }}>
                      {curRef}%
                    </span>
                    {isDeviating && (
                      <span style={{ marginLeft: '6px', fontSize: '0.68rem', color: '#f87171', fontWeight: 600 }}>
                        (Deviating)
                      </span>
                    )}
                  </td>

                  <td style={{ padding: '12px 14px', color: '#34d399', fontWeight: 600 }}>
                    {(m.payment_success_rate * 100).toFixed(1)}%
                  </td>

                  <td style={{ padding: '12px 14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {formatINR(m.avg_payment_value)}
                  </td>

                  <td style={{ padding: '12px 14px' }}>
                    {isDeviating ? (
                      <span className="badge badge-critical" style={{ fontSize: '0.65rem' }}>
                        <AlertTriangle size={11} /> Deviation Flag
                      </span>
                    ) : (
                      <span className="badge badge-resolved" style={{ fontSize: '0.65rem' }}>
                        <CheckCircle2 size={11} /> Nominal
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

    </div>
  );
}
