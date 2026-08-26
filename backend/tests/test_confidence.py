import pytest
from app.engine.confidence import calculate_evidence_confidence

def test_confidence_calculation_perfect_anomaly():
    """Tests confidence calculation when all 5 empirical indicators are maximally corroborated."""
    res = calculate_evidence_confidence(
        anomaly_score=1.0,
        failure_rate_pct=19.08,
        peer_failure_rate_pct=3.52,  # 5.42x ratio -> full 25% contrib
        top_failure_code_share_pct=85.06,  # 0.8506 * 20% -> ~17.0%
        failed_payments_count=87,  # >= 50 -> full 15% contrib
        affected_merchants_count=10  # >= 8 -> full 15% contrib
    )

    assert res["score"] >= 85.0
    assert res["confidence_level"] == "VERY HIGH"
    assert res["factors"]["anomaly_strength_contrib"] == 25.0
    assert res["factors"]["peer_deviation_contrib"] == 25.0
    assert res["factors"]["sample_volume_contrib"] == 15.0
    assert res["factors"]["merchant_breadth_contrib"] == 15.0
    assert res["score_fraction"] >= 0.85

def test_confidence_calculation_weak_anomaly():
    """Tests confidence calculation on borderline anomaly with low sample size."""
    res = calculate_evidence_confidence(
        anomaly_score=0.4,
        failure_rate_pct=4.2,
        peer_failure_rate_pct=3.8,  # ~1.1x ratio -> low peer contrib
        top_failure_code_share_pct=30.0,
        failed_payments_count=2,  # < 3 -> low volume contrib
        affected_merchants_count=1
    )

    assert res["score"] < 60.0
    assert res["confidence_level"] in ["LOW", "MODERATE"]
    assert res["factors"]["anomaly_strength_contrib"] == 10.0

def test_confidence_zero_division_safety():
    """Tests confidence calculation handles edge cases (zero peer baseline, None values) without crashing."""
    res = calculate_evidence_confidence(
        anomaly_score=0.0,
        failure_rate_pct=0.0,
        peer_failure_rate_pct=0.0,
        top_failure_code_share_pct=0.0,
        failed_payments_count=0,
        affected_merchants_count=0
    )

    assert res["score"] >= 0.0
    assert res["score"] <= 100.0
    assert isinstance(res["factors"], dict)
