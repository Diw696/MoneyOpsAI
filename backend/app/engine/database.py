import sqlite3
from typing import Optional
from pathlib import Path
from app.core.config import settings

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

def init_db():
    """Initializes the clean V2 9-table relational financial schema in SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Merchants Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS merchants (
        merchant_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT DEFAULT 'general',
        baseline_refund_rate REAL DEFAULT 0.015,
        created_at TEXT NOT NULL
    )
    """)

    # 2. Orders Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,
        merchant_id TEXT NOT NULL,
        amount REAL NOT NULL,
        currency TEXT DEFAULT 'INR',
        status TEXT NOT NULL,
        source TEXT DEFAULT 'razorpay_test',
        created_at TEXT NOT NULL,
        ingested_at TEXT NOT NULL,
        FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id) ON DELETE CASCADE
    )
    """)

    # 3. Payments Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        payment_id TEXT PRIMARY KEY,
        order_id TEXT,
        merchant_id TEXT NOT NULL,
        amount REAL NOT NULL,
        currency TEXT DEFAULT 'INR',
        status TEXT NOT NULL,
        method TEXT DEFAULT 'card',
        gateway TEXT DEFAULT 'Razorpay_Gateway',
        failure_code TEXT,
        error_description TEXT,
        retry_count INTEGER DEFAULT 0,
        source TEXT DEFAULT 'razorpay_test',
        created_at TEXT NOT NULL,
        captured_at TEXT,
        ingested_at TEXT NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE SET NULL,
        FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id) ON DELETE CASCADE
    )
    """)

    # 4. Refunds Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS refunds (
        refund_id TEXT PRIMARY KEY,
        payment_id TEXT NOT NULL,
        merchant_id TEXT NOT NULL,
        amount REAL NOT NULL,
        currency TEXT DEFAULT 'INR',
        status TEXT NOT NULL,
        speed TEXT DEFAULT 'normal',
        failure_reason TEXT,
        source TEXT DEFAULT 'razorpay_test',
        created_at TEXT NOT NULL,
        processed_at TEXT,
        ingested_at TEXT NOT NULL,
        FOREIGN KEY (payment_id) REFERENCES payments(payment_id) ON DELETE CASCADE,
        FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id) ON DELETE CASCADE
    )
    """)

    # 5. Webhook Events Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS webhook_events (
        event_id TEXT PRIMARY KEY,
        external_event_id TEXT UNIQUE,
        event_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        signature_valid INTEGER DEFAULT 1,
        delivery_status TEXT DEFAULT 'delivered',
        source TEXT DEFAULT 'razorpay_test',
        received_at TEXT NOT NULL,
        processed_at TEXT
    )
    """)

    # 6. Incidents Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS incidents (
        incident_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        type TEXT NOT NULL,
        severity TEXT NOT NULL,
        status TEXT DEFAULT 'open',
        affected_merchants INTEGER DEFAULT 1,
        affected_payments INTEGER DEFAULT 1,
        potential_exposure REAL NOT NULL,
        anomaly_score REAL DEFAULT 0.85,
        source TEXT DEFAULT 'razorpay_test',
        detected_at TEXT NOT NULL,
        description TEXT NOT NULL
    )
    """)

    # 7. AI Investigations Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_investigations (
        investigation_id TEXT PRIMARY KEY,
        incident_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        model TEXT NOT NULL,
        what_happened TEXT,
        why_it_happened TEXT,
        evidence_json TEXT,
        affected_entities_json TEXT,
        estimated_exposure REAL DEFAULT 0.0,
        historical_precedent TEXT,
        recommendation TEXT,
        confidence REAL DEFAULT 0.9,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        status TEXT DEFAULT 'completed',
        FOREIGN KEY (incident_id) REFERENCES incidents(incident_id) ON DELETE CASCADE
    )
    """)

    # 8. AI Investigation Steps Table (Granular Tool-Calling Audit)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_investigation_steps (
        step_id TEXT PRIMARY KEY,
        investigation_id TEXT NOT NULL,
        step_number INTEGER NOT NULL,
        tool_name TEXT NOT NULL,
        input_json TEXT NOT NULL,
        output_json TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (investigation_id) REFERENCES ai_investigations(investigation_id) ON DELETE CASCADE
    )
    """)

    # 9. Audit Logs Table (Action Governor Proof)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        audit_id TEXT PRIMARY KEY,
        investigation_id TEXT,
        incident_id TEXT NOT NULL,
        actor TEXT NOT NULL,
        action_name TEXT NOT NULL,
        action_tier TEXT NOT NULL,
        approval_status TEXT NOT NULL,
        operator_notes TEXT,
        financial_exposure REAL DEFAULT 0.0,
        simulated_action_result TEXT,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (incident_id) REFERENCES incidents(incident_id) ON DELETE CASCADE
    )
    """)

    # Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_merchant ON payments(merchant_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_source ON payments(source)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_refunds_payment ON refunds(payment_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_webhooks_external_id ON webhook_events(external_event_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_steps_investigation ON ai_investigation_steps(investigation_id)")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("V2 Database initialized with clean 9-table schema.")
