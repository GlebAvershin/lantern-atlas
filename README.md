# Lantern Atlas · Nightwatch

**[Play in the browser](https://glebavershin.github.io/lantern-atlas/)** · [16-second gameplay clip](evidence/nightwatch.mp4) · [Engineering case study (RU)](docs/NIGHTWATCH.md)

A model-proposed chart became the playable finale. An independent C++17 solver verified its six-move minimum. During review a model flagged a missing checkpoint, then a failing Godot test reproduced the problem. The Python tools also run on two Kubernetes replicas with shared PostgreSQL caching. [Game technology and AI evidence](docs/TECHNOLOGIES.md) · [Live model interruption test](https://github.com/GlebAvershin/lantern-atlas/actions/runs/44774475646) · [First-player session](docs/FIRST-PLAYER.md)

![Crescent Passage. Two shuttered stations receive light, and a pair of marked relays connect opposite sides of the chart.](evidence/nightwatch.png)

Light a chain of coastal beacons before the fleet comes home. Each pulse toggles a station and its orthogonal neighbours. Diamond-shaped relays also toggle their distant partner. Barred stations can receive light only from other stations. Eight charts introduce the rules on 3×3 and 4×4 boards, with shortest solutions from one to six moves.

Click or tap a lantern. Hover to preview the affected stations. Tab to the board and use the arrow keys and Space or Enter to operate it from the keyboard. H reveals the first step of a shortest route from the current position. Z undoes the last move. The voyage log saves your current chart, move history, personal bests and settings. Sound and reduced motion are available in Settings.

## How the release was built

| Part | Engineering decision | Evidence |
| --- | --- | --- |
| Game logic | Represent each pulse as a bit mask. Join two half-board lookup tables to find a minimum move set from any reachable position. A separate C++17 program enumerates legal press sets to verify the shipped levels. | [Runtime solver](game/chart.gd) · [Oracle](studio/oracle.cpp) |
| Level authoring | Qwen and SmolLM2 received a bounded design brief through Python tooling. Each selected a relay pair and scramble from the catalogue and supplied a title. An MCP tool validated each candidate against the same minimum length and relay condition. The Qwen proposal became the last playable chart. | [MCP server](studio/chart_mcp.py) · [Both records and negative control](evidence/nightwatch-authoring.json) |
| UI tooling | The actual release wireframe was run through a FastAPI model gateway and independently through EmbeddingGemma. Both agreed on the order rendered by the game. Ten simultaneous clients shared a generation. | [Release wireframe](studio/briefs/hud.txt) · [Local request timings](evidence/nightwatch-hud.json) · [Matcher output](evidence/nightwatch-matcher.json) |
| Review and support | A read-only GitHub MCP resource supplied PR context to a model. A missing move-history checkpoint was reproduced in Godot, fixed and covered by a reopen-and-undo regression. Sentry and Amplitude SDKs were exercised with a local receiver on recorded development events. | [Review](evidence/nightwatch-review.json) · [Regression](studio/check_game.gd) · [SDK evidence](evidence/nightwatch-telemetry.json) |
| Cloud execution | A standard GitHub-hosted Linux runner started two CPU inference servers and the gateway, checked the level candidates and exercised the cache. The runner stops after the job. Browser gameplay is hosted separately on GitHub Pages. | [Workflow](.github/workflows/nightwatch.yml) · [Measured run](https://github.com/GlebAvershin/lantern-atlas/actions/runs/44767485555) |

## More game engineering work

| Project | What to inspect |
| --- | --- |
| Blackout Freight | A first-shift compass shipped to a Roblox closed test. Follow an accepted battery delivery from the client HUD to the server-side experiment and its QA events. [Gameplay and release evidence](https://github.com/GlebAvershin/blackout-freight/blob/main/docs/portfolio-release-2026-11-16.md) |
| Soccerpoly | A bilingual cup event ships from a validated catalogue. See how a later design tool handles a model-proposed payout that passes the economy rules but misses the designer’s target. [Shipped event](https://github.com/GlebAvershin/Soccerpoly/blob/main/docs/RELEASE.md) · [Designer workflow](https://github.com/GlebAvershin/Soccerpoly/blob/main/docs/CUP-TRIAL.md) |

## Reproduce the game checks

From this repository, using Godot 4.5.1, Python 3 and a C++17 compiler, run:

```sh
c++ -std=c++17 -O2 studio/oracle.cpp -o /tmp/lantern-oracle
ATLAS_ORACLE=/tmp/lantern-oracle python3 studio/check_catalog.py
godot --headless --path game --import
godot --headless --path game --script "$PWD/studio/check_game.gd"
godot --path game
```

The scene test uses a disposable save slot. The macOS and single-threaded Web export presets live in the project. Install the corresponding Godot 4.5.1 template to build either target. [Official downloads](https://godotengine.org/download/archive/4.5.1-stable/)

For model reproduction, follow the two endpoint commands in the original experiment, compile the oracle above and run the following from the repository root. The hosted workflow uses verified hashes for both model files and the inference binary. [Inference setup and earlier measurements](HUD-experiment.md)

```sh
export HUD_QWEN_URL=http://127.0.0.1:18081 HUD_SMOL_URL=http://127.0.0.1:18082
export ATLAS_ORACLE=/tmp/lantern-oracle
uv sync --project studio --locked --python 3.12
studio/.venv/bin/python studio/author.py --output /tmp/nightwatch-candidates.json
```

The gameplay clip is a scripted capture of the real game scene. The illustration was made for this release with ImageGen. The chimes are synthesized from source. [Capture script](studio/capture.gd) · [Art prompt](docs/art-prompt.txt) · [Sound source](studio/chimes.py) · [Cormorant Garamond license](game/art/OFL.txt)
