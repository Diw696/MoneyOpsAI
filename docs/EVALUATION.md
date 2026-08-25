# MoneyOps AI — System Evaluation & Interview Defense Guide

This document contains evaluation benchmarks, architecture tradeoffs, and technical talking points for the **Razorpay Internship AI Project selection**.

---

## 1. Prototype vs. Production Scale Evolution

| Subsystem | MoneyOps AI Prototype Implementation | Enterprise Production Architecture Evolution |
| :--- | :--- | :--- |
| **Ingestion Pipeline** | `asyncio.Queue` + Canonical Ingestion Router | Distributed Apache Kafka topic with Apache Flink stream processing |
| **Relational Database** | SQLite (WAL mode, foreign keys, indexes) | CockroachDB / AWS Aurora PostgreSQL with multi-region sharding |
| **Money Graph** | In-memory NetworkX directed graph | Neo4j / Amazon Neptune distributed graph database |
| **Case Memory** | `SentenceTransformer (all-MiniLM-L6-v2)` + in-memory cosine | Qdrant / Milvus / pgvector with HNSW index |
| **Feature Engine** | Live relational SQL window aggregations | Feast / Hopsworks distributed real-time feature store |
| **LLM Reasoning** | Provider-Agnostic ReAct Tool-Calling | Fine-tuned FinOps reasoning LLM + constrained JSON decoding |

---

## 2. Technical Interview Defense — Key Talking Points

### Question: "Why didn't you just use an LLM with prompt engineering?"
> *"LLMs alone are bad financial bookkeepers—they hallucinate numbers and cannot reliably calculate blast radius across thousands of relational rows. MoneyOps AI uses the LLM strictly as a **reasoning and orchestration engine**. The database and NetworkX graph are the sources of mathematical truth. The LLM decides which tools to call, inspects real query outputs, and synthesizes hypotheses."*

### Question: "How do you ensure actions don't cause unintended financial loss?"
> *"Through our **Three-Tier Action Governor**. High-risk actions like pausing refund retries or freezing merchant ledger debits are classified as RED tier. The AI agent is architecturally barred from direct state mutation; it can only construct an approval request with evidence, requiring an authenticated human operator to authorize the action."*

### Question: "How do you detect anomalies without labeled fraud/incident datasets?"
> *"We use an unsupervised **Isolation Forest** pipeline trained on 8 engineered behavioral features (merchant refund deviation, retry velocity, gateway failure rate, settlement delay, etc.). This isolates anomalies geometrically in feature space without needing historical incident labels."*
