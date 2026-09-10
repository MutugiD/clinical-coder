"""Command-line entry point."""

import argparse
import sys
import traceback

from clinical_scribe import __version__
from clinical_scribe.config import Settings
from clinical_scribe.contracts import enforce
from clinical_scribe.errors import StageError
from clinical_scribe.extraction import extract
from clinical_scribe.loaders import parse_register, read_json, read_text
from clinical_scribe.output import write_json
from clinical_scribe.readiness import check
from clinical_scribe.resolver import resolve
from clinical_scribe.transcript import parse_transcript
from clinical_scribe.validation import validate


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
    mode.add_argument("--provider", choices=("ollama", "gemini"), default=None)
    mode.add_argument("--offline", action="store_true")


def dispatch(args: argparse.Namespace) -> None:
    stage = args.command
    settings = None
    if stage in ("check", "extract", "pipeline"):
        settings = Settings.from_env(args.provider, offline=args.offline)
    if stage == "check":
        check(settings)
        return
    if stage == "extract":
        transcript = read_text(args.transcript, stage)
        note, _ = extract(transcript, settings)
        write_json(args.out, note, stage)
        return
    if stage == "validate":
        validate(read_text(args.transcript, stage), read_json(args.note, stage))
        return
    if stage == "resolve":
        resolved = resolve(
            read_json(args.note, stage), read_text(args.register, stage), args.register
        )
        write_json(args.out, resolved, stage)
        return
    if hasattr(args, "transcript"):
        parse_transcript(read_text(args.transcript, stage), stage)
    if getattr(args, "note", None):
        enforce("note", read_json(args.note, stage), stage)
    if hasattr(args, "register"):
        parse_register(read_text(args.register, "resolve"), args.register)
    if hasattr(args, "source"):
        read_text(args.source, "knowledge")
    raise StageError(stage, "stage not implemented in this milestone")


def main() -> int:
    args = parser().parse_args()
    try:
        dispatch(args)
    except StageError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception:
        print(f"{args.command}: unexpected internal failure", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1
    return 0
