from typing import Dict, Any, List, Optional
import numpy as np
from app.engine.database import get_db_connection

class FeatureEngine:
    """
    Feature Engineering Layer for MoneyOps AI.
    Calculates explainable financial metrics and behavioral deviation features
    directly from PostgreSQL tables (payments, merchants, refunds).
    Zero synthetic or hardcoded feature values.
    """

    @classmethod
    def _recent_generation_cutoff(cls, n_runs: int = 4):
        """
        Returns the generated_at of the Nth-most-recent Incident Lab run (or
        None if fewer than N runs exist yet, meaning "no bound").

        Combined per-entity with "since last human decision" (whichever cutoff
        is LATER), this is what keeps a freshly-injected anomaly detectable
        regardless of how large the all-time accumulated population has grown.
        Population-relative statistics computed over UNBOUNDED history dilute
        any single new batch into irrelevance once a long testing/demo session
        has piled up tens of thousands of older rows — "since last decision"
        alone only helps entities that have already been decided on at least
        once; an entity that has simply never been decided on still evaluated
        against its entire history. Bounding to "the last few generated
        batches" fixes that for every entity, decided or not.
        """
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT generated_at FROM incident_lab_runs ORDER BY generated_at DESC LIMIT 1 OFFSET %s;", (max(n_runs, 1) - 1,))
        row = c.fetchone()
        c.close()
        conn.close()
        return row["generated_at"] if row else None

    @classmethod
    def extract_gateway_features(cls) -> List[Dict[str, Any]]:
        """
        Extracts operational features grouped by payment gateway from PostgreSQL.
        Calculates failure rates, peer averages, primary error codes, and financial exposure.
        """
        conn = get_db_connection()
        c = conn.cursor()

        recent_cutoff = cls._recent_generation_cutoff()

        # 1. Gateway Level Aggregations — scoped to activity since the LATER of
        # (a) this gateway's last handled gateway_failure_spike decision, and
        # (b) the start of the last few Incident Lab generation runs. (b) alone
        # is what stops a heavily-tested dev DB from diluting a freshly-injected
        # spike below the detection floor even on a gateway that's never had a
        # decision at all; (a) alone is what stops a resolved/rejected
        # incident's own old evidence from re-triggering with nothing new.
        c.execute("""
            WITH last_decision AS (
                SELECT i.target_entity_id AS gateway, MAX(a.timestamp) AS decided_at
                FROM audit_logs a
                JOIN incidents i ON i.incident_id = a.incident_id
                WHERE i.type = 'gateway_failure_spike' AND a.new_status IN ('executed', 'rejected')
                GROUP BY i.target_entity_id
            )
            SELECT
                payments.gateway,
                COUNT(*) as total_payments,
                SUM(CASE WHEN payments.status = 'captured' THEN 1 ELSE 0 END) as captured_payments,
                SUM(CASE WHEN payments.status = 'failed' THEN 1 ELSE 0 END) as failed_payments,
                ROUND((1.0 * SUM(CASE WHEN payments.status = 'failed' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0))::numeric, 4) as failure_rate,
                ROUND(AVG(payments.amount)::numeric, 2) as avg_amount,
                ROUND(COALESCE(SUM(CASE WHEN payments.status = 'failed' THEN payments.amount ELSE 0 END), 0)::numeric, 2) as potential_exposure,
                COUNT(DISTINCT CASE WHEN payments.status = 'failed' THEN payments.merchant_id ELSE NULL END) as affected_merchants,
                COUNT(DISTINCT CASE WHEN payments.status = 'failed' THEN payments.order_id ELSE NULL END) as affected_orders,
                MAX(payments.source) as source
            FROM payments
            LEFT JOIN last_decision ld ON ld.gateway = payments.gateway
            WHERE payments.gateway IS NOT NULL
              AND payments.ingested_at > GREATEST(
                    COALESCE(ld.decided_at, '1970-01-01'::timestamptz),
                    COALESCE(%s::timestamptz, '1970-01-01'::timestamptz)
                  )
            GROUP BY payments.gateway
            ORDER BY total_payments DESC;
        """, (recent_cutoff,))
        gateways_data = c.fetchall()

        # 2. Extract Top Failure Code per Gateway (same recency scoping)
        c.execute("""
            WITH last_decision AS (
                SELECT i.target_entity_id AS gateway, MAX(a.timestamp) AS decided_at
                FROM audit_logs a
                JOIN incidents i ON i.incident_id = a.incident_id
                WHERE i.type = 'gateway_failure_spike' AND a.new_status IN ('executed', 'rejected')
                GROUP BY i.target_entity_id
            )
            SELECT payments.gateway, payments.failure_code, COUNT(*) as code_count
            FROM payments
            LEFT JOIN last_decision ld ON ld.gateway = payments.gateway
            WHERE payments.status = 'failed' AND payments.failure_code IS NOT NULL
              AND payments.ingested_at > GREATEST(
                    COALESCE(ld.decided_at, '1970-01-01'::timestamptz),
                    COALESCE(%s::timestamptz, '1970-01-01'::timestamptz)
                  )
            GROUP BY payments.gateway, payments.failure_code
            ORDER BY payments.gateway, code_count DESC;
        """, (recent_cutoff,))
        failure_codes_raw = c.fetchall()
        
        top_codes: Dict[str, Dict[str, Any]] = {}
        for r in failure_codes_raw:
            gw = r["gateway"]
            if gw not in top_codes:
                top_codes[gw] = {"code": r["failure_code"], "count": r["code_count"]}

        c.close()
        conn.close()

        if not gateways_data:
            return []

        # 3. Calculate Peer Failure Rates & Deviation Ratios
        total_failed_all = sum(g["failed_payments"] for g in gateways_data)
        total_payments_all = sum(g["total_payments"] for g in gateways_data)
        overall_avg_failure_rate = (total_failed_all / total_payments_all) if total_payments_all > 0 else 0.0

        features_list: List[Dict[str, Any]] = []

        for g in gateways_data:
            gw_name = g["gateway"]
            tot = g["total_payments"]
            failed = g["failed_payments"]
            rate = float(g["failure_rate"] or 0.0)

            # Peer average: failure rate of all other gateways combined
            peer_tot = total_payments_all - tot
            peer_failed = total_failed_all - failed
            peer_rate = (peer_failed / peer_tot) if peer_tot > 0 else overall_avg_failure_rate

            ratio = (rate / peer_rate) if peer_rate > 0 else 1.0
            top_code_info = top_codes.get(gw_name, {"code": "UNKNOWN", "count": 0})
            code_share = (top_code_info["count"] / failed) if failed > 0 else 0.0

            features_list.append({
                "entity_type": "gateway",
                "entity_id": gw_name,
                "total_payments": tot,
                "captured_payments": g["captured_payments"],
                "failed_payments": failed,
                "failure_rate": rate,
                "peer_failure_rate": round(peer_rate, 4),
                "failure_rate_ratio": round(ratio, 2),
                "top_failure_code": top_code_info["code"],
                "top_failure_code_count": top_code_info["count"],
                "top_failure_code_share": round(code_share, 4),
                "avg_amount": float(g["avg_amount"] or 0.0),
                "potential_exposure": float(g["potential_exposure"] or 0.0),
                "affected_merchants": g["affected_merchants"],
                "affected_orders": g["affected_orders"],
                "source": g["source"]
            })

        return features_list

    @classmethod
    def extract_merchant_features(cls) -> List[Dict[str, Any]]:
        """
        Extracts behavioral features per merchant from PostgreSQL.
        Calculates refund rates, deviation from merchant baseline, and failure rates.
        """
        conn = get_db_connection()
        c = conn.cursor()

        recent_cutoff = cls._recent_generation_cutoff()

        c.execute("""
            WITH last_decision AS (
                -- A human decision (executed OR rejected) on this merchant's
                -- refund-spike incident resets what counts as "new" evidence —
                -- otherwise a rejected/resolved incident's own old refunds would
                -- immediately re-trigger detection on the very next scan.
                SELECT i.target_entity_id AS merchant_id, MAX(a.timestamp) AS decided_at
                FROM audit_logs a
                JOIN incidents i ON i.incident_id = a.incident_id
                WHERE i.type = 'merchant_refund_spike' AND a.new_status IN ('executed', 'rejected')
                GROUP BY i.target_entity_id
            )
            SELECT
                m.merchant_id,
                m.name as merchant_name,
                m.category,
                m.baseline_refund_rate,
                COALESCE(p.total_payments, 0) as total_payments,
                COALESCE(p.captured_payments, 0) as captured_payments,
                COALESCE(p.failed_payments, 0) as failed_payments,
                COALESCE(p.avg_amount, 0) as avg_amount,
                COALESCE(r.total_refunds, 0) as total_refunds,
                COALESCE(r.refund_amount, 0) as total_refund_amount,
                COALESCE(p.source, 'incident_lab') as source
            FROM merchants m
            LEFT JOIN (
                SELECT
                    payments.merchant_id,
                    COUNT(*) as total_payments,
                    SUM(CASE WHEN payments.status = 'captured' THEN 1 ELSE 0 END) as captured_payments,
                    SUM(CASE WHEN payments.status = 'failed' THEN 1 ELSE 0 END) as failed_payments,
                    AVG(payments.amount) as avg_amount,
                    -- Majority vote, not MAX(): a merchant with a handful of stray
                    -- real payments mixed into thousands of Incident Lab payments
                    -- (the shared demo Razorpay account has no real merchant
                    -- concept, so real activity defaults to this merchant_id) must
                    -- not have its overwhelmingly-synthetic incident mislabeled as
                    -- real just because 'razorpay_test' sorts after 'incident_lab'.
                    MODE() WITHIN GROUP (ORDER BY payments.source) as source
                FROM payments
                LEFT JOIN last_decision ld ON ld.merchant_id = payments.merchant_id
                WHERE payments.ingested_at > GREATEST(
                      COALESCE(ld.decided_at, '1970-01-01'::timestamptz),
                      COALESCE(%s::timestamptz, '1970-01-01'::timestamptz)
                    )
                GROUP BY payments.merchant_id
            ) p ON m.merchant_id = p.merchant_id
            LEFT JOIN (
                SELECT
                    refunds.merchant_id,
                    COUNT(*) as total_refunds,
                    SUM(refunds.amount) as refund_amount
                FROM refunds
                LEFT JOIN last_decision ld ON ld.merchant_id = refunds.merchant_id
                WHERE refunds.ingested_at > GREATEST(
                      COALESCE(ld.decided_at, '1970-01-01'::timestamptz),
                      COALESCE(%s::timestamptz, '1970-01-01'::timestamptz)
                    )
                GROUP BY refunds.merchant_id
            ) r ON m.merchant_id = r.merchant_id
            ORDER BY total_payments DESC;
        """, (recent_cutoff, recent_cutoff))
        rows = c.fetchall()
        c.close()
        conn.close()

        merchant_features: List[Dict[str, Any]] = []
        for r in rows:
            tot_p = r["total_payments"]
            tot_r = r["total_refunds"]
            actual_rate = (tot_r / tot_p) if tot_p > 0 else 0.0
            baseline = float(r["baseline_refund_rate"] or 0.015)
            deviation = actual_rate - baseline
            ratio = (actual_rate / baseline) if baseline > 0 else 1.0

            merchant_features.append({
                "entity_type": "merchant",
                "entity_id": r["merchant_id"],
                "merchant_name": r["merchant_name"],
                "category": r["category"],
                "total_payments": tot_p,
                "captured_payments": r["captured_payments"],
                "failed_payments": r["failed_payments"],
                "total_refunds": tot_r,
                "actual_refund_rate": round(actual_rate, 4),
                "baseline_refund_rate": round(baseline, 4),
                "refund_rate_deviation": round(deviation, 4),
                "refund_rate_ratio": round(ratio, 2),
                "avg_amount": round(float(r["avg_amount"]), 2),
                "potential_exposure": round(float(r["total_refund_amount"]), 2),
                "source": r["source"]
            })

        return merchant_features

    @classmethod
    def extract_webhook_features(cls) -> List[Dict[str, Any]]:
        """
        Extracts per-merchant webhook delivery reliability from PostgreSQL, joining
        webhook_events back to the merchant via its parent payment (webhook_events
        has no merchant_id column of its own; entity_id is the payment_id).
        """
        conn = get_db_connection()
        c = conn.cursor()
        recent_cutoff = cls._recent_generation_cutoff()
        c.execute("""
            WITH last_decision AS (
                SELECT i.target_entity_id AS merchant_id, MAX(a.timestamp) AS decided_at
                FROM audit_logs a
                JOIN incidents i ON i.incident_id = a.incident_id
                WHERE i.type = 'merchant_webhook_failure' AND a.new_status IN ('executed', 'rejected')
                GROUP BY i.target_entity_id
            )
            SELECT
                p.merchant_id,
                m.name as merchant_name,
                COUNT(*) as total_webhooks,
                SUM(CASE WHEN w.delivery_status = 'failed' THEN 1 ELSE 0 END) as failed_webhooks,
                COALESCE(SUM(CASE WHEN w.delivery_status = 'failed' THEN p.amount ELSE 0 END), 0) as failed_webhook_exposure,
                MODE() WITHIN GROUP (ORDER BY w.source) as source
            FROM webhook_events w
            JOIN payments p ON p.payment_id = w.entity_id
            JOIN merchants m ON m.merchant_id = p.merchant_id
            LEFT JOIN last_decision ld ON ld.merchant_id = p.merchant_id
            WHERE w.received_at > GREATEST(
                  COALESCE(ld.decided_at, '1970-01-01'::timestamptz),
                  COALESCE(%s::timestamptz, '1970-01-01'::timestamptz)
                )
            GROUP BY p.merchant_id, m.name;
        """, (recent_cutoff,))
        rows = c.fetchall()
        c.close()
        conn.close()

        if not rows:
            return []

        total_failed_all = sum(int(r["failed_webhooks"]) for r in rows)
        total_all = sum(int(r["total_webhooks"]) for r in rows)
        overall_rate = (total_failed_all / total_all) if total_all > 0 else 0.0

        out: List[Dict[str, Any]] = []
        for r in rows:
            tot = int(r["total_webhooks"])
            failed = int(r["failed_webhooks"])
            rate = (failed / tot) if tot > 0 else 0.0
            peer_tot = total_all - tot
            peer_failed = total_failed_all - failed
            peer_rate = (peer_failed / peer_tot) if peer_tot > 0 else overall_rate

            out.append({
                "entity_type": "merchant",
                "entity_id": r["merchant_id"],
                "merchant_name": r["merchant_name"],
                "total_webhooks": tot,
                "failed_webhooks": failed,
                "failure_rate": round(rate, 4),
                "peer_failure_rate": round(peer_rate, 4),
                # Exposure for a webhook incident is the value of PAYMENTS whose
                # confirmation delivery failed (settlement/reconciliation risk),
                # not a refund total — a webhook problem has nothing to do with
                # refund amounts, so reusing refund exposure here would display a
                # number with no real relationship to the incident's evidence.
                "webhook_exposure": round(float(r["failed_webhook_exposure"]), 2),
                "source": r["source"]
            })
        return out

    @classmethod
    def extract_duplicate_refund_features(cls) -> List[Dict[str, Any]]:
        """
        Extracts, per merchant, how many distinct payments received more than one
        refund attempt SINCE that merchant's last HANDLED duplicate-refund
        incident (executed OR rejected — either is a final human decision; or
        ever, if none has been handled) — the signature of a duplicate-refund /
        retry-race incident, distinct from a plain refund-volume spike.

        This is a pure running COUNT with no built-in decay (unlike a rate),
        so it can only ever grow as Incident Lab additively accumulates data —
        without excluding already-handled evidence, a handled duplicate-refund
        incident would immediately re-open on the very next scan from the SAME
        old evidence, even in a batch that injected nothing at all. Scoping to
        "since last human decision" is what makes handling an incident actually
        mean something, while still catching a genuinely NEW duplicate-refund
        batch for the same merchant later.
        """
        conn = get_db_connection()
        c = conn.cursor()
        recent_cutoff = cls._recent_generation_cutoff()
        c.execute("""
            WITH last_resolution AS (
                SELECT i.target_entity_id AS merchant_id, MAX(a.timestamp) AS resolved_at
                FROM audit_logs a
                JOIN incidents i ON i.incident_id = a.incident_id
                WHERE i.type = 'merchant_duplicate_refund' AND a.new_status IN ('executed', 'rejected')
                GROUP BY i.target_entity_id
            ),
            per_payment AS (
                -- Compares against ingested_at (real wall-clock insertion time),
                -- not created_at (a SIMULATED business timestamp Incident Lab
                -- assigns within its own generated window — which can legitimately
                -- land hours into the future relative to actual insertion time,
                -- making it useless for "was this evidence already accounted for
                -- by a resolution that really happened just now" comparisons).
                SELECT r.payment_id, COUNT(*) as refund_count
                FROM refunds r
                JOIN payments pp ON pp.payment_id = r.payment_id
                LEFT JOIN last_resolution lr ON lr.merchant_id = pp.merchant_id
                WHERE r.ingested_at > GREATEST(
                      COALESCE(lr.resolved_at, '1970-01-01'::timestamptz),
                      COALESCE(%s::timestamptz, '1970-01-01'::timestamptz)
                    )
                GROUP BY r.payment_id
            )
            SELECT
                p.merchant_id,
                m.name as merchant_name,
                COUNT(*) FILTER (WHERE per_payment.refund_count > 1) as duplicate_refund_payments,
                COUNT(*) as refunded_payments_total,
                SUM(per_payment.refund_count) as total_refund_rows,
                -- Exposure specific to this scenario: the value tied up in
                -- payments that were refunded MORE THAN ONCE — a distinct number
                -- from "total refund amount", which would also include every
                -- ordinary single refund and overstate the duplicate signature.
                COALESCE(SUM(p.amount) FILTER (WHERE per_payment.refund_count > 1), 0) as duplicate_refund_exposure,
                MODE() WITHIN GROUP (ORDER BY p.source) as source
            FROM per_payment
            JOIN payments p ON p.payment_id = per_payment.payment_id
            JOIN merchants m ON m.merchant_id = p.merchant_id
            GROUP BY p.merchant_id, m.name;
        """, (recent_cutoff,))
        rows = c.fetchall()
        c.close()
        conn.close()
        return [dict(r) for r in rows]

feature_engine = FeatureEngine()
