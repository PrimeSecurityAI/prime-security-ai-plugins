// OpenCode 2.x server plugin (@opencode/cli). No runtime dependencies; `Plugin.define` is an identity helper.
const reminder = 'Use the prime-code-guardrails skill before meaningful coding actions. Check fresh settings before using guidance and before every plan, retry or completion. Discard reusable guidance after confirmed disable; ordinary coding continues when disabled or settings are unavailable. This reminder does not fetch settings or capture plans.';

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
