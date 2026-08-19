---
description: Complete TestSeal TOML configuration schema, defaults, and path semantics.
---

# Configuration reference

TestSeal configuration is strict. Unknown keys, rule IDs, severities, invalid
types, and malformed fingerprints return exit code `2`.

## File discovery

Without `--config`, TestSeal loads the first applicable source from the
repository root:

1. `testseal.toml` with a `[testseal]` table.
2. `pyproject.toml` with a `[tool.testseal]` table.
3. Built-in defaults.

An explicit `--config PATH` takes precedence. Explicit files can use a
`[testseal]` table, `[tool.testseal]`, or top-level TestSeal keys.

## Complete example

```toml
[testseal]
fail_on = "high"
include = ["*.py", "**/*.py", "*.snap", "**/*.snap"]
exclude = [".venv/**", "**/generated/**", "**/vendor/**"]
test_patterns = ["test_*.py", "*_test.py", "tests/**/*.py"]
source_roots = ["src", "packages"]
disabled_rules = ["TS008"]
ignore_fingerprints = ["2ac578e72a8fb4a68d1b96f1"]

[testseal.guarding_tests]
"src/billing/**/*.py" = ["tests/billing/**/*.py"]

[testseal.rules.TS006]
enabled = true
severity = "low"
```

## Top-level keys

### `fail_on`

**Type:** string  
**Values:** `"never"`, `"low"`, `"medium"`, `"high"`  
**Default:** `"never"`

Sets the lowest severity that returns exit code `1`. `never` keeps findings
advisory. CLI `--fail-on` overrides this value.

### `include`

**Type:** array of strings  
**Default:**

```toml
include = [
  "*.py",
  "**/*.py",
  "*.snap",
  "**/*.snap",
  "*.snapshot",
  "**/*.snapshot",
]
```

Only changed paths matching at least one include pattern are eligible. Include
patterns apply before test classification.

### `exclude`

**Type:** array of strings  
**Default:**

```toml
exclude = [
  ".git/**",
  ".venv/**",
  "venv/**",
  "node_modules/**",
  "build/**",
  "dist/**",
]
```

Any matching path is excluded even if it also matches `include`. Add generated,
vendored, fixture, and tool-output paths here.

### `test_patterns`

**Type:** array of strings  
**Default:**

```toml
test_patterns = [
  "test_*.py",
  "*_test.py",
  "tests/**/*.py",
  "test/**/*.py",
  "**/tests/**/*.py",
]
```

Eligible Python paths matching these patterns receive AST-based test analysis.
Other eligible paths can still receive artifact or co-edit analysis.

### `source_roots`

**Type:** array of strings  
**Default:** `["src", "lib", "app"]`

Identifies repository areas treated as source for co-edit context. Use
repository-relative directory names or path prefixes that match the project
layout.

### `guarding_tests`

**Type:** table from source glob to a string or array of test globs  
**Default:** empty table

Defines explicit source-to-test relationships for TS008:

```toml
[testseal.guarding_tests]
"src/payments/**/*.py" = [
  "tests/payments/**/*.py",
  "tests/integration/test_checkout.py",
]
```

The table does not run or select tests. It describes path relationships in the
changed file set.

### `disabled_rules`

**Type:** array of rule ID strings  
**Default:** empty array

Disables rules across the scan:

```toml
disabled_rules = ["TS008"]
```

Only `TS001` through `TS008` are accepted. A rule listed here remains disabled
even if its rule table sets `enabled = true`.

### `ignore_fingerprints`

**Type:** array of strings  
**Default:** empty array

Suppresses reviewed findings by deterministic fingerprint. Every entry must be
exactly 24 hexadecimal characters. Values are normalized to lowercase.

```toml
ignore_fingerprints = ["2ac578e72a8fb4a68d1b96f1"]
```

Suppressed findings do not affect counts or failure thresholds. Their number is
reported in `suppressed_count`.

### `rules`

**Type:** table keyed by rule ID  
**Default:** empty table

Each rule table accepts only `enabled` and `severity`:

```toml
[testseal.rules.TS007]
enabled = true
severity = "low"
```

#### `enabled`

**Type:** boolean  
**Default:** `true`

Enables or disables that rule.

#### `severity`

**Type:** string  
**Values:** `"low"`, `"medium"`, `"high"`  
**Default:** the rule's documented default

Overrides the emitted severity without changing match behavior or confidence.

## Path matching

Paths are normalized to repository-relative forward-slash form. Configuration
patterns follow Git-style expectations:

- relative patterns apply at any directory depth;
- `**/` matches zero or more directories;
- `tests/**/*.py` matches `tests/test_api.py` and nested test files;
- an exclude match takes precedence over an include match;
- matching is case-sensitive.

Use forward slashes in committed TOML on every operating system.

## Standalone and pyproject forms

=== "testseal.toml"

    ```toml
    [testseal]
    fail_on = "high"

    [testseal.rules.TS007]
    severity = "low"
    ```

=== "pyproject.toml"

    ```toml
    [tool.testseal]
    fail_on = "high"

    [tool.testseal.rules.TS007]
    severity = "low"
    ```

## Invalid configuration

TestSeal returns exit code `2` for errors such as:

```text
testseal: error: unknown configuration key: 'fail_level'
testseal: error: unknown rule id in disabled_rules: 'TS999'
testseal: error: invalid severity for rules.TS007
```

This behavior prevents a misspelled policy from silently falling back to a
weaker default.
