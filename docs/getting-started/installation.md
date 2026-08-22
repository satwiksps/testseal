---
description: Install TestSeal from PyPI with pip, uv, or pipx.
---

# Installation

TestSeal requires Python 3.11 or newer. Git is required for working-tree,
staged, and revision scans. A saved unified diff can be scanned without a Git
repository.

## Install as a project tool

Use this option when TestSeal belongs in the repository's development
environment:

=== "pip"

    ```bash
    python -m pip install testseal
    ```

=== "uv"

    ```bash
    uv add --dev testseal
    ```

=== "Poetry"

    ```bash
    poetry add --group dev testseal
    ```

=== "PDM"

    ```bash
    pdm add --dev testseal
    ```

Pin the version in applications and shared CI images so policy changes are
reviewed with dependency updates.

## Install as an isolated command

Use an isolated installation when TestSeal should not share dependencies with
the target project. The Python package has no runtime dependencies.

=== "uv tool"

    ```bash
    uv tool install testseal
    ```

=== "pipx"

    ```bash
    pipx install testseal
    ```

Run without a persistent installation:

```bash
uvx testseal demo
```

## Verify the installation

```bash
testseal --version
testseal scan --help
testseal demo
```

The commands should print the installed version, list the scan options, and
report one `TS003` finding from the built-in example. If the
shell cannot find `testseal`, run it through the interpreter used for
installation:

```bash
python -m testseal --version
```

## Upgrade

=== "pip"

    ```bash
    python -m pip install --upgrade testseal
    ```

=== "uv tool"

    ```bash
    uv tool upgrade testseal
    ```

=== "pipx"

    ```bash
    pipx upgrade testseal
    ```

Read the [release notes](../project/release-notes.md) before upgrading a
blocking installation. Rule IDs retain their documented meaning, but matching
precision, messages, and evidence can improve between releases.

## Uninstall

=== "pip"

    ```bash
    python -m pip uninstall testseal
    ```

=== "uv tool"

    ```bash
    uv tool uninstall testseal
    ```

=== "pipx"

    ```bash
    pipx uninstall testseal
    ```

TestSeal does not create a global account or send telemetry. Local report files
and repository configuration remain under the repository owner's control.

## Next step

Continue with [your first scan](first-scan.md).
