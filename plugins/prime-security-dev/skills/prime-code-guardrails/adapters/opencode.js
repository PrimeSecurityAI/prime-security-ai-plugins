// OpenCode 2.x server plugin (@opencode/cli). No runtime dependencies; `Plugin.define` is an identity helper.
const reminder = 'Use the prime-code-guardrails skill before meaningful coding actions. Check capabilities first: explicit false uses account-wide guidance; true requires fresh settings before managed security work and reviewer dispatch. Discard reusable managed guidance after its confirmed disable. Capability, core-policy or managed API errors pause security work; ordinary coding continues. This reminder makes no API calls or plan captures.';

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
