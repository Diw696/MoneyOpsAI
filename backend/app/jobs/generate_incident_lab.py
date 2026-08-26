import argparse
import json
import sys
from app.engine.database import init_db, get_db_connection
from app.engine.incident_lab import IncidentLabGenerator

def main():
    parser = argparse.ArgumentParser(description="MoneyOps AI — Incident Lab Dataset Generator")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible generation")
    parser.add_argument("--payments", type=int, default=1000, help="Number of payments to generate")
    parser.add_argument("--merchants", type=int, default=10, help="Number of merchants to configure")
    parser.add_argument("--anomaly", type=str, default="none", choices=["none", "gateway_spike", "refund_spike", "duplicate_refund", "webhook_retry"], help="Controlled anomaly to inject")
    parser.add_argument("--clean", action="store_true", help="Truncate tables before generation (preserves schema)")

    args = parser.parse_args()

    print("=" * 65)
    print(" MONEYOPS AI — INCIDENT LAB REPRODUCIBLE GENERATOR")
    print("=" * 65)
    print(f" Config: Seed={args.seed} | Payments={args.payments} | Merchants={args.merchants} | Anomaly={args.anomaly}")
    
    init_db()
    
    if args.clean:
        print(" Cleaning existing database records...")
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("TRUNCATE TABLE audit_logs, ai_investigation_steps, ai_investigations, incidents, webhook_events, refunds, payments, orders, merchants CASCADE;")
        conn.commit()
        c.close()
        conn.close()

    print(" Generating financial lifecycles and routing through IngestionPipeline...")
    summary = IncidentLabGenerator.generate_dataset(
        seed=args.seed,
        num_payments=args.payments,
        num_merchants=args.merchants,
        anomaly_type=args.anomaly
    )

    print("\nIngestion Summary (PostgreSQL):")
    for k, v in summary.items():
        print(f"  - {k:<26}: {v}")
    print("=" * 65)

if __name__ == "__main__":
    main()
