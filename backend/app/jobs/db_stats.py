from app.engine.database import get_db_connection

def print_db_stats():
    conn = get_db_connection()
    cursor = conn.cursor()

    tables = [
        "raw_external_events", "customers", "merchants", "orders",
        "payments", "refunds", "settlements", "disputes",
        "webhook_events", "canonical_events", "incidents",
        "historical_cases", "investigations", "audit_logs"
    ]

    print("=" * 60)
    print(" MONEYOPS AI — RELATIONAL DATABASE & LINEAGE AUDIT")
    print("=" * 60)

    for tbl in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) as cnt FROM {tbl}")
            cnt = cursor.fetchone()["cnt"]
            print(f"  {tbl:<25}: {cnt:>6} rows")
        except Exception as e:
            print(f"  {tbl:<25}: Error ({e})")

    print("-" * 60)
    cursor.execute("SELECT source, COUNT(*) as cnt FROM payments GROUP BY source")
    print("Payments Lineage Breakdown:")
    for row in cursor.fetchall():
        print(f"  - Source '{row['source']}': {row['cnt']} payments")

    cursor.execute("SELECT source, COUNT(*) as cnt FROM raw_external_events GROUP BY source")
    print("Raw Events Lineage Breakdown:")
    for row in cursor.fetchall():
        print(f"  - Source '{row['source']}': {row['cnt']} raw events")

    print("=" * 60)
    conn.close()

if __name__ == "__main__":
    print_db_stats()
