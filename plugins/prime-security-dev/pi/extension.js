// Pi extension (@earendil-works/pi-coding-agent). Loaded from the repository's root package.json.
const reminder = 'Use the prime-developer-security skill before meaningful coding actions: call the Prime MCP tools get_developer_guardrails and get_developer_security_context for the files you will change. Use create_developer_security_plan and start_developer_pr_review only when requested. If the tools are unavailable or disabled, tell the user and continue ordinary coding. This reminder makes no API calls.';

export default function primeSecurityDev(pi) {
  // Runs before each agent run. Pi patches only changed sections, so an unchanged reminder keeps
  // the prompt cache, and the section is rebuilt after compaction. Skip it when the skill is
  // disabled (for example `--no-skills`) so the model is never pointed at a missing skill.
  pi.on('before_agent_start', (event) => {
    const options = event.systemPromptOptions;
    if (options.skills.some((skill) => skill.name === 'prime-developer-security')) {
      options.sections.prime_developer_security = reminder;
    } else {
      delete options.sections.prime_developer_security;
    }
  });
}
