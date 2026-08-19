---
description: Complete GitHub Action input, output, event, and outcome contract.
---

# GitHub Action reference

## Usage

```yaml
- id: testseal
  uses: satwiksps/testseal@v0.1.0
  with:
    fail-on: high
```

The Action runs on Node.js 24 and invokes the bundled Python core. Run
`actions/setup-python` first with Python 3.11 or newer.

## Inputs

| Input | Required | Default | Description |
| --- | --- | --- | --- |
| `base` | No | Event-derived | Base Git ref or commit |
| `head` | No | Event-derived or `HEAD` | Head Git ref or commit |
| `staged` | No | `false` | Analyze staged changes |
| `config` | No | Discovered policy | TOML configuration path |
| `paths` | No | All eligible changes | Newline-delimited repository paths |
| `fail-on` | No | Repository policy | `never`, `low`, `medium`, or `high` |
| `python-command` | No | `python` | Python executable name or absolute path |
| `install` | No | `true` | Install bundled TestSeal source before scanning |

### Input constraints

- `staged` cannot be combined with `base` or `head`.
- `python-command` cannot contain line breaks or NUL bytes.
- `python-command` is executed directly, not through a shell.
- `paths` is trimmed and blank entries are removed.
- boolean inputs accept only `true` or `false`, case-insensitively.
- an explicit `fail-on` value overrides repository configuration.

## Event-derived revisions

When `base`, `head`, and `staged` are omitted:

- `pull_request` uses `pull_request.base.sha` and `pull_request.head.sha`;
- `merge_group` uses `merge_group.base_sha` and `merge_group.head_sha`;
- other events use the CLI working-tree default.

The event SHA values must be 40 to 64 hexadecimal characters. Missing or
invalid event values fail the Action before scanning.

## Installation behavior

With `install: true`, the Action runs the equivalent of:

```text
python -m pip install --disable-pip-version-check --no-input <bundled-project-root>
```

The path is resolved from the Action archive, not from the consumer workspace.
If the bundled `pyproject.toml` is missing, the Action fails closed instead of
installing an unrelated repository project or falling back to PyPI.

With `install: false`, the selected Python environment must already provide a
compatible `testseal` module.

## Outputs

| Output | Type | Description |
| --- | --- | --- |
| `finding-count` | integer string | Visible finding count |
| `high-count` | integer string | High-severity count |
| `medium-count` | integer string | Medium-severity count |
| `low-count` | integer string | Low-severity count |
| `files-scanned` | integer string | Eligible changed file count |
| `suppressed-count` | integer string | Fingerprint-suppressed count |
| `outcome` | string | Normalized Action outcome |
| `result` | JSON string | Complete normalized JSON report |

GitHub Action outputs are strings when consumed in expressions. Parse numeric
values with `fromJSON` when numeric comparison is required:

```yaml
if: ${{ fromJSON(steps.testseal.outputs.high-count) > 0 }}
```

Parse the full report:

```yaml
- name: Save normalized report
  env:
    TESTSEAL_RESULT: ${{ steps.testseal.outputs.result }}
  run: printf '%s\n' "$TESTSEAL_RESULT" > testseal.json
```

## Outcomes

| Outcome | Meaning | Step state |
| --- | --- | --- |
| `clean` | Scan completed with no visible findings or warnings | Success |
| `findings` | Advisory scan completed with findings | Success |
| `incomplete` | Scan produced parse warnings | Success in advisory mode, failure in blocking mode |
| `threshold-failed` | CLI returned `1` | Failure |
| `error` | Input, install, process, or report error | Failure |

When the CLI returns `2` with a valid report containing warnings, the Action
emits annotations and outputs before failing the step as incomplete. Exit `2`
without a valid warning-bearing report is an error.

## Annotations

Each finding becomes a source annotation. Severity maps to GitHub annotation
levels through the Action adapter, and available path, line, column, evidence,
remediation, and fingerprint data are retained in the message or properties.

Parse warnings become workflow warnings. Source-derived values are passed
through the Actions toolkit rather than emitted as workflow command strings.

## Permissions

The Action needs only read access to repository contents:

```yaml
permissions:
  contents: read
```

It does not upload reports or call an external TestSeal service.
