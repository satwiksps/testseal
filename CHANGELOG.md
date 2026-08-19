# Changelog

TestSeal follows [Semantic Versioning](https://semver.org/). This file records
changes that affect users; routine dependency and repository-maintenance work
is omitted unless it changes installation or runtime behavior.

## [Unreleased]

### Changed

- Release automation now confirms that a published wheel is available from
  PyPI before creating the corresponding GitHub release.

### Added

- A complete MkDocs Material documentation site for Read the Docs, including
  installation, adoption, integrations, configuration, output schemas,
  security, troubleshooting, and contributor references.
- Strict documentation builds in CI and canonical documentation links in
  package metadata, SARIF rule help, the README, and the landing site.

## [0.1.0] - 2026-08-16

### Added

- Deterministic analysis of Python and pytest diffs through rules `TS001` to
  `TS008`, covering removed or weakened assertions, disabled tests, widened
  tolerances, swallowed exceptions, snapshot updates, suspicious mocks, and
  coupled source/test changes.
- Working-tree, staged, explicit-ref, merge-base, and unified-diff scan modes.
- Text, versioned JSON, and SARIF 2.1.0 reports with stable finding
  fingerprints and reviewed-finding suppression.
- Strict TOML policy, per-rule severity overrides, path filters, and opt-in
  failure thresholds.
- A self-installing pre-commit hook and a bundled Node 24 GitHub Action.
- Cross-platform CI for Python 3.11 through 3.14, package verification, and a
  Vercel-hosted project site.

### Security

- Analysis reads Git data and parses source without importing or executing the
  repository under review.
- The Action invokes Python without a shell and installs only the source
  bundled in the selected TestSeal revision.
- Release automation validates package metadata and publishes artifact
  checksums.

[Unreleased]: https://github.com/satwiksps/testseal/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/satwiksps/testseal/releases/tag/v0.1.0
