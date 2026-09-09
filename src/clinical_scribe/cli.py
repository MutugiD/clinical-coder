"""Command-line entry point."""

import argparse
import sys
import traceback

from clinical_scribe import __version__
from clinical_scribe.contracts import enforce
from clinical_scribe.errors import StageError
from clinical_scribe.loaders import parse_register, read_json, read_text
from clinical_scribe.readiness import check
from clinical_scribe.transcript import parse_transcript


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scribe")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    for name in ("extract", "validate", "resolve", "knowledge", "pipeline"):
        command = commands.add_parser(name)
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


def dispatch(args: argparse.Namespace) -> None:
    stage = args.command
    if stage == "check":
        check()
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
