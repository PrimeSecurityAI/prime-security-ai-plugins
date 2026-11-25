# Developer tools contract

All tools are on the Prime MCP server and act as the signed-in user. The plugin hooks call the same security context routes (`POST /dev/security-context`, `/dev/security-context/{context_id}/files`) with a PAT.

| Feature | Tool | Arguments | Returns |
|---|---|---|---|
| Security context | `get_developer_security_map` | `organization`, `repository`, `platform` | Security map |
| | `get_developer_security_files` | `context_id`, `paths` (1–10) | File cards |
| | `get_developer_security_details` | `context_id`, `threat_ids`, `safeguard_ids`, `component_ids`, `design_attack_vector_ids` (≤10 each), `guardrail_categories` (≤5) | Full text |
| | `report_developer_security_context_outcome` | `context_id`, `issue_ids` | Recorded outcome |
| Security plan | `create_developer_security_plan` | `code_references`, `title`, `markdown` | Plan with `id`, `security_review_id` |
| | `get_developer_security_plan` | `plan_id` | Plan with `security_review` |
| PR security review | `start_developer_pr_review` | `pr_ref` | `job`, `review` |
| | `get_developer_pr_review` | `review_id` | PR review |

## Inputs

`platform` is `github`, `gitlab`, `bitbucket` or `upload`. `paths` are files or directories relative to the repository root.

`CodeFileRef`: `{organization, repository, platform, branch?, commit?, pull_request?, filename?}`. At most one revision field; none means the default branch. `filename` is a relative file or directory; none means the whole repository. A request holds 1–100 references, all for the same repository and revision.

`pr_ref`: `{organization, repository, platform, pull_request}`.

## Outputs

Every security context response carries `unavailable_sources`, `truncated_sources` (more items exist than returned) and `limitations`.

- Security map: `context_id`, `connected` (false when the repository is not connected to Prime; guardrails are then account-wide), `modules[] {id, name}`, `threat_counts[] {severity, count}` of open code threats, `hotspots[] {path, findings_count}`, `guardrails[] {category, total, titles[]}`.
- File cards: `cards[]` with `path`, and for each kind a list plus its `*_total`:
  - `threats[]`: `{id, related_issue_ids, title, type, severity, locations[], suggested_fix}`
  - `safeguards[]`: `{id, title, assessment, locations[]}`
  - `components[]`: `{external_id, name, role, security_controls[]}`
  - `design_attack_vectors[]`: `{id, name, component_id}`

  Paths without stored findings are omitted.
- Details: `threats[]` (adds `description`, `steps`, `recommendations`), `safeguards[]` (`analysis_markdown`, `recommendations`), `components[]` (`description`, `security_controls[] {name, implementation_status, details}`), `design_attack_vectors[]` (`description`, `steps`, `security_review_title`), `guardrails[]` (full rules of the requested categories), `not_found` (unknown ids or ids outside the context).
- `security_review`: `processing_status` `{job_status, design_doc_status, processing_progress_percent}`, `risk_score`, `summary`, `top_recommendations`, `policy_recommendations`, `attack_scenarios`, `stride_threats`, `linddun_threats`.
- PR review: `id`, `review_state` (`PENDING`, `PROCESSING`, `WAITING_FOR_CATALOG`, `COMPLETED`, `FAILED`, `CANCELED`), `guardrail_issues`, `threat_issues`, `sca_issues`, `secret_issues`.

## Errors

| Error | Meaning |
|---|---|
| 401 | MCP login expired or missing; log in again ([setup](setup.md)). |
| 403 developer security not enabled | Developer features are off for the account. |
| 409 `developer_feature_disabled` | An account admin turned this feature off. |
