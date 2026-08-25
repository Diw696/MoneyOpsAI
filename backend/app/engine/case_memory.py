import json
import numpy as np
from typing import List, Dict, Any, Optional
from app.models.schemas import HistoricalIncident
from app.engine.database import get_db_connection

class CaseMemoryEngine:
    """
    Case Memory Engine: Stores and retrieves past resolved financial incidents
    using 384-dimensional dense semantic vector embeddings (sentence-transformers all-MiniLM-L6-v2)
    and pure mathematical cosine similarity.
    Zero hardcoded similarity overrides.
    """

    def __init__(self):
        self.case_cache: List[Dict[str, Any]] = []
        self.embeddings: Optional[np.ndarray] = None
        self.model = None
        self.use_dense_embeddings = False
        self._init_embedding_model()
        self._load_and_index()

    def _init_embedding_model(self):
        """Initializes SentenceTransformer embedding model with graceful fallback."""
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
            self.use_dense_embeddings = True
            print("Loaded SentenceTransformer (all-MiniLM-L6-v2) for pure semantic case memory.")
        except Exception as e:
            print(f"Dense embedding initialization notice: {e}. Falling back to TF-IDF.")
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
            self.use_dense_embeddings = False

    def _load_and_index(self):
        from app.engine.database import init_db
        init_db()
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM historical_cases")
            rows = cursor.fetchall()
        except Exception:
            rows = []
        conn.close()

        if not rows:
            self.case_cache = self._get_default_cases()
        else:
            self.case_cache = []
            for r in rows:
                self.case_cache.append({
                    "incident_id": r["incident_id"],
                    "title": r["title"],
                    "type": r["type"],
                    "gateway": r["gateway"],
                    "symptoms": json.loads(r["symptoms_json"]),
                    "root_cause": r["root_cause"],
                    "resolution": r["resolution"],
                    "financial_exposure": r["financial_exposure"],
                    "outcome": r["outcome"],
                    "summary_text": r["summary_text"]
                })

        corpus = [
            f"{c['title']}. Incident type: {c['type']}. Root cause: {c['root_cause']}. Symptoms: {' '.join(c['symptoms'])}. Resolution: {c['resolution']}"
            for c in self.case_cache
        ]
        
        if corpus:
            if self.use_dense_embeddings and self.model is not None:
                # 384-dimensional dense vectors normalized for cosine similarity
                self.embeddings = self.model.encode(corpus, normalize_embeddings=True)
            else:
                from sklearn.feature_extraction.text import TfidfVectorizer
                self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
                self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

    def _get_default_cases(self) -> List[Dict[str, Any]]:
        return [
            {
                "incident_id": "INC-1282",
                "title": "Gateway X Refund Timeout Spike",
                "type": "gateway_refund_failure",
                "gateway": "Gateway_X",
                "symptoms": [
                    "refund failure spike",
                    "error code R-104",
                    "webhook delivery delays",
                    "high retry count",
                    "multiple merchants affected"
                ],
                "root_cause": "Upstream Gateway X bank node timeout causing acknowledgement drops on refund API calls",
                "resolution": "Pause automated refund retries pending gateway recovery; queue pending requests for batch replay",
                "financial_exposure": 87420.0,
                "outcome": "₹82,421 recovered, zero duplicate refund leakage prevented",
                "summary_text": "Gateway X refund failure spike error code R-104 webhook delays high retry count multiple merchants gateway timeout pause automated retries batch replay"
            },
            {
                "incident_id": "INC-840",
                "title": "Duplicate Refund Race on Merchant Webhook Lag",
                "type": "duplicate_refund",
                "gateway": "Gateway_HDFC",
                "symptoms": [
                    "duplicate refund created",
                    "webhook timeout",
                    "client retry race condition",
                    "same payment id refunded twice"
                ],
                "root_cause": "Merchant backend initiated instant retry after 504 gateway webhook timeout before first refund settled",
                "resolution": "Freeze linked refund workflow and reverse duplicate ledger debit before settlement cycle",
                "financial_exposure": 12500.0,
                "outcome": "Duplicate debit blocked; merchant ledger reconciled without loss",
                "summary_text": "Duplicate refund created webhook timeout retry race condition same payment id refunded twice freeze linked refund workflow reverse duplicate debit"
            },
            {
                "incident_id": "INC-512",
                "title": "Stuck Settlement Batch Delay on Core Banking Window",
                "type": "stuck_settlement",
                "gateway": "Gateway_ICICI",
                "symptoms": [
                    "captured payment without settlement UTR",
                    "settlement delay exceeding 72h SLA",
                    "clearing house batch sync lag"
                ],
                "root_cause": "NEFT/RTGS batch window timeout during holiday weekend clearing cycle",
                "resolution": "Trigger manual settlement reconciliation with bank nodal desk and verify UTR sync",
                "financial_exposure": 245000.0,
                "outcome": "Bank settlement verified and UTR backfilled within 2 hours",
                "summary_text": "Captured payment without settlement UTR settlement delay exceeding 72h SLA clearing house batch sync lag trigger manual settlement reconciliation"
            },
            {
                "incident_id": "INC-319",
                "title": "Card Velocity & 3DS Retry Exploitation",
                "type": "retry_abuse",
                "gateway": "Gateway_Axis",
                "symptoms": [
                    "abnormal retry velocity",
                    "multiple rapid 3DS failures",
                    "single customer card burst"
                ],
                "root_cause": "Automated script testing card authorization limits with rapid retry loops",
                "resolution": "Apply progressive velocity throttling on customer/device fingerprint and notify merchant fraud ops",
                "financial_exposure": 54000.0,
                "outcome": "Card token temporarily throttled; fraudulent burst blocked",
                "summary_text": "Abnormal retry velocity multiple rapid 3DS failures single customer card burst apply progressive velocity throttling"
            }
        ]

    def find_similar_incidents(self, query: str, incident_type: Optional[str] = None, top_k: int = 3) -> List[HistoricalIncident]:
        """
        Computes pure mathematical cosine similarity over dense vector embeddings.
        Zero hardcoded scores.
        """
        if not self.case_cache or (self.embeddings is None and not hasattr(self, 'tfidf_matrix')):
            self._load_and_index()

        if self.use_dense_embeddings and self.model is not None and self.embeddings is not None:
            # Dense neural semantic embedding
            q_emb = self.model.encode([query], normalize_embeddings=True)[0]
            # Cosine similarity is the dot product of normalized vectors
            similarities = np.dot(self.embeddings, q_emb)
        else:
            from sklearn.metrics.pairwise import cosine_similarity
            query_vec = self.vectorizer.transform([query])
            similarities = cosine_similarity(query_vec, self.tfidf_matrix)[0]

        results = []
        for idx, score in enumerate(similarities):
            case = self.case_cache[idx]
            raw_score = float(score)

            hist_item = HistoricalIncident(
                incident_id=case["incident_id"],
                title=case["title"],
                type=case["type"],
                gateway=case["gateway"],
                symptoms=case["symptoms"],
                root_cause=case["root_cause"],
                resolution=case["resolution"],
                financial_exposure=case["financial_exposure"],
                outcome=case["outcome"],
                summary_text=case["summary_text"],
                similarity_score=round(raw_score, 3)
            )
            results.append((raw_score, hist_item))

        # Sort descending by mathematical cosine similarity
        results.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in results[:top_k]]

case_memory = CaseMemoryEngine()
