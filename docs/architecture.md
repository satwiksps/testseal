---
description: TestSeal components, analysis pipeline, trust boundary, and configuration precedence.
---

# Architecture

TestSeal has one deterministic detection engine and three delivery surfaces:

```text
terminal -----\
pre-commit ----> Python CLI/core ----> text / JSON / SARIF
GitHub Action -/        ^
                       |
                TypeScript adapter
```

The TypeScript Action installs the Python core bundled with the same release,
invokes it without a shell, interprets documented exit codes, and translates
findings into GitHub annotations and outputs. It does not reimplement detection
logic. A given diff and configuration should produce the same findings locally
and in CI.

## Analysis pipeline

### 1. Select input

The CLI accepts one mode:

- Working-tree changes (default), including non-ignored untracked files.
- Staged changes through `--staged`.
- Git revisions through `--base` and optional `--head`.
- A unified-diff file or standard input through `--diff`.

Path arguments and configuration then narrow the eligible files. Git-backed
modes are authoritative because they hydrate complete before/after file
contents. Standalone unified diffs contain only hunks, so rules needing omitted
context may not run; malformed or truncated hunk counts are rejected, and
incomplete syntax analysis is exposed through report warnings.

### 2. Normalize changes

Git metadata and unified hunks become `ChangedFile` records with normalized
paths, old/new source, and changed line ranges. Renames, additions, deletions,
quoted Unicode paths, and header-like source lines are handled explicitly.
Revision values beginning with option syntax are rejected before Git runs.

### 3. Decode and parse Python

Hydrated blobs honor UTF-8 BOMs and PEP 263 encoding cookies and normalize
newlines before AST parsing. Unreadable or undecodable content is an operational
error; it is never represented as an empty or deleted file.

The AST grammar comes from the Python interpreter running TestSeal. Invalid or
newer unsupported syntax produces a visible warning, not a fabricated semantic
finding. Advisory scans continue so a team can evaluate partial results; once a
`fail_on` threshold is configured, any parse warning fails closed with exit `2`.

### 4. Evaluate rules

Each rule receives normalized diff and syntax inventories and returns findings
through a shared model. Rules do not format output, write repository files,
call a model, or execute project code. Pairing is conservative: an added
assertion can replace a removed assertion only when their predicates or tested
subjects plausibly correspond.

Rule IDs are released integration keys. Messages, evidence, and precision may
improve, but an ID's meaning must not silently broaden.

### 5. Normalize findings

A finding carries:

- Rule ID, title, message, severity, and confidence.
- File and best available source location.
- Before/after evidence and remediation.
- A location-independent 24-hex fingerprint.

Fingerprint suppression is applied after deduplication. Suppressed findings do
not affect severity counts or thresholds, and their number remains visible in
the report summary.

### 6. Render and exit

Renderers produce text, JSON schema version `1`, or SARIF 2.1.0 without changing
the finding set.

| Exit | Meaning |
| --- | --- |
| `0` | Scan completed and the configured threshold was not reached |
| `1` | At least one visible finding reached the configured threshold |
| `2` | Usage, configuration, Git, decoding, incomplete blocking scan, or I/O error |

The default `fail_on = "never"` is advisory. The GitHub Action reports warning-
only advisory scans as `incomplete` while retaining their normalized output.

## Configuration precedence

From highest to lowest:

1. CLI flags.
2. An explicit `--config` file.
3. A discovered `testseal.toml`.
4. Discovered `[tool.testseal]` in `pyproject.toml`.
5. Conservative built-in defaults.

A standalone file uses `[testseal]`. Unknown keys, rule IDs, severities, and
malformed fingerprints are errors rather than silent no-ops.

## Trust boundary

Pull-request contents are untrusted input. Analysis may invoke Git to obtain
content, but it must not import the target project, load pytest plugins,
evaluate decorators, run tests, or execute configuration. TOML is data. Report
fields derived from source must be escaped by downstream HTML or command
consumers.

The recommended workflow uses `pull_request`, `contents: read`, a full checkout,
and no secrets. `pull_request_target` with an untrusted head checkout is outside
the supported threat model.

## Repository boundaries

```text
pyproject.toml             Python distribution metadata and CLI entry point
packages/testseal/         Python core, rules, renderers, and tests
packages/action/           TypeScript adapter and generated JavaScript bundle
site/                      Next.js, TypeScript, and Tailwind landing site
```

Repository-level files own configuration, CI, release automation, examples,
governance, and the self-installing pre-commit hook.
