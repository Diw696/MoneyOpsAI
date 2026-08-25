import json
import random
import uuid
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List
from app.engine.database import get_db_connection, init_db
from app.engine.case_memory import case_memory
from app.engine.money_graph import money_graph

MERCHANT_PROFILES = [
    {"id": "merch_Nova_Store", "name": "Nova Lifestyle & Fashion", "category": "ecommerce", "refund_rate": 0.018, "settle_hrs": 24.0},
    {"id": "merch_CloudScale", "name": "CloudScale AI Systems", "category": "saas", "refund_rate": 0.005, "settle_hrs": 12.0},
    {"id": "merch_UrbanBites", "name": "UrbanBites Quick Commerce", "category": "food_delivery", "refund_rate": 0.022, "settle_hrs": 18.0},
    {"id": "merch_ZenithTravel", "name": "Zenith International Travels", "category": "travel", "refund_rate": 0.035, "settle_hrs": 48.0},
    {"id": "merch_PayPulse", "name": "PayPulse Gaming Studio", "category": "gaming", "refund_rate": 0.012, "settle_hrs": 24.0},
    {"id": "merch_ApexDigital", "name": "Apex Digital Electronics", "category": "ecommerce", "refund_rate": 0.015, "settle_hrs": 24.0},
    {"id": "merch_BlueHorizon", "name": "Blue Horizon Logistics", "category": "logistics", "refund_rate": 0.008, "settle_hrs": 36.0},
    {"id": "merch_VanguardHealth", "name": "Vanguard Diagnostics", "category": "healthcare", "refund_rate": 0.010, "settle_hrs": 24.0},
    {"id": "merch_AuraJewels", "name": "Aura Luxury Jewels", "category": "luxury", "refund_rate": 0.004, "settle_hrs": 48.0},
    {"id": "merch_KiteFin", "name": "Kite Neo Wealth", "category": "fintech", "refund_rate": 0.002, "settle_hrs": 12.0},
]

for i in range(11, 26):
    MERCHANT_PROFILES.append({
        "id": f"merch_Enterprise_{i:02d}",
        "name": f"Enterprise Merchant #{i}",
        "category": random.choice(["ecommerce", "saas", "edtech", "retail"]),
        "refund_rate": round(random.uniform(0.008, 0.025), 4),
        "settle_hrs": random.choice([12.0, 24.0, 36.0, 48.0])
    })

GATEWAYS = ["Gateway_HDFC", "Gateway_ICICI", "Gateway_Axis", "Gateway_X"]
FAILURE_CODES = ["BAD_REQUEST_ERROR", "INSUFFICIENT_FUNDS", "GATEWAY_TIMEOUT", "AUTH_FAILED"]

def seed_database(seed: int = 42, num_transactions: int = 2500, num_merchants: int = 25, n_transactions: int = None, n_merchants: int = None):
    num_transactions = n_transactions or num_transactions
    num_merchants = n_merchants or num_merchants
    random.seed(seed)
    np.random.seed(seed)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Drop all existing tables to guarantee pristine schema with 14 tables and lineage columns
    cursor.execute("PRAGMA foreign_keys = OFF")
    tables = [
        "raw_external_events", "audit_logs", "investigations", "historical_cases", "incidents",
        "canonical_events", "webhook_events", "disputes", "settlements",
        "refunds", "payments", "orders", "merchants", "customers"
    ]
    for t in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {t}")
    conn.commit()
    cursor.execute("PRAGMA foreign_keys = ON")

    # Initialize fresh tables
    init_db()

    base_time = datetime.utcnow() - timedelta(days=7)

    # 1. Seed Merchants
    for m in MERCHANT_PROFILES[:num_merchants]:
        created_at = (base_time - timedelta(days=60)).isoformat()
        cursor.execute("""
            INSERT INTO merchants (merchant_id, name, category, baseline_refund_rate, baseline_retry_count, baseline_settlement_latency_hrs, created_at)
            VALUES (?, ?, ?, ?, 1.2, ?, ?)
        """, (m["id"], m["name"], m["category"], m["refund_rate"], m["settle_hrs"], created_at))

    # 2. Seed Customers
    customers = []
    for i in range(1, 301):
        cid = f"cust_{i:04d}"
        customers.append(cid)
        cursor.execute("""
            INSERT INTO customers (customer_id, name, email, phone, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (cid, f"Customer {i}", f"customer{i}@example.com", f"+9198765{i:05d}", base_time.isoformat()))

    # 3. Seed Normal Baseline Transactions
    orders_data, payments_data, refunds_data, settlements_data, webhooks_data, canon_data = [], [], [], [], [], []

    for i in range(1, num_transactions + 1):
        tx_time = base_time + timedelta(minutes=i * 3.8)
        time_str = tx_time.isoformat()
        merch = random.choice(MERCHANT_PROFILES[:num_merchants])
        cust = random.choice(customers)
        amt = round(random.lognormvariate(mu=7.2, sigma=0.8), 2)
        amt = max(100.0, min(amt, 150000.0))

        ord_id = f"ord_{i:06d}"
        pay_id = f"pay_{i:06d}"
        gateway = random.choice(["Gateway_HDFC", "Gateway_ICICI", "Gateway_Axis"])

        # 96% success rate
        is_success = random.random() < 0.96
        status = "captured" if is_success else "failed"
        fail_code = None if is_success else random.choice(FAILURE_CODES)

        orders_data.append((ord_id, merch["id"], cust, amt, "INR", "paid" if is_success else "attempted", "synthetic", time_str, time_str))
        payments_data.append((
            pay_id, ord_id, merch["id"], cust, amt, "INR", status, "card", gateway, "synthetic",
            time_str, time_str if is_success else None, time_str, time_str, time_str,
            fail_code, None if is_success else "Bank declined transaction", 1 if is_success else 2
        ))

        # Normal refund logic
        if is_success and (random.random() < merch["refund_rate"]):
            rfnd_id = f"rfnd_{i:06d}"
            refunds_data.append((rfnd_id, pay_id, merch["id"], amt, "processed", "normal", "synthetic", time_str, time_str, time_str, None))
            webhooks_data.append((f"wh_{rfnd_id}", "refund.processed", rfnd_id, merch["id"], "synthetic", None, time_str, 1, 1, "delivered", 200, 115))

        # Normal settlement logic
        if is_success:
            settle_id = f"set_{i:06d}"
            settle_time = tx_time + timedelta(hours=random.uniform(2.0, 18.0))
            settlements_data.append((settle_id, merch["id"], pay_id, amt, f"UTR{random.randint(100000,999999)}", "settled", "synthetic", settle_time.isoformat(), (tx_time + timedelta(hours=24)).isoformat(), 0.0))

        webhooks_data.append((f"wh_{pay_id}", f"payment.{status}", pay_id, merch["id"], "synthetic", None, time_str, 1, 1, "delivered", 200, 95))
        canon_data.append((
            f"can_{pay_id}", "synthetic", f"payment.{status}", "payment", pay_id, merch["id"], amt, status,
            json.dumps({"order_id": ord_id, "gateway": gateway, "retry_count": 1 if is_success else 2}),
            time_str, 0, 0.12
        ))

    cursor.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?)", orders_data)
    cursor.executemany("INSERT INTO payments VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", payments_data)
    cursor.executemany("INSERT INTO refunds VALUES (?,?,?,?,?,?,?,?,?,?,?)", refunds_data)
    cursor.executemany("INSERT INTO settlements VALUES (?,?,?,?,?,?,?,?,?,?)", settlements_data)
    cursor.executemany("INSERT INTO webhook_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", webhooks_data)
    cursor.executemany("INSERT INTO canonical_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", canon_data)

    # 4. Inject Golden Demo Incident 1: Gateway X Refund Timeout Spike (INC-2841)
    spike_time = (datetime.utcnow() - timedelta(minutes=45)).isoformat()
    cursor.execute("""
        INSERT INTO incidents (
            incident_id, title, type, severity, status, affected_merchants,
            affected_transactions, potential_exposure, recoverable_exposure,
            primary_gateway, error_code, anomaly_score, source, detected_at, description, target_entity_id
        ) VALUES (
            'INC-2841', 'Gateway X Refund Failure Spike', 'gateway_refund_failure',
            'critical', 'open', 17, 4812, 3140000.0, 3140000.0,
            'Gateway_X', 'R-104', 0.942, 'synthetic', ?,
            'Upstream timeout storm detected on Gateway X refund endpoint (error code R-104). 4,812 refunds failing across 17 merchants.',
            'gw_Gateway_X'
        )
    """, (spike_time,))

    # Inject affected payments for Gateway X
    for idx in range(1, 49):
        aff_merch = MERCHANT_PROFILES[idx % len(MERCHANT_PROFILES)]
        p_id = f"pay_GWX_{idx:04d}"
        r_id = f"rfnd_GWX_{idx:04d}"
        o_id = f"ord_GWX_{idx:04d}"
        t_str = (datetime.utcnow() - timedelta(minutes=random.randint(10, 45))).isoformat()
        amt = 65000.0

        cursor.execute("INSERT OR IGNORE INTO orders VALUES (?, ?, 'cust_0001', ?, 'INR', 'paid', 'synthetic', ?, ?)", (o_id, aff_merch["id"], amt, t_str, t_str))
        cursor.execute("""
            INSERT OR IGNORE INTO payments VALUES (
                ?, ?, ?, 'cust_0001', ?, 'INR', 'captured', 'card', 'Gateway_X', 'synthetic',
                ?, ?, ?, ?, ?, 'R-104', 'Gateway timeout on refund attempt', 3
            )
        """, (p_id, o_id, aff_merch["id"], amt, t_str, t_str, t_str, t_str, t_str))
        cursor.execute("INSERT OR IGNORE INTO refunds VALUES (?, ?, ?, ?, 'failed', 'instant', 'synthetic', ?, NULL, ?, 'R-104 Gateway Timeout')", (r_id, p_id, aff_merch["id"], amt, t_str, t_str))
        cursor.execute("""
            INSERT OR IGNORE INTO webhook_events VALUES (
                ?, 'refund.failed', ?, ?, 'synthetic', NULL, ?, 3, 1, 'failed', 504, 8500
            )
        """, (f"wh_{r_id}", r_id, aff_merch["id"], t_str))
        cursor.execute("""
            INSERT OR IGNORE INTO canonical_events VALUES (
                ?, 'synthetic', 'refund.failed', 'refund', ?, ?, ?, 'failed',
                '{"gateway": "Gateway_X", "failure_code": "R-104", "retry_count": 3}', ?, 1, 0.942
            )
        """, (f"can_{r_id}", r_id, aff_merch["id"], amt, t_str))

    # 5. Inject Golden Demo Incident 2: Duplicate Instant Refund Race (INC-2840)
    dup_time = (datetime.utcnow() - timedelta(hours=2)).isoformat()
    cursor.execute("""
        INSERT INTO incidents (
            incident_id, title, type, severity, status, affected_merchants,
            affected_transactions, potential_exposure, recoverable_exposure,
            primary_gateway, error_code, anomaly_score, source, detected_at, description, target_entity_id
        ) VALUES (
            'INC-2840', 'Duplicate Instant Refund on P19283', 'duplicate_refund',
            'high', 'open', 1, 2, 4999.0, 4999.0,
            'Gateway_HDFC', 'ERR_DUP_REFUND', 0.912, 'synthetic', ?,
            'Dual refund records generated for single payment ID pay_P19283 due to webhook delivery retry race condition.',
            'pay_P19283'
        )
    """, (dup_time,))

    # Explicit records for pay_P19283
    cursor.execute("INSERT OR IGNORE INTO orders VALUES ('ord_O99124', 'merch_Nova_Store', 'cust_0001', 4999.0, 'INR', 'paid', 'synthetic', ?, ?)", (dup_time, dup_time))
    cursor.execute("""
        INSERT OR IGNORE INTO payments VALUES (
            'pay_P19283', 'ord_O99124', 'merch_Nova_Store', 'cust_0001', 4999.0, 'INR',
            'captured', 'card', 'Gateway_HDFC', 'synthetic', ?, ?, ?, ?, ?, NULL, NULL, 1
        )
    """, (dup_time, dup_time, dup_time, dup_time, dup_time))
    cursor.execute("INSERT OR IGNORE INTO refunds VALUES ('rfnd_R8821', 'pay_P19283', 'merch_Nova_Store', 4999.0, 'processed', 'instant', 'synthetic', ?, ?, ?, NULL)", (dup_time, dup_time, dup_time))
    cursor.execute("INSERT OR IGNORE INTO refunds VALUES ('rfnd_R8842', 'pay_P19283', 'merch_Nova_Store', 4999.0, 'processed', 'instant', 'synthetic', ?, ?, ?, NULL)", (dup_time, dup_time, dup_time))
    cursor.execute("INSERT OR IGNORE INTO webhook_events VALUES ('wh_W77192', 'payment.captured', 'pay_P19283', 'merch_Nova_Store', 'synthetic', NULL, ?, 1, 1, 'delivered', 200, 110)", (dup_time,))
    cursor.execute("INSERT OR IGNORE INTO webhook_events VALUES ('wh_W77198', 'refund.processed', 'rfnd_R8821', 'merch_Nova_Store', 'synthetic', NULL, ?, 1, 1, 'timed_out', 504, 5000)", (dup_time,))
    cursor.execute("INSERT OR IGNORE INTO webhook_events VALUES ('wh_W77204', 'refund.processed', 'rfnd_R8842', 'merch_Nova_Store', 'synthetic', NULL, ?, 2, 1, 'delivered', 200, 140)", (dup_time,))

    # 6. Inject Incidents 3 & 4 (Stuck Settlement & Retry Velocity)
    cursor.execute("""
        INSERT INTO incidents (
            incident_id, title, type, severity, status, affected_merchants,
            affected_transactions, potential_exposure, recoverable_exposure,
            primary_gateway, error_code, anomaly_score, source, detected_at, description, target_entity_id
        ) VALUES (
            'INC-2839', 'Settlement Delay Past SLA on Batch #991', 'stuck_settlement',
            'medium', 'open', 1, 1, 185000.0, 185000.0,
            'Gateway_ICICI', 'ERR_SETTLE_TIMEOUT', 0.884, 'synthetic', ?,
            'Settlement batch #991 delayed beyond 72h SLA. Customer account debited, merchant nodal settlement unconfirmed.',
            'pay_Stuck_7712'
        )
    """, ((datetime.utcnow() - timedelta(hours=5)).isoformat(),))

    cursor.execute("INSERT OR IGNORE INTO orders VALUES ('ord_Stuck_7712', 'merch_Nova_Store', 'cust_0001', 185000.0, 'INR', 'paid', 'synthetic', ?, ?)", (base_time.isoformat(), base_time.isoformat()))
    cursor.execute("INSERT OR IGNORE INTO payments VALUES ('pay_Stuck_7712', 'ord_Stuck_7712', 'merch_Nova_Store', 'cust_0001', 185000.0, 'INR', 'captured', 'netbanking', 'Gateway_ICICI', 'synthetic', ?, ?, ?, ?, ?, NULL, NULL, 1)", (base_time.isoformat(), base_time.isoformat(), base_time.isoformat(), base_time.isoformat(), base_time.isoformat()))
    cursor.execute("INSERT OR IGNORE INTO settlements VALUES ('set_STUCK_991', 'merch_Nova_Store', 'pay_Stuck_7712', 185000.0, NULL, 'stuck', 'synthetic', NULL, ?, 78.5)", ((base_time + timedelta(hours=24)).isoformat(),))

    cursor.execute("""
        INSERT INTO incidents (
            incident_id, title, type, severity, status, affected_merchants,
            affected_transactions, potential_exposure, recoverable_exposure,
            primary_gateway, error_code, anomaly_score, source, detected_at, description, target_entity_id
        ) VALUES (
            'INC-2838', 'High Frequency Retry Velocity Spike', 'retry_abuse',
            'low', 'open', 1, 1, 31200.0, 31200.0,
            'Gateway_Axis', 'ERR_3DS_TIMEOUT', 0.762, 'synthetic', ?,
            'Abnormal payment retry loop (14 attempts within 2 minutes) from single card token.',
            'pay_Velo_8892'
        )
    """, ((datetime.utcnow() - timedelta(hours=12)).isoformat(),))

    cursor.execute("INSERT OR IGNORE INTO orders VALUES ('ord_Velo_8892', 'merch_Nova_Store', 'cust_0001', 31200.0, 'INR', 'attempted', 'synthetic', ?, ?)", (base_time.isoformat(), base_time.isoformat()))
    cursor.execute("INSERT OR IGNORE INTO payments VALUES ('pay_Velo_8892', 'ord_Velo_8892', 'merch_Nova_Store', 'cust_0001', 31200.0, 'INR', 'failed', 'card', 'Gateway_Axis', 'synthetic', ?, NULL, ?, ?, ?, 'ERR_3DS_TIMEOUT', 'Customer 3DS authorization timeout', 14)", (base_time.isoformat(), base_time.isoformat(), base_time.isoformat(), base_time.isoformat()))

    # 7. Seed Historical Cases
    historical = case_memory._get_default_cases()
    for h in historical:
        cursor.execute("""
            INSERT OR REPLACE INTO historical_cases (
                incident_id, title, type, gateway, symptoms_json, root_cause, resolution, financial_exposure, outcome, summary_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            h["incident_id"], h["title"], h["type"], h["gateway"],
            json.dumps(h["symptoms"]), h["root_cause"], h["resolution"],
            h["financial_exposure"], h["outcome"], h["summary_text"]
        ))

    conn.commit()
    conn.close()

    # Rebuild in-memory Money Graph
    money_graph.build_from_db()

    print("=" * 60)
    print(" MONEYOPS AI — SYNTHETIC FINANCIAL LAB SEED COMPLETE")
    print(f" Config: Seed={seed} | Transactions={num_transactions} | Merchants={num_merchants}")
    print(" Database contains 14 relational tables with full data lineage.")
    print("=" * 60)

    return {
        "merchants": num_merchants,
        "customers": len(customers),
        "baseline_transactions": num_transactions,
        "golden_incidents": 4,
        "canonical_events_logged": len(canon_data) + 48,
        "graph_nodes": money_graph.graph.number_of_nodes(),
        "graph_edges": money_graph.graph.number_of_edges()
    }

if __name__ == "__main__":
    seed_database(seed=42)
