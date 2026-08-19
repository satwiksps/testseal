---
description: Select the correct TestSeal input mode for local work, hooks, and CI.
---

# Choose a scan mode

TestSeal accepts exactly one source mode. The default reads working-tree
changes. `--base`, `--staged`, and `--diff` are mutually exclusive.

| Mode | Command | Best use |
| --- | --- | --- |
| Working tree | `testseal scan` | Local edits before staging |
| Staged index | `testseal scan --staged` | pre-commit and manual staged checks |
| Git revisions | `testseal scan --base BASE --head HEAD` | Pull requests and branch review |
| Unified diff | `testseal scan --diff PATH` | External systems and archived patches |

## Working-tree mode

```bash
testseal scan
```

The scan compares tracked files with `HEAD` and treats non-ignored untracked
files as additions. Git ignore rules are respected. Use this mode while editing
because it does not require staging.

You can compare the working tree to a different head revision:

```bash
testseal scan --head feature-snapshot
```

`--head` cannot be combined with `--staged` or `--diff`.

## Staged mode

```bash
testseal scan --staged
```

The scan compares the Git index with `HEAD`. Unstaged changes are not included.
This makes the result match the content that the next commit would contain.

The bundled pre-commit hook uses staged mode and sets `pass_filenames: false` so
TestSeal can inspect the complete staged diff once.

## Revision mode

```bash
testseal scan --base origin/main --head HEAD
```

TestSeal resolves the merge base between `--base` and `--head`, then compares
that merge base with the head revision. If `--head` is omitted, it defaults to
`HEAD`.

Revision mode is preferred in CI because TestSeal can hydrate both complete
file versions. Ensure the checkout contains both revisions. A shallow checkout
often lacks the base commit.

### GitHub pull requests

The GitHub Action derives exact base and head SHAs from `pull_request` and
`merge_group` event payloads when the inputs are omitted. A full checkout is
still required:

```yaml
- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
  with:
    fetch-depth: 0
```

## Unified-diff mode

Read a UTF-8 patch from a file:

```bash
testseal scan --diff changes.patch
```

Read from standard input:

```bash
git diff origin/main...HEAD | testseal scan --diff -
```

This mode validates unified hunk counts and rejects truncated input. It cannot
recover syntax outside included hunks, so semantic rules can be more
conservative and parse warnings can occur. Prefer Git-backed modes when the
repository is available.

## Path selection

Positional paths narrow the selected Git changes:

```bash
testseal scan --base origin/main --head HEAD tests/unit services/billing
```

Use `--` before paths that could be read as options:

```bash
testseal scan --staged -- tests/unit
```

After Git path selection, TestSeal applies `include`, `exclude`, and
`test_patterns`. A file omitted by configuration cannot be restored by a CLI
path argument.

## Choosing for automation

| Environment | Recommended mode |
| --- | --- |
| Developer command | Working tree |
| pre-commit | Staged |
| Pull request CI | Revision |
| Merge queue | Revision |
| Patch intake service | Unified diff |
| Scheduled branch audit | Revision |
