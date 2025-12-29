# Rule reference

TestSeal rules report evidence about a diff. They do not infer whether a change
was malicious, AI-generated, or incorrect. Released rule IDs are integration
keys and retain their documented meaning.

## Severity, confidence, and policy

Severity describes the potential review impact of a matched transformation;
it is not a probability that the change is wrong. Confidence is communicated by
the rule's matching scope and documentation. The CLI remains advisory
unless `fail_on` or `--fail-on` sets a threshold.

| Rule    | Default severity | Confidence |
| ------- | ---------------- | ---------- |
| `TS001` | High             | High       |
| `TS002` | High             | High       |
| `TS003` | High             | High       |
| `TS004` | High             | High       |
| `TS005` | High             | High       |
| `TS006` | Low              | Low        |
| `TS007` | Medium           | Medium     |
| `TS008` | Low              | Low        |

Rules can be disabled globally:

```toml
[tool.testseal]
disabled_rules = ["TS008"]
```

Or configured individually:

```toml
[tool.testseal.rules.TS001]
enabled = true
severity = "high"
```

For standalone `testseal.toml`, use `[testseal]` and
`[testseal.rules.TS001]` instead.

### Suppressing a reviewed finding

Every text and machine-readable finding includes a deterministic 24-character
fingerprint. After confirming that a specific finding is intentional, suppress
only that finding by adding its fingerprint to the project configuration:

```toml
[tool.testseal]
ignore_fingerprints = ["2ac578e72a8fb4a68d1b96f1"]
```

Fingerprints are case-insensitive in configuration and must contain exactly 24
hexadecimal characters. Suppression is applied after duplicate findings are
collapsed. Reports include the number of suppressed findings so an ignored
signal does not disappear without an audit trail. Prefer this narrow mechanism
over disabling a rule when the rule remains useful elsewhere in the project.

## `TS001`: assertion removed

**Signal:** an assertion present in a test's before-version has no corresponding
assertion in the same lexical scope after the change.

**Supported:** Python `assert`; common `unittest.TestCase` equality, identity,
type, ordering, membership, regex, collection, exception, warning, and logging
assertions; `pytest.raises`; and mock `assert_called*` / `assert_awaited*` calls.
Identical assertions are matched as a multiset, so reordering them within a
function does not create a finding.

**Intentional non-findings:** editing an expected value, making a semantically
plausible replacement over the same subject, or reordering unchanged assertions
is not reported as removal. A replacement may be evaluated separately by
`TS003`. An unrelated new assertion does not stand in for a deleted obligation
merely because the total assertion count stayed constant.

**Limits:** custom assertion APIs, validation hidden in helper functions, and
framework-specific matchers are not inventoried. Moving an assertion into a
different function looks like removal from the original scope. When complete
before/after source is unavailable, patch-only analysis is deliberately more
conservative.

## `TS002`: test skipped or expected to fail

**Signal:** a disabling marker or call is added, prepended, moved to another
location or test scope, or given a different condition.

**Supported:** `pytest.mark.skip`, `skipif`, and `xfail`; `pytest.skip` and
`pytest.xfail`; `self.skipTest`; and unittest `skip`, `skipIf`, `skipUnless`, and
`expectedFailure`. `import pytest as ...`, `from pytest import mark as ...`, and
directly imported pytest `skip` / `xfail` aliases are resolved.

**Intentional non-findings:** changing only a `reason` while preserving the
marker, condition, scope, and placement is treated as documentation, not a new
skip. Unchanged markers are matched before added ones, so prepending a duplicate
cannot hide behind an existing marker.

**Limits:** project wrapper decorators, dynamically constructed markers, and
indirect alias assignments are not resolved. TestSeal compares condition syntax;
it does not evaluate whether a condition is true on a particular runner.

## `TS003`: assertion weakened

**Signal:** a precise assertion is replaced in the same lexical scope by a
truthiness, falsiness, or non-null assertion over the same subject, or by an
obvious syntactic tautology.

**Supported:** Python comparisons and `isinstance` / `issubclass`, plus common
unittest equality, identity, type, ordering, and membership methods. Equivalent
predicate forms are canonicalized: for example,
`assertEqual(actual, expected)` to `assertTrue(actual == expected)` is not a
finding. Replacements such as equality to truthiness, type checking to
truthiness, or `assertEqual(value, value)` are findings.

**Intentional non-findings:** strengthening an assertion, changing an expected
value, or changing between equally precise predicates is not classified as
weakening.

**Limits:** the rule does not perform theorem proving, data-flow alias analysis,
or domain-specific matcher reasoning. Expression reshaping and custom assertion
libraries can therefore produce false negatives. Pairing is local to a lexical
scope and favors semantic subject identity and diff proximity.

## `TS004`: tolerance widened

**Signal:** a literal numeric tolerance becomes less strict: `rel`, `abs`,
`rel_tol`, `abs_tol`, `rtol`, `atol`, or `delta` increases, or unittest `places`
decreases.

**Supported:** numeric literals, including signed and scientific notation, in
keyword arguments; `places` is also recognized as the third positional argument
of `assertAlmostEqual` and `assertNotAlmostEqual`. Calls are paired using their
scope, callable, non-tolerance arguments, and diff location. Unchanged
tolerances are removed before pairing so an inserted assertion does not shift
the comparison set.

**Intentional non-findings:** unchanged or tighter tolerances, newly inserted
approximate assertions, and symbolic values such as `DEFAULT_TOLERANCE` are not
reported.

**Limits:** TestSeal does not evaluate constants, arithmetic expressions, or
framework-specific positional tolerance conventions. It reports the syntactic
widening and cannot decide whether the new precision is justified.

## `TS005`: exception swallowed

**Signal:** a new bare, `Exception`, `BaseException`, or
`builtins.Exception` handler can fall through without a direct validation or
re-raise. Tuples containing a recognized broad type are included.

**Supported:** a top-level `raise`, non-tautological Python `assert`, known
unittest/mock assertion call, `pytest.fail`, or `self.fail` makes a straight-line
handler safe. A conditional assertion or raise does not hide a swallowing path;
neither do `assert True`, `assertTrue(True)`, or an obvious self-equality.

**Intentional non-findings:** narrow exception handlers and broad handlers with
a statically visible, unconditional validation or re-raise are not reported.

**Limits:** this is intentionally not a full control-flow proof. Custom failure
helpers, exception aliases/subclasses, and validation performed indirectly are
not inferred. Legitimate cleanup or best-effort diagnostic handlers may still
need a local suppression or review explanation.

## `TS006`: snapshot regeneration enabled

**Signal:** an added line enables a recognized snapshot update mechanism, or a
`.snap`, `.snapshot`, or `__snapshots__` artifact changes.

**Supported:** `--snapshot-update`; enabled assignments or calls using
`snapshot_update` / `update_snapshots`; `snapshot.update(...)`;
`accept_snapshot(...)`; and snapshot calls with `update=True`. Explicit false
assignments such as `snapshot_update = False` are not described as enabling
updates.

**Intentional non-findings:** ordinary snapshot assertions and disabled update
flags are ignored. Artifact findings are emitted once per changed snapshot file,
not once per changed line.

**Limits:** this low-confidence rule uses conservative line patterns rather than
framework-specific configuration parsers. It can match text in comments or
strings and can miss custom update mechanisms. It is advisory by design.

## `TS007`: subject under test mocked

**Signal:** a newly introduced patch target shares meaningful name tokens with
the enclosing `test_*` function, suggesting that the test may have mocked the
behavior named by the test itself.

**Supported:** `patch`, `mock.patch`, `unittest.mock.patch`, their
`patch.object` variants, `mocker.patch` / `mocker.patch.object`, and
`monkeypatch.setattr`-style calls. For object patches, the object and attribute
name are combined before matching. A boundary target such as `http.request` in
`test_process_payment` has no overlap and is not reported.

**Intentional non-findings:** existing mocks and added mocks whose target name
does not overlap the test name are ignored. Mocking clocks, networks, storage,
and similar boundaries is expected to remain quiet when names are distinct.

**Limits:** this medium-confidence rule is a naming heuristic, not call-graph or
import resolution. Dynamic targets, aliases, generic test names, and coincidental
token overlap can cause misses or noise. Keep it advisory unless a repository's
naming conventions make the signal reliable.

## `TS008`: source and guarding test co-edited

**Signal:** a changed source path and a configured or inferred guarding-test
path are both present in the same diff.

**Posture:** context only and advisory. Healthy pull requests routinely update
code and tests together. The signal becomes useful when combined with a more
specific weakening finding, or in workflows that deliberately separate
test-authoring and implementation agents. It should not be treated as a defect
on its own.

Use `source_roots`, `test_patterns`, and `guarding_tests` configuration to make
project relationships explicit where supported.

## Reporting rule problems

A useful false-positive or false-negative report contains:

1. Minimal before and after Python source.
2. The exact TestSeal revision and rule ID.
3. The command and relevant configuration.
4. Why the change is legitimate or why a risky change was missed.

Remove proprietary names and data before publishing a fixture.
