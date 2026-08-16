# Contributing to TestSeal

TestSeal is deliberately narrow: it reports concrete ways a Python test suite
became easier to pass. Contributions should preserve deterministic behavior,
offline operation, and the rule precision documented in `docs/rules.md`.

## Before opening a change

- Use an issue for new rule ideas or behavior that changes the public CLI,
  JSON schema, configuration, or Action inputs.
- Use the false-positive issue form when a valid test change is flagged. A
  minimal before/after diff is more useful than a full private repository.
- Report vulnerabilities privately as described in `SECURITY.md`.

Small documentation corrections and focused test additions do not need prior
discussion.

## Development setup

TestSeal requires Python 3.11 or newer. The Action uses Node.js 24.

```bash
git clone https://github.com/satwiksps/testseal.git
cd testseal
python -m venv .venv
python -m pip install -e ".[dev]"
```

Activate the virtual environment using the command for your shell, then run:

```bash
python -m ruff check packages/testseal/src packages/testseal/tests scripts
python -m ruff format --check packages/testseal/src packages/testseal/tests scripts
python -m pytest packages/testseal/tests --cov=testseal --cov-branch
python scripts/verify_example.py
```

For Action changes:

```bash
cd packages/action
npm ci
npm run verify
```

`npm run verify` rebuilds `packages/action/dist/index.js`. Commit the rebuilt
bundle and `dist/licenses.txt` when Action runtime code or dependencies change.

For website changes:

```bash
cd site
npm ci
npm run verify
```

## Rule changes

A rule change needs examples that show both sides of the boundary:

1. a weakening that must be reported;
2. a nearby legitimate change that must remain quiet;
3. aliases or common pytest/unittest spellings the rule claims to support;
4. stable rule ID, severity, location, evidence, and fingerprint behavior.

Prefer syntax-aware comparisons over broad text matching. If a case requires
data-flow, runtime values, or project-specific conventions, document that limit
instead of guessing.

## Pull requests

Keep each pull request focused. Explain the user-visible problem, the chosen
boundary, and any precision tradeoff. CI must pass on every supported Python
platform, the Action bundle must be current, and documentation must agree with
the shipped behavior.

By contributing, you agree that your contribution is licensed under the
Apache License 2.0. Participation is also subject to `CODE_OF_CONDUCT.md`.
