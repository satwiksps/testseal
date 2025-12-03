import type { AnnotationProperties } from '@actions/core';

import type { CoreApi, Finding, Severity, TestSealReport } from './types';

const SEVERITY_ORDER: Readonly<Record<Severity, number>> = {
  high: 3,
  medium: 2,
  low: 1,
};
const MAX_ANNOTATIONS = 50;
const MAX_TITLE_LENGTH = 255;

export class ReportError extends Error {
  override readonly name = 'ReportError';
}

function record(value: unknown): Record<string, unknown> | undefined {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return undefined;
  return value as Record<string, unknown>;
}

function text(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() !== '' ? value : undefined;
}

function nonNegativeInteger(value: unknown): number | undefined {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) return undefined;
  return value;
}

function positiveInteger(value: unknown): number | undefined {
  const number = nonNegativeInteger(value);
  return number !== undefined && number > 0 ? number : undefined;
}

function severity(value: unknown, index: number): Severity {
  if (typeof value !== 'string') {
    throw new ReportError(`Finding ${index + 1} is missing a severity.`);
  }
  switch (value.toLowerCase()) {
    case 'high':
    case 'error':
      return 'high';
    case 'medium':
    case 'warning':
      return 'medium';
    case 'low':
    case 'info':
    case 'notice':
      return 'low';
    default:
      throw new ReportError(`Finding ${index + 1} has unknown severity '${value}'.`);
  }
}

function normalizeFinding(value: unknown, index: number): Finding {
  const raw = record(value);
  if (raw === undefined) throw new ReportError(`Finding ${index + 1} is not an object.`);

  const ruleId = text(raw.rule_id) ?? text(raw.rule) ?? text(raw.id);
  if (ruleId === undefined) throw new ReportError(`Finding ${index + 1} is missing a rule_id.`);

  const title = text(raw.title) ?? ruleId;
  const message = text(raw.message) ?? text(raw.description) ?? title;
  const confidence =
    typeof raw.confidence === 'string' || typeof raw.confidence === 'number'
      ? raw.confidence
      : undefined;
  const path = text(raw.path) ?? text(raw.file);
  const line = positiveInteger(raw.line) ?? positiveInteger(raw.start_line);
  const column = positiveInteger(raw.column) ?? positiveInteger(raw.start_column);
  const endLine = positiveInteger(raw.end_line);
  const evidence = text(raw.evidence);
  const remediation = text(raw.remediation);
  const helpUri = text(raw.help_uri) ?? text(raw.help_url);
  const fingerprint = text(raw.fingerprint);

  return {
    ruleId,
    title,
    message,
    severity: severity(raw.severity, index),
    ...(confidence === undefined ? {} : { confidence }),
    ...(path === undefined ? {} : { path }),
    ...(line === undefined ? {} : { line }),
    ...(column === undefined ? {} : { column }),
    ...(endLine === undefined ? {} : { endLine }),
    ...(evidence === undefined ? {} : { evidence }),
    ...(remediation === undefined ? {} : { remediation }),
    ...(helpUri === undefined ? {} : { helpUri }),
    ...(fingerprint === undefined ? {} : { fingerprint }),
  };
}

export function parseReport(stdout: string): TestSealReport {
  const clean = stdout.replace(/^\uFEFF/u, '').trim();
  if (clean === '') throw new ReportError('TestSeal did not produce a JSON report.');

  let value: unknown;
  try {
    value = JSON.parse(clean) as unknown;
  } catch (error) {
    const detail = error instanceof Error ? ` ${error.message}` : '';
    throw new ReportError(`TestSeal produced invalid JSON.${detail}`);
  }

  const raw = record(value);
  if (raw === undefined) throw new ReportError('TestSeal JSON report must be an object.');
  if (raw.findings !== undefined && !Array.isArray(raw.findings)) {
    throw new ReportError("TestSeal JSON field 'findings' must be an array.");
  }
  if (raw.warnings !== undefined && !Array.isArray(raw.warnings)) {
    throw new ReportError("TestSeal JSON field 'warnings' must be an array.");
  }

  const findings = (raw.findings ?? []).map(normalizeFinding);
  const summary = record(raw.summary) ?? {};
  const bySeverity = record(summary.by_severity) ?? {};
  const derived = findings.reduce<Record<Severity, number>>(
    (counts, finding) => {
      counts[finding.severity] += 1;
      return counts;
    },
    { low: 0, medium: 0, high: 0 },
  );
  const uniqueFiles = new Set(
    findings.flatMap((finding) => (finding.path === undefined ? [] : [finding.path])),
  ).size;
  const warnings = (raw.warnings ?? []).map((value, index) => {
    const warning = text(value);
    if (warning === undefined) {
      throw new ReportError(`Warning ${index + 1} must be a non-empty string.`);
    }
    return warning;
  });

  return {
    version: text(raw.version) ?? '1',
    summary: {
      filesScanned: nonNegativeInteger(summary.files_scanned) ?? uniqueFiles,
      findingCount:
        nonNegativeInteger(summary.finding_count) ??
        nonNegativeInteger(summary.count) ??
        findings.length,
      suppressedCount: nonNegativeInteger(summary.suppressed_count) ?? 0,
      bySeverity: {
        low: nonNegativeInteger(bySeverity.low) ?? derived.low,
        medium: nonNegativeInteger(bySeverity.medium) ?? derived.medium,
        high: nonNegativeInteger(bySeverity.high) ?? derived.high,
      },
    },
    findings,
    warnings,
  };
}

export function serializeReport(report: TestSealReport): string {
  return JSON.stringify({
    version: report.version,
    summary: {
      files_scanned: report.summary.filesScanned,
      finding_count: report.summary.findingCount,
      suppressed_count: report.summary.suppressedCount ?? 0,
      by_severity: report.summary.bySeverity,
    },
    findings: report.findings.map((finding) => ({
      rule_id: finding.ruleId,
      title: finding.title,
      message: finding.message,
      severity: finding.severity,
      ...(finding.confidence === undefined ? {} : { confidence: finding.confidence }),
      ...(finding.path === undefined ? {} : { path: finding.path }),
      ...(finding.line === undefined ? {} : { line: finding.line }),
      ...(finding.column === undefined ? {} : { column: finding.column }),
      ...(finding.endLine === undefined ? {} : { end_line: finding.endLine }),
      ...(finding.evidence === undefined ? {} : { evidence: finding.evidence }),
      ...(finding.remediation === undefined ? {} : { remediation: finding.remediation }),
      ...(finding.helpUri === undefined ? {} : { help_uri: finding.helpUri }),
      ...(finding.fingerprint === undefined ? {} : { fingerprint: finding.fingerprint }),
    })),
    ...(report.warnings.length === 0 ? {} : { warnings: report.warnings }),
  });
}

function truncateTitle(value: string): string {
  if (value.length <= MAX_TITLE_LENGTH) return value;
  return `${value.slice(0, MAX_TITLE_LENGTH - 3)}...`;
}

function annotationProperties(finding: Finding): AnnotationProperties {
  const startLine = finding.line;
  const endLine =
    startLine === undefined || finding.endLine === undefined
      ? undefined
      : Math.max(startLine, finding.endLine);

  return {
    title: truncateTitle(`${finding.ruleId}: ${finding.title}`),
    ...(finding.path === undefined ? {} : { file: finding.path }),
    ...(startLine === undefined ? {} : { startLine }),
    ...(endLine === undefined ? {} : { endLine }),
    ...(startLine === undefined ||
    finding.column === undefined ||
    (endLine !== undefined && endLine !== startLine)
      ? {}
      : { startColumn: finding.column }),
  };
}

export function emitAnnotations(core: CoreApi, report: TestSealReport): void {
  const findings = [...report.findings].sort(
    (left, right) => SEVERITY_ORDER[right.severity] - SEVERITY_ORDER[left.severity],
  );
  const selected = findings.slice(0, MAX_ANNOTATIONS);

  for (const finding of selected) {
    const properties = annotationProperties(finding);
    if (finding.severity === 'high') core.error(finding.message, properties);
    else if (finding.severity === 'medium') core.warning(finding.message, properties);
    else core.notice(finding.message, properties);
  }

  if (findings.length > selected.length) {
    core.notice(
      `${findings.length - selected.length} additional TestSeal findings were omitted from annotations; all findings remain in the result output.`,
    );
  }

  const selectedWarnings = report.warnings.slice(0, 10);
  for (const warning of selectedWarnings) {
    core.warning(warning, { title: 'TestSeal scan incomplete' });
  }
  if (report.warnings.length > selectedWarnings.length) {
    core.warning(
      `${report.warnings.length - selectedWarnings.length} additional scan warnings were omitted; all warnings remain in the result output.`,
      { title: 'TestSeal scan incomplete' },
    );
  }
}
