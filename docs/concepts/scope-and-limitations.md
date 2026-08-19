---
description: What TestSeal analyzes, what it does not claim, and where findings need review.
---

# Scope and limitations

TestSeal is a narrow test-integrity analyzer. Clear boundaries make its output
more useful and prevent a finding from being treated as proof it cannot provide.

## In scope

- Changes to Python test files.
- Common pytest, unittest, and `unittest.mock` syntax.
- Added, removed, or replaced syntax visible in a Git or unified diff.
- Snapshot artifacts and common snapshot update signals.
- Configured source-to-test co-edit context.
- Deterministic text, JSON, and SARIF reports.
- Local, pre-commit, and CI execution.

## Out of scope

- Determining whether code was written by a person or an AI tool.
- Judging author intent or labeling a contributor as dishonest.
- Proving that a test suite is complete or correct.
- Running tests, mutation testing, or coverage analysis.
- Reviewing production implementation correctness.
- Detecting vulnerabilities in application code.
- JavaScript, TypeScript, Java, Go, Rust, or other test syntax.
- Custom assertion libraries without explicit rule support.
- Whole-program theorem proving or data-flow analysis.

## False positives

A correctly detected transformation can still be legitimate. Examples include
a removed requirement, documented platform skip, measured numerical tolerance,
or intentional snapshot regeneration. Severity describes review impact, not the
probability that the author is wrong.

Context-heavy rules such as TS006, TS007, and TS008 are kept at lower default
severity or confidence. Baseline them before blocking.

## False negatives

TestSeal can miss a weakening when it is expressed through:

- project-specific assertion helpers;
- dynamic alias assignment;
- generated decorators or calls;
- semantic changes hidden in helper functions;
- complex control flow;
- symbolic tolerances or runtime constants;
- incomplete unified-diff context;
- syntax newer than the running Python interpreter.

No clean result should be interpreted as proof that the tests are strong.

## Unified-diff limits

Patch-only analysis lacks complete before and after source. TestSeal uses
conservative fallbacks and validates hunk completeness, but rules needing
lexical context can be unavailable. Use Git-backed modes whenever possible.

## Python grammar

The AST parser uses the running interpreter. Run TestSeal with a Python version
at least as new as the syntax used by changed tests. A parse warning in blocking
mode returns exit code `2`.

## Fingerprint stability

Fingerprints are deterministic for the normalized finding inputs. A changed
scope, evidence string, matcher, or fallback context can change a fingerprint.
Suppressions should be reviewed during upgrades and code changes.

## Complementary controls

Use TestSeal beside:

- the project test suite;
- coverage and mutation testing;
- linting and type checking;
- ordinary code review;
- dependency and static security analysis;
- protected branches and reviewed policy changes.

Each control answers a different question. TestSeal answers whether the diff
contains a documented test-weakening signal.
