# TestSeal GitHub Action

This package contains the TypeScript adapter and committed Node 24 bundle for
the repository-root TestSeal Action. Detection remains in the Python core. The
adapter installs the core bundled with the same release, launches it without a
shell, converts findings into source annotations, preserves scan warnings, and
exposes normalized outputs.

```yaml
name: Test integrity

on: [pull_request]

permissions:
  contents: read

jobs:
  testseal:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: '3.12'
      - id: testseal
        uses: satwiksps/testseal@e6bba7e933c37afc34e2836ac2b1baee7542bfe5 # v1.0.0
        with:
          fail-on: high
```

On `pull_request` and `merge_group`, omitted refs are derived from GitHub's
event context. `fetch-depth: 0` is still required so both commits exist in the
checkout. Outside those events, omitted refs scan working-tree changes.

Leave `fail-on` unset to honor repository configuration. With neither setting,
the scan remains advisory. `paths` accepts one path per line. `python-command`
must be an executable name or absolute path, not a shell command.

The default `install: true` installs only the root Python project bundled with
the pinned Action release. Set `install: false` only if a matching TestSeal is
already installed. The Action fails closed if its bundled source is missing.

Outputs: finding and severity counts, files scanned, suppressed fingerprint
count, normalized outcome, and the complete JSON report.

## Development

Use Node.js 24 or newer:

```shell
npm ci
npm run verify
```

`npm run verify` formats, lints, type-checks, runs coverage, and rebuilds the
minified `dist/index.js` plus third-party `dist/licenses.txt`. Both generated
files must be committed whenever runtime source or dependencies change.
