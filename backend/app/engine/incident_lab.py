import random
import uuid
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.engine.pipeline import CanonicalEvent, IngestionPipeline

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
        anomaly_type: str = "none",  # "none", "gateway_spike", "refund_spike", "duplicate_refund", "webhook_retry"
        days_back: int = 7
    ) -> Dict[str, Any]:
        random.seed(seed)
        np.random.seed(seed)

        merchants = MERCHANT_PROFILES[:num_merchants]
        base_time = datetime.utcnow() - timedelta(days=days_back)
        canonical_events: List[CanonicalEvent] = []

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

            if anomaly_type == "gateway_spike" and gateway == "Gateway_X" and i > (num_payments * 0.6):
                # Inject 45% failure rate on Gateway_X in second half
                if random.random() < 0.45:
                    is_success = False
                    fail_code = "GATEWAY_TIMEOUT"
                    is_anomalous = True
            else:
                # Normal failure rate (~4%)
                if random.random() < 0.04:
                    is_success = False
                    fail_code = random.choice(FAILURE_CODES)

            if is_anomalous:
                anomalous_records_count += 1

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
            canonical_events.append(CanonicalEvent(
                canonical_id=wh_id,
                source="incident_lab",
                event_type=f"payment.{pay_status}",
                entity_type="webhook",
                entity_id=payment_id,
                merchant_id=merch["id"],
                amount=0.0,
                status="delivered",
                timestamp=time_str,
                payload={
                    "external_event_id": f"x_evt_lab_pay_{i:06d}",
                    "signature_valid": True,
                    "payment_id": payment_id
                }
            ))
            generated_webhooks += 1

            # D. Refund Generation
            if is_success:
                refund_prob = merch["refund_rate"]
                if anomaly_type == "refund_spike" and merch["id"] == "merch_Nova_Store" and i > (num_payments * 0.5):
                    # Inject 14% refund rate for Nova Store
                    refund_prob = 0.14
                    is_anomalous = True

                if random.random() < refund_prob:
                    refund_count = 1
                    if anomaly_type == "duplicate_refund" and i % 7 == 0:
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

        # 3. Ingest Everything through the Unified IngestionPipeline
        ingest_stats = IngestionPipeline.ingest_batch(canonical_events)

        return {
            "status": "success",
            "seed": seed,
            "anomaly_injected": anomaly_type,
            "anomalous_events_count": anomalous_records_count,
            "merchants_configured": num_merchants,
            "total_canonical_events": len(canonical_events),
            "orders_ingested": ingest_stats["orders"],
            "payments_ingested": ingest_stats["payments"],
            "refunds_ingested": ingest_stats["refunds"],
            "webhooks_ingested": ingest_stats["webhooks"]
        }

incident_lab = IncidentLabGenerator()
