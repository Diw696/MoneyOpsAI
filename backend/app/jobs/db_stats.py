from app.engine.database import get_db_connection

def print_db_stats():
    print("=" * 65)
    print(" MONEYOPS AI — POSTGRESQL DATABASE OBSERVABILITY & METRICS")
    print("=" * 65)
    
    conn = get_db_connection()
    c = conn.cursor()
    
    tables = [
        "merchants", "orders", "payments", "refunds",
        "webhook_events", "incidents", "ai_investigations",
        "ai_investigation_steps", "audit_logs"
    ]
    
    print("\n1. Table Row Counts:")
    for tbl in tables:
        c.execute(f"SELECT COUNT(*) as cnt FROM {tbl};")
        cnt = c.fetchone()["cnt"]
        print(f"  - {tbl:<25}: {cnt:>6} rows")

    print("\n2. Payment Records by Provenance (Source):")
    c.execute("SELECT source, COUNT(*) as count FROM payments GROUP BY source ORDER BY count DESC;")
    pay_sources = c.fetchall()
    if pay_sources:
        for r in pay_sources:
            print(f"  - {r['source']:<25}: {r['count']:>6} payments")
    else:
        print("  - (No payments found)")

    print("\n3. Order Records by Provenance (Source):")
    c.execute("SELECT source, COUNT(*) as count FROM orders GROUP BY source ORDER BY count DESC;")
    ord_sources = c.fetchall()
    if ord_sources:
        for r in ord_sources:
            print(f"  - {r['source']:<25}: {r['count']:>6} orders")
    else:
        print("  - (No orders found)")

    print("\n4. Payment Status Distribution:")
    c.execute("SELECT status, COUNT(*) as count FROM payments GROUP BY status ORDER BY count DESC;")
    pay_statuses = c.fetchall()
    for r in pay_statuses:
        print(f"  - {r['status']:<25}: {r['count']:>6} payments")

    c.close()
    conn.close()
    print("=" * 65)

if __name__ == "__main__":
    print_db_stats()
