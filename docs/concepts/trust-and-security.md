---
description: Threat model, permissions, untrusted input handling, and secure deployment.
---

# Trust and security

TestSeal is designed to inspect untrusted pull-request content without executing
that content.

## Trust boundary

The following inputs are untrusted:

- changed Python and snapshot content;
- paths and Git metadata from a contributor branch;
- unified-diff text;
- source-derived finding messages and evidence;
- repository TestSeal configuration in the checked-out revision.

The scanner treats these inputs as data. It does not:

- import changed modules;
- run pytest or project tests;
- load pytest plugins or `conftest.py`;
- evaluate decorators, constants, or configuration expressions;
- execute repository hooks;
- call an LLM or remote TestSeal service;
- send telemetry.

## Executed programs

Git-backed modes invoke the `git` executable with argument arrays to resolve the
repository root, revisions, diffs, blobs, and untracked paths. Revision values
that begin with option syntax are rejected before Git runs.

The GitHub Action invokes Python and pip with argument arrays, without a shell.
The default installation source is the TestSeal project bundled in the Action
archive. It does not install the consumer repository.

## GitHub permissions

Recommended workflow permissions:

```yaml
permissions:
  contents: read
```

Use the `pull_request` event. Do not provide repository secrets to the job.
TestSeal does not need write access to code, checks, pull requests, or packages.
Annotations are emitted through the GitHub Actions logging protocol.

Avoid `pull_request_target` with an untrusted head checkout. That combination
can expose trusted-context credentials to contributor-controlled files and is
outside TestSeal's supported threat model.

## Configuration as policy

Repository configuration changes can weaken enforcement by:

- changing `fail_on`;
- excluding paths;
- disabling rules;
- lowering severities;
- adding fingerprint suppressions;
- changing guarding-test relationships.

Protect configuration and workflow files with normal review, code owners, and
branch rules. TestSeal validates structure and known values, but cannot decide
whether an authorized policy change is appropriate.

## Reports are untrusted output

Finding text can contain source-derived evidence. Downstream systems must escape
report values before inserting them into HTML, terminals with unsafe control
handling, SQL, or shell commands.

The official Action passes annotations through the Actions toolkit and launches
processes without string-built shell commands.

## Availability limits

Very large patches or pathological Python syntax can consume CPU and memory.
Public patch-processing services should enforce request size, process time, and
memory limits around the CLI. GitHub workflows should use a job timeout.

## Supported security reports

Report vulnerabilities through
[GitHub private vulnerability reporting](https://github.com/satwiksps/testseal/security/advisories/new).
Include the affected version, impact, minimal reproduction, and suggested
mitigation if known. Do not open a public issue for an undisclosed vulnerability.

The repository's disclosure process and supported versions are defined in
[`SECURITY.md`](https://github.com/satwiksps/testseal/blob/main/SECURITY.md).
