import pytest
from app.engine.case_memory import case_memory

def test_dense_semantic_similarity():
    query = "Gateway timeout error R-104 causing refund failure spike"
    results = case_memory.find_similar_incidents(query, top_k=3)
    assert len(results) >= 1
    top_match = results[0]
    assert top_match.incident_id == "INC-1282"
    assert top_match.similarity_score > 0.40  # mathematical cosine similarity

def test_duplicate_refund_similarity():
    query = "Duplicate refund issued on payment due to webhook delivery timeout"
    results = case_memory.find_similar_incidents(query, top_k=3)
    assert len(results) >= 1
    top_match = results[0]
    assert top_match.incident_id == "INC-840"
    assert top_match.similarity_score > 0.40
