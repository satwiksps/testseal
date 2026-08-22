# Changelog

TestSeal follows [Semantic Versioning](https://semver.org/). This file records
changes that affect users; routine dependency and repository-maintenance work
is omitted unless it changes installation or runtime behavior.

## [Unreleased]

## [1.0.0] - 2026-08-22

### Added

- `testseal demo`, an offline and configuration-independent installation check
  that runs the real analyzer against a bundled assertion-weakening diff.
- The MkDocs Material documentation site for installation, adoption,
  integrations, configuration, report schemas, security, and troubleshooting.

### Changed

- The documented CLI, configuration, package-root Python API, rule IDs, and
  versioned JSON report are now the supported 1.x compatibility surface.
- CLI report files are replaced atomically, malformed or incomplete unified
  diffs fail clearly, and direct `Config` construction validates resolved
  values.
- The GitHub Action derives pull-request and merge-queue revisions, accepts
  only valid schema-version 1 reports, and leaves summary outputs unset on
  report errors.

### Fixed

- Git diff parsing now handles added and deleted binary files without reading
  nonexistent blobs and honors an explicit worktree `--head` baseline.
- Production website builds now publish the canonical URL and release version.

### Security

- Action reports reject unsafe annotation paths, invalid fingerprints, and
  inconsistent summary counts before any finding output is emitted.
- Release validation covers Python, Action, website, citation, and changelog
  versions; publication is confirmed on PyPI before the GitHub release is
  created.

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
- CI for Python 3.11 through 3.14 on Linux and Python 3.12 on Windows and macOS,
  package verification, and a Vercel-hosted project site.

### Security

- Analysis reads Git data and parses source without importing or executing the
  repository under review.
- The Action invokes Python without a shell and installs only the source
  bundled in the selected TestSeal revision.
- Release automation validates package metadata and publishes artifact
  checksums.

[Unreleased]: https://github.com/satwiksps/testseal/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/satwiksps/testseal/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/satwiksps/testseal/releases/tag/v0.1.0
