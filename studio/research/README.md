# Game decision studies

Each game supplies a source adapter (`study.py`), an aggregate query (`metrics.sql`), and a second representation of the model inputs (`features.py`). Run from the Lantern Atlas checkout with Python 3.10 or newer. The Mosaic Pier study also uses a C++17 compiler.

```sh
python3 studio/research/run.py "../Mosaic Pier"
```

The default command reads versioned game data, runs the query in SQLite and prints the decisions. For Mosaic Pier it first compiles the native hint agent and plays every seed at every budget. To compare with a saved run, check the input hashes, query hash, metrics and rule for each case. Git revision identifies the base checkout. Source hashes pin the files used in the experiment.

## Hosted replay

Install the pinned dependencies from [the HUD toolkit](../hud/requirements.txt) in a virtual environment. Configure an active free AWS account with temporary SDK credentials, set `AWS_DEFAULT_REGION=eu-north-1`, and authenticate the Databricks CLI to a Free Edition workspace. Select its existing starter warehouse through `DATABRICKS_CONFIG_PROFILE` and `DATABRICKS_WAREHOUSE_ID`. Supply the QA project's `SENTRY_DSN` and `AMPLITUDE_API_KEY` through your environment.

```sh
python studio/research/run.py "../Mosaic Pier" --hosted > research-new.json
```

The SQL Statement Execution API receives one read-only inline query. The client compares every returned metric with SQLite before requesting model decisions from Bedrock Mantle. Amplitude receives one `game.study_evaluated` event per case. Sentry receives an expected warning for the designated negative control or a disagreement with the rule. Each event belongs to developer QA. Stable insert IDs include the service, game, revision, SQL digest and scenario. For an EU Amplitude project pass `--amplitude-region eu`. [SQL Statement Execution](https://docs.databricks.com/aws/en/dev-tools/sql-execution-tutorial)

## Paired prompt evaluation

```sh
python studio/research/paired.py "../Mosaic Pier" > research-paired-new.json
```

The paired command reads the game's published `docs/evidence/research.json`. It repeats each decision with the same Bedrock model and temperature, exposes normalized measurements and asks for a single action identifier. It records both exact-match and first-line accuracy to distinguish formatting problems from a wrong recommendation. The expected action is withheld from both prompts. A hard-coded rule makes the final decision. The paired cases measure behavior on these scenarios; a held-out gameplay board split is independent of the prompt evaluation.

## Verifying published evidence

From the Lantern Atlas repository, use a Python 3.12 environment with the [HUD dependencies](../hud/requirements.txt). Pass the path to one game checkout, or use `.` for Lantern Atlas.

```sh
python studio/research/verify_evidence.py "../Blackout Freight"
```

The command recalculates the study in SQLite, compares the results and input hashes with the saved Databricks query and Bedrock evaluations, and checks the recorded ingestion acknowledgements. For each saved Bedrock and Databricks HUD trace, it starts the game's MCP verifier and exercises all three accepted bindings and three rotated controls. This replay runs locally with the committed inputs.
