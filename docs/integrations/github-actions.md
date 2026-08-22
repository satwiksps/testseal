---
description: Add TestSeal annotations and policy enforcement to GitHub pull requests.
---

# GitHub Actions

The TestSeal Action installs the Python core bundled in the same release, scans
the pull request diff, creates source annotations, and exposes normalized
outputs. Detection remains in the Python core.

## Complete workflow

Create `.github/workflows/testseal.yml`:

```yaml
name: Test integrity

on:
  pull_request:
  merge_group:

permissions:
  contents: read

jobs:
  testseal:
    name: TestSeal
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
          persist-credentials: false
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: "3.12"
      - id: testseal
        uses: satwiksps/testseal@89a2ab087ad1b93b6cf26ef2851dc44d8712fc02 # v0.1.0
        with:
          fail-on: high
```

`fetch-depth: 0` ensures the base and head commits are available. On
`pull_request` and `merge_group`, the Action derives exact revision SHAs from
the event payload when `base` and `head` are omitted.

## Keep policy in the repository

For one policy shared by local and CI runs, omit `fail-on` from the workflow and
set it in `testseal.toml`:

```toml
[testseal]
fail_on = "high"
```

An explicit Action `fail-on` input overrides repository configuration. Use an
override only when the workflow intentionally has different enforcement.

## Advisory rollout

For the first deployment, leave `fail-on` unset and keep the configuration at
`fail_on = "never"`. Findings appear as annotations, but the check succeeds.

After reviewing representative pull requests, change the repository threshold
to `high`. See the [adoption guide](../getting-started/adoption.md).

## Scan selected paths

The `paths` input accepts one repository path per line:

```yaml
- uses: satwiksps/testseal@89a2ab087ad1b93b6cf26ef2851dc44d8712fc02 # v0.1.0
  with:
    paths: |
      services/billing
      libraries/money
```

Paths narrow the Git diff. Repository include and exclude policy still applies.

## Use an explicit configuration

```yaml
- uses: satwiksps/testseal@89a2ab087ad1b93b6cf26ef2851dc44d8712fc02 # v0.1.0
  with:
    config: config/testseal-strict.toml
```

The path is resolved in the checked-out repository.

## Use an existing installation

The default `install: true` installs source bundled with the Action release. It
does not download TestSeal from PyPI. This keeps the Action adapter and Python
core at the same version.

If a controlled runner image already contains the matching version:

```yaml
- uses: satwiksps/testseal@89a2ab087ad1b93b6cf26ef2851dc44d8712fc02 # v0.1.0
  with:
    install: false
    python-command: /opt/testseal/bin/python
```

`python-command` must be an executable name or absolute path. It is not passed
through a shell and cannot contain command-line flags.

## Consume outputs

```yaml
- id: testseal
  uses: satwiksps/testseal@89a2ab087ad1b93b6cf26ef2851dc44d8712fc02 # v0.1.0

- name: Print TestSeal summary
  if: always()
  run: |
    echo "Outcome: ${{ steps.testseal.outputs.outcome }}"
    echo "Findings: ${{ steps.testseal.outputs.finding-count }}"
    echo "Suppressed: ${{ steps.testseal.outputs.suppressed-count }}"
```

The complete output contract is in the [Action reference](../reference/action.md).

## Fork safety

Use the `pull_request` event with read-only `contents` permission. TestSeal does
not need repository secrets. Avoid `pull_request_target` with an untrusted head
checkout because that event can grant trusted-context permissions to
contributor-controlled code.

The Action invokes the bundled Python package without a shell. The core reads
Git content and parses Python without importing or executing the changed
project.

## Pinning policy

An immutable commit SHA provides the strongest workflow pin. A release tag is
easier to read and is protected against modification in the TestSeal repository.
Choose according to the repository's dependency policy and let Dependabot track
GitHub Action updates.

## Required check

After advisory rollout and baseline review:

1. Set a blocking `fail_on` threshold.
2. Merge a workflow run on the default branch.
3. Add the `TestSeal` job as a required status check in branch rules.
4. Keep configuration and workflow files under code-owner review.

Do not require the check before a successful default-branch run has created the
status context.
