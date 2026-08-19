---
description: Review TestSeal findings, handle false positives, and maintain suppressions.
---

# Review and suppress findings

A TestSeal finding is evidence about a change, not a verdict about the author or
the correctness of the patch. Triage should answer whether the reported
transformation is accurate and whether it is justified.

## Triage sequence

### 1. Confirm the changed code

Open the reported path and line in the new revision. Compare it with the old
revision and verify that the evidence belongs to the same lexical test scope.

### 2. Read the rule contract

Open the corresponding section in the [rule reference](../rules.md). Check:

- the exact signal;
- supported syntax;
- intentional non-findings;
- known precision limits;
- default severity and confidence.

### 3. Decide whether the change is justified

Common legitimate cases include:

- removing an assertion because the behavior no longer exists;
- skipping a test for a documented platform constraint;
- widening a tolerance to match a measured numerical bound;
- mocking a boundary whose name overlaps the test by coincidence;
- regenerating snapshots after reviewed output changes.

The author should explain the behavioral reason. A green test result alone does
not explain why a weaker obligation is correct.

### 4. Select the narrowest response

| Situation | Response |
| --- | --- |
| The finding identifies an accidental weakening | Restore or strengthen the test |
| The change is intentional and unique | Suppress the finding fingerprint |
| Generated or vendored content is being scanned | Exclude the path |
| A rule does not fit the repository | Disable or lower that rule |
| The matcher is wrong for supported syntax | Report a false positive |

## Suppress one finding

Copy the 24-character fingerprint from text, JSON, SARIF, or the Action output:

```toml
[testseal]
ignore_fingerprints = [
  "2ac578e72a8fb4a68d1b96f1",
]
```

Fingerprint values are case-insensitive in configuration and normalized to
lowercase. Every value must contain exactly 24 hexadecimal characters. An
invalid value causes exit code `2`.

Suppression occurs after findings are deduplicated. Suppressed findings do not
affect severity counts or thresholds, but reports include `suppressed_count`.

### Review suppressions over time

Treat the suppression list as policy, not as a cache:

1. Add each fingerprint in a reviewed change.
2. Record the reason in the pull request or an adjacent TOML comment.
3. Remove fingerprints when the underlying code changes.
4. Periodically inspect suppressions that no longer affect a scan.

TestSeal does not automatically remove stale fingerprints because configuration
edits should remain explicit.

## Change a rule policy

Disable a rule everywhere:

```toml
[testseal]
disabled_rules = ["TS008"]
```

Disable it through its rule table:

```toml
[testseal.rules.TS008]
enabled = false
```

Override a severity:

```toml
[testseal.rules.TS007]
severity = "low"
```

Do not use severity changes to conceal an unresolved false positive. Report
reproducible matcher problems so the rule can improve for every user.

## Report a rule problem

Open a [GitHub issue](https://github.com/satwiksps/testseal/issues/new/choose)
with:

1. Minimal before and after Python source.
2. TestSeal version and rule ID.
3. Exact command and relevant configuration.
4. Actual output.
5. Expected output and reasoning.

Remove proprietary names, credentials, and data before publishing a fixture.
Use [private vulnerability reporting](https://github.com/satwiksps/testseal/security/advisories/new)
when the report has security impact or cannot be safely disclosed.
