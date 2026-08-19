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

TestSeal uses semantic version tags such as `v0.1.0`. During 0.x development:

- rule IDs retain their documented signal meaning;
- the JSON report declares an independent schema version;
- matcher precision, messages, and evidence can improve in minor releases;
- public package-root Python exports are supported, while internal modules can
  change;
- Action and Python core versions are released together.

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

- version agreement between the tag, package, module, Action package, and
  changelog;
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
