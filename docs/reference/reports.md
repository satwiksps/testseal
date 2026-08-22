---
description: Text, JSON schema version 1, SARIF 2.1.0, warnings, and fingerprints.
---

# Report reference

TestSeal renders one normalized finding set as text, JSON, or SARIF. Report
format does not change detection or exit behavior.

## Text

Text is the default format:

```text
[HIGH] TS003 tests/test_totals.py:10:1 - Assertion weakened
  A specific equality assertion was replaced by a truthy/non-null check
  Evidence: assert total == Decimal("19.99")  ->  assert total
  Fingerprint: 3c056c0da89673cd1a42eacc
  Fix: Assert the specific expected value, type, relationship, or exception.

TestSeal: 1 finding(s) in 1 changed file(s) (high 1, medium 0, low 0).
```

Fields without values, such as evidence or remediation, are omitted. Parse
warnings appear after the summary.

## JSON

Select JSON with `--format json`. The top-level `version` is the report schema
version, not the TestSeal package version.

```json
{
  "version": "1",
  "summary": {
    "files_scanned": 1,
    "finding_count": 1,
    "suppressed_count": 0,
    "by_severity": {
      "low": 0,
      "medium": 0,
      "high": 1
    }
  },
  "findings": [
    {
      "rule_id": "TS003",
      "title": "Assertion weakened",
      "message": "A specific equality assertion was replaced by a truthy/non-null check",
      "severity": "high",
      "confidence": "high",
      "path": "tests/test_totals.py",
      "line": 10,
      "column": 1,
      "fingerprint": "3c056c0da89673cd1a42eacc",
      "evidence": "assert total == Decimal(\"19.99\")  ->  assert total",
      "remediation": "Assert the specific expected value, type, relationship, or exception."
    }
  ]
}
```

### Top-level fields

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `version` | string | Yes | Report schema version, currently `"1"` |
| `summary` | object | Yes | Counts for the complete visible result |
| `findings` | array | Yes | Ordered visible findings |
| `warnings` | array of strings | No | Parse or incomplete-analysis warnings |

### Summary fields

| Field | Type | Meaning |
| --- | --- | --- |
| `files_scanned` | integer | Eligible changed files examined |
| `finding_count` | integer | Visible findings after suppression |
| `suppressed_count` | integer | Deduplicated findings removed by fingerprint policy |
| `by_severity.low` | integer | Visible low findings |
| `by_severity.medium` | integer | Visible medium findings |
| `by_severity.high` | integer | Visible high findings |

### Finding fields

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `rule_id` | string | Yes | Stable rule integration key |
| `title` | string | Yes | Short finding title |
| `message` | string | Yes | Scope-specific explanation |
| `severity` | string | Yes | `low`, `medium`, or `high` |
| `confidence` | string | Yes | `low`, `medium`, or `high` |
| `path` | string | Yes | Repository-relative forward-slash path |
| `line` | integer | Yes | One-based start line |
| `column` | integer | Yes | One-based start column |
| `end_line` | integer | No | One-based inclusive end line |
| `fingerprint` | string | Yes | Deterministic 24-character hex value |
| `evidence` | string | No | Relevant before or after syntax |
| `remediation` | string | No | Suggested review or correction |
| `help_uri` | string | No | Rule-specific documentation URL |

Consumers should ignore unknown fields for forward compatibility and reject an
unsupported top-level schema version.

## SARIF 2.1.0

Select SARIF with `--format sarif`:

```bash
testseal scan --format sarif --output testseal.sarif
```

The document uses:

- tool driver name `TestSeal`;
- package version in `semanticVersion`;
- one rule descriptor per rule present in the result;
- `error`, `warning`, and `note` levels for high, medium, and low severity;
- repository-relative artifact URIs;
- one-based source regions;
- `testseal/v1` partial fingerprints;
- invocation properties containing the report summary;
- tool execution notifications for parse warnings.

An empty scan still contains a valid run, invocation, summary, and empty results
array.

## Fingerprints

A fingerprint identifies one normalized finding. It is derived from rule,
normalized path, scope-bearing message, evidence, and internal context needed to
distinguish repeated fallback findings. It does not include an absolute local
path.

Fingerprints support review suppressions and SARIF correlation. They are stable
for an unchanged finding input, but a meaningful source, scope, or matcher
change can produce a new value. Do not use fingerprints as security tokens or
global database identifiers.

## Warnings and incomplete scans

Warnings indicate that one or more changed Python versions could not receive
complete AST analysis. In advisory mode, results and warnings are returned with
exit code `0` unless the threshold is reached for another finding. In blocking
mode, any parse warning returns `2`.

Automation should display warnings and retain the report even when the process
fails.
