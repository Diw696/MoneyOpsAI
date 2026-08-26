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
    def extract_gateway_features(cls) -> List[Dict[str, Any]]:
        """
        Extracts operational features grouped by payment gateway from PostgreSQL.
        Calculates failure rates, peer averages, primary error codes, and financial exposure.
        """
        conn = get_db_connection()
        c = conn.cursor()

        # 1. Gateway Level Aggregations
        c.execute("""
            SELECT 
                gateway,
                COUNT(*) as total_payments,
                SUM(CASE WHEN status = 'captured' THEN 1 ELSE 0 END) as captured_payments,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_payments,
                ROUND((1.0 * SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0))::numeric, 4) as failure_rate,
                ROUND(AVG(amount)::numeric, 2) as avg_amount,
                ROUND(COALESCE(SUM(CASE WHEN status = 'failed' THEN amount ELSE 0 END), 0)::numeric, 2) as potential_exposure,
                COUNT(DISTINCT CASE WHEN status = 'failed' THEN merchant_id ELSE NULL END) as affected_merchants,
                COUNT(DISTINCT CASE WHEN status = 'failed' THEN order_id ELSE NULL END) as affected_orders,
                MAX(source) as source
            FROM payments
            WHERE gateway IS NOT NULL
            GROUP BY gateway
            ORDER BY total_payments DESC;
        """)
        gateways_data = c.fetchall()

        # 2. Extract Top Failure Code per Gateway
        c.execute("""
            SELECT gateway, failure_code, COUNT(*) as code_count
            FROM payments
            WHERE status = 'failed' AND failure_code IS NOT NULL
            GROUP BY gateway, failure_code
            ORDER BY gateway, code_count DESC;
        """)
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

        c.execute("""
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
                    merchant_id,
                    COUNT(*) as total_payments,
                    SUM(CASE WHEN status = 'captured' THEN 1 ELSE 0 END) as captured_payments,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_payments,
                    AVG(amount) as avg_amount,
                    MAX(source) as source
                FROM payments
                GROUP BY merchant_id
            ) p ON m.merchant_id = p.merchant_id
            LEFT JOIN (
                SELECT 
                    merchant_id,
                    COUNT(*) as total_refunds,
                    SUM(amount) as refund_amount
                FROM refunds
                GROUP BY merchant_id
            ) r ON m.merchant_id = r.merchant_id
            ORDER BY total_payments DESC;
        """)
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

feature_engine = FeatureEngine()
