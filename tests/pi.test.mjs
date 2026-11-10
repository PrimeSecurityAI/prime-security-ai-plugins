import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const repo = new URL('../', import.meta.url);
const extension = new URL('plugins/prime-security-dev/pi/extension.js', repo);

async function startRun(skills, sections = {}) {
  const { default: register } = await import(extension);
  const handlers = new Map();
  register({ on: (name, handler) => handlers.set(name, handler) });
  assert.deepEqual([...handlers.keys()], ['before_agent_start']);
  const event = { systemPromptOptions: { skills, sections } };
  const result = await handlers.get('before_agent_start')(event);
  return { event, result };
}

test('Pi adds a guardrails section when the skill is loaded', async () => {
  const { event, result } = await startRun([{ name: 'prime-code-guardrails' }], { existing: 'kept' });
  assert.equal(result, undefined); // mutate sections; never replace the whole prompt
  assert.equal(event.systemPromptOptions.sections.existing, 'kept');
  assert.match(event.systemPromptOptions.sections.prime_guardrails, /prime-code-guardrails/);
});

test('Pi omits the section when the skill is unavailable', async () => {
  const { event } = await startRun([], { prime_guardrails: 'stale' });
  assert.equal('prime_guardrails' in event.systemPromptOptions.sections, false);
});

test('Pi package points at the extension and the guardrails skill', async () => {
  const manifest = JSON.parse(await readFile(new URL('package.json', repo), 'utf8'));
  const plugin = JSON.parse(await readFile(new URL('plugins/prime-security-dev/.claude-plugin/plugin.json', repo), 'utf8'));
  assert.equal(manifest.private, true);
  assert.equal(manifest.version, plugin.version);
  assert.deepEqual(manifest.pi, {
    extensions: ['./plugins/prime-security-dev/pi/extension.js'],
    skills: ['./plugins/prime-security-dev/skills'],
  });
  assert.equal(manifest.dependencies, undefined); // Pi supplies its own packages
  await readFile(new URL('plugins/prime-security-dev/skills/prime-code-guardrails/SKILL.md', repo));
});

test('Pi reminder matches the shared hook reminder', async () => {
  const [source, script] = await Promise.all([
    readFile(extension, 'utf8'),
    readFile(new URL('plugins/prime-security-dev/skills/prime-code-guardrails/scripts/prime_hooks.py', repo), 'utf8'),
  ]);
  const pythonReminder = script.match(/REMINDER = \(([\s\S]*?)\)\n/)[1].match(/'([^']*)'/g).map((part) => part.slice(1, -1)).join('');
  assert.ok(source.includes(`'${pythonReminder}'`));
});
