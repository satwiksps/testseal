"""Public, serializable models used by the auditor and reporters."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    """Policy severity in increasing order."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def rank(self) -> int:
        return {Severity.LOW: 1, Severity.MEDIUM: 2, Severity.HIGH: 3}[self]

    @classmethod
    def parse(cls, value: object) -> Severity:
        if not isinstance(value, str):
            raise ValueError(f"severity must be a string; got {type(value).__name__}")
        try:
            return cls(value.lower())
        except ValueError as exc:
            choices = ", ".join(item.value for item in cls)
            raise ValueError(f"expected one of: {choices}; got {value!r}") from exc


class Confidence(StrEnum):
    """How directly a finding follows from the observed syntax change."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class Finding:
    """One integrity-relevant change at a source location."""

    rule_id: str
    title: str
    message: str
    severity: Severity
    confidence: Confidence
    path: str
    line: int
    column: int = 1
    end_line: int | None = None
    evidence: str | None = None
    remediation: str | None = None
    help_uri: str | None = None
    fingerprint: str | None = None
    fingerprint_context: str | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "line", max(1, self.line))
        object.__setattr__(self, "column", max(1, self.column))
        if self.end_line is not None:
            object.__setattr__(self, "end_line", max(self.line, self.end_line))
        if self.fingerprint is None:
            material = "\x00".join(
                (
                    self.rule_id,
                    self.path.replace("\\", "/"),
                    self.message,
                    self.evidence or "",
                    self.fingerprint_context or "",
                )
            )
            object.__setattr__(
                self,
                "fingerprint",
                hashlib.sha256(material.encode("utf-8")).hexdigest()[:24],
            )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "rule_id": self.rule_id,
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "confidence": self.confidence.value,
            "path": self.path.replace("\\", "/"),
            "line": self.line,
            "column": self.column,
            "fingerprint": self.fingerprint,
        }
        if self.end_line is not None:
            payload["end_line"] = self.end_line
        if self.evidence is not None:
            payload["evidence"] = self.evidence
        if self.remediation is not None:
            payload["remediation"] = self.remediation
        if self.help_uri is not None:
            payload["help_uri"] = self.help_uri
        return payload


@dataclass(slots=True)
class AuditResult:
    """Complete result of one deterministic audit."""

    files_scanned: int
    findings: list[Finding] = field(default_factory=list)
    parse_warnings: list[str] = field(default_factory=list)
    version: str = "1"
    suppressed_count: int = 0

    @property
    def by_severity(self) -> dict[str, int]:
        counts = {item.value: 0 for item in Severity}
        for finding in self.findings:
            counts[finding.severity.value] += 1
        return counts

    @property
    def summary(self) -> dict[str, Any]:
        return {
            "files_scanned": self.files_scanned,
            "finding_count": len(self.findings),
            "suppressed_count": self.suppressed_count,
            "by_severity": self.by_severity,
        }

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "version": self.version,
            "summary": self.summary,
            "findings": [finding.to_dict() for finding in self.findings],
        }
        if self.parse_warnings:
            payload["warnings"] = list(self.parse_warnings)
        return payload

    def fails_at(self, threshold: Severity | None) -> bool:
        if threshold is None:
            return False
        return any(item.severity.rank >= threshold.rank for item in self.findings)
