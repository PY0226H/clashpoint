#!/usr/bin/env bash
set -euo pipefail

MODE="dry-run"
KEEP_DAYS=14
MEMORY_WORKERS=16
REDIS_WORKERS=16
SKIP_REDIS=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --keep-days)
      KEEP_DAYS="${2:-}"
      shift 2
      ;;
    --memory-workers)
      MEMORY_WORKERS="${2:-}"
      shift 2
      ;;
    --redis-workers)
      REDIS_WORKERS="${2:-}"
      shift 2
      ;;
    --skip-redis)
      SKIP_REDIS=1
      shift
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [[ "$MODE" != "dry-run" && "$MODE" != "apply" ]]; then
  echo "--mode must be dry-run or apply" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

run_py() {
  (cd "$ROOT_DIR" && ../scripts/py "$@")
}

echo "[consistency-maintenance] start mode=${MODE}"
echo "[consistency-maintenance] memory collision stress workers=${MEMORY_WORKERS}"
run_py scripts/b3_report_collision_stress.py --workers "${MEMORY_WORKERS}" --mode memory

if [[ "${SKIP_REDIS}" -ne 1 ]]; then
  echo "[consistency-maintenance] redis collision stress workers=${REDIS_WORKERS}"
  run_py scripts/b3_report_collision_stress.py --workers "${REDIS_WORKERS}" --mode redis
fi

if [[ "$MODE" == "dry-run" ]]; then
  echo "[consistency-maintenance] archive dry-run keep_days=${KEEP_DAYS}"
  run_py scripts/archive_consistency_reports.py --keep-days-in-root "${KEEP_DAYS}" --dry-run
else
  echo "[consistency-maintenance] archive apply keep_days=${KEEP_DAYS}"
  run_py scripts/archive_consistency_reports.py --keep-days-in-root "${KEEP_DAYS}"
fi

echo "[consistency-maintenance] done"
