# MoneyOps AI — Semantic Case Memory

MoneyOps AI uses **Dense Vector Neural Embeddings** to retrieve past resolved financial incidents and precedent recovery actions.

---

## 1. Embedding Architecture

- **Model:** `SentenceTransformer("all-MiniLM-L6-v2")`
- **Embedding Dimensions:** 384-dimensional dense vectors normalized to unit length ($\|v\| = 1$).
- **Fallback:** Normalized TF-IDF vectorizer if offline.

---

## 2. Mathematical Similarity Calculation

Given a semantic query $q$ describing current incident symptoms, the engine computes normalized embedding vector $\mathbf{e}_q$.

For each indexed historical case $i$ with embedding vector $\mathbf{e}_i$:
$$\text{Similarity}(q, i) = \mathbf{e}_q \cdot \mathbf{e}_i = \sum_{k=1}^{384} e_{q,k} \cdot e_{i,k}$$

Because all embeddings are unit-normalized, the inner dot product equals the exact **Cosine Similarity** ($\cos \theta$).

### Zero Hardcoded Overrides:
All similarity scores shown in the UI are pure mathematical outputs of this dot product computation.

---

## 3. Historical Precedent Corpus

The institutional memory contains resolved fintech incident precedents:
- **`INC-1282`:** Gateway X Refund Timeout Spike (Upstream bank nodal drop, resolved by pausing automated retries).
- **`INC-840`:** Duplicate Refund Race on Webhook Lag (504 timeout retry race, resolved by freezing refund workflow).
- **`INC-512`:** Stuck Settlement Batch Delay on Core Banking Window (Batch window clearing timeout, resolved by manual nodal sync).
- **`INC-319`:** Card Velocity & 3DS Retry Exploitation (Scripted retry burst, resolved by progressive velocity throttling).
