---
description: Run TestSeal against staged changes with pre-commit.
---

# pre-commit

The bundled hook installs TestSeal in an isolated Python environment and scans
the complete staged diff once.

## Add the hook

Add this entry to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/satwiksps/testseal
    rev: v1.0.0
    hooks:
      - id: testseal
```

Install the Git hook:

```bash
python -m pip install pre-commit
pre-commit install
```

The next commit runs:

```bash
testseal scan --staged
```

The hook uses `pass_filenames: false` because TestSeal needs one coherent Git
diff rather than a separate invocation per file.

## Configure blocking

Keep the threshold in `testseal.toml` so manual, pre-commit, and CI scans use the
same policy:

```toml
[testseal]
fail_on = "high"
```

Or set hook-specific arguments:

```yaml
repos:
  - repo: https://github.com/satwiksps/testseal
    rev: v1.0.0
    hooks:
      - id: testseal
        args: ["--fail-on", "high"]
```

The argument overrides repository configuration for the hook only.

## Use a nonstandard config path

```yaml
hooks:
  - id: testseal
    args: ["--config", "config/testseal.toml"]
```

Paths are resolved from the repository root because pre-commit runs repository
hooks there.

## Run manually

Stage the intended changes first, then invoke the hook:

```bash
git add tests/test_invoice.py
pre-commit run testseal --hook-stage pre-commit
```

`pre-commit run --all-files` still invokes TestSeal's staged scan. The hook does
not synthesize changes for unchanged files, so use an actual staged diff when
validating detection.

## Update the hook

Change `rev` through a reviewed dependency update or run:

```bash
pre-commit autoupdate --repo https://github.com/satwiksps/testseal
```

Read the [release notes](../project/release-notes.md), then commit the updated
configuration. Do not use a moving branch such as `main` for shared hooks.

## Bypass and recovery

pre-commit supports `SKIP=testseal` and `git commit --no-verify`. These are
developer escape hatches, not policy enforcement. Required CI should run
TestSeal again on the committed branch diff.

If the hook environment becomes stale:

```bash
pre-commit clean
pre-commit install --install-hooks
```

If installation fails behind a restricted network, preinstalling the PyPI
package does not satisfy the isolated hook environment. Configure the approved
package index for pre-commit's Python installation process.
