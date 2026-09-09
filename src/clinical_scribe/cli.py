"""Command-line entry point."""

import argparse

from clinical_scribe import __version__


def main() -> int:
    parser = argparse.ArgumentParser(prog="scribe")
    parser.add_argument("--version", action="version", version=__version__)
    parser.parse_args()
    parser.print_help()
    return 0
