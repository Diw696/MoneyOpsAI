import React, { useState, useEffect } from 'react';
import { 
  fetchSourceStats, 
  syncRazorpay, 
  fetchPayments, 
  fetchOrders, 
  fetchRefunds, 
  fetchWebhooks 
} from '../api';

export default function DataView({ onRefreshAll }) {
  const [sourceStats, setSourceStats] = useState(null);
  const [activeTable, setActiveTable] = useState('payments'); // 'payments' | 'orders' | 'refunds' | 'webhooks'
  const [sourceFilter, setSourceFilter] = useState(''); // '' | 'razorpay_test' | 'incident_lab'
  const [tableData, setTableData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState(null);

  const loadProvenance = async () => {
    try {
      const data = await fetchSourceStats();
      setSourceStats(data);
    } catch (e) {
      console.warn("Could not load source distribution:", e);
    }
  };

  const loadTableData = async () => {
    setLoading(true);
    try {
      let records = [];
      const filter = sourceFilter || null;
      if (activeTable === 'payments') records = await fetchPayments(50, filter);
      else if (activeTable === 'orders') records = await fetchOrders(50, filter);
      else if (activeTable === 'refunds') records = await fetchRefunds(50, filter);
      else if (activeTable === 'webhooks') records = await fetchWebhooks(50);
      setTableData(records || []);
    } catch (e) {
      console.error("Table data load error:", e);
      setTableData([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProvenance();
  }, []);

  useEffect(() => {
    loadTableData();
  }, [activeTable, sourceFilter]);

  const handleSync = async () => {
    setSyncing(true);
    setSyncMsg(null);
    try {
      const res = await syncRazorpay();
      if (res.status === 'success') {
        setSyncMsg({
          type: 'success',
          text: `✓ Synchronized ${res.payments_fetched} payments, ${res.orders_fetched} orders, and ${res.refunds_fetched} refunds from Razorpay Test API. Database updated: ${res.payments_upserted} payments upserted.`
        });
      } else if (res.status === 'credentials_required') {
        setSyncMsg({
          type: 'warning',
          text: `⚠️ ${res.message}`
        });
      }
      await loadProvenance();
      await loadTableData();
      if (onRefreshAll) onRefreshAll();
    } catch (e) {
      setSyncMsg({
        type: 'error',
        text: `Razorpay sync failed: ${e.message}`
      });
    } finally {
      setSyncing(false);
    }
  };

  const realOrders = sourceStats?.orders?.razorpay_test || 0;
  const realPayments = sourceStats?.payments?.razorpay_test || 0;
  const realRefunds = sourceStats?.refunds?.razorpay_test || 0;
  const realWebhooks = sourceStats?.webhooks?.razorpay_webhook || 0;

  const labOrders = sourceStats?.orders?.incident_lab || 0;
  const labPayments = sourceStats?.payments?.incident_lab || 0;
  const labRefunds = sourceStats?.refunds?.incident_lab || 0;
  const labWebhooks = sourceStats?.webhooks?.incident_lab || 0;

  const formatSourceBadge = (src) => {
    if (src === 'razorpay_test') {
      return (
        <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '10px', fontWeight: '800', background: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa', border: '1px solid rgba(59, 130, 246, 0.3)' }}>
          RAZORPAY TEST
        </span>
      );
    }
    if (src === 'razorpay_webhook') {
      return (
        <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '10px', fontWeight: '800', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
          RAZORPAY WEBHOOK
        </span>
      );
    }
    return (
      <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '10px', fontWeight: '800', background: 'rgba(168, 85, 247, 0.15)', color: '#c084fc', border: '1px solid rgba(168, 85, 247, 0.3)' }}>
        INCIDENT LAB
      </span>
    );
  };

  return (
    <div className="view-container" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      
      {/* 1. TOP HEADER & SYNC CONTROLS */}
      <div className="card" style={{ padding: '20px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text)', margin: 0 }}>
            Data Sources & Provenance Ledger
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: '4px 0 0 0' }}>
            Inspect every financial record in PostgreSQL 18 with explicit provenance separation.
          </p>
        </div>

        <button 
          className="btn btn-primary"
          onClick={handleSync}
          disabled={syncing}
          style={{ padding: '10px 20px', fontWeight: '700', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}
        >
          {syncing ? '↻ Contacting Razorpay...' : '⚡ Sync Razorpay'}
        </button>
      </div>

      {syncMsg && (
        <div style={{
          padding: '12px 16px',
          borderRadius: '8px',
          fontSize: '13px',
          background: syncMsg.type === 'success' ? 'rgba(16, 185, 129, 0.1)' : syncMsg.type === 'warning' ? 'rgba(245, 158, 11, 0.1)' : 'rgba(239, 68, 68, 0.1)',
          border: `1px solid ${syncMsg.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : syncMsg.type === 'warning' ? 'rgba(245, 158, 11, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
          color: syncMsg.type === 'success' ? '#10b981' : syncMsg.type === 'warning' ? '#fbbf24' : '#f87171'
        }}>
          {syncMsg.text}
        </div>
      )}

      {/* 2. EXPLICIT PROVENANCE PURPOSE BANNER & SUMMARY */}
      <div style={{
        padding: '12px 18px',
        borderRadius: '8px',
        fontSize: '13px',
        background: 'rgba(99, 102, 241, 0.08)',
        border: '1px solid rgba(99, 102, 241, 0.25)',
        color: '#c7d2fe',
        display: 'flex',
        alignItems: 'center',
        gap: '10px'
      }}>
        <span style={{ fontSize: '16px' }}>ℹ️</span>
        <span>
          <strong>Data Provenance Notice:</strong> Simulation data is used to reproduce high-volume financial incidents that are difficult to generate safely in Razorpay Test Mode. All records maintain immutable source tags.
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        
        {/* Real Razorpay Box */}
        <div className="card" style={{ padding: '20px 24px', border: '1px solid rgba(59, 130, 246, 0.3)', background: 'rgba(59, 130, 246, 0.02)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ fontSize: '11px', fontWeight: '800', padding: '3px 8px', borderRadius: '4px', background: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa' }}>
              REAL DATA (RAZORPAY TEST MODE)
            </span>

            <code style={{ fontSize: '11px', color: 'var(--text-muted)' }}>source: razorpay_test / webhook</code>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', marginTop: '10px' }}>
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>ORDERS</div>
              <div style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text)' }}>{realOrders}</div>
            </div>
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>PAYMENTS</div>
              <div style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text)' }}>{realPayments}</div>
            </div>
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>REFUNDS</div>
              <div style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text)' }}>{realRefunds}</div>
            </div>
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>WEBHOOKS</div>
              <div style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text)' }}>{realWebhooks}</div>
            </div>
          </div>
        </div>

        {/* Incident Lab Simulation Box */}
        <div className="card" style={{ padding: '20px 24px', border: '1px solid rgba(168, 85, 247, 0.3)', background: 'rgba(168, 85, 247, 0.02)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ fontSize: '11px', fontWeight: '800', padding: '3px 8px', borderRadius: '4px', background: 'rgba(168, 85, 247, 0.15)', color: '#c084fc' }}>
              SIMULATION (INCIDENT LAB)
            </span>
            <code style={{ fontSize: '11px', color: 'var(--text-muted)' }}>source: incident_lab</code>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', marginTop: '10px' }}>
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>ORDERS</div>
              <div style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text)' }}>{labOrders}</div>
            </div>
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>PAYMENTS</div>
              <div style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text)' }}>{labPayments}</div>
            </div>
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>REFUNDS</div>
              <div style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text)' }}>{labRefunds}</div>
            </div>
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>WEBHOOKS</div>
              <div style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text)' }}>{labWebhooks}</div>
            </div>
          </div>
        </div>

      </div>

      {/* 3. CLEAN READABLE TABLES */}
      <div className="card" style={{ padding: '24px' }}>
        
        {/* Table Tab Selector & Filter */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            {['payments', 'orders', 'refunds', 'webhooks'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTable(tab)}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: activeTable === tab ? '1px solid var(--primary)' : '1px solid var(--border)',
                  background: activeTable === tab ? 'rgba(99, 102, 241, 0.15)' : 'rgba(255, 255, 255, 0.02)',
                  color: activeTable === tab ? 'var(--primary)' : 'var(--text-muted)',
                  fontSize: '13px',
                  fontWeight: '600',
                  cursor: 'pointer',
                  textTransform: 'capitalize'
                }}
              >
                {tab}
              </button>
            ))}
          </div>

          {activeTable !== 'webhooks' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Filter Source:</span>
              <select
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
                style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  background: 'var(--surface)',
                  border: '1px solid var(--border)',
                  color: 'var(--text)',
                  fontSize: '12px'
                }}
              >
                <option value="">All Sources</option>
                <option value="razorpay_test">Real (razorpay_test)</option>
                <option value="incident_lab">Simulation (incident_lab)</option>
              </select>
            </div>
          )}
        </div>

        {/* Table Rows */}
        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
            <span className="spinner"></span> Loading {activeTable} from PostgreSQL...
          </div>
        ) : tableData.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
            Zero {activeTable} records found for the selected filter.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', textAlign: 'left', color: 'var(--text-muted)' }}>
                  {activeTable === 'payments' && (
                    <>
                      <th style={{ padding: '10px 12px' }}>ID</th>
                      <th style={{ padding: '10px 12px' }}>ORDER</th>
                      <th style={{ padding: '10px 12px' }}>MERCHANT</th>
                      <th style={{ padding: '10px 12px' }}>AMOUNT</th>
                      <th style={{ padding: '10px 12px' }}>GATEWAY</th>
                      <th style={{ padding: '10px 12px' }}>STATUS</th>
                      <th style={{ padding: '10px 12px' }}>SOURCE</th>
                      <th style={{ padding: '10px 12px' }}>TIMESTAMP</th>
                    </>
                  )}
                  {activeTable === 'orders' && (
                    <>
                      <th style={{ padding: '10px 12px' }}>ID</th>
                      <th style={{ padding: '10px 12px' }}>MERCHANT</th>
                      <th style={{ padding: '10px 12px' }}>AMOUNT</th>
                      <th style={{ padding: '10px 12px' }}>STATUS</th>
                      <th style={{ padding: '10px 12px' }}>SOURCE</th>
                      <th style={{ padding: '10px 12px' }}>TIMESTAMP</th>
                    </>
                  )}
                  {activeTable === 'refunds' && (
                    <>
                      <th style={{ padding: '10px 12px' }}>ID</th>
                      <th style={{ padding: '10px 12px' }}>PAYMENT</th>
                      <th style={{ padding: '10px 12px' }}>MERCHANT</th>
                      <th style={{ padding: '10px 12px' }}>AMOUNT</th>
                      <th style={{ padding: '10px 12px' }}>STATUS</th>
                      <th style={{ padding: '10px 12px' }}>SOURCE</th>
                      <th style={{ padding: '10px 12px' }}>TIMESTAMP</th>
                    </>
                  )}
                  {activeTable === 'webhooks' && (
                    <>
                      <th style={{ padding: '10px 12px' }}>EVENT ID</th>
                      <th style={{ padding: '10px 12px' }}>EVENT TYPE</th>
                      <th style={{ padding: '10px 12px' }}>ENTITY</th>
                      <th style={{ padding: '10px 12px' }}>SIGNATURE</th>
                      <th style={{ padding: '10px 12px' }}>SOURCE</th>
                      <th style={{ padding: '10px 12px' }}>TIMESTAMP</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {tableData.map((row, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)', color: 'var(--text)' }}>
                    {activeTable === 'payments' && (
                      <>
                        <td style={{ padding: '10px 12px', fontFamily: 'monospace', color: 'var(--primary)' }}>{row.payment_id}</td>
                        <td style={{ padding: '10px 12px', fontFamily: 'monospace', color: 'var(--text-muted)' }}>{row.order_id}</td>
                        <td style={{ padding: '10px 12px' }}>{row.merchant_id}</td>
                        <td style={{ padding: '10px 12px', fontWeight: '600' }}>₹{Number(row.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                        <td style={{ padding: '10px 12px' }}>{row.gateway}</td>
                        <td style={{ padding: '10px 12px' }}>
                          <span style={{ 
                            padding: '2px 6px', 
                            borderRadius: '4px', 
                            fontSize: '11px', 
                            fontWeight: '600',
                            background: row.status === 'captured' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                            color: row.status === 'captured' ? '#10b981' : '#f87171'
                          }}>
                            {row.status}
                          </span>
                        </td>
                        <td style={{ padding: '10px 12px' }}>{formatSourceBadge(row.source)}</td>
                        <td style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>{new Date(row.created_at).toLocaleString()}</td>
                      </>
                    )}

                    {activeTable === 'orders' && (
                      <>
                        <td style={{ padding: '10px 12px', fontFamily: 'monospace', color: 'var(--primary)' }}>{row.order_id}</td>
                        <td style={{ padding: '10px 12px' }}>{row.merchant_id}</td>
                        <td style={{ padding: '10px 12px', fontWeight: '600' }}>₹{Number(row.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                        <td style={{ padding: '10px 12px' }}>
                          <span style={{ padding: '2px 6px', borderRadius: '4px', fontSize: '11px', fontWeight: '600', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
                            {row.status}
                          </span>
                        </td>
                        <td style={{ padding: '10px 12px' }}>{formatSourceBadge(row.source)}</td>
                        <td style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>{new Date(row.created_at).toLocaleString()}</td>
                      </>
                    )}

                    {activeTable === 'refunds' && (
                      <>
                        <td style={{ padding: '10px 12px', fontFamily: 'monospace', color: 'var(--primary)' }}>{row.refund_id}</td>
                        <td style={{ padding: '10px 12px', fontFamily: 'monospace', color: 'var(--text-muted)' }}>{row.payment_id}</td>
                        <td style={{ padding: '10px 12px' }}>{row.merchant_id}</td>
                        <td style={{ padding: '10px 12px', fontWeight: '600' }}>₹{Number(row.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                        <td style={{ padding: '10px 12px' }}>
                          <span style={{ padding: '2px 6px', borderRadius: '4px', fontSize: '11px', fontWeight: '600', background: 'rgba(234, 179, 8, 0.15)', color: '#facc15' }}>
                            {row.status}
                          </span>
                        </td>
                        <td style={{ padding: '10px 12px' }}>{formatSourceBadge(row.source)}</td>
                        <td style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>{new Date(row.created_at).toLocaleString()}</td>
                      </>
                    )}

                    {activeTable === 'webhooks' && (
                      <>
                        <td style={{ padding: '10px 12px', fontFamily: 'monospace', color: 'var(--primary)' }}>{row.event_id || row.external_event_id}</td>
                        <td style={{ padding: '10px 12px', fontWeight: '600' }}>{row.event_type}</td>
                        <td style={{ padding: '10px 12px', fontFamily: 'monospace', color: 'var(--text-muted)' }}>{row.entity_id || '—'}</td>
                        <td style={{ padding: '10px 12px' }}>
                          <span style={{ padding: '2px 6px', borderRadius: '4px', fontSize: '11px', fontWeight: '600', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
                            {row.signature_verified ? '✓ HMAC Verified' : 'Standard'}
                          </span>
                        </td>
                        <td style={{ padding: '10px 12px' }}>{formatSourceBadge(row.source || 'razorpay_webhook')}</td>
                        <td style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>{new Date(row.received_at).toLocaleString()}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </div>
  );
}
