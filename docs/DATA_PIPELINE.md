# MoneyOps AI — Canonical Ingestion Pipeline

The Ingestion Pipeline standardizes financial streams from diverse external origins into a structured internal representation (`CanonicalEvent`) before evaluation, persistence, and graph construction.

---

## 1. Pipeline Stages & Single Responsibility Principles

```text
  [ External Source ] ───▶ [ 1. EventValidator ]
                                    │
                                    ▼
                           [ 2. EventNormalizer ]
                                    │ (Produces CanonicalEvent)
                                    ▼
                           [ 3. AnomalyProcessor ]
                                    │ (Evaluates Isolation Forest)
                                    ▼
                           [ 4. EventRepository ]
                                    │ (Persists to SQLite WAL)
                                    ▼
                           [ 5. GraphProcessor ]
                                    │ (Mutates NetworkX DiGraph)
                                    ▼
                           [ Complete / Broadcast ]
```

### Stage 1: `EventValidator`
- Verifies structural invariants: non-null payload, valid event topic strings, positive amounts.
- Rejects malformed or incomplete messages immediately before state mutation.

### Stage 2: `EventNormalizer`
- Ingests Razorpay webhook JSON structures or internal synthetic lifecycle events.
- Converts monetary values from paise to standard INR float representation.
- Outputs uniform `CanonicalEvent` model.

### Stage 3: `AnomalyProcessor`
- Feeds normalized transaction and merchant feature vectors into the scikit-learn `IsolationForest` pipeline.
- Calculates model anomaly score $[0, 1]$ and flags anomalous records (`is_anomaly = True` when score $\ge 0.65$).

### Stage 4: `EventRepository`
- Atomically writes to `canonical_events` log table and corresponding relational tables (`payments`, `refunds`, `webhook_events`, `orders`).

### Stage 5: `GraphProcessor`
- Updates the in-memory NetworkX directed graph, adding entity nodes (`Payment`, `Refund`, `WebhookEvent`) and directional relationship edges (`PAID_WITH`, `REFUNDED_BY`, `TRIGGERED_WEBHOOK`).

---

## 2. Ingestion Pipeline Usage

### Programmatic Ingestion:
```python
from app.engine.event_pipeline import event_pipeline

result = event_pipeline.process_event(
    raw_event_type="payment.captured",
    raw_payload={
        "id": "pay_live_001",
        "order_id": "ord_live_001",
        "amount": 249900,  # paise
        "status": "captured",
        "method": "card",
        "notes": {"merchant_id": "merch_Nova_Store"},
        "acquirer_data": {"bank": "Gateway_HDFC"}
    },
    source="razorpay_webhook"
)

print(result["status"], result["canonical_id"], result["anomaly_score"])
```
