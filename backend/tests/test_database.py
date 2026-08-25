import pytest
import sqlite3
from app.engine.database import get_db_connection, init_db

def test_database_tables_exist():
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row["name"] for row in cursor.fetchall()}
    conn.close()

    expected_tables = {
        "merchants", "customers", "orders", "payments", "refunds",
        "settlements", "disputes", "webhook_events", "canonical_events",
        "incidents", "historical_cases", "investigations", "audit_logs"
    }
    for tbl in expected_tables:
        assert tbl in tables, f"Expected table {tbl} missing from database"

def test_foreign_key_enforcement():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Attempt inserting order with non-existent merchant
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("""
            INSERT INTO orders (order_id, merchant_id, customer_id, amount, status, created_at)
            VALUES ('ord_invalid', 'merch_non_existent', 'cust_non_existent', 500.0, 'paid', '2026-08-25T00:00:00')
        """)
        conn.commit()
    conn.close()
