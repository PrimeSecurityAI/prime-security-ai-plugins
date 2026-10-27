const reminder = 'Use the prime-code-guardrails skill before changing code. Load policies once for an independent coding task; follow-up messages reuse the full policy context. Reload after repository, account, or API origin changes, or when compaction loses policy text. This reminder does not mean policies have been loaded.';

export const PrimeSecurityDev = async () => {
  const reminded = new Set();
  return {
    'experimental.chat.system.transform': async (input, output) => {
      if (!input.sessionID || reminded.has(input.sessionID)) return;
      output.system.push(reminder);
      reminded.add(input.sessionID);
    },
    'experimental.session.compacting': async (input, output) => {
      output.context.push(reminder);
      reminded.delete(input.sessionID);
    },
    event: async ({ event }) => {
      if (event.type === 'session.deleted') reminded.delete(event.properties.info.id);
    },
  };
};
