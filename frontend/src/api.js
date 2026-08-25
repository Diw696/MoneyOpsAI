const API_BASE = "http://localhost:8000/api";

export async function fetchStats() {
  const res = await fetch(`${API_BASE}/stats`);
  if (!res.ok) throw new Error("Failed to fetch operational stats");
  return res.json();
}

export async function fetchIncidents() {
  const res = await fetch(`${API_BASE}/incidents`);
  if (!res.ok) throw new Error("Failed to fetch incidents");
  return res.json();
}

export async function fetchIncidentDetail(incidentId) {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}`);
  if (!res.ok) throw new Error("Failed to fetch incident detail");
  return res.json();
}

export async function runInvestigation(incidentId) {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/investigate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Investigation failed");
  }
  return res.json();
}

export async function authorizeAction(incidentId, approved, operatorNotes = "Authorized per FinOps Policy", authorizedBy = "FinOps_Lead") {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/action`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      approved,
      operator_notes: operatorNotes,
      authorized_by: authorizedBy
    })
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Action execution failed");
  }
  return res.json();
}

export async function fetchMerchants() {
  const res = await fetch(`${API_BASE}/merchants`);
  if (!res.ok) throw new Error("Failed to fetch merchants");
  return res.json();
}

export async function fetchGraph(targetId) {
  const res = await fetch(`${API_BASE}/graph/${targetId}`);
  if (!res.ok) throw new Error("Failed to fetch entity graph");
  return res.json();
}

export async function fetchAuditLogs() {
  const res = await fetch(`${API_BASE}/audit`);
  if (!res.ok) throw new Error("Failed to fetch audit logs");
  return res.json();
}

export async function resetDemo() {
  const res = await fetch(`${API_BASE}/reset`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to reset system");
  return res.json();
}
