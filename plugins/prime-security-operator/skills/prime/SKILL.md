---
name: prime
description: >
  Use when interacting with Prime Security's platform. Covers: security design
  reviews, knowledge base policy search, code repository analysis, code reviews,
  and AI-assisted security conversations via the Prime API. Trigger on: "prime",
  "security review", "design doc", "knowledge base", "policy search", "code analysis",
  "code review".
allowed-tools:
  - Bash(curl *.primesec.*)
  - WebFetch(domain:*.primesec.*)
  - Read(~/.claude/settings.json)
  - Edit(~/.claude/settings.json)
---

# Prime Skill

Prime is Prime Security's platform API for AI-assisted security reviews, policy search, code analysis, and conversational pipelines. It provides security insights through an API that supports template-based conversations with contextual attachments. All interactions are authenticated via a Personal Access Token (PAT) and follow an async request/poll flow.

## Pre-conditions

Complete all steps in order before making any API call.

### a) Environment Variables

| Variable | Description                          |
|---|--------------------------------------|
| `PRIME_PAT_TOKEN` | Prime Security Personal Access Token |
| `PRIME_API_URL` | API base URL (default: `https://api.primesec.ai`) |

If `PRIME_PAT_TOKEN` is not set, you must configure it before proceeding:

1. Use the `AskUserQuestion` tool to prompt the user with the question: "Your PRIME_PAT_TOKEN is not set. How would you like to proceed?" with two options:
   - **"I have my token ready"** — description: "I'll paste my Prime Security Personal Access Token"
   - **"I need to generate a token"** — description: "Direct me to the Prime Security platform to create one"
   If the user selects "I need to generate a token", tell them to go to **Settings → Access → API Token → Create Token** in the Prime Security platform, then re-prompt with the same question.
   If the user selects "I have my token ready" or provides a token via the free-text "Other" option, proceed to step 2 with the provided value.
2. Once the user provides the value, read `~/.claude/settings.json`, add or merge an `"env"` object with `"PRIME_PAT_TOKEN"` set to the provided value, and write it back. Preserve all existing keys in the file. If the file does not exist, create it with `{"env": {"PRIME_PAT_TOKEN": "<value>"}}`.
3. After writing the file, export the variable in the current session so the rest of this workflow can use it immediately: run `export PRIME_PAT_TOKEN='<value>'` (substituting the token the user provided) via Bash before making any API calls.

If `PRIME_API_URL` is not set, default to `https://api.primesec.ai`. If the user provides a custom URL, persist it the same way as above.

### b) Fetch API Documentation

The API documentation is public and does not require authentication:

```
GET {PRIME_API_URL}/llm.txt
```

This returns the authoritative, up-to-date API reference including all endpoints, request/response schemas, and conversation flow instructions. Always fetch this before making any other API calls. Endpoint paths and schemas may change — never assume them.

## Base URL

Read from `PRIME_API_URL` env var. If not set, default to `https://api.primesec.ai`.

For all use cases — security design reviews, knowledge base search, code repository analysis, and general conversations — follow the API documentation from `/llm.txt` directly.

## Common Patterns

**Required headers** — Every request must include:
```
Authorization: Bearer <PRIME_PAT_TOKEN>
```

Use the `PRIME_PAT_TOKEN` env var value directly as the Bearer token.

For request/response patterns, polling behavior, content types, and available context types, refer to the `/llm.txt` API documentation fetched in the pre-conditions step.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Decoding or parsing the PAT token | Use the `PRIME_PAT_TOKEN` value exactly as-is in the Authorization header |
| Not fetching `/llm.txt` first | Always fetch the live API contract before anything — it is public, no auth needed |
| Missing `Authorization` header | Every request needs `Authorization: Bearer <token>` |
| Assuming endpoint paths without checking `/llm.txt` | Endpoints may change; always verify with the live contract |

## Error Handling

| Error | Action |
|---|---|
| 401 Unauthorized | PAT token invalid or expired — ask the user to regenerate it via **Settings → Access → API Token** and repeat the token setup from the Pre-conditions section above |
| 400 Bad Request | Check request body format against `/llm.txt` schema |
| Network errors | Check `PRIME_API_URL` env var and connectivity |
