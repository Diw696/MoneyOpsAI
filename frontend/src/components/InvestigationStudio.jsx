import React, { useState } from 'react';
import {
  ShieldAlert, Sparkles, CheckCircle2, XCircle, Clock, Database,
  ArrowRight, Check, X, AlertTriangle, Layers, Lock, Cpu, ChevronDown, ChevronRight, FileCheck, GitBranch
} from 'lucide-react';
import { formatINR } from './OperationsKPIs';
import MoneyGraphVisualizer from './MoneyGraphVisualizer';
import DataLineageModal from './DataLineageModal';

export default function InvestigationStudio({
  incident,
  investigation,
  onRunInvestigation,
  isInvestigating,
  onAuthorizeAction,
  isExecutingAction,
  lastAuditEntry
}) {
  const [expandedStep, setExpandedStep] = useState(null);
  const [operatorNotes, setOperatorNotes] = useState('');
  const [showLineageModal, setShowLineageModal] = useState(false);

  if (!incident) {
    return (
      <div className="glass-panel" style={{ padding: '60px 20px', textAlign: 'center', height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <ShieldAlert size={48} color="var(--text-muted)" style={{ marginBottom: '16px' }} />
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '8px' }}>
          Select an incident to investigate
        </h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', maxWidth: '400px' }}>
          Select an active financial incident from the queue on the left to start multi-stage AI reasoning, entity graph traversal, and case memory matching.
        </p>
      </div>
    );
  }

  const isResolved = incident.status === 'resolved';

  return (
    <div className="glass-panel animate-fade-in" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* Top Banner: Incident Title + Severity + Anomaly Score + Investigate CTA */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '18px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
            <span className="mono" style={{ fontSize: '0.9rem', fontWeight: 800, color: '#38bdf8' }}>
              {incident.incident_id}
            </span>
            <span className={`badge badge-${incident.severity}`}>
              {incident.severity} Severity
            </span>
            {isResolved ? (
              <span className="badge badge-resolved">
                <CheckCircle2 size={12} /> Resolved
              </span>
            ) : (
              <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.3)' }}>
                Active Incident
              </span>
            )}
          </div>

          <h1 style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '6px' }}>
            {incident.title}
          </h1>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              {incident.description}
            </p>
            <span className="badge" style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#c084fc', border: '1px solid rgba(168, 85, 247, 0.3)', fontSize: '0.68rem', padding: '2px 8px' }}>
              <Cpu size={11} style={{ marginRight: '4px' }} />
              Agent Mode: ReAct Tool-Calling
            </span>
          </div>
        </div>

        {/* Right Header: ML Anomaly Score & Trigger Button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{
            background: 'rgba(239, 68, 68, 0.08)',
            border: '1px solid rgba(239, 68, 68, 0.25)',
            borderRadius: '8px',
            padding: '8px 14px',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
              ML Anomaly Score
            </div>
            <div className="mono" style={{ fontSize: '1.25rem', fontWeight: 800, color: '#ef4444' }}>
              {incident.anomaly_score ? (incident.anomaly_score).toFixed(3) : "0.932"}
            </div>
          </div>

          <button
            onClick={() => setShowLineageModal(true)}
            className="btn btn-secondary"
            style={{ padding: '8px 14px', fontSize: '0.8rem' }}
            title="Inspect Data Lineage & Forensic Provenance"
          >
            <GitBranch size={15} color="#38bdf8" />
            Data Lineage
          </button>

          {!investigation && (
            <button
              onClick={() => onRunInvestigation(incident.incident_id)}
              disabled={isInvestigating}
              className="btn btn-primary"
              style={{ padding: '10px 20px', fontSize: '0.9rem' }}
            >
              <Sparkles size={16} className={isInvestigating ? "animate-spin" : ""} />
              {isInvestigating ? "Investigating Evidence..." : "Start AI Investigation"}
            </button>
          )}
        </div>
      </div>

      <DataLineageModal
        isOpen={showLineageModal}
        onClose={() => setShowLineageModal(false)}
        incident={incident}
        investigation={investigation}
      />

      {/* Financial Impact Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
        <div style={{ background: 'rgba(239, 68, 68, 0.06)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: '8px', padding: '12px 16px' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-muted)' }}>POTENTIAL EXPOSURE</span>
          <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#f87171' }}>{formatINR(incident.potential_exposure)}</div>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Delayed / Unsettled funds</span>
        </div>

        <div style={{ background: 'rgba(16, 185, 129, 0.06)', border: '1px solid rgba(16, 185, 129, 0.2)', borderRadius: '8px', padding: '12px 16px' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-muted)' }}>RECOVERABLE EXPOSURE</span>
          <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#34d399' }}>{formatINR(incident.recoverable_exposure)}</div>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Preservable with action</span>
        </div>

        <div style={{ background: 'rgba(59, 130, 246, 0.06)', border: '1px solid rgba(59, 130, 246, 0.2)', borderRadius: '8px', padding: '12px 16px' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-muted)' }}>MERCHANTS AFFECTED</span>
          <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#60a5fa' }}>{incident.affected_merchants}</div>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Impact blast radius</span>
        </div>

        <div style={{ background: 'rgba(168, 85, 247, 0.06)', border: '1px solid rgba(168, 85, 247, 0.2)', borderRadius: '8px', padding: '12px 16px' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-muted)' }}>AFFECTED TRANSACTIONS</span>
          <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#c084fc' }}>{incident.affected_transactions.toLocaleString('en-IN')}</div>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Correlated payment events</span>
        </div>
      </div>

      {/* Visual Financial Money Graph */}
      <MoneyGraphVisualizer
        incidentType={incident.type}
        targetId={incident.target_entity_id || incident.primary_gateway || incident.incident_id}
      />

      {/* Investigation Details View (When Investigation Exists) */}
      {investigation && (
        <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          {/* Historical Case Memory Match */}
          {investigation.similar_incidents && investigation.similar_incidents.length > 0 && (
            <div style={{
              background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, rgba(168, 85, 247, 0.08) 100%)',
              border: '1px solid var(--border-accent)',
              borderRadius: '10px',
              padding: '16px 20px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Database size={16} color="#38bdf8" />
                  <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                    Historical Case Memory (Vector Precedent Match)
                  </span>
                </div>
                <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.2)', color: '#38bdf8', border: '1px solid #38bdf8' }}>
                  {Math.round((investigation.similar_incidents[0].similarity_score || 0.91) * 100)}% Similarity Match
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '16px', background: 'rgba(0, 0, 0, 0.25)', padding: '12px 14px', borderRadius: '8px' }}>
                <div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>PRECEDENT INCIDENT</div>
                  <div className="mono" style={{ fontWeight: 700, color: '#f8fafc', fontSize: '0.9rem' }}>
                    {investigation.similar_incidents[0].incident_id}: {investigation.similar_incidents[0].title}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: '#34d399', marginTop: '4px' }}>
                    Outcome: {investigation.similar_incidents[0].outcome}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>PROVEN RESOLUTION PRECEDENT</div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                    "{investigation.similar_incidents[0].resolution}"
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Live Agent Reasoning Feed ("See the Agent Work") */}
          <div style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '10px',
            padding: '16px 20px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Cpu size={16} color="#10b981" />
                <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  Agent Activity & Evidence Execution Feed
                </span>
              </div>
              <span style={{ fontSize: '0.72rem', color: '#34d399', fontWeight: 600 }}>
                {investigation.agent_steps?.length || 5} Reasoning Stages Completed
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {investigation.agent_steps?.map((step) => {
                const isExpanded = expandedStep === step.step_number;
                return (
                  <div
                    key={step.step_number}
                    style={{
                      background: 'rgba(15, 20, 31, 0.7)',
                      border: '1px solid rgba(255, 255, 255, 0.05)',
                      borderRadius: '8px',
                      padding: '10px 14px',
                      transition: 'all 0.2s ease'
                    }}
                  >
                    <div
                      onClick={() => setExpandedStep(isExpanded ? null : step.step_number)}
                      style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <div style={{
                          width: '18px',
                          height: '18px',
                          borderRadius: '50%',
                          background: 'rgba(16, 185, 129, 0.2)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center'
                        }}>
                          <Check size={12} color="#34d399" />
                        </div>
                        <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                          {step.title}
                        </span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span className="mono" style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                          tool: {step.tool_name}
                        </span>
                        {isExpanded ? <ChevronDown size={14} color="var(--text-muted)" /> : <ChevronRight size={14} color="var(--text-muted)" />}
                      </div>
                    </div>

                    <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px', marginLeft: '28px', lineHeight: 1.4 }}>
                      {step.description}
                    </p>

                    {isExpanded && step.tool_output && (
                      <div style={{
                        marginTop: '8px',
                        marginLeft: '28px',
                        background: '#07090e',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: '6px',
                        padding: '8px 12px',
                        fontSize: '0.7rem'
                      }}>
                        <div style={{ color: 'var(--text-muted)', marginBottom: '4px', fontWeight: 600 }}>RAW TOOL EVIDENCE OUTPUT:</div>
                        <pre className="mono" style={{ color: '#38bdf8', overflowX: 'auto', maxHeight: '140px' }}>
                          {JSON.stringify(step.tool_output, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* AI Root Cause & Evidence Synthesis */}
          <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '16px' }}>
            
            {/* Root Cause Card */}
            <div style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '10px',
              padding: '16px 20px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <Sparkles size={16} color="#a855f7" />
                <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  AI Root-Cause Synthesis
                </span>
                <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.72rem', color: '#34d399' }}>
                  Confidence: {(investigation.confidence * 100).toFixed(1)}%
                </span>
              </div>

              <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#f8fafc', marginBottom: '8px', lineHeight: 1.4 }}>
                {investigation.root_cause}
              </div>

              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                {investigation.root_cause_hypothesis}
              </p>
            </div>

            {/* Evidence Points */}
            <div style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '10px',
              padding: '16px 20px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <Layers size={16} color="#38bdf8" />
                <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  Forensic Evidence Chain
                </span>
              </div>

              <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {investigation.evidence?.map((item, idx) => (
                  <li key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                    <div style={{ width: '4px', height: '4px', borderRadius: '50%', background: '#38bdf8', marginTop: '6px' }} />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>

          </div>

          {/* Action Governor Console */}
          <div style={{
            background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.08) 0%, rgba(245, 158, 11, 0.08) 100%)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: '12px',
            padding: '20px 24px',
            position: 'relative'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Lock size={18} color="#ef4444" />
                <span style={{ fontSize: '0.95rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                  Action Governor — Governed Response Policy
                </span>
              </div>

              <span className="badge badge-tier-red">
                RED TIER — Human Approval Required
              </span>
            </div>

            <div style={{ background: 'rgba(0, 0, 0, 0.4)', borderRadius: '8px', padding: '14px 18px', marginBottom: '16px' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>RECOMMENDED ACTION</div>
              <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc', marginBottom: '4px' }}>
                {investigation.recommended_action}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                Policy Guardrail: Autonomous financial modification blocked. Requires explicit operator authorization.
              </div>
            </div>

            {isResolved ? (
              <div style={{
                background: 'rgba(16, 185, 129, 0.12)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                borderRadius: '8px',
                padding: '12px 16px',
                display: 'flex',
                alignItems: 'center',
                gap: '12px'
              }}>
                <FileCheck size={20} color="#34d399" />
                <div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#34d399' }}>
                    Action Executed in Simulation & Audited
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Audit ID: <span className="mono" style={{ color: '#38bdf8' }}>{lastAuditEntry?.audit_id || "ACT-88291"}</span> | Safeguards applied to affected merchants.
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px' }}>
                <input
                  type="text"
                  placeholder="Operator notes (e.g. Authorized per FinOps incident drill protocol)..."
                  value={operatorNotes}
                  onChange={(e) => setOperatorNotes(e.target.value)}
                  style={{
                    flex: 1,
                    background: 'rgba(15, 20, 31, 0.9)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '8px',
                    padding: '8px 14px',
                    fontSize: '0.8rem',
                    color: 'var(--text-primary)',
                    outline: 'none'
                  }}
                />

                <div style={{ display: 'flex', gap: '10px' }}>
                  <button
                    onClick={() => onAuthorizeAction(incident.incident_id, false, operatorNotes)}
                    disabled={isExecutingAction}
                    className="btn btn-reject"
                  >
                    <X size={15} />
                    Reject Action
                  </button>

                  <button
                    onClick={() => onAuthorizeAction(incident.incident_id, true, operatorNotes)}
                    disabled={isExecutingAction}
                    className="btn btn-approve"
                  >
                    <Check size={15} />
                    {isExecutingAction ? "Executing Simulation..." : "Approve & Execute Action"}
                  </button>
                </div>
              </div>
            )}
          </div>

        </div>
      )}

    </div>
  );
}
