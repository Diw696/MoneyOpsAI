import pytest
from app.engine.database import init_db, get_db_connection
from app.engine.incident_lab import IncidentLabGenerator
from app.engine.anomaly_detector import anomaly_detector

@pytest.fixture(autouse=True)
def setup_clean_db():
    init_db()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM audit_logs; DELETE FROM ai_investigation_steps; DELETE FROM ai_investigations; DELETE FROM incidents; DELETE FROM webhook_events; DELETE FROM refunds; DELETE FROM payments; DELETE FROM orders; DELETE FROM merchants;")
    conn.commit()
    c.close()
    conn.close()

def test_diagnose_default_volume_detection_behavior():
    """Diagnostic only (prints, no hard failure) — inspects WHY gateway/webhook
    incidents rarely fire at default demo volume while one low-baseline merchant
    dominates, by tracking distinct incident IDs (not re-confirmations of an
    already-open one) and raw gateway evaluation numbers each cycle."""
    seen_ids = {}
    for seed in range(1, 13):
        IncidentLabGenerator.generate_dataset(seed=seed, num_payments=250, num_merchants=10, anomaly_type="auto")
        res = anomaly_detector.run_detection()
        for inc in res["incidents"]:
            iid = inc.get("incident_id")
            if iid and iid not in seen_ids:
                seen_ids[iid] = inc["title"]

        gw_evals = anomaly_detector.evaluate_gateways()
        near_misses = [
            (g["gateway"], round(g["failure_rate"] * 100, 2), round(g["wilson_lower_bound_pct"], 2), g["sample_size_sufficient"], g["statistically_significant"], round(g["anomaly_score"], 2))
            for g in gw_evals if g["failure_rate"] > 0.10
        ]
        print(f"\nseed={seed} gateway near-misses (rate>10%): {near_misses}")

    print("\nDISTINCT incidents ever created across 12 cycles:")
    for iid, title in seen_ids.items():
        print(" ", iid, title)
    print("total distinct incidents:", len(seen_ids))
