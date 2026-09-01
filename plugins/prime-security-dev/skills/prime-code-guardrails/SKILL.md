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

Code Guardrails is Prime Security's mechanism for enforcing security policies at code-writing time. Before writing any code, this skill fetches the account's active security guardrails and, where available, a summary of the target repository. Together these provide the constraints and context needed to produce code that conforms to the organization's security posture.

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

Fetch the API documentation so you know the exact response schemas for subsequent steps. Documentation routes are **unauthenticated** — never send the PAT token to them.

`{PRIME_API_URL}/llm.txt` is the route-group index; it lists the valid `/llm/<group>` documents. The two groups this skill needs are:

- `{PRIME_API_URL}/llm/guardrails` — documents the response schema for the guardrails endpoint.
- `{PRIME_API_URL}/llm/code-management` — documents the response schema for the repositories endpoints.

Use `WebFetch` to retrieve both pages in parallel. There is no `/llm/instructions` group — that path returns HTTP 422.

Use these schemas when parsing API responses in Steps 1 and 2. Do not assume the response structure — always rely on the fetched documentation.

### Step 1 — Fetch Guardrails

The API paginates results. Fetch **all** guardrails by paginating with `offset` and `limit` query parameters.

**First request:**

```
GET {PRIME_API_URL}/guardrails?limit=1000&offset=0
```

Required headers:
```
Authorization: Bearer <PRIME_PAT_TOKEN>
```

Use the `PRIME_PAT_TOKEN` env var value directly as the Bearer token.

**Response structure** (`PaginationResponsePolicyGuardrailResponse`):

```json
{
  "results": [ ... ],
  "size": <number of items in this page>,
  "limit": <page size>,
  "offset": <current offset>,
  "total": <total items>,
  "has_next": <boolean>
}
```

Each item in `results` is a `PolicyGuardrailResponse` with the fields `guardrail_title`, `guardrail`, `quote`, `category`, `guardrail_type`, `framework`, `level`, `policy_id`, `policy_name`, and `external_id`.

**Pagination:** Keep incrementing `offset` by `limit` until `has_next` is false or all `total` items are collected. `limit` accepts a maximum of 9999.

The parameter is `offset`. An unknown pagination parameter such as `start` is **silently ignored** — the API returns page 1 with `offset: 0` and HTTP 200, so a paging loop built on `start` re-collects the first page forever instead of erroring. Always confirm the `offset` echoed in the response matches what you requested.

Parse the response according to the schema from Step 0. Treat every guardrail returned as a hard constraint when writing code. Do not proceed to write code before all pages have been fetched.

### Step 2 — Fetch Repo Summary

This step is best-effort. If the repository is not registered in Prime Security, skip it and proceed without a summary.

**a)** Get the current repository's remote URL:

```
git remote get-url origin
```

**b)** List registered repositories (paginated):

```
GET {PRIME_API_URL}/code-management/repositories?limit=1000&offset=0
```

Use the same headers as Step 1. Same pagination structure as Step 1 — keep incrementing `offset` by `limit` until `has_next` is false or all `total` repositories are collected. Parse the response according to the schema from Step 0 to extract the list of repository objects.

**c)** Match the current repository against the list by comparing the `repo_url` field with the git remote URL, or the `repo_name` field with the current directory name.

**d)** If a match is found, fetch the full repository context using the matched repository's `id` field as the `repository_id` path parameter:

```
GET {PRIME_API_URL}/code-management/repositories/{repository_id}?detailed_summary_required=true
```

Use the same headers as Step 1.

**e)** The summary is nested under the `analysis` object of the `ExtendedRepositoryResponse`, not at the top level:

- `analysis.concise_summary` — short architecture overview, always present.
- `analysis.detailed_summary` — full analysis; **only populated when `detailed_summary_required=true`**, otherwise `null`.
- `data_flow.nodes` / `data_flow.edges` — component and data-flow graph.

Use these as additional context when writing code. This context is informational; the guardrails from Step 1 remain the authoritative constraints.

**f)** If no match is found, proceed without a repo summary. Not all repositories are registered in Prime Security.

### Step 3 — Write Code

Apply the guardrails from Step 1 and the repo context from Step 2 while implementing the requested changes. Every guardrail returned in Step 1 must be respected.

### Step 4 — Report Applied Guardrails

After finishing the code changes, output a short summary listing which guardrails were applied and why. For each applied guardrail, include the `guardrail_title` and a brief explanation of how it influenced the code.

## Common Mistakes

| Mistake                                                    | Fix |
|------------------------------------------------------------|---|
| Not fetching guardrails before writing code                | Always call `GET /guardrails` before writing code |
| Calling `/instructions` or fetching `/llm/instructions`     | Neither path exists. Guardrails live at `GET /guardrails`; its schema doc is `GET /llm/guardrails` |
| Paginating with `start`                                    | The API paginates with `offset`. `start` is silently ignored and every page comes back as page 1 — verify the echoed `offset` |
| Sending the PAT token to `/llm.txt` or `/llm/<group>`      | Documentation routes are unauthenticated — never send credentials to them |
| Skipping the repo summary lookup                           | Always attempt to match the repo and fetch the detailed summary — skip only when no match is found |
| Hardcoding endpoint paths instead of using `PRIME_API_URL` | Read all base URLs from the `PRIME_API_URL` env var |
| Missing `Authorization` header                             | Every request needs `Authorization: Bearer <token>` |
| Decoding or parsing the PAT token                          | Use the `PRIME_PAT_TOKEN` value exactly as-is in the Authorization header |
| Assuming all repos have summaries in Prime Security                | The repo lookup may return no match — proceed without a summary in that case |
| Assuming API responses are bare arrays                     | Always parse responses according to the schemas fetched in Step 0 — responses are paginated objects, not plain arrays |
| Fetching only the first page of guardrails                 | Always compare collected items against `total` and paginate until all results are collected — partial guardrails means missed security constraints |

## Error Handling

| Error | Action |
|---|---|
| 401 Unauthorized | PAT token invalid or expired — ask the user to regenerate it via **Settings → Access → API Token** and repeat the token setup from the Pre-conditions section above |
| 400 Bad Request | Check request format and headers |
| Network errors | Check `PRIME_API_URL` env var and connectivity |
| Repo not found in repository list | Proceed without a repo summary |
