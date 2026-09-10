# End-to-end testing

Run from the repository root after README setup. Supply your own transcript,
register and guideline paths. Use a fresh result directory for each experiment.
The examples below use the separately supplied work-sample inputs.

## Historical baseline before Gemini migration

PR #13 merged the complete pipeline and services. At that milestone:

- 206 tests passed locally and in the Linux Docker image. The test client emitted
  two dependency deprecation warnings; there were no test failures.
- CI tests, actual Compose processing checks and CodeQL passed before merge.
- The full supplied-input Ollama pipeline passed in 60.469 seconds with CPU
  inference enforced. This is a local observation, not a fresh-machine benchmark.
- Offline replay passed locally and inside Linux Docker. All four HTTP services
  passed health, valid processing and invalid-input checks; stopping extraction
  left the other services healthy.
- The historical log recorded successful run
  `f6136a3b-042c-4e43-af21-1e068535d2d1`. Final samples are regenerated after migration.

Current Gemini generation and clean-checkout verification are recorded separately. See [evaluation](evaluation.md) for measurements and limitations,
and [acceptance checks](acceptance-checks.md) for the regression-test mapping.

## Windows session setup

Open PowerShell in the repository root. If the virtual environment already exists,
use its interpreter directly; activation is optional:

```powershell
$python = Join-Path (Get-Location) '.venv/Scripts/python.exe'
& $python scribe --version
```

For a new machine, complete the README setup first and transfer the supplied inputs
separately. Keep `outputs/` as the committed reference artifacts; write experiments
under `results/`. The commands below use an activated environment's `python`; you
can replace `python` with `& $python` in PowerShell.

## Local environment

The local `.env` contains SCRIBE_PROVIDER, GEMINI_MODEL, GEMINI_API_KEY,
GEMINI_TIMEOUT_SECONDS, SCRIBE_OFFLINE and SCRIBE_SERVICE. Git ignores it and the
Docker build excludes it. `.env.example` documents the names with a blank key.
Compose reads `.env` automatically; the CLI reads exported environment variables.

For individual CLI commands, import the simple KEY=value file into PowerShell:

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^(SCRIBE_PROVIDER|GEMINI_MODEL|GEMINI_API_KEY|GEMINI_TIMEOUT_SECONDS|SCRIBE_OFFLINE|SCRIBE_SERVICE)=(.*)$') {
        Set-Item -LiteralPath "Env:$($Matches[1])" -Value $Matches[2]
    }
}
python scribe check
```

## Start with offline replay

On Windows:

```powershell
python scribe check --offline
python scribe pipeline --offline --transcript instructions-data/transcript_01.txt --register instructions-data/register.csv --source instructions-data/guideline.txt --out results/first-run
if ($LASTEXITCODE -ne 0) { throw 'Pipeline failed; inspect stderr and run_log.jsonl.' }
```

On Linux, replace `python scribe` with `./scribe`. A successful run exits zero and
writes `note.json`, `resolved.json`, `knowledge.json` and `run_log.jsonl`.
Successful CLI commands leave stdout empty. Inspect all four log records for the
latest `run_id`; each must say `ok`. Validate a note independently with:

```sh
python scribe validate --transcript instructions-data/transcript_01.txt --note results/first-run/note.json
```

Inspect the latest audit run in PowerShell:

```powershell
$records = @(Get-Content results/first-run/run_log.jsonl | ForEach-Object { $_ | ConvertFrom-Json })
$latestRun = $records[-1].run_id
$latest = @($records | Where-Object { $_.run_id -eq $latestRun })
$latest | Select-Object stage, status, mode, model, message | Format-Table -AutoSize
if ($latest.Count -ne 4 -or @($latest | Where-Object { $_.status -ne 'ok' }).Count -gt 0) {
    throw 'The latest run did not complete all four stages.'
}
```

The supplied-input offline run should show `mode: replay`; a supported different
transcript should show `mode: rules`. Live extraction should show `mode: model`
with a provider/model identifier and prompt hash. Only extraction has model metadata.

For an independent consultation, use a new directory:

```sh
python scribe pipeline --offline --transcript src/tests/fixtures/alternate_consultation.txt --register instructions-data/register.csv --source instructions-data/guideline.txt --out results/alternate-run
```

Check nurse attribution, retained rejected reasoning, and unresolved concepts as
well as exit status. A successful validation result does not prove that extraction
captured every clinically relevant fact.

Replay is selected by transcript content, not its path. For a new consultation,
offline extraction uses bounded rules or fails clearly. The committed sample is
never returned merely because timestamps or filenames look familiar.

## Run the model path

Export `GEMINI_API_KEY` in your shell; optionally set `GEMINI_MODEL`. Never place
an actual key in a command example or tracked file. Gemini is the sole live provider.

```sh
python scribe check
python scribe pipeline --provider gemini --transcript instructions-data/transcript_01.txt --register instructions-data/register.csv --source instructions-data/guideline.txt --out results/gemini-run
```

Repeat with `src/tests/fixtures/alternate_consultation.txt` and
`src/tests/fixtures/submission_consultation.txt`, using a fresh output directory for
each. Inspect clinical facts, conflicts, rejection markers and codes separately
from exit status. A provider failure never switches to offline mode automatically.

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

To inspect current service status and send a real source-only request:

```powershell
docker compose ps
Invoke-RestMethod http://127.0.0.1:8003/health
$sourceText = [System.IO.File]::ReadAllText((Join-Path (Get-Location) 'instructions-data/guideline.txt'))
$requestBody = @{ source = $sourceText } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8004/process -ContentType 'application/json' -Body $requestBody -ErrorAction Stop
```

The CLI pipeline runs in-process and does not require Compose. Conversely, starting
Compose does not change the CLI's provider selection. Docker Compose can read a
local `.env` for interpolation; the Python CLI does not load it automatically.

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

To switch Compose to Gemini, export `GEMINI_API_KEY`, set `SCRIBE_OFFLINE=false`
and run `docker compose up -d extract`. Only extraction receives the key. Other
services need no provider credentials. `docker compose up -d --no-deps resolve`
starts resolution independently. Stop the stack with `docker compose down` when finished.

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

For a manual numeric mutation, preserve the original note and change only a copy:

```powershell
$changedNote = Get-Content results/first-run/note.json -Raw | ConvertFrom-Json
$dose = $changedNote.plan | Where-Object { $_.value -match '20 milligrams' } | Select-Object -First 1
if ($null -eq $dose) { throw 'Expected sample dose was not found; inspect the note first.' }
$dose.value = $dose.value.Replace('20 milligrams', '40 milligrams')
$changedNote | ConvertTo-Json -Depth 40 | Set-Content results/first-run/tampered-note.json -Encoding utf8
python scribe validate --transcript instructions-data/transcript_01.txt --note results/first-run/tampered-note.json
if ($LASTEXITCODE -eq 0) { throw 'Unexpected acceptance of a changed dose.' }
```

Expected: nonzero exit with a validation error; the unchanged note must still pass.
The automated pipeline tests exercise missing register columns, duplicate codes
across kinds, empty files and malformed rows. Run those four cases directly with:

```sh
pytest -q src/tests/test_pipeline.py -k all_broken_registers
```

To reproduce a missing-key failure without contacting the provider, temporarily
remove the environment variable for one run and restore it afterwards:

```powershell
$previousKey = $env:GEMINI_API_KEY
try {
    Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue
    python scribe pipeline --provider gemini --transcript instructions-data/transcript_01.txt --register instructions-data/register.csv --source instructions-data/guideline.txt --out results/provider-failure
    if ($LASTEXITCODE -eq 0) { throw 'Unexpected provider success.' }
} finally {
    $env:GEMINI_API_KEY = $previousKey
}
```

Expected: extraction failed, the other three stages skipped, and no successful
output hash for any stage. An unavailable audit directory fails before a run can
be logged; no fallback log location is used.

Outputs are replaced atomically only after their stage succeeds. Failed runs do
not erase previous successful artifacts; existing downstream files may therefore
belong to an older run. Never interpret file existence as a successful current
run. Use a fresh directory, the process exit code and the latest four audit records.
Concurrent runs must use separate directories.
