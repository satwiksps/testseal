---
description: Run TestSeal in GitLab CI, CircleCI, Jenkins, and other CI systems.
---

# Other CI systems

TestSeal needs Python 3.11 or newer, a checkout containing the compared Git
revisions, and one CLI invocation. It does not require a service account or API
key.

## Generic shell sequence

```bash
python -m pip install testseal
git fetch --no-tags origin main
testseal scan --base origin/main --head HEAD --format json --output testseal.json
```

Set `fail_on = "high"` in repository configuration, or pass
`--fail-on high`, when the job should block.

Preserve these exit codes:

| Exit | CI meaning |
| --- | --- |
| `0` | Completed and threshold not reached |
| `1` | Finding threshold reached |
| `2` | Invalid or incomplete scan |

Do not rewrite exit code `2` as a successful advisory result. It indicates that
policy, Git data, parsing, or I/O prevented a complete blocking scan.

## GitLab CI

```yaml
testseal:
  image: python:3.12-slim
  stage: test
  variables:
    GIT_DEPTH: "0"
  before_script:
    - python -m pip install --disable-pip-version-check testseal
  script:
    - testseal scan
      --base "$CI_MERGE_REQUEST_DIFF_BASE_SHA"
      --head "$CI_COMMIT_SHA"
      --format json
      --output testseal.json
  artifacts:
    when: always
    paths:
      - testseal.json
```

Use the merge request diff base SHA when available. For branch pipelines, fetch
and compare the intended target branch explicitly.

## CircleCI

```yaml
version: 2.1

jobs:
  testseal:
    docker:
      - image: cimg/python:3.12
    steps:
      - checkout
      - run:
          name: Fetch base branch
          command: git fetch --no-tags origin main
      - run:
          name: Install TestSeal
          command: python -m pip install testseal
      - run:
          name: Scan test integrity
          command: testseal scan --base origin/main --head HEAD

workflows:
  checks:
    jobs:
      - testseal
```

CircleCI checkout behavior can be shallow or use a detached revision. Confirm
that `origin/main` and the current head exist before scanning.

## Jenkins declarative pipeline

```groovy
pipeline {
  agent any
  stages {
    stage('TestSeal') {
      steps {
        sh 'python3 -m pip install --user testseal'
        sh 'git fetch --no-tags origin main'
        sh 'python3 -m testseal scan --base origin/main --head HEAD'
      }
    }
  }
}
```

Use a controlled virtual environment instead of `--user` on shared or
persistent agents.

## Upload reports

JSON is suited to custom dashboards and job artifacts. SARIF is suited to code
scanning systems that implement SARIF 2.1.0:

```bash
testseal scan \
  --base origin/main \
  --head HEAD \
  --format sarif \
  --output testseal.sarif
```

Upload report files even when the scan exits `1`. In shell-based systems, capture
the exit code, upload artifacts, then return the original exit code.

## Cache safely

TestSeal has no runtime dependencies and no analysis cache. Caching the Python
package installation is optional. Do not cache reports across commits as if they
were current results.
