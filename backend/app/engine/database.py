import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional
from app.core.config import settings

def get_db_connection():
    """Returns a connection to the PostgreSQL database with RealDictCursor."""
    conn = psycopg2.connect(
        settings.DATABASE_URL,
        cursor_factory=RealDictCursor
    )
    return conn

def init_db():
    """Initializes the clean V2 9-table relational financial schema in PostgreSQL."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Merchants Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS merchants (
        merchant_id VARCHAR(100) PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        category VARCHAR(100) DEFAULT 'general',
        baseline_refund_rate DOUBLE PRECISION DEFAULT 0.015,
        created_at TIMESTAMPTZ NOT NULL
    );
    """)

    # 2. Orders Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id VARCHAR(100) PRIMARY KEY,
        merchant_id VARCHAR(100) NOT NULL REFERENCES merchants(merchant_id) ON DELETE CASCADE,
        amount DOUBLE PRECISION NOT NULL,
        currency VARCHAR(10) DEFAULT 'INR',
        status VARCHAR(50) NOT NULL,
        source VARCHAR(50) DEFAULT 'razorpay_test',
        created_at TIMESTAMPTZ NOT NULL,
        ingested_at TIMESTAMPTZ NOT NULL
    );
    """)

    # 3. Payments Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        payment_id VARCHAR(100) PRIMARY KEY,
        order_id VARCHAR(100) REFERENCES orders(order_id) ON DELETE SET NULL,
        merchant_id VARCHAR(100) NOT NULL REFERENCES merchants(merchant_id) ON DELETE CASCADE,
        amount DOUBLE PRECISION NOT NULL,
        currency VARCHAR(10) DEFAULT 'INR',
        status VARCHAR(50) NOT NULL,
        method VARCHAR(50) DEFAULT 'card',
        gateway VARCHAR(100) DEFAULT 'Razorpay_Gateway',
        failure_code VARCHAR(50),
        error_description TEXT,
        retry_count INTEGER DEFAULT 0,
        source VARCHAR(50) DEFAULT 'razorpay_test',
        created_at TIMESTAMPTZ NOT NULL,
        captured_at TIMESTAMPTZ,
        ingested_at TIMESTAMPTZ NOT NULL
    );
    """)

    # 4. Refunds Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS refunds (
        refund_id VARCHAR(100) PRIMARY KEY,
        payment_id VARCHAR(100) NOT NULL REFERENCES payments(payment_id) ON DELETE CASCADE,
        merchant_id VARCHAR(100) NOT NULL REFERENCES merchants(merchant_id) ON DELETE CASCADE,
        amount DOUBLE PRECISION NOT NULL,
        currency VARCHAR(10) DEFAULT 'INR',
        status VARCHAR(50) NOT NULL,
        speed VARCHAR(50) DEFAULT 'normal',
        failure_reason TEXT,
        source VARCHAR(50) DEFAULT 'razorpay_test',
        created_at TIMESTAMPTZ NOT NULL,
        processed_at TIMESTAMPTZ,
        ingested_at TIMESTAMPTZ NOT NULL
    );
    """)

    # 5. Webhook Events Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS webhook_events (
        event_id VARCHAR(100) PRIMARY KEY,
        external_event_id VARCHAR(100) UNIQUE,
        event_type VARCHAR(100) NOT NULL,
        entity_id VARCHAR(100) NOT NULL,
        payload_json TEXT NOT NULL,
        signature_valid INTEGER DEFAULT 1,
        delivery_status VARCHAR(50) DEFAULT 'delivered',
        source VARCHAR(50) DEFAULT 'razorpay_test',
        received_at TIMESTAMPTZ NOT NULL,
        processed_at TIMESTAMPTZ
    );
    """)

    # 6. Incidents Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS incidents (
        incident_id VARCHAR(100) PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        type VARCHAR(100) NOT NULL,
        target_entity_type VARCHAR(50) DEFAULT 'gateway',
        target_entity_id VARCHAR(100),
        severity VARCHAR(50) NOT NULL,
        status VARCHAR(50) DEFAULT 'open',
        affected_merchants INTEGER DEFAULT 1,
        affected_payments INTEGER DEFAULT 1,
        potential_exposure DOUBLE PRECISION NOT NULL,
        anomaly_score DOUBLE PRECISION DEFAULT 0.85,
        primary_signal TEXT,
        evidence_json TEXT,
        source VARCHAR(50) DEFAULT 'razorpay_test',
        detected_at TIMESTAMPTZ NOT NULL,
        description TEXT NOT NULL
    );
    """)

    # Alter table if existing from earlier migration to guarantee new columns exist
    cursor.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS target_entity_type VARCHAR(50) DEFAULT 'gateway';")
    cursor.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS target_entity_id VARCHAR(100);")
    cursor.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS primary_signal TEXT;")
    cursor.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS evidence_json TEXT;")

    # 7. AI Investigations Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_investigations (
        investigation_id VARCHAR(100) PRIMARY KEY,
        incident_id VARCHAR(100) NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
        provider VARCHAR(50) NOT NULL,
        model VARCHAR(100) NOT NULL,
        what_happened TEXT,
        why_it_happened TEXT,
        evidence_json TEXT,
        affected_entities_json TEXT,
        estimated_exposure DOUBLE PRECISION DEFAULT 0.0,
        historical_precedent TEXT,
        recommendation TEXT,
        confidence DOUBLE PRECISION DEFAULT 0.9,
        started_at TIMESTAMPTZ NOT NULL,
        completed_at TIMESTAMPTZ,
        status VARCHAR(50) DEFAULT 'completed'
    );
    """)

    # 8. AI Investigation Steps Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_investigation_steps (
        step_id VARCHAR(100) PRIMARY KEY,
        investigation_id VARCHAR(100) NOT NULL REFERENCES ai_investigations(investigation_id) ON DELETE CASCADE,
        step_number INTEGER NOT NULL,
        tool_name VARCHAR(100) NOT NULL,
        input_json TEXT NOT NULL,
        output_json TEXT NOT NULL,
        timestamp TIMESTAMPTZ NOT NULL
    );
    """)

    # 9. Audit Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        audit_id VARCHAR(100) PRIMARY KEY,
        investigation_id VARCHAR(100),
        incident_id VARCHAR(100) NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
        actor VARCHAR(100) NOT NULL,
        action_name VARCHAR(100) NOT NULL,
        action_tier VARCHAR(50) NOT NULL,
        approval_status VARCHAR(50) NOT NULL,
        operator_notes TEXT,
        financial_exposure DOUBLE PRECISION DEFAULT 0.0,
        simulated_action_result TEXT,
        timestamp TIMESTAMPTZ NOT NULL
    );
    """)

    # Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_merchant ON payments(merchant_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_gateway ON payments(gateway);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_source ON payments(source);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_refunds_payment ON refunds(payment_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_webhooks_external_id ON webhook_events(external_event_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_entity ON incidents(target_entity_type, target_entity_id);")

    conn.commit()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("PostgreSQL 9-table schema initialized successfully.")
