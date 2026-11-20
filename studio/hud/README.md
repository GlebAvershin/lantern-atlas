# Responsive HUD handoff

A designer supplies three region descriptions, a catalogue of components bound to source symbols and a separate acceptance key. The local MCP server scopes each session to one game. The author reads the design resource, asks an inference route for a binding, then calls the verifier. Rejected choices leave the candidate set. The trace records a remaining singleton as elimination and charges it zero inference tokens. The renderer supplies the responsive geometry, typography and existing game art. The result is a design proof with a disabled sample action.

## Reproduce the handoff

Open **Actions → Responsive HUD handoff → Run workflow** in any of the four game repositories. The Ubuntu job starts a checksum-verified llama.cpp and Qwen2.5-0.5B Q4_K_M, resolves real source bindings over MCP, renders the result and measures it in Chromium. The job produces the download **hud-proof**.

| File | What it measures |
| --- | --- |
| authoring.json | Choices, rejections, forced completions, inference tokens and time from the first region to the last MCP verification |
| geometry.json | Seven viewports, including either side of the 840 px breakpoint and short landscape. An injected 18 px action must fail the touch-target check |
| contrast.json | Four solid foreground/background pairs from computed Chromium styles, independently checked by C++20 against a project minimum of 4.5 and a deliberately low-contrast control |
| qwen.json | Blind first choices on two additional briefs, compared with a maximum-overlap one-to-one text matcher. The model gets all three candidates for each instruction without verifier feedback |
| screen.html, screen.jpg | Standalone HTML handoff and its 840 × 600 Chromium capture |
| desk-probe.json | Five concurrent HTTP reads and rejection checks against the Django proof viewer |
| review-app.tgz | The generated proof alongside its read-only Django app and Databricks Apps manifest |

For local authoring, use Python 3.12 in a virtual environment and install the dependencies in this directory. The commands below assume the platform checkout is the current directory and the game is at `$GAME`. Start llama-server with the Qwen file and alias from the CI script on loopback port 18490, then run these commands. [CI commands and checksums](run-ci.sh)

```sh
python -m pip install -r studio/hud/requirements.txt
python -m playwright install chromium
python studio/hud/check_routes.py
python studio/hud/author.py "$GAME" /tmp/hud-proof --model qwen
python studio/hud/measure.py "$GAME" /tmp/hud-proof
python studio/hud/compare.py "$GAME" /tmp/qwen.json --model qwen \
  --weights-sha256 74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db
```

A second benchmark uses the local alias `DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M`. Use llama.cpp b12578 with `--reasoning-budget 0`, that alias, its GGUF file and a spare loopback port. Set `HUD_LLAMA_PORT` when running compare.py. With the default thinking budget the first 64-token trial ended with no structured answer. The zero budget preserves the same 64-token cap for the returned JSON. The Q4_K_M file has SHA-256 `1741e5b2d062b07acf048bf0d2c514dadf2a48f94e2b4aa0cfe069af3838ee2f`. [Weights](https://huggingface.co/bartowski/DeepSeek-R1-Distill-Qwen-1.5B-GGUF)

## Inspect a completed job

Extract review-app.tgz into a new folder, run `python -m pip install -r requirements.txt` there, then `python desk.py`. The preview opens at localhost port 8000. The /metrics endpoint reports the commit, token usage, wall time, viewport count and rejected choices. The package holds public design output only. A Node.js Actions step compares tokens and calls with the published baseline when the route, model and brief match. Service-side milliseconds include scheduling and model work. A paired session with independent developers is needed to measure changes in human task time. [Viewer](desk/desk.py) · [Probe](probe.go) · [CI summary](summary.mjs)

The archive includes app.yaml for Databricks Apps, using the runtime port and an explicit bind address. The same Python entry point runs on the CI worker. Workspace deployment requires access to a Databricks workspace. [Databricks Apps environment](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/system-env)

## Provider and release context

The default job uses local open weights. With an independently provisioned endpoint, author.py also accepts `--route bedrock --model MODEL_ID` via the AWS SDK credential chain, or `--route databricks --model ENDPOINT_NAME` with DATABRICKS_HOST and DATABRICKS_TOKEN. The latter targets a workspace serving endpoint. Gateway policies, billing and permissions belong to that workspace. Provider contracts run offline with Botocore Stubber and HTTPX MockTransport. [Routes](routes.py) · [Tests](check_routes.py)

A separate stdio MCP server offers three fixed, read-only release resources. Its operator binds the process to one game. GitHub reads the selected public Actions run with STUDIO_PROJECT and HUD_RUN_ID. The Sentry reader requires SENTRY_ORG, SENTRY_PROJECT_ID and SENTRY_READ_TOKEN and returns level counts for one page of up to 20 issues. The Amplitude reader uses AMPLITUDE_API_KEY and AMPLITUDE_SECRET_KEY for the selected game and aggregates one event over the previous UTC date. External credentials belong in the process environment. The evidence records which responses came from a hosted service and which came from an offline fixture. [Server](../agents/signal_context.py) · [MCP read and contract checks](../agents/check_signals.py) · [Sentry issues](https://docs.sentry.io/api/events/) · [Amplitude Dashboard API](https://amplitude.com/docs/apis/analytics/dashboard-rest)

## Route for a known catalogue

The alternative author uses the existing quantized CPU EmbeddingGemma matcher. It maximizes the sum of similarities over all six distinct assignments. Cached component embeddings are reused within the process. Run the command below with the model snapshot described in the [original matcher experiment](../../HUD-experiment.md). It scores the two extra briefs blind and checks the canonical handoff over MCP before writing the HTML. See [the agent skill](../../.agents/skills/responsive-hud/SKILL.md).

```sh
uv run --script studio/hud/match.py "$GAME" /tmp/matcher.json \
  --snapshot "$EMBEDDING_SNAPSHOT" --screen /tmp/matched-screen.html
```
