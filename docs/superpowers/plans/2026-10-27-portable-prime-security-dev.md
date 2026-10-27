# Portable Prime Security Dev Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prepare prime-security-dev for customer installation in Claude Code, Codex, and OpenCode.

**Architecture:** One portable skill owns a dependency-free Python API client. Optional lifecycle adapters remind agents to load policies and record supported file edits. Guidance and edit telemetry are explicitly distinguished from enforcement.

**Tech Stack:** Python 3.10+ standard library, Bash compatibility wrappers, JavaScript OpenCode adapter, unittest and node:test.

**Spec:** User-approved recommendations in the conversation on 2026-10-27: portable installation, shared credential handling and helper, reliable loading, exact repository identity, API sequencing, scoped freshness, honest support claims, tests and customer documentation.

## Global Constraints

- Keep the existing operator skill unchanged and retain Claude marketplace compatibility.
- No PAT in chat, command arguments, diagnostics, or repository files. Read environment or the standard Prime token file for each execution.
- Authenticated requests use HTTPS and never follow redirects; custom origins require explicit configuration approval.
- Fetch every guardrail page before returning success. Repository context is best-effort and cannot downgrade guardrail failures.
- No live policy mutations, scans, installations into the user's clients, publishing, or merges during implementation.
- Keep all portable helper resources inside the skill folder.
- Do not claim host integration certification from unit tests alone.

## Review Focus

- Redirects, malformed URLs, API error bodies, and token-file permissions must not expose credentials.
- Pagination with missing totals, capped page sizes, inconsistent totals, and repeated pages must terminate safely.
- Same-name repositories, SSH/HTTPS URLs, and ambiguous registrations must not select incorrect context.
- Missing credentials, malformed responses, and interrupted loads must not be presented as empty policies or successful loading.
- Hook inputs are untrusted; malformed payloads and session/path traversal must not create unsafe state.

## Tasks

- [x] 1. Shared API helper: `skills/prime-code-guardrails/scripts/prime_guardrails.py`; tests in `tests/test_guardrails.py`. CLI loads current policies and optional repository context as JSON; no persistent policy cache. Test credentials, transport, pagination, repository matching and output states before implementation.
- [x] 2. Lifecycle integration: shared `scripts/prime_hooks.py`, Claude wrappers and hooks, Codex manifest/hooks, and OpenCode adapter. Test reminder behavior on every prompt/compaction and file tracking with sanitized session keys. Reminders never claim load success.
- [x] 3. Skill and distribution: neutral SKILL.md, setup reference, consistent version metadata, client-specific installation/update/removal instructions and a release checklist. Use the existing Skills CLI pattern; package adapters independently from standalone skill installation.
- [x] 4. Validate: run the full offline suite and syntax/manifest checks; exercise local installation in an isolated home; review the final diff independently. Record live-client/API checks separately and leave a release gate for any that cannot be completed.

## Decisions and evidence

- Clean checkout on feature branch `feat/portable-prime-security-dev`; no pre-existing tests or build system.
- API contract retrieved without credentials from `/llm/guardrails` and `/llm/code-management` on 2026-10-27. Pagination `total` and `has_next` are nullable; repository detail uses `{repository_id}`.
- Fetch fresh policies for each coding task rather than persisting account-scoped policy caches. This removes stale-account, stale-repository, and context-compaction cache hazards at the cost of an API read per task.
- Implement inline; user already approved the design and requested implementation. No additional design approval gate.

## Implementation result

Implemented all four tasks and validated locally. Final suite: 20 Python + 2 Node tests passing. Native Codex installation and OpenCode discovery/adapter initialization passed in disposable configurations; Claude manifests/skill and universal plugin schema validate. No live model certification or Linux CI run is implied.

Independent review: one P2 HTTPException leak fixed with failing-then-passing tests for malformed HTTP and truncated responses. Hardened missing-completion pagination to require an empty page instead of inferring completion from a short page. No persistent policy cache was introduced.

Release evidence and pending acceptance are in `docs/prime-security-dev-release.md`. Changes remain on the feature branch for review; nothing published or merged.
