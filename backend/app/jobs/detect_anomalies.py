import json
from app.engine.anomaly_detector import anomaly_detector
from app.engine.database import get_db_connection

def main():
    print("=" * 65)
    print(" MONEYOPS AI — UNSUPERVISED ML ANOMALY DETECTION ENGINE")
    print("=" * 65)

    result = anomaly_detector.run_detection()

    print(f"\nRecords Analyzed : {result['records_analyzed']} payment transactions")
    print(f"Gateways Evaluated : {result['gateways_evaluated']}")
    print(f"Anomalies Detected : {result['anomalies_detected']}")

    print("\n--- Gateway ML Anomaly Scores ---")
    print(f"{'Gateway':<20} {'Failure Rate':>14} {'Peer Rate':>12} {'ML Score':>10} {'Status':>12}")
    print("-" * 72)
    for g in result.get("gateway_evaluations", []):
        status_tag = "[ANOMALY]" if g["is_anomalous"] else "[NORMAL]"
        print(f"{g['gateway']:<20} {round(g['failure_rate'] * 100, 2):>13}% {round(g['peer_failure_rate'] * 100, 2):>11}% {g['anomaly_score']:>10.4f} {status_tag:>12}")

    print("\n--- Active Incidents in PostgreSQL ---")
    if result["incidents"]:
        for inc in result["incidents"]:
            print(f"\nIncident ID       : {inc['incident_id']}")
            print(f"Title             : {inc['title']}")
            print(f"Entity            : gateway ({inc['target_entity']})")
            print(f"Severity          : {inc['severity'].upper()}")
            print(f"Anomaly Score     : {inc['anomaly_score']}")
            print(f"Failure Rate      : {inc['failure_rate']} (Peer average: {inc['peer_failure_rate']})")
            print(f"Failed Payments   : {inc['failed_payments']}")
            print(f"Potential Exposure: INR {inc['potential_exposure']:,.2f}")
            print(f"Primary Signal    : {inc['primary_signal']}")
            print(f"Data Provenance   : {inc['source']}")
    else:
        print("  ✓ No active anomalies detected. System operating within normal baseline limits.")

    print("\n" + "=" * 65)

if __name__ == "__main__":
    main()
