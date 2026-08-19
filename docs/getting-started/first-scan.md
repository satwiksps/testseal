---
description: Run TestSeal against working-tree, staged, branch, and saved changes.
---

# First scan

Run TestSeal from the root of a Git repository:

```bash
testseal scan
```

This compares the working tree with `HEAD`. It includes tracked modifications
and non-ignored untracked files. Built-in path policy limits analysis to Python
and snapshot files that match the configured include patterns.

## Read the result

A finding has a severity, rule ID, source location, title, explanation,
fingerprint, and usually evidence and remediation:

```text
[HIGH] TS001 tests/test_invoice.py:27:5 - Assertion removed
  An assertion was removed from test_total_with_tax.
  Evidence: assert total == Decimal("19.99")
  Fingerprint: 2ac578e72a8fb4a68d1b96f1
  Fix: Restore the assertion or replace it with an equally specific check.
```

The final line summarizes visible findings and changed files:

```text
TestSeal: 1 finding(s) in 2 changed file(s) (high 1, medium 0, low 0).
```

No findings produces a short confirmation:

```text
TestSeal: no test-integrity findings across 2 changed file(s).
```

## Understand advisory mode

TestSeal is advisory unless a failure threshold is configured. Findings in an
advisory scan return exit code `0`, which is suitable for an initial rollout.

To block on high-severity findings for one command:

```bash
testseal scan --fail-on high
```

The command returns `1` when at least one visible finding meets or exceeds the
threshold. Lower severities remain visible but do not fail the command.

## Try the main scan modes

### Staged changes

```bash
git add tests/test_invoice.py
testseal scan --staged
```

This is the mode used by the bundled pre-commit hook.

### Branch comparison

```bash
git fetch origin main
testseal scan --base origin/main --head HEAD
```

TestSeal uses the merge base of the two revisions. This matches the effective
change introduced by the branch rather than unrelated changes added to the base
after the branch was created.

### Saved diff

```bash
git diff origin/main...HEAD > changes.patch
testseal scan --diff changes.patch
```

Saved diffs are useful outside a repository, but only include changed hunks.
Git-backed modes can load complete before and after files and provide stronger
semantic analysis.

## Limit the scan to paths

Add repository-relative paths after the options:

```bash
testseal scan --base origin/main tests/unit packages/billing/tests
```

Path arguments narrow the Git diff first. Configuration include, exclude, and
test patterns are then applied to the selected changes.

## Write a machine-readable report

```bash
testseal scan \
  --base origin/main \
  --format json \
  --output artifacts/testseal.json
```

Use `--format sarif` for systems that accept SARIF 2.1.0. Parent directories for
the output are created automatically.

## Next step

Read [adopt in a repository](adoption.md) before enabling TestSeal as a required
CI check.
