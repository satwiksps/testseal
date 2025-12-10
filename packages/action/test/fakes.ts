import type { AnnotationProperties } from '@actions/core';

import type { CommandResult, CommandRunner, CoreApi } from '../src/types';

export interface AnnotationCall {
  readonly level: 'notice' | 'warning' | 'error';
  readonly message: string;
  readonly properties?: AnnotationProperties;
}

export class FakeCore implements CoreApi {
  readonly annotations: AnnotationCall[] = [];
  readonly debugMessages: string[] = [];
  readonly infoMessages: string[] = [];
  readonly failed: string[] = [];
  readonly groups: string[] = [];
  readonly outputs = new Map<string, unknown>();

  constructor(private readonly inputs: Readonly<Record<string, string>> = {}) {}

  getInput(name: string): string {
    return this.inputs[name] ?? '';
  }

  getMultilineInput(name: string): string[] {
    const value = this.getInput(name);
    return value === '' ? [] : value.split(/\r?\n/u);
  }

  debug(message: string): void {
    this.debugMessages.push(message);
  }

  info(message: string): void {
    this.infoMessages.push(message);
  }

  notice(message: string, properties?: AnnotationProperties): void {
    this.annotations.push({
      level: 'notice',
      message,
      ...(properties === undefined ? {} : { properties }),
    });
  }

  warning(message: string, properties?: AnnotationProperties): void {
    this.annotations.push({
      level: 'warning',
      message,
      ...(properties === undefined ? {} : { properties }),
    });
  }

  error(message: string, properties?: AnnotationProperties): void {
    this.annotations.push({
      level: 'error',
      message,
      ...(properties === undefined ? {} : { properties }),
    });
  }

  setOutput(name: string, value: unknown): void {
    this.outputs.set(name, value);
  }

  setFailed(message: string | Error): void {
    this.failed.push(message instanceof Error ? message.message : message);
  }

  startGroup(name: string): void {
    this.groups.push(`start:${name}`);
  }

  endGroup(): void {
    this.groups.push('end');
  }
}

export class FakeRunner implements CommandRunner {
  readonly calls: { readonly command: string; readonly args: readonly string[] }[] = [];

  constructor(private readonly responses: (CommandResult | Error)[]) {}

  async run(command: string, args: readonly string[]): Promise<CommandResult> {
    this.calls.push({ command, args: [...args] });
    const response = this.responses.shift();
    if (response === undefined) throw new Error('No fake command response was configured.');
    if (response instanceof Error) throw response;
    return Promise.resolve(response);
  }
}

export function result(exitCode: number, stdout = '', stderr = ''): CommandResult {
  return { exitCode, stdout, stderr };
}
