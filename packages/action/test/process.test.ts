import { describe, expect, it } from 'vitest';

import { CommandError, NodeCommandRunner } from '../src/process';

describe('NodeCommandRunner', () => {
  it('captures stdout, stderr, and a nonzero exit code without a shell', async () => {
    const runner = new NodeCommandRunner();

    const result = await runner.run(process.execPath, [
      '-e',
      "process.stdout.write('path with spaces'); process.stderr.write('diagnostic'); process.exit(7)",
    ]);

    expect(result).toEqual({
      exitCode: 7,
      stdout: 'path with spaces',
      stderr: 'diagnostic',
    });
  });

  it('wraps executable launch errors', async () => {
    const runner = new NodeCommandRunner();
    const missing = `definitely-missing-testseal-command-${process.pid}`;

    await expect(runner.run(missing, [])).rejects.toThrow(CommandError);
    await expect(runner.run(missing, [])).rejects.toThrow(`Unable to start '${missing}'`);
  });
});
