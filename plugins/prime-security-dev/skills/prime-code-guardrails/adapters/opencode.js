const reminder = 'Use the prime-code-guardrails skill before changing code. Load policies once for an independent coding task; follow-up messages reuse the full policy context. Reload after repository, account, or API origin changes, or when compaction loses policy text. This reminder does not mean policies have been loaded.';

export const PrimeSecurityDev = async () => {
  return {
    // OpenCode builds a new system array for each model request, including tool continuations.
    'experimental.chat.system.transform': async (_input, output) => {
      output.system.push(reminder);
    },
    'experimental.session.compacting': async (_input, output) => {
      output.context.push(reminder);
    },
  };
};
