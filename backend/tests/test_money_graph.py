import pytest
from app.engine.money_graph import money_graph
from app.engine.seed_data import seed_database

def test_money_graph_payment_cluster():
    cluster = money_graph.get_payment_cluster("pay_P19283")
    assert cluster["payment"]["id"] == "pay_P19283"
    assert cluster["merchant_id"] == "merch_Nova_Store"
    assert len(cluster["refunds"]) == 2  # Duplicate refunds
    assert cluster["is_duplicate_refund"] is True

def test_money_graph_gateway_blast_radius():
    blast = money_graph.get_gateway_blast_radius("Gateway_X", "R-104")
    assert blast["gateway"] == "Gateway_X"
    assert blast["affected_payments_count"] >= 1
    assert blast["affected_refunds_count"] >= 1
    assert blast["affected_merchants_count"] >= 1
