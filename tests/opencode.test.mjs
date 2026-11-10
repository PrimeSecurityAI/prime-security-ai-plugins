import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const adapter = new URL('../plugins/prime-security-dev/skills/prime-code-guardrails/adapters/opencode.js', import.meta.url);
const hooksScript = new URL('../plugins/prime-security-dev/skills/prime-code-guardrails/scripts/prime_hooks.py', import.meta.url);

async function setUp() {
  const { default: plugin } = await import(adapter);
  const hooks = new Map();
  let disposed = 0;
  const ctx = {
    session: {
      hook: async (name, callback) => {
        hooks.set(name, callback);
        return { dispose: async () => { disposed += 1; } };
      },
    },
  };
  const cleanup = await plugin.setup(ctx);
  return { plugin, hooks, cleanup, disposed: () => disposed };
}

test('OpenCode v2 plugin has the required default definition and starts without Python', async () => {
  const previous = process.env.PATH;
  process.env.PATH = '';
  try {
    const { plugin, hooks } = await setUp();
    assert.equal(plugin.id, 'prime-security-dev');
    assert.deepEqual([...hooks.keys()], ['context']);
  } finally {
    process.env.PATH = previous;
  }
});

test('OpenCode v2 adds one reminder to each freshly built request', async () => {
  const { hooks } = await setUp();
  const context = hooks.get('context');
  const request = { sessionID: 'one', system: [{ type: 'text', text: 'existing' }], messages: [] };
  await context(request);
  assert.equal(request.system[0].text, 'existing');
  assert.equal(request.system.length, 2);
  assert.equal(request.system[1].type, 'text');
  assert.match(request.system[1].text, /prime-code-guardrails/);
  const next = { sessionID: 'one', system: [], messages: [] };
  await context(next);
  assert.equal(next.system.length, 1);
});

test('OpenCode v2 cleanup disposes the hook', async () => {
  const { cleanup, disposed } = await setUp();
  await cleanup();
  assert.equal(disposed(), 1);
});

test('OpenCode reminder matches the shared hook reminder', async () => {
  const [adapterSource, script] = await Promise.all([readFile(adapter, 'utf8'), readFile(hooksScript, 'utf8')]);
  const pythonReminder = script.match(/REMINDER = \(([\s\S]*?)\)\n/)[1].match(/'([^']*)'/g).map((part) => part.slice(1, -1)).join('');
  assert.ok(adapterSource.includes(`'${pythonReminder}'`));
});
