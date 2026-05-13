#!/usr/bin/env bash

payload=$(cat)

session_id=$(echo "$payload" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('session_id', ''))" 2>/dev/null || true)

if [ -z "$session_id" ]; then
    echo '{}'
    exit 0
fi

state_dir="${CLAUDE_PLUGIN_DATA:-${CLAUDE_PROJECT_DIR:-.}/.claude/state}"
flag_file="${state_dir}/guardrails-loaded-${session_id}"

if [ -f "$flag_file" ]; then
    echo '{}'
    exit 0
fi

mkdir -p "$state_dir"
touch "$flag_file"

cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "IMPORTANT: The prime-code-guardrails skill has not been loaded yet in this session. You MUST invoke it now before doing any code-related work. This is a mandatory security step — do not skip it."
  }
}
EOF
