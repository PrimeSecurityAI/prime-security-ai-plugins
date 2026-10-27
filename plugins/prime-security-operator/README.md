# prime-security-operator

The portable `prime` Agent Skill interacts with Prime Security for security design reviews, knowledge base and policy search, repository analysis, code reviews, and AI-assisted security conversations.

## Prerequisites

- Node.js 22.20.0 or later with `npx`
- Claude Code, Codex, OpenCode, or Cursor
- A Prime Security account
- `python3` 3.9 or later for the browser login
- HTTPS access to GitHub, npm, and the Prime Security API

On first use the skill opens your browser to log in to Prime Security. A PAT is needed only on machines without a browser. The Claude plugin's MCP connection reads the same private token file; see [MCP Server](#mcp-server).

## Install

The primary cross-client installation is:

```bash
npx skills add PrimeSecurityAI/prime-security-ai-plugins --skill prime --global
```

Use this command to target all supported clients without prompts:

```bash
npx skills add PrimeSecurityAI/prime-security-ai-plugins --skill prime --global --agent claude-code --agent codex --agent opencode --agent cursor --yes
```

Choose one installation path. Do not install both this plain skill and the Claude marketplace plugin in the same client.

When Claude Code and OpenCode are targeted together, OpenCode may log a duplicate-source warning because it scans both `~/.agents/skills` and Claude's compatibility directory. Both paths resolve to the Skills CLI's same canonical copy, and OpenCode exposes one `prime` skill.

### Update Or Remove

```bash
npx skills update prime --global --yes
npx skills remove prime --global --agent claude-code --agent codex --agent opencode --agent cursor --yes
```

Restart a client if it does not detect the change.

## Credentials

When no credential is configured, the skill runs `scripts/prime_login.py`. It opens your browser; after you log in and click **Authorize**, it saves a 30-day token to the token file below. The token appears under **Settings > Access > API Token**, where you can revoke it. To log in again, run `python3 <skill-dir>/scripts/prime_login.py` yourself; to log out, revoke the token under **Settings > Access > API Token** and delete the token file.

Credential precedence is:

1. `PRIME_PAT_TOKEN`
2. `${XDG_CONFIG_HOME:-$HOME/.config}/prime-security/token`

`PRIME_API_URL` is optional and defaults to `https://api.primesec.ai`.

For the shared-file setup, run `unset PRIME_PAT_TOKEN`, remove old exports from shell profiles or client launch settings, then fully quit and restart the client. An inherited environment token overrides the file for skills even after re-login. Subsequent browser logins update the file, which the skill reads on its next authenticated request.

On machines without a browser (SSH, CI, containers), create a PAT under **Settings > Access > API Token > Create Token** instead. Never paste a PAT into chat. Paste this into Bash or zsh on macOS/Linux. It runs an isolated Bash process with hidden input and restrictive permissions. It removes surrounding spaces/tabs and a trailing carriage return, accepts a non-empty final line without a newline, and rejects empty or invalid input before replacing the existing token:

```bash
bash -c '
set -e
LC_ALL=C
IFS= read -r -s -p "Prime PAT: " prime_pat || {
  [ "$?" -eq 1 ] && [ -n "$prime_pat" ]
} || {
  printf "\nNo token entered; existing token unchanged.\n" >&2
  exit 1
}
printf "\n"
prime_pat="${prime_pat%"$(printf "\r")"}"
prime_pat="${prime_pat#"${prime_pat%%[![:blank:]]*}"}"
prime_pat="${prime_pat%"${prime_pat##*[![:blank:]]}"}"
if [[ -z "$prime_pat" || "$prime_pat" == *[![:graph:]]* ]]; then
  printf "Invalid token; existing token unchanged.\n" >&2
  exit 1
fi
config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/prime-security"
umask 077
mkdir -p "$config_dir"
chmod 700 "$config_dir"
token_tmp=$(mktemp "$config_dir/token.XXXXXX")
trap "rm -f -- \"\$token_tmp\"" EXIT
printf "%s\n" "$prime_pat" > "$token_tmp"
mv -f -- "$token_tmp" "$config_dir/token"
'
```

On other systems, use hidden terminal input and grant only the current user access to the same logical token path. Never print or log the token.

## Invocation

Natural-language requests can activate the skill automatically.

| Client | Explicit invocation | Example |
|---|---|---|
| Claude Code | `/prime` | `/prime review this design for security risks` |
| Codex | `$prime` | `$prime search policies for password requirements` |
| OpenCode | Ask it to use `prime` | `Use the prime skill to review this design` |
| Cursor | Ask it to use `prime` | `Use the prime skill to analyze this repository` |

The skill fetches `/llm.txt` as a route-group index, loads only relevant `/llm/<group>` documentation, follows each endpoint's authentication contract, and polls only documented asynchronous responses.

## MCP Server

The Claude marketplace plugin also connects Claude Code to the Prime MCP server through `.mcp.json`. The Skills CLI and manual installations include only the skill; to use the MCP server from Claude, Codex, OpenCode, or Cursor, follow the [MCP Server section](../../README.md#mcp-server) of the repository README.

The plugin uses `headersHelper` to read the private shared token file on every connection. This was validated with Claude Code **2.1.312**; update older clients before using this setup. The helper ignores `PRIME_PAT_TOKEN`, so launch Claude normally without exporting a token.

On first startup, a missing token leaves MCP disconnected while the skill remains available. Invoke `/prime-security-operator:prime` and complete browser login, or save a PAT above. Then open `/mcp`, select the Prime server, and reconnect. After re-login or replacing the PAT, repeat `/mcp` reconnect to read the new file without restarting Claude.

Portable skills use the file directly when `PRIME_PAT_TOKEN` is unset. Codex, OpenCode, and Cursor MCP configurations instead require a token in the client process environment; use the [process-scoped launch instructions](../../README.md#environment-based-mcp-clients). Fully quit and relaunch those clients after re-login, because their environment token also overrides the file for skills.

## Pre-Approving Network Access

The skill needs outbound HTTPS access to `*.primesec.*` (or your configured `PRIME_API_URL` host). There is no shared setting for this across clients — each has its own allowlist mechanism, so configure the ones you use:

| Client | Where | Notes |
|---|---|---|
| Claude Code | `permissions.allow`/`deny` in `settings.json` | Allow `WebFetch(domain:*.primesec.*)`. Do not try to domain-scope `Bash(curl ...)` — Claude Code's own docs note it's bypassable via redirects, protocol swaps, or flags before the URL; deny `Bash(curl *)` and `Bash(wget *)` instead. |
| OpenCode | `permission` in `opencode.json`/`opencode.jsonc` | Both `bash` and `webfetch` support per-pattern rules, e.g. `"webfetch": {"https://*.primesec.*/*": "allow"}`. |
| Cursor | `.cursor/permissions.json` / Agent settings | `terminalAllowlist` prefix-matches the command name only, not the URL — there is no domain-scoped fetch allowlist. Leave `curl` in ask-mode unless you accept that limitation. |
| Codex CLI | `~/.codex/config.toml` | Network access is controlled via `sandbox_mode` / `[sandbox_workspace_write] network_access`, with proxy-based domain allowlisting on some versions. Check the current Codex config reference for exact field names before relying on it. |

Skipping this is safe: without it, the client just prompts for approval on the skill's requests as usual.

The plugin's MCP tools use Claude Code permission rules of the form `mcp__plugin_prime-security-operator_prime__<tool>`, for example `mcp__plugin_prime-security-operator_prime__get_repositories`. Do not pre-approve `call_prime_operation`, because it can change data in your Prime account.

## Manual Install Alternative

Copy the canonical `skills/prime` directory to the client user directory as a folder named `prime`:

| Client | User skill directory |
|---|---|
| Claude Code | `~/.claude/skills/prime` |
| Codex | `~/.agents/skills/prime` |
| OpenCode | `~/.agents/skills/prime` |
| Cursor | `~/.agents/skills/prime` |

For multiple clients, keep one copy at `~/.agents/skills/prime` and link it into `~/.claude/skills/prime`. Do not combine manual, Skills CLI, and marketplace installations.

## Claude Marketplace Alternative

For backward-compatible Claude Code plugin installation:

```bash
claude plugin marketplace add PrimeSecurityAI/prime-security-ai-plugins
claude plugin install prime-security-operator@prime
```

Invoke the plugin skill as `/prime-security-operator:prime`. Do not also install the plain `/prime` skill.

## Canonical Source

`skills/prime/SKILL.md` is the only canonical Prime operator skill. There is no root-level copy or installer script.

## License

MIT
