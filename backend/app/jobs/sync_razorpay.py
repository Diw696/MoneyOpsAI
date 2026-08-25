import argparse
import sys
from app.integrations.razorpay.client import razorpay_client
from app.integrations.razorpay.mapper import RazorpayMapper
from app.engine.event_pipeline import event_pipeline
from app.engine.database import get_db_connection

def sync_razorpay(count: int = 20, from_ts: int = None, to_ts: int = None):
    print("=" * 60)
    print(" MONEYOPS AI — RAZORPAY TEST MODE RECONCILIATION & SYNC")
    print("=" * 60)
    print(f"Fetching latest {count} payments from Razorpay API...")

    payments = razorpay_client.fetch_payments(count=count, from_timestamp=from_ts, to_timestamp=to_ts)
    if not payments:
        print("No live Razorpay payments fetched (or credentials offline).")
        print("To sync with live Razorpay Test Mode, set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env.")
        return

    synced_count = 0
    duplicate_count = 0

    for p in payments:
        canon = RazorpayMapper.payment_to_canonical(p)
        res = event_pipeline.process_event(
            raw_event_type="payment.captured" if p.status == "captured" else "payment.failed",
            raw_payload={
                "id": p.id,
                "payload": {"payment": {"entity": p.model_dump()}}
            },
            source="razorpay_api_sync",
            external_event_id=f"sync_{p.id}"
        )
        if res.get("status") == "duplicate_skipped":
            duplicate_count += 1
        else:
            synced_count += 1

    print(f"Sync Complete: {synced_count} new entities ingested, {duplicate_count} duplicates skipped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synchronize Razorpay Test Mode payments into MoneyOps database.")
    parser.add_argument("--count", type=int, default=20, help="Number of records to fetch")
    args = parser.parse_args()
    sync_razorpay(count=args.count)
