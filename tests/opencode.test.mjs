import assert from 'node:assert/strict';
import test from 'node:test';

const adapter = new URL('../plugins/prime-security-dev/skills/prime-code-guardrails/adapters/opencode.js', import.meta.url);

test('OpenCode starts without Python and includes guidance in every fresh request', async () => {
  const previous = process.env.PATH;
  process.env.PATH = '';
  try {
    const { PrimeSecurityDev } = await import(adapter);
    const hooks = await PrimeSecurityDev({});
    const output = { system: ['existing'] };
    await hooks['experimental.chat.system.transform']({ sessionID: 'one' }, output);
    assert.equal(output.system[0], 'existing');
    assert.match(output.system[1], /prime-code-guardrails/);
    const next = { system: [] };
    await hooks['experimental.chat.system.transform']({ sessionID: 'one' }, next);
    assert.equal(next.system.length, 1);
    assert.match(next.system[0], /prime-code-guardrails/);
    const another = { system: [] };
    await hooks['experimental.chat.system.transform']({ sessionID: 'two' }, another);
    assert.equal(another.system.length, 1);
    assert.equal(hooks['tool.execute.after'], undefined);
  } finally {
    process.env.PATH = previous;
  }
});

test('OpenCode compaction preserves existing prompt and restores next-turn reminder', async () => {
  const { PrimeSecurityDev } = await import(adapter);
  const hooks = await PrimeSecurityDev({});
  await hooks['experimental.chat.system.transform']({ sessionID: 'one' }, { system: [] });
  const compact = { context: ['existing'], prompt: 'custom' };
  await hooks['experimental.session.compacting']({ sessionID: 'one' }, compact);
  assert.equal(compact.prompt, 'custom');
  assert.match(compact.context[1], /reload/i);
  const output = { system: [] };
  await hooks['experimental.chat.system.transform']({ sessionID: 'one' }, output);
  assert.equal(output.system.length, 1);
});
