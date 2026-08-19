---
description: Complete command-line reference for TestSeal.
---

# CLI reference

## Synopsis

```text
testseal [--version] scan [OPTIONS] [PATH ...]
python -m testseal [--version] scan [OPTIONS] [PATH ...]
```

TestSeal currently provides one command, `scan`.

## Global option

### `--version`

Print the installed TestSeal version and exit.

```bash
testseal --version
```

## `scan`

Audit a Git-backed change set or unified diff.

```text
testseal scan
  [--base REV | --staged | --diff PATH]
  [--head REV]
  [--config PATH]
  [--format {text,json,sarif}]
  [--output PATH]
  [--fail-on {never,low,medium,high}]
  [PATH ...]
```

### Input mode options

#### `--base REV`

Compare the merge base of `REV` and `--head` with the head revision. If
`--head` is omitted, it defaults to `HEAD`.

```bash
testseal scan --base origin/main
testseal scan --base origin/main --head feature/payment-fix
```

`--base` cannot be combined with `--staged` or `--diff`.

#### `--head REV`

Select the head Git revision. With `--base`, it is the new side of the branch
comparison. Without another input mode, it is the revision compared with the
working tree.

```bash
testseal scan --head HEAD
```

`--head` cannot be combined with `--staged` or `--diff`.

#### `--staged`

Compare the Git index with `HEAD`. Unstaged and untracked working-tree changes
are excluded.

```bash
testseal scan --staged
```

#### `--diff PATH`

Read a UTF-8 unified diff from `PATH`. Use `-` to read standard input.

```bash
testseal scan --diff changes.patch
git diff origin/main...HEAD | testseal scan --diff -
```

Unified-diff mode uses best-effort hunk-only analysis because complete file
versions may be absent.

### Policy and configuration

#### `--config PATH`

Load an explicit TOML configuration. The file may contain `[testseal]`,
`[tool.testseal]`, or TestSeal keys directly at the top level.

```bash
testseal scan --config config/testseal-strict.toml
```

An explicit missing or malformed file returns exit code `2`. Without this
option, TestSeal discovers configuration from the repository root.

#### `--fail-on LEVEL`

Override the configured failure threshold for this invocation.

| Value | Behavior |
| --- | --- |
| `never` | Findings never return exit code `1` |
| `high` | High findings return `1` |
| `medium` | Medium or high findings return `1` |
| `low` | Any finding returns `1` |

```bash
testseal scan --fail-on high
```

If omitted, the value comes from configuration and otherwise defaults to
`never`.

### Report options

#### `--format FORMAT`

Select the report format.

| Format | Use |
| --- | --- |
| `text` | Human-readable terminal output; default |
| `json` | Versioned machine-readable report |
| `sarif` | SARIF 2.1.0 code-scanning report |

```bash
testseal scan --format json
```

#### `--output PATH`

Write the complete report to a UTF-8 file instead of standard output. Parent
directories are created automatically.

```bash
testseal scan --format sarif --output artifacts/testseal.sarif
```

The file is written only after analysis and report rendering complete.

### Positional `PATH`

Zero or more repository paths narrow Git-backed changes before configuration is
applied.

```bash
testseal scan --base origin/main tests/unit services/billing
```

Use `--` before path values that begin with a hyphen:

```bash
testseal scan --staged -- tests/unit
```

## Exit codes

| Exit | Meaning |
| --- | --- |
| `0` | Scan completed and no visible finding reached the threshold |
| `1` | At least one visible finding reached the threshold |
| `2` | Usage, configuration, Git, decoding, parsing in blocking mode, diff validation, or I/O error |

An advisory scan can return `0` with findings or parse warnings. A blocking
scan returns `2` when parse warnings make the analysis incomplete.

## Standard streams

| Stream | Content |
| --- | --- |
| stdout | Selected report unless `--output` is used |
| stderr | Usage and operational error messages |

When a blocking scan has parse warnings, the report can still be produced and
the process returns `2`. Consumers should retain both the report and exit code.

## Configuration precedence

From highest to lowest:

1. CLI `--fail-on` override.
2. Explicit `--config` file.
3. Discovered `testseal.toml`.
4. Discovered `[tool.testseal]` in `pyproject.toml`.
5. Built-in defaults.
