import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.engine.database import get_db_connection

class InvestigationTools:
    """
    Authoritative Investigation Tools for the Gemini AI Agent.
    Every tool executes direct, parameterized SQL against PostgreSQL
    and returns factual data from the database.
    """

    @staticmethod
    def get_incident(incident_id: str) -> Dict[str, Any]:
        """
        Retrieves the core incident metadata, anomaly score, and initial detection evidence.
        """
        if not incident_id:
            return {"error": "Missing incident_id parameter"}

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM incidents WHERE incident_id = %s;", (incident_id,))
        row = c.fetchone()
        c.close()
        conn.close()

        if not row:
            return {"error": f"Incident '{incident_id}' not found in database"}

        d = dict(row)
        if d.get("evidence_json"):
            try:
                d["evidence"] = json.loads(d["evidence_json"])
            except Exception:
                pass
        return d

    @staticmethod
    def get_gateway_metrics(gateway: str) -> Dict[str, Any]:
        """
        Calculates live performance metrics, failure rates, peer averages, and failure code breakdowns
        for a specific payment gateway.
        """
        if not gateway:
            return {"error": "Missing gateway parameter"}

        conn = get_db_connection()
        c = conn.cursor()

        # 1. Target Gateway Metrics
        c.execute("""
            SELECT 
                COUNT(*) as total_payments,
                SUM(CASE WHEN status = 'captured' THEN 1 ELSE 0 END) as captured_payments,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_payments,
                ROUND((100.0 * SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0))::numeric, 2) as failure_rate_pct,
                ROUND(AVG(amount)::numeric, 2) as avg_amount,
                ROUND(COALESCE(SUM(CASE WHEN status = 'failed' THEN amount ELSE 0 END), 0)::numeric, 2) as potential_exposure_inr,
                COUNT(DISTINCT CASE WHEN status = 'failed' THEN merchant_id ELSE NULL END) as affected_merchants_count
            FROM payments
            WHERE gateway = %s;
        """, (gateway,))
        gw_row = c.fetchone()

        if not gw_row or gw_row["total_payments"] == 0:
            c.close()
            conn.close()
            return {"error": f"No payment activity found for gateway '{gateway}'"}

        # 2. Peer Gateways Average Failure Rate
        c.execute("""
            SELECT 
                ROUND((100.0 * SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0))::numeric, 2) as peer_failure_rate_pct
            FROM payments
            WHERE gateway != %s AND gateway IS NOT NULL;
        """, (gateway,))
        peer_row = c.fetchone()
        peer_rate = float(peer_row["peer_failure_rate_pct"] or 0.0)

        # 3. Failure Code Distribution
        c.execute("""
            SELECT failure_code, COUNT(*) as count,
                   ROUND((100.0 * COUNT(*) / NULLIF(%s, 0))::numeric, 2) as share_pct
            FROM payments
            WHERE gateway = %s AND status = 'failed' AND failure_code IS NOT NULL
            GROUP BY failure_code
            ORDER BY count DESC;
        """, (gw_row["failed_payments"], gateway))
        failure_codes = [dict(r) for r in c.fetchall()]

        c.close()
        conn.close()

        gw_rate = float(gw_row["failure_rate_pct"] or 0.0)
        ratio = round(gw_rate / peer_rate, 2) if peer_rate > 0 else 1.0

        return {
            "gateway": gateway,
            "total_payments": gw_row["total_payments"],
            "captured_payments": gw_row["captured_payments"],
            "failed_payments": gw_row["failed_payments"],
            "failure_rate_pct": gw_rate,
            "peer_failure_rate_pct": peer_rate,
            "failure_rate_ratio": ratio,
            "potential_exposure_inr": float(gw_row["potential_exposure_inr"] or 0.0),
            "affected_merchants_count": gw_row["affected_merchants_count"],
            "failure_code_breakdown": failure_codes
        }

    @staticmethod
    def get_failed_payments(gateway: str, limit: int = 25) -> Dict[str, Any]:
        """
        Retrieves representative failed payment records for a gateway with full forensic attributes.
        """
        if not gateway:
            return {"error": "Missing gateway parameter"}

        limit = min(max(1, limit), 100)
        conn = get_db_connection()
        c = conn.cursor()

        c.execute("""
            SELECT 
                payment_id, order_id, merchant_id, amount, currency, status,
                method, gateway, failure_code, error_description, retry_count,
                created_at, source
            FROM payments
            WHERE gateway = %s AND status = 'failed'
            ORDER BY created_at DESC
            LIMIT %s;
        """, (gateway, limit))
        rows = [dict(r) for r in c.fetchall()]

        c.close()
        conn.close()

        return {
            "gateway": gateway,
            "failed_payments_returned": len(rows),
            "sample_records": rows
        }

    @staticmethod
    def get_affected_merchants(gateway: str) -> Dict[str, Any]:
        """
        Returns a breakdown of all merchants affected by failures on a specific gateway.
        """
        if not gateway:
            return {"error": "Missing gateway parameter"}

        conn = get_db_connection()
        c = conn.cursor()

        c.execute("""
            SELECT 
                m.merchant_id,
                m.name as merchant_name,
                m.category,
                COUNT(p.payment_id) as attempts,
                SUM(CASE WHEN p.status = 'failed' THEN 1 ELSE 0 END) as failures,
                ROUND((100.0 * SUM(CASE WHEN p.status = 'failed' THEN 1 ELSE 0 END) / NULLIF(COUNT(p.payment_id), 0))::numeric, 2) as failure_rate_pct,
                ROUND(COALESCE(SUM(CASE WHEN p.status = 'failed' THEN p.amount ELSE 0 END), 0)::numeric, 2) as merchant_exposure_inr
            FROM merchants m
            JOIN payments p ON m.merchant_id = p.merchant_id
            WHERE p.gateway = %s
            GROUP BY m.merchant_id, m.name, m.category
            HAVING SUM(CASE WHEN p.status = 'failed' THEN 1 ELSE 0 END) > 0
            ORDER BY failures DESC;
        """, (gateway,))
        merchants = [dict(r) for r in c.fetchall()]

        c.close()
        conn.close()

        return {
            "gateway": gateway,
            "affected_merchants_count": len(merchants),
            "merchants": merchants
        }

    @staticmethod
    def get_payment_context(payment_id: str) -> Dict[str, Any]:
        """
        Retrieves complete relational context for a payment: order, merchant, refunds, and webhooks.
        """
        if not payment_id:
            return {"error": "Missing payment_id parameter"}

        conn = get_db_connection()
        c = conn.cursor()

        # 1. Payment
        c.execute("SELECT * FROM payments WHERE payment_id = %s;", (payment_id,))
        pay = c.fetchone()
        if not pay:
            c.close()
            conn.close()
            return {"error": f"Payment '{payment_id}' not found"}

        pay_dict = dict(pay)

        # 2. Order
        order_dict = None
        if pay_dict.get("order_id"):
            c.execute("SELECT * FROM orders WHERE order_id = %s;", (pay_dict["order_id"],))
            ord_row = c.fetchone()
            if ord_row:
                order_dict = dict(ord_row)

        # 3. Merchant
        c.execute("SELECT * FROM merchants WHERE merchant_id = %s;", (pay_dict["merchant_id"],))
        merch_row = c.fetchone()
        merch_dict = dict(merch_row) if merch_row else None

        # 4. Refunds
        c.execute("SELECT * FROM refunds WHERE payment_id = %s;", (payment_id,))
        refunds = [dict(r) for r in c.fetchall()]

        # 5. Webhook Events
        c.execute("SELECT * FROM webhook_events WHERE entity_id = %s;", (payment_id,))
        webhooks = [dict(r) for r in c.fetchall()]

        c.close()
        conn.close()

        return {
            "payment": pay_dict,
            "order": order_dict,
            "merchant": merch_dict,
            "refunds": refunds,
            "webhook_events": webhooks
        }

    @staticmethod
    def get_webhook_activity(gateway: str, limit: int = 50) -> Dict[str, Any]:
        """
        Retrieves webhook delivery status and event logs associated with transactions on the gateway.
        """
        if not gateway:
            return {"error": "Missing gateway parameter"}

        limit = min(max(1, limit), 100)
        conn = get_db_connection()
        c = conn.cursor()

        c.execute("""
            SELECT 
                w.event_id, w.external_event_id, w.event_type, w.entity_id,
                w.signature_valid, w.delivery_status, w.received_at, w.source
            FROM webhook_events w
            JOIN payments p ON w.entity_id = p.payment_id
            WHERE p.gateway = %s
            ORDER BY w.received_at DESC
            LIMIT %s;
        """, (gateway, limit))
        rows = [dict(r) for r in c.fetchall()]

        c.close()
        conn.close()

        return {
            "gateway": gateway,
            "webhook_events_returned": len(rows),
            "events": rows
        }

    @staticmethod
    def get_merchant_metrics(merchant_id: str) -> Dict[str, Any]:
        """
        Calculates a merchant's refund rate against its own historical baseline,
        webhook delivery reliability, and duplicate-refund activity — the three
        merchant-level incident signatures, all from real PostgreSQL aggregates.
        """
        if not merchant_id:
            return {"error": "Missing merchant_id parameter"}

        conn = get_db_connection()
        c = conn.cursor()

        c.execute("SELECT merchant_id, name, category, baseline_refund_rate FROM merchants WHERE merchant_id = %s;", (merchant_id,))
        merch = c.fetchone()
        if not merch:
            c.close()
            conn.close()
            return {"error": f"Merchant '{merchant_id}' not found"}

        c.execute("""
            SELECT COUNT(*) as total_payments,
                   SUM(CASE WHEN status = 'captured' THEN 1 ELSE 0 END) as captured_payments,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_payments
            FROM payments WHERE merchant_id = %s;
        """, (merchant_id,))
        pay_row = c.fetchone()

        c.execute("""
            SELECT COUNT(*) as total_refunds, COALESCE(SUM(r.amount), 0) as refund_amount
            FROM refunds r JOIN payments p ON p.payment_id = r.payment_id
            WHERE p.merchant_id = %s;
        """, (merchant_id,))
        refund_row = c.fetchone()

        c.execute("""
            SELECT r.payment_id, COUNT(*) as refund_count
            FROM refunds r JOIN payments p ON p.payment_id = r.payment_id
            WHERE p.merchant_id = %s
            GROUP BY r.payment_id HAVING COUNT(*) > 1;
        """, (merchant_id,))
        dup_rows = c.fetchall()

        c.execute("""
            SELECT COUNT(*) as total_webhooks,
                   SUM(CASE WHEN w.delivery_status = 'failed' THEN 1 ELSE 0 END) as failed_webhooks
            FROM webhook_events w JOIN payments p ON p.payment_id = w.entity_id
            WHERE p.merchant_id = %s;
        """, (merchant_id,))
        wh_row = c.fetchone()

        c.close()
        conn.close()

        total_payments = int(pay_row["total_payments"] or 0)
        total_refunds = int(refund_row["total_refunds"] or 0)
        actual_rate = (total_refunds / total_payments) if total_payments > 0 else 0.0
        baseline = float(merch["baseline_refund_rate"] or 0.015)
        wh_total = int(wh_row["total_webhooks"] or 0)
        wh_failed = int(wh_row["failed_webhooks"] or 0)

        return {
            "merchant_id": merchant_id,
            "merchant_name": merch["name"],
            "category": merch["category"],
            "total_payments": total_payments,
            "captured_payments": int(pay_row["captured_payments"] or 0),
            "failed_payments": int(pay_row["failed_payments"] or 0),
            "total_refunds": total_refunds,
            "refund_amount_inr": float(refund_row["refund_amount"] or 0.0),
            "actual_refund_rate_pct": round(actual_rate * 100, 2),
            "baseline_refund_rate_pct": round(baseline * 100, 2),
            "refund_rate_ratio": round(actual_rate / baseline, 2) if baseline > 0 else None,
            "duplicate_refund_payments_count": len(dup_rows),
            "duplicate_refund_payment_ids": [r["payment_id"] for r in dup_rows],
            "webhook_total": wh_total,
            "webhook_failed": wh_failed,
            "webhook_failure_rate_pct": round((wh_failed / wh_total) * 100, 2) if wh_total > 0 else 0.0
        }

    @staticmethod
    def get_merchant_refunds(merchant_id: str, limit: int = 25) -> Dict[str, Any]:
        """
        Retrieves representative refund records for a merchant, flagging which
        payments received more than one refund (duplicate-refund forensic evidence).
        """
        if not merchant_id:
            return {"error": "Missing merchant_id parameter"}

        limit = min(max(1, limit), 100)
        conn = get_db_connection()
        c = conn.cursor()

        c.execute("""
            SELECT r.refund_id, r.payment_id, r.amount, r.status, r.speed, r.created_at,
                   COUNT(*) OVER (PARTITION BY r.payment_id) as refunds_on_same_payment
            FROM refunds r JOIN payments p ON p.payment_id = r.payment_id
            WHERE p.merchant_id = %s
            ORDER BY r.created_at DESC
            LIMIT %s;
        """, (merchant_id, limit))
        rows = [dict(r) for r in c.fetchall()]

        c.close()
        conn.close()

        return {
            "merchant_id": merchant_id,
            "refunds_returned": len(rows),
            "sample_records": rows
        }

    @staticmethod
    def get_merchant_webhook_activity(merchant_id: str, limit: int = 50) -> Dict[str, Any]:
        """
        Retrieves webhook delivery status and event logs for a merchant's payments.
        """
        if not merchant_id:
            return {"error": "Missing merchant_id parameter"}

        limit = min(max(1, limit), 100)
        conn = get_db_connection()
        c = conn.cursor()

        c.execute("""
            SELECT w.event_id, w.external_event_id, w.event_type, w.entity_id,
                   w.signature_valid, w.delivery_status, w.received_at, w.source
            FROM webhook_events w JOIN payments p ON w.entity_id = p.payment_id
            WHERE p.merchant_id = %s
            ORDER BY w.received_at DESC
            LIMIT %s;
        """, (merchant_id, limit))
        rows = [dict(r) for r in c.fetchall()]

        c.close()
        conn.close()

        return {
            "merchant_id": merchant_id,
            "webhook_events_returned": len(rows),
            "events": rows
        }

    @staticmethod
    def find_similar_incidents(incident_type: str = None, incident_id: str = None) -> Dict[str, Any]:
        """
        Searches historical incident precedents in PostgreSQL using Case Memory.
        """
        from app.engine.case_memory import case_memory
        
        target_id = incident_id
        if not target_id:
            conn = get_db_connection()
            c = conn.cursor()
            if incident_type:
                c.execute("SELECT incident_id FROM incidents WHERE type = %s AND status = 'open' LIMIT 1;", (incident_type,))
            else:
                c.execute("SELECT incident_id FROM incidents WHERE status = 'open' LIMIT 1;")
            row = c.fetchone()
            c.close()
            conn.close()
            if row:
                target_id = row["incident_id"]

        if target_id:
            similar = case_memory.find_similar_incidents(target_id, limit=3)
            if similar:
                return {
                    "status": "AVAILABLE",
                    "incident_id": target_id,
                    "similar_incidents": similar,
                    "top_match": similar[0]
                }

        from app.engine.case_memory import HISTORICAL_CASES
        return {
            "status": "AVAILABLE",
            "similar_incidents": HISTORICAL_CASES,
            "note": "Historical simulation repository cases available."
        }


# =============================================================================
# GEMINI FUNCTION CALLING DECLARATIONS (TOOL SCHEMAS)
# =============================================================================

GEMINI_TOOL_DECLARATIONS = [
    {
        "name": "get_incident",
        "description": "Retrieves the core incident metadata, severity, anomaly score, and initial detection metrics.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "incident_id": {
                    "type": "STRING",
                    "description": "The unique incident identifier, e.g. 'INC-0001'."
                }
            },
            "required": ["incident_id"]
        }
    },
    {
        "name": "get_gateway_metrics",
        "description": "Calculates live failure rates, peer averages, failure code breakdown, and financial exposure for a payment gateway.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "gateway": {
                    "type": "STRING",
                    "description": "The name of the banking gateway node, e.g. 'Gateway_X', 'Gateway_HDFC'."
                }
            },
            "required": ["gateway"]
        }
    },
    {
        "name": "get_failed_payments",
        "description": "Retrieves representative sample records of failed payments on a gateway with error codes and descriptions.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "gateway": {
                    "type": "STRING",
                    "description": "The gateway name to query failed payments for."
                },
                "limit": {
                    "type": "INTEGER",
                    "description": "Maximum number of payment records to retrieve (default 25)."
                }
            },
            "required": ["gateway"]
        }
    },
    {
        "name": "get_affected_merchants",
        "description": "Returns all merchants affected by payment failures on a gateway with individual merchant failure rates and exposure.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "gateway": {
                    "type": "STRING",
                    "description": "The gateway name."
                }
            },
            "required": ["gateway"]
        }
    },
    {
        "name": "get_payment_context",
        "description": "Retrieves the complete relational lifecycle for a specific payment ID (order, merchant, refunds, webhooks).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "payment_id": {
                    "type": "STRING",
                    "description": "The unique payment identifier, e.g. 'pay_lab_000002'."
                }
            },
            "required": ["payment_id"]
        }
    },
    {
        "name": "get_webhook_activity",
        "description": "Retrieves webhook event delivery history and signatures for transactions routed through a gateway.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "gateway": {
                    "type": "STRING",
                    "description": "The gateway name."
                },
                "limit": {
                    "type": "INTEGER",
                    "description": "Max events to return."
                }
            },
            "required": ["gateway"]
        }
    },
    {
        "name": "get_merchant_metrics",
        "description": "Calculates a merchant's refund rate against its own historical baseline, webhook delivery reliability, and duplicate-refund payment count — use this for merchant_refund_spike, merchant_duplicate_refund, and merchant_webhook_failure incidents.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "merchant_id": {
                    "type": "STRING",
                    "description": "The merchant identifier, e.g. 'merch_Nova_Store'."
                }
            },
            "required": ["merchant_id"]
        }
    },
    {
        "name": "get_merchant_refunds",
        "description": "Retrieves representative refund records for a merchant, flagging which payments received more than one refund attempt (duplicate-refund forensic evidence).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "merchant_id": {
                    "type": "STRING",
                    "description": "The merchant identifier."
                },
                "limit": {
                    "type": "INTEGER",
                    "description": "Maximum number of refund records to retrieve (default 25)."
                }
            },
            "required": ["merchant_id"]
        }
    },
    {
        "name": "get_merchant_webhook_activity",
        "description": "Retrieves webhook delivery status and event logs for a merchant's payments.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "merchant_id": {
                    "type": "STRING",
                    "description": "The merchant identifier."
                },
                "limit": {
                    "type": "INTEGER",
                    "description": "Max events to return."
                }
            },
            "required": ["merchant_id"]
        }
    },
    {
        "name": "find_similar_incidents",
        "description": "Searches Case Memory in PostgreSQL for historically resolved incidents similar to the current incident to identify precedents, past root causes, and proven remediation actions.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "incident_type": {
                    "type": "STRING",
                    "description": "The type of incident, e.g. 'gateway_failure_spike'."
                },
                "incident_id": {
                    "type": "STRING",
                    "description": "The optional active incident ID, e.g. 'INC-0001'."
                }
            }
        }
    }
]

TOOL_REGISTRY = {
    "get_incident": InvestigationTools.get_incident,
    "get_gateway_metrics": InvestigationTools.get_gateway_metrics,
    "get_failed_payments": InvestigationTools.get_failed_payments,
    "get_affected_merchants": InvestigationTools.get_affected_merchants,
    "get_payment_context": InvestigationTools.get_payment_context,
    "get_webhook_activity": InvestigationTools.get_webhook_activity,
    "get_merchant_metrics": InvestigationTools.get_merchant_metrics,
    "get_merchant_refunds": InvestigationTools.get_merchant_refunds,
    "get_merchant_webhook_activity": InvestigationTools.get_merchant_webhook_activity,
    "find_similar_incidents": InvestigationTools.find_similar_incidents,
}

