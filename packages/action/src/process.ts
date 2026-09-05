import { spawn } from 'node:child_process';

import { which } from '@actions/io';

import type { CommandResult, CommandRunner } from './types';

const MAX_CAPTURE_BYTES = 32 * 1024 * 1024;

export class CommandError extends Error {
  override readonly name = 'CommandError';
}

export class NodeCommandRunner implements CommandRunner {
  async run(command: string, args: readonly string[]): Promise<CommandResult> {
    let executable: string;
    try {
      // Resolve PATH explicitly so Windows cannot select a checkout-local executable.
      executable = await which(command, true);
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      throw new CommandError(`Unable to start '${command}': ${detail}`);
    }
    return new Promise((resolve, reject) => {
      let stdoutBytes = 0;
      let stderrBytes = 0;
      const stdout: Buffer[] = [];
      const stderr: Buffer[] = [];
      let settled = false;

      const child = spawn(executable, [...args], {
        cwd: process.cwd(),
        // pip starts further Python processes which do not inherit the -I flag.
        env: Object.fromEntries(
          Object.entries(process.env).filter(([name]) => !name.toUpperCase().startsWith('PYTHON')),
        ),
        shell: false,
        stdio: ['ignore', 'pipe', 'pipe'],
        windowsHide: true,
      });

      const rejectOnce = (error: Error): void => {
        if (settled) return;
        settled = true;
        reject(error);
      };

      const capture = (
        chunk: Buffer,
        chunks: Buffer[],
        currentBytes: number,
        streamName: string,
      ): number => {
        const nextBytes = currentBytes + chunk.length;
        if (nextBytes > MAX_CAPTURE_BYTES) {
          child.kill();
          rejectOnce(
            new CommandError(
              `TestSeal ${streamName} exceeded the ${MAX_CAPTURE_BYTES / 1024 / 1024} MiB capture limit.`,
            ),
          );
          return nextBytes;
        }
        chunks.push(chunk);
        return nextBytes;
      };

      child.stdout.on('data', (chunk: Buffer) => {
        stdoutBytes = capture(chunk, stdout, stdoutBytes, 'stdout');
      });
      child.stderr.on('data', (chunk: Buffer) => {
        stderrBytes = capture(chunk, stderr, stderrBytes, 'stderr');
      });
      child.on('error', (error) => {
        rejectOnce(new CommandError(`Unable to start '${command}': ${error.message}`));
      });
      child.on('close', (code, signal) => {
        if (settled) return;
        settled = true;
        if (code === null) {
          reject(
            new CommandError(
              `TestSeal process ended without an exit code${signal === null ? '.' : ` (signal ${signal}).`}`,
            ),
          );
          return;
        }
        resolve({
          exitCode: code,
          stdout: Buffer.concat(stdout).toString('utf8'),
          stderr: Buffer.concat(stderr).toString('utf8'),
        });
      });
    });
  }
}
