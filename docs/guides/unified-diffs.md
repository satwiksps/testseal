---
description: Audit unified diff files and standard input when Git objects are unavailable.
---

# Scan a saved diff

Unified-diff mode is designed for patch archives, review services, and systems
that cannot provide the original Git repository.

## Create and scan a patch

```bash
git diff --binary origin/main...HEAD > changes.patch
testseal scan --diff changes.patch
```

Read from standard input:

```bash
git diff origin/main...HEAD | testseal scan --diff -
```

Write JSON output while reading the patch from standard input:

```bash
git diff origin/main...HEAD | \
  testseal scan --diff - --format json --output testseal-report.json
```

## What the parser accepts

TestSeal reads ordinary Git-style unified diffs with:

- multiple files and multiple hunks;
- additions, deletions, and renames;
- quoted Git paths, including UTF-8 octal escapes;
- `---` and `+++` file headers;
- exact old and new hunk counts.

Malformed or truncated hunk counts return exit code `2`. This prevents a
damaged patch from looking like a complete clean scan.

## Analysis differences

A unified diff contains changed lines and limited context. It usually does not
contain complete Python functions or modules. TestSeal therefore uses
conservative hunk-based fallbacks when complete syntax cannot be reconstructed.

Consequences:

- rules that depend on lexical scope can produce fewer findings;
- a syntax warning can appear for an incomplete reconstructed file;
- precise assertion pairing may be unavailable;
- snapshot artifact checks still work from paths and changed lines.

Git-backed modes hydrate complete file versions and should be preferred when Git
objects are available.

## Blocking behavior

In advisory mode, parse warnings remain visible and the scan can return `0`.
When `fail_on` or `--fail-on` enables blocking, any parse warning returns `2`.
This prevents partial analysis from passing a required integrity check.

## Secure patch intake

- Limit patch size before invoking TestSeal in a public service.
- Run in a temporary working directory with ordinary filesystem restrictions.
- Treat report text derived from source as untrusted when rendering HTML.
- Do not execute the patch or install its project dependencies.
- Retain stderr and exit code `2` as operational failures.

TestSeal itself parses the patch as data and does not execute changed code.
