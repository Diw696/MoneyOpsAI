import json
from app.engine.database import get_db_connection
from app.engine.anomaly_detector import anomaly_detector

def detect_anomalies():
    print("Running Isolation Forest Anomaly Detection across SQLite payments...")
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM payments ORDER BY created_at DESC LIMIT 500")
    payments = cursor.fetchall()

    anomalies = []
    for p in payments:
        sig = anomaly_detector.score_anomaly(
            entity_id=p["payment_id"],
            entity_type="payment",
            payload={
                "amount": p["amount"],
                "retry_count": p["retry_count"],
                "failure_code": p["failure_code"],
                "status": p["status"],
                "gateway": p["gateway"]
            }
        )
        if sig.is_anomaly:
            anomalies.append((p["payment_id"], sig.anomaly_score, sig.contributing_signals))

    conn.close()
    print(f"Anomaly Evaluation Complete: Scanned {len(payments)} records, found {len(anomalies)} anomalies.")
    for pay_id, score, signals in anomalies[:5]:
        print(f"  - [{pay_id}] Score: {score:.3f} | Signals: {', '.join(signals)}")

if __name__ == "__main__":
    detect_anomalies()
