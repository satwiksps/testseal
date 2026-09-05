import { writeFile, unlink } from 'node:fs/promises';
import { basename, dirname, resolve } from 'node:path';

import { describe, expect, it, vi } from 'vitest';

import { CommandError, NodeCommandRunner } from '../src/process';

describe('NodeCommandRunner', () => {
  it('removes Python startup overrides from the environment inherited by installer children', async () => {
    vi.stubEnv('PYTHONPATH', 'untrusted');
    vi.stubEnv('PYTHONHOME', 'untrusted');
    vi.stubEnv('TESTSEAL_RUNNER_TEST', 'preserved');
    try {
      const result = await new NodeCommandRunner().run(process.execPath, [
        '-p',
        'JSON.stringify([process.env.PYTHONPATH, process.env.PYTHONHOME, process.env.TESTSEAL_RUNNER_TEST])',
      ]);
      expect(result.exitCode).toBe(0);
      expect(JSON.parse(result.stdout)).toEqual([null, null, 'preserved']);
    } finally {
      vi.unstubAllEnvs();
    }
  });

  it.runIf(process.platform === 'win32')(
    'uses the PATH executable even when a file of the same name exists in the checkout',
    async () => {
      const command = basename(process.execPath);
      const checkoutExecutable = resolve(command);
      await writeFile(checkoutExecutable, 'This is untrusted checkout content', { flag: 'wx' });
      try {
        vi.stubEnv('PATH', dirname(process.execPath));
        const result = await new NodeCommandRunner().run(command, ['-p', '6 * 7']);
        expect(result.exitCode).toBe(0);
        expect(result.stdout.trim()).toBe('42');
      } finally {
        vi.unstubAllEnvs();
        await unlink(checkoutExecutable);
      }
    },
  );

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
