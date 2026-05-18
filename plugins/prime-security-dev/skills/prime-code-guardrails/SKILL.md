---
name: prime-code-guardrails
description: >
  ALWAYS use before exploring, writing, modifying, reviewing any code. This skill must be
  invoked for every coding task — including adding features, fixing bugs, refactoring,
  creating endpoints, writing tests, and any other code changes. It fetches the
  organization's security guardrails and repository context so that all code produced
  conforms to security policies from the start. Invoke once per session — the guardrails
  apply to all subsequent code changes within that session.
allowed-tools:
  - Bash(curl *.primesec.*)
  - Bash(git remote get-url *)
  - WebFetch(domain:*.primesec.*)
  - Read(~/.claude/settings.json)
  - Edit(~/.claude/settings.json)
---

# Code Guardrails Skill

Code Guardrails is Prime Security's mechanism for enforcing security policies at code-writing time. Before writing any code, this skill fetches the active security instructions for the account and, where available, a summary of the target repository. Together these provide the constraints and context needed to produce code that conforms to the organization's security posture.

## Pre-conditions

Complete all steps in order before fetching guardrails or writing any code.

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

Do NOT skip the guardrails and proceed with coding. The guardrails are mandatory.

## Base URL

Read from `PRIME_API_URL` env var. If not set, default to `https://api.primesec.ai`.

## Workflow

Complete the pre-conditions first, then run Step 0, Step 1, and Step 2 in parallel to minimize latency.

### Step 0 — Fetch API Documentation

Fetch the API documentation so you know the exact response schemas for subsequent steps. Use `WebFetch` to retrieve both pages in parallel:

- `{PRIME_API_URL}/llm/instructions` — documents the response schema for the guardrails endpoint.
- `{PRIME_API_URL}/llm/code-management` — documents the response schema for the repositories endpoint.

Use these schemas when parsing API responses in Steps 1 and 2. Do not assume the response structure — always rely on the fetched documentation.

### Step 1 — Fetch Guardrails

The API paginates results. Fetch **all** instructions by paginating with `start` and `limit` query parameters.

**First request:**

```
GET {PRIME_API_URL}/instructions?limit=5000&start=0
```

Required headers:
```
Authorization: Bearer <PRIME_PAT_TOKEN>
```

Use the `PRIME_PAT_TOKEN` env var value directly as the Bearer token.

**Response structure:**

```json
{
  "results": [ ... ],
  "size": <number of items in this page>,
  "limit": <page size>,
  "start": <current offset>,
  "total": <total items>,
  "has_next": <boolean>
}
```

**Pagination:** Keep incrementing `start` by `limit` until all `total` items are collected.

Parse the response according to the schema from Step 0. Treat every instruction returned as a hard constraint when writing code. Do not proceed to write code before all pages have been fetched.

### Step 2 — Fetch Repo Summary

This step is best-effort. If the repository is not registered in Prime Security, skip it and proceed without a summary.

**a)** Get the current repository's remote URL:

```
git remote get-url origin
```

**b)** List registered repositories (paginated):

```
GET {PRIME_API_URL}/code-management/repositories?limit=5000&start=0
```

Use the same headers as Step 1. Same pagination structure as Step 1 — keep incrementing `start` by `limit` until all `total` repositories are collected. Parse the response according to the schema from Step 0 to extract the list of repository objects.

**c)** Match the current repository against the list by comparing the `repo_url` field with the git remote URL, or the `repo_name` field with the current directory name.

**d)** If a match is found, fetch the full repository context using the matched repository's `id` field:

```
GET {PRIME_API_URL}/code-management/repositories/{id}?detailed_summary_required=true
```

Use the same headers as Step 1.

**e)** Use the returned summary — architecture overview, component descriptions, and security notes — as additional context when writing code. This context is informational; the instructions from Step 1 remain the authoritative constraints.

**f)** If no match is found, proceed without a repo summary. Not all repositories are registered in Prime Security.

### Step 3 — Write Code

Apply the guardrails from Step 1 and the repo context from Step 2 while implementing the requested changes. Every security instruction returned in Step 1 must be respected.

### Step 4 — Report Applied Guardrails

After finishing the code changes, output a short summary listing which guardrails were applied and why. For each applied guardrail, include the `instruction_title` and a brief explanation of how it influenced the code.

## Common Mistakes

| Mistake                                                    | Fix |
|------------------------------------------------------------|---|
| Not fetching guardrails before writing code                | Always call `GET /instructions` before writing code |
| Skipping the repo summary lookup                           | Always attempt to match the repo and fetch the detailed summary — skip only when no match is found |
| Hardcoding endpoint paths instead of using `PRIME_API_URL` | Read all base URLs from the `PRIME_API_URL` env var |
| Missing `Authorization` header                             | Every request needs `Authorization: Bearer <token>` |
| Decoding or parsing the PAT token                          | Use the `PRIME_PAT_TOKEN` value exactly as-is in the Authorization header |
| Assuming all repos have summaries in Prime Security                | The repo lookup may return no match — proceed without a summary in that case |
| Assuming API responses are bare arrays                     | Always parse responses according to the schemas fetched in Step 0 — responses are paginated objects, not plain arrays |
| Fetching only the first page of instructions               | Always compare collected items against `total` and paginate until all results are collected — partial guardrails means missed security constraints |

## Error Handling

| Error | Action |
|---|---|
| 401 Unauthorized | PAT token invalid or expired — ask the user to regenerate it via **Settings → Access → API Token** and repeat the token setup from the Pre-conditions section above |
| 400 Bad Request | Check request format and headers |
| Network errors | Check `PRIME_API_URL` env var and connectivity |
| Repo not found in repository list | Proceed without a repo summary |
