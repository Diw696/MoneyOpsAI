import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import InvestigationStudio from './components/InvestigationStudio';
import { fetchStats, fetchIncidents, fetchIncidentDetail, fetchAIStatus, triggerAnomalyDetection, generateLabData } from './api';

export default function App() {
  const [stats, setStats] = useState(null);
  const [aiStatus, setAiStatus] = useState({ provider: 'gemini', configured: false, model: 'gemini-2.0-flash' });
  const [incidents, setIncidents] = useState([]);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [isDetecting, setIsDetecting] = useState(false);
  const [notification, setNotification] = useState(null);

  const loadData = async () => {
    try {
      const [sData, incList, aiInfo] = await Promise.all([
        fetchStats().catch(() => null),
        fetchIncidents().catch(() => []),
        fetchAIStatus().catch(() => ({ provider: 'gemini', configured: false, model: 'gemini-2.0-flash' }))
      ]);

      setStats(sData);
      setIncidents(incList || []);
      setAiStatus(aiInfo || { provider: 'gemini', configured: false, model: 'gemini-2.0-flash' });

      if (incList && incList.length > 0) {
        if (!selectedIncident || !incList.some(i => i.incident_id === selectedIncident.incident_id)) {
          setSelectedIncident(incList[0]);
        } else {
          const updated = incList.find(i => i.incident_id === selectedIncident.incident_id);
          if (updated) setSelectedIncident(updated);
        }
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

  const handleSelectIncident = async (inc) => {
    setSelectedIncident(inc);
    try {
      const detailed = await fetchIncidentDetail(inc.incident_id);
      setSelectedIncident(detailed);
    } catch (e) {
      console.warn("Detail fetch failed, using list object:", e);
    }
  };

  const handleTriggerDetection = async () => {
    setIsDetecting(true);
    setNotification(null);
    try {
      const res = await triggerAnomalyDetection();
      setNotification({
        type: "success",
        text: `Detection complete. ${res.anomalies_detected} anomalies evaluated across ${res.records_analyzed} PostgreSQL records.`
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
      {/* Top Header */}
      <Header stats={stats} aiStatus={aiStatus} onRefresh={loadData} />

      {notification && (
        <div style={{
          margin: "12px 24px 0",
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
      )}

      {/* Main Workspace Layout */}
      <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: "24px", padding: "24px", maxWidth: "1600px", margin: "0 auto" }}>
        
        {/* LEFT: Incident Queue */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div className="card" style={{ padding: "18px 20px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
              <h3 style={{ fontSize: "15px", fontWeight: "600", color: "var(--text)", margin: 0 }}>
                🚨 Active Incidents ({incidents.length})
              </h3>
              <button 
                onClick={handleTriggerDetection} 
                disabled={isDetecting}
                style={{ 
                  padding: "4px 10px", 
                  fontSize: "11px", 
                  borderRadius: "4px", 
                  background: "rgba(99, 102, 241, 0.15)", 
                  border: "1px solid rgba(99, 102, 241, 0.4)", 
                  color: "var(--primary)", 
                  cursor: "pointer",
                  fontWeight: "600"
                }}
              >
                {isDetecting ? "Scanning..." : "↻ Scan ML"}
              </button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {incidents.length === 0 ? (
                <div style={{ padding: "20px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
                  ✓ Zero active incidents. All banking gateways within normal operational baselines.
                </div>
              ) : (
                incidents.map((inc) => {
                  const isSelected = selectedIncident?.incident_id === inc.incident_id;
                  return (
                    <div
                      key={inc.incident_id}
                      onClick={() => handleSelectIncident(inc)}
                      style={{
                        padding: "14px",
                        borderRadius: "8px",
                        border: isSelected ? "1.5px solid var(--primary)" : "1px solid var(--border)",
                        background: isSelected ? "rgba(99, 102, 241, 0.08)" : "rgba(255, 255, 255, 0.02)",
                        cursor: "pointer",
                        transition: "all 0.15s ease"
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                        <span className={`badge badge-${inc.severity || 'critical'}`} style={{ fontSize: "10px", fontWeight: "700" }}>
                          {inc.severity?.toUpperCase() || 'CRITICAL'}
                        </span>
                        <span style={{ fontSize: "11px", color: "var(--text-muted)", fontFamily: "monospace" }}>
                          {inc.incident_id}
                        </span>
                      </div>
                      
                      <div style={{ fontSize: "13px", fontWeight: "600", color: "var(--text)", marginBottom: "6px" }}>
                        {inc.title}
                      </div>

                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "var(--text-muted)" }}>
                        <span>Exposure: <strong style={{ color: "#f87171" }}>₹{(inc.potential_exposure || 0).toLocaleString('en-IN')}</strong></span>
                        <span>Score: <strong style={{ color: "var(--primary)" }}>{inc.anomaly_score?.toFixed(2) || '1.00'}</strong></span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Database Provenance Box */}
          <div className="card" style={{ padding: "16px 20px", fontSize: "12px", color: "var(--text-muted)" }}>
            <div style={{ fontWeight: "600", color: "var(--text)", marginBottom: "8px" }}>📦 Database Observability</div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
              <span>Database</span>
              <strong style={{ color: "var(--text)" }}>PostgreSQL 18</strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
              <span>Payments Analyzed</span>
              <strong style={{ color: "var(--text)" }}>{stats?.payments || 0}</strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
              <span>Orders Stored</span>
              <strong style={{ color: "var(--text)" }}>{stats?.orders || 0}</strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>Webhooks Verified</span>
              <strong style={{ color: "var(--text)" }}>{stats?.webhook_events || 0}</strong>
            </div>
          </div>
        </div>

        {/* RIGHT: Investigation Studio */}
        <div>
          <InvestigationStudio 
            incident={selectedIncident} 
            aiStatus={aiStatus} 
            onRefresh={loadData} 
          />
        </div>

      </div>
    </div>
  );
}
