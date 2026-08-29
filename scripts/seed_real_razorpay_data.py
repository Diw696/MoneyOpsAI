"""
scripts/seed_real_razorpay_data.py

Seeds genuine test-mode Orders via Razorpay's real REST API using server-side
credentials from .env, then syncs whatever real objects exist on the account
(orders, payments, refunds) through CanonicalEvent -> IngestionPipeline -> PostgreSQL.

SCOPE (diagnosed, not guessed — see proof report for the investigation):
- Razorpay's live Checkout page loads real anti-fraud/bot-detection infrastructure
  (hCaptcha + a behavioral "Human Security" SDK) the moment a scripted browser
  submits the card form. Defeating that to script a captured payment would mean
  circumventing Razorpay's own fraud tooling on a live system, which this project
  deliberately does not attempt.
- This account's Checkout also does not offer UPI as a payment method (confirmed
  by inspecting the live rendered method list), so the UPI test-VPA auto-success
  shortcut (`success@razorpay`) is not available either.
- Server-to-server (S2S) payment creation, which would bypass Checkout entirely,
  returned HTTP 400 "URL not found on the server" — this account does not have
  S2S enabled (a manual Razorpay approval, not something a fresh test account gets).
- Net result: Orders can be created and synced genuinely via the REST API.
  Captured Payments/Refunds/Webhooks stay at whatever the account's real state is
  (this account currently has 2 real failed test payments and 0 refunds) because
  there is no remaining API-only path to a captured payment. That is reported
  honestly below rather than padded.

Invariants:
- Does NOT fabricate synthetic records as 'razorpay_test'.
- Contacts https://api.razorpay.com/v1 directly with Basic Auth.
- Only ADDS data; never deletes or truncates existing rows.
"""

import os
import sys
import time
import random
import httpx
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from app.core.config import settings
from app.integrations.razorpay.client import razorpay_client
from app.integrations.razorpay.mapper import RazorpayMapper
from app.engine.pipeline import IngestionPipeline
from app.engine.database import init_db


def build_order_payload(amount_rupees: int, merchant: str, receipt: str) -> dict:
    return {
        "amount": amount_rupees * 100,
        "currency": "INR",
        "receipt": receipt,
        "notes": {
            "merchant_tag": merchant,
            "environment": "test_mode",
            "source": "moneyops_real_seed",
        },
    }


def seed_real_razorpay_orders(count: int = 300):
    print("=================================================================")
    print(" MONEYOPS AI V2 — REAL RAZORPAY TEST-MODE ORDER SEED SCRIPT")
    print("=================================================================")

    key_id = settings.RAZORPAY_KEY_ID
    key_secret = settings.RAZORPAY_KEY_SECRET

    if not key_id or not key_secret:
        print("[ERROR] Razorpay credentials missing in .env (RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET).")
        return {"status": "error", "message": "Missing credentials"}

    print(f"Target Account Key ID  : {key_id[:12]}...")
    print(f"Target Orders to Create: {count}")
    print("Target Gateway Base    : https://api.razorpay.com/v1")
    print()
    print("NOTE: This script creates real Orders only. It does NOT attempt to")
    print("script captured Payments — Razorpay's Checkout enforces bot-detection")
    print("(hCaptcha / behavioral risk scoring) that this project will not try to")
    print("circumvent, and this account has neither UPI checkout nor S2S enabled.")
    print("Payments/Refunds/Webhooks below reflect the account's real, unpadded state.")
    print()

    auth = (key_id, key_secret)
    created_orders = []
    failed_items = []

    merchants = ["CloudScale_SaaS", "NovaStore_Retail", "PayPulse_Gaming", "QuickDrop_QCommerce", "ZenTravels"]

    with httpx.Client(timeout=20.0) as client:
        for i in range(1, count + 1):
            amount_rupees = random.choice([299, 499, 999, 1499, 2499, 4999, 9999, 14999])
            merchant = random.choice(merchants)
            receipt = f"rcpt_real_{int(time.time())}_{i:04d}"
            order_payload = build_order_payload(amount_rupees, merchant, receipt)

            try:
                order_res = client.post("https://api.razorpay.com/v1/orders", auth=auth, json=order_payload)
                if order_res.status_code not in (200, 201):
                    print(f"  [FAIL] Order {i} failed: HTTP {order_res.status_code} -> {order_res.text[:250]}")
                    failed_items.append({"index": i, "status_code": order_res.status_code, "response": order_res.text})
                    continue

                order_data = order_res.json()
                created_orders.append(order_data)
                if i % 25 == 0 or i == count:
                    print(f"  [OK] Created {i}/{count} real Razorpay orders (latest: {order_data.get('id')} / Rs {amount_rupees})")

            except Exception as e:
                print(f"  [FAIL] Network error while processing item {i}: {e}")
                failed_items.append({"index": i, "status_code": None, "response": str(e)})

            time.sleep(0.35)

    print()
    print(f"Successfully created {len(created_orders)} genuine orders in Razorpay Test Mode account.")
    print(f"Failed items: {len(failed_items)}")

    print("\n--- Synchronizing live Razorpay objects into PostgreSQL via Canonical Pipeline ---")
    init_db()
    orders = razorpay_client.fetch_all_orders(max_items=1000)
    payments = razorpay_client.fetch_all_payments(max_items=1000)
    refunds = razorpay_client.fetch_all_refunds(max_items=1000)

    canonical_events = []
    for o in orders:
        canonical_events.append(RazorpayMapper.order_to_canonical(o, source="razorpay_test"))
    for p in payments:
        canonical_events.append(RazorpayMapper.payment_to_canonical(p, source="razorpay_test"))
    for r in refunds:
        canonical_events.append(RazorpayMapper.refund_to_canonical(r, source="razorpay_test"))

    ingest_stats = IngestionPipeline.ingest_batch(canonical_events)

    captured_payments = sum(1 for p in payments if p.status == "captured")
    failed_payments = sum(1 for p in payments if p.status == "failed")

    print()
    print("=================================================================")
    print(" HARD SUMMARY (do not skim past this)")
    print("=================================================================")
    print(f" Orders created this run     : {len(created_orders)}")
    print(f" Orders failed this run      : {len(failed_items)}")
    print(f" Total orders on account     : {len(orders)}")
    print(f" Total payments on account   : {len(payments)}  (captured: {captured_payments}, failed: {failed_payments})")
    print(f" Total refunds on account    : {len(refunds)}")
    print(f" Database ingestion stats    : {ingest_stats}")
    print("=================================================================")

    return {
        "status": "success",
        "orders_created_on_razorpay": len(created_orders),
        "failed_items": len(failed_items),
        "synced_orders": len(orders),
        "synced_payments": len(payments),
        "synced_refunds": len(refunds),
        "captured_payments": captured_payments,
        "failed_payments": failed_payments,
        "ingest_stats": ingest_stats,
    }


if __name__ == "__main__":
    load_dotenv(BASE_DIR / ".env")
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    seed_real_razorpay_orders(count)
