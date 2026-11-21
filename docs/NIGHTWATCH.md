# Nightwatch · Engineering Release Dossier

<p align="center">
  <a href="NIGHTWATCH.md"><b>English</b></a> •
  <a href="NIGHTWATCH.ru.md"><b>Русский</b></a>
</p>

The technical objective of this release was to transform a five-level puzzle prototype into a production-ready game feature while applying AI agents across the end-to-end release lifecycle. The resulting 8-chart campaign on Godot 4.5.1 is published both as a WebAssembly browser game and a native macOS application. On the final chart, players experience level geometry and UI layouts selected during automated model benchmarking runs. [Play Game](https://glebavershin.github.io/lantern-atlas/) · [Walkthrough Capture](../evidence/nightwatch.mp4)

---

## 🎮 What Changed for the Player

Previously, all five puzzle tasks adhered to uniform rules on a 3×3 grid. In Nightwatch:
* **Compound Relays:** Pairs of lighthouse stations transmit secondary light pulses across the archipelago.
* **Shuttered Stations:** Stations with sealed shutters respond to adjacent pulses and cannot be directly toggled by the player.
* **4×4 Strategic Grids:** Players must coordinate intersecting beams and remote connections across larger grids.
* **Calibrated Move Minimums:** Solutions for the 8 charts are mathematically proved at 1, 2, 3, 4, 4, 5, 6, and 6 moves.
* **State Persistence:** Turn history, par scores, and undo stacks persist reliably between sessions. [Campaign Dataset](../game/voyage.json)

Visual hints dynamically highlight reach zones upon hover. Activating a station triggers radial light propagation with distance-based delays. Relays are denoted by diamond nodes and dashed lines; shuttered stations feature vertical security bars. Configurable accessibility toggles support disabling audio chimes and reducing motion tweens. [Sky Rendering](../game/sky.gd) · [Atlas UI](../game/atlas.gd) · [Artwork](../game/art/northwatch.jpg)

---

## 🤖 The AI & Developer Collaboration Pipeline

1. **Problem Definition & Invariants:** Briefs formalized grid bounds, disabled direct clicking on shuttered relays, minimal solution lengths, and mandatory relay nodes. The human engineer established search parameters and acceptance criteria. Codex implemented mechanics, UI components, tests, and build configurations. A custom Python client queried MCP resources, passed briefs to candidate models, and verified outputs. [Brief Schema](../studio/briefs/nightwatch.json) · [Orchestrator](../studio/author.py)
2. **Procedural Content Generation:** Qwen2.5-0.5B synthesized *Crescent Passage*, while SmolLM2-360M synthesized *The Coastal Route*. Both passed automated acceptance tests. The final level adopted Crescent Passage due to its challenging diagonal connection. A C++17 solver proved a strict minimal solution of 6 moves. Disabling clicks on either relay rendered the level unsolvable. Pre-selected negative controls requiring $\le 2$ moves were automatically rejected. [Authoring Trace](../evidence/nightwatch-authoring.json)
3. **UI Layout Matching:** Three lines of functional specification mapped to the journal, interactive chart, and control deck. Qwen and EmbeddingGemma (via bijective assignment) independently arrived at the identical layout order. Validated configurations were serialized into JSON for the Godot runtime. [Brief](../studio/briefs/hud.txt) · [Matching Trace](../evidence/nightwatch-matcher.json) · [HUD Data](../game/hud.json)
4. **Code Review & Regression Bug Fix:** A Python MCP server fetched checkpoint serialization logic from a specific PR commit. Qwen was provided with scoped code and resumption criteria. The model identified a state loss bug where the final move was omitted upon serialization. A regression test confirmed the defect. The fix persists full action sequences with rule versions, replaying valid moves on resume. [Review Context & Verdict](../evidence/nightwatch-review.json) · [Before Fix](../evidence/checkpoint-before.txt) · [After Fix](../evidence/checkpoint-after.txt)
5. **Release Observability:** Sentry SDK captured an envelope containing the true regression error trace; Amplitude SDK logged 2 event authoring events recording token consumption and validation outcomes. Receipts were made available to IDE agents via MCP. [Telemetry Evidence](../evidence/nightwatch-telemetry.json) · [SDK Code](../studio/telemetry.py)

---

## 🔬 Dual Independent Solvers

* **Godot Runtime Bitmask Solver:** Light pulses are represented as integer bitmasks. Valid moves are partitioned into two halves; for each half, the shortest combination of toggles is precomputed. The hint system queries the complement table, minimizing total moves in under 1 ms across 256 states per half. [Godot Solver](../game/chart.gd)
* **Independent C++17 Oracle:** Independently constructs coordinate bitmasks, traverses complete state spaces, prunes illegal actions, and validates levels without relays. CI cross-verifies results against level JSON files. An automated Godot test script completes all 8 charts through simulated input, verifying hints, saves, undo, and resets. [C++ Oracle](../studio/oracle.cpp) · [Test Script](../studio/check_game.gd)

---

## ☁️ Cloud Benchmarks & Token Costs

On a standard GitHub-hosted Linux runner, two llama.cpp endpoints were deployed alongside a FastAPI gateway and an MCP server:

| Test Condition | First Batch (10 Requests) | Repeated Batch (10 Requests) |
| :--- | :--- | :--- |
| **Local macOS ARM64** | 1 inference + 9 waiting, p95: 390.72 ms, 132 tokens | 10 cache hits, p95: 8.23 ms, 0 tokens |
| **Linux GitHub Runner** | 1 inference + 9 waiting, p95: 808.50 ms, 136 tokens | 10 cache hits, p95: 11.29 ms, 0 tokens |

The game is hosted on GitHub Pages; CI builds execute on standard public runners, incurring zero marginal server costs. [Cloud Run Log](https://github.com/GlebAvershin/lantern-atlas/actions/runs/44767485555) · [Local Traces](../evidence/nightwatch-hud.json)
