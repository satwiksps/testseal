import { describe, expect, it } from 'vitest';
import { resolve } from 'node:path';

import { installArgs, runAction, withEventRefs } from '../src/action';
import { CommandError } from '../src/process';
import type { ActionInputs } from '../src/types';
import { FakeCore, FakeRunner, result } from './fakes';

const cleanReport = JSON.stringify({
  version: '1',
  summary: {
    files_scanned: 3,
    finding_count: 0,
    suppressed_count: 0,
    by_severity: { low: 0, medium: 0, high: 0 },
  },
  findings: [],
  warnings: [],
});

const findingReport = JSON.stringify({
  version: '1',
  summary: {
    files_scanned: 2,
    finding_count: 1,
    suppressed_count: 0,
    by_severity: { low: 0, medium: 1, high: 0 },
  },
  findings: [
    {
      rule_id: 'TS003',
      title: 'Assertion weakened',
      message: 'A strict assertion became permissive.',
      severity: 'medium',
      confidence: 'high',
      path: 'tests/test_service.py',
      line: 8,
      column: 1,
      fingerprint: '0123456789abcdef01234567',
    },
  ],
  warnings: [],
});

function baseInputs(overrides: Partial<ActionInputs> = {}): ActionInputs {
  return {
    staged: false,
    paths: [],
    pythonCommand: 'python',
    install: true,
    ...overrides,
  };
}

describe('installation resolution', () => {
  it('installs only the source bundled with the action release', () => {
    const workspace = resolve('work');
    const packagePath = workspace;
    const exists = (path: string): boolean => path === resolve(packagePath, 'pyproject.toml');

    expect(installArgs(workspace, exists)).toEqual([
      '-m',
      'pip',
      'install',
      '--disable-pip-version-check',
      '--no-input',
      packagePath,
    ]);
  });

  it('fails closed when a release does not contain the Python package', () => {
    expect(() => installArgs(resolve('work'), () => false)).toThrow(
      'bundled TestSeal Python package is missing',
    );
  });
});

describe('runAction', () => {
  it('passes every scan input as a separate process argument and sets clean outputs', async () => {
    const core = new FakeCore({
      install: 'false',
      base: 'origin/main',
      head: 'feature',
      staged: 'false',
      config: 'testseal.toml',
      paths: 'tests/one.py\ntests/path with spaces.py',
      'fail-on': 'high',
      'python-command': 'python3',
    });
    const runner = new FakeRunner([result(0, cleanReport)]);

    await runAction(core, runner);

    expect(runner.calls).toEqual([
      {
        command: 'python3',
        args: [
          '-m',
          'testseal',
          'scan',
          '--format',
          'json',
          '--fail-on',
          'high',
          '--base',
          'origin/main',
          '--head',
          'feature',
          '--config',
          'testseal.toml',
          '--',
          'tests/one.py',
          'tests/path with spaces.py',
        ],
      },
    ]);
    expect(core.outputs.get('outcome')).toBe('clean');
    expect(core.outputs.get('finding-count')).toBe(0);
    expect(core.outputs.get('files-scanned')).toBe(3);
    expect(core.outputs.get('suppressed-count')).toBe(0);
    expect(core.failed).toEqual([]);
  });

  it('omits --fail-on so TOML policy remains authoritative', async () => {
    const core = new FakeCore({ install: 'false', config: 'testseal.toml' });
    const runner = new FakeRunner([result(0, cleanReport)]);

    await runAction(core, runner);

    expect(runner.calls[0]?.args).not.toContain('--fail-on');
  });

  it('derives pull-request refs from the event payload when inputs are absent', () => {
    const base = 'a'.repeat(40);
    const head = 'b'.repeat(40);
    const inputs = withEventRefs(baseInputs(), 'pull_request', {
      pull_request: { base: { sha: base }, head: { sha: head } },
    });

    expect(inputs).toMatchObject({ base, head });
  });

  it('fails clearly when a pull-request payload lacks usable refs', async () => {
    const core = new FakeCore({ install: 'false' });
    const runner = new FakeRunner([]);

    await runAction(core, runner, {
      eventName: 'pull_request',
      eventPayload: {},
    });

    expect(core.failed.at(-1)).toContain('does not contain usable base/head SHAs');
    expect(runner.calls).toEqual([]);
  });

  it('marks a warning-only scan as incomplete and preserves diagnostics', async () => {
    const core = new FakeCore({ install: 'false' });
    const runner = new FakeRunner([
      result(
        0,
        JSON.stringify({
          version: '1',
          summary: {
            files_scanned: 1,
            finding_count: 0,
            suppressed_count: 0,
            by_severity: { low: 0, medium: 0, high: 0 },
          },
          findings: [],
          warnings: ['tests/test_broken.py could not be parsed'],
        }),
      ),
    ]);

    await runAction(core, runner);

    expect(core.outputs.get('outcome')).toBe('incomplete');
    expect(core.outputs.get('result')).toContain('could not be parsed');
    expect(core.annotations).toHaveLength(2);
    expect(core.annotations[0]?.level).toBe('warning');
    expect(core.annotations[0]?.message).toContain('parsed');
  });

  it('annotates a threshold failure before failing the action', async () => {
    const core = new FakeCore({ install: 'false', 'fail-on': 'medium' });
    const runner = new FakeRunner([result(1, findingReport, 'diagnostic detail')]);

    await runAction(core, runner);

    expect(core.annotations).toHaveLength(1);
    expect(core.annotations[0]).toMatchObject({
      level: 'warning',
      message: 'A strict assertion became permissive.',
    });
    expect(core.annotations[0]?.properties).toMatchObject({
      file: 'tests/test_service.py',
      startLine: 8,
    });
    expect(core.outputs.get('outcome')).toBe('threshold-failed');
    expect(core.outputs.get('medium-count')).toBe(1);
    expect(core.outputs.get('result')).toContain('TS003');
    expect(core.failed[0]).toContain("'medium' failure threshold was met");
    expect(core.debugMessages).toContain('diagnostic detail');
  });

  it('reports CLI usage errors without attempting to parse stdout', async () => {
    const core = new FakeCore({ install: 'false' });
    const runner = new FakeRunner([result(2, '', 'bad configuration')]);

    await runAction(core, runner);

    expect(core.outputs.get('outcome')).toBe('error');
    expect(core.failed.at(-1)).toContain('exit code 2: bad configuration');
    expect(core.annotations).toEqual([]);
  });

  it('preserves a structured incomplete report from a blocking scan', async () => {
    const incompleteReport = JSON.stringify({
      version: '1',
      summary: {
        files_scanned: 1,
        finding_count: 0,
        suppressed_count: 0,
        by_severity: { low: 0, medium: 0, high: 0 },
      },
      findings: [],
      warnings: ['tests/test_broken.py could not be parsed'],
    });
    const core = new FakeCore({ install: 'false', 'fail-on': 'high' });
    const runner = new FakeRunner([result(2, incompleteReport)]);

    await runAction(core, runner);

    expect(core.outputs.get('outcome')).toBe('incomplete');
    expect(core.outputs.get('result')).toContain('could not be parsed');
    expect(core.annotations.some((annotation) => annotation.level === 'warning')).toBe(true);
    expect(core.failed.at(-1)).toContain('could not complete a blocking scan');
  });

  it('fails safely on malformed success output', async () => {
    const core = new FakeCore({ install: 'false' });
    const runner = new FakeRunner([result(0, 'this is not json')]);

    await runAction(core, runner);

    expect(core.outputs.get('outcome')).toBe('error');
    expect(core.failed.at(-1)).toContain('invalid JSON');
  });

  it.each([
    ['missing schema fields', '{}', 'missing schema version'],
    [
      'unsupported schema version',
      JSON.stringify({
        version: '999',
        summary: {
          files_scanned: 0,
          finding_count: 0,
          suppressed_count: 0,
          by_severity: { low: 0, medium: 0, high: 0 },
        },
        findings: [],
      }),
      "unsupported schema version '999'",
    ],
    [
      'inconsistent summary',
      JSON.stringify({
        version: '1',
        summary: {
          files_scanned: 1,
          finding_count: 0,
          suppressed_count: 0,
          by_severity: { low: 0, medium: 0, high: 0 },
        },
        findings: [
          {
            rule_id: 'TS003',
            title: 'Assertion weakened',
            message: 'A strict assertion became permissive.',
            severity: 'high',
            confidence: 'high',
            path: 'tests/test_service.py',
            line: 8,
            column: 1,
            fingerprint: '0123456789abcdef01234567',
          },
        ],
      }),
      'inconsistent summary',
    ],
  ])('fails closed on %s', async (_name, report, message) => {
    const core = new FakeCore({ install: 'false' });
    const runner = new FakeRunner([result(0, report)]);

    await runAction(core, runner);

    expect(core.outputs.get('outcome')).toBe('error');
    expect(core.outputs.get('finding-count')).toBeUndefined();
    expect(core.annotations).toEqual([]);
    expect(core.failed.at(-1)).toContain(message);
  });

  it('stops when installation fails', async () => {
    const core = new FakeCore();
    const runner = new FakeRunner([result(1, '', 'No matching distribution')]);

    await runAction(core, runner, {
      eventName: 'push',
      eventPayload: {},
    });

    expect(runner.calls).toHaveLength(1);
    expect(runner.calls[0]?.args.at(-1)).toBe(resolve('..', '..'));
    expect(core.failed.at(-1)).toContain('installation failed');
    expect(core.groups).toEqual(['start:Install TestSeal', 'end']);
  });

  it('converts process start errors into an action failure', async () => {
    const core = new FakeCore({ install: 'false' });
    const runner = new FakeRunner([new CommandError("Unable to start 'python': not found")]);

    await runAction(core, runner);

    expect(core.outputs.get('outcome')).toBe('error');
    expect(core.failed).toEqual(["Unable to start 'python': not found"]);
  });
});
