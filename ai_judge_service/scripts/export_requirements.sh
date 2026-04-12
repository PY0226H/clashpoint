#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

uv export \
  --frozen \
  --format requirements.txt \
  --no-dev \
  --no-emit-project \
  --no-header \
  --no-annotate \
  --no-hashes \
  --output-file requirements.txt
