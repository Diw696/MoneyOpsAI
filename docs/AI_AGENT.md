# MoneyOps AI — AI Investigation Agent & Tool Calling

The Investigation Agent is an autonomous reasoning engine designed to investigate operational anomalies across payment processing layers.

---

## 1. Multi-Stage Reasoning Workflow

The investigation progresses across 4 deliberate stages:

1. **Sentinel Stage:** Ingests anomaly trigger parameters (incident type, error code, gateway, target entity) and isolates the affected scope.
2. **Investigator Stage:** Traverses cross-entity financial graph (`get_payment_graph`) and calculates blast radius (`get_gateway_telemetry`).
3. **Analyst Stage:** Contextualizes findings against rolling merchant behavioral baselines (`get_merchant_profile`) and retrieves historical precedent resolutions from dense semantic Case Memory (`find_similar_incidents`).
4. **Recovery Stage:** Evaluates the Action Governor policy tier and generates a structured, validated `InvestigationReport`.

---

## 2. Available Investigative Python Tools

| Tool Name | Parameters | Responsibility |
| :--- | :--- | :--- |
| `get_incident` | `incident_id: str` | Retrieves high-level incident record and detection metadata. |
| `get_payment` | `payment_id: str` | Fetches payment record, connected refunds, webhooks, and settlements. |
| `get_payment_graph` | `payment_id: str` | Traverses NetworkX graph to extract 2-hop entity relationships and duplicate refund flags. |
| `get_gateway_telemetry`| `gateway_name: str`, `error_code: str` | Computes cross-merchant blast radius and failure counts for a gateway node. |
| `get_merchant_profile` | `merchant_id: str` | Fetches rolling 30-day behavioral baselines and deviation metrics. |
| `get_anomaly_features` | `entity_id: str`, `entity_type: str`, `payload: dict` | Runs the unsupervised Isolation Forest ML model to produce an anomaly score. |
| `find_similar_incidents`| `query: str`, `incident_type: str` | Queries dense vector Case Memory using neural embeddings and cosine similarity. |

---

## 3. Provider-Agnostic LLM Interface

MoneyOps AI uses a clean abstraction layer (`BaseLLMProvider` in `backend/app/engine/llm_provider.py`):

1. **Anthropic Claude Provider:** Configured via `ANTHROPIC_API_KEY` and optional `LLM_MODEL` (e.g. `claude-3-5-sonnet-20241022`).
2. **Local Model Provider:** Connects to local LLMs (Ollama, LMStudio, vLLM) via `LLM_PROVIDER=local` and `LLM_BASE_URL=http://localhost:11434/v1` using standard function calling.
3. **Deterministic Fallback Reasoner:** Executes the exact same tool queries locally against SQLite, NetworkX, Isolation Forest, and SentenceTransformers, dynamically calculating exposure and evidence with zero external dependencies.
