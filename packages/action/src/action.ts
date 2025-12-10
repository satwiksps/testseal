import { existsSync } from 'node:fs';
import { resolve } from 'node:path';

import { context as githubContext } from '@actions/github';

import { InputError, readInputs } from './inputs';
import { CommandError, NodeCommandRunner } from './process';
import { emitAnnotations, parseReport, ReportError, serializeReport } from './report';
import type {
  ActionInputs,
  CommandResult,
  CommandRunner,
  CoreApi,
  Outcome,
  TestSealReport,
} from './types';

type FileExists = (path: string) => boolean;

export interface ActionRuntime {
  readonly eventName: string;
  readonly eventPayload: unknown;
}

const DEFAULT_RUNTIME: ActionRuntime = {
  eventName: githubContext.eventName,
  eventPayload: githubContext.payload,
};
const BUNDLED_PROJECT_ROOT = resolve(__dirname, '..', '..', '..');

function record(value: unknown): Record<string, unknown> | undefined {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function sha(value: unknown): string | undefined {
  return typeof value === 'string' && /^[0-9a-f]{40,64}$/iu.test(value) ? value : undefined;
}

export function withEventRefs(
  inputs: ActionInputs,
  eventName: string = githubContext.eventName,
  eventPayload: unknown = githubContext.payload,
): ActionInputs {
  if (inputs.staged || inputs.base !== undefined || inputs.head !== undefined) return inputs;

  if (eventName !== 'pull_request' && eventName !== 'merge_group') return inputs;
  const event = record(eventPayload);
  if (event === undefined) {
    throw new InputError(`The '${eventName}' payload is not an object.`);
  }

  let base: string | undefined;
  let head: string | undefined;
  if (eventName === 'pull_request') {
    const pullRequest = record(event.pull_request);
    base = sha(record(pullRequest?.base)?.sha);
    head = sha(record(pullRequest?.head)?.sha);
  } else {
    const mergeGroup = record(event.merge_group);
    base = sha(mergeGroup?.base_sha);
    head = sha(mergeGroup?.head_sha);
  }
  if (base === undefined || head === undefined) {
    throw new InputError(`The '${eventName}' payload does not contain usable base/head SHAs.`);
  }
  return { ...inputs, base, head };
}

function testSealArgs(inputs: ActionInputs): string[] {
  return [
    '-m',
    'testseal',
    'scan',
    '--format',
    'json',
    ...(inputs.failOn === undefined ? [] : ['--fail-on', inputs.failOn]),
    ...(inputs.base === undefined ? [] : ['--base', inputs.base]),
    ...(inputs.head === undefined ? [] : ['--head', inputs.head]),
    ...(inputs.staged ? ['--staged'] : []),
    ...(inputs.config === undefined ? [] : ['--config', inputs.config]),
    ...(inputs.paths.length === 0 ? [] : ['--', ...inputs.paths]),
  ];
}

export function findLocalTestSeal(
  bundledRoot: string = BUNDLED_PROJECT_ROOT,
  fileExists: FileExists = existsSync,
): string | undefined {
  return fileExists(resolve(bundledRoot, 'pyproject.toml')) ? bundledRoot : undefined;
}

export function installArgs(
  bundledRoot: string = BUNDLED_PROJECT_ROOT,
  fileExists: FileExists = existsSync,
): string[] {
  const localPackage = findLocalTestSeal(bundledRoot, fileExists);
  if (localPackage === undefined) {
    throw new CommandError(
      'The bundled TestSeal Python package is missing. Pin a complete TestSeal release or set install: false after installing TestSeal yourself.',
    );
  }
  return ['-m', 'pip', 'install', '--disable-pip-version-check', '--no-input', localPackage];
}

function lastUsefulOutput(result: CommandResult): string {
  const output = result.stderr.trim() || result.stdout.trim();
  if (output === '') return '';
  const maximum = 2_000;
  return output.length <= maximum ? output : `...${output.slice(-maximum)}`;
}

function errorMessage(error: unknown): string {
  if (
    error instanceof InputError ||
    error instanceof ReportError ||
    error instanceof CommandError
  ) {
    return error.message;
  }
  if (error instanceof Error) return `Unexpected action error: ${error.message}`;
  return 'Unexpected action error.';
}

function setSummaryOutputs(core: CoreApi, report: TestSealReport, outcome: Outcome): void {
  core.setOutput('finding-count', report.summary.findingCount);
  core.setOutput('high-count', report.summary.bySeverity.high);
  core.setOutput('medium-count', report.summary.bySeverity.medium);
  core.setOutput('low-count', report.summary.bySeverity.low);
  core.setOutput('files-scanned', report.summary.filesScanned);
  core.setOutput('suppressed-count', report.summary.suppressedCount ?? 0);
  core.setOutput('outcome', outcome);
  core.setOutput('result', serializeReport(report));
}

async function installTestSeal(
  core: CoreApi,
  runner: CommandRunner,
  inputs: ActionInputs,
): Promise<void> {
  core.startGroup('Install TestSeal');
  try {
    const args = installArgs();
    core.info('Installing TestSeal from the source bundled with this Action release.');
    const result = await runner.run(inputs.pythonCommand, args);
    if (result.exitCode !== 0) {
      const detail = lastUsefulOutput(result);
      throw new CommandError(
        `TestSeal installation failed with exit code ${result.exitCode}${detail === '' ? '.' : `: ${detail}`}`,
      );
    }
    if (result.stderr.trim() !== '') core.debug(result.stderr.trim());
  } finally {
    core.endGroup();
  }
}

async function scan(core: CoreApi, runner: CommandRunner, inputs: ActionInputs): Promise<void> {
  core.startGroup('Run TestSeal');
  let result: CommandResult;
  try {
    result = await runner.run(inputs.pythonCommand, testSealArgs(inputs));
  } finally {
    core.endGroup();
  }

  if (result.stderr.trim() !== '') core.debug(result.stderr.trim());

  let report: TestSealReport;
  if (result.exitCode === 0 || result.exitCode === 1) {
    report = parseReport(result.stdout);
  } else if (result.exitCode === 2 && result.stdout.trim() !== '') {
    try {
      report = parseReport(result.stdout);
    } catch {
      core.setOutput('outcome', 'error');
      const detail = lastUsefulOutput(result);
      throw new CommandError(
        `TestSeal scan failed with exit code ${result.exitCode}${detail === '' ? '.' : `: ${detail}`}`,
      );
    }
    if (report.warnings.length === 0) {
      throw new CommandError('TestSeal returned exit code 2 without an incomplete-scan warning.');
    }
    emitAnnotations(core, report);
    setSummaryOutputs(core, report, 'incomplete');
    core.setFailed(
      `TestSeal could not complete a blocking scan because ${report.warnings.length} file(s) produced warnings.`,
    );
    return;
  } else {
    core.setOutput('outcome', 'error');
    const detail = lastUsefulOutput(result);
    throw new CommandError(
      `TestSeal scan failed with exit code ${result.exitCode}${detail === '' ? '.' : `: ${detail}`}`,
    );
  }

  emitAnnotations(core, report);
  const outcome: Outcome =
    result.exitCode === 1
      ? 'threshold-failed'
      : report.warnings.length > 0
        ? 'incomplete'
        : report.summary.findingCount === 0
          ? 'clean'
          : 'findings';
  setSummaryOutputs(core, report, outcome);
  core.info(
    `TestSeal scanned ${report.summary.filesScanned} file(s) and found ${report.summary.findingCount} issue(s): ` +
      `${report.summary.bySeverity.high} high, ${report.summary.bySeverity.medium} medium, ${report.summary.bySeverity.low} low.`,
  );
  if (report.warnings.length > 0) {
    core.warning(`TestSeal completed with ${report.warnings.length} scan warning(s).`);
  }

  if (result.exitCode === 1) {
    core.setFailed(
      `TestSeal found ${report.summary.findingCount} issue(s) and the ${
        inputs.failOn === undefined ? 'configured' : `'${inputs.failOn}'`
      } failure threshold was met.`,
    );
  }
}

export async function runAction(
  core: CoreApi,
  runner: CommandRunner = new NodeCommandRunner(),
  runtime: ActionRuntime = DEFAULT_RUNTIME,
): Promise<void> {
  try {
    const inputs = withEventRefs(readInputs(core), runtime.eventName, runtime.eventPayload);
    if (inputs.install) await installTestSeal(core, runner, inputs);
    await scan(core, runner, inputs);
  } catch (error) {
    core.setOutput('outcome', 'error');
    core.setFailed(errorMessage(error));
  }
}
