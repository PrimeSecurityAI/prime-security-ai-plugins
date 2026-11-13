// Pi extension (@earendil-works/pi-coding-agent). Loaded from the repository's root package.json.
const reminder = 'Use the prime-code-guardrails skill before meaningful coding actions. Check fresh settings before using guidance and before every plan, retry or completion. Discard reusable guidance after confirmed disable; ordinary coding continues when disabled or settings are unavailable. This reminder does not fetch settings or capture plans.';

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
