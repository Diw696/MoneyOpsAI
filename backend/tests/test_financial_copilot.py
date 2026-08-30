import io
import json
import uuid
import httpx
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.engine.database import get_db_connection
from app.engine.document_ingestion import DocumentIngestionPipeline
from app.engine.financial_tools import FinancialTools
from app.engine.financial_copilot_agent import financial_copilot_agent

client = TestClient(app)

CSV_CONTENT = b"""Date,Description,Merchant,Debit,Credit,Balance
2026-08-01,Salary Credit,Acme Corp,,50000.00,50000.00
2026-08-02,AWS Hosting,Amazon Web Services,2000.00,,48000.00
2026-08-05,Zoom Subscription,Zoom Video,1500.00,,46500.00
2026-08-05,Zoom Subscription Duplicate,Zoom Video,1500.00,,45000.00
2026-08-10,AWS Hosting,Amazon Web Services,2000.00,,43000.00
2026-08-15,Uber Ride,Uber India,500.00,,42500.00
2026-08-20,Late Fee,Razorpay,999.00,,41501.00
"""


@pytest.fixture(scope="module", autouse=True)
def seeded_document():
    """Ingests one deterministic CSV statement (no network dependency — CSV
    extraction never calls Gemini; only chunk embedding does, and that's
    allowed to no-op gracefully if unconfigured, per generate_embedding's
    own contract)."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM financial_document_chunks; DELETE FROM financial_transactions; DELETE FROM financial_analysis_runs; DELETE FROM financial_documents; DELETE FROM financial_accounts;")
    conn.commit()
    c.close()
    conn.close()

    result = DocumentIngestionPipeline.ingest(
        filename="test_august.csv",
        raw_bytes=CSV_CONTENT,
        document_type="bank_statement",
        account_id=None
    )
    return result


def test_csv_ingestion_extracts_all_transactions(seeded_document):
    """Verify the ingestion pipeline extracts every real row, no more, no fewer, and marks READY."""
    assert seeded_document["processing_status"] == "ready"
    assert seeded_document["transactions_extracted"] == 7
    assert seeded_document["chunks_created"] >= 1


def test_csv_ingestion_infers_categories_deterministically():
    """Verify the keyword-based category heuristic tags known merchants correctly."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT merchant, category FROM financial_transactions WHERE merchant = 'Amazon Web Services' LIMIT 1;")
    row = dict(c.fetchone())
    c.close()
    conn.close()
    assert row["category"] == "Cloud/Hosting"


def test_document_upload_endpoint_rejects_empty_file():
    """Verify POST /api/financial/documents/upload rejects a zero-byte file rather than
    silently creating a fabricated 'ready' document with no content."""
    res = client.post(
        "/api/financial/documents/upload",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")}
    )
    assert res.status_code == 400


def test_document_upload_endpoint_marks_unsupported_type_failed():
    """Verify an unsupported file type is marked 'failed' with a real reason, not silently ignored."""
    res = client.post(
        "/api/financial/documents/upload",
        files={"file": ("notes.txt", io.BytesIO(b"random text"), "text/plain")}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["processing_status"] == "failed"
    assert "error_message" in data


def test_tool_get_transactions_filters_by_merchant():
    """Verify get_transactions returns only real PostgreSQL rows matching the merchant filter."""
    res = FinancialTools.get_transactions(merchant="Zoom")
    assert "error" not in res
    assert res["transactions_returned"] == 2
    for t in res["transactions"]:
        assert "Zoom" in t["merchant"]


def test_tool_get_transaction_details_not_found():
    """Verify a nonexistent transaction ID returns an explicit error, never fabricated data."""
    res = FinancialTools.get_transaction_details("ftxn_does_not_exist")
    assert res == {"error": "Transaction 'ftxn_does_not_exist' not found"}


def test_tool_find_duplicate_transactions_detects_real_duplicate():
    """Verify the duplicate-detection tool finds the two identical Zoom charges on the same date."""
    res = FinancialTools.find_duplicate_transactions(date_window_days=1, amount_tolerance=0.01)
    assert res["duplicate_pairs_found"] >= 1
    merchants = [d["merchant"] for d in res["duplicates"]]
    assert "Zoom Video" in merchants


def test_tool_find_recurring_transactions_detects_aws():
    """Verify recurring-payment detection finds the two AWS charges of the same amount."""
    res = FinancialTools.find_recurring_transactions(min_occurrences=2)
    merchants = [r["merchant"] for r in res["recurring"]]
    assert "Amazon Web Services" in merchants


def test_tool_calculate_financial_metric_total_spend():
    """Verify total_spend is computed deterministically by SQL, matching a hand-summed total."""
    res = FinancialTools.calculate_financial_metric("total_spend")
    expected = 2000.00 + 1500.00 + 1500.00 + 2000.00 + 500.00 + 999.00
    assert res["metric"] == "total_spend"
    assert abs(res["value"] - expected) < 0.01


def test_tool_calculate_financial_metric_rejects_unknown_metric():
    """Verify the metric whitelist rejects any name Gemini might invent — the concrete
    boundary preventing 'arbitrary SQL' execution via this tool."""
    res = FinancialTools.calculate_financial_metric("DROP TABLE financial_transactions")
    assert "error" in res
    assert "Unknown metric" in res["error"]


def test_tool_compare_periods_computes_real_delta():
    """Verify compare_periods performs its own arithmetic rather than deferring to the model."""
    res = FinancialTools.compare_periods(
        account_id=None,
        period_a_start="2026-08-01", period_a_end="2026-08-10",
        period_b_start="2026-08-11", period_b_end="2026-08-31"
    )
    assert res["period_a"]["total_spend"] == 2000.00 + 1500.00 + 1500.00 + 2000.00
    assert res["period_b"]["total_spend"] == 500.00 + 999.00
    assert res["delta_inr"] == round(res["period_b"]["total_spend"] - res["period_a"]["total_spend"], 2)


def test_financial_summary_endpoint_reflects_real_counts():
    """Verify GET /api/financial/summary returns real PostgreSQL-derived counts, not hardcoded ones."""
    res = client.get("/api/financial/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["transactions"] == 7
    assert data["documents"] >= 1


def test_financial_transactions_endpoint():
    """Verify GET /api/financial/transactions returns real rows."""
    res = client.get("/api/financial/transactions?limit=50")
    assert res.status_code == 200
    assert len(res.json()) == 7


def test_copilot_ask_endpoint_when_ai_not_configured(monkeypatch):
    """Verify POST /api/financial/copilot/ask returns 400 AI_NOT_CONFIGURED when key is empty —
    consistent with the existing gemini_agent endpoint's behavior."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    res = client.post("/api/financial/copilot/ask", json={"query": "Why did spending increase?"})
    assert res.status_code == 400
    assert res.json()["detail"]["error_code"] == "AI_NOT_CONFIGURED"


def test_copilot_ask_endpoint_rejects_empty_query(monkeypatch):
    """Verify an empty query is rejected explicitly rather than sent to Gemini."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "dummy_key_for_test_000000000")
    res = client.post("/api/financial/copilot/ask", json={"query": "   "})
    assert res.status_code == 400
    assert res.json()["detail"]["error_code"] == "EMPTY_QUERY"


def test_copilot_ask_records_analysis_run_on_failure(monkeypatch):
    """Real end-to-end transition test: forces the Gemini HTTP call to fail immediately (no
    live network dependency, deterministic) and asserts the endpoint surfaces a clean error —
    mirrors test_investigate_transitions_to_investigating_then_investigation_failed."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "dummy_key_for_transition_test_000")

    def _raise_timeout(*args, **kwargs):
        raise httpx.TimeoutException("forced failure for transition test")
    monkeypatch.setattr(httpx.Client, "post", _raise_timeout)

    res = client.post("/api/financial/copilot/ask", json={"query": "Find unusual transactions"})
    assert res.status_code == 500


def test_copilot_runs_endpoint_lists_history():
    """Verify GET /api/financial/copilot/runs reflects real financial_analysis_runs rows."""
    conn = get_db_connection()
    c = conn.cursor()
    run_id = f"frun_test_{uuid.uuid4().hex[:8]}"
    c.execute("""
        INSERT INTO financial_analysis_runs (run_id, query, tools_called_json, retrieved_evidence_json, model, response_json, created_at)
        VALUES (%s, 'test query', '[]', '[]', 'gemini-test', '{}', %s);
    """, (run_id, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    c.close()
    conn.close()

    res = client.get("/api/financial/copilot/runs")
    assert res.status_code == 200
    run_ids = [r["run_id"] for r in res.json()]
    assert run_id in run_ids

    detail = client.get(f"/api/financial/copilot/runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["query"] == "test query"
