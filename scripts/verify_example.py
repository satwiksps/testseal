"""Verify that the documented example produces the expected finding."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    command = [
        sys.executable,
        "-m",
        "testseal",
        "scan",
        "--diff",
        str(ROOT / "examples/diffs/assertion-weakened.diff"),
        "--format",
        "json",
        "--fail-on",
        "never",
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        print("Documented example timed out after 30 seconds", file=sys.stderr)
        return 1
    if result.returncode != 0:
        print(result.stderr or result.stdout, file=sys.stderr)
        return result.returncode

    try:
        report = json.loads(result.stdout)
        findings = report["findings"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"Example did not produce a valid report: {exc}", file=sys.stderr)
        return 1

    if not isinstance(findings, list) or not all(
        isinstance(item, dict) for item in findings
    ):
        print(
            "Example report field 'findings' must be an array of objects",
            file=sys.stderr,
        )
        return 1

    if (
        len(findings) != 1
        or findings[0].get("rule_id") != "TS003"
        or findings[0].get("severity") != "high"
    ):
        print(
            "Expected exactly one high-severity TS003 finding; "
            f"received {json.dumps(findings, indent=2)}",
            file=sys.stderr,
        )
        return 1

    print("Documented diff produced one high-severity TS003 finding")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
