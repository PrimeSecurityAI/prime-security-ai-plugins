# Prime Security Dev Plugin

This plugin provides the `prime-code-guardrails` skill for enforcing security policies during code development, and hooks for post-generation analysis.

## Skill
- **prime-code-guardrails** — Fetches security instructions and repo context from Prime API before writing code

## Hooks
- **PostToolUse hook** — Tracks which files Claude modifies during a session

## Required Environment Variables
- `PRIME_PAT_TOKEN` — Prime Security Personal Access Token
