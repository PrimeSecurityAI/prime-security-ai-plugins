# prime-security-operator

Interact with Prime Security's platform API — run security design reviews, search knowledge base policies, analyze code repositories, perform code reviews, and have AI-assisted security conversations.

## Configuration

| Variable | Required | Description |
|---|---|---|
| `PRIME_PAT_TOKEN` | Yes | Prime Security Personal Access Token |

To generate a PAT token, go to the Prime Security platform: **Settings > Access > API Token > Create Token**.

## Skill: `prime`

Trigger with: `"prime"`, `"security review"`, `"design doc"`, `"knowledge base"`, `"policy search"`, `"code analysis"`, `"code review"`.

The skill fetches the live API contract from `/llm.txt` on every invocation, so it always uses up-to-date endpoints and schemas. All interactions follow an async request/poll flow authenticated via your PAT token.

**Examples:**

- "Run a security review on this design doc"
- "Search the knowledge base for our password policy"
- "Analyze the authentication service repository"
- "Start a code review for the changes on this branch"

## License

MIT
