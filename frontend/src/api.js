const API_BASE = "http://localhost:8000/api";

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error("Failed to fetch system health");
  return res.json();
}

export async function fetchAIStatus() {
  const res = await fetch(`${API_BASE}/ai/status`);
  if (!res.ok) throw new Error("Failed to fetch AI status");
  return res.json();
}

export async function fetchStats() {
  const res = await fetch(`${API_BASE}/stats`);
  if (!res.ok) throw new Error("Failed to fetch operational stats");
  return res.json();
}

export async function fetchSourceStats() {
  const res = await fetch(`${API_BASE}/stats/sources`);
  if (!res.ok) throw new Error("Failed to fetch source distribution");
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
    const msg = typeof err.detail === "object" ? err.detail.message : (err.detail || "Investigation failed");
    throw new Error(msg);
  }
  return res.json();
}

export async function fetchInvestigation(investigationId) {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}`);
  if (!res.ok) throw new Error("Failed to fetch investigation");
  return res.json();
}

export async function fetchInvestigationSteps(investigationId) {
  const res = await fetch(`${API_BASE}/investigations/${investigationId}/steps`);
  if (!res.ok) throw new Error("Failed to fetch investigation steps");
  return res.json();
}

export async function fetchIncidentInvestigations(incidentId) {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/investigations`);
  if (!res.ok) throw new Error("Failed to fetch incident investigations");
  return res.json();
}

// Action Governor API Functions (Phase D)
export async function proposeAction(data) {
  const res = await fetch(`${API_BASE}/actions/propose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to propose action");
  }
  return res.json();
}

export async function approveAction(actionId, notes = "Authorized per FinOps Policy") {
  const res = await fetch(`${API_BASE}/actions/${actionId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor: "Human_Operator", operator_notes: notes })
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to approve action");
  }
  return res.json();
}

export async function rejectAction(actionId, reason = "Human operator rejected action") {
  const res = await fetch(`${API_BASE}/actions/${actionId}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor: "Human_Operator", reason })
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to reject action");
  }
  return res.json();
}

export async function executeAction(actionId) {
  const res = await fetch(`${API_BASE}/actions/${actionId}/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor: "Human_Operator" })
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to execute action");
  }
  return res.json();
}

export async function fetchIncidentActions(incidentId) {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/actions`);
  if (!res.ok) throw new Error("Failed to fetch incident actions");
  return res.json();
}

export async function fetchAuditLogs() {
  const res = await fetch(`${API_BASE}/audit-logs`);
  if (!res.ok) throw new Error("Failed to fetch audit logs");
  return res.json();
}

export async function triggerAnomalyDetection() {
  const res = await fetch(`${API_BASE}/anomalies/detect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  });
  if (!res.ok) throw new Error("Failed to trigger anomaly detection");
  return res.json();
}

export async function generateLabData(payload = { seed: 42, payments: 2500, merchants: 10, anomaly: "gateway_spike" }) {
  const res = await fetch(`${API_BASE}/incident-lab/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error("Failed to generate laboratory dataset");
  return res.json();
}

export async function syncRazorpay() {
  const res = await fetch(`${API_BASE}/razorpay/sync`, {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Razorpay sync failed");
  }
  return res.json();
}

export async function fetchPayments(limit = 50, source = null) {
  const url = source ? `${API_BASE}/payments?limit=${limit}&source=${source}` : `${API_BASE}/payments?limit=${limit}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch payments");
  return res.json();
}

export async function fetchOrders(limit = 50, source = null) {
  const url = source ? `${API_BASE}/orders?limit=${limit}&source=${source}` : `${API_BASE}/orders?limit=${limit}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch orders");
  return res.json();
}

export async function fetchRefunds(limit = 50, source = null) {
  const url = source ? `${API_BASE}/refunds?limit=${limit}&source=${source}` : `${API_BASE}/refunds?limit=${limit}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch refunds");
  return res.json();
}

export async function fetchWebhooks(limit = 50) {
  const res = await fetch(`${API_BASE}/webhooks?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch webhooks");
  return res.json();
}

