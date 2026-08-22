---
title: TestSeal documentation
description: Install, configure, and operate TestSeal in local development and CI.
---

# TestSeal

**Deterministic test-integrity checks for Python and pytest diffs.**

TestSeal compares tests before and after a change. It reports concrete signals
that can make a test suite easier to pass, including removed assertions, new
skips, weaker comparisons, wider tolerances, swallowed exceptions, snapshot
regeneration, and suspicious mocks.

[Install TestSeal](getting-started/installation.md){ .md-button .md-button--primary }
[Run the first scan](getting-started/first-scan.md){ .md-button }

```diff
- assert total == Decimal("19.99")
+ assert total
```

```text
[HIGH] TS003 tests/test_totals.py:10:1 - Assertion weakened
  A specific equality assertion was replaced by a truthy/non-null check
  Evidence: assert total == Decimal("19.99")  ->  assert total
  Fingerprint: 3c056c0da89673cd1a42eacc
  Fix: Assert the specific expected value, type, relationship, or exception.

TestSeal: 1 finding(s) in 1 changed file(s) (high 1, medium 0, low 0).
```

## What TestSeal provides

<div class="grid cards" markdown>

-   **Repeatable findings**

    The same diff and configuration produce the same result. Detection does not
    depend on a model, network service, or prompt.

-   **Reviewable evidence**

    Each finding includes a rule ID, location, severity, confidence, evidence,
    remediation, and stable fingerprint.

-   **Safe analysis**

    TestSeal reads Git data and parses Python source. It does not import the
    target repository, load pytest plugins, or run tests.

-   **Local and CI delivery**

    Use the CLI, pre-commit hook, GitHub Action, JSON output, or SARIF 2.1.0.

</div>

## Quick start

```bash
python -m pip install testseal
testseal demo
testseal scan
```

The demo is offline and does not read the current repository or configuration.
The default scan checks working-tree and non-ignored untracked changes. It is
advisory and exits successfully even when findings are present. Set a threshold
only after reviewing representative results:

```bash
testseal scan --fail-on high
```

## Choose the right section

| If you want to | Start here |
| --- | --- |
| Install the CLI | [Installation](getting-started/installation.md) |
| Understand a finding | [Rule reference](rules.md) |
| Add a repository policy | [Adopt in a repository](getting-started/adoption.md) |
| Configure GitHub Actions | [GitHub Actions](integrations/github-actions.md) |
| Configure file patterns and rules | [Configuration reference](reference/configuration.md) |
| Consume JSON or SARIF | [Report reference](reference/reports.md) |
| Diagnose an unexpected result | [Troubleshooting](guides/troubleshooting.md) |
| Understand execution and trust boundaries | [Architecture](architecture.md) |

## Scope

TestSeal analyzes Python test files and common pytest, unittest, and
`unittest.mock` syntax. It identifies specific transformations in a diff. It
does not prove test completeness, determine intent, or replace tests, review,
coverage, type checking, or security analysis.

See [scope and limitations](concepts/scope-and-limitations.md) before setting a
blocking policy.
