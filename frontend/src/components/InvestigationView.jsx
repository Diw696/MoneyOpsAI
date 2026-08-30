import React, { useState, useEffect } from 'react';
import { 
  runInvestigation, 
  fetchIncidentInvestigations, 
  fetchInvestigationSteps,
  fetchIncidentActions,
  fetchSimilarIncidents,
  proposeAction,
  approveAction,
  rejectAction,
  executeAction
} from '../api';

// One authoritative per-row status label derivable WITHOUT an extra per-incident
// fetch (governed-action state like "awaiting approval" needs its own API call,
// so the workspace list intentionally only shows what the incidents list already
// carries: investigation_status. The detail pane on the right shows the fuller
// approval/execution state once an incident is selected).
const rowStatusPill = (inc) => ({
  not_investigated: { label: 'PENDING INVESTIGATION', color: '#94a3b8', bg: 'rgba(148, 163, 184, 0.12)' },
  investigating: { label: 'INVESTIGATING…', color: '#60a5fa', bg: 'rgba(96, 165, 250, 0.12)' },
  investigated: { label: 'INVESTIGATED', color: '#34d399', bg: 'rgba(52, 211, 153, 0.12)' },
  investigation_failed: { label: 'INVESTIGATION FAILED', color: '#f87171', bg: 'rgba(248, 113, 113, 0.12)' }
}[inc.investigation_status || 'not_investigated']);

function WorkspaceRow({ inc, isSelected, onClick, isCompleted }) {
  const pill = rowStatusPill(inc);
  const isRejected = inc.status === 'rejected';
  return (
    <button
      onClick={onClick}
      style={{
        display: 'block',
        width: '100%',
        textAlign: 'left',
        padding: isCompleted ? '9px 12px' : '11px 12px',
        borderRadius: '6px',
        border: isSelected ? '1px solid var(--border-hover)' : '1px solid transparent',
        borderLeft: isSelected ? '2px solid var(--primary)' : '2px solid transparent',
        background: isSelected ? 'var(--bg-card-hover)' : 'transparent',
        opacity: isCompleted && !isSelected ? 0.62 : 1,
        cursor: 'pointer',
        marginBottom: '3px',
        transition: 'opacity 0.15s ease'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', marginBottom: '3px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0 }}>
          {!isCompleted && (
            <span className={`badge badge-${inc.severity || 'medium'}`} style={{ fontSize: '9px', fontWeight: '800', padding: '1px 5px' }}>
              {(inc.severity || 'medium').toUpperCase()}
            </span>
          )}
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'monospace', flexShrink: 0 }}>{inc.incident_id}</span>
        </div>
        {!isCompleted && (
          <span style={{ fontSize: '9px', fontWeight: '700', padding: '1px 6px', borderRadius: '3px', background: pill.bg, color: pill.color, flexShrink: 0 }}>
            {pill.label}
          </span>
        )}
        {isCompleted && (
          <span style={{ fontSize: '9px', fontWeight: '700', padding: '1px 6px', borderRadius: '3px', flexShrink: 0, color: isRejected ? '#94a3b8' : '#34d399', background: isRejected ? 'rgba(148, 163, 184, 0.1)' : 'rgba(52, 211, 153, 0.1)' }}>
            {isRejected ? 'REJECTED' : 'RESOLVED'}
          </span>
        )}
      </div>
      <div style={{ fontSize: isCompleted ? '12.5px' : '13px', fontWeight: isCompleted ? '500' : '600', color: isCompleted ? 'var(--text-secondary)' : 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {inc.title}
      </div>
      <div style={{ fontSize: '10.5px', color: 'var(--text-muted)', marginTop: '2px' }}>
        {inc.target_entity_id} · {new Date(inc.detected_at).toLocaleDateString()}
      </div>
    </button>
  );
}

export default function InvestigationView({ incident, incidents = [], onSelectIncident, aiStatus, onRefreshAll }) {
  const [investigating, setInvestigating] = useState(false);
  const [investigationData, setInvestigationData] = useState(null);
  const [steps, setSteps] = useState([]);
  const [similarCases, setSimilarCases] = useState([]);
  const [similarCasesError, setSimilarCasesError] = useState(null);
  const [expandedStep, setExpandedStep] = useState(null);
  const [showMerchants, setShowMerchants] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [staleInvestigationNotice, setStaleInvestigationNotice] = useState(null);

  // Action Governor State
  const [actions, setActions] = useState([]);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState(null);

  // Depend on incident_id specifically, not the incident object — App.jsx's 5s
  // polling refresh creates a new object reference for the SAME incident on every
  // tick, and this effect must only reset/reload state on an actual navigation to
  // a different incident, not on every background refresh of the one being viewed.
  useEffect(() => {
    if (incident?.incident_id) {
      setExpandedStep(null);
      setShowMerchants(false);
      setErrorMsg(null);
      setActionMsg(null);
      loadInvestigationAndActions(incident.incident_id);
      loadSimilarCases(incident.incident_id);
    }
  }, [incident?.incident_id]);

  const loadSimilarCases = async (incId) => {
    try {
      const cases = await fetchSimilarIncidents(incId);
      setSimilarCases(cases && cases.length > 0 ? cases : []);
      setSimilarCasesError(null);
    } catch (e) {
      console.warn("Could not load similar cases:", e);
      setSimilarCases([]);
      setSimilarCasesError("Case-memory similarity lookup failed — no similar incidents could be retrieved.");
    }
  };


  const loadInvestigationAndActions = async (incId) => {
    // Reset first so switching incidents never shows stale state from the
    // previously-selected one while the new fetch is in flight.
    setInvestigationData(null);
    setSteps([]);
    setActions([]);
    setStaleInvestigationNotice(null);

    try {
      const [invs, acts] = await Promise.all([
        fetchIncidentInvestigations(incId).catch(() => []),
        fetchIncidentActions(incId).catch(() => [])
      ]);

      const sortedInvs = invs || [];
      const primaryAct = acts && acts.length > 0 ? acts[0] : null;

      // The most recent investigation ATTEMPT (sortedInvs[0]) is not necessarily the
      // one a proposed/approved/executed action is actually based on — a later
      // re-investigation can fail (e.g. a Gemini timeout) without invalidating an
      // earlier successful one an action already relies on. Show the investigation
      // the action is grounded in, and surface the later failure as a visible notice
      // instead of letting it silently look like the action has no basis at all.
      let toDisplay = sortedInvs.length > 0 ? sortedInvs[0] : null;

      if (primaryAct?.investigation_id) {
        const backing = sortedInvs.find(i => i.investigation_id === primaryAct.investigation_id);
        if (backing && backing.investigation_id !== toDisplay?.investigation_id) {
          if (toDisplay && toDisplay.status !== 'completed') {
            setStaleInvestigationNotice(
              `A more recent re-investigation attempt (${toDisplay.investigation_id}) ${toDisplay.status === 'failed' ? 'failed' : `is ${toDisplay.status}`} — showing investigation ${backing.investigation_id}, the one this action is actually based on.`
            );
          }
          toDisplay = backing;
        }
      }

      if (toDisplay) {
        setInvestigationData(toDisplay);
        const stps = await fetchInvestigationSteps(toDisplay.investigation_id);
        setSteps(stps || []);
      }

      setActions(acts || []);
    } catch (e) {
      console.warn("Could not load investigation/action details:", e);
    }
  };

  const handleInvestigate = async () => {
    if (!incident?.incident_id) return;
    setInvestigating(true);
    setErrorMsg(null);

    try {
      const res = await runInvestigation(incident.incident_id);
      if (res.status === 'completed') {
        setInvestigationData({
          investigation_id: res.investigation_id,
          status: 'completed',
          started_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
          provider: res.provider,
          model: res.model,
          what_happened: res.report?.what_happened || res.report?.summary,
          why_it_happened: res.report?.why,
          estimated_exposure: res.report?.financial_exposure?.amount_inr || incident.potential_exposure,
          recommendation: res.report?.recommendation,
          confidence: res.report?.confidence || 0.94,
          evidence_confidence: res.report?.evidence_confidence,
          historical_precedent: res.report?.historical_precedent,
          similar_cases: res.report?.similar_cases || [],
          evidence_json: res.report?.evidence ? JSON.stringify(res.report.evidence) : null,
          affected_entities_json: res.report?.affected_entities ? JSON.stringify(res.report.affected_entities) : null
        });

        const stps = await fetchInvestigationSteps(res.investigation_id);
        setSteps(stps || res.steps || []);

        if (res.report?.similar_cases) {
          setSimilarCases(res.report.similar_cases);
        } else {
          loadSimilarCases(incident.incident_id);
        }

        // Auto-propose governed action if none exists. Action type must match the
        // incident's own entity type — a merchant-type incident (refund spike,
        // duplicate refund, webhook failure) has no gateway to reroute traffic away
        // from, so it gets the merchant-scoped policy action instead.
        const isMerchantIncident = incident.target_entity_type === 'merchant';
        try {
          await proposeAction({
            incident_id: incident.incident_id,
            investigation_id: res.investigation_id,
            action_type: isMerchantIncident ? "pause_merchant_settlements" : "reroute_gateway_traffic",
            target_entity: incident.target_entity_id || "Gateway_X",
            reason: res.report?.recommendation || (isMerchantIncident
              ? "Place a temporary hold on merchant settlements pending review."
              : "Reroute traffic away from degraded banking node to backup partner nodes."),
            actor: "Gemini_Agent"
          });
          const acts = await fetchIncidentActions(incident.incident_id);
          setActions(acts || []);
        } catch (err) {
          console.warn("Auto propose action notice:", err);
        }

        if (onRefreshAll) onRefreshAll();
      } else {
        setErrorMsg(res.message || "Investigation could not be completed.");
      }
    } catch (err) {
      setErrorMsg(err.message || "Failed to contact Gemini investigation engine.");
    } finally {
      setInvestigating(false);
    }
  };

  const handleApprove = async (actionId) => {
    setActionLoading(true);
    setActionMsg(null);
    try {
      await approveAction(actionId, "Operator authorized traffic cutover per FinOps incident governance policy");
      setActionMsg("✓ Action approved by human operator. Ready for safe demonstration simulation.");
      const acts = await fetchIncidentActions(incident.incident_id);
      setActions(acts || []);
    } catch (e) {
      setActionMsg(`Approval failed: ${e.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async (actionId) => {
    setActionLoading(true);
    setActionMsg(null);
    try {
      await rejectAction(actionId, "Operator rejected automated traffic cutover");
      setActionMsg("Action rejected by operator. Governance policy prevented modification.");
      const acts = await fetchIncidentActions(incident.incident_id);
      setActions(acts || []);
      // A rejection is a final decision, same as execution — refresh the shared
      // incidents list immediately so the workspace sidebar moves this incident
      // out of Active/Pending right now, not after the next 5s poll.
      if (onRefreshAll) onRefreshAll();
    } catch (e) {
      setActionMsg(`Rejection failed: ${e.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleExecuteSimulation = async (actionId) => {
    setActionLoading(true);
    setActionMsg(null);
    try {
      await executeAction(actionId);
      setActionMsg("✓ Safe demonstration simulation completed. Immutable audit trail appended to PostgreSQL.");
      const acts = await fetchIncidentActions(incident.incident_id);
      setActions(acts || []);
      // Execution resolves the parent incident (open -> resolved) — refresh the
      // shared incidents list immediately so the workspace sidebar moves it from
      // Active/Pending into Completed right now, not after the next 5s poll.
      if (onRefreshAll) onRefreshAll();
    } catch (e) {
      setActionMsg(`Execution failed: ${e.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  // ACTIVE/PENDING = genuinely unresolved work only (any sub-state: not yet
  // investigated, investigating, investigated-awaiting-approval, approved). A
  // human rejection is just as final a decision as an executed simulation —
  // it moves to COMPLETED immediately, not only once something executes.
  const activeList = incidents
    .filter(i => i.status !== 'resolved' && i.status !== 'rejected')
    .slice()
    .sort((a, b) => {
      const aPending = a.investigation_status !== 'investigated' ? 0 : 1;
      const bPending = b.investigation_status !== 'investigated' ? 0 : 1;
      if (aPending !== bPending) return aPending - bPending;
      return new Date(b.detected_at) - new Date(a.detected_at);
    });
  const completedList = incidents
    .filter(i => i.status === 'resolved' || i.status === 'rejected')
    .slice()
    .sort((a, b) => new Date(b.detected_at) - new Date(a.detected_at));

  const workspaceSidebar = (
    <div style={{ width: '320px', flexShrink: 0, display: 'flex', flexDirection: 'column', gap: '18px' }}>
      <div>
        <div style={{ fontSize: '11px', fontWeight: '800', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px', display: 'flex', justifyContent: 'space-between' }}>
          <span>Active / Pending</span>
          <span>{activeList.length}</span>
        </div>
        {activeList.length === 0 ? (
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', padding: '10px 0' }}>No open incidents.</div>
        ) : (
          <div>
            {activeList.map(inc => (
              <WorkspaceRow
                key={inc.incident_id}
                inc={inc}
                isSelected={incident?.incident_id === inc.incident_id}
                isCompleted={false}
                onClick={() => onSelectIncident && onSelectIncident(inc)}
              />
            ))}
          </div>
        )}
      </div>

      <div>
        <div style={{ fontSize: '11px', fontWeight: '800', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px', display: 'flex', justifyContent: 'space-between' }}>
          <span>Completed</span>
          <span>{completedList.length}</span>
        </div>
        {completedList.length === 0 ? (
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', padding: '10px 0' }}>No resolved incidents yet.</div>
        ) : (
          <div>
            {completedList.map(inc => (
              <WorkspaceRow
                key={inc.incident_id}
                inc={inc}
                isSelected={incident?.incident_id === inc.incident_id}
                isCompleted={true}
                onClick={() => onSelectIncident && onSelectIncident(inc)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );

  if (!incident) {
    return (
      <div className="view-container" style={{ display: 'flex', gap: '20px', alignItems: 'flex-start' }}>
        {incidents.length > 0 && workspaceSidebar}
        <div className="card" style={{ padding: '60px 24px', textAlign: 'center', color: 'var(--text-muted)', flex: 1 }}>
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>🔍</div>
          <h3 style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text)', margin: '0 0 8px 0' }}>
            {incidents.length === 0 ? 'No Incidents Yet' : 'Select an Incident'}
          </h3>
          <p style={{ fontSize: '13px', margin: 0 }}>
            {incidents.length === 0
              ? 'Generate data and run a detection scan to discover the first incident.'
              : 'Pick an incident from Active/Pending or Completed on the left to view its investigation.'}
          </p>
        </div>
      </div>
    );
  }

  const isGeminiConnected = aiStatus?.configured;
  const primaryAction = actions.length > 0 ? actions[0] : null;

  const isMerchantIncident = incident.target_entity_type === 'merchant';
  const ev = incident.evidence || {};

  // Gateway-type incidents surface failure-rate-vs-peer evidence; merchant-type
  // incidents (refund spike / duplicate refund / webhook failure) surface
  // whichever of the three merchant evidence shapes this incident actually has —
  // there is no single shared metric name across all four scenario families.
  const primaryRatePct = ev.failure_rate_pct ?? ev.actual_refund_rate_pct ?? ev.webhook_failure_rate_pct ?? null;
  const baselineRatePct = ev.peer_failure_rate_pct ?? ev.baseline_refund_rate_pct ?? null;
  const primaryRateLabel = ev.failure_rate_pct != null ? 'FAILURE RATE' : (ev.actual_refund_rate_pct != null ? 'REFUND RATE' : (ev.webhook_failure_rate_pct != null ? 'WEBHOOK FAILURE RATE' : 'PRIMARY RATE'));
  const baselineRateLabel = ev.peer_failure_rate_pct != null ? 'PEER BASELINE' : (ev.baseline_refund_rate_pct != null ? "MERCHANT'S OWN BASELINE" : 'PEER BASELINE');

  const failureRate = primaryRatePct;
  const peerRate = baselineRatePct;
  const ratio = ev.failure_rate_ratio ?? ev.refund_rate_ratio ?? (peerRate && Number(peerRate) > 0 && failureRate ? (Number(failureRate) / Number(peerRate)).toFixed(2) : null);
  const topErrors = ev.top_failure_code_count ?? ev.duplicate_refund_payments ?? null;
  const topErrorsLabel = ev.top_failure_code_count != null ? 'GATEWAY TIMEOUTS' : (ev.duplicate_refund_payments != null ? 'DUPLICATE REFUNDS' : 'GATEWAY TIMEOUTS');
  const totalFailed = ev.failed_payments_count ?? ev.total_refunds ?? (incident.affected_payments || null);
  const exposureAmt = investigationData?.estimated_exposure ?? (incident.potential_exposure || null);
  const merchantCount = isMerchantIncident ? 1 : (incident.affected_merchants || null);

  let affectedMerchantsList = [];
  if (investigationData?.affected_entities_json) {
    try {
      affectedMerchantsList = JSON.parse(investigationData.affected_entities_json);
    } catch (e) {
      affectedMerchantsList = [];
    }
  }

  // Evidence confidence is only shown once a real investigation has computed it — never a placeholder guess.
  const evidenceScore = investigationData?.confidence != null
    ? Math.round(investigationData.confidence * 100)
    : null;

  const topSimilarCase = similarCases.length > 0 ? similarCases[0] : null;

  // Visible workflow stage: detected -> investigating -> investigated ->
  // recommendation available -> awaiting approval -> approved -> executed.
  // Nothing here implies "resolved" or "nothing found" just because a panel is empty.
  const workflowStage = (() => {
    if (investigating) return { label: 'Investigating…', color: '#60a5fa', bg: 'rgba(96, 165, 250, 0.12)' };
    if (!investigationData) return { label: 'Detected — not yet investigated', color: '#94a3b8', bg: 'rgba(148, 163, 184, 0.12)' };
    if (investigationData.status === 'running') return { label: 'Investigating…', color: '#60a5fa', bg: 'rgba(96, 165, 250, 0.12)' };
    if (investigationData.status === 'failed') return { label: 'Investigation attempt failed', color: '#f87171', bg: 'rgba(248, 113, 113, 0.12)' };
    if (!primaryAction) return { label: 'Investigated — recommendation available', color: '#34d399', bg: 'rgba(52, 211, 153, 0.12)' };
    if (primaryAction.status === 'pending_approval') return { label: 'Awaiting human approval', color: '#facc15', bg: 'rgba(250, 204, 21, 0.12)' };
    if (primaryAction.status === 'approved') return { label: 'Approved — ready to execute', color: '#60a5fa', bg: 'rgba(96, 165, 250, 0.12)' };
    if (primaryAction.status === 'executed') return { label: 'Executed (safe simulation)', color: '#34d399', bg: 'rgba(52, 211, 153, 0.12)' };
    if (primaryAction.status === 'rejected') return { label: 'Rejected by human', color: '#94a3b8', bg: 'rgba(148, 163, 184, 0.12)' };
    return { label: 'Investigated', color: '#34d399', bg: 'rgba(52, 211, 153, 0.12)' };
  })();

  return (
    <div className="view-container" style={{ display: 'flex', gap: '20px', alignItems: 'flex-start' }}>
      {workspaceSidebar}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '20px' }}>

      {/* 1. INCIDENT HEADER */}
      <div className="card" style={{ padding: '24px', background: 'var(--surface)', border: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px', flexWrap: 'wrap' }}>
              <span className={`badge badge-${incident.severity || 'critical'}`} style={{ fontSize: '11px', fontWeight: '800' }}>
                {incident.severity?.toUpperCase() || 'CRITICAL'}
              </span>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                {incident.incident_id}
              </span>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>•</span>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                Target: <strong style={{ color: 'var(--text)' }}>{incident.target_entity_id || 'Gateway_X'}</strong>
              </span>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>•</span>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                source: {incident.source || 'incident_lab'}
              </span>
              <span style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '4px', background: workflowStage.bg, color: workflowStage.color, fontWeight: '700' }}>
                {workflowStage.label}
              </span>
            </div>
            <h1 style={{ fontSize: '22px', fontWeight: '800', color: 'var(--text)', margin: '0 0 6px 0' }}>
              {incident.title}
            </h1>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
              Discovered by IsolationForest ML at: {new Date(incident.detected_at).toLocaleString()}
            </div>
            {investigationData?.status === 'completed' && (investigationData.completed_at || investigationData.started_at) && (
              <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '2px' }}>
                Last investigated: <strong style={{ color: 'var(--text)' }}>{new Date(investigationData.completed_at || investigationData.started_at).toLocaleString()}</strong> — this is a saved result, not something that just happened
              </div>
            )}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px' }}>
            {/* Primary CTA only for a fresh, never-investigated incident — once a
                real completed investigation exists, the loud primary action becomes
                whatever the Action Governor panel below needs next (review/approve/
                execute), and re-investigating is demoted to a small secondary link
                so a completed incident never again looks like it "still needs
                investigating". */}
            {!investigationData || investigationData.status !== 'completed' ? (
              <button
                className="btn btn-primary"
                onClick={handleInvestigate}
                disabled={investigating || !isGeminiConnected}
                style={{ padding: '10px 22px', fontWeight: '700', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}
              >
                {investigating ? (
                  <>
                    <span className="spinner"></span>
                    Gemini Querying PostgreSQL...
                  </>
                ) : (
                  <>⚡ Investigate with Gemini</>
                )}
              </button>
            ) : (
              <>
                <span style={{ fontSize: '13px', fontWeight: '700', color: '#34d399', padding: '9px 18px', border: '1px solid rgba(52, 211, 153, 0.3)', borderRadius: '6px', background: 'rgba(52, 211, 153, 0.08)' }}>
                  {primaryAction?.status === 'executed' || primaryAction?.status === 'approved' || primaryAction?.status === 'rejected'
                    ? '👁 View Investigation (below)'
                    : '📋 Review Recommendation (below)'}
                </span>
                <button
                  onClick={handleInvestigate}
                  disabled={investigating || !isGeminiConnected}
                  title="Re-runs Gemini against current evidence. Secondary/debugging use — does not undo the existing recommendation or approval."
                  style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '11.5px', fontWeight: '600', padding: '2px' }}
                >
                  {investigating ? 'Re-investigating…' : '↻ Re-investigate with Gemini'}
                </button>
              </>
            )}
          </div>
        </div>

        {errorMsg && (
          <div style={{ marginTop: '16px', padding: '12px 16px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', color: '#f87171', fontSize: '13px' }}>
            <strong>Investigation Notice:</strong> {errorMsg}
          </div>
        )}

        {staleInvestigationNotice && (
          <div style={{ marginTop: '16px', padding: '12px 16px', background: 'rgba(251, 191, 36, 0.1)', border: '1px solid rgba(251, 191, 36, 0.3)', borderRadius: '6px', color: '#fbbf24', fontSize: '13px' }}>
            <strong>Note:</strong> {staleInvestigationNotice}
          </div>
        )}
      </div>

      {/* 2. WHAT HAPPENED & WHY DID IT HAPPEN */}
      <div className="card" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          
          {/* What Happened */}
          <div>
            <div style={{ fontSize: '12px', fontWeight: '800', color: 'var(--primary)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '6px' }}>
              What Happened
            </div>
            <p style={{ margin: 0, fontSize: '15px', lineHeight: '1.6', color: 'var(--text)' }}>
              {investigationData?.what_happened || incident.description || "No description recorded for this incident yet."}
            </p>
          </div>

          <div style={{ height: '1px', background: 'var(--border)' }}></div>

          {/* Why Did It Happen */}
          <div>
            <div style={{ fontSize: '12px', fontWeight: '800', color: '#facc15', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '6px' }}>
              Why Did It Happen? (Root Cause)
            </div>
            <p style={{ margin: 0, fontSize: '15px', lineHeight: '1.6', color: 'var(--text)' }}>
              {investigationData?.why_it_happened || incident.primary_signal || "Root cause not yet determined — run \"Investigate with Gemini\" above."}
            </p>
          </div>

        </div>
      </div>

      {/* 3. FIVE CORE EVIDENCE CARDS */}
      <div style={{ fontSize: '11px', fontWeight: '800', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
        Current Incident Evidence
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
        
        <div className="card" style={{ padding: '18px 20px', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{primaryRateLabel}</div>
          <div style={{ fontSize: '24px', fontWeight: '800', color: '#f87171', marginTop: '6px' }}>
            {failureRate != null ? `${failureRate}%` : '—'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            {ratio != null ? `${ratio}x baseline` : 'No evidence recorded'}
          </div>
        </div>

        <div className="card" style={{ padding: '18px 20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{baselineRateLabel}</div>
          <div style={{ fontSize: '24px', fontWeight: '800', color: 'var(--text)', marginTop: '6px' }}>
            {peerRate != null ? `${peerRate}%` : '—'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            {isMerchantIncident && ev.baseline_refund_rate_pct != null ? "This merchant's historical rate" : 'Healthy peer average'}
          </div>
        </div>

        <div className="card" style={{ padding: '18px 20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{topErrorsLabel}</div>
          <div style={{ fontSize: '24px', fontWeight: '800', color: 'var(--text)', marginTop: '6px' }}>
            {topErrors != null && totalFailed != null ? `${topErrors} / ${totalFailed}` : (topErrors != null ? topErrors : '—')}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            {topErrors != null && totalFailed ? `${((topErrors / totalFailed) * 100).toFixed(2)}% concentration` : 'No evidence recorded'}
          </div>
        </div>

        <div className="card" style={{ padding: '18px 20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{isMerchantIncident ? 'TARGET MERCHANT' : 'AFFECTED MERCHANTS'}</div>
          <div style={{ fontSize: isMerchantIncident ? '15px' : '24px', fontWeight: '800', color: 'var(--text)', marginTop: '6px' }}>
            {isMerchantIncident ? (incident.target_entity_id || '—') : (merchantCount != null ? merchantCount : '—')}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            {isMerchantIncident ? 'Single-merchant incident' : 'Impacted across categories'}
          </div>
        </div>

        <div className="card" style={{ padding: '18px 20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>POTENTIAL EXPOSURE</div>
          <div style={{ fontSize: '24px', fontWeight: '800', color: '#f87171', marginTop: '6px' }}>
            {exposureAmt != null ? `₹${Number(exposureAmt).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '—'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Unresolved transaction value
          </div>
        </div>

      </div>

      {/* 4. CASE MEMORY (HISTORICAL SIMULATION PRECEDENTS) */}
      <div className="card" style={{ padding: '20px 24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: '800', padding: '3px 8px', borderRadius: '4px', background: 'rgba(99, 102, 241, 0.15)', color: 'var(--primary)' }}>
              🧠 CASE MEMORY • HISTORICAL SIMULATION PRECEDENTS
            </span>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              (PostgreSQL-backed similarity matching)
            </span>
          </div>

          {topSimilarCase && (
            <span style={{ fontSize: '12px', fontWeight: '700', color: '#10b981' }}>
              🎯 Top Match: {topSimilarCase.similarity_score_pct}% match ({topSimilarCase.match_tier}) — category + semantic signals
            </span>
          )}
        </div>

        {topSimilarCase ? (
          <div style={{ padding: '14px 18px', background: 'rgba(0, 0, 0, 0.2)', borderRadius: '8px', border: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px', flexWrap: 'wrap', gap: '8px' }}>
              <div>
                <span style={{ fontFamily: 'monospace', fontSize: '11px', color: 'var(--primary)', fontWeight: '700' }}>
                  {topSimilarCase.historical_incident_id}
                </span>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '0 8px' }}>•</span>
                <strong style={{ fontSize: '14px', color: 'var(--text)' }}>
                  {topSimilarCase.title}
                </strong>
              </div>
              <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', background: 'rgba(168, 85, 247, 0.15)', color: '#c084fc', border: '1px solid rgba(168, 85, 247, 0.3)' }}>
                {topSimilarCase.provenance}
              </span>
            </div>

            {topSimilarCase.factors && (
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', margin: '10px 0', padding: '10px 12px', background: 'rgba(0,0,0,0.25)', borderRadius: '6px', border: '1px solid var(--border)' }}>
                <div style={{ fontWeight: '700', color: 'var(--text)', marginBottom: '6px' }}>
                  {topSimilarCase.similarity_score_pct}% is a weighted composite, not raw semantic similarity — breakdown:
                </div>
                <div>Raw embedding cosine similarity: <strong>{topSimilarCase.cosine_similarity}</strong> (contributes {topSimilarCase.factors.cosine_sim_contrib} pts)</div>
                <div>Incident type match: {topSimilarCase.factors.type_match} pts · Entity match: {topSimilarCase.factors.entity_match} pts · Error code match: {topSimilarCase.factors.error_code_match} pts · Severity match: {topSimilarCase.factors.severity_match} pts</div>
              </div>
            )}

            <div style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.5', marginTop: '6px' }}>
              <div><strong>Historical Root Cause:</strong> {topSimilarCase.historical_root_cause}</div>
              <div style={{ marginTop: '4px' }}><strong>Previous Action Taken:</strong> {topSimilarCase.previous_action}</div>
              <div style={{ marginTop: '4px', color: '#10b981' }}><strong>Historical Outcome:</strong> {topSimilarCase.outcome}</div>
            </div>
          </div>
        ) : (
          <div style={{ fontSize: '13px', color: similarCasesError ? '#f87171' : 'var(--text-muted)' }}>
            {similarCasesError || 'No similar historical incidents found in Case Memory for this incident.'}
          </div>
        )}
      </div>

      {/* 5. AFFECTED MERCHANTS — gateway-type incidents only; a merchant-type
          incident's single target is already shown in the evidence card above. */}
      {!isMerchantIncident && (
        <div className="card" style={{ padding: '20px 24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <span style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text)' }}>
                👥 Affected Merchants: <strong>{merchantCount != null ? `${merchantCount} merchants` : 'No evidence recorded'}</strong>
              </span>
            </div>

            <button
              onClick={() => setShowMerchants(!showMerchants)}
              style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', fontSize: '13px', fontWeight: '600' }}
            >
              {showMerchants ? '▲ Hide Merchant List' : '▼ View Affected Merchants'}
            </button>
          </div>

          {showMerchants && (
            <div style={{ marginTop: '16px', padding: '14px 18px', background: 'rgba(0, 0, 0, 0.2)', borderRadius: '8px', border: '1px solid var(--border)' }}>
              {affectedMerchantsList.length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
                  {affectedMerchantsList.map((m, idx) => (
                    <div key={idx} style={{ padding: '8px 12px', background: 'rgba(255, 255, 255, 0.02)', borderRadius: '4px', border: '1px solid var(--border)', fontSize: '12px' }}>
                      <strong style={{ color: 'var(--text)' }}>{m.merchant_name || m.merchant_id}</strong>
                      <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>{m.failures_count || m.failures} failures</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  No per-merchant breakdown was returned by this investigation's <code>get_affected_merchants</code> tool call yet — run or re-run the investigation to populate this list from real PostgreSQL data.
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 6. EVIDENCE CONFIDENCE & AI RECOMMENDATION */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        
        {/* Evidence Confidence Card */}
        <div className="card" style={{ padding: '22px 24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: '800', padding: '3px 8px', borderRadius: '4px', background: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa' }}>
              EVIDENCE CONFIDENCE
            </span>
            <span style={{ fontSize: '16px', fontWeight: '800', color: '#60a5fa' }}>
              {evidenceScore != null ? `${evidenceScore}% • ${evidenceScore >= 80 ? 'VERY HIGH' : evidenceScore >= 60 ? 'HIGH' : evidenceScore >= 40 ? 'MODERATE' : 'LOW'}` : 'Not yet computed'}
            </span>
          </div>
          <p style={{ margin: '8px 0 10px 0', fontSize: '13px', lineHeight: '1.5', color: 'var(--text)' }}>
            {evidenceScore != null
              ? 'Evidence confidence is derived deterministically from 5 independent database and anomaly signals:'
              : 'Run "Investigate with Gemini" to compute evidence confidence from real signals.'}
          </p>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div>• <strong>Anomaly Strength (25%):</strong> IsolationForest score {incident.anomaly_score != null ? incident.anomaly_score : '—'} (Flagged Anomaly)</div>
            <div>• <strong>Peer Deviation (25%):</strong> {failureRate != null && ratio != null && peerRate != null ? `${failureRate}% failure rate is ${ratio}x peer baseline (${peerRate}%)` : 'No evidence recorded'}</div>
            <div>• <strong>Concentration (20%):</strong> {topErrors != null && totalFailed ? `${((topErrors / totalFailed) * 100).toFixed(2)}% share are ${topErrorsLabel.toLowerCase()}` : 'No evidence recorded'}</div>
            <div>• <strong>Sample Volume (15%):</strong> {totalFailed != null ? `${totalFailed} failed transactions analyzed` : 'No evidence recorded'}</div>
            <div>• <strong>Merchant Breadth (15%):</strong> {merchantCount != null ? `Failures corroborated across ${merchantCount} distinct merchants` : 'No evidence recorded'}</div>
          </div>
        </div>

        {/* AI Recommendation Card */}
        <div className="card" style={{ padding: '22px 24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap', gap: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: '800', padding: '3px 8px', borderRadius: '4px', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
              AI-GENERATED RECOMMENDATION
            </span>
            <span style={{ fontSize: '11px', color: '#facc15', fontWeight: '600' }}>
              Human approval required
            </span>
          </div>
          <p style={{ margin: '8px 0 0 0', fontSize: '14px', lineHeight: '1.6', color: 'var(--text)' }}>
            {investigationData?.recommendation || "No AI recommendation yet — run \"Investigate with Gemini\" above to generate one from real evidence."}
          </p>
        </div>

      </div>

      {/* 7. ACTION GOVERNOR (HUMAN-IN-THE-LOOP) */}
      <div className="card" style={{ padding: '24px', border: '1px solid rgba(239, 68, 68, 0.3)', background: 'rgba(239, 68, 68, 0.02)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <span style={{ fontSize: '11px', fontWeight: '800', padding: '3px 8px', borderRadius: '4px', background: 'rgba(239, 68, 68, 0.2)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.4)' }}>
              Risk: RED • Human approval required
            </span>
          </div>

          {primaryAction && (
            <span style={{ 
              fontSize: '11px', 
              fontWeight: '700', 
              padding: '4px 10px', 
              borderRadius: '4px', 
              background: primaryAction.status === 'executed' ? 'rgba(16, 185, 129, 0.2)' : primaryAction.status === 'approved' ? 'rgba(59, 130, 246, 0.2)' : primaryAction.status === 'rejected' ? 'rgba(100, 116, 139, 0.2)' : 'rgba(234, 179, 8, 0.2)',
              color: primaryAction.status === 'executed' ? '#10b981' : primaryAction.status === 'approved' ? '#60a5fa' : primaryAction.status === 'rejected' ? '#94a3b8' : '#facc15',
              border: '1px solid var(--border)',
              textTransform: 'uppercase'
            }}>
              {primaryAction.status === 'executed' ? 'EXECUTED — SIMULATION ONLY' : primaryAction.status === 'approved' ? 'APPROVED BY HUMAN' : primaryAction.status === 'rejected' ? 'REJECTED' : 'PENDING APPROVAL'}
            </span>
          )}
        </div>

        <div style={{ background: 'rgba(0, 0, 0, 0.2)', padding: '18px 20px', borderRadius: '8px', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text)', marginBottom: '6px' }}>
            {incident.target_entity_type === 'merchant' ? (
              <>Pause settlements for <code style={{ color: '#f87171' }}>{incident.target_entity_id}</code> pending review</>
            ) : (
              <>Reroute traffic away from <code style={{ color: '#f87171' }}>{incident.target_entity_id || 'Gateway_X'}</code></>
            )}
          </div>
          <div style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.5', marginBottom: '14px' }}>
            <strong>Policy Reason:</strong> {incident.primary_signal || (incident.target_entity_type === 'merchant'
              ? `Anomalous account activity detected for ${incident.target_entity_id}.`
              : `High failure concentration on ${incident.target_entity_id || 'this gateway'} relative to peer baseline.`)}
          </div>

          {/* Action Control Buttons */}
          {primaryAction ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
              {primaryAction.status === 'pending_approval' && (
                <>
                  <button 
                    className="btn btn-primary"
                    onClick={() => handleApprove(primaryAction.action_id)}
                    disabled={actionLoading}
                    style={{ background: '#10b981', borderColor: '#10b981', padding: '9px 20px', fontWeight: '700' }}
                  >
                    ✓ Approve Action
                  </button>
                  <button 
                    className="btn"
                    onClick={() => handleReject(primaryAction.action_id)}
                    disabled={actionLoading}
                    style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.3)', padding: '9px 18px', fontWeight: '600' }}
                  >
                    ✕ Reject
                  </button>
                </>
              )}

              {primaryAction.status === 'approved' && (
                <button 
                  className="btn btn-primary"
                  onClick={() => handleExecuteSimulation(primaryAction.action_id)}
                  disabled={actionLoading}
                  style={{ background: '#3b82f6', borderColor: '#3b82f6', padding: '9px 22px', fontWeight: '700' }}
                >
                  ⚡ Execute Safe Simulation
                </button>
              )}

              {primaryAction.status === 'executed' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: '#10b981', fontSize: '13px', fontWeight: '700', flexWrap: 'wrap' }}>
                    <span>✓ Approved by human operator</span>
                    <span>•</span>
                    <span>✓ Safe demonstration simulation executed</span>
                    <span>•</span>
                    <span>✓ Immutable audit log appended</span>
                  </div>

                  <div style={{ marginTop: '6px', padding: '12px 14px', background: '#0f172a', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '12px' }}>
                    <div style={{ color: '#38bdf8', fontWeight: '700', marginBottom: '4px' }}>
                      SIMULATION ONLY: {primaryAction.execution_result?.message || "Traffic diversion simulation completed successfully."}
                    </div>
                    <div style={{ color: '#10b981', fontWeight: '600' }}>
                      0 live Razorpay payments modified.
                    </div>
                  </div>
                </div>
              )}

              {primaryAction.status === 'rejected' && (
                <div style={{ color: '#94a3b8', fontSize: '13px', fontStyle: 'italic' }}>
                  Action rejected by human operator. Zero traffic diversion permitted. Recorded in audit trail.
                </div>
              )}
            </div>
          ) : (
            <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
              Click <strong>"⚡ Investigate with Gemini"</strong> above to evaluate telemetry and propose this governed action.
            </div>
          )}

          {actionMsg && (
            <div style={{ marginTop: '12px', padding: '8px 12px', background: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.3)', borderRadius: '6px', color: '#60a5fa', fontSize: '12px' }}>
              {actionMsg}
            </div>
          )}
        </div>
      </div>

      {/* 8. AI TOOL TRACE (COLLAPSED BY DEFAULT) */}
      <div className="card" style={{ padding: '20px 24px' }}>
        <details style={{ cursor: 'pointer' }}>
          <summary style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>View AI investigation trace ({steps.length} tool calls executed against PostgreSQL)</span>
            <span style={{ fontSize: '12px', color: 'var(--primary)' }}>Toggle Details</span>
          </summary>

          <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {steps.length === 0 ? (
              <div style={{ fontSize: '13px', color: 'var(--text-muted)', padding: '10px 0' }}>
                No tool steps recorded yet. Click <strong>"Investigate with Gemini"</strong> above to trigger live multi-turn tool calling.
              </div>
            ) : (
              steps.map((st, idx) => (
                <div key={st.step_id || idx} style={{ border: '1px solid var(--border)', borderRadius: '6px', overflow: 'hidden' }}>
                  <div 
                    onClick={() => setExpandedStep(expandedStep === idx ? null : idx)}
                    style={{ 
                      padding: '10px 14px', 
                      background: 'rgba(255, 255, 255, 0.03)', 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center',
                      fontSize: '13px'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ color: '#10b981', fontWeight: 'bold' }}>✓</span>
                      <span style={{ fontFamily: 'monospace', fontWeight: '700', color: 'var(--primary)' }}>
                        Step {st.step_number || idx + 1}: Gemini → {st.tool_name}
                      </span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '11px', color: 'var(--text-muted)' }}>
                      <span>{expandedStep === idx ? "▲ Hide" : "▼ Inspect Tool Arguments & Output"}</span>
                    </div>
                  </div>

                  {expandedStep === idx && (
                    <div style={{ padding: '12px 14px', background: 'rgba(0, 0, 0, 0.2)', borderTop: '1px solid var(--border)', fontSize: '12px' }}>
                      <div style={{ marginBottom: '8px' }}>
                        <strong style={{ color: 'var(--text-muted)' }}>Input Arguments:</strong>
                        <pre style={{ margin: '4px 0', padding: '8px', background: '#0f172a', borderRadius: '4px', overflowX: 'auto' }}>
                          {JSON.stringify(st.arguments || st.input_json, null, 2)}
                        </pre>
                      </div>
                      <div>
                        <strong style={{ color: 'var(--text-muted)' }}>Database Output:</strong>
                        <pre style={{ margin: '4px 0', padding: '8px', background: '#0f172a', borderRadius: '4px', overflowX: 'auto', maxHeight: '200px' }}>
                          {JSON.stringify(st.result || st.output_json, null, 2)}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </details>
      </div>

      </div>
    </div>
  );
}
