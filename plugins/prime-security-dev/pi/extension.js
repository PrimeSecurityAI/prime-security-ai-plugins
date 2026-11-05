// Pi extension (@earendil-works/pi-coding-agent). Loaded from the repository's root package.json.
const reminder = 'Use the prime-code-guardrails skill before changing code. Load policies once for an independent coding task; follow-up messages in that task reuse the full policy context. Reload after repository, account, or API origin changes, or when compaction loses policy text. This reminder does not mean policies have been loaded.';

export default function primeSecurityDev(pi) {
  // Runs before each agent run. Pi patches only changed sections, so an unchanged reminder keeps
  // the prompt cache, and the section is rebuilt after compaction. Skip it when the skill is
  // disabled (for example `--no-skills`) so the model is never pointed at a missing skill.
  pi.on('before_agent_start', (event) => {
    const options = event.systemPromptOptions;
    if (options.skills.some((skill) => skill.name === 'prime-code-guardrails')) {
      options.sections.prime_guardrails = reminder;
    } else {
      delete options.sections.prime_guardrails;
    }
  });
}
