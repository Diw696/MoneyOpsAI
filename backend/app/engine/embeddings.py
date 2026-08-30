"""
backend/app/engine/embeddings.py

Real semantic embeddings for the Financial Copilot's RAG layer, via Gemini's
embedding endpoint. pgvector is not installed on this project's Postgres
instance (verified: no 'vector' row in pg_available_extensions), so vectors
are stored as JSON float arrays in PostgreSQL and ranked with in-process
cosine similarity — the same proven pattern already used by
case_memory.py/incident_embeddings, upgraded here to a real embedding model
instead of a small hardcoded-vocabulary term-frequency vector.
"""

import httpx
import numpy as np
from typing import List, Optional
from app.core.config import settings

EMBEDDING_MODEL = "gemini-embedding-001"


def generate_embedding(text: str, timeout_sec: float = 30.0) -> Optional[List[float]]:
    """
    Calls Gemini's embedContent endpoint for a single piece of text.
    Returns None (never a fabricated vector) if the API key is unconfigured
    or the request fails — callers must treat that as "no embedding available"
    rather than substituting anything.
    """
    api_key = settings.GEMINI_API_KEY
    if not api_key or api_key.startswith("YOUR_") or len(api_key) <= 10:
        return None

    text = (text or "").strip()
    if not text:
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBEDDING_MODEL}:embedContent?key={api_key}"
    body = {
        "model": f"models/{EMBEDDING_MODEL}",
        "content": {"parts": [{"text": text[:8000]}]}
    }
    try:
        with httpx.Client(timeout=timeout_sec) as client:
            res = client.post(url, json=body, headers={"Content-Type": "application/json"})
        if res.status_code != 200:
            return None
        data = res.json()
        values = data.get("embedding", {}).get("values")
        if not values:
            return None
        return [float(v) for v in values]
    except Exception:
        return None


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Cosine similarity between two embedding vectors."""
    a = np.array(vec_a, dtype=np.float64)
    b = np.array(vec_b, dtype=np.float64)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0 or a.shape != b.shape:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
