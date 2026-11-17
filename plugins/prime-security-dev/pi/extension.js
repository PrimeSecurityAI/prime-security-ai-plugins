// Pi extension (@earendil-works/pi-coding-agent). Loaded from the repository's root package.json.
const reminder = 'Use the prime-code-guardrails skill before meaningful coding actions. Check capabilities first: explicit false uses account-wide guidance; true requires fresh settings before managed security work and reviewer dispatch. Discard reusable managed guidance after its confirmed disable. Capability, core-policy or managed API errors pause security work; ordinary coding continues. This reminder makes no API calls or plan captures.';

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
