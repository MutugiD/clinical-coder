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

The scaffold, CI, CLI argument contract, strict input parsing, and `check` are
implemented. Clinical stages currently fail explicitly as not implemented.
See [requirements](docs/prd.md),
[architecture](docs/architecture.md), [decisions](docs/decisions.md), and
[testing strategy](docs/testing-strategy.md). Schemas define the intended public
interfaces before clinical implementation.

Final delivery will include the exact CLI commands, four Compose services,
validated sample outputs, actual time and cuts, and the required leadership answer.

## Extraction configuration

Export `OLLAMA_BASE_URL` (default `http://localhost:11434`), `OLLAMA_MODEL`
(default `glm-5.2:cloud`), and optionally `OLLAMA_TIMEOUT_SECONDS` (default 180).
The supplied `.env.example` documents settings; it is not loaded automatically.
Run `./scribe check` to verify the configured model is listed by Ollama.
This checks availability, not whether cloud generation is authorized or retired.

The installed Gemini preview alias returned HTTP 410 during a live test. The
explicit default `glm-5.2:cloud` returned valid JSON. There is no automatic fallback.
The evaluator needs its own accessible Ollama endpoint and any cloud authentication
required by the chosen model. Listing a cloud alias does not provide offline weights.

Input files are supplied separately. `instructions-data/` stays local and is excluded
from Git and Docker images. All CLI paths may be absolute or relative to the
repository root; invoke the CLI and service processes from that root.
