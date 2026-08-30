import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.engine.database import init_db, get_db_connection
from app.engine.incident_lab import IncidentLabGenerator

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_clean_db():
    init_db()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM audit_logs; DELETE FROM ai_investigation_steps; DELETE FROM ai_investigations; DELETE FROM incidents; DELETE FROM webhook_events; DELETE FROM refunds; DELETE FROM payments; DELETE FROM orders; DELETE FROM merchants;")
    conn.commit()
    c.close()
    conn.close()

def test_auto_mode_produces_varied_targets_across_runs():
    """
    "auto" mode must not default to the same merchant/gateway every call — this
    reproduces the exact product complaint (every screenshot showing
    merch_Nova_Store). Five auto-mode runs with different seeds must produce
    more than one distinct target entity among the runs that actually inject
    a scenario (a "none" outcome run has no target and is excluded).
    """
    targets = []
    for seed in range(1, 26):
        res = IncidentLabGenerator.generate_dataset(seed=seed, num_payments=300, num_merchants=10, anomaly_type="auto")
        if res["outcome"] != "none":
            targets.append(res["target_entity"])

    assert len(targets) >= 5, f"expected at least 5 non-'none' runs across 25 seeds, got {targets}"
    assert len(set(targets)) > 1, f"all non-'none' runs targeted the same entity: {targets}"

def test_auto_mode_produces_varied_scenario_types_across_runs():
    """Auto mode across enough seeds must produce more than one distinct
    scenario family, not the same incident type repeated."""
    scenario_types = []
    for seed in range(1, 25):
        res = IncidentLabGenerator.generate_dataset(seed=seed, num_payments=300, num_merchants=10, anomaly_type="auto")
        if res["outcome"] != "none":
            scenario_types.append(res["anomaly_injected"])

    assert len(scenario_types) >= 5, f"expected several non-'none' runs across 24 seeds, got {scenario_types}"
    assert len(set(scenario_types)) > 1, f"all non-'none' runs injected the same scenario type: {scenario_types}"

def test_auto_mode_outcome_distribution_includes_normal_runs():
    """Not every batch should be an incident — the 'none' outcome must actually occur."""
    outcomes = [
        IncidentLabGenerator.generate_dataset(seed=s, num_payments=200, num_merchants=5, anomaly_type="auto")["outcome"]
        for s in range(1, 15)
    ]
    assert "none" in outcomes, f"no 'none' (normal activity) outcome occurred across 14 seeds: {outcomes}"
