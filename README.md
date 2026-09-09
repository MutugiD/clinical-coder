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

The scaffold and CI are implemented. Clinical stages and service endpoints are
planned, not yet available. See [requirements](docs/prd.md),
[architecture](docs/architecture.md), [decisions](docs/decisions.md), and
[testing strategy](docs/testing-strategy.md). Schemas define the intended public
interfaces before clinical implementation.

Final delivery will include the exact CLI commands, four Compose services,
validated sample outputs, actual time and cuts, and the required leadership answer.
