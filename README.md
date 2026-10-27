# Prime Security Tools

Agent Skills, Claude Code plugins, and an MCP server for working with Prime Security from AI agents: security design reviews, policy search, repository analysis, code reviews, security posture, and AI-assisted security conversations.

## What's Included

| Component | What it does | Clients |
|---|---|---|
| `prime` skill | Calls the Prime API using its published route documentation | Claude Code, Codex, OpenCode, Cursor |
| Prime MCP server | Exposes Prime as MCP tools | Claude (web, Desktop, mobile), Claude Code, any MCP client |
| `prime-security-operator` plugin | The `prime` skill and the MCP server connection | Claude Code |
| `prime-security-dev` | Portable code guardrails skill and optional client hooks; Claude plugin retains MCP connection | Claude Code, Codex, OpenCode |

## Prerequisites

- A Prime Security account.
- HTTPS access to the Prime Security API.
- For the `prime` skill's browser login: `python3` 3.9 or later.
- For the Skills CLI installation only: Node.js 22.20.0 or later with `npx`, and HTTPS access to GitHub and npm.

On first use the `prime` skill opens your browser to log in to Prime Security, so the skill needs a Personal Access Token (PAT) only on machines without a browser. The development guardrails helper reads `PRIME_PAT_TOKEN` or the shared token file. Claude Code plugins read that file for MCP authentication; other clients have separate MCP setup below.

## Install The Portable Skill

Use the Skills CLI for the primary cross-client installation:

```bash
npx skills add PrimeSecurityAI/prime-security-ai-plugins --skill prime --global
```

For a non-interactive installation targeting all four supported clients explicitly:

```bash
npx skills add PrimeSecurityAI/prime-security-ai-plugins --skill prime --global --agent claude-code --agent codex --agent opencode --agent cursor --yes
```

Choose one installation path. Do not install both the plain `prime` skill and the `prime-security-operator` Claude plugin for the same client; duplicate skills can produce ambiguous invocation and updates.

When Claude Code and OpenCode are targeted together, OpenCode may log a duplicate-source warning because it scans both `~/.agents/skills` and Claude's compatibility directory. The Skills CLI links both paths to the same canonical installed copy, and OpenCode exposes one `prime` skill.

### Update Or Remove

```bash
npx skills update prime --global --yes
npx skills remove prime --global --agent claude-code --agent codex --agent opencode --agent cursor --yes
```

Restart a client if it does not detect a newly installed, updated, or removed skill.

## Configure Credentials

When no credential is configured, the operator `prime` skill runs its browser login. After you log in and click **Authorize**, it saves a 30-day token to the token file below. The token appears under **Settings > Access > API Token**, where you can revoke it. The standalone dev skill can use this same file, but does not bundle browser login; install the operator skill or use the PAT setup below.

The skills resolve credentials immediately before requests, in this order:

1. `PRIME_PAT_TOKEN`
2. `${XDG_CONFIG_HOME:-$HOME/.config}/prime-security/token`

`PRIME_API_URL` is optional and defaults to `https://api.primesec.ai`.

For the shared-file setup, run `unset PRIME_PAT_TOKEN`, remove old `PRIME_PAT_TOKEN` exports from shell profiles or client launch settings, then fully quit and restart the client. An inherited environment token overrides the file for skills, even after browser re-login. Do not save token values in shell profiles.

On machines without a browser (SSH, CI, containers), create a PAT under **Settings > Access > API Token > Create Token** instead. Never paste a PAT into an agent chat. Paste this into Bash or zsh on macOS/Linux. It runs an isolated Bash process and hides input. It removes surrounding spaces/tabs and a trailing carriage return, accepts a non-empty final line without a newline, and rejects empty or invalid input before replacing the existing token:

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

On other systems, use hidden terminal input and a current-user-only ACL for the same logical token path. Do not print or log the token.

After browser re-login or PAT replacement, skills using the file read the new token on their next authenticated request. Claude Code plugins refresh MCP authentication when you reconnect through `/mcp`. Codex, OpenCode, and Cursor MCP configurations require the process environment setup below.

## MCP Server

Prime exposes a remote MCP server over Streamable HTTP at `https://api.primesec.ai/mcp`. Its tools act as the signed-in user, within that user's account and permissions.

| Tools | Purpose |
|---|---|
| `get_design_docs`, `get_design_doc_by_id` | Security design reviews |
| `get_repositories`, `get_repository_by_id`, `get_repository_code_issues` | Code repositories and their findings |
| `get_posture_metrics` | Security posture metrics |
| `get_all_products` | Products |
| `start_prime_ai_conversation`, `ask_prime_ai`, `get_prime_ai_answer` | Ask Prime's security AI a free-form question, then poll `get_prime_ai_answer` until the answer is complete |
| `search_prime_operations`, `call_prime_operation` | Find and run any other Prime API operation |

`call_prime_operation` can run operations that change data in your Prime account. Review those calls before approving them.

### Claude (Web, Desktop, Mobile)

1. Go to **Customize > Connectors**, select **+ Add**, then **Add custom connector**.
2. Enter `https://api.primesec.ai/mcp` as the URL.
3. In the OAuth client settings, use your own OAuth client with Client ID `claude` and no client secret.
4. Connect and sign in with your Prime account.

On Team and Enterprise plans, an organization Owner adds the connector, and each member connects and signs in. The connector is then available in Claude on the web, Desktop, and mobile, and in Claude Code.

### Claude Code

Installing either Claude Code plugin connects the server using `headersHelper`, which reads the private shared token file on each connection. This was validated with Claude Code **2.1.312**; update older clients before using this setup. The helper ignores `PRIME_PAT_TOKEN`, and Claude does not need a token in its process environment. `PRIME_API_URL` selects the API origin when set.

On first startup, missing credentials leave the MCP server disconnected while the skill remains available. Invoke `/prime-security-operator:prime` to sign in through the browser, or save a PAT above. A dev-only installation uses the PAT setup or a separately installed operator skill for browser login. Then open `/mcp`, select the Prime server, and reconnect. After re-login or replacing the PAT, repeat `/mcp` reconnect to read the current file without restarting Claude.

Without a plugin, install the portable `prime` skill first, then add the same dynamic connection at user scope. Replace the path below with the absolute installed path to its bundled helper, normally `~/.agents/skills/prime/scripts/prime_mcp_headers.py` expanded to an absolute path. The command checks that the file exists and stores only its command path, never a token:

```bash
python3 - "/absolute/path/to/prime/scripts/prime_mcp_headers.py" <<'PY'
import json
from pathlib import Path
import shlex
import subprocess
import sys

helper = Path(sys.argv[1]).expanduser()
if not helper.is_absolute() or not helper.is_file():
    raise SystemExit("Set the absolute path to the installed prime_mcp_headers.py first.")
config = {
    "type": "http",
    "url": "https://api.primesec.ai/mcp",
    "headersHelper": "python3 " + shlex.quote(str(helper)),
}
subprocess.run(["claude", "mcp", "add-json", "--scope", "user", "prime", json.dumps(config)], check=True)
PY
```

For a custom deployment, change `url` to its approved MCP URL. Use `/prime` for browser login and `/mcp` to reconnect. If you previously added a static `prime` connection, remove it with `claude mcp remove --scope user prime` before adding this one. Plugin installations manage their own connection and do not need this command.

### Environment-Based MCP Clients

The Codex, OpenCode, and Cursor MCP configurations below read `PRIME_PAT_TOKEN` from the client process. They cannot read the shared file directly. Portable skills alone can use the file without this setup; enabling MCP supplies an environment token that also takes precedence for skills in that client.

After saving a token, paste this function into Bash or zsh. It reads the current file each time, supplies the token only to the launched client, and forwards every client argument unchanged:

```bash
prime_mcp() (
  LC_ALL=C
  prime_token_file="${XDG_CONFIG_HOME:-$HOME/.config}/prime-security/token"
  if [ ! -f "$prime_token_file" ] || [ ! -r "$prime_token_file" ]; then
    printf 'No readable Prime token. Sign in or save a PAT first.\n' >&2
    exit 1
  fi
  prime_pat=$(cat "$prime_token_file") || exit 1
  case "$prime_pat" in
    ""|*[![:graph:]]*)
      printf 'Invalid Prime token. Sign in or save a PAT first.\n' >&2
      exit 1
      ;;
  esac
  PRIME_PAT_TOKEN="$prime_pat" "$@"
)
```

After browser re-login or PAT replacement, fully quit the client and launch it again through this function. Reconnecting MCP inside an already running client retains its old environment token. For Cursor, quit all existing windows and the application before launching from this terminal; an existing GUI process can retain its original environment. GUI launches outside this terminal do not inherit the function's token.

### Codex

```bash
codex mcp add prime --url https://api.primesec.ai/mcp --bearer-token-env-var PRIME_PAT_TOKEN
```

Or add it to `~/.codex/config.toml`:

```toml
[mcp_servers.prime]
url = "https://api.primesec.ai/mcp"
bearer_token_env_var = "PRIME_PAT_TOKEN"
```

Launch from the terminal where you defined `prime_mcp`:

```bash
prime_mcp codex
```

### OpenCode

Add it to `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "prime": {
      "type": "remote",
      "url": "https://api.primesec.ai/mcp",
      "oauth": false,
      "headers": {
        "Authorization": "Bearer {env:PRIME_PAT_TOKEN}"
      }
    }
  }
}
```

Launch from the terminal where you defined `prime_mcp`:

```bash
prime_mcp opencode
```

### Cursor

Add it to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "prime": {
      "url": "https://api.primesec.ai/mcp",
      "headers": {
        "Authorization": "Bearer ${env:PRIME_PAT_TOKEN}"
      }
    }
  }
}
```

With Cursor's `cursor` shell command installed, launch from the terminal where you defined `prime_mcp`:

```bash
prime_mcp cursor --new-window .
```

### Other MCP Clients

Connect to `https://api.primesec.ai/mcp` over Streamable HTTP and send `Authorization: Bearer <PAT>`. Keep the PAT in the client's secret or environment configuration, never in a chat.

## Skill Invocation

All clients can select `prime` automatically from a natural-language request.

| Client | Explicit invocation | Example |
|---|---|---|
| Claude Code | `/prime` | `/prime review this design for security risks` |
| Codex | `$prime` | `$prime search our policies for password requirements` |
| OpenCode | Ask it to use `prime` | `Use the prime skill to review this design` |
| Cursor | Ask it to use `prime` | `Use the prime skill to analyze this repository` |

## Manual Install Alternative

If the Skills CLI is unavailable, copy the canonical directory at `plugins/prime-security-operator/skills/prime` into the skill directory as a folder named `prime`:

| Client | User skill directory |
|---|---|
| Claude Code | `~/.claude/skills/prime` |
| Codex | `~/.agents/skills/prime` |
| OpenCode | `~/.agents/skills/prime` |
| Cursor | `~/.agents/skills/prime` |

For several clients, keep one copy at `~/.agents/skills/prime` and link `~/.claude/skills/prime` to it for Claude Code. On systems without links, use the client-specific directories. Do not combine manual installation with the Skills CLI or marketplace installation.

## Claude Marketplace Alternative

The Claude marketplace remains available for backward compatibility, and its plugins also connect the MCP server:

```bash
claude plugin marketplace add PrimeSecurityAI/prime-security-ai-plugins
claude plugin install prime-security-operator@prime
```

Inside Claude Code, the equivalents are `/plugin marketplace add PrimeSecurityAI/prime-security-ai-plugins` and `/plugin install prime-security-operator@prime`.

The plugin skill is invoked as `/prime-security-operator:prime` in Claude Code. For development guardrails across Claude Code, Codex, and OpenCode, see the [prime-security-dev installation guide](plugins/prime-security-dev/README.md).

## Plugins

### prime-security-operator

The cross-client Prime API skill packaged for Claude Code, plus the MCP server connection. Its only canonical skill source is `plugins/prime-security-operator/skills/prime/SKILL.md`.

### prime-security-dev

Portable `prime-code-guardrails` skill for Claude Code, Codex, and OpenCode, with safe shared credentials, a bundled API helper, and optional client lifecycle integrations. The Claude plugin retains its MCP server connection. Install separately from the operator skill; see the [installation and support guide](plugins/prime-security-dev/README.md).

## Structure

```text
.claude-plugin/marketplace.json
plugins/
|-- prime-security-operator/
|   |-- .claude-plugin/plugin.json
|   |-- .mcp.json
|   `-- skills/prime/SKILL.md
`-- prime-security-dev/
    |-- .claude-plugin/plugin.json
    |-- .mcp.json
    |-- skills/prime-code-guardrails/SKILL.md
    |-- hooks/hooks.json
    `-- scripts/
```

## License

MIT
