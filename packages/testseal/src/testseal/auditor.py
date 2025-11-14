"""High-level TestSeal audit API."""

from __future__ import annotations

from collections.abc import Sequence

from .config import Config
from .diff import ChangedFile, parse_unified_diff
from .models import AuditResult
from .rules import RuleEngine, coedit_findings, deduplicate


class Auditor:
    """Audit hydrated file changes using a resolved :class:`Config`."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self.engine = RuleEngine(self.config)

    def audit(self, changes: Sequence[ChangedFile]) -> AuditResult:
        eligible = [item for item in changes if self.config.includes_path(item.path)]
        findings = []
        warnings: list[str] = []
        for change in eligible:
            if change.path.endswith(".py") and self.config.is_test_path(change.path):
                file_findings, warning = self.engine.analyze_test_file(change)
                findings.extend(file_findings)
                if warning:
                    warnings.append(warning)
            else:
                findings.extend(self.engine.analyze_artifact(change))
        findings.extend(coedit_findings(eligible, self.config))
        unique_findings = deduplicate(findings)
        visible_findings = [
            finding
            for finding in unique_findings
            if finding.fingerprint not in self.config.ignore_fingerprints
        ]
        return AuditResult(
            files_scanned=len(eligible),
            findings=visible_findings,
            parse_warnings=warnings,
            suppressed_count=len(unique_findings) - len(visible_findings),
        )


def audit_diff(text: str, config: Config | None = None) -> AuditResult:
    """Convenience API for auditing caller-supplied unified-diff text."""

    return Auditor(config).audit(parse_unified_diff(text))
