# Developer tools contract

All tools are on the Prime MCP server and act as the signed-in user.

| Feature | Tool | Arguments | Returns |
|---|---|---|---|
| Guardrails | `get_developer_guardrails` | `code_references` | `modules`, `guardrails`, `packages`, `limitations` |
| Security context | `get_developer_security_context` | `code_references` | `context_id`, `modules`, `evidence`, `unavailable_sources`, `truncated_sources`, `limitations` |
| | `report_developer_security_context_outcome` | `context_id`, `issue_ids` | Recorded outcome |
| Security plan | `create_developer_security_plan` | `code_references`, `title`, `markdown` | Plan with `id`, `security_review_id` |
| | `get_developer_security_plan` | `plan_id` | Plan with `security_review` |
| PR security review | `start_developer_pr_review` | `pr_ref` | `triggered`, `review` |
| | `get_developer_pr_review` | `review_id` | PR review |

## Inputs

`CodeFileRef`: `{organization, repository, platform, branch?, commit?, pull_request?, filename?}`. `platform` is `github`, `gitlab`, `bitbucket` or `upload`. At most one revision field; none means the default branch. `filename` is a relative file or directory; none means the whole repository. A request holds 1–100 references, all for the same repository and revision.

`pr_ref`: `{organization, repository, platform, pull_request}`.

## Outputs

- `modules[]`: `{id, name}` of the modules Prime matched to the paths. Empty when the repository is not connected; `limitations` then says so.
- `guardrails[]`: `guardrail` (rule text), `guardrail_title`, `category`, `external_id`, `framework`, `policy_name`. Only guardrails from the packages that cover `modules`, or account-wide packages for an unconnected repository.
- `evidence[]`: `{id, kind, text, code_references}` where `kind` is `architecture`, `component`, `safeguard` or `attack_vector`, plus the matching detail:
  - `code_issue`: `{id, related_issue_ids, title, type, severity, suggested_fix}`
  - `safeguard`: `{title, category, assessment}`
  - `design_attack_vector`: `{name, security_review_id, security_review_title, steps}`
  - `component`: `{name, role, type, security_controls: [{name, implementation_status}]}`
- `security_review`: `processing_status` `{job_status, design_doc_status, processing_progress_percent}`, `risk_score`, `summary`, `top_recommendations`, `policy_recommendations`, `attack_scenarios`, `stride_threats`, `linddun_threats`.
- PR review: `id`, `review_state` (`PENDING`, `PROCESSING`, `WAITING_FOR_CATALOG`, `COMPLETED`, `FAILED`, `CANCELED`), `guardrail_issues`, `threat_issues`, `sca_issues`, `secret_issues`.

## Errors

| Error | Meaning |
|---|---|
| 401 | MCP login expired or missing; log in again ([setup](setup.md)). |
| 403 developer security not enabled | Developer features are off for the account. |
| 409 `developer_feature_disabled` | An account admin turned this feature off. |
