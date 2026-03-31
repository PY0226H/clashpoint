#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CHAT_DIR="${ROOT_DIR}/chat"
ACK_SCRIPT="${ROOT_DIR}/chat/scripts/debate_ws_ack_drift_regression.sh"

DB_URL="${DATABASE_URL:-postgres://panyihang@localhost/chat}"
OUTPUT_DIR=""
RUN_TEST_GATE=0

usage() {
  cat <<'USAGE'
Usage:
  bash chat/scripts/debate_kafka_phase6_closed_loop.sh [options]

Options:
  --db-url <url>        Postgres url for local calibration snapshot
  --output-dir <path>   Output directory (default: /tmp/debate_kafka_phase6_<ts>)
  --with-test-gate      Run full test gate after phase6 targeted suite
  -h, --help            Show help

This script executes phase6 local closed-loop checks:
1) ACK drift + gap recovery regression (WS)
2) chat-server consumer business logic closed-loop tests (4 debate event types)
3) notify ingress parsing/runtime signal related tests
4) DLQ replay rate local calibration snapshot + recommendation
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db-url)
      DB_URL="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --with-test-gate)
      RUN_TEST_GATE=1
      shift 1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${OUTPUT_DIR}" ]]; then
  OUTPUT_DIR="/tmp/debate_kafka_phase6_$(date +%Y%m%d_%H%M%S)"
fi
mkdir -p "${OUTPUT_DIR}"

SUMMARY_FILE="${OUTPUT_DIR}/summary.md"
GO_NO_GO_FILE="${OUTPUT_DIR}/go_no_go.md"
CALIBRATION_TSV="${OUTPUT_DIR}/dlq_replay_rate_windows.tsv"
CALIBRATION_PENDING_TSV="${OUTPUT_DIR}/dlq_pending_snapshot.tsv"
CALIBRATION_JSON="${OUTPUT_DIR}/dlq_replay_rate_recommendation.json"

run_cmd() {
  local label="$1"
  local logfile="$2"
  shift 2
  echo "[run] ${label}"
  (
    set -x
    "$@"
  ) >"${logfile}" 2>&1
}

write_header() {
  cat > "${SUMMARY_FILE}" <<EOF
# Debate Kafka Phase6 Closed Loop

- ExecutedAt: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
- Root: ${ROOT_DIR}
- DB: ${DB_URL}

## Results

EOF
}

append_pass_line() {
  local text="$1"
  echo "- ${text}: PASS" >> "${SUMMARY_FILE}"
}

write_header

ACK_LOG="${OUTPUT_DIR}/ack_drift_suite.log"
run_cmd \
  "debate_ws_ack_drift_regression" \
  "${ACK_LOG}" \
  bash "${ACK_SCRIPT}" --output-dir "${OUTPUT_DIR}/ack_drift"
append_pass_line "ACK drift + gap recovery suite (log: ${ACK_LOG})"

CHAT_PARTICIPANT_LOG="${OUTPUT_DIR}/chat_consumer_participant_joined.log"
run_cmd \
  "chat-server worker participant joined effect" \
  "${CHAT_PARTICIPANT_LOG}" \
  cargo test -p chat-server --manifest-path "${CHAT_DIR}/Cargo.toml" \
  process_worker_envelope_should_validate_and_record_participant_joined_effect
append_pass_line "chat-server participant joined worker effect test (log: ${CHAT_PARTICIPANT_LOG})"

CHAT_STATUS_LOG="${OUTPUT_DIR}/chat_consumer_status_changed.log"
run_cmd \
  "chat-server worker status changed effect" \
  "${CHAT_STATUS_LOG}" \
  cargo test -p chat-server --manifest-path "${CHAT_DIR}/Cargo.toml" \
  process_worker_envelope_should_validate_and_record_status_changed_effect
append_pass_line "chat-server status changed worker effect test (log: ${CHAT_STATUS_LOG})"

CHAT_MSG_LOG="${OUTPUT_DIR}/chat_consumer_message_created.log"
run_cmd \
  "chat-server worker message created duplicate-safe effect" \
  "${CHAT_MSG_LOG}" \
  cargo test -p chat-server --manifest-path "${CHAT_DIR}/Cargo.toml" \
  process_worker_envelope_should_record_effect_once_for_duplicate_message_event
append_pass_line "chat-server message created worker effect test (log: ${CHAT_MSG_LOG})"

CHAT_PIN_LOG="${OUTPUT_DIR}/chat_consumer_message_pinned.log"
run_cmd \
  "chat-server worker message pinned effect" \
  "${CHAT_PIN_LOG}" \
  cargo test -p chat-server --manifest-path "${CHAT_DIR}/Cargo.toml" \
  process_worker_envelope_should_validate_and_record_pinned_effect
append_pass_line "chat-server message pinned worker effect test (log: ${CHAT_PIN_LOG})"

READINESS_NOTIFY_LOG="${OUTPUT_DIR}/chat_readiness_notify_signal.log"
run_cmd \
  "chat-server readiness should mark notify chain ready with fresh signal" \
  "${READINESS_NOTIFY_LOG}" \
  cargo test -p chat-server --manifest-path "${CHAT_DIR}/Cargo.toml" \
  get_kafka_transport_readiness_should_mark_notify_chain_ready_with_fresh_signal
append_pass_line "chat-server readiness notify signal test (log: ${READINESS_NOTIFY_LOG})"

READINESS_MULTI_NOTIFY_LOG="${OUTPUT_DIR}/chat_readiness_multi_notify.log"
run_cmd \
  "chat-server readiness should allow when any notify signal is ready" \
  "${READINESS_MULTI_NOTIFY_LOG}" \
  cargo test -p chat-server --manifest-path "${CHAT_DIR}/Cargo.toml" \
  get_kafka_transport_readiness_should_allow_when_any_notify_signal_is_ready
append_pass_line "chat-server readiness multi-notify aggregation test (log: ${READINESS_MULTI_NOTIFY_LOG})"

READINESS_DLQ_PROGRESS_LOG="${OUTPUT_DIR}/chat_readiness_dlq_progress.log"
run_cmd \
  "chat-server readiness dlq progressing gate" \
  "${READINESS_DLQ_PROGRESS_LOG}" \
  cargo test -p chat-server --manifest-path "${CHAT_DIR}/Cargo.toml" \
  get_kafka_transport_readiness_should_mark_dlq_loop_ready_when_replay_progressing
append_pass_line "chat-server readiness dlq progress test (log: ${READINESS_DLQ_PROGRESS_LOG})"

READINESS_REPLAY_RATE_LOG="${OUTPUT_DIR}/chat_readiness_replay_rate.log"
run_cmd \
  "chat-server readiness replay rate blocker gate" \
  "${READINESS_REPLAY_RATE_LOG}" \
  cargo test -p chat-server --manifest-path "${CHAT_DIR}/Cargo.toml" \
  evaluate_pending_dlq_replay_rate_blocking_should_block_when_rate_below_threshold
append_pass_line "chat-server readiness replay rate blocker test (log: ${READINESS_REPLAY_RATE_LOG})"

NOTIFY_PARTICIPANT_LOG="${OUTPUT_DIR}/notify_parse_participant.log"
run_cmd \
  "notify parse DebateParticipantJoined ingress payload" \
  "${NOTIFY_PARTICIPANT_LOG}" \
  cargo test -p notify-server --manifest-path "${CHAT_DIR}/Cargo.toml" \
  notification_load_should_parse_debate_participant_joined
append_pass_line "notify parse DebateParticipantJoined test (log: ${NOTIFY_PARTICIPANT_LOG})"

NOTIFY_STATUS_LOG="${OUTPUT_DIR}/notify_parse_status_changed.log"
run_cmd \
  "notify parse DebateSessionStatusChanged ingress payload" \
  "${NOTIFY_STATUS_LOG}" \
  cargo test -p notify-server --manifest-path "${CHAT_DIR}/Cargo.toml" \
  notification_load_should_parse_debate_session_status_changed
append_pass_line "notify parse DebateSessionStatusChanged test (log: ${NOTIFY_STATUS_LOG})"

NOTIFY_MSG_LOG="${OUTPUT_DIR}/notify_parse_message_created.log"
run_cmd \
  "notify parse DebateMessageCreated ingress payload" \
  "${NOTIFY_MSG_LOG}" \
  cargo test -p notify-server --manifest-path "${CHAT_DIR}/Cargo.toml" \
  notification_load_should_parse_debate_message_created
append_pass_line "notify parse DebateMessageCreated test (log: ${NOTIFY_MSG_LOG})"

NOTIFY_PIN_LOG="${OUTPUT_DIR}/notify_parse_message_pinned.log"
run_cmd \
  "notify parse DebateMessagePinned ingress payload" \
  "${NOTIFY_PIN_LOG}" \
  cargo test -p notify-server --manifest-path "${CHAT_DIR}/Cargo.toml" \
  notification_load_should_parse_debate_message_pinned
append_pass_line "notify parse DebateMessagePinned test (log: ${NOTIFY_PIN_LOG})"

NOTIFY_BACKOFF_LOG="${OUTPUT_DIR}/notify_kafka_backoff.log"
run_cmd \
  "notify kafka reconnect backoff and cap" \
  "${NOTIFY_BACKOFF_LOG}" \
  cargo test -p notify-server --manifest-path "${CHAT_DIR}/Cargo.toml" \
  compute_kafka_consumer_reconnect_delay_should_backoff_and_cap
append_pass_line "notify kafka reconnect backoff test (log: ${NOTIFY_BACKOFF_LOG})"

PSQL_WINDOWS_LOG="${OUTPUT_DIR}/calibration_windows_query.log"
echo "[run] calibration query dlq replay action windows"
(
  set -x
  psql "${DB_URL}" -At -F '|' -c "
SELECT
  w.window_secs,
  (
    SELECT COUNT(1)::bigint
    FROM kafka_dlq_events e
    WHERE e.status IN ('replayed', 'discarded')
      AND e.updated_at >= NOW() - (w.window_secs * INTERVAL '1 second')
  ) AS replay_actions,
  ROUND(
    (
      SELECT COUNT(1)::numeric
      FROM kafka_dlq_events e
      WHERE e.status IN ('replayed', 'discarded')
        AND e.updated_at >= NOW() - (w.window_secs * INTERVAL '1 second')
    ) / (w.window_secs::numeric / 60.0),
    3
  ) AS replay_actions_per_minute
FROM (VALUES (60), (180), (300), (600)) AS w(window_secs)
ORDER BY w.window_secs;
"
) > "${CALIBRATION_TSV}" 2>"${PSQL_WINDOWS_LOG}"
append_pass_line "DLQ replay window snapshot (file: ${CALIBRATION_TSV}, log: ${PSQL_WINDOWS_LOG})"

PSQL_PENDING_LOG="${OUTPUT_DIR}/calibration_pending_query.log"
echo "[run] calibration query pending dlq snapshot"
(
  set -x
  psql "${DB_URL}" -At -F '|' -c "
SELECT
  COUNT(1) FILTER (WHERE status = 'pending') AS pending_count,
  COALESCE(
    FLOOR(EXTRACT(EPOCH FROM (NOW() - MIN(first_failed_at) FILTER (WHERE status = 'pending'))))::bigint,
    0
  ) AS pending_oldest_age_secs
FROM kafka_dlq_events;
"
) > "${CALIBRATION_PENDING_TSV}" 2>"${PSQL_PENDING_LOG}"
append_pass_line "DLQ pending snapshot (file: ${CALIBRATION_PENDING_TSV}, log: ${PSQL_PENDING_LOG})"

rate_samples=()
while IFS= read -r line; do
  rate_samples+=("${line}")
done < <(awk -F'|' '{ if ($3+0 > 0) print $3 }' "${CALIBRATION_TSV}" | sort -n)
sample_count="${#rate_samples[@]}"
recommended_min_rate="0.000"
recommendation_reason="insufficient_samples_keep_disabled"

if (( sample_count > 0 )); then
  # Use conservative p25*0.8 to reduce false-positive blocking on low-traffic windows.
  idx=$(( (sample_count - 1) / 4 ))
  p25="${rate_samples[$idx]}"
  recommended_min_rate="$(awk -v v="${p25}" 'BEGIN {
    rec = v * 0.8;
    if (rec < 0.05) rec = 0.05;
    printf "%.3f", rec;
  }')"
  recommendation_reason="derived_from_local_replay_samples"
fi

cat > "${CALIBRATION_JSON}" <<EOF
{
  "dbUrl": "${DB_URL}",
  "windowSnapshotFile": "${CALIBRATION_TSV}",
  "pendingSnapshotFile": "${CALIBRATION_PENDING_TSV}",
  "nonZeroReplayRateSampleCount": ${sample_count},
  "recommendedMinReplayActionsPerMinute": ${recommended_min_rate},
  "recommendationReason": "${recommendation_reason}",
  "currentDefaultMinReplayActionsPerMinute": 0.0
}
EOF
append_pass_line "DLQ replay rate recommendation (file: ${CALIBRATION_JSON})"

if (( RUN_TEST_GATE == 1 )); then
  TEST_GATE_LOG="${OUTPUT_DIR}/full_test_gate.log"
  run_cmd \
    "run full post-module test gate" \
    "${TEST_GATE_LOG}" \
    bash "${ROOT_DIR}/skills/post-module-test-guard/scripts/run_test_gate.sh" --mode full --root "${ROOT_DIR}"
  append_pass_line "Full test gate (log: ${TEST_GATE_LOG})"
fi

cat > "${GO_NO_GO_FILE}" <<EOF
# Phase6 Go/No-Go (Local)

- GeneratedAt: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
- SummaryFile: ${SUMMARY_FILE}

## Decision Inputs

1. Consumer business logic closed-loop tests (4 debate event types): PASS
2. Notify ingress parse/runtime tests: PASS
3. WS ACK drift/gap recovery suite: PASS
4. DLQ replay rate local calibration snapshot: PASS

## Calibration Note

- Recommendation file: ${CALIBRATION_JSON}
- If \`recommendationReason=insufficient_samples_keep_disabled\`, keep \`kafka_readiness_pending_dlq_min_replay_actions_per_minute=0.0\` until real replay samples are accumulated.

## Local Decision

- Go for phase6 local development closure.
- Keep production-style kafka-only switch as next phase action (outside this script scope).
EOF

echo "- Go/No-Go report: ${GO_NO_GO_FILE}" >> "${SUMMARY_FILE}"
echo ""
echo "Phase6 closed-loop suite passed."
echo "Summary: ${SUMMARY_FILE}"
