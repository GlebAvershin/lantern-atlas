# Lantern Atlas · Technologies & Engineering Solutions

<p align="center">
  <a href="TECHNOLOGIES.md"><b>English</b></a> •
  <a href="TECHNOLOGIES.ru.md"><b>Русский</b></a>
</p>

Lantern Atlas is an island lighthouse beam-routing puzzle built on **Godot 4.5.1**. Players transmit beams of light across coastal archipelagoes, activating remote relays and unlocking sealed harbor stations over 8 handcrafted charts with an optimal hint solver. This engineering dossier documents the algorithmic C++17 solver oracle, Kubernetes multi-replica resilience, Circuit Breaker cloud AI gateway, FinOps semantic caching, and Semantic RAG retrieval. [Play in Browser (WASM)](https://glebavershin.github.io/lantern-atlas/) · [Download Desktop Build](https://github.com/GlebAvershin/lantern-atlas/releases) · [Nightwatch Gameplay Video](evidence/nightwatch.mp4)

---

## 🎯 Minimal Move Proofs Across All 8 Charts

The C++17 algorithmic oracle (`studio/oracle.cpp`) independently models the full state graph of all 8 charts using breadth-first search (BFS) and A* heuristic pathfinding:
* **Charts 1–2 (Introductory):** Minimal solution length: **1 move** (direct beam alignment).
* **Charts 3–5 (Relay Chains):** Minimal solution length: **2 to 3 moves** (compound refraction).
* **Charts 6–8 (Deep Archipelagoes):** Minimal solution length: **4 to 6 moves** (multi-station cycle elimination).

Every optimal move sequence was proved mathematically to have no shorter valid trajectory, serving as the ground-truth oracle for in-game hint systems. The audit script was executed via AWS Agent Toolkit (`aws___run_script`) under AWS Free tier with 0 billable API calls. [Receipts & Checksums](evidence/aws-toolkit.json) · [Audit Script](../studio/research/aws_audit.py) · [Replay Guide](https://github.com/GlebAvershin/lantern-atlas/blob/main/studio/research/README.md#aws-agent-toolkit-replay)

---

## ☁️ Cross-Service Verification via Cloud MCP Servers

1. **Amplitude MCP:** Verified 8 `game.study_evaluated` events recorded during research evaluation runs.
2. **Sentry MCP:** Queried issue **PYTHON-8** for `solution_gap` telemetry and verified the `report_oracle` action.
3. **Databricks MCP (`system.ai.dbsql`):** Queried level completion metrics; all 4 rows matched local SQLite calculations byte-for-byte.

[Query Parameters & SQL Evidence](evidence/service-mcp.json) · [Analytical SQL Queries](../studio/research/metrics.sql)

---

## 🔬 Reproducibility Verification

* **C++17 Oracle & GDScript Tests:** 12 automated unit tests verified checkpoint saving, lighthouse beam reflection, and chart parity.
* **Database & Cloud Consistency:** Replayed all 4 analytical scenarios; SQLite matched Databricks outputs identically. Sentry and Amplitude accepted 5 production event envelopes with HTTP 200 responses. [Verification Results](evidence/replay-check.json) · [Replication Command](https://github.com/GlebAvershin/lantern-atlas/blob/main/studio/research/README.md#verifying-published-evidence)

---

## 📋 Minimal Chart Solution Oracle Table

| Chart ID | Lighthouse Station | Minimal Moves Required | Verification Oracle |
| :---: | :--- | :---: | :---: |
| **Chart 1** | Pelican Shoals | 1 Move | C++17 BFS / A* Oracle |
| **Chart 2** | Mist Reef | 1 Move | C++17 BFS / A* Oracle |
| **Chart 3** | Iron Bell Bay | 2 Moves | C++17 BFS / A* Oracle |
| **Chart 4** | Kraken Trench | 3 Moves | C++17 BFS / A* Oracle |
| **Chart 5** | Anchor Point | 3 Moves | C++17 BFS / A* Oracle |
| **Chart 6** | Obsidian Strait | 4 Moves | C++17 BFS / A* Oracle |
| **Chart 7** | Storm Reach | 5 Moves | C++17 BFS / A* Oracle |
| **Chart 8** | Aurora Harbor | 6 Moves | C++17 BFS / A* Oracle |

---

## 📱 Responsive HUD Layout Generation via LLM & MCP

| Method / Model | Correct Region Placements | Execution Environment |
| :--- | :---: | :--- |
| Lexical Matching & Combinatorial Search | 4 / 6 | Python, Linux CI |
| Qwen2.5-0.5B Q4_K_M | 3 / 6 | llama.cpp, Linux CI |
| DeepSeek-R1-Distill-Qwen-1.5B Q4_K_M | 3 / 6 | llama.cpp, macOS ARM64 |
| Kimi-VL-A3B-Instruct Q3_K_S (Text Input) | 5 / 6 | llama.cpp, Linux Runner |
| **EmbeddingGemma-300M (Bijective Assignment)** | **6 / 6 (100%)** | **ONNX Runtime, CPU** |

* **Layout Geometry:** Tested across 7 responsive screen viewports in headless Chromium (including 839px and 840px breakpoint boundaries).
* **Color Contrast:** Independent C++20 tool evaluated UI palette: minimum contrast ratio reached **9.03**, exceeding the WCAG AA threshold of 4.5. [GitHub Actions Run](https://github.com/GlebAvershin/lantern-atlas/actions/runs/44798032011) · [Geometry](evidence/hud/geometry.json) · [Contrast](evidence/hud/contrast.json)

---

## 🛡️ High-Availability AI Gateway: Circuit Breaker & Semantic Caching

To scale AI agent workloads with zero downtime and minimal API costs, a distributed gateway was built at `studio/agents/live_platform_gateway.py`. The gateway routes level-verification requests between cloud Model Serving and local fallback models, backed by a Circuit Breaker state machine and an in-memory semantic deduplication cache.

### 1. Architecture & Cascading Failure Protection

* **Circuit Breaker State Machine:** Monitors a sliding error window. When 3 consecutive timeouts (>30s) or inference errors occur, the breaker transitions from `CLOSED` to `OPEN`, immediately short-circuiting downstream calls and serving verified deterministic fallback responses without blocking client threads. After 5 seconds, the breaker enters `HALF_OPEN` for canary health probes.
* **Semantic Caching:** Hashes normalized prompts and model parameters via SHA-256. Duplicate requests from agent tools return in **0.05 ms** with **zero token consumption**.

---

### 2. 50-Request Benchmark & FinOps Token Accounting

The benchmark scenario `studio/agents/gateway_benchmark.py` ran 50 level-verification requests through the active endpoint `databricks-qwen3-next-80b-a3b-instruct` on Databricks Model Serving:

| Gateway Metric | Measured Benchmark Value | Infrastructure Benefit |
| :--- | :---: | :---: |
| Total Request Volume | 50 requests | High-concurrency agent load |
| **Cache Hit Rate** | **96.0% (48 / 50)** | Massive external API offloading |
| Cold p95 Latency (Cloud Inference) | **6,759.29 ms** | Full 80B model generation over network |
| **Cache p95 Latency (Warm Cache)** | **0.05 ms** | Sub-millisecond instantaneous response |
| Actual Billed Tokens | 2,158 tokens | Only cold queries incur provider fees |
| **Tokens Saved via Deduplication** | **51,792 tokens (96.0%)** | **Direct FinOps Budget Optimization** |
| Circuit Breaker Final State | `CLOSED` (Healthy) | Automatic fault recovery verified |

[Gateway Code](../studio/agents/live_platform_gateway.py) · [Unit Tests](../studio/agents/test_live_platform_gateway.py) · [Benchmark Script](../studio/agents/gateway_benchmark.py) · [Measurements](evidence/platform-gateway-benchmark.json)

---

### 3. Semantic RAG Assistant (Vector Indexing & Technical Retrieval)

To eliminate LLM hallucinations on technical specs, the RAG module `studio/agents/semantic_rag.py` vector-indexes engineering docs, MCP schemas, and C++ contracts using cosine similarity search, generating verified responses with 100% source attribution:

* **Retrieval Quality:** Tested across complex queries (K8s pod failover, minimal oracle moves, and Nightwatch checkpoint bug reproduction), achieving **100% source retrieval precision** (`docs/TECHNOLOGIES.md`, `docs/NIGHTWATCH.md`). [RAG Code](../studio/agents/semantic_rag.py) · [Evaluation Receipt](evidence/semantic-rag-eval.json)
