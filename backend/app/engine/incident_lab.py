import random
import uuid
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.engine.pipeline import CanonicalEvent, IngestionPipeline
from app.engine.database import get_db_connection

# The four scenario types this generator can inject, matching the ones the
# evaluation harness and Gemini investigation agent already reason about
# elsewhere in this project.
SCENARIO_TYPES = ["gateway_spike", "refund_spike", "duplicate_refund", "webhook_delivery_failure"]

MERCHANT_PROFILES = [
    {"id": "merch_Nova_Store", "name": "Nova Lifestyle & Fashion", "category": "ecommerce", "refund_rate": 0.018},
    {"id": "merch_CloudScale", "name": "CloudScale AI Systems", "category": "saas", "refund_rate": 0.005},
    {"id": "merch_UrbanBites", "name": "UrbanBites Quick Commerce", "category": "food_delivery", "refund_rate": 0.022},
    {"id": "merch_ZenithTravel", "name": "Zenith International Travels", "category": "travel", "refund_rate": 0.035},
    {"id": "merch_PayPulse", "name": "PayPulse Gaming Studio", "category": "gaming", "refund_rate": 0.012},
    {"id": "merch_ApexDigital", "name": "Apex Digital Electronics", "category": "ecommerce", "refund_rate": 0.015},
    {"id": "merch_BlueHorizon", "name": "Blue Horizon Logistics", "category": "logistics", "refund_rate": 0.008},
    {"id": "merch_VanguardHealth", "name": "Vanguard Diagnostics", "category": "healthcare", "refund_rate": 0.010},
    {"id": "merch_AuraJewels", "name": "Aura Luxury Jewels", "category": "luxury", "refund_rate": 0.004},
    {"id": "merch_KiteFin", "name": "Kite Neo Wealth", "category": "fintech", "refund_rate": 0.002},
]

GATEWAYS = ["Gateway_HDFC", "Gateway_ICICI", "Gateway_Axis", "Gateway_SBI", "Gateway_X"]
PAYMENT_METHODS = ["upi", "card", "netbanking", "wallet"]
FAILURE_CODES = ["BAD_REQUEST_ERROR", "INSUFFICIENT_FUNDS", "GATEWAY_TIMEOUT", "AUTH_FAILED", "PAYMENT_CANCELLED"]

class IncidentLabGenerator:
    """
    Incident Lab: Controlled, reproducible financial lifecycle & incident dataset generator.
    Produces CanonicalEvents tagged with source="incident_lab" and pushes them through IngestionPipeline.
    """

    @classmethod
    def generate_dataset(
        cls,
        seed: int = 42,
        num_payments: int = 1000,
        num_merchants: int = 10,
        anomaly_type: str = "auto",  # "auto" (random each run), "none", or one of SCENARIO_TYPES
        days_back: int = 7
    ) -> Dict[str, Any]:
        random.seed(seed)
        np.random.seed(seed)

        merchants = MERCHANT_PROFILES[:num_merchants]
        base_time = datetime.utcnow() - timedelta(days=days_back)
        canonical_events: List[CanonicalEvent] = []

        # "auto" resolves into a random scenario type AND a random target, varying
        # every call — this is what the "Generate New Simulation" UI action uses.
        # An explicit anomaly_type (e.g. a caller that wants a specific, repeatable
        # demo scenario) keeps the original fixed targets (Gateway_X / Nova Store)
        # so existing callers and tests stay deterministic and unsurprised.
        is_auto = anomaly_type in ("auto", "random")
        resolved_anomaly_type = random.choice(SCENARIO_TYPES) if is_auto else anomaly_type

        if is_auto:
            target_gateway = random.choice(GATEWAYS) if resolved_anomaly_type == "gateway_spike" else None
            target_merchant = random.choice(merchants) if resolved_anomaly_type in ("refund_spike", "duplicate_refund", "webhook_delivery_failure") else None
            target_merchant_id = target_merchant["id"] if target_merchant else None
        else:
            target_gateway = "Gateway_X" if resolved_anomaly_type == "gateway_spike" else None
            target_merchant_id = "merch_Nova_Store" if resolved_anomaly_type in ("refund_spike", "duplicate_refund", "webhook_delivery_failure") else None

        # Same reasoning for severity: only vary it in "auto" mode. An explicit call
        # keeps the original fixed magnitudes so existing callers/tests that assert a
        # minimum injected failure rate stay reliably above their threshold.
        if is_auto:
            anomaly_start_frac = round(random.uniform(0.45, 0.70), 2)
            gateway_fail_rate = round(random.uniform(0.30, 0.55), 2)
            refund_spike_rate = round(random.uniform(0.10, 0.20), 3)
            webhook_fail_rate = round(random.uniform(0.25, 0.50), 2)
        else:
            anomaly_start_frac = 0.6
            gateway_fail_rate = 0.45
            refund_spike_rate = 0.14
            webhook_fail_rate = 0.40

        severity_magnitude = {
            "gateway_spike": gateway_fail_rate,
            "refund_spike": refund_spike_rate,
            "duplicate_refund": None,
            "webhook_delivery_failure": webhook_fail_rate,
            "none": None
        }.get(resolved_anomaly_type)

        # 1. Generate Merchants as CanonicalEvents
        for m in merchants:
            canonical_events.append(CanonicalEvent(
                canonical_id=f"can_merch_{m['id']}",
                source="incident_lab",
                event_type="merchant.created",
                entity_type="merchant",
                entity_id=m["id"],
                merchant_id=m["id"],
                amount=0.0,
                status="active",
                timestamp=(base_time - timedelta(days=30)).isoformat(),
                payload={
                    "merchant_name": m["name"],
                    "category": m["category"],
                    "baseline_refund_rate": m["refund_rate"]
                }
            ))

        # 2. Generate Orders, Payments, Refunds, and Webhooks
        generated_orders = 0
        generated_payments = 0
        generated_refunds = 0
        generated_webhooks = 0
        anomalous_records_count = 0

        for i in range(1, num_payments + 1):
            tx_time = base_time + timedelta(seconds=i * int(days_back * 86400 / max(num_payments, 1)))
            time_str = tx_time.isoformat()
            merch = random.choice(merchants)
            
            # Amount: Log-normal distribution (average ~₹2,500, max ₹150,000)
            amt = round(float(np.random.lognormal(mean=7.2, sigma=0.8)), 2)
            amt = max(100.0, min(amt, 150000.0))

            order_id = f"order_lab_{i:06d}"
            payment_id = f"pay_lab_{i:06d}"
            method = random.choice(PAYMENT_METHODS)
            gateway = random.choice(GATEWAYS)

            # Determine Success/Failure Probability based on Anomaly Injection
            is_success = True
            fail_code = None
            is_anomalous = False

            if resolved_anomaly_type == "gateway_spike" and gateway == target_gateway and i > (num_payments * anomaly_start_frac):
                # Inject an elevated failure rate on the chosen target gateway
                # for the back portion of the run (this scenario's "incident window").
                if random.random() < gateway_fail_rate:
                    is_success = False
                    fail_code = "GATEWAY_TIMEOUT"
                    is_anomalous = True
            else:
                # Normal failure rate (~4%)
                if random.random() < 0.04:
                    is_success = False
                    fail_code = random.choice(FAILURE_CODES)

            # A. Order Event
            order_status = "paid" if is_success else "attempted"
            canonical_events.append(CanonicalEvent(
                canonical_id=f"can_ord_{order_id}",
                source="incident_lab",
                event_type=f"order.{order_status}",
                entity_type="order",
                entity_id=order_id,
                merchant_id=merch["id"],
                amount=amt,
                status=order_status,
                timestamp=time_str,
                payload={"notes": {"purpose": "Incident Lab Order", "merchant_id": merch["id"]}}
            ))
            generated_orders += 1

            # B. Payment Event
            pay_status = "captured" if is_success else "failed"
            canonical_events.append(CanonicalEvent(
                canonical_id=f"can_pay_{payment_id}",
                source="incident_lab",
                event_type=f"payment.{pay_status}",
                entity_type="payment",
                entity_id=payment_id,
                merchant_id=merch["id"],
                amount=amt,
                status=pay_status,
                timestamp=time_str,
                payload={
                    "order_id": order_id,
                    "method": method,
                    "gateway": gateway,
                    "failure_code": fail_code,
                    "error_description": f"Failed via {gateway} ({fail_code})" if fail_code else None,
                    "retry_count": 1 if not is_success else 0,
                    "captured_at": time_str if is_success else None
                }
            ))
            generated_payments += 1

            # C. Webhook Event for Payment
            wh_id = f"wh_lab_pay_{i:06d}"
            wh_status = "delivered"
            if resolved_anomaly_type == "webhook_delivery_failure" and merch["id"] == target_merchant_id and i > (num_payments * anomaly_start_frac):
                if random.random() < webhook_fail_rate:
                    wh_status = "failed"
                    is_anomalous = True

            canonical_events.append(CanonicalEvent(
                canonical_id=wh_id,
                source="incident_lab",
                event_type=f"payment.{pay_status}",
                entity_type="webhook",
                entity_id=payment_id,
                merchant_id=merch["id"],
                amount=0.0,
                status=wh_status,
                timestamp=time_str,
                payload={
                    "external_event_id": f"x_evt_lab_pay_{i:06d}",
                    "signature_valid": wh_status != "failed",
                    "payment_id": payment_id
                }
            ))
            generated_webhooks += 1

            # D. Refund Generation
            if is_success:
                refund_prob = merch["refund_rate"]
                in_target_window = merch["id"] == target_merchant_id and i > (num_payments * anomaly_start_frac)

                if resolved_anomaly_type == "refund_spike" and in_target_window:
                    # Inject an elevated refund rate for the chosen target merchant
                    refund_prob = refund_spike_rate
                    is_anomalous = True
                elif resolved_anomaly_type == "duplicate_refund" and in_target_window:
                    # A merchant's baseline refund rate (often <2%) is too low for a
                    # duplicate-refund race condition to actually show up within a
                    # few hundred payments, so raise the odds a refund happens at all
                    # for the target merchant during the incident window — the
                    # duplication itself still only hits every 7th of those.
                    refund_prob = max(refund_prob, 0.25)

                if random.random() < refund_prob:
                    refund_count = 1
                    if resolved_anomaly_type == "duplicate_refund" and in_target_window and i % 7 == 0:
                        # Inject duplicate refund race condition (2 instant refunds on same payment)
                        refund_count = 2
                        is_anomalous = True

                    for r_idx in range(refund_count):
                        rfnd_id = f"rfnd_lab_{i:06d}_{r_idx+1}"
                        rfnd_time = tx_time + timedelta(hours=random.randint(1, 48))
                        rfnd_time_str = rfnd_time.isoformat()

                        canonical_events.append(CanonicalEvent(
                            canonical_id=f"can_rfnd_{rfnd_id}",
                            source="incident_lab",
                            event_type="refund.processed",
                            entity_type="refund",
                            entity_id=rfnd_id,
                            merchant_id=merch["id"],
                            amount=amt,
                            status="processed",
                            timestamp=rfnd_time_str,
                            payload={
                                "payment_id": payment_id,
                                "speed": "instant" if refund_count > 1 else "normal",
                                "processed_at": rfnd_time_str
                            }
                        ))
                        generated_refunds += 1

            # Count this iteration once, after payment/webhook/refund injection have
            # all had a chance to mark it anomalous (a refund-spike or duplicate-refund
            # record would otherwise be missed since those are decided after the
            # original mid-loop count point).
            if is_anomalous:
                anomalous_records_count += 1

        # 3. Replace the previous Incident Lab dataset with this run's, scoped strictly
        # to source='incident_lab' — this can never touch real razorpay_test rows.
        # Without this, a new run with a different scenario/target/refund-count would
        # only overwrite the payment/order IDs it reuses and leave stale rows behind
        # from whatever the previous run generated (e.g. orphaned refunds), producing
        # an internally incoherent mix of two unrelated scenarios' data.
        purge_conn = get_db_connection()
        purge_cur = purge_conn.cursor()
        for table in ("refunds", "webhook_events", "payments", "orders"):
            purge_cur.execute(f"DELETE FROM {table} WHERE source = 'incident_lab';")
        purge_conn.commit()
        purge_cur.close()
        purge_conn.close()

        # 4. Ingest Everything through the Unified IngestionPipeline
        ingest_stats = IngestionPipeline.ingest_batch(canonical_events)

        # 4. Record this run so it can be identified and regenerated by its seed.
        run_id = f"lab_run_{uuid.uuid4().hex[:10]}"
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO incident_lab_runs (
                run_id, seed, anomaly_type, target_entity_type, target_entity_id,
                severity_magnitude, num_payments, anomalous_events_count, generated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (
            run_id, seed, resolved_anomaly_type,
            "gateway" if target_gateway else ("merchant" if target_merchant_id else None),
            target_gateway or target_merchant_id,
            severity_magnitude, num_payments, anomalous_records_count,
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        cur.close()
        conn.close()

        return {
            "status": "success",
            "run_id": run_id,
            "seed": seed,
            "anomaly_requested": anomaly_type,
            "anomaly_injected": resolved_anomaly_type,
            "target_entity": target_gateway or target_merchant_id,
            "anomalous_events_count": anomalous_records_count,
            "merchants_configured": num_merchants,
            "total_canonical_events": len(canonical_events),
            "orders_ingested": ingest_stats["orders"],
            "payments_ingested": ingest_stats["payments"],
            "refunds_ingested": ingest_stats["refunds"],
            "webhooks_ingested": ingest_stats["webhooks"]
        }

incident_lab = IncidentLabGenerator()
