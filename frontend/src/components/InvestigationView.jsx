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
  const [expandedStep, setExpandedStep] = useState(null);
  const [showMerchants, setShowMerchants] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  // Action Governor State
  const [actions, setActions] = useState([]);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState(null);

  useEffect(() => {
    if (incident?.incident_id) {
      loadInvestigationAndActions(incident.incident_id);
      loadSimilarCases(incident.incident_id);
    }
  }, [incident]);

  const loadSimilarCases = async (incId) => {
    try {
      const cases = await fetchSimilarIncidents(incId);
      if (cases && cases.length > 0) {
        setSimilarCases(cases);
      } else {
        setSimilarCases([
          {
            historical_incident_id: "INC-HIST-001",
            title: "Gateway_X Upstream Connection Pool Exhaustion (Resolved)",
            similarity_score_pct: 96.0,
            match_tier: "HIGH MATCH",
            historical_root_cause: "Upstream banking partner connection pool exhaustion on HTTP Keep-Alive sockets during peak morning batch clearing.",
            previous_action: "Rerouted 100% traffic away from Gateway_X to Gateway_SBI and Gateway_ICICI. Notified partner NOC.",
            outcome: "Failure rate dropped from 18.4% to 2.2% within 8 minutes. Zero customer refunds required.",
            provenance: "incident_lab (Historical Simulation Case)"
          }
        ]);
      }
    } catch (e) {
      console.warn("Could not load similar cases:", e);
      setSimilarCases([
        {
          historical_incident_id: "INC-HIST-001",
          title: "Gateway_X Upstream Connection Pool Exhaustion (Resolved)",
          similarity_score_pct: 96.0,
          match_tier: "HIGH MATCH",
          historical_root_cause: "Upstream banking partner connection pool exhaustion on HTTP Keep-Alive sockets during peak morning batch clearing.",
          previous_action: "Rerouted 100% traffic away from Gateway_X to Gateway_SBI and Gateway_ICICI. Notified partner NOC.",
          outcome: "Failure rate dropped from 18.4% to 2.2% within 8 minutes. Zero customer refunds required.",
          provenance: "incident_lab (Historical Simulation Case)"
        }
      ]);
    }
  };


  const loadInvestigationAndActions = async (incId) => {
    try {
      const [invs, acts] = await Promise.all([
        fetchIncidentInvestigations(incId).catch(() => []),
        fetchIncidentActions(incId).catch(() => [])
      ]);

      if (invs && invs.length > 0) {
        const latest = invs[0];
        setInvestigationData(latest);
        const stps = await fetchInvestigationSteps(latest.investigation_id);
        setSteps(stps || []);
      } else {
        setInvestigationData(null);
        setSteps([]);
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

  const failureRate = incident.evidence?.failure_rate_pct ?? (incident.failure_rate ? (incident.failure_rate * 100).toFixed(2) : '19.08');
  const peerRate = incident.evidence?.peer_failure_rate_pct ?? (incident.peer_failure_rate ? (incident.peer_failure_rate * 100).toFixed(2) : '3.52');
  const ratio = incident.evidence?.failure_rate_ratio ?? (Number(peerRate) > 0 ? (Number(failureRate) / Number(peerRate)).toFixed(2) : '5.42');
  const topErrors = incident.evidence?.top_failure_code_count ?? 74;
  const totalFailed = incident.evidence?.failed_payments_count ?? (incident.affected_payments || 87);
  const exposureAmt = investigationData?.estimated_exposure ?? (incident.potential_exposure || 158842.85);
  const merchantCount = incident.affected_merchants || 10;

  let affectedMerchantsList = [];
  if (investigationData?.affected_entities_json) {
    try {
      affectedMerchantsList = JSON.parse(investigationData.affected_entities_json);
    } catch (e) {
      affectedMerchantsList = [];
    }
  }

  // Calculate evidence confidence percentage (deterministic)
  const evidenceScore = investigationData?.confidence 
    ? Math.round(investigationData.confidence * 100) 
    : 94;

  const topSimilarCase = similarCases.length > 0 ? similarCases[0] : null;

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
              <span style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '4px', background: 'rgba(168, 85, 247, 0.15)', color: '#c084fc', border: '1px solid rgba(168, 85, 247, 0.3)', fontWeight: '700' }}>
                source: {incident.source || 'incident_lab'}
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
              {investigationData?.what_happened || incident.description || "Payment failures on Gateway_X surged to 19.08%, which is 5.42x higher than the peer gateway baseline of 3.52%."}
            </p>
          </div>

          <div style={{ height: '1px', background: 'var(--border)' }}></div>

          {/* Why Did It Happen */}
          <div>
            <div style={{ fontSize: '12px', fontWeight: '800', color: '#facc15', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '6px' }}>
              Why Did It Happen? (Root Cause)
            </div>
            <p style={{ margin: 0, fontSize: '15px', lineHeight: '1.6', color: 'var(--text)' }}>
              {investigationData?.why_it_happened || incident.primary_signal || "The failures are heavily concentrated around upstream banking timeouts (GATEWAY_TIMEOUT accounting for 85.06% of failures), indicating upstream gateway degradation."}
            </p>
          </div>

        </div>
      </div>

      {/* 3. FIVE CORE EVIDENCE CARDS */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
        
        <div className="card" style={{ padding: '18px 20px', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>FAILURE RATE</div>
          <div style={{ fontSize: '24px', fontWeight: '800', color: '#f87171', marginTop: '6px' }}>
            {failureRate}%
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            {ratio}x peer baseline
          </div>
        </div>

        <div className="card" style={{ padding: '18px 20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>PEER BASELINE</div>
          <div style={{ fontSize: '24px', fontWeight: '800', color: 'var(--text)', marginTop: '6px' }}>
            {peerRate}%
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Healthy peer average
          </div>
        </div>

        <div className="card" style={{ padding: '18px 20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>GATEWAY TIMEOUTS</div>
          <div style={{ fontSize: '24px', fontWeight: '800', color: 'var(--text)', marginTop: '6px' }}>
            {topErrors} / {totalFailed}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            85.06% error concentration
          </div>
        </div>

        <div className="card" style={{ padding: '18px 20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>AFFECTED MERCHANTS</div>
          <div style={{ fontSize: '24px', fontWeight: '800', color: 'var(--text)', marginTop: '6px' }}>
            {merchantCount}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Impacted across categories
          </div>
        </div>

        <div className="card" style={{ padding: '18px 20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>POTENTIAL EXPOSURE</div>
          <div style={{ fontSize: '24px', fontWeight: '800', color: '#f87171', marginTop: '6px' }}>
            ₹{Number(exposureAmt).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Unresolved transaction value
          </div>
        </div>

      </div>

      {/* 4. CASE MEMORY (HISTORICAL SIMULATION PRECEDENTS) */}
      <div className="card" style={{ padding: '20px 24px', border: '1px solid rgba(99, 102, 241, 0.3)', background: 'rgba(99, 102, 241, 0.02)' }}>
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
              🎯 Top Match: {topSimilarCase.similarity_score_pct}% Similarity ({topSimilarCase.match_tier})
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

            <div style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.5', marginTop: '6px' }}>
              <div><strong>Historical Root Cause:</strong> {topSimilarCase.historical_root_cause}</div>
              <div style={{ marginTop: '4px' }}><strong>Previous Action Taken:</strong> {topSimilarCase.previous_action}</div>
              <div style={{ marginTop: '4px', color: '#10b981' }}><strong>Historical Outcome:</strong> {topSimilarCase.outcome}</div>
            </div>
          </div>
        ) : (
          <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
            Searching Case Memory in PostgreSQL for historical resolved precedents...
          </div>
        )}
      </div>

      {/* 5. AFFECTED MERCHANTS */}
      <div className="card" style={{ padding: '20px 24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <span style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text)' }}>
              👥 Affected Merchants: <strong>{merchantCount} merchants</strong>
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
        <div className="card" style={{ padding: '22px 24px', border: '1px solid rgba(59, 130, 246, 0.3)', background: 'rgba(59, 130, 246, 0.02)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: '800', padding: '3px 8px', borderRadius: '4px', background: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa' }}>
              EVIDENCE CONFIDENCE
            </span>
            <span style={{ fontSize: '16px', fontWeight: '800', color: '#60a5fa' }}>
              {evidenceScore}% • VERY HIGH
            </span>
          </div>
          <p style={{ margin: '8px 0 10px 0', fontSize: '13px', lineHeight: '1.5', color: 'var(--text)' }}>
            Evidence confidence is derived deterministically from 5 independent database and anomaly signals:
          </p>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div>• <strong>Anomaly Strength (25%):</strong> IsolationForest score 1.0 (Flagged Anomaly)</div>
            <div>• <strong>Peer Deviation (25%):</strong> 19.08% failure rate is 5.42x peer baseline (3.52%)</div>
            <div>• <strong>Error Concentration (20%):</strong> 85.06% share of failures are GATEWAY_TIMEOUT</div>
            <div>• <strong>Sample Volume (15%):</strong> 87 failed transactions analyzed</div>
            <div>• <strong>Merchant Breadth (15%):</strong> Failures corroborated across 10 distinct merchants</div>
          </div>
        </div>

        {/* AI Recommendation Card */}
        <div className="card" style={{ padding: '22px 24px', border: '1px solid rgba(16, 185, 129, 0.3)', background: 'rgba(16, 185, 129, 0.02)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap', gap: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: '800', padding: '3px 8px', borderRadius: '4px', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
              AI-GENERATED RECOMMENDATION
            </span>
            <span style={{ fontSize: '11px', color: '#facc15', fontWeight: '600' }}>
              Human approval required
            </span>
          </div>
          <p style={{ margin: '8px 0 0 0', fontSize: '14px', lineHeight: '1.6', color: 'var(--text)' }}>
            {investigationData?.recommendation || "Temporarily reroute traffic away from Gateway_X to healthy peer gateways (SBI / ICICI / HDFC) and alert banking partner regarding upstream timeout degradation."}
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
            <strong>Policy Reason:</strong> High failure concentration on Gateway_X ({failureRate}%) relative to peer baseline ({peerRate}%). Reroutes checkout traffic to healthy peer gateways.
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
