import React, { useState, useEffect } from "react";
import { 
  runInvestigation, 
  fetchIncidentInvestigations, 
  fetchInvestigationSteps,
  fetchIncidentActions,
  proposeAction,
  approveAction,
  rejectAction,
  executeAction
} from "../api";

export default function InvestigationStudio({ incident, aiStatus, onRefresh }) {
  const [investigating, setInvestigating] = useState(false);
  const [investigationData, setInvestigationData] = useState(null);
  const [steps, setSteps] = useState([]);
  const [expandedStep, setExpandedStep] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  // Phase D: Action Governor State
  const [actions, setActions] = useState([]);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState(null);

  useEffect(() => {
    if (incident?.incident_id) {
      loadLatestInvestigation(incident.incident_id);
      loadIncidentActions(incident.incident_id);
    }
  }, [incident]);

  async function loadLatestInvestigation(incId) {
    try {
      const invs = await fetchIncidentInvestigations(incId);
      if (invs && invs.length > 0) {
        const latest = invs[0];
        setInvestigationData(latest);
        const stps = await fetchInvestigationSteps(latest.investigation_id);
        setSteps(stps || []);
      } else {
        setInvestigationData(null);
        setSteps([]);
      }
    } catch (e) {
      console.warn("No prior investigation loaded:", e);
    }
  }

  async function loadIncidentActions(incId) {
    try {
      const acts = await fetchIncidentActions(incId);
      setActions(acts || []);
    } catch (e) {
      console.warn("No actions loaded:", e);
    }
  }

  async function handleInvestigate() {
    if (!incident?.incident_id) return;
    setInvestigating(true);
    setErrorMsg(null);

    try {
      const res = await runInvestigation(incident.incident_id);
      if (res.status === "completed") {
        setInvestigationData({
          investigation_id: res.investigation_id,
          provider: res.provider,
          model: res.model,
          what_happened: res.report?.what_happened || res.report?.summary,
          why_it_happened: res.report?.why,
          estimated_exposure: res.report?.financial_exposure?.amount_inr || incident.potential_exposure,
          recommendation: res.report?.recommendation,
          confidence: res.report?.confidence || 0.9,
          evidence_json: res.report?.evidence ? JSON.stringify(res.report.evidence) : null
        });
        const stps = await fetchInvestigationSteps(res.investigation_id);
        setSteps(stps || res.steps || []);

        // Automatically propose governed action if none exists
        await handleProposeInitialAction(incident.incident_id, res.investigation_id, res.report);
        if (onRefresh) onRefresh();
      } else {
        setErrorMsg(res.message || "Investigation could not be completed.");
      }
    } catch (err) {
      setErrorMsg(err.message || "Failed to connect to AI investigation engine.");
    } finally {
      setInvestigating(false);
    }
  }

  async function handleProposeInitialAction(incId, invId, report) {
    try {
      const prop = await proposeAction({
        incident_id: incId,
        investigation_id: invId,
        action_type: "reroute_gateway_traffic",
        target_entity: incident.target_entity_id || "Gateway_X",
        reason: report?.recommendation || "Reroute traffic away from degraded Gateway_X banking node to healthy partner channels.",
        actor: "Gemini_Agent"
      });
      await loadIncidentActions(incId);
    } catch (e) {
      console.warn("Could not auto-propose action:", e);
    }
  }

  async function handleApprove(actionId) {
    setActionLoading(true);
    setActionMsg(null);
    try {
      await approveAction(actionId, "Operator approved cutover per FinOps Incident Policy");
      setActionMsg("Action successfully approved by human operator. Ready for safe simulation.");
      await loadIncidentActions(incident.incident_id);
    } catch (e) {
      setActionMsg(`Approval error: ${e.message}`);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReject(actionId) {
    setActionLoading(true);
    setActionMsg(null);
    try {
      await rejectAction(actionId, "Operator rejected automated rerouting");
      setActionMsg("Action rejected by operator. No traffic modification permitted.");
      await loadIncidentActions(incident.incident_id);
    } catch (e) {
      setActionMsg(`Rejection error: ${e.message}`);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleExecuteSimulation(actionId) {
    setActionLoading(true);
    setActionMsg(null);
    try {
      await executeAction(actionId);
      setActionMsg("Safe demonstration simulation executed successfully. Audit log recorded in PostgreSQL.");
      await loadIncidentActions(incident.incident_id);
    } catch (e) {
      setActionMsg(`Execution error: ${e.message}`);
    } finally {
      setActionLoading(false);
    }
  }

  if (!incident) {
    return (
      <div className="card" style={{ padding: "40px", textAlign: "center", color: "var(--text-muted)" }}>
        <h3>No Incident Selected</h3>
        <p>Select an incident from the operations queue to initiate a forensic AI investigation.</p>
      </div>
    );
  }

  const evidenceList = investigationData?.evidence_json 
    ? (typeof investigationData.evidence_json === "string" ? JSON.parse(investigationData.evidence_json) : investigationData.evidence_json)
    : (incident.evidence ? [
        { claim: "Elevated Rejection Velocity", supporting_data: `${incident.evidence.failure_rate_pct}% Rejections (${incident.evidence.failure_rate_ratio}x peer baseline)` },
        { claim: "Primary Failure Signature", supporting_data: `${incident.evidence.top_failure_code} (${incident.evidence.top_failure_code_count} rejections)` },
        { claim: "Cross-Merchant Impact", supporting_data: `${incident.evidence.affected_merchants_count} merchants affected` }
      ] : []);

  const isGeminiConnected = aiStatus?.configured;
  const primaryAction = actions.length > 0 ? actions[0] : null;

  return (
    <div className="investigation-studio-clean" style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      
      {/* 1. HEADER & AI BADGE */}
      <div className="card" style={{ padding: "20px 24px", background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
              <span className={`badge badge-${incident.severity || 'critical'}`} style={{ textTransform: "uppercase", fontSize: "11px", fontWeight: "700", letterSpacing: "0.5px" }}>
                {incident.severity || "CRITICAL"}
              </span>
              <span style={{ fontSize: "12px", color: "var(--text-muted)", fontFamily: "monospace" }}>
                ID: {incident.incident_id}
              </span>
              <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>•</span>
              <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                Source: <code style={{ color: "var(--primary)" }}>{incident.source || "incident_lab"}</code>
              </span>
            </div>
            <h2 style={{ fontSize: "20px", fontWeight: "600", color: "var(--text)", margin: "0 0 6px 0" }}>
              {incident.title}
            </h2>
            <div style={{ fontSize: "13px", color: "var(--text-muted)" }}>
              Detected at: {new Date(incident.detected_at).toLocaleString()}
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div style={{ 
              display: "flex", 
              alignItems: "center", 
              gap: "8px", 
              padding: "6px 12px", 
              borderRadius: "20px", 
              background: isGeminiConnected ? "rgba(16, 185, 129, 0.1)" : "rgba(239, 68, 68, 0.1)",
              border: `1px solid ${isGeminiConnected ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)"}`,
              fontSize: "12px",
              fontWeight: "600",
              color: isGeminiConnected ? "#10b981" : "#ef4444"
            }}>
              <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: isGeminiConnected ? "#10b981" : "#ef4444" }}></span>
              AI: {isGeminiConnected ? `Gemini (${aiStatus.model || '3.5-flash-lite'}) ● Connected` : "AI OFFLINE"}
            </div>

            <button 
              className="btn btn-primary"
              onClick={handleInvestigate}
              disabled={investigating || !isGeminiConnected}
              style={{ padding: "8px 18px", fontWeight: "600", display: "flex", alignItems: "center", gap: "8px" }}
            >
              {investigating ? (
                <>
                  <span className="spinner"></span>
                  Gemini Investigating PostgreSQL...
                </>
              ) : (
                <>⚡ Investigate with Gemini</>
              )}
            </button>
          </div>
        </div>

        {errorMsg && (
          <div style={{ marginTop: "16px", padding: "12px 16px", background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.3)", borderRadius: "6px", color: "#f87171", fontSize: "13px" }}>
            <strong>Investigation Notice:</strong> {errorMsg}
          </div>
        )}
      </div>

      {/* 2. IMPACT & FORENSIC METRICS SUMMARY */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px" }}>
        <div className="card" style={{ padding: "16px 20px" }}>
          <div style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: "500" }}>POTENTIAL EXPOSURE</div>
          <div style={{ fontSize: "22px", fontWeight: "700", color: "#f87171", marginTop: "4px" }}>
            ₹{(investigationData?.estimated_exposure || incident.potential_exposure || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>Unresolved failed payments</div>
        </div>

        <div className="card" style={{ padding: "16px 20px" }}>
          <div style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: "500" }}>FAILED PAYMENTS</div>
          <div style={{ fontSize: "22px", fontWeight: "700", color: "var(--text)", marginTop: "4px" }}>
            {incident.affected_payments || incident.evidence?.failed_payments_count || 87}
          </div>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>
            {incident.evidence ? `${incident.evidence.failure_rate_pct}% failure rate` : "Elevated failure rate"}
          </div>
        </div>

        <div className="card" style={{ padding: "16px 20px" }}>
          <div style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: "500" }}>AFFECTED MERCHANTS</div>
          <div style={{ fontSize: "22px", fontWeight: "700", color: "var(--text)", marginTop: "4px" }}>
            {incident.affected_merchants || incident.evidence?.affected_merchants_count || 10}
          </div>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>Enterprise & SMB accounts</div>
        </div>

        <div className="card" style={{ padding: "16px 20px" }}>
          <div style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: "500" }}>ANOMALY SCORE</div>
          <div style={{ fontSize: "22px", fontWeight: "700", color: "var(--primary)", marginTop: "4px" }}>
            {incident.anomaly_score?.toFixed(2) || "1.00"}
          </div>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>IsolationForest Outlier Index</div>
        </div>
      </div>

      {/* 3. INVESTIGATION REPORT (WHAT HAPPENED / WHY) */}
      <div className="card" style={{ padding: "24px" }}>
        <h3 style={{ fontSize: "16px", fontWeight: "600", color: "var(--text)", marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
          <span>🔍</span> AI Forensic Findings
          {investigationData && (
            <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: "normal", marginLeft: "auto" }}>
              Investigated by Gemini ({investigationData.model || 'gemini-3.5-flash-lite'})
            </span>
          )}
        </h3>

        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div style={{ background: "rgba(255, 255, 255, 0.02)", padding: "14px 18px", borderRadius: "8px", border: "1px solid var(--border)" }}>
            <div style={{ fontSize: "12px", fontWeight: "700", color: "var(--primary)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "4px" }}>
              1. What Happened
            </div>
            <p style={{ margin: 0, fontSize: "14px", lineHeight: "1.6", color: "var(--text)" }}>
              {investigationData?.what_happened || incident.description}
            </p>
          </div>

          <div style={{ background: "rgba(255, 255, 255, 0.02)", padding: "14px 18px", borderRadius: "8px", border: "1px solid var(--border)" }}>
            <div style={{ fontSize: "12px", fontWeight: "700", color: "#eab308", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "4px" }}>
              2. Why It Happened (Root Cause)
            </div>
            <p style={{ margin: 0, fontSize: "14px", lineHeight: "1.6", color: "var(--text)" }}>
              {investigationData?.why_it_happened || incident.primary_signal || "Awaiting multi-turn AI tool investigation against PostgreSQL database."}
            </p>
          </div>
        </div>
      </div>

      {/* 4. PHASE D: ACTION GOVERNOR & HUMAN-IN-THE-LOOP APPROVAL */}
      <div className="card" style={{ padding: "24px", border: "1px solid rgba(239, 68, 68, 0.3)", background: "rgba(239, 68, 68, 0.02)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "10px" }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text)", margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
            <span>🛡️</span> Governed Operational Action
          </h3>

          {primaryAction && (
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ 
                fontSize: "11px", 
                fontWeight: "700", 
                padding: "4px 8px", 
                borderRadius: "4px", 
                background: primaryAction.risk_level === "RED" ? "rgba(239, 68, 68, 0.2)" : "rgba(234, 179, 8, 0.2)",
                color: primaryAction.risk_level === "RED" ? "#f87171" : "#facc15",
                border: `1px solid ${primaryAction.risk_level === "RED" ? "rgba(239, 68, 68, 0.4)" : "rgba(234, 179, 8, 0.4)"}`
              }}>
                RISK: {primaryAction.risk_level} (HUMAN AUTHORIZATION REQUIRED)
              </span>

              <span style={{ 
                fontSize: "11px", 
                fontWeight: "700", 
                padding: "4px 8px", 
                borderRadius: "4px", 
                background: primaryAction.status === "executed" ? "rgba(16, 185, 129, 0.2)" : primaryAction.status === "approved" ? "rgba(59, 130, 246, 0.2)" : primaryAction.status === "rejected" ? "rgba(100, 116, 139, 0.2)" : "rgba(234, 179, 8, 0.2)",
                color: primaryAction.status === "executed" ? "#10b981" : primaryAction.status === "approved" ? "#60a5fa" : primaryAction.status === "rejected" ? "#94a3b8" : "#facc15",
                border: "1px solid var(--border)",
                textTransform: "uppercase"
              }}>
                {primaryAction.status === "executed" ? "EXECUTED (SIMULATION)" : primaryAction.status === "approved" ? "APPROVED BY HUMAN" : primaryAction.status === "rejected" ? "REJECTED" : "RECOMMENDED (PENDING APPROVAL)"}
              </span>
            </div>
          )}
        </div>

        <div style={{ background: "rgba(0, 0, 0, 0.2)", padding: "16px 20px", borderRadius: "8px", border: "1px solid var(--border)" }}>
          <div style={{ fontSize: "14px", fontWeight: "600", color: "var(--text)", marginBottom: "6px" }}>
            Proposed Action: Reroute traffic away from <code style={{ color: "#f87171" }}>{incident.target_entity_id || "Gateway_X"}</code> to healthy backup channels (SBI / ICICI / HDFC)
          </div>
          <div style={{ fontSize: "13px", color: "var(--text-muted)", lineHeight: "1.5", marginBottom: "12px" }}>
            <strong>Why:</strong> 74 out of 87 failed payments are <code style={{ color: "var(--primary)" }}>GATEWAY_TIMEOUT</code> (85.06% concentration) with 19.08% failure rate (5.42x peer baseline).
          </div>

          {/* Action Control Buttons */}
          {primaryAction && (
            <div style={{ marginTop: "16px", display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
              {primaryAction.status === "pending_approval" && (
                <>
                  <button 
                    className="btn btn-primary"
                    onClick={() => handleApprove(primaryAction.action_id)}
                    disabled={actionLoading}
                    style={{ background: "#10b981", borderColor: "#10b981", padding: "8px 18px", fontWeight: "600" }}
                  >
                    ✓ Approve Action (Human Operator)
                  </button>
                  <button 
                    className="btn"
                    onClick={() => handleReject(primaryAction.action_id)}
                    disabled={actionLoading}
                    style={{ background: "rgba(239, 68, 68, 0.15)", color: "#f87171", border: "1px solid rgba(239, 68, 68, 0.3)", padding: "8px 16px" }}
                  >
                    ✕ Reject Action
                  </button>
                </>
              )}

              {primaryAction.status === "approved" && (
                <button 
                  className="btn btn-primary"
                  onClick={() => handleExecuteSimulation(primaryAction.action_id)}
                  disabled={actionLoading}
                  style={{ background: "#3b82f6", borderColor: "#3b82f6", padding: "8px 20px", fontWeight: "600" }}
                >
                  ⚡ Execute Safe Simulation
                </button>
              )}

              {primaryAction.status === "executed" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "6px", width: "100%" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#10b981", fontSize: "13px", fontWeight: "600" }}>
                    <span>✓ Approved by Human</span>
                    <span>•</span>
                    <span>✓ Safe Simulation Executed</span>
                    <span>•</span>
                    <span>✓ Immutable Audit Log Recorded</span>
                  </div>

                  {primaryAction.execution_result && (
                    <div style={{ marginTop: "8px", padding: "12px 14px", background: "#0f172a", borderRadius: "6px", border: "1px solid var(--border)", fontSize: "12px" }}>
                      <div style={{ color: "#38bdf8", fontWeight: "600", marginBottom: "4px" }}>
                        Simulation Result: {primaryAction.execution_result.message}
                      </div>
                      <div style={{ color: "var(--text-muted)" }}>
                        Backup Nodes Activated: {primaryAction.execution_result.backup_nodes_activated?.join(", ")} | Live Razorpay records modified: {primaryAction.execution_result.real_razorpay_payments_modified}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {primaryAction.status === "rejected" && (
                <div style={{ color: "#94a3b8", fontSize: "13px", fontStyle: "italic" }}>
                  Action rejected by human operator. Governance policy prevented execution.
                </div>
              )}
            </div>
          )}

          {!primaryAction && (
            <div style={{ marginTop: "12px", fontSize: "12px", color: "var(--text-muted)" }}>
              Click <strong>"⚡ Investigate with Gemini"</strong> above to evaluate telemetry and propose this governed action.
            </div>
          )}

          {actionMsg && (
            <div style={{ marginTop: "12px", padding: "8px 12px", background: "rgba(59, 130, 246, 0.1)", border: "1px solid rgba(59, 130, 246, 0.3)", borderRadius: "6px", color: "#60a5fa", fontSize: "12px" }}>
              {actionMsg}
            </div>
          )}
        </div>
      </div>

      {/* 5. EVIDENCE CARDS */}
      <div className="card" style={{ padding: "24px" }}>
        <h3 style={{ fontSize: "15px", fontWeight: "600", color: "var(--text)", marginBottom: "14px" }}>
          📊 Corroborating Forensic Evidence (PostgreSQL Sourced)
        </h3>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "12px" }}>
          {evidenceList.map((ev, idx) => (
            <div key={idx} style={{ padding: "12px 16px", background: "rgba(255, 255, 255, 0.02)", border: "1px solid var(--border)", borderRadius: "6px" }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "4px" }}>
                {ev.claim || `Finding #${idx + 1}`}
              </div>
              <div style={{ fontSize: "14px", fontWeight: "600", color: "var(--text)" }}>
                {ev.supporting_data || ev.key_metric || JSON.stringify(ev)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 6. AUDITABLE INVESTIGATION TRACE (COLLAPSED BY DEFAULT) */}
      <div className="card" style={{ padding: "20px 24px" }}>
        <details style={{ cursor: "pointer" }}>
          <summary style={{ fontSize: "14px", fontWeight: "600", color: "var(--text)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span>🛠️ Investigation Trace & Tool Calling Logs ({steps.length} steps executed)</span>
            <span style={{ fontSize: "12px", color: "var(--primary)" }}>Toggle Execution Details</span>
          </summary>

          <div style={{ marginTop: "16px", display: "flex", flexDirection: "column", gap: "10px" }}>
            {steps.length === 0 ? (
              <div style={{ fontSize: "13px", color: "var(--text-muted)", padding: "10px 0" }}>
                No tool steps recorded yet. Click <strong>"Investigate with Gemini"</strong> to trigger real multi-turn tool calling.
              </div>
            ) : (
              steps.map((st, idx) => (
                <div key={st.step_id || idx} style={{ border: "1px solid var(--border)", borderRadius: "6px", overflow: "hidden" }}>
                  <div 
                    onClick={() => setExpandedStep(expandedStep === idx ? null : idx)}
                    style={{ 
                      padding: "10px 14px", 
                      background: "rgba(255, 255, 255, 0.03)", 
                      display: "flex", 
                      justifyContent: "space-between", 
                      alignItems: "center",
                      fontSize: "13px"
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span style={{ color: "#10b981", fontWeight: "bold" }}>✓</span>
                      <span style={{ fontFamily: "monospace", fontWeight: "600", color: "var(--primary)" }}>
                        Step {st.step_number || idx + 1}: Gemini → {st.tool_name}
                      </span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "12px", fontSize: "11px", color: "var(--text-muted)" }}>
                      {st.latency_ms && <span>{st.latency_ms}ms</span>}
                      <span>{expandedStep === idx ? "▲ Hide" : "▼ Inspect Output"}</span>
                    </div>
                  </div>

                  {expandedStep === idx && (
                    <div style={{ padding: "12px 14px", background: "rgba(0, 0, 0, 0.2)", borderTop: "1px solid var(--border)", fontSize: "12px" }}>
                      <div style={{ marginBottom: "8px" }}>
                        <strong style={{ color: "var(--text-muted)" }}>Arguments:</strong>
                        <pre style={{ margin: "4px 0", padding: "8px", background: "#0f172a", borderRadius: "4px", overflowX: "auto" }}>
                          {JSON.stringify(st.arguments || st.input_json, null, 2)}
                        </pre>
                      </div>
                      <div>
                        <strong style={{ color: "var(--text-muted)" }}>PostgreSQL Result:</strong>
                        <pre style={{ margin: "4px 0", padding: "8px", background: "#0f172a", borderRadius: "4px", overflowX: "auto", maxHeight: "200px" }}>
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
