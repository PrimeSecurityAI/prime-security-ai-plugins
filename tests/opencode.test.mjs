import assert from 'node:assert/strict';
import { mkdtemp, readFile, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

const adapter = new URL('../plugins/prime-security-dev/skills/prime-code-guardrails/adapters/opencode.js', import.meta.url);

test('OpenCode adds reminders without replacing existing system/compaction context', async () => {
  const { PrimeSecurityDev } = await import(adapter);
  const hooks = await PrimeSecurityDev({ directory: tmpdir() });
  const output = { system: ['existing'] };
  await hooks['experimental.chat.system.transform']({}, output);
  assert.equal(output.system[0], 'existing');
  assert.match(output.system[1], /prime-code-guardrails/);
  const compact = { context: ['existing'], prompt: 'custom' };
  await hooks['experimental.session.compacting']({ sessionID: 'test' }, compact);
  assert.equal(compact.prompt, 'custom');
  assert.match(compact.context[1], /reload/i);
});

test('OpenCode edit adapter writes local telemetry without source contents', async () => {
  const { PrimeSecurityDev } = await import(adapter);
  const directory = await mkdtemp(join(tmpdir(), 'prime-opencode-'));
  const previous = process.env.XDG_STATE_HOME;
  process.env.XDG_STATE_HOME = directory;
  try {
    const hooks = await PrimeSecurityDev({ directory });
    await hooks['tool.execute.after']({ tool: 'write', sessionID: 'test', args: { filePath: 'a.py', content: 'private source' } }, {});
    const files = await readdir(join(directory, 'prime-security'));
    assert.equal(files.length, 1);
    const log = await readFile(join(directory, 'prime-security', files[0]), 'utf8');
    assert.deepEqual(JSON.parse(log).paths, [join(directory, 'a.py')]);
    assert.ok(!log.includes('private source'));
  } finally {
    if (previous === undefined) delete process.env.XDG_STATE_HOME;
    else process.env.XDG_STATE_HOME = previous;
    await rm(directory, { recursive: true, force: true });
  }
});
