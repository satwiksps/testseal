import { describe, expect, it } from 'vitest';

import { emitAnnotations, parseReport, ReportError, serializeReport } from '../src/report';
import type { Finding, TestSealReport } from '../src/types';
import { FakeCore } from './fakes';

function finding(overrides: Partial<Finding> = {}): Finding {
  return {
    ruleId: 'TS001',
    title: 'Assertion removed',
    message: 'An assertion was removed.',
    severity: 'high',
    path: 'tests/test_widget.py',
    line: 12,
    column: 3,
    ...overrides,
  };
}

describe('parseReport', () => {
  it('parses the canonical CLI schema and strips a BOM', () => {
    const report = parseReport(
      `\uFEFF${JSON.stringify({
        version: '1',
        summary: {
          files_scanned: 4,
          finding_count: 1,
          by_severity: { low: 0, medium: 0, high: 1 },
        },
        findings: [
          {
            rule_id: 'TS001',
            title: 'Assertion removed',
            message: 'The assertion disappeared.',
            severity: 'high',
            confidence: 0.98,
            path: 'tests/test_api.py',
            line: 20,
            column: 5,
            end_line: 21,
            evidence: 'assert value == 42 -> assert value',
            remediation: 'Restore the precise assertion.',
            help_uri: 'https://example.test/TS001',
            fingerprint: 'abc',
          },
        ],
        warnings: ['tests/broken.py could not be parsed'],
      })}`,
    );

    expect(report.summary).toEqual({
      filesScanned: 4,
      findingCount: 1,
      suppressedCount: 0,
      bySeverity: { low: 0, medium: 0, high: 1 },
    });
    expect(report.findings[0]).toMatchObject({
      ruleId: 'TS001',
      confidence: 0.98,
      line: 20,
      endLine: 21,
      evidence: 'assert value == 42 -> assert value',
      remediation: 'Restore the precise assertion.',
      helpUri: 'https://example.test/TS001',
    });
    expect(report.warnings).toEqual(['tests/broken.py could not be parsed']);
  });

  it('derives missing summary values and tolerates legacy aliases', () => {
    const report = parseReport(
      JSON.stringify({
        summary: { count: 2 },
        findings: [
          { rule: 'A', description: 'a', severity: 'warning', file: 'one.py', start_line: 2 },
          { id: 'B', title: 'b', severity: 'notice', file: 'two.py' },
        ],
      }),
    );

    expect(report.summary).toEqual({
      filesScanned: 2,
      findingCount: 2,
      suppressedCount: 0,
      bySeverity: { low: 1, medium: 1, high: 0 },
    });
    expect(report.findings.map((item) => item.severity)).toEqual(['medium', 'low']);
  });

  it.each([
    ['', 'did not produce'],
    ['not json', 'invalid JSON'],
    ['[]', 'must be an object'],
    ['{"findings":{}}', "'findings' must be an array"],
    ['{"findings":[{"rule_id":"A","severity":"critical"}]}', 'unknown severity'],
  ])('rejects malformed reports', (value, message) => {
    expect(() => parseReport(value)).toThrow(message);
    expect(() => parseReport(value)).toThrow(ReportError);
  });

  it('serializes the normalized report using the public snake-case schema', () => {
    const input: TestSealReport = {
      version: '1',
      summary: {
        filesScanned: 1,
        findingCount: 1,
        bySeverity: { low: 0, medium: 0, high: 1 },
      },
      findings: [
        finding({
          evidence: 'assert value == 42',
          remediation: 'Restore the assertion.',
          helpUri: 'https://example.test/help',
        }),
      ],
      warnings: ['partial scan'],
    };
    const output = JSON.parse(serializeReport(input)) as Record<string, unknown>;

    expect(output).toMatchObject({
      version: '1',
      summary: {
        files_scanned: 1,
        finding_count: 1,
        by_severity: { low: 0, medium: 0, high: 1 },
      },
    });
    expect(output.findings).toEqual([
      expect.objectContaining({
        rule_id: 'TS001',
        evidence: 'assert value == 42',
        remediation: 'Restore the assertion.',
        help_uri: 'https://example.test/help',
      }),
    ]);
    expect(output.warnings).toEqual(['partial scan']);
  });
});

describe('emitAnnotations', () => {
  it('maps severity and source locations to GitHub annotations', () => {
    const core = new FakeCore();
    const report: TestSealReport = {
      version: '1',
      summary: {
        filesScanned: 1,
        findingCount: 3,
        bySeverity: { low: 1, medium: 1, high: 1 },
      },
      findings: [
        finding({ ruleId: 'LOW', severity: 'low' }),
        finding({ ruleId: 'MEDIUM', severity: 'medium' }),
        finding({ ruleId: 'HIGH', severity: 'high', endLine: 15 }),
      ],
      warnings: [],
    };

    emitAnnotations(core, report);

    expect(core.annotations.map((call) => call.level)).toEqual(['error', 'warning', 'notice']);
    expect(core.annotations[0]?.properties).toMatchObject({
      title: 'HIGH: Assertion removed',
      file: 'tests/test_widget.py',
      startLine: 12,
      endLine: 15,
    });
    expect(core.annotations[0]?.properties).not.toHaveProperty('startColumn');
  });

  it('limits annotations while retaining an omission notice', () => {
    const core = new FakeCore();
    const findings = Array.from({ length: 52 }, (_, index) =>
      finding({ ruleId: `TS${String(index).padStart(3, '0')}` }),
    );
    emitAnnotations(core, {
      version: '1',
      summary: {
        filesScanned: 1,
        findingCount: findings.length,
        bySeverity: { low: 0, medium: 0, high: findings.length },
      },
      findings,
      warnings: [],
    });

    expect(core.annotations).toHaveLength(51);
    expect(core.annotations.at(-1)?.message).toContain('2 additional');
  });

  it('emits scan warnings and retains them in normalized output', () => {
    const core = new FakeCore();
    const report: TestSealReport = {
      version: '1',
      summary: {
        filesScanned: 1,
        findingCount: 0,
        bySeverity: { low: 0, medium: 0, high: 0 },
      },
      findings: [],
      warnings: ['tests/test_broken.py: new source could not be parsed'],
    };

    emitAnnotations(core, report);

    expect(core.annotations).toHaveLength(1);
    expect(core.annotations[0]?.level).toBe('warning');
    expect(core.annotations[0]?.message).toContain('could not be parsed');
    expect(serializeReport(report)).toContain('"warnings"');
    expect(serializeReport(report)).toContain(
      'tests/test_broken.py: new source could not be parsed',
    );
  });
});
