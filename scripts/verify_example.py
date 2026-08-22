"""Verify that the documented demo produces the expected finding."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_OUTPUT = """\
[HIGH] TS003 tests/test_totals.py:10:1 - Assertion weakened
  A specific equality assertion was replaced by a truthy/non-null check
  Evidence: assert total == Decimal("19.99")  ->  assert total
  Fingerprint: 3c056c0da89673cd1a42eacc
  Fix: Assert the specific expected value, type, relationship, or exception.

TestSeal: 1 finding(s) in 1 changed file(s) (high 1, medium 0, low 0).
"""


def main() -> int:
    commands = {
        "demo": ["demo"],
        "saved diff": [
            "scan",
            "--diff",
            str(ROOT / "examples/diffs/assertion-weakened.diff"),
        ],
    }
    for label, arguments in commands.items():
        try:
            result = subprocess.run(
                [sys.executable, "-m", "testseal", *arguments],
                check=False,
                capture_output=True,
                cwd=ROOT.parent,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            print(f"Documented {label} timed out after 30 seconds", file=sys.stderr)
            return 1
        if result.returncode != 0:
            print(result.stderr or result.stdout, file=sys.stderr)
            return result.returncode
        if result.stdout != EXPECTED_OUTPUT:
            print(
                f"Documented {label} output does not match the expected report.\n"
                f"Received:\n{result.stdout}",
                file=sys.stderr,
            )
            return 1

    print("Documented demo and saved diff produced the expected TS003 finding")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
