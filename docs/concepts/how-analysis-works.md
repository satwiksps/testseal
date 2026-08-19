---
description: Understand how TestSeal turns a Git diff into deterministic findings.
---

# How analysis works

TestSeal analyzes the change to a test, not only the final test file. Both sides
can be valid Python while the new side verifies less behavior.

## Diff-first analysis

Consider this change:

```diff
- assert response.status_code == 201
+ assert response.status_code
```

A linter sees a valid assertion in the new file. TestSeal compares the old and
new predicates in the same test scope, recognizes equality becoming truthiness,
and emits TS003.

The diff-first model also allows TestSeal to distinguish:

- an existing skip from a newly added skip;
- an unchanged broad handler from a newly swallowing handler;
- an existing mock from a newly introduced mock;
- a tight tolerance from one widened by the change;
- ordinary snapshot use from newly enabled snapshot regeneration.

## Git-backed hydration

For working-tree, staged, and revision scans, TestSeal asks Git for:

1. changed paths and unified hunks;
2. old blob content;
3. new blob or working-tree content;
4. rename, addition, and deletion metadata.

Complete file content enables Python AST parsing and lexical-scope matching.
Git object access does not execute project code.

## Path policy

The normalized changed files pass through three policy layers:

1. CLI positional paths narrow the Git query.
2. `include` and `exclude` select eligible changed files.
3. `test_patterns` identify Python files for semantic test analysis.

Eligible snapshot artifacts and source paths can still participate in TS006 and
TS008 even when they are not Python test files.

## Python parsing

TestSeal decodes Python source using UTF-8 BOM and PEP 263 encoding rules. It
normalizes newlines and parses with the AST grammar of the running Python
interpreter.

The parser builds inventories of assertions, skip markers, tolerance-bearing
calls, exception handlers, snapshot update signals, and mock targets. Aliases
are resolved only where the rule contract documents support.

TestSeal does not import the module. Decorators, constants, and dynamic code are
not evaluated.

## Before and after matching

Rules cancel unchanged records first. Remaining old and new records are paired
within lexical scope using rule-specific semantics such as predicate shape,
tested subject, callable, non-tolerance arguments, and diff proximity.

Pairing is conservative. An unrelated new assertion cannot replace a removed
assertion merely because the assertion count stayed constant.

## Findings and deduplication

Every rule returns the same finding model:

- stable rule ID;
- title and scope-specific message;
- severity and confidence;
- normalized path and source region;
- evidence and remediation where available;
- deterministic fingerprint.

Equivalent findings are deduplicated. Fingerprint suppressions are then
applied. The final visible set drives counts and failure thresholds, while the
number removed remains in `suppressed_count`.

## Reporting

Text, JSON, and SARIF renderers consume the normalized result. They do not
rerun rules or change the finding set. This makes local text output and CI
machine reports comparable.

## Failure semantics

The threshold is applied after deduplication and suppression. A scan fails with
exit code `1` only when a visible finding reaches the threshold.

An operational or policy error returns `2`. Parse warnings are allowed in
advisory mode but return `2` when a threshold is active, because blocking on a
partial analysis would fail open.

Continue with the [architecture](../architecture.md) for component boundaries
and the [rule reference](../rules.md) for exact match contracts.
