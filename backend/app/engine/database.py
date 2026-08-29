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

    # 9. Governed Actions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS governed_actions (
        action_id VARCHAR(100) PRIMARY KEY,
        incident_id VARCHAR(100) NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
        investigation_id VARCHAR(100),
        action_type VARCHAR(100) NOT NULL,
        target_entity VARCHAR(100) NOT NULL,
        risk_level VARCHAR(20) NOT NULL,
        status VARCHAR(50) DEFAULT 'pending_approval',
        reason TEXT NOT NULL,
        evidence_json TEXT,
        created_at TIMESTAMPTZ NOT NULL,
        approved_by VARCHAR(100),
        approved_at TIMESTAMPTZ,
        executed_at TIMESTAMPTZ,
        execution_result_json TEXT
    );
    """)

    # 10. Audit Logs Table (Immutable Append-Only Log)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        audit_id VARCHAR(100) PRIMARY KEY,
        action_id VARCHAR(100),
        incident_id VARCHAR(100) NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
        investigation_id VARCHAR(100),
        action_type VARCHAR(100) NOT NULL,
        previous_status VARCHAR(50),
        new_status VARCHAR(50) NOT NULL,
        actor VARCHAR(100) NOT NULL,
        reason TEXT,
        evidence_json TEXT,
        execution_result_json TEXT,
        timestamp TIMESTAMPTZ NOT NULL
    );
    """)

    # Alter audit_logs for columns added since its original schema version.
    cursor.execute("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS action_id VARCHAR(100);")
    cursor.execute("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS action_type VARCHAR(100);")
    cursor.execute("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS previous_status VARCHAR(50);")
    cursor.execute("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS new_status VARCHAR(50);")
    cursor.execute("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS reason TEXT;")
    cursor.execute("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS evidence_json TEXT;")
    cursor.execute("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS execution_result_json TEXT;")

    # These three columns only exist on databases upgraded from an older schema
    # version; a freshly created audit_logs table never has them, so guard each
    # ALTER so init_db() stays idempotent on both fresh and upgraded databases.
    for legacy_column in ("action_name", "action_tier", "approval_status"):
        cursor.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'audit_logs' AND column_name = '{legacy_column}'
                ) THEN
                    ALTER TABLE audit_logs ALTER COLUMN {legacy_column} DROP NOT NULL;
                END IF;
            END $$;
        """)

    # 11. Evaluation Ground Truth Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS eval_ground_truth (
        evaluation_id VARCHAR(100) PRIMARY KEY,
        scenario_id VARCHAR(100) NOT NULL,
        scenario_type VARCHAR(100) NOT NULL,
        entity_type VARCHAR(50) NOT NULL,
        entity_id VARCHAR(100) NOT NULL,
        expected_anomaly BOOLEAN NOT NULL,
        expected_detection VARCHAR(50) NOT NULL,
        severity VARCHAR(50) NOT NULL,
        seed INTEGER NOT NULL,
        anomaly_magnitude DOUBLE PRECISION,
        detected_incident_id VARCHAR(100),
        is_true_positive BOOLEAN,
        is_false_positive BOOLEAN,
        is_false_negative BOOLEAN,
        is_true_negative BOOLEAN,
        miss_reason TEXT,
        created_at TIMESTAMPTZ NOT NULL,
        metadata_json TEXT
    );
    """)

    # 12. Incident Embeddings Table (for Case Memory cosine similarity)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS incident_embeddings (
        incident_id VARCHAR(100) PRIMARY KEY REFERENCES incidents(incident_id) ON DELETE CASCADE,
        embedding_vector TEXT NOT NULL,
        content_text TEXT,
        model_name VARCHAR(100) DEFAULT 'deterministic-semantic-vector',
        created_at TIMESTAMPTZ NOT NULL
    );
    """)

    cursor.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS embedding_json TEXT;")

    # Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_merchant ON payments(merchant_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_gateway ON payments(gateway);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_source ON payments(source);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_refunds_payment ON refunds(payment_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_webhooks_external_id ON webhook_events(external_event_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_entity ON incidents(target_entity_type, target_entity_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_actions_incident ON governed_actions(incident_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_actions_status ON governed_actions(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eval_scenario ON eval_ground_truth(scenario_id);")


    conn.commit()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("PostgreSQL 9-table schema initialized successfully.")
