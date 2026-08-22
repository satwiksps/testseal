---
description: Supported Python API for embedding TestSeal diff analysis.
---

# Python API

The package exports a small API for Python integrations. The CLI remains the
recommended boundary for language-neutral automation and subprocess isolation.

## Exported names

```python
from testseal import (
    AuditResult,
    Auditor,
    Confidence,
    Config,
    ConfigError,
    Finding,
    Severity,
    audit_diff,
    load_config,
)
```

These names are listed in `testseal.__all__`. Modules below the package root are
implementation details unless documented here.

## `audit_diff`

```python
def audit_diff(text: str, config: Config | None = None) -> AuditResult
```

Parse and audit caller-supplied unified-diff text:

```python
from testseal import Severity, audit_diff

patch = """\
diff --git a/tests/test_total.py b/tests/test_total.py
--- a/tests/test_total.py
+++ b/tests/test_total.py
@@ -1 +1 @@
-assert total == 42
+assert total
"""

result = audit_diff(patch)

for finding in result.findings:
    print(finding.rule_id, finding.path, finding.line)

if result.fails_at(Severity.HIGH):
    raise SystemExit(1)
```

This convenience function has the same context limits as CLI `--diff`. It does
not hydrate Git blobs.

## `Auditor`

```python
Auditor(config: Config | None = None)
```

`Auditor.audit(changes)` accepts a sequence of normalized internal changed-file
records. Construction and Git hydration of those records are not currently a
public package-root API. Most embeddings should use `audit_diff` or invoke the
CLI.

## `Config`

`Config` is an immutable dataclass containing resolved policy. Construct it for
programmatic use:

```python
from testseal import Config, Severity

config = Config(
    fail_on=Severity.HIGH,
    test_patterns=("tests/**/*.py",),
    disabled_rules=frozenset({"TS008"}),
)
```

Using `load_config` is preferred when policy is stored in TOML because it applies
the same validation and discovery rules as the CLI.

## `load_config`

```python
def load_config(path: str | Path | None = None, *, cwd: str | Path = ".") -> Config
```

Load an explicit file:

```python
from testseal import load_config

config = load_config("config/testseal.toml")
```

Discover policy in a repository root:

```python
config = load_config(cwd="/workspace/project")
```

Malformed policy raises `ConfigError`.

## `AuditResult`

Important attributes and methods:

| Member | Meaning |
| --- | --- |
| `files_scanned` | Eligible changed-file count |
| `findings` | List of visible `Finding` objects |
| `parse_warnings` | Incomplete-analysis warning strings |
| `suppressed_count` | Findings removed by fingerprint policy |
| `version` | JSON report schema version |
| `by_severity` | Computed severity count mapping |
| `summary` | JSON-compatible summary mapping |
| `to_dict()` | Complete JSON-compatible report mapping |
| `fails_at(threshold)` | Whether a visible finding reaches a severity |

## `Finding`

A frozen dataclass describing one normalized signal. Public fields match the
JSON report with Python snake-case names. `to_dict()` returns a JSON-compatible
mapping and omits optional fields that have no value.

Fingerprint generation is automatic when `fingerprint=None`. Callers should not
construct findings for policy suppression unless they reproduce TestSeal's
normal rule pipeline.

## `Severity` and `Confidence`

Both are string enums with `low`, `medium`, and `high` values.

```python
from testseal import Severity

threshold = Severity.parse("HIGH")
assert threshold is Severity.HIGH
```

`Severity.parse` is case-insensitive. `Severity.rank` provides ordering used by
failure thresholds.

## Compatibility

- The JSON schema version is the stable machine-readable contract.
- Exported package-root names are the supported Python surface.
- Rule IDs are stable integration keys.
- Internal modules and normalized Git data structures are not compatibility
  surfaces.
- Callers should preserve warnings and handle configuration or diff errors.
