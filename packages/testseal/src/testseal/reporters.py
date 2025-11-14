"""Text, versioned JSON, and SARIF 2.1.0 reporters."""

from __future__ import annotations

import json
from typing import Any

from . import __version__
from .models import AuditResult, Finding, Severity
from .rules import RULES

REPOSITORY_URL = "https://github.com/satwiksps/testseal"
RULE_DOC_ANCHORS = {
    "TS001": "ts001-assertion-removed",
    "TS002": "ts002-test-skipped-or-expected-to-fail",
    "TS003": "ts003-assertion-weakened",
    "TS004": "ts004-tolerance-widened",
    "TS005": "ts005-exception-swallowed",
    "TS006": "ts006-snapshot-regeneration-enabled",
    "TS007": "ts007-subject-under-test-mocked",
    "TS008": "ts008-source-and-guarding-test-co-edited",
}


def render_json(result: AuditResult) -> str:
    return json.dumps(result.to_dict(), indent=2, sort_keys=False) + "\n"


def render_text(result: AuditResult) -> str:
    if not result.findings:
        lines = [
            f"TestSeal: no test-integrity findings across {result.files_scanned} changed file(s)."
        ]
    else:
        lines = []
        for finding in result.findings:
            lines.append(
                f"[{finding.severity.value.upper()}] {finding.rule_id} "
                f"{finding.path}:{finding.line}:{finding.column} - {finding.title}"
            )
            lines.append(f"  {finding.message}")
            if finding.evidence:
                lines.append(f"  Evidence: {finding.evidence}")
            if finding.fingerprint:
                lines.append(f"  Fingerprint: {finding.fingerprint}")
            if finding.remediation:
                lines.append(f"  Fix: {finding.remediation}")
        counts = result.by_severity
        lines.extend(
            (
                "",
                (
                    f"TestSeal: {len(result.findings)} finding(s) in "
                    f"{result.files_scanned} changed file(s) "
                    f"(high {counts['high']}, medium {counts['medium']}, low {counts['low']})."
                ),
            )
        )
    if result.suppressed_count:
        lines.append(
            f"TestSeal: {result.suppressed_count} finding(s) suppressed by fingerprint."
        )
    if result.parse_warnings:
        lines.append("")
        lines.extend(f"Warning: {warning}" for warning in result.parse_warnings)
    return "\n".join(lines) + "\n"


def _sarif_level(severity: Severity) -> str:
    return {
        Severity.HIGH: "error",
        Severity.MEDIUM: "warning",
        Severity.LOW: "note",
    }[severity]


def _sarif_rule(rule_id: str) -> dict[str, Any]:
    metadata = RULES[rule_id]
    return {
        "id": rule_id,
        "name": metadata.title.replace(" ", ""),
        "shortDescription": {"text": metadata.title},
        "fullDescription": {"text": metadata.remediation},
        "helpUri": (
            f"{REPOSITORY_URL}/blob/main/docs/rules.md#{RULE_DOC_ANCHORS[rule_id]}"
        ),
        "defaultConfiguration": {"level": _sarif_level(metadata.severity)},
        "properties": {
            "tags": ["test-integrity", "security", "ai-agent"],
            "precision": metadata.confidence.value,
        },
    }


def _sarif_result(finding: Finding) -> dict[str, Any]:
    region: dict[str, int] = {
        "startLine": finding.line,
        "startColumn": finding.column,
    }
    if finding.end_line is not None:
        region["endLine"] = finding.end_line
    payload: dict[str, Any] = {
        "ruleId": finding.rule_id,
        "level": _sarif_level(finding.severity),
        "message": {"text": finding.message},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": finding.path.replace("\\", "/")},
                    "region": region,
                }
            }
        ],
        "partialFingerprints": {"testseal/v1": finding.fingerprint},
        "properties": {
            "confidence": finding.confidence.value,
            "remediation": finding.remediation,
        },
    }
    return payload


def render_sarif(result: AuditResult) -> str:
    used_rule_ids = sorted({finding.rule_id for finding in result.findings})
    invocation: dict[str, Any] = {
        "executionSuccessful": True,
        "properties": result.summary,
    }
    if result.parse_warnings:
        invocation["toolExecutionNotifications"] = [
            {
                "descriptor": {"id": "TS-PARSE-WARNING"},
                "level": "warning",
                "message": {"text": warning},
            }
            for warning in result.parse_warnings
        ]
    document = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "TestSeal",
                        "semanticVersion": __version__,
                        "informationUri": REPOSITORY_URL,
                        "rules": [_sarif_rule(rule_id) for rule_id in used_rule_ids],
                    }
                },
                "results": [_sarif_result(finding) for finding in result.findings],
                "invocations": [invocation],
            }
        ],
    }
    return json.dumps(document, indent=2) + "\n"


def render(result: AuditResult, format_name: str) -> str:
    if format_name == "text":
        return render_text(result)
    if format_name == "json":
        return render_json(result)
    if format_name == "sarif":
        return render_sarif(result)
    raise ValueError(f"unsupported output format: {format_name}")
