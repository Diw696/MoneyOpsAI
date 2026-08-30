import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import OverviewView from './components/OverviewView';
import DataView from './components/DataView';
import InvestigationView from './components/InvestigationView';
import EvaluationView from './components/EvaluationView';
import AuditView from './components/AuditView';
import {
  fetchHealth,
  fetchStats,
  fetchSourceStats,
  fetchIncidents,
  fetchIncidentDetail,
  fetchAIStatus,
  triggerAnomalyDetection
} from './api';

export default function App() {
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'data' | 'investigation' | 'evaluation' | 'audit'

  const [health, setHealth] = useState(null);
  const [stats, setStats] = useState(null);
  const [sourceStats, setSourceStats] = useState(null);
  const [aiStatus, setAiStatus] = useState({ provider: 'gemini', configured: false, model: 'gemini-3.5-flash-lite' });
  const [incidents, setIncidents] = useState([]);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [isDetecting, setIsDetecting] = useState(false);
  const [notification, setNotification] = useState(null);

  const loadData = async () => {
    try {
      const [hData, sData, srcData, incList, aiInfo] = await Promise.all([
        fetchHealth().catch(() => ({ status: "offline", database: "PostgreSQL", razorpay_configured: false, gemini_configured: false })),
        fetchStats().catch(() => null),
        fetchSourceStats().catch(() => null),
        fetchIncidents().catch(() => []),
        fetchAIStatus().catch(() => ({ provider: 'gemini', configured: false, model: 'gemini-3.5-flash-lite' }))
      ]);

      setHealth(hData);
      setStats(sData);
      setSourceStats(srcData);
      setIncidents(incList || []);
      setAiStatus(aiInfo || { provider: 'gemini', configured: false, model: 'gemini-3.5-flash-lite' });

      if (incList && incList.length > 0) {
        if (!selectedIncident || !incList.some(i => i.incident_id === selectedIncident.incident_id)) {
          setSelectedIncident(incList[0]);
        } else {
          const updated = incList.find(i => i.incident_id === selectedIncident.incident_id);
          if (updated) setSelectedIncident(updated);
        }
      } else {
        setSelectedIncident(null);
      }
    } catch (err) {
      console.error("Error loading dashboard data:", err);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleSelectAndInvestigate = async (inc) => {
    setSelectedIncident(inc);
    try {
      const detailed = await fetchIncidentDetail(inc.incident_id);
      setSelectedIncident(detailed);
    } catch (e) {
      console.warn("Detail fetch failed, using list object:", e);
    }
    setActiveTab('investigation');
  };

  const handleTriggerDetection = async () => {
    setIsDetecting(true);
    setNotification(null);
    try {
      const res = await triggerAnomalyDetection();
      setNotification({
        type: "success",
        text: `✓ Detection scan complete. ${res.anomalies_detected} anomalies evaluated across ${res.records_analyzed} PostgreSQL records.`
      });
      await loadData();
    } catch (e) {
      setNotification({
        type: "error",
        text: `Detection failed: ${e.message}`
      });
    } finally {
      setIsDetecting(false);
    }
  };

  return (
    <div className="app-container" style={{ minHeight: "100vh", background: "var(--bg)", color: "var(--text)" }}>
      
      {/* 1. TOP HEADER & 4-VIEW NAVIGATION */}
      <Header 
        activeTab={activeTab} 
        onTabChange={setActiveTab} 
        health={health}
        stats={stats} 
        aiStatus={aiStatus} 
        incidentsCount={incidents.filter(i => i.status !== 'resolved').length}
        onRefresh={loadData} 
      />

      {/* 2. GLOBAL NOTIFICATION BANNER */}
      {notification && (
        <div style={{
          maxWidth: "1600px",
          margin: "16px auto 0",
          padding: "10px 24px"
        }}>
          <div style={{
            padding: "10px 16px",
            borderRadius: "6px",
            fontSize: "13px",
            background: notification.type === "success" ? "rgba(16, 185, 129, 0.1)" : "rgba(239, 68, 68, 0.1)",
            border: `1px solid ${notification.type === "success" ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)"}`,
            color: notification.type === "success" ? "#10b981" : "#f87171",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center"
          }}>
            <span>{notification.text}</span>
            <button onClick={() => setNotification(null)} style={{ background: "none", border: "none", color: "inherit", cursor: "pointer" }}>✕</button>
          </div>
        </div>
      )}

      {/* 3. PRIMARY WORKSPACE CONTAINER */}
      <main style={{ maxWidth: "1600px", margin: "0 auto", padding: "24px" }}>
        {activeTab === 'overview' && (
          <OverviewView
            stats={stats}
            sourceStats={sourceStats}
            incidents={incidents}
            onSelectIncident={handleSelectAndInvestigate}
            onTriggerDetection={handleTriggerDetection}
            isDetecting={isDetecting}
          />
        )}

        {activeTab === 'data' && (
          <DataView onRefreshAll={loadData} />
        )}

        {activeTab === 'investigation' && (
          <InvestigationView 
            incident={selectedIncident} 
            aiStatus={aiStatus} 
            onRefreshAll={loadData} 
          />
        )}

        {activeTab === 'evaluation' && (
          <EvaluationView />
        )}

        {activeTab === 'audit' && (
          <AuditView />
        )}
      </main>


    </div>
  );
}

