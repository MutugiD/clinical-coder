# End-to-end testing

Run from the repository root after README setup. Supply your own transcript,
register and guideline paths. Use a fresh result directory for each experiment.
The examples below use the separately supplied work-sample inputs.

## Start with offline replay

On Windows:

```powershell
python scribe check --offline
python scribe pipeline --offline --transcript instructions-data/transcript_01.txt --register instructions-data/register.csv --source instructions-data/guideline.txt --out results/first-run
```

On Linux, replace `python scribe` with `./scribe`. A successful run exits zero and
writes `note.json`, `resolved.json`, `knowledge.json` and `run_log.jsonl`.
Successful CLI commands leave stdout empty. Inspect all four log records for the
latest `run_id`; each must say `ok`. Validate a note independently with:

```sh
python scribe validate --transcript instructions-data/transcript_01.txt --note results/first-run/note.json
```

Replay is selected by transcript content, not its path. For a new consultation,
offline extraction uses bounded rules or fails clearly. The committed sample is
never returned merely because timestamps or filenames look familiar.

## Run the model path

With Ollama running and the configured model installed:

```sh
python scribe check --provider ollama
python scribe pipeline --provider ollama --transcript instructions-data/transcript_01.txt --register instructions-data/register.csv --source instructions-data/guideline.txt --out results/ollama-run
```

For the hosted path, export `GEMINI_API_KEY`, optionally set `GEMINI_MODEL`, and
replace `--provider ollama` with `--provider gemini`. No failure automatically
switches providers. The local Ollama full-pipeline run has been verified; direct
Gemini generation remains unverified live without a key. Controlled failure tests
do not establish hosted generation accuracy.

## Exercise services

For a credential-free Compose run, set offline mode explicitly. PowerShell:

```powershell
$env:SCRIBE_OFFLINE = 'true'
docker compose up -d --build --wait
python src/tests/compose_smoke.py
```

On a POSIX shell, use `export SCRIBE_OFFLINE=true` before those same commands.
Ports bound to localhost are 8001 extraction, 8002 validation, 8003 resolution and
8004 knowledge. Each exposes `GET /health` and `POST /process`. The smoke script
exercises the full sequence through real HTTP requests and checks invalid-input
rejection. Its alternate transcript runs through local rules in offline mode.

The request bodies are:

| Service | JSON body |
| --- | --- |
| Extract | `{"transcript":"timestamped speaker text"}` |
| Validate | `{"transcript":"timestamped speaker text","note":{...}}` |
| Resolve | `{"note":{...},"register":"CSV content"}` |
| Knowledge | `{"source":"guideline content","note":{...}}` with optional note |

Send content, not local file paths. HTTP 422 reports invalid input; 503 reports
provider/configuration unavailability; 500 reports an invalid boundary output or
unexpected implementation failure. Health reports liveness, not model readiness.
Use `scribe check` for extraction dependency checks.

To switch Compose to Ollama, set `SCRIBE_OFFLINE=false` and run `docker compose up
-d extract`. The container defaults to `http://host.docker.internal:11434`; override
`OLLAMA_BASE_URL` for a different reachable endpoint. Other services need no
provider credentials. `docker compose up -d --no-deps resolve` starts resolution
independently. Stop the stack with `docker compose down` when finished.

## Check failure behavior

Run the focused tests, then the full suite:

```sh
pytest -q src/tests/test_pipeline.py src/tests/test_services.py src/tests/test_review_acceptance.py
pytest -q
```

These cover all four broken registers, changed numeric facts, contradictory
medication statements, unavailable providers, bad citations, invalid service
outputs and source-only knowledge with no note present. A broken register produces
`extract: ok`, `validate: ok`, `resolve: failed`, `knowledge: skipped` when extraction
succeeds. The error names the register file and row when available.

Outputs are replaced atomically only after their stage succeeds. Failed runs do
not erase previous successful artifacts; existing downstream files may therefore
belong to an older run. Never interpret file existence as a successful current
run. Use a fresh directory, the process exit code and the latest four audit records.
Concurrent runs must use separate directories.
