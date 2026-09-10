# Clinical coder

Grounded clinical note extraction, deterministic coding, and cited guideline rules.

This repository implements the supplied clinical engineering work sample in
Python 3.12. The authoritative interface is Appendix A of the supplied brief.

## Development setup

```sh
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.lock
pip install --no-deps --no-build-isolation -e .
./scribe --version
```

On Windows activate `.venv/Scripts/Activate.ps1` and run `python scribe`.

## Checks

```sh
ruff check .
pytest -q
python -m compileall -q src tests
docker build -t clinical-scribe .
docker run --rm clinical-scribe --version
```

## Design and implementation status

The scaffold, CI, CLI argument contract, strict input parsing, configuration, and
readiness diagnostics are implemented. Clinical stages are not implemented yet.
`check` deliberately returns nonzero even when dependencies are present, explaining
that extraction is unfinished. This milestone is not ready for clinical grading.
See [requirements](docs/prd.md),
[architecture](docs/architecture.md), [decisions](docs/decisions.md), and
[testing strategy](docs/testing-strategy.md). Schemas define the intended public
interfaces before clinical implementation.

Final delivery will include the exact CLI commands, four Compose services,
validated sample outputs, actual time and cuts, and the required leadership answer.

## Extraction configuration

Select `--provider ollama` or `--provider gemini` for `check`, `extract`, and
`pipeline`. If the flag is absent, `SCRIBE_PROVIDER` supplies the selection and
defaults to `ollama`. `--offline` is mutually exclusive with an explicit provider
and ignores provider environment settings. No failure silently switches providers.

| Setting | Default or purpose |
| --- | --- |
| `OLLAMA_BASE_URL` | `http://localhost:11434` |
| `OLLAMA_MODEL` | `qwen3:1.7b` |
| `OLLAMA_TIMEOUT_SECONDS` | `180` |
| `GEMINI_API_KEY` | Required for Gemini; no default |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` |
| `GEMINI_TIMEOUT_SECONDS` | `180` |

The supplied `.env.example` documents settings; it is not loaded automatically.
Local Ollama readiness distinguishes a missing executable, unavailable server, and
missing model. For a remote endpoint, only the server and model are checked.
Gemini readiness checks key presence and model metadata access; it does not prove
generation quota or extraction accuracy. Both then report the unfinished stage.

After installing Ollama, start it with `ollama serve` if it is not already running,
then pull the local model with `ollama pull qwen3:1.7b`. No cloud model or GPU is
required for the planned local path. CPU latency and extraction accuracy have not
yet been measured. The final grading setup will include this pull within five
commands; the current development instructions are not that final setup.

Offline replay and unseen-input rules are scheduled for PR 4. `check --offline`
currently reports missing replay artifacts or an unimplemented path, not readiness.
No sample outputs are being presented as live extraction results.

## Clarified clinical behavior

Conflicting statements retain separate spans and shared conflict metadata and stay
uncoded. Probable and differential diagnoses may resolve while retaining certainty;
considered-and-rejected statements never receive codes. Optional contextual spans
aid traceability but cannot justify values or numbers absent from the primary span.
Mixed-language values are acceptable. Knowledge rows and corpus gaps come only from
the guideline; optional note input influences prose only.

## Remaining milestones

PR 4 implements extraction, offline handling, and strict validation. PR 5 implements
deterministic resolution, including uncertainty and conflicts. PR 6 implements
guideline extraction. PR 7 implements services and audit logging. PR 8 verifies
CPU-only setup and completes outputs, limitations, and the leadership answer.

Input files are supplied separately. `instructions-data/` stays local and is excluded
from Git and Docker images. All CLI paths may be absolute or relative to the
repository root; invoke the CLI and service processes from that root.
