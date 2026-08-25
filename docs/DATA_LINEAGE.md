# MoneyOps AI — Data Lineage & Forensic Provenance

Every financial record and incident in MoneyOps AI maintains complete auditability and data provenance from ingestion to governed action.

---

## 1. End-to-End Lineage Flow

```text
1. DATA ORIGIN
   - Source A: Razorpay Test Mode (Live REST API & HMAC-SHA256 Webhooks)
   - Source B: MoneyOps Incident Laboratory (Synthetic Reproducible Seed)
         │
         ▼
2. RAW INGESTION LAYER (`raw_external_events`)
   - Untouched JSON payloads stored before normalization
   - Idempotency enforced via `external_event_id` (e.g. `x-razorpay-event-id`)
   - Replay and audit capability preserved
         │
         ▼
3. CANONICAL NORMALIZATION (`canonical_events`)
   - Uniform `CanonicalEvent` model
   - Paise converted to standard float INR
   - Relational entity tables updated (`payments`, `refunds`, `orders`)
         │
         ▼
4. FEATURE ENGINE & MERCHANT BEHAVIORAL MEMORY
   - Live SQL window aggregations
   - Rolling refund rates, failure rates, and retry counts computed against 30-day merchant baselines
         │
         ▼
5. ML ANOMALY DETECTION (Isolation Forest)
   - 8 engineered financial features evaluated
   - Pure mathematical score $[0, 1]$ generated with granular signal attribution
         │
         ▼
6. MONEY GRAPH TRAVERSAL (NetworkX)
   - Multi-hop entity clusters traversed (`Payment → Order → Refunds → Webhooks`)
   - Cross-merchant gateway blast radius computed
         │
         ▼
7. DENSE SEMANTIC CASE MEMORY (SentenceTransformers)
   - 384-dimensional dense neural embeddings (`all-MiniLM-L6-v2`)
   - Pure mathematical cosine similarity matching historical precedents
         │
         ▼
8. AI INVESTIGATION AGENT (Provider-Agnostic ReAct)
   - Autonomous tool-calling loop querying database, graph, features, and case memory
   - Strict separation of observed facts from root-cause hypotheses
         │
         ▼
9. ACTION GOVERNOR (Three-Tier Policy Safeguard)
   - GREEN (Autonomous Observe), YELLOW (Advisory Recommend), RED (Human Authorization Enforced)
         │
         ▼
10. IMMUTABLE AUDIT LEDGER (`audit_logs`)
   - Cryptographically logged execution record with unique Audit ID (e.g. `ACT-5B0A49B6`)
```

---

## 2. Lineage Audit Command

To audit relational database row counts and data source breakdowns:
```powershell
$env:PYTHONPATH="backend"
python -m app.jobs.db_stats
```
