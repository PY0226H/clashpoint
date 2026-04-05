#!/usr/bin/env bash
set -euo pipefail

BASE_URL="http://127.0.0.1:6688"
SESSION_ID=""
TOKEN=""
TOTAL_REQUESTS=200
CONCURRENCY=20
LIMIT=80
LAST_ID=""
OUTPUT_FILE=""

usage() {
  cat <<'USAGE'
Usage:
  bash chat/scripts/debate_messages_list_perf_baseline.sh \
    --session-id <id> \
    --token <access_token> \
    [--base-url <url>] \
    [--total-requests <n>] \
    [--concurrency <n>] \
    [--limit <n>] \
    [--last-id <id>] \
    [--output <path>]

Example:
  bash chat/scripts/debate_messages_list_perf_baseline.sh \
    --session-id 1001 \
    --token "$TOKEN" \
    --total-requests 300 \
    --concurrency 30 \
    --limit 50
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)
      BASE_URL="$2"
      shift 2
      ;;
    --session-id)
      SESSION_ID="$2"
      shift 2
      ;;
    --token)
      TOKEN="$2"
      shift 2
      ;;
    --total-requests)
      TOTAL_REQUESTS="$2"
      shift 2
      ;;
    --concurrency)
      CONCURRENCY="$2"
      shift 2
      ;;
    --limit)
      LIMIT="$2"
      shift 2
      ;;
    --last-id)
      LAST_ID="$2"
      shift 2
      ;;
    --output)
      OUTPUT_FILE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$SESSION_ID" || -z "$TOKEN" ]]; then
  echo "Error: --session-id and --token are required." >&2
  usage
  exit 1
fi

if [[ "$TOTAL_REQUESTS" -le 0 || "$CONCURRENCY" -le 0 || "$LIMIT" -le 0 ]]; then
  echo "Error: total/concurrency/limit must be positive integers." >&2
  exit 1
fi

URL="${BASE_URL}/api/debate/sessions/${SESSION_ID}/messages?limit=${LIMIT}"
if [[ -n "$LAST_ID" ]]; then
  URL="${URL}&lastId=${LAST_ID}"
fi

RESULTS_FILE="$(mktemp -t debate_messages_perf_XXXXXX.log)"
trap 'rm -f "$RESULTS_FILE"' EXIT

run_one() {
  local req_no="$1"
  local out
  out="$(curl -sS -o /dev/null -w "%{http_code} %{time_total}" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "x-forwarded-for: 127.0.0.1" \
    "$URL")"
  printf "%s %s\n" "$req_no" "$out" >> "$RESULTS_FILE"
}

echo "[perf] start baseline: total=${TOTAL_REQUESTS}, concurrency=${CONCURRENCY}, url=${URL}"

for ((i = 1; i <= TOTAL_REQUESTS; i++)); do
  run_one "$i" &
  while [[ "$(jobs -rp | wc -l | tr -d ' ')" -ge "$CONCURRENCY" ]]; do
    wait -n
  done
done
wait

TOTAL="$(wc -l < "$RESULTS_FILE" | tr -d ' ')"
OK_200="$(awk '$2 == 200 {c++} END {print c+0}' "$RESULTS_FILE")"
RL_429="$(awk '$2 == 429 {c++} END {print c+0}' "$RESULTS_FILE")"
ERR_4XX_5XX="$(awk '$2 != 200 && $2 != 429 {c++} END {print c+0}' "$RESULTS_FILE")"

SUCCESS_RATE="$(awk -v ok="$OK_200" -v total="$TOTAL" 'BEGIN { if (total==0) {print "0.00"} else {printf "%.2f", (ok*100.0/total)} }')"
RL_RATE="$(awk -v rl="$RL_429" -v total="$TOTAL" 'BEGIN { if (total==0) {print "0.00"} else {printf "%.2f", (rl*100.0/total)} }')"

LAT_FILE="$(mktemp -t debate_messages_perf_lat_XXXXXX.log)"
trap 'rm -f "$RESULTS_FILE" "$LAT_FILE"' EXIT
awk '{print $3}' "$RESULTS_FILE" | sort -n > "$LAT_FILE"

if [[ "$TOTAL" -gt 0 ]]; then
  P95_INDEX=$(( (TOTAL * 95 + 99) / 100 ))
  P99_INDEX=$(( (TOTAL * 99 + 99) / 100 ))
  P95="$(sed -n "${P95_INDEX}p" "$LAT_FILE")"
  P99="$(sed -n "${P99_INDEX}p" "$LAT_FILE")"
else
  P95="0"
  P99="0"
fi

REPORT="$(cat <<EOF
[perf] debate messages baseline result
- total_requests: ${TOTAL}
- concurrency: ${CONCURRENCY}
- ok_200: ${OK_200}
- rate_limited_429: ${RL_429}
- other_errors: ${ERR_4XX_5XX}
- success_rate_pct: ${SUCCESS_RATE}
- rate_limited_rate_pct: ${RL_RATE}
- p95_seconds: ${P95}
- p99_seconds: ${P99}
EOF
)"

echo "$REPORT"

if [[ -n "$OUTPUT_FILE" ]]; then
  cat > "$OUTPUT_FILE" <<EOF
$REPORT
EOF
  echo "[perf] report saved: $OUTPUT_FILE"
fi
