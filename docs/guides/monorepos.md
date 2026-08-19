---
description: Configure TestSeal paths and guarding-test relationships in a Python monorepo.
---

# Configure a monorepo

Monorepos need explicit path policy. Start with repository-wide advisory
scanning, then narrow generated content and package relationships.

## Example layout

```text
services/
  billing/
    src/
    tests/
  identity/
    src/
    tests/
libraries/
  money/
    src/
    tests/
```

## Include repository package roots

```toml
[testseal]
fail_on = "never"
include = [
  "services/**/*.py",
  "libraries/**/*.py",
]
exclude = [
  "**/generated/**",
  "**/fixtures/**",
  "**/vendor/**",
]
test_patterns = [
  "**/tests/test_*.py",
  "**/tests/*_test.py",
]
source_roots = ["services", "libraries"]
```

Patterns use repository-relative forward-slash paths. A relative pattern also
matches at deeper directory levels. `**/` can match zero or more directories,
so `tests/**/*.py` includes `tests/conftest.py` and nested files.

## Define guarding tests for TS008

`TS008` reports when configured source and guarding-test paths are co-edited.
It is context only and low severity. Define relationships only where they are
meaningful:

```toml
[testseal.guarding_tests]
"services/billing/**/*.py" = ["services/billing/tests/**/*.py"]
"services/identity/**/*.py" = ["services/identity/tests/**/*.py"]
"libraries/money/**/*.py" = ["libraries/money/tests/**/*.py"]
```

A string is accepted for one guarding pattern:

```toml
[testseal.guarding_tests]
"libraries/dates/**/*.py" = "libraries/dates/tests/**/*.py"
```

Do not use TS008 as proof that a change is suspicious. Healthy changes normally
update source and tests together. The signal is useful as review context beside
a specific rule such as TS001 or TS003.

## Scan one package locally

```bash
testseal scan services/billing
```

Scan a package in branch CI:

```bash
testseal scan \
  --base origin/main \
  --head HEAD \
  services/billing
```

In the GitHub Action, `paths` is newline-delimited:

```yaml
with:
  paths: |
    services/billing
    libraries/money
```

## Use one policy unless boundaries require more

The CLI loads one configuration per invocation. Prefer a single root policy so
the same diff produces the same result locally and in CI. If packages require
different policies, run TestSeal once per package with an explicit config:

```bash
testseal scan --config services/billing/testseal.toml services/billing
testseal scan --config services/identity/testseal.toml services/identity
```

Each command has its own threshold and report. Choose distinct output paths for
machine-readable reports.

## Avoid common pattern errors

- Do not use absolute filesystem paths.
- Do not use backslashes in committed patterns.
- Keep generated and vendored files in `exclude`.
- Include source paths when TS008 is enabled.
- Keep `test_patterns` narrower than `include`.
- Test top-level and nested files because `**/` has zero-depth behavior.

The complete example is available at
[`examples/configs/monorepo.toml`](https://github.com/satwiksps/testseal/blob/main/examples/configs/monorepo.toml).
