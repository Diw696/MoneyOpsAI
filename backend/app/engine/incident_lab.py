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
# Which code dominates a gateway_spike's injected failures is itself real
# scenario variety — a timeout concentration and an auth-failure concentration
# are genuinely different operational stories the title/evidence can reflect.
GATEWAY_SPIKE_FAILURE_CODES = ["GATEWAY_TIMEOUT", "AUTH_FAILED", "BAD_REQUEST_ERROR"]

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
        days_back: int = 2
    ) -> Dict[str, Any]:
        random.seed(seed)
        np.random.seed(seed)

        merchants = MERCHANT_PROFILES[:num_merchants]
        # Anchored to "now", not a fixed historical window — every call is a new
        # batch of simulated production events arriving after whatever came before
        # it, not a redraw of the same fixed world.
        base_time = datetime.utcnow() - timedelta(days=days_back)
        canonical_events: List[CanonicalEvent] = []

        # Every generated record this run gets IDs namespaced by a unique run token
        # so a new batch is additive (upserts never collide with a prior run's rows)
        # instead of silently overwriting the previous run's payments/orders/refunds
        # under reused IDs — this is what makes "Generate New Simulation" actually
        # grow a continuous simulated production stream rather than just redrawing
        # the same fixed-size world every time.
        run_token = uuid.uuid4().hex[:8]

        # "auto" resolves into a genuinely realistic OUTCOME distribution, not "always
        # an incident": most batches are ordinary background noise (no anomaly at
        # all), most of the rest inject exactly one coherent scenario, and a small
        # minority inject two independent, still internally-coherent scenarios in the
        # same batch (a compound/multi-signal incident window). An explicit
        # anomaly_type (a caller that wants one specific, repeatable demo scenario)
        # bypasses this distribution entirely and keeps the original fixed target/
        # severity so existing callers and tests stay deterministic and unsurprised.
        is_auto = anomaly_type in ("auto", "random")

        # Recent-history awareness: never let "auto" land on the EXACT same
        # (scenario combo, target) pair the most recent runs already used —
        # that's what produced "Nova refund surge" three times in a row.
        # Reusing a merchant/gateway is still fine as long as the scenario
        # actually injected is materially different (per-run key is the full
        # joined (anomaly_type, target) tuple, so a different scenario type
        # against the same entity is never blocked).
        recent_combos = set()
        if is_auto:
            try:
                _conn = get_db_connection()
                _c = _conn.cursor()
                _c.execute("SELECT anomaly_type, target_entity_id FROM incident_lab_runs ORDER BY generated_at DESC LIMIT 3;")
                for _r in _c.fetchall():
                    recent_combos.add((_r["anomaly_type"], _r["target_entity_id"]))
                _c.close()
                _conn.close()
            except Exception:
                recent_combos = set()

        merchant_scenario_kinds = ("refund_spike", "duplicate_refund", "webhook_delivery_failure")
        scenario_target: Dict[str, str] = {}
        shared_merchant_id: Optional[str] = None
        gateway_fail_code = "GATEWAY_TIMEOUT"

        if is_auto:
            outcome = None
            active_scenarios: List[str] = []
            for _attempt in range(6):
                roll = random.random()
                # ~88% of batches inject a real, detectable anomaly — a
                # monitoring system that cries wolf on every scan is not
                # credible, but neither is one that never finds anything.
                if roll < 0.12:
                    candidate_outcome = "none"
                    candidate_scenarios: List[str] = []
                elif roll < 0.75:
                    candidate_outcome = "single"
                    candidate_scenarios = [random.choice(SCENARIO_TYPES)]
                else:
                    candidate_outcome = "compound"
                    candidate_scenarios = random.sample(SCENARIO_TYPES, 2)

                if candidate_outcome == "none":
                    outcome, active_scenarios = candidate_outcome, candidate_scenarios
                    break

                # Resolve the actual target now (not a throwaway peek) — merchant
                # scenarios in a compound batch share one merchant pick, gateway
                # gets its own. This IS the target used later; nothing re-draws it.
                candidate_target: Dict[str, str] = {}
                candidate_merchant = None
                for _scen in candidate_scenarios:
                    if _scen == "gateway_spike":
                        candidate_target[_scen] = random.choice(GATEWAYS)
                    else:
                        if candidate_merchant is None:
                            candidate_merchant = random.choice(merchants)["id"]
                        candidate_target[_scen] = candidate_merchant
                candidate_key = (
                    "+".join(candidate_scenarios),
                    "+".join(dict.fromkeys(candidate_target.values()))
                )

                if candidate_key not in recent_combos or _attempt == 5:
                    outcome, active_scenarios = candidate_outcome, candidate_scenarios
                    scenario_target = candidate_target
                    shared_merchant_id = candidate_merchant
                    break
                # else: retry — draw a fresh roll/scenario/target next loop.
        else:
            outcome = "none" if anomaly_type == "none" else "single"
            active_scenarios = [] if anomaly_type == "none" else [anomaly_type]

        # Resolve one severity magnitude per active scenario (target already
        # resolved above for auto mode; explicit calls keep fixed targets here).
        scenario_severity: Dict[str, float] = {}

        for scen in active_scenarios:
            if scen == "gateway_spike":
                if not is_auto:
                    scenario_target[scen] = "Gateway_X"
                # A gateway's total accumulated volume only ever grows across
                # every Incident Lab batch ever generated (additive, never
                # purged) — with the target chosen fresh at random each batch
                # (not sticky), a single batch's injected spike has to clear an
                # ever-larger population on its own. A materially higher fail
                # rate keeps a single batch's own signal detectable for
                # realistic session lengths without needing gateway stickiness.
                scenario_severity[scen] = round(random.uniform(0.45, 0.75), 2) if is_auto else 0.45
                # Which failure code dominates is itself real, evidence-bearing
                # variety — a timeout concentration and an auth-failure
                # concentration are genuinely different operational stories,
                # not just the same incident with a different number. Explicit
                # calls keep the original fixed GATEWAY_TIMEOUT for backward
                # compatibility with existing callers/tests.
                gateway_fail_code = random.choice(GATEWAY_SPIKE_FAILURE_CODES) if is_auto else "GATEWAY_TIMEOUT"
            elif scen in merchant_scenario_kinds:
                if not is_auto:
                    shared_merchant_id = "merch_Nova_Store"
                    scenario_target[scen] = shared_merchant_id
                if scen == "refund_spike":
                    scenario_severity[scen] = round(random.uniform(0.10, 0.20), 3) if is_auto else 0.14
                elif scen == "webhook_delivery_failure":
                    scenario_severity[scen] = round(random.uniform(0.25, 0.50), 2) if is_auto else 0.40
                # duplicate_refund has no continuous severity dial, only a boosted
                # refund-eligibility probability applied inline below.

        # A wider window (starting earlier in the batch) means more absolute
        # anomalous events survive dilution once split across the real default
        # of 10 merchants / 5 gateways — 0.45-0.70 was calibrated against a
        # 5-merchant test configuration and under-powered every scenario at the
        # real 10-merchant default, which is why the same one or two entities
        # kept dominating detection regardless of what a batch actually injected.
        anomaly_start_frac = round(random.uniform(0.20, 0.45), 2) if is_auto else 0.6

        # Legacy single-target fields, kept for the loop below and for existing
        # single-scenario callers/tests that reason about "the" target.
        target_gateway = scenario_target.get("gateway_spike")
        target_merchant_id = shared_merchant_id
        gateway_fail_rate = scenario_severity.get("gateway_spike", 0.45)
        refund_spike_rate = scenario_severity.get("refund_spike", 0.14)
        webhook_fail_rate = scenario_severity.get("webhook_delivery_failure", 0.40)

        resolved_anomaly_type = "+".join(active_scenarios) if active_scenarios else "none"
        severity_magnitude = max(scenario_severity.values()) if scenario_severity else None

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

            order_id = f"order_lab_{run_token}_{i:06d}"
            payment_id = f"pay_lab_{run_token}_{i:06d}"
            method = random.choice(PAYMENT_METHODS)
            gateway = random.choice(GATEWAYS)

            # Determine Success/Failure Probability based on Anomaly Injection
            is_success = True
            fail_code = None
            is_anomalous = False

            if "gateway_spike" in active_scenarios and gateway == target_gateway and i > (num_payments * anomaly_start_frac):
                # Inject an elevated failure rate on the chosen target gateway
                # for the back portion of the run (this scenario's "incident window").
                if random.random() < gateway_fail_rate:
                    is_success = False
                    fail_code = gateway_fail_code
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
            wh_id = f"wh_lab_{run_token}_pay_{i:06d}"
            wh_status = "delivered"
            if "webhook_delivery_failure" in active_scenarios and merch["id"] == target_merchant_id and i > (num_payments * anomaly_start_frac):
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
                    "external_event_id": f"x_evt_lab_{run_token}_pay_{i:06d}",
                    "signature_valid": wh_status != "failed",
                    "payment_id": payment_id
                }
            ))
            generated_webhooks += 1

            # D. Refund Generation
            if is_success:
                refund_prob = merch["refund_rate"]
                in_target_window = merch["id"] == target_merchant_id and i > (num_payments * anomaly_start_frac)

                if "refund_spike" in active_scenarios and in_target_window:
                    # Inject an elevated refund rate for the chosen target merchant
                    refund_prob = refund_spike_rate
                    is_anomalous = True
                elif "duplicate_refund" in active_scenarios and in_target_window:
                    # A merchant's baseline refund rate (often <2%) is too low for a
                    # duplicate-refund race condition to actually show up within a
                    # few hundred payments, so raise the odds a refund happens at all
                    # for the target merchant during the incident window — the
                    # duplication itself still only hits every 3rd of those. At the
                    # real default demo settings (10 merchants sharing one batch),
                    # a target merchant's window share is already thin; a 1-in-7
                    # duplication cadence on top of that under-powered the scenario
                    # to the point it frequently produced zero actual duplicates.
                    refund_prob = max(refund_prob, 0.25)

                if random.random() < refund_prob:
                    refund_count = 1
                    if "duplicate_refund" in active_scenarios and in_target_window and i % 3 == 0:
                        # Inject duplicate refund race condition (2 instant refunds on same payment)
                        refund_count = 2
                        is_anomalous = True

                    for r_idx in range(refund_count):
                        rfnd_id = f"rfnd_lab_{run_token}_{i:06d}_{r_idx+1}"
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

        # 3. Ingest through the unified IngestionPipeline. No purge here: this batch's
        # IDs are namespaced by run_token (never collide with an earlier run's rows),
        # so this run's events are APPENDED to the simulated production stream —
        # prior batches, and any incidents already investigated against them, stay
        # intact. This is what makes Incident Lab a continuous event source rather
        # than a one-shot dataset generator that redraws the same fixed world.
        ingest_stats = IngestionPipeline.ingest_batch(canonical_events)

        target_types = [
            ("gateway" if s == "gateway_spike" else "merchant")
            for s in active_scenarios
        ]
        target_entity_type_label = "+".join(dict.fromkeys(target_types)) if target_types else None
        target_entity_id_label = "+".join(dict.fromkeys(scenario_target.values())) if scenario_target else None

        # 4. Record this run so it can be identified and reproduced by its seed.
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
            target_entity_type_label, target_entity_id_label,
            severity_magnitude, num_payments, anomalous_records_count,
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        cur.close()
        conn.close()

        return {
            "status": "success",
            "run_id": run_id,
            "run_token": run_token,
            "seed": seed,
            "outcome": outcome,
            "anomaly_requested": anomaly_type,
            "anomaly_injected": resolved_anomaly_type,
            "scenarios_injected": active_scenarios,
            "target_entity": target_entity_id_label,
            "anomalous_events_count": anomalous_records_count,
            "merchants_configured": num_merchants,
            "total_canonical_events": len(canonical_events),
            "orders_ingested": ingest_stats["orders"],
            "payments_ingested": ingest_stats["payments"],
            "refunds_ingested": ingest_stats["refunds"],
            "webhooks_ingested": ingest_stats["webhooks"]
        }

incident_lab = IncidentLabGenerator()
