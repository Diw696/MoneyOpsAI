import pytest
from app.engine.agent import investigation_agent
from app.models.schemas import ActionTier

def test_agent_investigation_golden_demo():
    report = investigation_agent.investigate("INC-2841")
    assert report.incident_id == "INC-2841"
    assert report.severity == "critical"
    assert report.confidence > 0.60
    assert report.action_tier == ActionTier.RED_EXECUTE
    assert report.requires_approval is True
    assert len(report.agent_steps) >= 4
    assert len(report.similar_incidents) >= 1
    assert report.similar_incidents[0].incident_id == "INC-1282"

def test_agent_investigation_duplicate_refund():
    report = investigation_agent.investigate("INC-2840")
    assert report.incident_id == "INC-2840"
    assert report.financial_exposure == 4999.0
    assert "duplicate" in report.root_cause.lower() or "refund" in report.root_cause.lower()
    assert report.action_tier == ActionTier.RED_EXECUTE
