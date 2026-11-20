# Lantern Atlas

A five-chart logic puzzle built in Godot 4.5.1. Tap a star to toggle it and its four orthogonal neighbours. Light all nine stars to advance. The charts have shortest solutions of one through five moves. Every move can be undone. The game runs offline.

[Mac build](Lantern%20Atlas.zip) · [Source project](game/project.godot) · [Gameplay screenshot](evidence/game.png)

## Play

Unzip the Mac build and open **Lantern Atlas**. Alternatively, import the project into Godot 4.5.1 and press F6 with `atlas.tscn` open, or F5 from the project. Click the stars or use keys 1–9 from the top-left. Z undoes a move. The keyboard and mouse paths share the same board state. The build is ad-hoc signed for a local macOS demo.

## Where AI enters the game

The authoring brief is a three-line text wireframe. One Python service reads a project-specific component catalogue through MCP, asks a selected language model to map the brief to component IDs, and calls an MCP tool to check its output. The author reviews the order before copying it into the game. Godot renders the actual controls, so play never waits for inference. The accepted Qwen response for the first Atlas case supplies the order in the game. Two additional catalogues represent the compass HUD in Blackout Freight and the club card in Soccerpoly. Their layouts are evaluation fixtures. [Accepted response](evidence/layout-eval.json) · [Game layout](game/hud.json) · [MCP contracts](studio/contracts.py) · [Gateway](studio/service.py)

## What the experiment found

Each brief has a reference ordering. A correct answer needs every component exactly once, in the designer's intended order. The first six cases span three project contexts and include changes to the default layout. A fixed project default already solves three. Models ran on an Apple M4 with llama.cpp build 12578, two slots per endpoint, temperature zero, seed 42, an 80-token output cap and constrained JSON.

| Strategy | Cases | Qwen2.5-0.5B-Instruct, Q4_K_M | SmolLM2-360M-Instruct, Q8_0 | Fixed-order baseline |
| --- | ---: | ---: | ---: | ---: |
| One call for the wireframe | 6 | 1 exact, 6 structurally valid | 0 exact, 4 valid | 3 exact |
| Classify each row separately, same six cases | 6 | 2 exact, 2 valid | 0 exact, 0 valid | 3 exact |
| Per-row strategy on three additional paraphrases | 3 | 0 exact, 0 valid | 0 exact, 0 valid | 0 exact |

The whole-wireframe prompt returned plausible permutations with the wrong order. Classifying rows independently prevented some order reversals but often selected one widget twice. The MCP check caught those duplicates. Both experiments keep generated layouts in author review. Production evaluation would need independent designers, unseen screens, actual device renders and time-to-accepted-layout. [First experiment](evidence/layout-eval.json) · [Per-row experiment](evidence/row-eval.json)

The best result came from treating the task as component matching. A third model, EmbeddingGemma-300M, embeds each instruction and each component description. The tool scores all six possible one-to-one assignments and selects the highest total cosine similarity. It reuses component embeddings and calls the same MCP validator. It matched **12 of 12** gold orderings across the original six, the three paraphrases and three additional briefs. The fixed-order baseline matched **3 of 12**. These are author-written fixtures from a three-widget domain. Performance on unseen team designs and screenshots remains an open question. The matcher is a standalone authoring tool. The latency benchmark below covers the generative HTTP gateway. [Matcher](studio/retrieve.py) · [Raw comparisons](evidence/retrieval-eval.json)

For the service test, three simulated project clients each sent eight simultaneous copies of their own labelled wireframe. The models were already loaded and these specific drafts were absent from the gateway cache. The first batch used three whole-wireframe generations and 341 reported input-plus-output tokens. Twenty-one requests joined work in progress. All 24 repeated requests hit the cache and used zero additional model tokens. Client-side p95 was **676.32 ms** for the first batch and **42.56 ms** for the repeated batch. These are individual localhost runs on one machine. They establish request coalescing and cache behaviour. They do not estimate cloud latency, dollars saved or developer productivity. [Per-request records](evidence/layout-eval.json)

## Reproduce

The game can be checked independently of the model service. From this directory run:

```sh
godot --headless --path game --script "$PWD/studio/check_game.gd"
```

The check explores all 512 board states, verifies each shortest solution, simulates star taps, and exercises undo, restart, advance and replay. To export locally, install the official Mac export template and use the included macOS preset. [Godot 4.5.1 downloads](https://godotengine.org/download/archive/4.5.1-stable/)

For inference, obtain the two GGUF files from their publishers. In separate terminals start each server from llama.cpp. Substitute the paths of the downloaded files below. [Qwen weights](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF) · [SmolLM2 weights](https://huggingface.co/HuggingFaceTB/SmolLM2-360M-Instruct-GGUF) · [llama.cpp build](https://github.com/ggml-org/llama.cpp/releases/tag/b12578)

```sh
llama-server -m /path/to/qwen2.5-0.5b-instruct-q4_k_m.gguf --alias qwen --host 127.0.0.1 --port 18081 -c 4096 -np 2
llama-server -m /path/to/smollm2-360m-instruct-q8_0.gguf --alias smol --host 127.0.0.1 --port 18082 -c 4096 -np 2
```

From `studio/` start one gateway worker. The example credentials are for a loopback test.

```sh
export HUD_TOKENS='{"local-atlas":"atlas","local-soccer":"soccer","local-freight":"freight"}'
export HUD_QWEN_URL=http://127.0.0.1:18081 HUD_SMOL_URL=http://127.0.0.1:18082
export HUD_STRATEGY=whole
uv sync --locked --python 3.12
uv run --locked uvicorn service:app --host 127.0.0.1 --port 18083
```

Use a second terminal with the same `HUD_TOKENS` and run `uv run --locked python evaluate.py --output /tmp/atlas-whole.json` from `studio/`. Restart the gateway with `HUD_STRATEGY=per_row` and repeat with `--transfer --output /tmp/atlas-rows.json` to measure the alternative on the original six and three additional cases. Use new output filenames and a freshly started gateway for each benchmark. [Evaluation cases and scoring](studio/evaluate.py)

To run the matching alternative, supply an unpacked EmbeddingGemma snapshot containing `tokenizer.json`, `onnx/model_quantized.onnx` and its neighbouring `.onnx_data` file as regular files. From `studio/` run `uv run --script retrieve.py --snapshot /path/to/snapshot --output /tmp/atlas-matching.json`. For a new design, replace `--output …` with `--project atlas --brief three-lines.txt`. The model weights are distributed separately. [Model snapshot](https://huggingface.co/onnx-community/embeddinggemma-300m-ONNX/tree/5090578d9565bb06545b4552f76e6bc2c93e4a66)

For a container, build from `studio/` with `docker build -t lantern-atlas-hud .`. Supply the same token map and endpoint variables at runtime. Each endpoint must be reachable from the container. The HTTP gateway listens on port 8000. The build contains the Python service and its MCP subprocess. The weights run on the two separate inference endpoints. In a Docker Desktop smoke run the same text sent under Atlas and Freight credentials yielded two different component sets, each with its own miss and subsequent hit. A request without credentials returned HTTP 401.

## Where scale changes the design

The operator assigns bearer credentials to project catalogues. The cache key includes project, model route, prompt, strategy, catalogue and input. An in-memory LRU retains up to 128 accepted drafts per process. Concurrent duplicates wait for the same job. At most 16 distinct jobs can be pending and four provider requests can run simultaneously. A model upgrade behind the same endpoint alias requires restarting the process to clear cached outputs.

A multi-replica cloud deployment needs a shared result and job store, scoped permissions, quotas and request tracing across workers. Cost per accepted layout must include rejected drafts. The two local models produced no cloud invoices. The benchmark includes no external team trial or measured authoring time savings.
