// OpenCode 2.x server plugin (@opencode/cli). No runtime dependencies; `Plugin.define` is an identity helper.
const reminder = 'Use the prime-developer-security skill before meaningful coding actions: call the Prime MCP tools get_developer_security_map once, get_developer_security_files for the files you will change, and get_developer_security_details for the items your change touches. Use create_developer_security_plan and start_developer_pr_review only when requested. If the tools are unavailable or disabled, tell the user and continue ordinary coding.';

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
