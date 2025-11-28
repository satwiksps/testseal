import type { ActionInputs, CoreApi, FailOn } from './types';

const FAIL_ON_VALUES = new Set<FailOn>(['never', 'low', 'medium', 'high']);

export class InputError extends Error {
  override readonly name = 'InputError';
}

function optionalInput(core: CoreApi, name: string): string | undefined {
  const value = core.getInput(name).trim();
  return value === '' ? undefined : value;
}

function booleanInput(core: CoreApi, name: string, defaultValue: boolean): boolean {
  const raw = core.getInput(name).trim().toLowerCase();
  if (raw === '') return defaultValue;
  if (raw === 'true') return true;
  if (raw === 'false') return false;
  throw new InputError(`Input '${name}' must be either 'true' or 'false'.`);
}

function failOnInput(core: CoreApi): FailOn | undefined {
  const raw = optionalInput(core, 'fail-on');
  if (raw === undefined) return undefined;
  const value = raw.toLowerCase();
  if (!FAIL_ON_VALUES.has(value as FailOn)) {
    throw new InputError("Input 'fail-on' must be one of: never, low, medium, high.");
  }
  return value as FailOn;
}

function pythonCommandInput(core: CoreApi): string {
  const command = optionalInput(core, 'python-command') ?? 'python';
  if (command.includes('\0') || command.includes('\n') || command.includes('\r')) {
    throw new InputError("Input 'python-command' must be a single executable name or path.");
  }
  return command;
}

export function readInputs(core: CoreApi): ActionInputs {
  const base = optionalInput(core, 'base');
  const head = optionalInput(core, 'head');
  const config = optionalInput(core, 'config');
  const staged = booleanInput(core, 'staged', false);
  const failOn = failOnInput(core);
  const paths = core
    .getMultilineInput('paths')
    .map((path) => path.trim())
    .filter((path) => path !== '');

  if (staged && (base !== undefined || head !== undefined)) {
    throw new InputError("Input 'staged' cannot be combined with 'base' or 'head'.");
  }

  return {
    ...(base === undefined ? {} : { base }),
    ...(head === undefined ? {} : { head }),
    staged,
    ...(config === undefined ? {} : { config }),
    paths,
    ...(failOn === undefined ? {} : { failOn }),
    pythonCommand: pythonCommandInput(core),
    install: booleanInput(core, 'install', true),
  };
}
