"""
backend/app/engine/financial_tools.py

Authoritative, backend-executed tools for the Financial Copilot Gemini agent.
Every tool is strictly parameterized and executes real parameterized SQL or
in-process cosine-similarity retrieval against PostgreSQL — Gemini selects a
tool and arguments, but never writes, sees, or executes SQL itself. This is
the concrete enforcement of "Gemini must never execute arbitrary SQL":
calculate_financial_metric in particular only accepts a name from a closed
whitelist, not a free-form expression.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.engine.database import get_db_connection
from app.engine.embeddings import generate_embedding, cosine_similarity

_ALLOWED_METRICS = {"total_spend", "average_transaction", "largest_expense", "transaction_count"}


def _date_filter_clause(col: str, start_date: Optional[str], end_date: Optional[str], params: list) -> str:
    """Casts both sides to a bare date so a date-only filter (e.g. '2026-08-10')
    matches the whole calendar day regardless of the TIMESTAMPTZ column's
    stored time-of-day/timezone — a plain '<=' comparison against a date
    string is timezone-sensitive and can silently exclude same-day rows."""
    clause = ""
    if start_date:
        clause += f" AND {col}::date >= %s::date"
        params.append(start_date)
    if end_date:
        clause += f" AND {col}::date <= %s::date"
        params.append(end_date)
    return clause


class FinancialTools:

    @staticmethod
    def search_financial_documents(query: str, document_type: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
        """Semantic search over uploaded financial document chunks (real embeddings, cosine-ranked)."""
        if not query:
            return {"error": "Missing query parameter"}
        limit = min(max(1, limit), 20)

        query_vec = generate_embedding(query)
        if query_vec is None:
            return {"error": "Embedding generation is unavailable (Gemini not configured or request failed)."}

        conn = get_db_connection()
        c = conn.cursor()
        if document_type:
            c.execute("""
                SELECT ch.chunk_id, ch.content, ch.embedding_json, ch.page_number, ch.section,
                       d.document_id, d.filename, d.document_type
                FROM financial_document_chunks ch
                JOIN financial_documents d ON d.document_id = ch.document_id
                WHERE ch.embedding_json IS NOT NULL AND d.document_type = %s;
            """, (document_type,))
        else:
            c.execute("""
                SELECT ch.chunk_id, ch.content, ch.embedding_json, ch.page_number, ch.section,
                       d.document_id, d.filename, d.document_type
                FROM financial_document_chunks ch
                JOIN financial_documents d ON d.document_id = ch.document_id
                WHERE ch.embedding_json IS NOT NULL;
            """)
        rows = c.fetchall()
        c.close()
        conn.close()

        scored = []
        for r in rows:
            row = dict(r)
            try:
                vec = json.loads(row["embedding_json"])
            except Exception:
                continue
            score = cosine_similarity(query_vec, vec)
            scored.append({
                "chunk_id": row["chunk_id"],
                "content": row["content"],
                "page_number": row["page_number"],
                "section": row["section"],
                "document_id": row["document_id"],
                "filename": row["filename"],
                "document_type": row["document_type"],
                "similarity_score": round(score, 4)
            })
        scored.sort(key=lambda x: x["similarity_score"], reverse=True)
        return {"query": query, "results_returned": len(scored[:limit]), "results": scored[:limit]}

    @staticmethod
    def search_financial_policy(query: str, limit: int = 5) -> Dict[str, Any]:
        """Semantic search restricted to uploaded fee-policy documents."""
        return FinancialTools.search_financial_documents(query, document_type="fee_policy", limit=limit)

    @staticmethod
    def get_transactions(
        account_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        merchant: Optional[str] = None,
        category: Optional[str] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Retrieves persisted financial transactions with optional filters. Parameterized SQL only."""
        limit = min(max(1, limit), 200)
        clauses = ["1=1"]
        params: list = []

        if account_id:
            clauses.append("account_id = %s")
            params.append(account_id)
        if merchant:
            clauses.append("merchant ILIKE %s")
            params.append(f"%{merchant}%")
        if category:
            clauses.append("category = %s")
            params.append(category)
        if min_amount is not None:
            clauses.append("amount >= %s")
            params.append(min_amount)
        if max_amount is not None:
            clauses.append("amount <= %s")
            params.append(max_amount)
        clauses.append(_date_filter_clause("transaction_date", start_date, end_date, params) or "1=1")

        query = f"SELECT * FROM financial_transactions WHERE {' AND '.join(clauses)} ORDER BY transaction_date DESC LIMIT %s;"
        params.append(limit)

        conn = get_db_connection()
        c = conn.cursor()
        c.execute(query, tuple(params))
        rows = [dict(r) for r in c.fetchall()]
        c.close()
        conn.close()
        return {"transactions_returned": len(rows), "transactions": rows}

    @staticmethod
    def get_transaction_details(transaction_id: str) -> Dict[str, Any]:
        """Retrieves a single transaction, its source document, and a best-effort match against
        an existing MoneyOps incident on the same merchant name (for cross-linking to Investigation)."""
        if not transaction_id:
            return {"error": "Missing transaction_id parameter"}

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM financial_transactions WHERE transaction_id = %s;", (transaction_id,))
        tx = c.fetchone()
        if not tx:
            c.close()
            conn.close()
            return {"error": f"Transaction '{transaction_id}' not found"}
        tx = dict(tx)

        document = None
        if tx.get("document_id"):
            c.execute("SELECT document_id, filename, document_type FROM financial_documents WHERE document_id = %s;", (tx["document_id"],))
            doc_row = c.fetchone()
            if doc_row:
                document = dict(doc_row)

        matched_incident = None
        if tx.get("merchant"):
            c.execute("""
                SELECT incident_id, title, type, status, target_entity_id
                FROM incidents WHERE target_entity_id ILIKE %s ORDER BY detected_at DESC LIMIT 1;
            """, (f"%{tx['merchant']}%",))
            inc_row = c.fetchone()
            if inc_row:
                matched_incident = dict(inc_row)

        c.close()
        conn.close()
        return {"transaction": tx, "document": document, "matched_incident": matched_incident}

    @staticmethod
    def get_spending_summary(
        account_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        group_by: str = "category"
    ) -> Dict[str, Any]:
        """SQL aggregation of spend, grouped by category or merchant."""
        group_col = "category" if group_by not in ("category", "merchant") else group_by
        clauses = ["transaction_type = 'debit'"]
        params: list = []
        if account_id:
            clauses.append("account_id = %s")
            params.append(account_id)
        clauses.append(_date_filter_clause("transaction_date", start_date, end_date, params) or "1=1")

        query = f"""
            SELECT COALESCE({group_col}, 'uncategorized') as group_key, SUM(amount) as total, COUNT(*) as txn_count
            FROM financial_transactions WHERE {' AND '.join(clauses)}
            GROUP BY group_key ORDER BY total DESC;
        """
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(query, tuple(params))
        rows = [dict(r) for r in c.fetchall()]
        c.execute(f"SELECT COALESCE(SUM(amount),0) as total_spend, COUNT(*) as total_txns FROM financial_transactions WHERE {' AND '.join(clauses)};", tuple(params))
        totals = dict(c.fetchone())
        c.close()
        conn.close()
        return {"group_by": group_col, "breakdown": rows, "total_spend": float(totals["total_spend"]), "total_transactions": totals["total_txns"]}

    @staticmethod
    def compare_periods(
        account_id: Optional[str],
        period_a_start: str,
        period_a_end: str,
        period_b_start: str,
        period_b_end: str
    ) -> Dict[str, Any]:
        """Deterministic two-period spend comparison. All arithmetic performed here, not by Gemini."""
        if not (period_a_start and period_a_end and period_b_start and period_b_end):
            return {"error": "period_a_start, period_a_end, period_b_start, period_b_end are all required"}

        def _period_summary(start: str, end: str) -> Dict[str, Any]:
            clauses = ["transaction_type = 'debit'", "transaction_date::date >= %s::date", "transaction_date::date <= %s::date"]
            params: list = [start, end]
            if account_id:
                clauses.append("account_id = %s")
                params.append(account_id)
            conn = get_db_connection()
            c = conn.cursor()
            c.execute(f"SELECT COALESCE(SUM(amount),0) as total, COUNT(*) as cnt FROM financial_transactions WHERE {' AND '.join(clauses)};", tuple(params))
            totals = dict(c.fetchone())
            c.execute(f"""
                SELECT COALESCE(category, 'uncategorized') as group_key, SUM(amount) as total
                FROM financial_transactions WHERE {' AND '.join(clauses)}
                GROUP BY group_key ORDER BY total DESC LIMIT 10;
            """, tuple(params))
            breakdown = [dict(r) for r in c.fetchall()]
            c.close()
            conn.close()
            return {"total_spend": float(totals["total"]), "transaction_count": totals["cnt"], "breakdown": breakdown}

        period_a = _period_summary(period_a_start, period_a_end)
        period_b = _period_summary(period_b_start, period_b_end)
        delta = round(period_b["total_spend"] - period_a["total_spend"], 2)
        pct_change = round((delta / period_a["total_spend"]) * 100, 2) if period_a["total_spend"] > 0 else None

        return {
            "period_a": {"start": period_a_start, "end": period_a_end, **period_a},
            "period_b": {"start": period_b_start, "end": period_b_end, **period_b},
            "delta_inr": delta,
            "percent_change": pct_change
        }

    @staticmethod
    def find_duplicate_transactions(account_id: Optional[str] = None, amount_tolerance: float = 0.01, date_window_days: int = 3) -> Dict[str, Any]:
        """SQL self-join: same merchant + amount within a date window — a real duplicate-charge signature."""
        clauses = ["a.transaction_id < b.transaction_id", "a.merchant = b.merchant",
                   "ABS(a.amount - b.amount) <= %s",
                   "ABS(EXTRACT(EPOCH FROM (a.transaction_date - b.transaction_date))) <= %s"]
        params: list = [amount_tolerance, date_window_days * 86400]
        if account_id:
            clauses.append("a.account_id = %s AND b.account_id = %s")
            params.extend([account_id, account_id])

        query = f"""
            SELECT a.transaction_id as txn_a, b.transaction_id as txn_b, a.merchant, a.amount,
                   a.transaction_date as date_a, b.transaction_date as date_b
            FROM financial_transactions a
            JOIN financial_transactions b ON {' AND '.join(clauses)}
            WHERE a.merchant IS NOT NULL
            ORDER BY a.transaction_date DESC LIMIT 100;
        """
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(query, tuple(params))
        rows = [dict(r) for r in c.fetchall()]
        c.close()
        conn.close()
        return {"duplicate_pairs_found": len(rows), "duplicates": rows}

    @staticmethod
    def find_recurring_transactions(account_id: Optional[str] = None, min_occurrences: int = 3) -> Dict[str, Any]:
        """SQL grouping by merchant + rounded amount, counting occurrences — a real recurring-payment signature."""
        clauses = ["merchant IS NOT NULL"]
        params: list = []
        if account_id:
            clauses.append("account_id = %s")
            params.append(account_id)

        query = f"""
            SELECT merchant, ROUND(amount::numeric, 2) as rounded_amount, COUNT(*) as occurrences,
                   MIN(transaction_date) as first_seen, MAX(transaction_date) as last_seen
            FROM financial_transactions WHERE {' AND '.join(clauses)}
            GROUP BY merchant, rounded_amount
            HAVING COUNT(*) >= %s
            ORDER BY occurrences DESC;
        """
        params.append(min_occurrences)
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(query, tuple(params))
        rows = [dict(r) for r in c.fetchall()]
        c.close()
        conn.close()
        return {"recurring_patterns_found": len(rows), "recurring": rows}

    @staticmethod
    def calculate_financial_metric(metric: str, account_id: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """Computes one whitelisted deterministic metric. Rejects any metric name not on the
        whitelist rather than falling through to arbitrary computation — this is the boundary
        that keeps Gemini from ever specifying its own SQL/calculation."""
        if metric not in _ALLOWED_METRICS:
            return {"error": f"Unknown metric '{metric}'. Allowed: {sorted(_ALLOWED_METRICS)}"}

        clauses = ["transaction_type = 'debit'"]
        params: list = []
        if account_id:
            clauses.append("account_id = %s")
            params.append(account_id)
        clauses.append(_date_filter_clause("transaction_date", start_date, end_date, params) or "1=1")
        where = " AND ".join(clauses)

        conn = get_db_connection()
        c = conn.cursor()
        if metric == "total_spend":
            c.execute(f"SELECT COALESCE(SUM(amount),0) as value FROM financial_transactions WHERE {where};", tuple(params))
            value = float(c.fetchone()["value"])
        elif metric == "average_transaction":
            c.execute(f"SELECT COALESCE(AVG(amount),0) as value FROM financial_transactions WHERE {where};", tuple(params))
            value = round(float(c.fetchone()["value"]), 2)
        elif metric == "largest_expense":
            c.execute(f"SELECT merchant, amount, transaction_date FROM financial_transactions WHERE {where} ORDER BY amount DESC LIMIT 1;", tuple(params))
            row = c.fetchone()
            c.close()
            conn.close()
            return {"metric": metric, "result": dict(row) if row else None}
        elif metric == "transaction_count":
            c.execute(f"SELECT COUNT(*) as value FROM financial_transactions WHERE {where};", tuple(params))
            value = c.fetchone()["value"]
        c.close()
        conn.close()
        return {"metric": metric, "value": value}


GEMINI_FINANCIAL_TOOL_DECLARATIONS = [
    {
        "name": "search_financial_documents",
        "description": "Semantic search over all uploaded financial documents (statements, invoices, policies) using real embeddings. Use for textual/explanatory questions.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "The natural-language search query."},
                "document_type": {"type": "STRING", "description": "Optional filter: 'bank_statement', 'credit_card_statement', 'fee_policy', 'invoice', 'refund_report'."},
                "limit": {"type": "INTEGER", "description": "Max chunks to return (default 5)."}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_financial_policy",
        "description": "Semantic search restricted to uploaded fee/policy documents only — use when the user asks whether a fee/charge is supported by policy.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "The policy question to search for."},
                "limit": {"type": "INTEGER", "description": "Max chunks to return (default 5)."}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_transactions",
        "description": "Retrieves structured financial transactions with optional filters (date range, merchant, category, amount range).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "account_id": {"type": "STRING"},
                "start_date": {"type": "STRING", "description": "ISO date, e.g. '2026-08-01'."},
                "end_date": {"type": "STRING", "description": "ISO date, e.g. '2026-08-31'."},
                "merchant": {"type": "STRING", "description": "Partial merchant name to filter by."},
                "category": {"type": "STRING"},
                "min_amount": {"type": "NUMBER"},
                "max_amount": {"type": "NUMBER"},
                "limit": {"type": "INTEGER"}
            },
            "required": []
        }
    },
    {
        "name": "get_transaction_details",
        "description": "Retrieves full detail for one transaction by ID, including its source document and any matching MoneyOps incident.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"transaction_id": {"type": "STRING"}},
            "required": ["transaction_id"]
        }
    },
    {
        "name": "get_spending_summary",
        "description": "Aggregates spend grouped by category or merchant over an optional date range.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "account_id": {"type": "STRING"},
                "start_date": {"type": "STRING"},
                "end_date": {"type": "STRING"},
                "group_by": {"type": "STRING", "description": "'category' or 'merchant'."}
            },
            "required": []
        }
    },
    {
        "name": "compare_periods",
        "description": "Deterministic comparison of total spend and category breakdown between two date ranges (e.g. this month vs last month). All math computed by the backend, not estimated.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "account_id": {"type": "STRING"},
                "period_a_start": {"type": "STRING"},
                "period_a_end": {"type": "STRING"},
                "period_b_start": {"type": "STRING"},
                "period_b_end": {"type": "STRING"}
            },
            "required": ["period_a_start", "period_a_end", "period_b_start", "period_b_end"]
        }
    },
    {
        "name": "find_duplicate_transactions",
        "description": "Finds transaction pairs with the same merchant and amount within a short date window — a duplicate-charge signature.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "account_id": {"type": "STRING"},
                "amount_tolerance": {"type": "NUMBER"},
                "date_window_days": {"type": "INTEGER"}
            },
            "required": []
        }
    },
    {
        "name": "find_recurring_transactions",
        "description": "Finds merchant+amount combinations that repeat at least min_occurrences times — a recurring-subscription/payment signature.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "account_id": {"type": "STRING"},
                "min_occurrences": {"type": "INTEGER"}
            },
            "required": []
        }
    },
    {
        "name": "calculate_financial_metric",
        "description": "Computes one deterministic financial metric from a fixed whitelist: 'total_spend', 'average_transaction', 'largest_expense', 'transaction_count'. Reject any other metric name.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "metric": {"type": "STRING", "description": "One of: total_spend, average_transaction, largest_expense, transaction_count."},
                "account_id": {"type": "STRING"},
                "start_date": {"type": "STRING"},
                "end_date": {"type": "STRING"}
            },
            "required": ["metric"]
        }
    }
]

FINANCIAL_TOOL_REGISTRY = {
    "search_financial_documents": FinancialTools.search_financial_documents,
    "search_financial_policy": FinancialTools.search_financial_policy,
    "get_transactions": FinancialTools.get_transactions,
    "get_transaction_details": FinancialTools.get_transaction_details,
    "get_spending_summary": FinancialTools.get_spending_summary,
    "compare_periods": FinancialTools.compare_periods,
    "find_duplicate_transactions": FinancialTools.find_duplicate_transactions,
    "find_recurring_transactions": FinancialTools.find_recurring_transactions,
    "calculate_financial_metric": FinancialTools.calculate_financial_metric,
}
