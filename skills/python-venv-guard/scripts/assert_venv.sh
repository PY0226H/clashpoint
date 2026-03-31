#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR=""
VENV_DIR=""

usage() {
  cat <<'USAGE'
用法:
  assert_venv.sh --project <path> --venv <path>

示例:
  bash skills/python-venv-guard/scripts/assert_venv.sh \
    --project /Users/panyihang/Documents/EchoIsle/ai_judge_service \
    --venv /Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)
      PROJECT_DIR="$2"
      shift 2
      ;;
    --venv)
      VENV_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$PROJECT_DIR" || -z "$VENV_DIR" ]]; then
  echo "--project 和 --venv 为必填参数" >&2
  usage
  exit 1
fi

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "project 目录不存在: $PROJECT_DIR" >&2
  exit 1
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "虚拟环境解释器不存在: $VENV_DIR/bin/python" >&2
  echo "请先创建并安装依赖（仅首次创建 venv 可用系统解释器）：" >&2
  echo "  /usr/bin/python3 -m venv $VENV_DIR" >&2
  echo "  $VENV_DIR/bin/python -m pip install -r $PROJECT_DIR/requirements.txt" >&2
  echo "后续所有 Python/PIP 命令必须走 venv 解释器，不得使用全局 python/pip。" >&2
  exit 1
fi

PYTHON_BIN="$VENV_DIR/bin/python"

ASSERT_VENV_DIR="$VENV_DIR" "$PYTHON_BIN" - <<'PY'
import os
import sys

venv_dir = os.environ["ASSERT_VENV_DIR"]
exe = os.path.realpath(sys.executable)
venv_real = os.path.realpath(venv_dir)
prefix = os.path.realpath(sys.prefix)
base_prefix = os.path.realpath(getattr(sys, "base_prefix", sys.prefix))

if prefix != venv_real:
    raise SystemExit(
        "当前解释器前缀与目标 venv 不一致: "
        f"sys.prefix={prefix}, expected={venv_real}"
    )

if prefix == base_prefix:
    raise SystemExit(
        "当前解释器看起来不是虚拟环境（sys.prefix == sys.base_prefix）"
    )

print("venv check passed")
print(f"python={exe}")
PY

echo "建议后续统一使用: $PYTHON_BIN"
