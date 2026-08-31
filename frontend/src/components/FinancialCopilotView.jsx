import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  uploadFinancialDocument, fetchFinancialDocuments, fetchFinancialSummary,
  fetchFinancialTransactions, askCopilot, fetchCopilotRuns, fetchCopilotRun,
  financialDocumentDownloadUrl, fetchFinancialDocumentPreview, deleteFinancialDocument
} from '../api';

const SUGGESTED_QUESTIONS = [
  "Find unusual transactions",
  "Why did spending increase?",
  "Compare this month vs last month",
  "Find recurring payments",
  "Explain my largest charges"
];

const DOC_TYPE_OPTIONS = [
  { value: '', label: 'Auto-detect' },
  { value: 'bank_statement', label: 'Bank Statement' },
  { value: 'credit_card_statement', label: 'Credit Card Statement' },
  { value: 'transaction_csv', label: 'Transaction CSV' },
  { value: 'invoice', label: 'Invoice' },
  { value: 'fee_policy', label: 'Fee / Policy Document' },
  { value: 'refund_report', label: 'Refund Report' }
];

const STATUS_BADGE = {
  ready: { label: 'READY', color: '#34d399', bg: 'rgba(52, 211, 153, 0.12)' },
  processing: { label: 'PROCESSING', color: '#60a5fa', bg: 'rgba(96, 165, 250, 0.12)' },
  partial: { label: 'READY — SEARCH ONLY', color: '#fbbf24', bg: 'rgba(251, 191, 36, 0.12)' },
  failed: { label: 'FAILED', color: '#f87171', bg: 'rgba(248, 113, 113, 0.12)' }
};

const LOADING_PHASES = [
  "Analyzing your financial data…",
  "Retrieving relevant evidence…",
  "Preparing your answer…"
];

function LoadingBubble() {
  const [phase, setPhase] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setPhase(p => (p + 1) % LOADING_PHASES.length), 1600);
    return () => clearInterval(id);
  }, []);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--text-muted)', fontSize: '13px' }}>
      <span className="spinner"></span>
      <span>{LOADING_PHASES[phase]}</span>
    </div>
  );
}

function AnswerBody({ report, incidents, onSelectIncident, onViewTransactions }) {
  const matchedIncidentFor = (merchant) => {
    if (!merchant || !incidents) return null;
    const lower = merchant.toLowerCase();
    return incidents.find(inc => inc.target_entity_id && inc.target_entity_id.toLowerCase().includes(lower)) || null;
  };

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', marginBottom: '12px', flexWrap: 'wrap' }}>
        <div style={{ fontSize: '11px', fontWeight: '800', color: 'var(--primary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Answer</div>
        {report.insufficient_evidence && (
          <span style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '4px', background: 'rgba(251, 191, 36, 0.12)', color: '#fbbf24', fontWeight: '700' }}>INSUFFICIENT EVIDENCE</span>
        )}
      </div>
      <p style={{ fontSize: '16px', lineHeight: '1.6', color: 'var(--text)', margin: '0 0 20px 0', fontWeight: '600' }}>
        {report.answer}
      </p>

      {report.primary_drivers?.length > 0 && (
        <div style={{ marginBottom: '18px' }}>
          <div style={{ fontSize: '11px', fontWeight: '800', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '8px' }}>Primary Drivers</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {report.primary_drivers.map((d, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', padding: '6px 10px', background: 'rgba(0,0,0,0.15)', borderRadius: '4px' }}>
                <span style={{ color: 'var(--text)' }}>{d.label}</span>
                <span style={{ color: d.direction === 'increase' ? '#f87171' : '#34d399', fontWeight: '700' }}>
                  {d.direction === 'increase' ? '+' : '−'}₹{Math.abs(d.amount).toLocaleString('en-IN')}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {report.notable_transactions?.length > 0 && (
        <div style={{ marginBottom: '18px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <div style={{ fontSize: '11px', fontWeight: '800', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Notable Transactions</div>
            <button onClick={onViewTransactions} style={{ background: 'none', border: 'none', color: 'var(--primary)', fontSize: '11px', fontWeight: '700', cursor: 'pointer' }}>
              [View Transactions]
            </button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {report.notable_transactions.map((t, i) => {
              const matched = matchedIncidentFor(t.merchant);
              return (
                <div key={i} style={{ padding: '10px 12px', background: 'rgba(0,0,0,0.15)', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                    <span style={{ fontSize: '13px', color: 'var(--text)', fontWeight: '600' }}>{t.merchant}</span>
                    <span style={{ fontSize: '13px', color: '#f87171', fontWeight: '700' }}>₹{Number(t.amount).toLocaleString('en-IN')}</span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>{t.date} · {t.reason}</div>
                  {matched && (
                    <button
                      onClick={() => onSelectIncident && onSelectIncident(matched)}
                      style={{ marginTop: '6px', background: 'rgba(248, 113, 113, 0.12)', border: '1px solid rgba(248, 113, 113, 0.3)', color: '#f87171', fontSize: '11px', fontWeight: '700', padding: '4px 10px', borderRadius: '4px', cursor: 'pointer' }}>
                      ⚠ Related MoneyOps incident found — [Open Investigation]
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {report.evidence?.length > 0 && (
        <div style={{ marginBottom: '18px' }}>
          <div style={{ fontSize: '11px', fontWeight: '800', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '8px' }}>Evidence</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {report.evidence.map((e, i) => (
              <div key={i} style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
                <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', flexShrink: 0, marginTop: '1px',
                  background: e.type === 'calculation' ? 'rgba(96, 165, 250, 0.12)' : e.type === 'document' ? 'rgba(167, 139, 250, 0.12)' : 'rgba(52, 211, 153, 0.12)',
                  color: e.type === 'calculation' ? '#60a5fa' : e.type === 'document' ? '#a78bfa' : '#34d399' }}>
                  {e.type === 'calculation' ? 'DETERMINISTIC CALC' : e.type === 'document' ? 'DOCUMENT' : 'TRANSACTION'}
                </span>
                <span>
                  {e.filename && <strong style={{ color: 'var(--text)' }}>{e.filename}{e.page ? ` (p.${e.page})` : ''}{e.section ? ` — ${e.section}` : ''}: </strong>}
                  {e.detail}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {report.sources_consulted?.length > 0 && (
        <div>
          <div style={{ fontSize: '11px', fontWeight: '800', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '8px' }}>Sources Consulted</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {report.sources_consulted.map((s, i) => (
              <span key={i} style={{ fontSize: '11px', padding: '4px 10px', borderRadius: '4px', background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}>
                📄 {s.filename}{s.page ? ` · p.${s.page}` : ''}{s.section ? ` · ${s.section}` : ''}
              </span>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

export default function FinancialCopilotView({ incidents, onSelectIncident }) {
  const [summary, setSummary] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [runs, setRuns] = useState([]);
  const [showUpload, setShowUpload] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadType, setUploadType] = useState('');
  const [uploadAccount, setUploadAccount] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadNotice, setUploadNotice] = useState(null);

  const [query, setQuery] = useState('');
  const [asking, setAsking] = useState(false);
  const [conversation, setConversation] = useState([]); // [{id, question, status, report, error, run_id, model, timestamp}]
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [showTransactions, setShowTransactions] = useState(false);
  const [transactionList, setTransactionList] = useState([]);

  const [previewDoc, setPreviewDoc] = useState(null); // {document, transactions, chunks}
  const [previewLoading, setPreviewLoading] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const conversationEndRef = useRef(null);

  const loadAll = useCallback(async () => {
    try {
      const [s, docs, runHistory] = await Promise.all([
        fetchFinancialSummary().catch(() => null),
        fetchFinancialDocuments().catch(() => []),
        fetchCopilotRuns(15).catch(() => [])
      ]);
      setSummary(s);
      setDocuments(docs || []);
      setRuns(runHistory || []);
    } catch (e) {
      console.error('Failed to load Financial Copilot data:', e);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  useEffect(() => {
    conversationEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [conversation.length, conversation[conversation.length - 1]?.status]);

  const handleUpload = async () => {
    if (!uploadFile) return;
    setUploading(true);
    setUploadNotice(null);
    try {
      const result = await uploadFinancialDocument(uploadFile, uploadType || null, uploadAccount || null);
      if (result.processing_status === 'ready') {
        setUploadNotice({ type: 'success', text: `✓ ${result.filename} indexed — ${result.transactions_extracted} transactions extracted, ${result.chunks_embedded}/${result.chunks_created} chunks embedded.` });
      } else {
        setUploadNotice({ type: 'error', text: `${result.filename} failed to process: ${result.error_message || 'Unknown error'}` });
      }
      setUploadFile(null);
      await loadAll();
    } catch (e) {
      setUploadNotice({ type: 'error', text: e.message });
    } finally {
      setUploading(false);
    }
  };

  const handleAsk = async (q) => {
    const question = (q || query).trim();
    if (!question || asking) return;

    const turnId = `turn_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    setConversation(prev => [...prev, { id: turnId, question, status: 'loading', timestamp: new Date().toISOString() }]);
    setQuery('');
    setAsking(true);
    setSelectedRunId(null);

    try {
      const result = await askCopilot(question);
      setConversation(prev => prev.map(t => t.id === turnId
        ? { ...t, status: 'done', report: result.report, run_id: result.run_id, model: result.model }
        : t));
      await loadAll();
    } catch (e) {
      setConversation(prev => prev.map(t => t.id === turnId ? { ...t, status: 'error', error: e.message } : t));
    } finally {
      setAsking(false);
    }
  };

  const handleOpenHistory = async (run) => {
    setSelectedRunId(run.run_id);
    const existing = conversation.find(t => t.run_id === run.run_id);
    if (existing) {
      conversationEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      return;
    }
    try {
      const detail = await fetchCopilotRun(run.run_id);
      const isError = detail.response && detail.response.error;
      setConversation(prev => [...prev, {
        id: `hist_${run.run_id}`,
        question: detail.query,
        status: isError ? 'error' : 'done',
        report: isError ? null : detail.response,
        error: isError ? detail.response.error : null,
        run_id: detail.run_id,
        model: detail.model,
        timestamp: detail.created_at,
        isHistorical: true
      }]);
    } catch (e) {
      console.error('Failed to load history entry:', e);
    }
  };

  const handleViewTransactions = async () => {
    try {
      const txns = await fetchFinancialTransactions(100);
      setTransactionList(txns);
      setShowTransactions(true);
    } catch (e) {
      console.error(e);
    }
  };

  const handleView = async (doc) => {
    if (!doc.has_raw_content) return;
    if (doc.content_type === 'application/pdf') {
      window.open(financialDocumentDownloadUrl(doc.document_id, 'inline'), '_blank');
      return;
    }
    setPreviewLoading(true);
    try {
      const data = await fetchFinancialDocumentPreview(doc.document_id);
      setPreviewDoc(data);
    } catch (e) {
      console.error(e);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleDelete = async (documentId) => {
    setDeletingId(documentId);
    try {
      await deleteFinancialDocument(documentId);
      setConfirmDeleteId(null);
      await loadAll();
    } catch (e) {
      console.error(e);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="view-container" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* HEADER */}
      <div className="card" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--primary)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '6px' }}>
              Financial Intelligence Copilot
            </div>
            <h1 style={{ fontSize: '22px', fontWeight: '800', color: 'var(--text)', margin: 0 }}>
              Your financial evidence, analyzed with AI.
            </h1>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: '6px 0 0 0' }}>
              Hybrid retrieval over your uploaded statements and policies — structured PostgreSQL analytics + document RAG + Gemini reasoning, always grounded in real evidence.
            </p>
          </div>
          <button className="btn btn-primary" onClick={() => setShowUpload(v => !v)} style={{ padding: '10px 20px', fontWeight: '700', fontSize: '13px' }}>
            + Upload Financial Data
          </button>
        </div>

        {showUpload && (
          <div style={{ marginTop: '20px', padding: '16px', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)', borderRadius: '8px', display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'flex-end' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>File (PDF, CSV, XLSX)</label>
              <input type="file" accept=".pdf,.csv,.xlsx,.xls" onChange={e => setUploadFile(e.target.files[0] || null)} style={{ fontSize: '12px', color: 'var(--text)' }} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Document Type</label>
              <select value={uploadType} onChange={e => setUploadType(e.target.value)} style={{ padding: '6px 8px', borderRadius: '6px', background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text)', fontSize: '12px' }}>
                {DOC_TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Account Name (optional)</label>
              <input type="text" value={uploadAccount} onChange={e => setUploadAccount(e.target.value)} placeholder="Primary Business Account"
                style={{ padding: '6px 8px', borderRadius: '6px', background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text)', fontSize: '12px' }} />
            </div>
            <button className="btn" onClick={handleUpload} disabled={!uploadFile || uploading}
              style={{ background: 'rgba(99, 102, 241, 0.15)', borderColor: 'rgba(99, 102, 241, 0.4)', color: 'var(--primary)', padding: '8px 16px', fontSize: '12px', fontWeight: '600' }}>
              {uploading ? 'Processing…' : 'Ingest Document'}
            </button>
          </div>
        )}

        {uploadNotice && (
          <div style={{ marginTop: '12px', padding: '10px 14px', borderRadius: '6px', fontSize: '12px',
            background: uploadNotice.type === 'success' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
            border: `1px solid ${uploadNotice.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
            color: uploadNotice.type === 'success' ? '#10b981' : '#f87171' }}>
            {uploadNotice.text}
          </div>
        )}
      </div>

      {/* CONNECTED DATA SUMMARY */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
        <div className="card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Documents</div>
          <div style={{ fontSize: '28px', fontWeight: '800', color: 'var(--text)', marginTop: '8px' }}>{summary?.documents ?? 0}</div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>{summary?.documents_ready ?? 0} ready for retrieval</div>
        </div>
        <div className="card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Transactions</div>
          <div style={{ fontSize: '28px', fontWeight: '800', color: 'var(--text)', marginTop: '8px' }}>{(summary?.transactions ?? 0).toLocaleString('en-IN')}</div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>Structured, in PostgreSQL</div>
        </div>
        <div className="card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Accounts</div>
          <div style={{ fontSize: '28px', fontWeight: '800', color: 'var(--text)', marginTop: '8px' }}>{summary?.accounts ?? 0}</div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>Derived from uploads</div>
        </div>
        <div className="card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Total Volume</div>
          <div style={{ fontSize: '28px', fontWeight: '800', color: 'var(--text)', marginTop: '8px' }}>₹{(summary?.total_volume_inr ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>Across all transactions</div>
        </div>
      </div>

      {/* DOCUMENT LIBRARY */}
      <div className="card" style={{ padding: '20px' }}>
        <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text)', marginBottom: '12px' }}>Connected Documents</div>
        {documents.length === 0 ? (
          <div style={{ fontSize: '13px', color: 'var(--text-muted)', padding: '12px 0' }}>No documents uploaded yet.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {documents.map(d => {
              const badge = STATUS_BADGE[d.processing_status] || STATUS_BADGE.processing;
              const isCsv = d.content_type && d.content_type.includes('csv');
              const isPdf = d.content_type === 'application/pdf';
              return (
                <div key={d.document_id} style={{ padding: '12px', background: 'rgba(255,255,255,0.02)', borderRadius: '6px', border: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '10px', color: badge.color, background: badge.bg, fontWeight: '700' }}>{badge.label}</span>
                      <span style={{ fontSize: '13px', color: 'var(--text)', fontWeight: '600' }}>{d.filename}</span>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{d.document_type}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      {d.has_raw_content && (
                        <button onClick={() => handleView(d)} disabled={previewLoading}
                          style={{ background: 'rgba(99, 102, 241, 0.1)', border: '1px solid rgba(99, 102, 241, 0.3)', color: 'var(--primary)', fontSize: '11px', fontWeight: '600', padding: '4px 10px', borderRadius: '4px', cursor: 'pointer' }}>
                          {isPdf ? 'View' : isCsv ? 'Preview' : 'View'}
                        </button>
                      )}
                      {d.has_raw_content && (
                        <a href={financialDocumentDownloadUrl(d.document_id, 'attachment')}
                          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)', color: 'var(--text-muted)', fontSize: '11px', fontWeight: '600', padding: '4px 10px', borderRadius: '4px', textDecoration: 'none' }}>
                          Download
                        </a>
                      )}
                      {confirmDeleteId === d.document_id ? (
                        <span style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                          <span style={{ fontSize: '11px', color: '#fbbf24' }}>Delete permanently?</span>
                          <button onClick={() => handleDelete(d.document_id)} disabled={deletingId === d.document_id}
                            style={{ background: 'rgba(248, 113, 113, 0.15)', border: '1px solid rgba(248, 113, 113, 0.4)', color: '#f87171', fontSize: '11px', fontWeight: '700', padding: '4px 10px', borderRadius: '4px', cursor: 'pointer' }}>
                            {deletingId === d.document_id ? 'Removing…' : 'Yes, delete'}
                          </button>
                          <button onClick={() => setConfirmDeleteId(null)} style={{ background: 'none', border: '1px solid var(--border)', color: 'var(--text-muted)', fontSize: '11px', padding: '4px 10px', borderRadius: '4px', cursor: 'pointer' }}>
                            Cancel
                          </button>
                        </span>
                      ) : (
                        <button onClick={() => setConfirmDeleteId(d.document_id)}
                          style={{ background: 'none', border: '1px solid var(--border)', color: 'var(--text-muted)', fontSize: '11px', fontWeight: '600', padding: '4px 10px', borderRadius: '4px', cursor: 'pointer' }}>
                          Remove
                        </button>
                      )}
                    </div>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '8px', display: 'flex', gap: '14px', flexWrap: 'wrap' }}>
                    <span>{d.chunk_count} chunk{d.chunk_count === 1 ? '' : 's'} indexed</span>
                    <span>{d.transaction_count} transaction{d.transaction_count === 1 ? '' : 's'} extracted</span>
                    <span>Uploaded {new Date(d.uploaded_at).toLocaleString()}</span>
                    {!d.has_raw_content && <span style={{ color: '#fbbf24' }}>Original file unavailable (uploaded before file storage)</span>}
                  </div>
                  {(d.processing_status === 'failed' || d.processing_status === 'partial') && d.error_message && (
                    <div style={{ fontSize: '11px', color: d.processing_status === 'failed' ? '#f87171' : '#fbbf24', marginTop: '4px' }}>{d.error_message}</div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* PREVIEW MODAL (CSV/XLSX table preview) */}
      {previewDoc && (
        <div onClick={() => setPreviewDoc(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px' }}>
          <div onClick={e => e.stopPropagation()} className="card" style={{ maxWidth: '900px', width: '100%', maxHeight: '80vh', overflowY: 'auto', padding: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text)' }}>{previewDoc.document.filename}</div>
              <button onClick={() => setPreviewDoc(null)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '16px' }}>✕</button>
            </div>
            {previewDoc.transactions.length > 0 ? (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                  <thead>
                    <tr style={{ textAlign: 'left', color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
                      <th style={{ padding: '8px' }}>Date</th><th style={{ padding: '8px' }}>Merchant</th><th style={{ padding: '8px' }}>Category</th>
                      <th style={{ padding: '8px' }}>Type</th><th style={{ padding: '8px', textAlign: 'right' }}>Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {previewDoc.transactions.map(t => (
                      <tr key={t.transaction_id} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ padding: '8px', color: 'var(--text-muted)' }}>{new Date(t.transaction_date).toLocaleDateString()}</td>
                        <td style={{ padding: '8px', color: 'var(--text)' }}>{t.merchant || '—'}</td>
                        <td style={{ padding: '8px', color: 'var(--text-muted)' }}>{t.category || '—'}</td>
                        <td style={{ padding: '8px', color: t.transaction_type === 'credit' ? '#34d399' : '#f87171' }}>{t.transaction_type}</td>
                        <td style={{ padding: '8px', textAlign: 'right', color: 'var(--text)', fontWeight: '600' }}>₹{Number(t.amount).toLocaleString('en-IN')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : previewDoc.chunks.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {previewDoc.chunks.map(c => (
                  <div key={c.chunk_id} style={{ padding: '10px', background: 'rgba(0,0,0,0.15)', borderRadius: '6px', fontSize: '12px', color: 'var(--text-muted)', whiteSpace: 'pre-wrap' }}>
                    {c.section && <div style={{ color: 'var(--text)', fontWeight: '700', marginBottom: '4px' }}>{c.section}{c.page_number ? ` (p.${c.page_number})` : ''}</div>}
                    {c.content}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>No indexed content available for this document.</div>
            )}
          </div>
        </div>
      )}

      {/* INVESTIGATE — chat-style conversation */}
      <div className="card" style={{ padding: '24px' }}>
        <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text)', marginBottom: '10px' }}>Investigate</div>

        {conversation.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '20px' }}>
            {conversation.map(turn => (
              <div key={turn.id} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {/* USER MESSAGE */}
                <div style={{ alignSelf: 'flex-end', maxWidth: '80%' }}>
                  <div style={{ fontSize: '10px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px', textAlign: 'right' }}>You</div>
                  <div style={{ padding: '10px 16px', background: 'rgba(99, 102, 241, 0.12)', border: '1px solid rgba(99, 102, 241, 0.3)', borderRadius: '10px', color: 'var(--text)', fontSize: '14px' }}>
                    {turn.question}
                  </div>
                </div>

                {/* ASSISTANT MESSAGE */}
                <div style={{
                  alignSelf: 'flex-start', width: '100%',
                  border: turn.run_id === selectedRunId ? '1px solid rgba(99, 102, 241, 0.5)' : '1px solid var(--border)',
                  borderRadius: '10px', padding: '18px', background: 'rgba(0,0,0,0.12)'
                }}>
                  <div style={{ fontSize: '10px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '10px' }}>
                    MoneyOps AI {turn.isHistorical && <span style={{ color: '#60a5fa' }}>· from history</span>}
                  </div>
                  {turn.status === 'loading' && <LoadingBubble />}
                  {turn.status === 'error' && (
                    <div style={{ color: '#f87171', fontSize: '13px' }}><strong>Copilot Notice:</strong> {turn.error}</div>
                  )}
                  {turn.status === 'done' && turn.report && (
                    <AnswerBody report={turn.report} incidents={incidents} onSelectIncident={onSelectIncident} onViewTransactions={handleViewTransactions} />
                  )}
                </div>
              </div>
            ))}
            <div ref={conversationEndRef} />
          </div>
        )}

        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleAsk(); }}
            placeholder="Ask about your financial data…"
            disabled={asking}
            style={{ flex: 1, minWidth: '260px', padding: '14px 16px', borderRadius: '8px', background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text)', fontSize: '14px' }}
          />
          <button className="btn btn-primary" onClick={() => handleAsk()} disabled={asking || !query.trim()} style={{ padding: '12px 24px', fontWeight: '700', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            {asking && <span className="spinner"></span>}
            {asking ? 'Investigating…' : 'Ask'}
          </button>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '12px' }}>
          {SUGGESTED_QUESTIONS.map(q => (
            <button key={q} onClick={() => handleAsk(q)} disabled={asking}
              style={{ padding: '6px 12px', borderRadius: '14px', background: 'rgba(99, 102, 241, 0.1)', border: '1px solid rgba(99, 102, 241, 0.3)', color: 'var(--primary)', fontSize: '11px', cursor: asking ? 'default' : 'pointer', opacity: asking ? 0.5 : 1 }}>
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* TRANSACTION TABLE (toggled via View Transactions) */}
      {showTransactions && (
        <div className="card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text)' }}>Transactions ({transactionList.length})</div>
            <button onClick={() => setShowTransactions(false)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '12px' }}>✕ Close</button>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
              <thead>
                <tr style={{ textAlign: 'left', color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
                  <th style={{ padding: '8px' }}>Date</th>
                  <th style={{ padding: '8px' }}>Merchant</th>
                  <th style={{ padding: '8px' }}>Category</th>
                  <th style={{ padding: '8px' }}>Type</th>
                  <th style={{ padding: '8px', textAlign: 'right' }}>Amount</th>
                </tr>
              </thead>
              <tbody>
                {transactionList.map(t => (
                  <tr key={t.transaction_id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '8px', color: 'var(--text-muted)' }}>{new Date(t.transaction_date).toLocaleDateString()}</td>
                    <td style={{ padding: '8px', color: 'var(--text)' }}>{t.merchant || '—'}</td>
                    <td style={{ padding: '8px', color: 'var(--text-muted)' }}>{t.category || '—'}</td>
                    <td style={{ padding: '8px', color: t.transaction_type === 'credit' ? '#34d399' : '#f87171' }}>{t.transaction_type}</td>
                    <td style={{ padding: '8px', textAlign: 'right', color: 'var(--text)', fontWeight: '600' }}>₹{Number(t.amount).toLocaleString('en-IN')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* RUN HISTORY (Copilot auditability — click to restore, never re-runs Gemini) */}
      {runs.length > 0 && (
        <div className="card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text)', marginBottom: '10px' }}>Recent Investigations</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {runs.map(r => (
              <button key={r.run_id} onClick={() => handleOpenHistory(r)}
                style={{
                  display: 'flex', justifyContent: 'space-between', gap: '8px', fontSize: '12px', padding: '8px 10px',
                  background: selectedRunId === r.run_id ? 'rgba(99, 102, 241, 0.12)' : 'rgba(255,255,255,0.02)',
                  border: selectedRunId === r.run_id ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
                  borderRadius: '4px', flexWrap: 'wrap', cursor: 'pointer', textAlign: 'left', width: '100%'
                }}>
                <span style={{ color: 'var(--text)' }}>{r.query}</span>
                <span style={{ color: 'var(--text-muted)', fontFamily: 'monospace' }}>{new Date(r.created_at).toLocaleString()}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
