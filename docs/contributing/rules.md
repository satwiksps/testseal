---
description: Design, implement, test, and document a TestSeal detection rule.
---

# Rule development

Rules are public contracts. A new matcher should provide a narrow,
deterministic signal with evidence a reviewer can verify from the diff.

## Start with a behavior contract

Before implementation, write:

1. **Signal:** the exact before and after transformation.
2. **Supported syntax:** concrete Python forms and resolved aliases.
3. **Intentional non-findings:** nearby changes that must remain quiet.
4. **Limits:** dynamic or semantic cases the matcher cannot prove.
5. **Severity:** review impact if the transformation is accurate.
6. **Confidence:** how directly syntax establishes the signal.

Avoid broad categories such as "bad test" or "AI slop." Rule output should be
usable without guessing intent or authorship.

## Prefer comparison over final-state linting

TestSeal's value comes from old and new syntax. An assertion that is weak in the
final file may be intentional and longstanding. A precise assertion that became
weak is a reviewable change.

Cancel unchanged records before pairing deleted and added records. Pair only
within plausible lexical scope and semantic subject. Do not let an unrelated
added assertion hide a removed one.

## Keep analysis safe

Rules may inspect normalized paths, diff hunks, decoded source, and Python AST
nodes. They must not:

- import the target project;
- evaluate AST expressions;
- execute decorators or configuration;
- run tests or hooks;
- call a model or network service;
- write to the target repository.

## Finding quality

Every finding needs:

- stable rule ID;
- concise title;
- scope-specific message;
- appropriate severity and confidence;
- best available path and source location;
- concrete evidence when available;
- actionable remediation.

Messages should state what changed. Avoid claims about malicious intent,
authorship, or correctness.

## Test matrix

Add focused cases for:

- canonical positive match;
- pytest and unittest forms where supported;
- imports and direct aliases;
- unchanged syntax;
- reordered syntax;
- equivalent replacement;
- strengthened replacement;
- nearby unrelated insertion;
- multiple lexical scopes;
- duplicate syntax and fingerprint separation;
- hydrated Git changes;
- unified-diff fallback where applicable;
- platform-independent paths and encodings.

Regression tests should reproduce the smallest source pair that failed.

## Precision before recall

Blocking tools lose trust when common refactors produce noise. Prefer a narrow
matcher with explicit limits over a broad heuristic. Context-heavy signals
should have lower confidence or severity and remain advisory by default.

## Rule ID policy

Released IDs are integration keys. Do not reuse an existing ID for a different
signal or silently broaden its meaning. A new rule requires the next available
ID, metadata, reporter integration, documentation, configuration validation,
and tests.

## Documentation checklist

- [ ] Add the rule to the summary table.
- [ ] Document signal, support, intentional non-findings, and limits.
- [ ] Update CLI or report examples if useful.
- [ ] Add SARIF help-link mapping.
- [ ] Add configuration examples only when the rule needs policy.
- [ ] Explain migration if an existing matcher changes materially.

Run the full Python test and coverage suite before submitting the change.
