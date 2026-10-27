import { execFile } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const helper = fileURLToPath(new URL('../scripts/prime_hooks.py', import.meta.url));

function runHook(action, payload) {
  return new Promise((resolve, reject) => {
    const child = execFile('python3', [helper, action], { timeout: 5000, maxBuffer: 1024 * 1024 }, (error, stdout, stderr) => {
      if (error || stderr) {
        reject(new Error('Prime lifecycle helper unavailable. Check Python 3.10+ and load policies through the skill.'));
        return;
      }
      try {
        resolve(JSON.parse(stdout));
      } catch {
        reject(new Error('Prime lifecycle helper returned invalid output.'));
      }
    });
    child.stdin.on('error', () => {}); // execFile reports child startup/exit failures.
    child.stdin.end(JSON.stringify(payload));
  });
}

export const PrimeSecurityDev = async ({ directory }) => {
  const response = await runHook('reminder', { hook_event_name: 'UserPromptSubmit' });
  const reminder = response.hookSpecificOutput.additionalContext;
  return {
    'experimental.chat.system.transform': async (_input, output) => {
      output.system.push(reminder);
    },
    'experimental.session.compacting': async (_input, output) => {
      output.context.push(reminder);
    },
    'tool.execute.after': async (input) => {
      if (!['write', 'edit', 'apply_patch', 'applypatch'].includes(input.tool)) return;
      const args = input.args ?? {};
      const toolInput = ['apply_patch', 'applypatch'].includes(input.tool)
        ? { patchText: args.patchText }
        : { filePath: args.filePath };
      try {
        await runHook('track', {
          session_id: input.sessionID, cwd: directory, tool_name: input.tool, tool_input: toolInput,
        });
      } catch {
        // Local telemetry is best-effort and never blocks a completed edit.
        console.error('Prime edit tracking unavailable; review the final diff directly.');
      }
    },
  };
};
