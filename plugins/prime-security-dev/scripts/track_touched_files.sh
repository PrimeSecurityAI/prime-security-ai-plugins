#!/usr/bin/env bash

payload=$(cat)

session_id=$(echo "$payload" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('session_id', ''))" 2>/dev/null || true)
file_path=$(echo "$payload" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('tool_input', {}).get('file_path', ''))" 2>/dev/null || true)

if [ -n "$file_path" ] && [ -n "$session_id" ]; then
    state_dir="${CLAUDE_PLUGIN_DATA:-${CLAUDE_PROJECT_DIR:-.}/.claude/state}"
    mkdir -p "$state_dir"
    echo "$file_path" >> "${state_dir}/touched-${session_id}.txt"
fi

exit 0
