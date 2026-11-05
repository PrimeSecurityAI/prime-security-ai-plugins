// OpenCode 2.x server plugin (@opencode/cli). No runtime dependencies; `Plugin.define` is an identity helper.
const reminder = 'Use the prime-code-guardrails skill before changing code. Load policies once for an independent coding task; follow-up messages in that task reuse the full policy context. Reload after repository, account, or API origin changes, or when compaction loses policy text. This reminder does not mean policies have been loaded.';

export default {
  id: 'prime-security-dev',
  async setup(ctx) {
    // `context` runs before every agent-loop model call, including tool continuations and the
    // first request after compaction, on a freshly built system array.
    const registration = await ctx.session.hook('context', (request) => {
      request.system.push({ type: 'text', text: reminder });
    });
    return () => registration.dispose();
  },
};
