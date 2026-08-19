---
description: Roll out TestSeal without creating noisy or brittle repository policy.
---

# Adopt in a repository

A reliable rollout starts in advisory mode. TestSeal is intentionally strict
about configuration, but a valid finding can describe a legitimate change.

## Recommended rollout

### 1. Add a minimal configuration

Create `testseal.toml` at the repository root:

```toml
[testseal]
fail_on = "never"
test_patterns = ["test_*.py", "*_test.py", "tests/**/*.py"]
source_roots = ["src"]
disabled_rules = ["TS008"]
```

Use `[tool.testseal]` instead when policy belongs in `pyproject.toml`.

### 2. Run representative changes

Scan recent branches or saved diffs that contain:

- normal test refactors;
- legitimate skip and tolerance changes;
- assertion replacements;
- test fixtures and generated files;
- changes from automated coding tools;
- monorepo package boundaries, if applicable.

For each finding, check the exact rule scope in the [rule reference](../rules.md).
Record false positives with minimal before and after examples.

### 3. Tune paths before rules

Exclude generated tests, fixtures, vendored files, and snapshots that should not
be analyzed. Prefer precise `include`, `exclude`, and `test_patterns` over
disabling a rule across the whole repository.

```toml
[testseal]
exclude = ["tests/generated/**", "tests/fixtures/**", "vendor/**"]
```

### 4. Keep context-heavy rules advisory

`TS006`, `TS007`, and `TS008` need repository context. Their default severities
already reflect this. Do not raise their severity until repository naming and
test ownership conventions make the signal reliable.

### 5. Add CI without a threshold

Install the [GitHub Action](../integrations/github-actions.md) or run the CLI in
your existing CI. Leave `fail-on` unset so repository configuration remains the
single policy source.

### 6. Set the narrowest useful threshold

After the team has reviewed advisory results, set a repository threshold:

```toml
[testseal]
fail_on = "high"
```

This blocks high-severity findings while retaining medium and low findings for
review. Avoid `fail_on = "low"` unless every enabled rule has been baselined.

## Handling accepted findings

Use a fingerprint suppression for a reviewed, intentional instance:

```toml
[testseal]
ignore_fingerprints = ["2ac578e72a8fb4a68d1b96f1"]
```

A suppression applies only to that finding. Reports retain a suppressed count.
Add a code-review explanation beside the configuration change so future
maintainers can reassess it.

If an entire rule is inappropriate for the repository, disable it explicitly:

```toml
[testseal]
disabled_rules = ["TS008"]
```

See [review and suppress findings](../guides/triage.md) for the decision process.

## Policy ownership

Treat changes to these files as review-sensitive:

- `testseal.toml` or `[tool.testseal]`;
- pre-commit configuration;
- CI thresholds and path inputs;
- fingerprint suppressions;
- rule enablement and severity overrides.

For high-assurance repositories, add these paths to `CODEOWNERS` and require a
maintainer review for policy changes.

## Completion checklist

- [ ] File patterns match the repository layout.
- [ ] Generated and vendored paths are excluded.
- [ ] All enabled rules were exercised on representative diffs.
- [ ] Context-heavy rules remain advisory or have documented justification.
- [ ] CI uses a pinned TestSeal version or Action tag.
- [ ] Fork pull requests receive no repository secrets.
- [ ] Suppressions include a review explanation.
- [ ] The failure threshold is stored in repository configuration.
