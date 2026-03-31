#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CHAT_DIR="${ROOT_DIR}/chat"
CHATAPP_DIR="${ROOT_DIR}/chatapp"

OUTPUT_DIR=""
RUN_TEST_GATE=0

usage() {
  cat <<'USAGE'
Usage:
  bash chat/scripts/debate_ws_ack_drift_regression.sh [options]

Options:
  --output-dir <path>   Directory for logs and summary (default: /tmp/debate_ws_ack_drift_<ts>)
  --with-test-gate      Run full post-module test gate after targeted regression tests
  -h, --help            Show help

This script validates Phase6 ACK drift readiness baseline:
1) notify-server websocket ACK drift and gap recovery regression tests
2) chatapp debate room ack utility regression test
3) optional full quality gate
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
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
  OUTPUT_DIR="/tmp/debate_ws_ack_drift_$(date +%Y%m%d_%H%M%S)"
fi
mkdir -p "${OUTPUT_DIR}"

SUMMARY_FILE="${OUTPUT_DIR}/summary.md"

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

echo "# Debate WS ACK Drift Regression" > "${SUMMARY_FILE}"
echo "" >> "${SUMMARY_FILE}"
echo "- ExecutedAt: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "${SUMMARY_FILE}"
echo "- Root: ${ROOT_DIR}" >> "${SUMMARY_FILE}"
echo "" >> "${SUMMARY_FILE}"

NOTIFY_CLAMP_LOG="${OUTPUT_DIR}/notify_server_ack_clamp_test.log"
NOTIFY_GAP_LOG="${OUTPUT_DIR}/notify_server_gap_recovery_test.log"
NOTIFY_ACK_LOG="${OUTPUT_DIR}/notify_server_ack_frame_test.log"
FRONTEND_LOG="${OUTPUT_DIR}/chatapp_ack_utils_test.log"
TEST_GATE_LOG="${OUTPUT_DIR}/full_test_gate.log"

run_cmd \
  "cargo test -p notify-server clamp future lastAckSeq" \
  "${NOTIFY_CLAMP_LOG}" \
  cargo test -p notify-server --manifest-path "${CHAT_DIR}/Cargo.toml" \
  debate_room_ws_handler_should_clamp_future_last_ack_seq_and_stream_new_event

run_cmd \
  "cargo test -p notify-server replay gap syncRequired" \
  "${NOTIFY_GAP_LOG}" \
  cargo test -p notify-server --manifest-path "${CHAT_DIR}/Cargo.toml" \
  debate_room_ws_handler_should_require_sync_when_replay_window_has_gap

run_cmd \
  "cargo test -p notify-server ack frame accept" \
  "${NOTIFY_ACK_LOG}" \
  cargo test -p notify-server --manifest-path "${CHAT_DIR}/Cargo.toml" \
  debate_room_ws_handler_should_accept_ack_frame

run_cmd \
  "node chatapp/src/debate-room-utils.test.js" \
  "${FRONTEND_LOG}" \
  node "${CHATAPP_DIR}/src/debate-room-utils.test.js"

if (( RUN_TEST_GATE == 1 )); then
  run_cmd \
    "bash skills/post-module-test-guard/scripts/run_test_gate.sh --mode full" \
    "${TEST_GATE_LOG}" \
    bash "${ROOT_DIR}/skills/post-module-test-guard/scripts/run_test_gate.sh" --mode full --root "${ROOT_DIR}"
fi

echo "## Results" >> "${SUMMARY_FILE}"
echo "" >> "${SUMMARY_FILE}"
echo "- notify ack clamp test: PASS (log: ${NOTIFY_CLAMP_LOG})" >> "${SUMMARY_FILE}"
echo "- notify gap recovery test: PASS (log: ${NOTIFY_GAP_LOG})" >> "${SUMMARY_FILE}"
echo "- notify ack frame test: PASS (log: ${NOTIFY_ACK_LOG})" >> "${SUMMARY_FILE}"
echo "- chatapp ack utils test: PASS (log: ${FRONTEND_LOG})" >> "${SUMMARY_FILE}"
if (( RUN_TEST_GATE == 1 )); then
  echo "- full test gate: PASS (log: ${TEST_GATE_LOG})" >> "${SUMMARY_FILE}"
else
  echo "- full test gate: SKIPPED (use --with-test-gate to enable)" >> "${SUMMARY_FILE}"
fi

echo ""
echo "Regression suite passed."
echo "Summary: ${SUMMARY_FILE}"
