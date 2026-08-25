import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import OperationsKPIs from './components/OperationsKPIs';
import IncidentQueue from './components/IncidentQueue';
import InvestigationStudio from './components/InvestigationStudio';
import MerchantBaselinesView from './components/MerchantBaselinesView';
import AuditTrailView from './components/AuditTrailView';
import SystemArchitectureModal from './components/SystemArchitectureModal';
import WebhookSimulatorModal from './components/WebhookSimulatorModal';
import {
  fetchStats, fetchIncidents, fetchIncidentDetail, runInvestigation,
  authorizeAction, fetchMerchants, fetchAuditLogs, resetDemo
} from './api';

export default function App() {
  const [activeTab, setActiveTab] = useState('operations');
  const [stats, setStats] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState('INC-2841');
  const [currentIncident, setCurrentIncident] = useState(null);
  const [currentInvestigation, setCurrentInvestigation] = useState(null);
  const [lastAuditEntry, setLastAuditEntry] = useState(null);
  const [merchants, setMerchants] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  
  const [isInvestigating, setIsInvestigating] = useState(false);
  const [isExecutingAction, setIsExecutingAction] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [isWebhookModalOpen, setIsWebhookModalOpen] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  // Load initial data
  const loadDashboardData = async () => {
    try {
      const [sData, incData] = await Promise.all([
        fetchStats(),
        fetchIncidents()
      ]);
      setStats(sData);
      setIncidents(incData);

      if (!selectedIncidentId && incData.length > 0) {
        setSelectedIncidentId(incData[0].incident_id);
      }
    } catch (err) {
      console.error("Error loading dashboard data:", err);
    }
  };

  const loadIncidentDetails = async (id) => {
    if (!id) return;
    try {
      const detail = await fetchIncidentDetail(id);
      setCurrentIncident(detail.incident);
      setCurrentInvestigation(detail.latest_investigation);
    } catch (err) {
      console.error("Error loading incident detail:", err);
    }
  };

  const loadMerchants = async () => {
    try {
      const mList = await fetchMerchants();
      setMerchants(mList);
    } catch (err) {
      console.error("Error loading merchants:", err);
    }
  };

  const loadAuditLogs = async () => {
    try {
      const aList = await fetchAuditLogs();
      setAuditLogs(aList);
    } catch (err) {
      console.error("Error loading audit logs:", err);
    }
  };

  useEffect(() => {
    loadDashboardData();
    const interval = setInterval(loadDashboardData, 4000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (selectedIncidentId) {
      loadIncidentDetails(selectedIncidentId);
    }
  }, [selectedIncidentId]);

  useEffect(() => {
    if (activeTab === 'merchants') {
      loadMerchants();
    } else if (activeTab === 'audit') {
      loadAuditLogs();
    }
  }, [activeTab]);

  const handleSelectIncident = (id) => {
    setSelectedIncidentId(id);
    loadIncidentDetails(id);
  };

  const handleRunInvestigation = async (id) => {
    setIsInvestigating(true);
    setErrorMsg(null);
    try {
      const report = await runInvestigation(id);
      setCurrentInvestigation(report);
      await loadDashboardData();
    } catch (err) {
      setErrorMsg(err.message || "Failed to complete investigation");
    } finally {
      setIsInvestigating(false);
    }
  };

  const handleAuthorizeAction = async (id, approved, operatorNotes) => {
    setIsExecutingAction(true);
    setErrorMsg(null);
    try {
      const auditResult = await authorizeAction(id, approved, operatorNotes);
      setLastAuditEntry(auditResult);
      // Reload updated incident & dashboard stats
      await loadIncidentDetails(id);
      await loadDashboardData();
      await loadAuditLogs();
    } catch (err) {
      setErrorMsg(err.message || "Failed to execute governed action");
    } finally {
      setIsExecutingAction(false);
    }
  };

  const handleReset = async () => {
    setIsResetting(true);
    try {
      await resetDemo();
      await loadDashboardData();
      if (selectedIncidentId) {
        await loadIncidentDetails(selectedIncidentId);
      }
      if (activeTab === 'merchants') await loadMerchants();
      if (activeTab === 'audit') await loadAuditLogs();
    } catch (err) {
      console.error("Reset failed:", err);
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      
      {/* Platform Header */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onReset={handleReset}
        isResetting={isResetting}
        onOpenWebhookModal={() => setIsWebhookModalOpen(true)}
      />

      {/* Razorpay Webhook Ingestion Simulator Modal */}
      <WebhookSimulatorModal
        isOpen={isWebhookModalOpen}
        onClose={() => setIsWebhookModalOpen(false)}
        onWebhookSent={async () => {
          await loadDashboardData();
          if (selectedIncidentId) await loadIncidentDetails(selectedIncidentId);
        }}
      />

      {/* Main Container */}
      <main className="container" style={{ padding: '24px 20px', flex: 1 }}>
        
        {/* Error Alert Bar */}
        {errorMsg && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid #ef4444',
            borderRadius: '8px',
            padding: '10px 16px',
            color: '#fca5a5',
            fontSize: '0.85rem',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <span><strong>Alert:</strong> {errorMsg}</span>
            <button onClick={() => setErrorMsg(null)} className="btn btn-ghost" style={{ padding: '2px 8px', fontSize: '0.7rem' }}>
              Dismiss
            </button>
          </div>
        )}

        {/* Tab 1: Operations Control Dashboard */}
        {activeTab === 'operations' && (
          <div>
            <OperationsKPIs stats={stats} />

            <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: '20px', alignItems: 'start' }}>
              {/* Left Column: Active Incidents Queue */}
              <IncidentQueue
                incidents={incidents}
                selectedIncidentId={selectedIncidentId}
                onSelectIncident={handleSelectIncident}
                isInvestigating={isInvestigating}
              />

              {/* Right Column: Deep Investigation Studio */}
              <InvestigationStudio
                incident={currentIncident}
                investigation={currentInvestigation}
                onRunInvestigation={handleRunInvestigation}
                isInvestigating={isInvestigating}
                onAuthorizeAction={handleAuthorizeAction}
                isExecutingAction={isExecutingAction}
                lastAuditEntry={lastAuditEntry}
              />
            </div>
          </div>
        )}

        {/* Tab 2: Merchant Behavioral Baselines */}
        {activeTab === 'merchants' && (
          <MerchantBaselinesView merchants={merchants} />
        )}

        {/* Tab 3: Governed Audit Trail */}
        {activeTab === 'audit' && (
          <AuditTrailView auditLogs={auditLogs} />
        )}

        {/* Tab 4: System Architecture & Judgment */}
        {activeTab === 'architecture' && (
          <SystemArchitectureModal />
        )}

      </main>

      {/* Footer */}
      <footer style={{
        borderTop: '1px solid var(--border-subtle)',
        padding: '16px 0',
        textAlign: 'center',
        fontSize: '0.75rem',
        color: 'var(--text-muted)',
        background: 'rgba(10, 14, 23, 0.9)'
      }}>
        <div className="container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span>MoneyOps AI — Built for Razorpay Internship (Open Track AI)</span>
          <span className="mono">Data Engineering + Unsupervised ML + Money Graph + Case Memory + 3-Tier Governance</span>
        </div>
      </footer>

    </div>
  );
}
