"""Command-line interface for local hooks and CI."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from . import __version__
from .auditor import Auditor
from .config import ConfigError, load_config
from .diff import DiffError, GitRepository, filter_changes, parse_unified_diff
from .reporters import render


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="testseal",
        description="Detect deterministic signs of test-suite weakening in a diff.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan", help="audit a Git or unified diff")
    source = scan.add_mutually_exclusive_group()
    source.add_argument(
        "--base", help="base Git revision (uses merge-base with --head)"
    )
    source.add_argument(
        "--staged", action="store_true", help="audit staged/index changes"
    )
    source.add_argument(
        "--diff",
        metavar="PATH",
        help=(
            "audit a unified diff from PATH, or '-' for standard input "
            "(best-effort hunk-only analysis)"
        ),
    )
    scan.add_argument("--head", help="head revision (default: HEAD)")
    scan.add_argument("--config", metavar="PATH", help="TOML configuration path")
    scan.add_argument(
        "--format",
        choices=("text", "json", "sarif"),
        default="text",
        help="report format (default: text)",
    )
    scan.add_argument("--output", metavar="PATH", help="write report to a file")
    scan.add_argument(
        "--fail-on",
        choices=("never", "low", "medium", "high"),
        help="exit 1 at this severity (default: config, otherwise never)",
    )
    scan.add_argument(
        "--repo",
        default=".",
        metavar="PATH",
        help=argparse.SUPPRESS,
    )
    scan.add_argument("paths", nargs="*", help="optional repository paths to scan")
    return parser


def _read_diff(path: str, stdin: TextIO) -> str:
    if path == "-":
        return stdin.read()
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise DiffError(f"cannot read diff {path}: {exc}") from exc


def _run_scan(args: argparse.Namespace, *, stdin: TextIO, stdout: TextIO) -> int:
    if args.head is not None and (args.staged or args.diff is not None):
        mode = "--staged" if args.staged else "--diff"
        raise DiffError(f"--head cannot be combined with {mode}")

    head = "HEAD" if args.head is None else args.head
    if args.diff is not None:
        config_root = args.repo
        changes = filter_changes(
            parse_unified_diff(_read_diff(args.diff, stdin)), args.paths
        )
    else:
        repository = GitRepository(args.repo)
        config_root = repository.root
        if args.staged:
            changes = repository.staged_changes(paths=args.paths)
        elif args.base is not None:
            changes = repository.revision_changes(args.base, head, paths=args.paths)
        else:
            changes = repository.working_changes(head=head, paths=args.paths)

    config = load_config(args.config, cwd=config_root).with_fail_on(args.fail_on)
    result = Auditor(config).audit(changes)
    report = render(result, args.format)
    if args.output:
        output = Path(args.output)
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(report, encoding="utf-8")
        except OSError as exc:
            raise DiffError(f"cannot write report {output}: {exc}") from exc
    else:
        stdout.write(report)
    if result.parse_warnings and config.fail_on is not None:
        return 2
    return 1 if result.fails_at(config.fail_on) else 0


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    parser = build_parser()
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    try:
        args = parser.parse_args(argv)
        if args.command == "scan":
            return _run_scan(args, stdin=stdin, stdout=stdout)
        parser.error(f"unknown command: {args.command}")
    except (ConfigError, DiffError, ValueError) as exc:
        stderr.write(f"testseal: error: {exc}\n")
        return 2
    return 2
