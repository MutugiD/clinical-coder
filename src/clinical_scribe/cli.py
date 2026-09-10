"""Command-line entry point."""

import argparse
import sys

from clinical_scribe import __version__
from clinical_scribe.boundaries import process
from clinical_scribe.config import Settings
from clinical_scribe.errors import StageError
from clinical_scribe.loaders import read_json, read_text
from clinical_scribe.output import write_json
from clinical_scribe.pipeline import run_pipeline
from clinical_scribe.readiness import check


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scribe")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    readiness = commands.add_parser("check")
    execution_arguments(readiness)
    for name in ("extract", "validate", "resolve", "knowledge", "pipeline"):
        command = commands.add_parser(name)
        if name in ("extract", "pipeline"):
            execution_arguments(command)
        if name in ("extract", "validate", "pipeline"):
            command.add_argument("--transcript", required=True)
        if name in ("validate", "resolve", "knowledge"):
            command.add_argument("--note", required=name != "knowledge")
        if name in ("resolve", "pipeline"):
            command.add_argument("--register", required=True)
        if name in ("knowledge", "pipeline"):
            command.add_argument("--source", required=True)
        if name != "validate":
            command.add_argument("--out", required=True)
    return parser


def execution_arguments(command: argparse.ArgumentParser) -> None:
    mode = command.add_mutually_exclusive_group()
    mode.add_argument("--provider", choices=("gemini",), default=None)
    mode.add_argument("--offline", action="store_true")


def dispatch(args: argparse.Namespace) -> None:
    stage = args.command
    if stage == "pipeline":
        run_pipeline(
            args.transcript,
            args.register,
            args.source,
            args.out,
            provider=args.provider,
            offline=args.offline,
        )
        return
    settings = None
    if stage in ("check", "extract"):
        settings = Settings.from_env(args.provider, offline=args.offline)
    if stage == "check":
        check(settings)
        return
    payload = {}
    if stage in ("extract", "validate"):
        payload["transcript"] = read_text(args.transcript, stage)
    if getattr(args, "note", None):
        payload["note"] = read_json(args.note, stage)
    if stage == "resolve":
        payload["register"] = read_text(args.register, stage)
    if stage == "knowledge":
        payload["source"] = read_text(args.source, stage)
    try:
        result, _ = process(stage, payload, settings)
    except StageError as exc:
        location = getattr(args, "register", None) or getattr(args, "source", None)
        if location and exc.source in {"input", "register"}:
            raise StageError(stage, exc.message, location) from exc
        raise
    if stage != "validate":
        write_json(args.out, result, stage)


def main() -> int:
    args = parser().parse_args()
    try:
        dispatch(args)
    except StageError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception:
        print(f"{args.command}: unexpected internal failure", file=sys.stderr)
        return 1
    return 0
