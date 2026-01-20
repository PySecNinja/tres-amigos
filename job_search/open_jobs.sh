#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JOBS_FILE="${1:-$SCRIPT_DIR/jobs.txt}"

echo "SCRIPT_DIR = $SCRIPT_DIR"
echo "JOBS_FILE  = $JOBS_FILE"

if [[ ! -f "$JOBS_FILE" ]]; then
  echo "ERROR: jobs file not found: $JOBS_FILE" >&2
  exit 1
fi

echo "jobs.txt line count: $(wc -l < "$JOBS_FILE")"
echo "first 5 lines:"
sed -n '1,5p' "$JOBS_FILE"

open -a "Google Chrome"
sleep 1

count=0

while IFS= read -r url || [[ -n "$url" ]]; do
  url="$(printf '%s' "$url" | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  [[ -z "$url" ]] && continue
  [[ "$url" == \#* ]] && continue

  count=$((count + 1))
  echo "[$count] Opening: $url"

  osascript -e "tell application \"Google Chrome\" to open location \"${url//\"/\\\"}\""
done < "$JOBS_FILE"

echo "Done. Opened $count URLs."

