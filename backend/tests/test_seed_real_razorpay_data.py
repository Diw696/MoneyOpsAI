from scripts.seed_real_razorpay_data import build_order_payload


def test_build_order_payload_uses_valid_live_fields():
    payload = build_order_payload(
        amount_rupees=299,
        merchant="CloudScale_SaaS",
        receipt="rcpt_probe_001",
    )

    assert payload["amount"] == 29900
    assert payload["currency"] == "INR"
    assert payload["receipt"] == "rcpt_probe_001"
    assert payload["notes"]["merchant_tag"] == "CloudScale_SaaS"
    assert payload["notes"]["source"] == "moneyops_real_seed"
