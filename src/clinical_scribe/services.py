"""Independently started HTTP wrappers over the same processing contracts."""

import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from clinical_scribe import __version__
from clinical_scribe.boundaries import STAGES, process
from clinical_scribe.config import Settings
from clinical_scribe.contracts import enforce
from clinical_scribe.errors import BoundaryOutputError, ProviderError, StageError
from clinical_scribe.loaders import parse_json


def create_app(stage: str | None = None) -> FastAPI:
    stage = stage or os.getenv("SCRIBE_SERVICE", "extract")
    if stage not in STAGES:
        raise ValueError("SCRIBE_SERVICE must be extract, validate, resolve or knowledge")
    app = FastAPI(title="Clinical " + stage, version=__version__)

    @app.get("/health")
    def health():
        result = {"service": stage, "name": stage, "version": __version__}
        enforce("health", result, stage)
        return result

    @app.post("/process")
    async def handle(request: Request):
        try:
            payload = parse_json((await request.body()).decode("utf-8"), stage, "request")
            settings = None
            if stage == "extract":
                flag = os.getenv("SCRIBE_OFFLINE", "false").casefold()
                if flag not in {"true", "false", "1", "0"}:
                    raise ProviderError(
                        stage, "invalid SCRIBE_OFFLINE configuration", "environment"
                    )
                settings = Settings.from_env(offline=flag in {"true", "1"})
            result, _ = await run_in_threadpool(process, stage, payload, settings)
            return JSONResponse(result)
        except BoundaryOutputError as exc:
            status, error = 500, exc
        except ProviderError as exc:
            status, error = 503, exc
        except StageError as exc:
            status, error = (503 if exc.stage == "check" else 422), exc
        except UnicodeError:
            status, error = 422, StageError(stage, "request must be UTF-8", "request")
        except Exception:
            status, error = 500, StageError(stage, "unexpected internal failure", "service")
        body = {"error": {"stage": stage, "source": error.source, "message": error.message}}
        enforce("service_error", body, stage)
        return JSONResponse(body, status_code=status)

    return app
