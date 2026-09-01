import React, { useState, useEffect } from 'react';
import { Zap, Plus } from 'lucide-react';
import {
  fetchSourceStats,
  syncRazorpay,
  fetchPayments,
  fetchOrders,
  fetchRefunds,
  fetchWebhooks,
  generateLabData,
  fetchIncidentLabRuns,
  triggerAnomalyDetection
} from '../api';
import { Metric, Button, Chip, SegmentedControl } from '../primitives';

const TABLE_OPTIONS = [
  { value: 'payments', label: 'Payments' },
  { value: 'orders', label: 'Orders' },
  { value: 'refunds', label: 'Refunds' },
  { value: 'webhooks', label: 'Webhooks' },
];
const SOURCE_OPTIONS = [
  { value: '', label: 'All sources' },
  { value: 'razorpay_test', label: 'Real' },
  { value: 'incident_lab', label: 'Simulated' },
];

// Source identity is communicated once per row via plain text + a small dot,
// not a Chip on every cell — a Chip means "this has a useful categorical
// state," and source here is already established by which provenance panel
// above the table it belongs to. The one place a Chip earns its keep is
// STATUS, which genuinely varies row to row (captured/failed, etc.).
function sourceLabel(src) {
  if (src === 'razorpay_test') return 'Real';
  if (src === 'razorpay_webhook') return 'Webhook';
  return 'Simulated';
}

export default function DataView({ onRefreshAll }) {
  const [sourceStats, setSourceStats] = useState(null);
  const [activeTable, setActiveTable] = useState('payments');
  const [sourceFilter, setSourceFilter] = useState('');
  const [tableData, setTableData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState(null);
  const [labRuns, setLabRuns] = useState([]);
  const [generatingLab, setGeneratingLab] = useState(false);
  const [labMsg, setLabMsg] = useState(null);

  const loadProvenance = async () => {
    try {
      const data = await fetchSourceStats();
      setSourceStats(data);
    } catch (e) {
      console.warn("Could not load source distribution:", e);
    }
  };

  const loadLabRuns = async () => {
    try {
      const runs = await fetchIncidentLabRuns(5);
      setLabRuns(runs || []);
    } catch (e) {
      console.warn("Could not load Incident Lab run history:", e);
    }
  };

  const handleGenerateLab = async () => {
    setGeneratingLab(true);
    setLabMsg(null);
    try {
      const res = await generateLabData();
      const ingestLine = `+${res.payments_ingested} payments, +${res.webhooks_ingested} webhooks, +${res.refunds_ingested} refunds ingested (seed ${res.seed}).`;

      // Two-stage message, matching what's actually happening as two separate
      // steps: ingestion completes first (visible immediately), then the scan
      // runs against the now-updated dataset and the message is replaced with
      // its real result — never implying the new records were "already
      // scanned" before detection actually ran on them.
      setLabMsg({ type: 'success', text: `${ingestLine} New data available — running anomaly scan…` });
      await loadLabRuns();
      await loadProvenance();
      await loadTableData();

      // A generation batch is not the same thing as an incident — most batches
      // (per the outcome distribution) inject nothing at all. Running the
      // (non-AI) anomaly scan against the now-updated dataset is what lets this
      // button honestly report "produced an incident" instead of guessing from
      // the injected scenario alone; it does NOT run Gemini and does NOT create
      // a completed investigation — that stays a separate, human-triggered step.
      let outcomeLine = '';
      try {
        const totalRecords = await fetchSourceStats().then(s =>
          Object.values(s.payments || {}).reduce((a, b) => a + b, 0)
        ).catch(() => null);
        const det = await triggerAnomalyDetection();
        const newOnes = (det.incidents || []).filter(i => i.incident_id);
        const recordsPhrase = totalRecords ? ` across ${totalRecords.toLocaleString('en-IN')} records` : '';
        outcomeLine = newOnes.length > 0
          ? `Detection scan complete — ${newOnes.length} anomal${newOnes.length === 1 ? 'y' : 'ies'} detected${recordsPhrase} (${newOnes.map(i => i.incident_id).join(', ')}).`
          : `Detection scan complete — no significant anomaly found${recordsPhrase}.`;
      } catch (e) {
        outcomeLine = 'Detection scan could not run after generation — use "Run Anomaly Scan" on Overview.';
      }

      setLabMsg({ type: 'success', text: `${ingestLine} ${outcomeLine}` });
      if (onRefreshAll) onRefreshAll();
    } catch (e) {
      setLabMsg({ type: 'error', text: `Generation failed: ${e.message}` });
    } finally {
      setGeneratingLab(false);
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
    loadLabRuns();
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
          text: `Synchronized ${res.payments_fetched} payments, ${res.orders_fetched} orders, and ${res.refunds_fetched} refunds from Razorpay Test API. ${res.payments_upserted} payments upserted.`
        });
      } else if (res.status === 'credentials_required') {
        setSyncMsg({ type: 'warning', text: res.message });
      }
      await loadProvenance();
      await loadTableData();
      if (onRefreshAll) onRefreshAll();
    } catch (e) {
      setSyncMsg({ type: 'error', text: `Razorpay sync failed: ${e.message}` });
    } finally {
      setSyncing(false);
    }
  };

  const realOrders = sourceStats?.orders?.razorpay_test || 0;
  const realPayments = sourceStats?.payments?.razorpay_test || 0;
  const realPaymentsCaptured = sourceStats?.payments_captured?.razorpay_test || 0;
  const realRefunds = sourceStats?.refunds?.razorpay_test || 0;
  const realWebhooks = sourceStats?.webhooks?.razorpay_webhook || 0;
  const detectionVolume = sourceStats?.detection_volume || null;

  const labOrders = sourceStats?.orders?.incident_lab || 0;
  const labPayments = sourceStats?.payments?.incident_lab || 0;
  const labRefunds = sourceStats?.refunds?.incident_lab || 0;
  const labWebhooks = sourceStats?.webhooks?.incident_lab || 0;

  const columnsFor = {
    payments: ['ID', 'Order', 'Merchant', 'Amount', 'Gateway', 'Status', 'Source', 'Timestamp'],
    orders: ['ID', 'Merchant', 'Amount', 'Status', 'Source', 'Timestamp'],
    refunds: ['ID', 'Payment', 'Merchant', 'Amount', 'Status', 'Source', 'Timestamp'],
    webhooks: ['Event ID', 'Event type', 'Entity', 'Signature', 'Source', 'Timestamp'],
  };

  return (
    <div className="cc-page">

      {/* DATA — quiet page identity */}
      <div className="cc-page-header" style={{ maxWidth: 'none', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ maxWidth: 640 }}>
          <h1 className="text-page-title">Data</h1>
          <p className="cc-page-desc">Every financial record in PostgreSQL, with explicit real-vs-simulated provenance.</p>
        </div>
        <Button tier="primary" onClick={handleSync} state={syncing ? 'loading' : 'idle'} loadingLabel="Syncing">
          <Zap size={13} strokeWidth={2} style={{ marginRight: 6 }} />
          Sync Razorpay
        </Button>
      </div>

      {syncMsg && (
        <p style={{ margin: 0, fontSize: '12.5px', color: syncMsg.type === 'success' ? 'var(--state-verified)' : syncMsg.type === 'warning' ? 'var(--sev-medium)' : 'var(--sev-critical)' }}>
          {syncMsg.text}
        </p>
      )}

      {/* SOURCE / PROVENANCE — two panels distinguished by texture as well
          as text: the simulated panel carries the provenance hatch
          (--hatch-simulated, established in Phase 1), the real panel stays
          flat. Neither is a heavy bordered card competing with the table
          below — this is context for the table, not a peer section. */}
      <div className="cc-provenance">
        <div className="cc-provenance-panel">
          <p className="cc-section-eyebrow">Real — Razorpay Test Mode</p>
          <div className="cc-provenance-metrics">
            <Metric size="sm" label="Orders" value={realOrders} sub="created, not paid" />
            <Metric size="sm" label="Payments" value={realPayments} sub={`${realPaymentsCaptured} captured`} />
            <Metric size="sm" label="Refunds" value={realRefunds} />
            <Metric size="sm" label="Webhooks" value={realWebhooks} />
          </div>
          {detectionVolume && !detectionVolume.razorpay_test_sufficient_for_detection && (
            <p className="cc-provenance-note" style={{ color: 'var(--sev-medium)' }}>
              {detectionVolume.razorpay_test_payment_count} payment attempt{detectionVolume.razorpay_test_payment_count === 1 ? '' : 's'} — intentionally below the {detectionVolume.min_sample_size}+ threshold used for reliable detection.
            </p>
          )}
        </div>

        <div className="cc-provenance-divider" />

        <div className="cc-provenance-panel cc-provenance-simulated">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <p className="cc-section-eyebrow" style={{ margin: 0 }}>Simulated — Incident Lab</p>
            <Button tier="ghost" onClick={handleGenerateLab} state={generatingLab ? 'loading' : 'idle'} loadingLabel="Generating">
              <Plus size={12} strokeWidth={2} style={{ marginRight: 4 }} />
              Generate new data
            </Button>
          </div>
          <div className="cc-provenance-metrics">
            <Metric size="sm" label="Orders" value={labOrders} />
            <Metric size="sm" label="Payments" value={labPayments} />
            <Metric size="sm" label="Refunds" value={labRefunds} />
            <Metric size="sm" label="Webhooks" value={labWebhooks} />
          </div>
          {labMsg && (
            <p className="cc-provenance-note" style={{ color: labMsg.type === 'success' ? 'var(--state-verified)' : 'var(--sev-critical)' }}>
              {labMsg.text}
            </p>
          )}
          {labRuns.length > 0 && (
            <div style={{ marginTop: '10px' }}>
              {labRuns.map((r) => (
                <div key={r.run_id} className="text-data" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <span style={{ color: 'var(--cc-text-secondary)' }}>seed={r.seed}</span>
                  <span>{r.anomaly_type}</span>
                  {r.target_entity_id && <span>→ {r.target_entity_id}</span>}
                  <span>({r.anomalous_events_count} anomalous)</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <p className="cc-provenance-footnote">
        Orders below are created via Razorpay's live test-mode Orders API — an order being created does not mean a payment
        was made. Captured-payment volume stays at this account's real, unpadded state. Incident Lab data is a synthetic
        financial event stream, not a real Razorpay payment. Both sources persist to the same PostgreSQL database with an
        immutable, queryable <span className="text-data" style={{ color: 'inherit' }}>source</span> tag on every row.
      </p>

      {/* VIEW CONTROL + DATASET + TABLE */}
      <section>
        <div className="cc-section-header" style={{ alignItems: 'center' }}>
          <SegmentedControl label="Table" value={activeTable} onChange={setActiveTable} options={TABLE_OPTIONS} />
          {activeTable !== 'webhooks' && (
            <SegmentedControl label="Source filter" value={sourceFilter} onChange={setSourceFilter} options={SOURCE_OPTIONS} />
          )}
        </div>

        <p className="cc-section-eyebrow" style={{ marginBottom: '10px' }}>
          {loading ? 'Loading…' : `${tableData.length} ${activeTable}${sourceFilter ? ` · ${sourceFilter === 'razorpay_test' ? 'real only' : 'simulated only'}` : ''}`}
        </p>

        {loading ? (
          <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--cc-text-tertiary)', fontSize: '13px' }}>
            Loading {activeTable} from PostgreSQL…
          </div>
        ) : tableData.length === 0 ? (
          <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--cc-text-tertiary)', fontSize: '13px' }}>
            Zero {activeTable} records found for the selected filter.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="cc-data-table">
              <thead>
                <tr>
                  {columnsFor[activeTable].map(col => (
                    <th key={col} className="cc-section-eyebrow" style={col === 'Amount' ? { textAlign: 'right' } : undefined}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tableData.map((row, idx) => (
                  <tr key={idx}>
                    {activeTable === 'payments' && (
                      <>
                        <td className="cc-data-mono cc-data-primary">{row.payment_id}</td>
                        <td className="cc-data-mono">{row.order_id}</td>
                        <td>{row.merchant_id}</td>
                        <td className="cc-numeric cc-data-amount">₹{Number(row.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                        <td className="cc-data-quiet">{row.gateway}</td>
                        <td><Chip tone={row.status === 'captured' ? 'verified' : 'critical'}>{row.status}</Chip></td>
                        <td className="cc-data-quiet">{sourceLabel(row.source)}</td>
                        <td className="text-data cc-data-quiet">{new Date(row.created_at).toLocaleString()}</td>
                      </>
                    )}

                    {activeTable === 'orders' && (
                      <>
                        <td className="cc-data-mono cc-data-primary">{row.order_id}</td>
                        <td>{row.merchant_id}</td>
                        <td className="cc-numeric cc-data-amount">₹{Number(row.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                        <td><Chip tone="verified">{row.status}</Chip></td>
                        <td className="cc-data-quiet">{sourceLabel(row.source)}</td>
                        <td className="text-data cc-data-quiet">{new Date(row.created_at).toLocaleString()}</td>
                      </>
                    )}

                    {activeTable === 'refunds' && (
                      <>
                        <td className="cc-data-mono cc-data-primary">{row.refund_id}</td>
                        <td className="cc-data-mono">{row.payment_id}</td>
                        <td>{row.merchant_id}</td>
                        <td className="cc-numeric cc-data-amount">₹{Number(row.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                        <td><Chip tone="medium">{row.status}</Chip></td>
                        <td className="cc-data-quiet">{sourceLabel(row.source)}</td>
                        <td className="text-data cc-data-quiet">{new Date(row.created_at).toLocaleString()}</td>
                      </>
                    )}

                    {activeTable === 'webhooks' && (
                      <>
                        <td className="cc-data-mono cc-data-primary">{row.event_id || row.external_event_id}</td>
                        <td style={{ fontWeight: 600 }}>{row.event_type}</td>
                        <td className="cc-data-mono cc-data-quiet">{row.entity_id || '—'}</td>
                        <td><Chip tone={row.signature_verified ? 'verified' : 'neutral'}>{row.signature_verified ? 'HMAC verified' : 'Standard'}</Chip></td>
                        <td className="cc-data-quiet">{sourceLabel(row.source || 'razorpay_webhook')}</td>
                        <td className="text-data cc-data-quiet">{new Date(row.received_at).toLocaleString()}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

    </div>
  );
}
