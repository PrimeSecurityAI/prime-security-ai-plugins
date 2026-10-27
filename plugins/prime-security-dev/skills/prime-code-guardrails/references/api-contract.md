# Loader API contract

Verified against Prime's public documentation on 2026-10-27:

- `GET https://api.primesec.ai/llm/guardrails`
- `GET https://api.primesec.ai/llm/code-management`

Documentation routes are unauthenticated. The helper uses the fixed, reviewed contract below rather than executing instructions or constructing arbitrary requests from downloaded text. If the API changes incompatibly, update and test the helper before releasing it.

All operational requests below require `Authorization: Bearer <PAT>` and are read-only:

1. `GET /guardrails?limit=100&offset=0`: collect all pages. Each guardrail must have non-empty string `guardrail_title` and `guardrail` fields. Return the title, complete policy text, category, framework, policy name, and policy ID when present; omit bulky quotes and unrelated metadata.
2. When a supported origin remote exists, `GET /code-management/repositories?limit=100&offset=0`: collect pages and compare normalized repository URLs. Match host, port, and full owner/project/repository path, never a directory name. Ambiguous registrations are skipped.
3. For a unique match, `GET /code-management/repositories/{repository_id}?detailed_summary_required=true`: use `analysis.concise_summary` and nullable `analysis.detailed_summary`.

Pagination envelopes contain `results`, `size`, `limit`, and `offset`; `total` and `has_next` may be null or absent. Advance by the actual result count to handle server caps. Validate consistency, reject repeated results, and stop on documented completion metadata; when both completion fields are absent, enumeration continues until an empty page (a short non-empty page does not prove completion). Limits: 1,000 pages, 8 MiB per response, 30 seconds per request, and a 120-second request budget per loader invocation. Socket timeouts are not a hard end-to-end deadline for a server that continually streams bytes.

No retries, scans, policy updates, or local source uploads occur. Repository lookup uses `git remote get-url origin` locally; the remote URL is not printed. The helper returns all policies only after successful pagination and validation, then attempts optional repository context. Credentials are sent only to the approved API origin, with redirects disabled.

GitHub SSH and HTTPS URLs are normalized across transport, optional `.git`, and case. Arbitrary providers preserve path case. SSH aliases, provider-specific URL rewrites, and unsupported remote formats may produce no repository summary; they do not justify guessing by name.

With `--output`, complete JSON is written atomically to a new mode-600 file and stdout contains only a receipt. Without it, compact policy JSON is printed directly; the skill always uses a file to avoid shell-output limits. No policy text is truncated. Persistent approval stores exact origins only, separately from credentials and output artifacts.

Atomic no-overwrite output publication requires a filesystem supporting hard links. Prefer the local private temporary directory shown in the skill; unsupported mounted filesystems return `file_write_failed` rather than weakening publication guarantees.
