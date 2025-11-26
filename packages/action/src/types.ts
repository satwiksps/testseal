import type { AnnotationProperties, InputOptions } from '@actions/core';

export type Severity = 'low' | 'medium' | 'high';
export type FailOn = 'never' | Severity;
export type Outcome = 'clean' | 'findings' | 'incomplete' | 'threshold-failed' | 'error';

export interface ActionInputs {
  readonly base?: string;
  readonly head?: string;
  readonly staged: boolean;
  readonly config?: string;
  readonly paths: readonly string[];
  readonly failOn?: FailOn;
  readonly pythonCommand: string;
  readonly install: boolean;
}

export interface Finding {
  readonly ruleId: string;
  readonly title: string;
  readonly message: string;
  readonly severity: Severity;
  readonly confidence?: string | number;
  readonly path?: string;
  readonly line?: number;
  readonly column?: number;
  readonly endLine?: number;
  readonly evidence?: string;
  readonly remediation?: string;
  readonly helpUri?: string;
  readonly fingerprint?: string;
}

export interface ReportSummary {
  readonly filesScanned: number;
  readonly findingCount: number;
  readonly suppressedCount?: number;
  readonly bySeverity: Readonly<Record<Severity, number>>;
}

export interface TestSealReport {
  readonly version: string;
  readonly summary: ReportSummary;
  readonly findings: readonly Finding[];
  readonly warnings: readonly string[];
}

export interface CommandResult {
  readonly exitCode: number;
  readonly stdout: string;
  readonly stderr: string;
}

export interface CommandRunner {
  run(command: string, args: readonly string[]): Promise<CommandResult>;
}

export interface CoreApi {
  getInput(name: string, options?: InputOptions): string;
  getMultilineInput(name: string, options?: InputOptions): string[];
  debug(message: string): void;
  info(message: string): void;
  notice(message: string, properties?: AnnotationProperties): void;
  warning(message: string, properties?: AnnotationProperties): void;
  error(message: string, properties?: AnnotationProperties): void;
  setOutput(name: string, value: unknown): void;
  setFailed(message: string | Error): void;
  startGroup(name: string): void;
  endGroup(): void;
}
