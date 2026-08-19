---
description: Diagnose installation, Git, configuration, parsing, and CI problems.
---

# Troubleshooting

## Command not found

Confirm which interpreter received the package:

```bash
python -m pip show testseal
python -m testseal --version
```

If `python -m testseal` works but `testseal` does not, the interpreter's scripts
directory is missing from `PATH`. Use an isolated tool installation with
`uv tool install testseal` or `pipx install testseal` to manage that path.

## Python version is unsupported

TestSeal requires Python 3.11 or newer:

```bash
python --version
```

The GitHub Action can select a specific executable with `python-command`, but
the executable must already exist on the runner.

## Not a Git repository

Working-tree, staged, and revision modes must run inside a Git worktree. Change
to the repository root or scan a saved patch with `--diff`.

## Unknown or missing revision

Fetch the base revision before scanning:

```bash
git fetch --no-tags origin main
testseal scan --base origin/main --head HEAD
```

In GitHub Actions, use `fetch-depth: 0`. The Action cannot derive content that
is absent from the checkout.

## Configuration file not found

An explicit `--config` path must exist. Without the option, TestSeal discovers
`testseal.toml` and then `pyproject.toml` from the repository root.

Print the current directory and inspect the path:

```bash
pwd
testseal scan --config ./testseal.toml
```

## Unknown configuration key

Configuration is fail-closed. Check spelling and table placement against the
[configuration reference](../reference/configuration.md). Common mistakes are:

- using `[tool.testseal]` in `testseal.toml` when `[testseal]` is clearer;
- placing rule tables outside the TestSeal table;
- using a rule ID other than `TS001` through `TS008`;
- providing a string where an array is required;
- using a fingerprint that is not exactly 24 hexadecimal characters.

## No changed files

Check the selected input:

```bash
git status --short
git diff --name-only
git diff --cached --name-only
git diff --name-only origin/main...HEAD
```

Then check `include`, `exclude`, `test_patterns`, and positional paths. Only
eligible changes contribute to `files_scanned`.

## Expected finding is missing

1. Confirm the file matches `include` and `test_patterns`.
2. Confirm the rule is enabled.
3. Check whether its fingerprint is suppressed.
4. Use a Git-backed mode instead of a partial patch.
5. Compare the syntax with the rule's supported forms.
6. Reduce the case to a minimal before and after example.

TestSeal intentionally does not infer custom matcher APIs, dynamic aliases, or
domain-specific semantics.

## Unexpected finding

Read the rule's intentional non-findings and limits. If the transformation is
correct but justified, use a reviewed fingerprint suppression. If the matcher
misclassifies documented syntax, open a false-positive report with a minimal
fixture.

## Parse warning

The running Python interpreter could not parse a changed test version. Causes
include invalid syntax, syntax newer than the interpreter, or incomplete
unified-diff context.

- Run TestSeal with a Python version that supports the target syntax.
- Prefer Git-backed scanning so complete files can be loaded.
- Fix invalid source before relying on the integrity result.

Advisory scans report warnings. Blocking scans return exit code `2` so partial
analysis cannot pass silently.

## GitHub Action installation failed

The Action installs the Python project bundled with the pinned Action release.
Check that:

- `actions/setup-python` ran first;
- `python-command` names that interpreter;
- the Action reference points to a complete TestSeal release;
- `install: false` is used only when a matching TestSeal is already installed.

Do not replace the Action package with source copied from an incomplete archive.

## Getting help

Open a [support issue](https://github.com/satwiksps/testseal/issues/new/choose)
with the version, command, configuration, operating system, relevant Git state,
and minimal changed source. Do not include secrets or proprietary code.
