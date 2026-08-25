import json
from typing import Optional, Dict, Any, List
from app.engine.database import get_db_connection
from app.models.schemas import MerchantBaseline

class MerchantMemoryEngine:
    """
    Maintains rolling behavioral profiles for merchants.
    Computes contextual deviations against individual merchant baselines
    using live relational SQL aggregations over payment history.
    """

    def __init__(self):
        pass

    def get_merchant_profile(self, merchant_id: str) -> Optional[MerchantBaseline]:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch merchant metadata
        cursor.execute("SELECT * FROM merchants WHERE merchant_id = ?", (merchant_id,))
        m_row = cursor.fetchone()
        if not m_row:
            conn.close()
            return None

        # Aggregate payment statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_payments,
                AVG(amount) as avg_amount,
                SUM(CASE WHEN status = 'captured' THEN 1 ELSE 0 END) as captured_payments,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_payments,
                AVG(retry_count) as avg_retries
            FROM payments 
            WHERE merchant_id = ?
        """, (merchant_id,))
        p_stats = cursor.fetchone()

        total_p = p_stats["total_payments"] or 0
        avg_amt = p_stats["avg_amount"] or 0.0
        captured_p = p_stats["captured_payments"] or 0
        success_rate = (captured_p / total_p) if total_p > 0 else 0.95
        avg_retries = p_stats["avg_retries"] or 1.0

        # Aggregate refunds
        cursor.execute("""
            SELECT COUNT(*) as total_refunds, SUM(amount) as refund_vol
            FROM refunds 
            WHERE merchant_id = ?
        """, (merchant_id,))
        r_stats = cursor.fetchone()
        total_r = r_stats["total_refunds"] or 0
        refund_rate = (total_r / total_p) if total_p > 0 else m_row["baseline_refund_rate"]

        # Aggregate disputes
        cursor.execute("SELECT COUNT(*) as total_disputes FROM disputes WHERE merchant_id = ?", (merchant_id,))
        d_stats = cursor.fetchone()
        total_d = d_stats["total_disputes"] or 0
        chargeback_rate = (total_d / total_p) if total_p > 0 else 0.001

        # Failure codes distribution
        cursor.execute("""
            SELECT failure_code, COUNT(*) as count 
            FROM payments 
            WHERE merchant_id = ? AND failure_code IS NOT NULL 
            GROUP BY failure_code
        """, (merchant_id,))
        f_rows = cursor.fetchall()
        total_failures = sum(row["count"] for row in f_rows) or 1
        failure_dist = {row["failure_code"]: round(row["count"] / total_failures, 3) for row in f_rows}

        # Gateway distribution
        cursor.execute("""
            SELECT gateway, COUNT(*) as count 
            FROM payments 
            WHERE merchant_id = ? 
            GROUP BY gateway
        """, (merchant_id,))
        g_rows = cursor.fetchall()
        g_dist = {row["gateway"]: round(row["count"] / max(total_p, 1), 3) for row in g_rows}

        # Calculate current window failure rate (last 50 payments)
        cursor.execute("""
            SELECT 
                COUNT(*) as recent_total,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as recent_failed
            FROM payments 
            WHERE merchant_id = ? 
            ORDER BY created_at DESC 
            LIMIT 50
        """, (merchant_id,))
        recent_p = cursor.fetchone()
        rec_tot = recent_p["recent_total"] or 0
        rec_fail = recent_p["recent_failed"] or 0
        cur_fail_rate = (rec_fail / rec_tot) if rec_tot > 0 else 0.0

        # Query actual historical anomaly count from canonical events
        cursor.execute("SELECT COUNT(*) as anom_count FROM canonical_events WHERE merchant_id = ? AND is_anomaly = 1", (merchant_id,))
        anom_cnt = cursor.fetchone()["anom_count"] or 0

        # Query linked incidents count
        cursor.execute("""
            SELECT COUNT(*) as inc_count FROM incidents 
            WHERE affected_merchants > 0 AND (
                target_entity_id IN (SELECT payment_id FROM payments WHERE merchant_id = ?) OR
                description LIKE ?
            )
        """, (merchant_id, f"%{merchant_id}%"))
        inc_cnt = cursor.fetchone()["inc_count"] or 0

        # Deviation check: is current failure or refund rate > 2.5x baseline?
        baseline_ref = m_row["baseline_refund_rate"]
        is_anom = (cur_fail_rate > 0.25) or (refund_rate > (baseline_ref * 2.5) and refund_rate > 0.04)

        conn.close()

        return MerchantBaseline(
            merchant_id=m_row["merchant_id"],
            merchant_name=m_row["name"],
            avg_payment_value=round(avg_amt, 2),
            payment_success_rate=round(success_rate, 4),
            refund_rate=round(refund_rate, 4),
            chargeback_rate=round(chargeback_rate, 4),
            settlement_latency_hrs=round(m_row["baseline_settlement_latency_hrs"], 1),
            avg_retry_count=round(avg_retries, 2),
            failure_code_distribution=failure_dist,
            gateway_distribution=g_dist,
            historical_anomaly_count=anom_cnt,
            historical_incident_count=inc_cnt,
            current_refund_rate=round(refund_rate, 4),
            current_failure_rate=round(cur_fail_rate, 4),
            is_anomalous=is_anom
        )

    def get_all_merchants_summary(self) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT merchant_id, name, category, baseline_refund_rate FROM merchants")
        merchants = cursor.fetchall()
        conn.close()

        summaries = []
        for m in merchants:
            prof = self.get_merchant_profile(m["merchant_id"])
            if prof:
                summaries.append({
                    "merchant_id": prof.merchant_id,
                    "merchant_name": prof.merchant_name,
                    "category": m["category"],
                    "baseline_refund_rate": m["baseline_refund_rate"],
                    "current_refund_rate": prof.current_refund_rate,
                    "payment_success_rate": prof.payment_success_rate,
                    "is_anomalous": prof.is_anomalous,
                    "avg_payment_value": prof.avg_payment_value,
                    "failure_codes": prof.failure_code_distribution
                })
        return summaries

merchant_memory = MerchantMemoryEngine()
