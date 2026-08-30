"""
backend/app/engine/document_ingestion.py

Financial document ingestion pipeline for the Financial Intelligence Copilot.

UPLOAD -> detect type -> extract text/table data -> normalize structured
transactions -> chunk meaningfully (not naive fixed-size) -> embed chunks ->
persist to PostgreSQL -> mark document READY (or FAILED with a real reason).

Two extraction paths:
  - CSV/XLSX: reliable, deterministic column-heuristic transaction extraction.
  - PDF: text is always extracted and chunked for RAG; transaction-row
    extraction is best-effort (regex over date/description/amount-shaped
    lines) since bank-statement PDF layouts vary too much for a universal
    parser. A PDF that doesn't match yields zero transactions, never
    fabricated ones — chunking/RAG still works for it either way.
"""

import io
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
import psycopg2
from pypdf import PdfReader

_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
}


def _guess_content_type(filename: str) -> str:
    lower = filename.lower()
    for ext, ct in _CONTENT_TYPES.items():
        if lower.endswith(ext):
            return ct
    return "application/octet-stream"

from app.engine.database import get_db_connection
from app.engine.embeddings import generate_embedding

CHUNK_CHAR_LIMIT = 1000
CHUNK_OVERLAP = 100

_DATE_COL_NAMES = {"date", "transaction date", "txn date", "value date", "posting date"}
_DESC_COL_NAMES = {"description", "narration", "particulars", "details", "remarks"}
_MERCHANT_COL_NAMES = {"merchant", "payee", "vendor", "counterparty"}
_DEBIT_COL_NAMES = {"debit", "withdrawal", "withdrawal amt", "amount debited"}
_CREDIT_COL_NAMES = {"credit", "deposit", "deposit amt", "amount credited"}
_AMOUNT_COL_NAMES = {"amount", "amt", "transaction amount"}
_BALANCE_COL_NAMES = {"balance", "closing balance", "balance amt"}
_REFERENCE_COL_NAMES = {"reference", "ref no", "reference number", "cheque no", "utr"}

# Deterministic keyword -> category heuristic, applied uniformly by backend
# code (never by Gemini) so "primary drivers" analysis has something more
# useful to group by than an undifferentiated "uncategorized" bucket. This is
# a transparent, rule-based tag, not an invented fact about the transaction.
_CATEGORY_KEYWORDS = [
    ("Cloud/Hosting", ("aws", "amazon web services", "azure", "google cloud", "hosting", "server")),
    ("Software/Subscriptions", ("slack", "zoom", "subscription", "saas", "software", "license")),
    ("Travel", ("uber", "ola", "flight", "airlines", "cab", "taxi", "travel")),
    ("Office", ("rent", "office", "supplies", "staples", "electricity", "utilities")),
    ("Fees/Charges", ("fee", "charge", "penalty", "interest")),
    ("Payroll/Salary", ("salary", "payroll", "wages")),
    ("Client Revenue", ("client payment", "invoice payment", "customer payment")),
]


def _infer_category(description: Optional[str], merchant: Optional[str]) -> Optional[str]:
    text = f"{description or ''} {merchant or ''}".lower()
    if not text.strip():
        return None
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(kw in text for kw in keywords):
            return category
    return "Other"


def _norm_col(c: str) -> str:
    return re.sub(r"\s+", " ", str(c).strip().lower())


def _find_column(columns: List[str], candidates: set) -> Optional[str]:
    for c in columns:
        if _norm_col(c) in candidates:
            return c
    return None


def _parse_amount(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val) if val == val else None  # filters NaN
    s = str(val).strip().replace(",", "").replace("₹", "").replace("Rs.", "").replace("INR", "")
    if not s or s.lower() in ("nan", "none", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    try:
        ts = pd.to_datetime(val, dayfirst=False, errors="coerce")
        if pd.isna(ts):
            ts = pd.to_datetime(val, dayfirst=True, errors="coerce")
        if pd.isna(ts):
            return None
        return ts.to_pydatetime().replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _detect_document_type(filename: str, declared_type: Optional[str]) -> str:
    if declared_type:
        return declared_type
    lower = filename.lower()
    if "policy" in lower or "fee" in lower:
        return "fee_policy"
    if "invoice" in lower:
        return "invoice"
    if "refund" in lower:
        return "refund_report"
    if "credit" in lower and "card" in lower:
        return "credit_card_statement"
    if "statement" in lower:
        return "bank_statement"
    if lower.endswith(".csv") or lower.endswith(".xlsx"):
        return "transaction_csv"
    return "other"


def _extract_dataframe(filename: str, raw_bytes: bytes) -> Optional[pd.DataFrame]:
    lower = filename.lower()
    try:
        if lower.endswith(".csv"):
            return pd.read_csv(io.BytesIO(raw_bytes))
        if lower.endswith(".xlsx") or lower.endswith(".xls"):
            return pd.read_excel(io.BytesIO(raw_bytes))
    except Exception:
        return None
    return None


def _transactions_from_dataframe(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Column-heuristic structured transaction extraction — the reliable, deterministic path."""
    columns = list(df.columns)
    date_col = _find_column(columns, _DATE_COL_NAMES)
    desc_col = _find_column(columns, _DESC_COL_NAMES)
    merchant_col = _find_column(columns, _MERCHANT_COL_NAMES)
    debit_col = _find_column(columns, _DEBIT_COL_NAMES)
    credit_col = _find_column(columns, _CREDIT_COL_NAMES)
    amount_col = _find_column(columns, _AMOUNT_COL_NAMES)
    balance_col = _find_column(columns, _BALANCE_COL_NAMES)
    ref_col = _find_column(columns, _REFERENCE_COL_NAMES)

    if not date_col or (not amount_col and not debit_col and not credit_col):
        return []  # doesn't look like a transaction table — no fabricated rows

    out = []
    for _, row in df.iterrows():
        tx_date = _parse_date(row.get(date_col))
        if tx_date is None:
            continue

        amount = None
        tx_type = None
        if amount_col:
            amount = _parse_amount(row.get(amount_col))
            if amount is not None:
                tx_type = "credit" if amount >= 0 else "debit"
                amount = abs(amount)
        if amount is None and debit_col:
            debit_amt = _parse_amount(row.get(debit_col))
            if debit_amt:
                amount, tx_type = debit_amt, "debit"
        if amount is None and credit_col:
            credit_amt = _parse_amount(row.get(credit_col))
            if credit_amt:
                amount, tx_type = credit_amt, "credit"
        if amount is None:
            continue

        description = str(row.get(desc_col)).strip() if desc_col and pd.notna(row.get(desc_col)) else None
        merchant = str(row.get(merchant_col)).strip() if merchant_col and pd.notna(row.get(merchant_col)) else description
        balance_after = _parse_amount(row.get(balance_col)) if balance_col else None
        reference = str(row.get(ref_col)).strip() if ref_col and pd.notna(row.get(ref_col)) else None

        out.append({
            "transaction_date": tx_date,
            "description": description,
            "merchant": merchant,
            "amount": amount,
            "transaction_type": tx_type or "debit",
            "category": _infer_category(description, merchant),
            "reference": reference,
            "balance_after": balance_after
        })
    return out


_PDF_TXN_LINE = re.compile(
    r"(?P<date>\d{1,2}[-/][A-Za-z0-9]{2,9}[-/]\d{2,4})\s+(?P<desc>.+?)\s+(?P<amount>-?[\d,]+\.\d{2})\s*(?P<type>CR|DR)?\s*$"
)


def _transactions_from_pdf_text(pages_text: List[str]) -> List[Dict[str, Any]]:
    """Best-effort regex extraction of transaction-row-shaped lines from PDF text.
    Zero matches is a valid, honest outcome — never invents rows for an
    unrecognized statement layout."""
    out = []
    for text in pages_text:
        for line in text.splitlines():
            m = _PDF_TXN_LINE.match(line.strip())
            if not m:
                continue
            tx_date = _parse_date(m.group("date"))
            amount = _parse_amount(m.group("amount"))
            if tx_date is None or amount is None:
                continue
            tx_type = "credit" if (m.group("type") == "CR" or amount >= 0) else "debit"
            desc = m.group("desc").strip()
            out.append({
                "transaction_date": tx_date,
                "description": desc,
                "merchant": desc,
                "amount": abs(amount),
                "transaction_type": tx_type,
                "category": _infer_category(desc, desc),
                "reference": None,
                "balance_after": None
            })
    return out


def _chunk_pdf_pages(pages_text: List[str]) -> List[Dict[str, Any]]:
    """Section-aware chunking: split per-page, then by paragraph breaks,
    capped with overlap — not naive fixed-size chunking across the whole doc."""
    chunks = []
    idx = 0
    for page_num, text in enumerate(pages_text, start=1):
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        if not paragraphs:
            continue
        buf = ""
        for para in paragraphs:
            if buf and len(buf) + len(para) + 1 > CHUNK_CHAR_LIMIT:
                chunks.append({"content": buf, "page_number": page_num, "section": None, "chunk_index": idx})
                idx += 1
                buf = buf[-CHUNK_OVERLAP:] + "\n" + para
            else:
                buf = f"{buf}\n{para}" if buf else para
        if buf.strip():
            chunks.append({"content": buf.strip(), "page_number": page_num, "section": None, "chunk_index": idx})
            idx += 1
    return chunks


def _chunk_dataframe(df: pd.DataFrame, filename: str) -> List[Dict[str, Any]]:
    """One summary chunk describing the sheet, then one chunk per ~20-row
    window — so a semantic question about 'which statement covers X' or a
    general summary question has something meaningful to retrieve, without
    duplicating the full structured data (that's what financial_transactions
    and its SQL tools are for)."""
    columns = list(df.columns)
    chunks = []
    header_summary = f"Document: {filename}\nColumns: {', '.join(str(c) for c in columns)}\nRows: {len(df)}"
    chunks.append({"content": header_summary, "page_number": None, "section": "document_summary", "chunk_index": 0})

    window = 20
    idx = 1
    for start in range(0, len(df), window):
        window_df = df.iloc[start:start + window]
        lines = [", ".join(f"{c}={window_df.iloc[i][c]}" for c in columns) for i in range(len(window_df))]
        content = "\n".join(lines)
        if content.strip():
            chunks.append({
                "content": content[:CHUNK_CHAR_LIMIT],
                "page_number": None,
                "section": f"rows_{start + 1}-{start + len(window_df)}",
                "chunk_index": idx
            })
            idx += 1
    return chunks


class DocumentIngestionPipeline:

    @classmethod
    def ingest(
        cls,
        filename: str,
        raw_bytes: bytes,
        document_type: Optional[str] = None,
        account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        detected_type = _detect_document_type(filename, document_type)
        document_id = f"fdoc_{uuid.uuid4().hex[:10]}"
        now_str = datetime.now(timezone.utc).isoformat()

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""
            INSERT INTO financial_documents (
                document_id, filename, document_type, source, account_id,
                processing_status, uploaded_at, metadata_json, raw_content, content_type
            ) VALUES (%s, %s, %s, 'user_upload', %s, 'processing', %s, %s, %s, %s);
        """, (
            document_id, filename, detected_type, account_id, now_str, json.dumps({}),
            psycopg2.Binary(raw_bytes), _guess_content_type(filename)
        ))
        conn.commit()

        try:
            transactions: List[Dict[str, Any]] = []
            chunk_specs: List[Dict[str, Any]] = []

            if filename.lower().endswith((".csv", ".xlsx", ".xls")):
                df = _extract_dataframe(filename, raw_bytes)
                if df is None or df.empty:
                    raise ValueError("File could not be parsed as a table (CSV/XLSX) or contains no rows.")
                transactions = _transactions_from_dataframe(df)
                chunk_specs = _chunk_dataframe(df, filename)
            elif filename.lower().endswith(".pdf"):
                reader = PdfReader(io.BytesIO(raw_bytes))
                pages_text = [(page.extract_text() or "") for page in reader.pages]
                if not any(t.strip() for t in pages_text):
                    raise ValueError("PDF contained no extractable text (likely a scanned image PDF).")
                transactions = _transactions_from_pdf_text(pages_text)
                chunk_specs = cls._chunk_pdf_with_fallback(pages_text)
            else:
                raise ValueError(f"Unsupported file type for '{filename}'. Supported: PDF, CSV, XLSX.")

            for tx in transactions:
                tx_id = f"ftxn_{uuid.uuid4().hex[:12]}"
                c.execute("""
                    INSERT INTO financial_transactions (
                        transaction_id, account_id, document_id, transaction_date,
                        description, merchant, amount, transaction_type, category,
                        reference, balance_after, metadata_json, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    tx_id, account_id, document_id, tx["transaction_date"],
                    tx["description"], tx["merchant"], tx["amount"], tx["transaction_type"],
                    tx["category"], tx["reference"], tx["balance_after"], json.dumps({}), now_str
                ))

            embedded_count = 0
            for spec in chunk_specs:
                chunk_id = f"fchunk_{uuid.uuid4().hex[:12]}"
                embedding = generate_embedding(spec["content"])
                if embedding is not None:
                    embedded_count += 1
                c.execute("""
                    INSERT INTO financial_document_chunks (
                        chunk_id, document_id, chunk_index, content, embedding_json,
                        page_number, section, metadata_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    chunk_id, document_id, spec["chunk_index"], spec["content"],
                    json.dumps(embedding) if embedding is not None else None,
                    spec.get("page_number"), spec.get("section"), json.dumps({})
                ))

            c.execute("""
                UPDATE financial_documents SET
                    processing_status = 'ready',
                    metadata_json = %s
                WHERE document_id = %s;
            """, (json.dumps({
                "transactions_extracted": len(transactions),
                "chunks_created": len(chunk_specs),
                "chunks_embedded": embedded_count
            }), document_id))
            conn.commit()

            result = {
                "document_id": document_id,
                "filename": filename,
                "document_type": detected_type,
                "processing_status": "ready",
                "transactions_extracted": len(transactions),
                "chunks_created": len(chunk_specs),
                "chunks_embedded": embedded_count
            }
        except Exception as e:
            c.execute("""
                UPDATE financial_documents SET processing_status = 'failed', error_message = %s
                WHERE document_id = %s;
            """, (str(e), document_id))
            conn.commit()
            result = {
                "document_id": document_id,
                "filename": filename,
                "document_type": detected_type,
                "processing_status": "failed",
                "error_message": str(e)
            }
        finally:
            c.close()
            conn.close()

        return result

    @staticmethod
    def _chunk_pdf_with_fallback(pages_text: List[str]) -> List[Dict[str, Any]]:
        chunks = _chunk_pdf_pages(pages_text)
        if chunks:
            return chunks
        # Every page was empty of paragraph-shaped text but had *some* text
        # (e.g. no blank-line breaks at all) — fall back to one chunk per page
        # rather than silently indexing nothing.
        out = []
        for page_num, text in enumerate(pages_text, start=1):
            if text.strip():
                out.append({"content": text.strip()[:CHUNK_CHAR_LIMIT], "page_number": page_num, "section": None, "chunk_index": page_num - 1})
        return out
