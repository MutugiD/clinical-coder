# Clinical coder

Clinical coder produces source-backed clinical notes from speaker-labelled English
and Swahili consultations. It preserves verbatim evidence and validates notes before
writing them. Deterministic register lookup adds codes, while guideline extraction
produces cited rules for clinical review.

[Requirements](docs/prd.md) · [Architecture](docs/architecture.md) ·
[Design decisions](docs/decisions.md) · [Testing](docs/testing-strategy.md) ·
[End-to-end guide](docs/end-to-end-testing.md) ·
[Issues](https://github.com/MutugiD/clinical-coder/issues)

## Setup

Use Python 3.12 and an installed, running Ollama server. From the repository checkout:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps --no-build-isolation -e .
ollama pull qwen3:1.7b
```

Then run `./scribe check`. If Ollama is stopped, start it with `ollama serve`.
On Windows, activate `.venv/Scripts/Activate.ps1` and use `python scribe`.

## Extract and validate

```sh
./scribe extract --transcript consultation.txt --out results/note.json
./scribe validate --transcript consultation.txt --note results/note.json
```

The note contains the 13 contract sections. Each element includes its value,
timestamped evidence, and confidence; assessment also carries certainty.
A section with no evidence contains `NOT_STATED`.

The default provider is local Ollama with `qwen3:1.7b`, CPU inference, and thinking
disabled. Provider selection is explicit; failures never silently switch providers.

```sh
./scribe check --provider gemini
./scribe extract --provider gemini --transcript consultation.txt --out results/note.json
./scribe extract --offline --transcript consultation.txt --out results/note.json
```

Gemini requires `GEMINI_API_KEY`. Offline execution uses verified committed output
for a matching transcript or conservative rules for a new input. Unsupported input
fails with an explanation. Every returned note is validated.

| Variable | Default |
| --- | --- |
| `SCRIBE_PROVIDER` | `ollama` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` |
| `OLLAMA_MODEL` | `qwen3:1.7b` |
| `OLLAMA_TIMEOUT_SECONDS` | `180` |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` |
| `GEMINI_API_KEY` | Required for Gemini |
| `GEMINI_TIMEOUT_SECONDS` | `180` |

`.env.example` documents settings. Export them in the shell; the application does
not load `.env` automatically. `--offline` cannot be combined with `--provider`.

## Resolve codes

```sh
./scribe resolve --note results/note.json --register register.csv --out results/resolved.json
```

Validate the note against its transcript before resolution. The resolver accepts
only the note and register, so it cannot establish source provenance itself. It
uses no model or network. A unique exact name or synonym within the allowed kind
resolves; near matches remain uncoded suggestions and competing exact matches are
ambiguous. Conflict, rejected, companion, family-history and negated elements stay
uncoded. Certainty and evidence remain unchanged. Resolution confidence describes
the lookup; the original confidence is retained as `extraction_confidence`.

For 12,000 conditions and 3,000 drugs, compile each versioned register into a
kind-partitioned alias index and token trie. Retrieve exact candidates first, then
bounded character-gram candidates for suggestions, using fixed thresholds and
stable code ordering. Version normalization and contextual aliases with the
register checksum; record selected aliases, alternatives and rule versions so each
decision can be reproduced. Review synonym changes against a frozen evaluation
set before releasing a new catalogue.

## Extract guideline knowledge

```sh
./scribe knowledge --source guideline.txt --out results/knowledge.json
./scribe knowledge --source guideline.txt --note results/note.json --out results/knowledge.json
```

The source alone determines drug-class rules, red flags, test constraints and
`not_in_corpus` gaps. Every row carries an exact quotation, source name, section
and page. The optional note affects only the review prose, which stays below 200
words. The committed example uses the supplied note for that prose.

The deterministic parser supports one citation block in the supplied format:
`SOURCE: Title, edition, Section X.Y, page N.`, followed by a matching section
heading and supported recommendation sentences. Missing metadata, additional
sections or unrecognised sentences fail explicitly. This is a bounded excerpt
parser, not a general guideline-document reader. It uses no model or network and
does not infer drug-class membership or replace clinical decisions.

## Verification

Run the complete pipeline from the repository root:

```sh
./scribe pipeline --offline --transcript consultation.txt --register register.csv --source guideline.txt --out results/run-1
```

Use `--provider ollama` or `--provider gemini` instead of `--offline` for live
extraction. The pipeline runs extract → validate → resolve → knowledge and writes
three JSON artifacts plus `run_log.jsonl`. A failure exits nonzero and logs later
stages as skipped. Reusing a directory preserves prior successful files on failure;
check the latest run's records or use a fresh directory for each test.

Four independent HTTP services are available through `docker compose up -d
--build --wait`. For a credential-free service test, set `SCRIBE_OFFLINE=true`
first, then run `python src/tests/compose_smoke.py`. Their localhost ports are
8001–8004 for extract, validate, resolve and knowledge. Each provides `/health`
and `/process`; health reports liveness rather than model readiness.

See the [end-to-end guide](docs/end-to-end-testing.md) for Windows commands,
request bodies, failure checks and model configuration. The
[acceptance checks](docs/acceptance-checks.md) map the brief and review cases to tests.

```sh
ruff check .
pytest -q
python -m compileall -q src
docker build -t clinical-scribe .
docker run --rm clinical-scribe --version
```

Tests and independent fixtures live in `src/tests`. Provider mocks are distinct
from live model measurements. Use read-only input and writable output volumes for
Docker extraction. Docker Desktop reaches host Ollama through
`OLLAMA_BASE_URL=http://host.docker.internal:11434`.

## Architecture

Extraction selects evidence; deterministic rendering constructs the note; validation
checks source fidelity and clinical scope. Resolution and guideline extraction use
separate contracts so their rules can evolve independently of the model. At higher
load, queue bounded model requests and scale deterministic stages separately.
Monitor latency, validation failures, unresolved rates, and provider availability
without patient text in metric labels. Version resolver rules and catalogue hashes
so a release does not silently recode historical notes. See the architecture document
for component responsibilities, data flows, and service contracts.

## Failure behavior

Exit `0` means success; `1` means processing or validation failure; `2` means invalid
arguments. Diagnostics go to stderr. Output is written only after a stage succeeds.
Unsupported language, scope, or transformations cause rejection rather than guessed
facts. Implementation coverage and defects are tracked in GitHub Issues.

## Where this would break

- **Unrecognised Sheng or indirect answers:** scope rules may not classify a relevant
  utterance. Offline extraction reports unsupported turns; broader bilingual
  evaluation is required before deployment.
- **Incorrect speaker labels:** a relative's account could be attributed to the
  patient. Validate attribution against the source; incorrectly labelled source
  audio still requires upstream review.
- **Ambiguous corrections and chronology:** a clinician may need to determine which
  statement is current. Preserve detected conflicts; the rules are not a general
  semantic contradiction solver.
- **Small-model omissions or slow inference:** a grounded note may be incomplete or
  time out. Evaluate coverage separately from validity and record CPU latency.
