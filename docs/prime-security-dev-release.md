# Prime Security Dev release checklist

Use this checklist before publishing a release candidate. Record results, exact client versions, operating systems, API environment, and immutable commit in the release PR. Do not attach raw policies, PATs, or private source.

## Automated checks

- Python and Node suites pass on macOS and Linux, including the minimum supported Python version.
- Complete policy artifacts are recoverable from private files; failed loads publish no artifact and existing destinations are not overwritten.
- Schema, pagination, authentication, exact-origin approval, and repository-matching failure cases pass.
- Claude skill/plugin/marketplace and portable manifest validation pass.
- Installations include the entire skill folder and its helper/reference resources.

## Live acceptance

Exercise each supported client: Claude Code, Codex, and OpenCode. Use an authorized test account and disposable repositories, without production mutations.

- Fresh install and explicit skill invocation load the complete policy set.
- A coding request selects the skill automatically, or the documented explicit invocation reliably invokes it.
- Missing/expired credentials produce safe recovery instructions and no false success.
- Follow-up messages reuse the ongoing task's policies; a new independent task or repository/account change reloads them.
- Session start/resume and compaction recovery provide guidance. Claude/Codex ordinary prompts do not add transcript reminders; OpenCode includes guidance in each fresh system prompt without accumulating messages.
- Optional adapters work when enabled; explicit standalone invocation works without them.
- Large policy sets are fully read from the artifact, including policy text longer than a shell output limit.
- Update, uninstall, and restart leave no duplicate skill or broken adapter.

Verify empty-policy accounts separately from unavailable service responses. Check unregistered, uniquely matched SSH/HTTPS, and ambiguous repositories. Provider-specific remote rewrites may intentionally skip context; never guess by directory name. Windows adapters and Cursor are not certified by this release.

## Publication and rollback

- Version metadata agrees across the Claude, Codex, portable manifest, and both marketplace entries.
- Supported API contracts and client interfaces have not drifted.
- An approved brand icon is available if required by the target directory.
- Installation from the final immutable release reference succeeds.
- Complete the acceptance checks before customer rollout, then pilot with a small group.
- For rollback, reinstall the previous reviewed version and remove the optional OpenCode wrapper if that version lacks its adapter. Shared token files remain usable by the operator skill.

## Reference documentation

- https://learn.chatgpt.com/docs/build-skills
- https://learn.chatgpt.com/docs/hooks
- https://developers.openai.com/plugins/build/plugins
- https://code.claude.com/docs/en/hooks
- https://opencode.ai/docs/skills/
- https://opencode.ai/docs/plugins/
