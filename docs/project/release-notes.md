---
description: Find TestSeal release changes, artifacts, and upgrade guidance.
---

# Release notes

The authoritative changelog is
[`CHANGELOG.md`](https://github.com/satwiksps/testseal/blob/main/CHANGELOG.md).
Published artifacts and generated notes are available on
[GitHub Releases](https://github.com/satwiksps/testseal/releases). Python
distributions are published on [PyPI](https://pypi.org/project/testseal/).

## Versioning

TestSeal uses semantic version tags such as `v1.0.0`. Within the 1.x series:

- documented CLI options, configuration keys, package-root Python exports, and
  rule IDs remain compatible;
- the JSON report declares an independent schema version;
- matcher precision, messages, evidence, and fingerprints may change in minor
  releases without changing a rule's documented meaning;
- breaking changes to supported interfaces require a new major version;
- the Action and Python core are released together.

Review release notes before updating a blocking installation.

## Upgrade checklist

1. Read changes since the installed version.
2. Update the package, Action tag, and pre-commit revision together where used.
3. Run advisory scans against representative diffs.
4. Inspect new findings and changed fingerprints.
5. Rebuild the checked-in Action bundle only when contributing to TestSeal.
6. Re-enable required enforcement after policy review.

## Release integrity

The release workflow verifies:

- version agreement between the tag, Python package, module, Action package,
  website package, citation metadata, and changelog;
- the release commit is contained in `main`;
- Python tests, coverage, lint, formatting, package metadata, and wheel install;
- TypeScript Action tests, coverage, formatting, types, and committed bundle;
- landing site verification;
- consumer Action installation;
- PyPI publication before the GitHub release is created.

GitHub release assets include Python distributions and SHA-256 checksums.

## Documentation versions

Read the Docs builds the current `main` branch as `latest`. Stable semantic
version tags are available as immutable documentation versions when activated
in the Read the Docs project.
