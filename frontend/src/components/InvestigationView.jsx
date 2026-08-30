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

export default function InvestigationView({ incident, aiStatus, onRefreshAll }) {
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

        // Auto-propose governed action if none exists
        try {
          await proposeAction({
            incident_id: incident.incident_id,
            investigation_id: res.investigation_id,
            action_type: "reroute_gateway_traffic",
            target_entity: incident.target_entity_id || "Gateway_X",
            reason: res.report?.recommendation || "Reroute traffic away from degraded banking node to backup partner nodes.",
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
    } catch (e) {
      setActionMsg(`Execution failed: ${e.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  if (!incident) {
    return (
      <div className="card" style={{ padding: '60px 24px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <div style={{ fontSize: '32px', marginBottom: '12px' }}>🔍</div>
        <h3 style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text)', margin: '0 0 8px 0' }}>No Active Incident Selected</h3>
        <p style={{ fontSize: '13px', margin: 0 }}>Select an incident from the Overview tab to view forensic telemetry and investigate.</p>
      </div>
    );
  }

  const isGeminiConnected = aiStatus?.configured;
  const primaryAction = actions.length > 0 ? actions[0] : null;

  const failureRate = incident.evidence?.failure_rate_pct ?? (incident.failure_rate ? (incident.failure_rate * 100).toFixed(2) : null);
  const peerRate = incident.evidence?.peer_failure_rate_pct ?? (incident.peer_failure_rate ? (incident.peer_failure_rate * 100).toFixed(2) : null);
  const ratio = incident.evidence?.failure_rate_ratio ?? (peerRate && Number(peerRate) > 0 && failureRate ? (Number(failureRate) / Number(peerRate)).toFixed(2) : null);
  const topErrors = incident.evidence?.top_failure_code_count ?? null;
  const totalFailed = incident.evidence?.failed_payments_count ?? (incident.affected_payments || null);
  const exposureAmt = investigationData?.estimated_exposure ?? (incident.potential_exposure || null);
  const merchantCount = incident.affected_merchants || null;

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
    if (primaryAction.status === 'rejected') return { label: 'Action rejected by operator', color: '#94a3b8', bg: 'rgba(148, 163, 184, 0.12)' };
    return { label: 'Investigated', color: '#34d399', bg: 'rgba(52, 211, 153, 0.12)' };
  })();

  return (
    <div className="view-container" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
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
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
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
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
        
        <div className="card" style={{ padding: '18px 20px', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>FAILURE RATE</div>
          <div style={{ fontSize: '24px', fontWeight: '800', color: '#f87171', marginTop: '6px' }}>
            {failureRate != null ? `${failureRate}%` : '—'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            {ratio != null ? `${ratio}x peer baseline` : 'No evidence recorded'}
          </div>
        </div>

        <div className="card" style={{ padding: '18px 20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>PEER BASELINE</div>
          <div style={{ fontSize: '24px', fontWeight: '800', color: 'var(--text)', marginTop: '6px' }}>
            {peerRate != null ? `${peerRate}%` : '—'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Healthy peer average
          </div>
        </div>

        <div className="card" style={{ padding: '18px 20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>GATEWAY TIMEOUTS</div>
          <div style={{ fontSize: '24px', fontWeight: '800', color: 'var(--text)', marginTop: '6px' }}>
            {topErrors != null && totalFailed != null ? `${topErrors} / ${totalFailed}` : '—'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            {topErrors != null && totalFailed ? `${((topErrors / totalFailed) * 100).toFixed(2)}% error concentration` : 'No evidence recorded'}
          </div>
        </div>

        <div className="card" style={{ padding: '18px 20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>AFFECTED MERCHANTS</div>
          <div style={{ fontSize: '24px', fontWeight: '800', color: 'var(--text)', marginTop: '6px' }}>
            {merchantCount != null ? merchantCount : '—'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Impacted across categories
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

      {/* 5. AFFECTED MERCHANTS */}
      <div className="card" style={{ padding: '20px 24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <span style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text)' }}>
              👥 Affected Merchants: <strong>{merchantCount != null ? `${merchantCount} merchants` : 'No evidence recorded'}</strong>
            </span>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)', marginLeft: '12px' }}>
              Impacted across SaaS, Gaming, Travel, and Quick Commerce
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
                Top impacted merchants: PayPulse Gaming, CloudScale SaaS, Nova Store, Apex Logistics, ZenTravels, QuickDrop, StreamWave, NeoPay, ByteBazaar, LuxeLiving.
              </div>
            )}
          </div>
        )}
      </div>

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
            <div>• <strong>Error Concentration (20%):</strong> {topErrors != null && totalFailed ? `${((topErrors / totalFailed) * 100).toFixed(2)}% share of failures are GATEWAY_TIMEOUT` : 'No evidence recorded'}</div>
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
            Reroute traffic away from <code style={{ color: '#f87171' }}>{incident.target_entity_id || 'Gateway_X'}</code>
          </div>
          <div style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.5', marginBottom: '14px' }}>
            <strong>Policy Reason:</strong> High failure concentration on {incident.target_entity_id || 'this gateway'} ({failureRate != null ? `${failureRate}%` : 'no evidence'}) relative to peer baseline ({peerRate != null ? `${peerRate}%` : 'no evidence'}). Reroutes checkout traffic to healthy peer gateways.
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
  );
}
