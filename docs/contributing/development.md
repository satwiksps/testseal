---
description: Set up a TestSeal development environment and run repository verification.
---

# Development setup

TestSeal is a monorepo with a Python analyzer, TypeScript GitHub Action, and
Next.js landing site.

## Repository layout

```text
packages/testseal/   Python core and tests
packages/action/     TypeScript Action adapter and generated bundle
site/                Next.js and Tailwind landing site
docs/                MkDocs documentation sources
examples/            Configuration and diff examples
scripts/             Release and smoke-test utilities
```

## Clone

```bash
git clone https://github.com/satwiksps/testseal.git
cd testseal
```

## Python environment

Python 3.11 or newer is required. Python 3.12 is the primary development
version.

=== "POSIX"

    ```bash
    python3.12 -m venv .venv
    source .venv/bin/activate
    python -m pip install -e ".[dev]"
    ```

=== "Windows PowerShell"

    ```powershell
    py -3.12 -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install -e ".[dev]"
    ```

Run Python verification:

```bash
python -m ruff check packages/testseal/src packages/testseal/tests scripts
python -m ruff format --check packages/testseal/src packages/testseal/tests scripts
python -m pytest
python scripts/verify_example.py
```

Run branch coverage locally:

```bash
python -m pytest \
  --cov=testseal \
  --cov-branch \
  --cov-report=term-missing \
  --cov-fail-under=80
```

## GitHub Action

Node.js 24 or newer is required:

```bash
cd packages/action
npm ci
npm run verify
```

`npm run verify` checks formatting, lint, types, tests, coverage, and the
production bundle. Commit `dist/index.js` and `dist/licenses.txt` whenever
runtime source or dependencies change. CI rejects a stale bundle.

Do not edit files in `dist` directly.

## Landing site

```bash
cd site
npm ci
npm run verify
```

Use the environment variables documented in `site/.env.example` for local
metadata testing.

## Documentation

Install and serve the docs:

```bash
python -m pip install -r docs/requirements.txt
python -m mkdocs serve
```

The local site is available at `http://127.0.0.1:8000`. Run the strict build
before committing:

```bash
python -m mkdocs build --strict
```

The output goes to `.docs-site/`, not the Next.js `site/` directory.

## Build the Python distribution

```bash
python -m build
python -m twine check dist/*
```

Install and smoke-test the wheel in a clean environment before a release.

## Pre-commit

```bash
pre-commit install
pre-commit run --all-files
```

The TestSeal hook itself scans staged changes, so an all-files invocation does
not create a synthetic diff for detection tests.

## Change discipline

- Add focused regression tests for behavior changes.
- Keep rule matching deterministic and side-effect free.
- Preserve the trust boundary: do not import or execute target code.
- Update documentation and examples with public contract changes.
- Keep JSON schema compatibility or version the schema deliberately.
- Regenerate the Action bundle when its runtime changes.

Read [`CONTRIBUTING.md`](https://github.com/satwiksps/testseal/blob/main/CONTRIBUTING.md)
for commit, pull request, and review expectations.
