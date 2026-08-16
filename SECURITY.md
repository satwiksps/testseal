# Security policy

## Supported versions

Security fixes are provided for the latest tagged `0.1.x` release and the
default branch.

| Version | Supported |
| --- | --- |
| Latest `0.1.x` | Yes |
| `main` | Yes |
| Older releases and forks | No |

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Use GitHub's private
[Report a vulnerability](https://github.com/satwiksps/testseal/security/advisories/new)
flow. If that flow is unavailable, contact the maintainer through the private
contact method on their GitHub profile and ask for a secure channel without
including exploit details in the first message.

Please include the affected version or commit, a minimal reproduction, the
realistic impact, and any mitigation you have tested. Reports should receive an
acknowledgement within seven days and an initial assessment within fourteen
days. Disclosure timing and credit will be coordinated with the reporter.

## Security model

Pull-request content is untrusted input. TestSeal asks Git for refs, diffs, and
blobs, then parses Python source. It does not import changed modules, load
pytest plugins, run tests, evaluate decorators, or execute repository
configuration. TOML configuration is treated as data.

TestSeal is not a sandbox. The Git executable and Python interpreter running it
are part of the local trust boundary, and the process has the runner's normal
filesystem access. Use CI timeouts, runner resource limits, path filters, and
exclusions for generated or exceptionally large repositories.

When scanning contributions from forks:

- use `pull_request`, not `pull_request_target` with an untrusted checkout;
- grant only `contents: read` unless another permission is required;
- do not expose repository or environment secrets;
- fetch both sides of the comparison; and
- treat report strings as untrusted data in custom renderers.

The official Action passes arguments as separate process values, captures
bounded output, and installs only the Python source bundled with the selected
TestSeal revision.

## Release integrity

Release tags are expected to be signed and protected from deletion or rewrite.
The release workflow checks version agreement, rebuilds distribution artifacts,
verifies the committed Action bundle, and publishes SHA-256 checksums.
