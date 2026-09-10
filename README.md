# Clinical coder

Clinical coder produces source-backed clinical notes from speaker-labelled English
and Swahili consultations. It preserves verbatim evidence and validates notes before
writing them. Separate contracts define deterministic coding and cited guideline
knowledge for an auditable clinical workflow.

[Requirements](docs/prd.md) · [Architecture](docs/architecture.md) ·
[Design decisions](docs/decisions.md) · [Testing](docs/testing-strategy.md) ·
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

## Verification

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
