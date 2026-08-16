# TestSeal

![TestSeal — deterministic test integrity for the agent era](https://raw.githubusercontent.com/satwiksps/testseal/main/docs/assets/testseal-banner.svg)

[![CI](https://github.com/satwiksps/testseal/actions/workflows/ci.yml/badge.svg)](https://github.com/satwiksps/testseal/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/satwiksps/testseal)](https://github.com/satwiksps/testseal/releases)
[![PyPI](https://img.shields.io/pypi/v/testseal?logo=pypi&logoColor=white)](https://pypi.org/project/testseal/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License](https://img.shields.io/github/license/satwiksps/testseal)](https://github.com/satwiksps/testseal/blob/main/LICENSE)

**Deterministic test-integrity checks for Python and pytest diffs.**

TestSeal compares tests before and after a change and reports concrete weakening
signals: removed assertions, newly disabled tests, weaker comparisons, wider
tolerances, swallowed exceptions, snapshot regeneration, and suspicious mocks.
It runs locally, needs no model or API key, and never imports or executes the
repository it scans.

```diff
- assert total == Decimal("19.99")
+ assert total
```

```text
[HIGH] TS003 tests/test_checkout.py:42:5 - Assertion weakened
  A precise equality assertion became a truthiness assertion.
  Fingerprint: 6c48d147cbe59f553e224d7d
```

## Why TestSeal

A green test suite is weak evidence when the same change made the suite easier
to pass. Ordinary linters accept both sides of the example because both are
valid Python. General code reviewers may notice the downgrade, but their output
is probabilistic. TestSeal provides a narrow, reproducible signal dedicated to
how the tests themselves changed.

- **Deterministic:** identical input and configuration produce identical output.
- **Offline:** zero runtime dependencies, model calls, telemetry, or accounts.
- **Diff-aware:** compares complete before/after syntax when Git blobs are available.
- **Safe by design:** reads source and Git data without importing the target project.
- **Advisory by default:** teams choose when findings should block a workflow.
- **Portable:** text, versioned JSON, SARIF 2.1.0, pre-commit, and GitHub Actions.

## Install

TestSeal requires Python 3.11 or newer and Git 2.x for repository-backed scans:

```bash
python -m pip install testseal
```

For an isolated CLI installation:

```bash
uv tool install testseal
# or: pipx install testseal
```

## Use the CLI

Scan tracked changes plus non-ignored untracked files in the working tree:

```bash
testseal scan
```

Scan a branch relative to its base:

```bash
testseal scan --base origin/main --head HEAD
```

Scan only staged changes:

```bash
testseal scan --staged
```

TestSeal remains advisory unless a threshold is configured:

```bash
testseal scan --fail-on high
```

Exit codes are `0` for a completed advisory scan, `1` when the selected finding
threshold is met, and `2` for invalid configuration or an incomplete blocking
scan.

### Output

Text is the default. JSON and SARIF can be printed or written atomically:

```bash
testseal scan --base origin/main --format json --output testseal-report.json
testseal scan --base origin/main --format sarif --output testseal-report.sarif
```

Run `testseal scan --help` for the complete CLI contract.

## Configure policy

TestSeal discovers `testseal.toml` first, then `[tool.testseal]` in
`pyproject.toml`. An explicit `--config PATH` takes precedence.

```toml
[testseal]
fail_on = "high"
test_patterns = ["test_*.py", "*_test.py", "tests/**/*.py"]
source_roots = ["src"]
disabled_rules = ["TS008"]

# Copy a fingerprint from text, JSON, SARIF, or the Action output after review.
ignore_fingerprints = ["6c48d147cbe59f553e224d7d"]

[testseal.rules.TS006]
severity = "low"
```

Configuration is strict: unknown keys, rule IDs, severities, and malformed
fingerprints fail with exit code `2` instead of silently weakening policy.
See the repository's
[default](https://github.com/satwiksps/testseal/blob/main/testseal.toml),
[strict](https://github.com/satwiksps/testseal/blob/main/examples/configs/strict.toml),
and [monorepo](https://github.com/satwiksps/testseal/blob/main/examples/configs/monorepo.toml)
examples.

## Pre-commit

The hook installs TestSeal in its own environment and scans the staged diff:

```yaml
repos:
  - repo: https://github.com/satwiksps/testseal
    rev: v0.1.0
    hooks:
      - id: testseal
        args: ["--fail-on", "high"] # omit to remain advisory
```

## GitHub Actions

The Action installs the Python core bundled in the same release, derives pull
request refs from the event payload, annotates changed lines, and exposes a
normalized JSON result.

```yaml
name: Test integrity

on: [pull_request]

permissions:
  contents: read

jobs:
  testseal:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: "3.12"
      - id: testseal
        uses: satwiksps/testseal@v0.1.0
        with:
          fail-on: high
```

Omit `fail-on` to honor repository configuration. The default `install: true`
uses only the source bundled with the pinned Action release. Set
`install: false` only when the same TestSeal version is already installed in the
selected Python environment.

Action outputs include `finding-count`, severity counts, `files-scanned`,
`suppressed-count`, `outcome`, and the complete normalized `result` JSON.

## Rules

| Rule | Signal | Severity | Confidence |
| --- | --- | --- | --- |
| `TS001` | An assertion was removed from a test | High | High |
| `TS002` | A pytest or unittest skip/xfail was added | High | High |
| `TS003` | An assertion was replaced with a weaker form | High | High |
| `TS004` | A comparison tolerance was widened | High | High |
| `TS005` | A broad exception is now swallowed | High | High |
| `TS006` | Snapshot update or regeneration behavior was added | Low | Low |
| `TS007` | The apparent subject under test is now mocked | Medium | Medium |
| `TS008` | Source and a configured guarding test changed together | Low | Low |

The table is a summary. The
[rule reference](https://github.com/satwiksps/testseal/blob/main/docs/rules.md)
defines supported syntax, intentional non-findings, and precision limits.
Context-heavy rules should be baselined before enabling a blocking threshold.

## Trust boundary and limitations

TestSeal invokes Git to obtain refs, diffs, and blobs, then parses Python source
with the running interpreter. It does not run tests, import changed modules, or
execute hooks from the target repository. Use `pull_request`, read-only
permissions, and no repository secrets when scanning contributions from forks.

The analyzer reports specific transformations; it does not decide whether an
author is honest, prove that tests are complete, or replace code review,
coverage, linters, type checkers, and security analysis. A finding can describe
a legitimate refactor, so blocking is explicit and reviewed exceptions use
stable fingerprints rather than hidden heuristics.

Read the full [architecture and trust model](https://github.com/satwiksps/testseal/blob/main/docs/architecture.md)
and [security policy](https://github.com/satwiksps/testseal/blob/main/SECURITY.md).

## Development

```bash
git clone https://github.com/satwiksps/testseal.git
cd testseal
python -m venv .venv
# POSIX: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
```

The TypeScript Action lives in `packages/action` and the Next.js/Tailwind site
in `site`. See [CONTRIBUTING.md](https://github.com/satwiksps/testseal/blob/main/CONTRIBUTING.md)
for the complete verification commands and rule-change requirements.

## License

TestSeal is licensed under the [Apache License 2.0](https://github.com/satwiksps/testseal/blob/main/LICENSE).
