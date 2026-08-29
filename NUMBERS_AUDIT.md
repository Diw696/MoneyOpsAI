# MoneyOps AI — Numbers Audit

Every headline number currently shown in the UI, with the exact query/code that
produces it and its confirmed live value, re-run against `moneyops_v2` on
2026-08-29 (post DB-wipe, post-restore, post schema fixes).

## Summary

**Everything reconfirmed identical to the last known-good state. No regressions found.**

- Evaluation metrics (Task 2): exact match to pre-wipe values — real re-run output included below.
- Incident Lab (Task 3): exact match at 250 orders / 250 payments / 5 refunds / 250 webhooks. All 4 incidents present; `find_similar_incidents` retrieves all 3 historical cases correctly.
- Similarity-score UI (Task 4): was **not** yet fixed in the prior pass — `InvestigationView.jsx` showed an unqualified "90% Similarity" with no indication it was a weighted composite. Fixed now: label reads `90% match (HIGH MATCH) — category + semantic signals`, with a real breakdown panel showing the raw cosine similarity (0.3397) separately from the four category-match components. Screenshot-verified live.
- Test suite (Task 5): **46/46 passing**, fresh run against the isolated `moneyops_v2_test` database.

No changes were made to Incident Lab generation logic, `eval_ground_truth`, or evaluation scoring methodology.

---

## Overview page

| Number | Displayed as | Query / computation | Confirmed value |
|---|---|---|---|
| Transactions | `stats.payments` — Overview card 1, header badge "PostgreSQL: N txs" | `SELECT COUNT(*) FROM payments;` (routes.py `get_database_stats`) | **252** (250 incident_lab + 2 razorpay_test) |
| Failed Payments | Overview card 2 | Frontend: `activeIncidents.reduce((s,i) => s + (i.evidence?.failed_payments_count ?? i.affected_payments ?? 0), 0)` over incidents where `status !== 'resolved'` | **7** (INC-0001 only; the 3 HIST incidents are resolved and excluded) |
| Active Incidents | Overview card 3 + Investigation tab badge | `incidents.filter(i => i.status !== 'resolved').length` (was `incidents.length` unfiltered before the Part 2 fix) | **1** (INC-0001) |
| Potential Exposure | Overview card 4 | `activeIncidents.reduce((s,i) => s + (i.potential_exposure ?? 0), 0)`; source column `incidents.potential_exposure`, populated at detection time from `evidence_json.potential_exposure_inr` | **₹38,296.34** |

---

## Data page — Real (Razorpay Test Mode)

| Number | Query | Confirmed value |
|---|---|---|
| Real orders | `SELECT COUNT(*) FROM orders WHERE source='razorpay_test';` | **922** |
| Real payments (total) | `SELECT COUNT(*) FROM payments WHERE source='razorpay_test';` | **2** (both `status='failed'`) |
| Real payments captured | `SELECT COUNT(*) FROM payments WHERE source='razorpay_test' AND status='captured';` | **0** |
| Real refunds | `SELECT COUNT(*) FROM refunds WHERE source='razorpay_test';` | **0** |
| Real webhooks | `SELECT COUNT(*) FROM webhook_events WHERE source='razorpay_test';` | **0** |

UI now shows "922 / created, not paid" under Orders and "2 / 0 captured" under Payments — both driven by the real `payments_captured` field the backend now computes (`GET /api/stats/sources`), not a hardcoded string.

## Data page — Simulation (Incident Lab)

| Number | Query | Confirmed value | vs. last known-good |
|---|---|---|---|
| Incident Lab orders | `SELECT COUNT(*) FROM orders WHERE source='incident_lab';` | **250** | unchanged |
| Incident Lab payments | `SELECT COUNT(*) FROM payments WHERE source='incident_lab';` | **250** | unchanged |
| Incident Lab refunds | `SELECT COUNT(*) FROM refunds WHERE source='incident_lab';` | **5** | unchanged |
| Incident Lab webhooks | `SELECT COUNT(*) FROM webhook_events WHERE source='incident_lab';` | **250** | unchanged |

Confirmed identical to the pre-wipe baseline after the `pg_restore` and every subsequent schema fix.

---

## Evaluation page

Real re-run, `POST /api/evaluation/run` → `batch_evaluator.run_full_evaluation()`, 2026-08-29T10:32:00Z:

```json
{
  "total_cases": 20,
  "confusion_matrix": { "true_positives": 12, "false_positives": 1, "false_negatives": 2, "true_negatives": 5 },
  "metrics": { "precision_pct": 92.3, "recall_pct": 85.7, "f1_pct": 88.9, "accuracy_pct": 85.0 }
}
```

| Number | Confirmed value | vs. last known-good |
|---|---|---|
| Precision | **92.3%** | unchanged |
| Recall | **85.7%** | unchanged |
| F1 | **88.9%** | unchanged |
| Accuracy | **85.0%** | unchanged |
| True Positives | **12** | unchanged |
| False Positives | **1** | unchanged |
| False Negatives | **2** | unchanged |
| True Negatives | **5** | unchanged |

No investigation into a discrepancy was needed — the re-run output is byte-identical to the values recorded before the DB wipe. `eval_ground_truth` itself was untouched throughout the wipe incident (it was never in the truncate/delete list of the fixtures that caused it), which is consistent with this result.

---

## Investigation page (INC-0001)

| Number | Displayed as | Query / computation | Confirmed value |
|---|---|---|---|
| Evidence Confidence | "85% • VERY HIGH" | `ai_investigations.confidence` for the latest completed investigation (`inv_96cc623137`), `Math.round(confidence * 100)` | **85%** |
| IsolationForest anomaly score | "Anomaly Strength" bullet | `incidents.evidence_json.ml_anomaly_score` | **1.0** |
| Failure rate / peer baseline / ratio | Evidence cards | `evidence_json.failure_rate_pct` / `peer_failure_rate_pct` / `failure_rate_ratio` | **15.91% / 1.46% / 10.92x** |

### Case Memory similarity — raw vs. composite, side by side

`case_memory.find_similar_incidents('INC-0001')`, real function call, re-run live:

| Historical case | Composite score (UI) | Raw cosine similarity | Contribution breakdown |
|---|---|---|---|
| INC-HIST-001 | **90.0%** (HIGH MATCH) | **0.3397** | cosine 10.0 + type_match 35.0 + entity_match 25.0 + error_code_match 20.0 + severity_match 0.0 = 90.0 |
| INC-HIST-002 | 55.0% (MODERATE MATCH) | 0.2774 | cosine 20.0 + type_match 35.0 + entity_match 0.0 + error_code_match 0.0 + severity_match 0.0 = 55.0 |
| INC-HIST-003 | 15.0% (LOW MATCH) | 0.0620 | cosine 10.0 + type_match 0.0 + entity_match 0.0 + error_code_match 0.0 + severity_match 0.0 = 15.0 |

**UI fix confirmed live (Task 4):** `InvestigationView.jsx` previously showed only `"{score}% Similarity ({tier})"` with no indication this was a hybrid score. Now reads `"{score}% match ({tier}) — category + semantic signals"`, with an expandable breakdown panel showing the raw cosine similarity number and each category-match component separately. Verified with a fresh screenshot against the live running app.

---

## Test suite

```
$ pytest tests/ -q          (against isolated moneyops_v2_test, dropped and recreated fresh)
46 passed in 14.65s
```

This is run against `moneyops_v2_test`, provisioned and guarded by `tests/conftest.py` — confirmed by re-checking `moneyops_v2` row counts before and after the run (payments 252, orders 1172, refunds 5, webhook_events 250 — identical before/after).

---

## Source references

- `backend/app/api/routes.py` — `get_database_stats`, `get_source_distribution`, `get_similar_incidents`, `run_batch_evaluation` (routes calling into the engine)
- `backend/app/engine/batch_evaluator.py` — `run_full_evaluation`
- `backend/app/engine/case_memory.py` — `compute_cosine_similarity`, `calculate_similarity`, `find_similar_incidents`
- `backend/app/engine/anomaly_detector.py` — writes `incidents.evidence_json`
- `frontend/src/components/OverviewView.jsx`, `DataView.jsx`, `InvestigationView.jsx`, `EvaluationView.jsx`
