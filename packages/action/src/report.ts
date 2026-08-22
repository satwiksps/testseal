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

function requiredCount(value: unknown, field: string): number {
  const count = nonNegativeInteger(value);
  if (count === undefined) {
    throw new ReportError(`TestSeal JSON field '${field}' must be a non-negative integer.`);
  }
  return count;
}

function severity(value: unknown, index: number): Severity {
  switch (value) {
    case 'high':
      return 'high';
    case 'medium':
      return 'medium';
    case 'low':
      return 'low';
    default:
      throw new ReportError(`Finding ${index + 1} has invalid severity '${String(value)}'.`);
  }
}

function requiredFindingText(raw: Record<string, unknown>, field: string, index: number): string {
  const value = text(raw[field]);
  if (value === undefined) throw new ReportError(`Finding ${index + 1} is missing a ${field}.`);
  return value;
}

function optionalFindingText(
  raw: Record<string, unknown>,
  field: string,
  index: number,
): string | undefined {
  if (raw[field] === undefined) return undefined;
  const value = text(raw[field]);
  if (value === undefined) {
    throw new ReportError(`Finding ${index + 1} field '${field}' must be a non-empty string.`);
  }
  return value;
}

function normalizeFinding(value: unknown, index: number): Finding {
  const raw = record(value);
  if (raw === undefined) throw new ReportError(`Finding ${index + 1} is not an object.`);

  const ruleId = requiredFindingText(raw, 'rule_id', index);
  const title = requiredFindingText(raw, 'title', index);
  const message = requiredFindingText(raw, 'message', index);
  const confidence = requiredFindingText(raw, 'confidence', index);
  if (!['low', 'medium', 'high'].includes(confidence)) {
    throw new ReportError(`Finding ${index + 1} has invalid confidence '${confidence}'.`);
  }
  const path = requiredFindingText(raw, 'path', index);
  if (
    path.includes('\\') ||
    path.startsWith('/') ||
    /^[A-Za-z]:/u.test(path) ||
    path.split('/').some((part) => part === '' || part === '.' || part === '..')
  ) {
    throw new ReportError(
      `Finding ${index + 1} field 'path' must be a repository-relative forward-slash path.`,
    );
  }
  const line = positiveInteger(raw.line);
  if (line === undefined) {
    throw new ReportError(`Finding ${index + 1} field 'line' must be a positive integer.`);
  }
  const column = positiveInteger(raw.column);
  if (column === undefined) {
    throw new ReportError(`Finding ${index + 1} field 'column' must be a positive integer.`);
  }
  const fingerprint = requiredFindingText(raw, 'fingerprint', index);
  if (!/^[0-9a-f]{24}$/u.test(fingerprint)) {
    throw new ReportError(
      `Finding ${index + 1} field 'fingerprint' must contain 24 lowercase hexadecimal characters.`,
    );
  }
  const endLine = raw.end_line === undefined ? undefined : positiveInteger(raw.end_line);
  if (raw.end_line !== undefined && (endLine === undefined || endLine < line)) {
    throw new ReportError(
      `Finding ${index + 1} field 'end_line' must be an integer at or after line ${line}.`,
    );
  }
  const evidence = optionalFindingText(raw, 'evidence', index);
  const remediation = optionalFindingText(raw, 'remediation', index);
  const helpUri = optionalFindingText(raw, 'help_uri', index);

  return {
    ruleId,
    title,
    message,
    severity: severity(raw.severity, index),
    confidence,
    path,
    line,
    column,
    ...(endLine === undefined ? {} : { endLine }),
    ...(evidence === undefined ? {} : { evidence }),
    ...(remediation === undefined ? {} : { remediation }),
    ...(helpUri === undefined ? {} : { helpUri }),
    fingerprint,
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
  const version = text(raw.version);
  if (version === undefined)
    throw new ReportError('TestSeal JSON report is missing schema version.');
  if (version !== '1')
    throw new ReportError(`TestSeal JSON report has unsupported schema version '${version}'.`);
  if (!Array.isArray(raw.findings)) {
    throw new ReportError("TestSeal JSON field 'findings' must be an array.");
  }
  if (raw.warnings !== undefined && !Array.isArray(raw.warnings)) {
    throw new ReportError("TestSeal JSON field 'warnings' must be an array.");
  }
  const validatedSummary = record(raw.summary);
  if (validatedSummary === undefined)
    throw new ReportError("TestSeal JSON field 'summary' must be an object.");
  const validatedBySeverity = record(validatedSummary.by_severity);
  if (validatedBySeverity === undefined) {
    throw new ReportError("TestSeal JSON field 'summary.by_severity' must be an object.");
  }
  const filesScanned = requiredCount(validatedSummary.files_scanned, 'summary.files_scanned');
  const findingCount = requiredCount(validatedSummary.finding_count, 'summary.finding_count');
  const suppressedCount = requiredCount(
    validatedSummary.suppressed_count,
    'summary.suppressed_count',
  );
  const severityCounts = {
    low: requiredCount(validatedBySeverity.low, 'summary.by_severity.low'),
    medium: requiredCount(validatedBySeverity.medium, 'summary.by_severity.medium'),
    high: requiredCount(validatedBySeverity.high, 'summary.by_severity.high'),
  };

  const findings = (raw.findings ?? []).map(normalizeFinding);
  const derived = findings.reduce<Record<Severity, number>>(
    (counts, finding) => {
      counts[finding.severity] += 1;
      return counts;
    },
    { low: 0, medium: 0, high: 0 },
  );
  if (
    findingCount !== findings.length ||
    (['low', 'medium', 'high'] as const).some((level) => severityCounts[level] !== derived[level])
  ) {
    throw new ReportError('TestSeal JSON report has an inconsistent summary.');
  }
  const uniqueFiles = new Set(
    findings.flatMap((finding) => (finding.path === undefined ? [] : [finding.path])),
  ).size;
  if (filesScanned < uniqueFiles) {
    throw new ReportError('TestSeal JSON report has an inconsistent summary.');
  }
  const warnings = (raw.warnings ?? []).map((value, index) => {
    const warning = text(value);
    if (warning === undefined) {
      throw new ReportError(`Warning ${index + 1} must be a non-empty string.`);
    }
    return warning;
  });

  return {
    version,
    summary: {
      filesScanned,
      findingCount,
      suppressedCount,
      bySeverity: severityCounts,
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
