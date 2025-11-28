import { describe, expect, it } from 'vitest';

import { InputError, readInputs } from '../src/inputs';
import { FakeCore } from './fakes';

describe('readInputs', () => {
  it('defers the failure policy to core configuration by default', () => {
    expect(readInputs(new FakeCore())).toEqual({
      staged: false,
      paths: [],
      pythonCommand: 'python',
      install: true,
    });
  });

  it('reads refs, config, booleans, and newline-delimited paths', () => {
    const inputs = readInputs(
      new FakeCore({
        base: ' origin/main ',
        head: 'HEAD~1',
        staged: 'false',
        config: 'config/testseal.toml',
        paths: 'tests/unit\npath with spaces/test_file.py\n\n',
        'fail-on': 'Medium',
        'python-command': 'C:\\Program Files\\Python\\python.exe',
        install: 'false',
      }),
    );

    expect(inputs).toEqual({
      base: 'origin/main',
      head: 'HEAD~1',
      staged: false,
      config: 'config/testseal.toml',
      paths: ['tests/unit', 'path with spaces/test_file.py'],
      failOn: 'medium',
      pythonCommand: 'C:\\Program Files\\Python\\python.exe',
      install: false,
    });
  });

  it('rejects staged mode combined with either revision input', () => {
    expect(() => readInputs(new FakeCore({ staged: 'true', base: 'main' }))).toThrow(
      'cannot be combined',
    );
    expect(() => readInputs(new FakeCore({ staged: 'true', head: 'HEAD~1' }))).toThrow(InputError);
  });

  it.each([
    ['staged', 'yes', "Input 'staged' must be either 'true' or 'false'."],
    ['install', '1', "Input 'install' must be either 'true' or 'false'."],
    ['fail-on', 'critical', "Input 'fail-on' must be one of"],
    ['python-command', 'python\nmalicious', "Input 'python-command' must be"],
  ])('rejects invalid %s input', (name, value, message) => {
    expect(() => readInputs(new FakeCore({ [name]: value }))).toThrow(message);
    expect(() => readInputs(new FakeCore({ [name]: value }))).toThrow(InputError);
  });
});
