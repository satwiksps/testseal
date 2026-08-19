---
description: Choose the correct support, bug report, feature, and security channel.
---

# Support

TestSeal support is handled in the public GitHub repository. There is no private
support service or community chat that must be monitored.

## Bugs and false positives

Use [GitHub Issues](https://github.com/satwiksps/testseal/issues/new/choose) for:

- reproducible crashes or incorrect exit codes;
- false-positive and false-negative rule behavior;
- platform or Git compatibility problems;
- documentation errors;
- Action input, annotation, or output problems.

Include:

1. TestSeal version.
2. Python version and operating system.
3. Exact command or workflow fragment.
4. Relevant configuration.
5. Minimal before and after source or diff.
6. Actual and expected output.

Remove proprietary data and credentials before posting.

## Feature and rule proposals

Open a proposal before implementing a broad rule or public contract change.
Describe the exact diff signal, supported syntax, intentional non-findings,
precision risks, and why existing rules do not cover it.

General requests such as "detect weak tests" are too broad for a deterministic
rule. A useful proposal includes concrete before and after code.

## Questions

Use [GitHub Discussions](https://github.com/satwiksps/testseal/discussions) for
usage questions that do not identify a reproducible defect. Search the
documentation and existing discussions first.

## Security

Do not open a public issue for an undisclosed vulnerability. Use
[private vulnerability reporting](https://github.com/satwiksps/testseal/security/advisories/new)
and follow the repository [security policy](https://github.com/satwiksps/testseal/blob/main/SECURITY.md).

## Response expectations

TestSeal is maintained as an open source project without a guaranteed service
level. Clear minimal reproductions are easier to review and fix. Maintainers may
close requests that cannot be reproduced, fall outside the documented scope, or
contain no actionable example.
