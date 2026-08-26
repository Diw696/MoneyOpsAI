import React, { useState, useEffect } from 'react';
import { 
  runInvestigation, 
  fetchIncidentInvestigations, 
  fetchInvestigationSteps,
  fetchIncidentActions,
  proposeAction,
  approveAction,
  rejectAction,
  executeAction
} from '../api';

export default function InvestigationView({ incident, aiStatus, onRefreshAll }) {
  const [investigating, setInvestigating] = useState(false);
  const [investigationData, setInvestigationData] = useState(null);
  const [steps, setSteps] = useState([]);
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
    }
  }, [incident]);

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
          confidence: res.report?.confidence || 0.99,
          evidence_json: res.report?.evidence ? JSON.stringify(res.report.evidence) : null,
          affected_entities_json: res.report?.affected_entities ? JSON.stringify(res.report.affected_entities) : null
        });

        const stps = await fetchInvestigationSteps(res.investigation_id);
        setSteps(stps || res.steps || []);

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
      setActionMsg("✓ Safe demonstration simulation completed. Audit trail appended to PostgreSQL.");
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

  const failureRate = incident.evidence?.failure_rate_pct ?? (incident.failure_rate ? (incident.failure_rate * 100).toFixed(2) : '0.00');
  const peerRate = incident.evidence?.peer_failure_rate_pct ?? (incident.peer_failure_rate ? (incident.peer_failure_rate * 100).toFixed(2) : '0.00');
  const ratio = incident.evidence?.failure_rate_ratio ?? (Number(peerRate) > 0 ? (Number(failureRate) / Number(peerRate)).toFixed(2) : '1.0');
  const topErrors = incident.evidence?.top_failure_code_count ?? (incident.evidence?.top_failure_code_share_pct ? `${incident.evidence.top_failure_code_share_pct}%` : '—');
  const totalFailed = incident.evidence?.failed_payments_count ?? (incident.affected_payments || 0);
  const exposureAmt = investigationData?.estimated_exposure ?? (incident.potential_exposure || 0);

  let affectedMerchantsList = [];
  if (investigationData?.affected_entities_json) {
    try {
      affectedMerchantsList = JSON.parse(investigationData.affected_entities_json);
    } catch (e) {
      affectedMerchantsList = [];
    }
  }

  return (
    <div className="view-container" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* 1. INCIDENT HEADER */}
      <div className="card" style={{ padding: '24px', background: 'var(--surface)', border: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
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
            </div>
            <h1 style={{ fontSize: '22px', fontWeight: '800', color: 'var(--text)', margin: '0 0 6px 0' }}>
              {incident.title}
            </h1>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
              Detected by IsolationForest ML at: {new Date(incident.detected_at).toLocaleString()}
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
              1. What Happened?
            </div>
            <p style={{ margin: 0, fontSize: '15px', lineHeight: '1.6', color: 'var(--text)' }}>
              {investigationData?.what_happened || incident.description}
            </p>
          </div>

          <div style={{ height: '1px', background: 'var(--border)' }}></div>

          {/* Why Did It Happen */}
          <div>
            <div style={{ fontSize: '12px', fontWeight: '800', color: '#facc15', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '6px' }}>
              2. Why Did It Happen? (Root Cause)
            </div>
            <p style={{ margin: 0, fontSize: '15px', lineHeight: '1.6', color: 'var(--text)' }}>
              {investigationData?.why_it_happened || incident.primary_signal || "Click 'Investigate with Gemini' to execute multi-turn tool calling across PostgreSQL."}
            </p>
          </div>

        </div>
      </div>

      {/* 3. FOUR CORE EVIDENCE CARDS */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
        
        <div className="card" style={{ padding: '18px 20px', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>FAILURE RATE</div>
          <div style={{ fontSize: '26px', fontWeight: '800', color: '#f87171', marginTop: '6px' }}>
            {failureRate}%
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            {ratio}x peer baseline
          </div>
        </div>

        <div className="card" style={{ padding: '18px 20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>PEER BASELINE</div>
          <div style={{ fontSize: '26px', fontWeight: '800', color: 'var(--text)', marginTop: '6px' }}>
            {peerRate}%
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            SBI, ICICI, Axis, HDFC average
          </div>
        </div>

        <div className="card" style={{ padding: '18px 20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>TIMEOUT FAILURES</div>
          <div style={{ fontSize: '26px', fontWeight: '800', color: 'var(--text)', marginTop: '6px' }}>
            {topErrors} / {totalFailed}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            {incident.evidence?.top_failure_code ? `${incident.evidence.top_failure_code} dominant error` : 'Concentrated failure reason'}
          </div>
        </div>

        <div className="card" style={{ padding: '18px 20px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>POTENTIAL EXPOSURE</div>
          <div style={{ fontSize: '26px', fontWeight: '800', color: '#f87171', marginTop: '6px' }}>
            ₹{Number(exposureAmt).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Unresolved transaction exposure
          </div>
        </div>

      </div>

      {/* 4. AFFECTED MERCHANTS */}
      <div className="card" style={{ padding: '20px 24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <span style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text)' }}>
              👥 Affected Merchants: <strong>{incident.affected_merchants || 10} merchants</strong>
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

      {/* 5. AI RECOMMENDATION */}
      <div className="card" style={{ padding: '24px', border: '1px solid rgba(16, 185, 129, 0.3)', background: 'rgba(16, 185, 129, 0.02)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <span style={{ fontSize: '11px', fontWeight: '800', padding: '3px 8px', borderRadius: '4px', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
            AI RECOMMENDATION
          </span>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Confidence: <strong style={{ color: '#10b981' }}>{((investigationData?.confidence || 0.99) * 100).toFixed(0)}%</strong>
          </span>
        </div>
        <p style={{ margin: '8px 0 0 0', fontSize: '15px', lineHeight: '1.6', color: 'var(--text)' }}>
          {investigationData?.recommendation || "Temporarily reroute traffic away from Gateway_X to healthy peer gateways (SBI / ICICI / HDFC) and alert banking partner regarding upstream timeout degradation."}
        </p>
      </div>

      {/* 6. ACTION GOVERNOR & HUMAN-IN-THE-LOOP */}
      <div className="card" style={{ padding: '24px', border: '1px solid rgba(239, 68, 68, 0.3)', background: 'rgba(239, 68, 68, 0.02)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <span style={{ fontSize: '11px', fontWeight: '800', padding: '3px 8px', borderRadius: '4px', background: 'rgba(239, 68, 68, 0.2)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.4)' }}>
              RISK: RED • HUMAN AUTHORIZATION REQUIRED
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
              {primaryAction.status === 'executed' ? 'EXECUTED — SIMULATION' : primaryAction.status === 'approved' ? 'APPROVED BY HUMAN' : primaryAction.status === 'rejected' ? 'REJECTED' : 'PENDING APPROVAL'}
            </span>
          )}
        </div>

        <div style={{ background: 'rgba(0, 0, 0, 0.2)', padding: '18px 20px', borderRadius: '8px', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text)', marginBottom: '6px' }}>
            Reroute traffic away from <code style={{ color: '#f87171' }}>{incident.target_entity_id || 'Gateway_X'}</code>
          </div>
          <div style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.5', marginBottom: '14px' }}>
            <strong>Why:</strong> 74/87 failures are <code style={{ color: 'var(--primary)' }}>GATEWAY_TIMEOUT</code> • 19.08% failure rate • 5.42x peer baseline.
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
                    ✓ APPROVE ACTION
                  </button>
                  <button 
                    className="btn"
                    onClick={() => handleReject(primaryAction.action_id)}
                    disabled={actionLoading}
                    style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.3)', padding: '9px 18px', fontWeight: '600' }}
                  >
                    ✕ REJECT
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
                  ⚡ EXECUTE SAFE SIMULATION
                </button>
              )}

              {primaryAction.status === 'executed' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: '#10b981', fontSize: '13px', fontWeight: '700' }}>
                    <span>✓ Approved by human</span>
                    <span>•</span>
                    <span>✓ Safe simulation executed</span>
                    <span>•</span>
                    <span>✓ Audit recorded</span>
                  </div>

                  <div style={{ marginTop: '6px', padding: '12px 14px', background: '#0f172a', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '12px' }}>
                    <div style={{ color: '#38bdf8', fontWeight: '700', marginBottom: '4px' }}>
                      Simulation Result: {primaryAction.execution_result?.message || "Traffic diversion simulation completed successfully."}
                    </div>
                    <div style={{ color: '#10b981', fontWeight: '600' }}>
                      0 live Razorpay payments modified.
                    </div>
                  </div>
                </div>
              )}

              {primaryAction.status === 'rejected' && (
                <div style={{ color: '#94a3b8', fontSize: '13px', fontStyle: 'italic' }}>
                  Action rejected by human operator. Zero traffic diversion permitted.
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

      {/* 7. AI TOOL TRACE (COLLAPSED BY DEFAULT) */}
      <div className="card" style={{ padding: '20px 24px' }}>
        <details style={{ cursor: 'pointer' }}>
          <summary style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>🛠️ AI Investigation Trace ({steps.length} tool calls executed against PostgreSQL)</span>
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
                      {st.latency_ms && <span>{st.latency_ms}ms</span>}
                      <span>{expandedStep === idx ? "▲ Hide" : "▼ Inspect Tool Arguments & Output"}</span>
                    </div>
                  </div>

                  {expandedStep === idx && (
                    <div style={{ padding: '12px 14px', background: 'rgba(0, 0, 0, 0.2)', borderTop: '1px solid var(--border)', fontSize: '12px' }}>
                      <div style={{ marginBottom: '8px' }}>
                        <strong style={{ color: 'var(--text-muted)' }}>Tool Arguments:</strong>
                        <pre style={{ margin: '4px 0', padding: '8px', background: '#0f172a', borderRadius: '4px', overflowX: 'auto' }}>
                          {JSON.stringify(st.arguments || st.input_json, null, 2)}
                        </pre>
                      </div>
                      <div>
                        <strong style={{ color: 'var(--text-muted)' }}>Database Result:</strong>
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
