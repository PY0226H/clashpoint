#!/usr/bin/env bash
set -euo pipefail

ROOT=""
ANCHOR_JSON=""
MANIFEST_JSON=""
OUTPUT_DIR=""
EMIT_JSON=""
EMIT_MD=""
PYTHON_BIN=""
RUN_ID=""

usage() {
  cat <<'USAGE'
用法:
  ai_judge_audit_anchor_export_local.sh \
    [--root <repo-root>] \
    --anchor-json <audit-anchor.json> \
    [--manifest-json <artifact-manifest.json>] \
    [--output-dir <dir>] \
    [--emit-json <summary.json>] \
    [--emit-md <summary.md>] \
    [--python-bin <venv-python>]

说明:
  本脚本只生成本地可核对的 audit anchor export。
  - artifact_ready: 校验 anchorHash、componentHashes.artifactManifestHash 与 artifactManifest.manifestHash。
  - artifact_pending: 明确保留 pending 状态，不伪造 anchorHash 或外部锚定结果。
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT="${2:-}"
      shift 2
      ;;
    --anchor-json)
      ANCHOR_JSON="${2:-}"
      shift 2
      ;;
    --manifest-json)
      MANIFEST_JSON="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --emit-json)
      EMIT_JSON="${2:-}"
      shift 2
      ;;
    --emit-md)
      EMIT_MD="${2:-}"
      shift 2
      ;;
    --python-bin)
      PYTHON_BIN="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$ROOT" ]]; then
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi

if [[ -z "$ANCHOR_JSON" ]]; then
  echo "--anchor-json is required" >&2
  usage >&2
  exit 2
fi

if [[ -z "$RUN_ID" ]]; then
  RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-ai_judge_audit_anchor_export_local"
fi

if [[ -z "$OUTPUT_DIR" ]]; then
  OUTPUT_DIR="$ROOT/artifacts/harness/$RUN_ID"
fi
if [[ -z "$EMIT_JSON" ]]; then
  EMIT_JSON="$ROOT/artifacts/harness/${RUN_ID}.summary.json"
fi
if [[ -z "$EMIT_MD" ]]; then
  EMIT_MD="$ROOT/artifacts/harness/${RUN_ID}.summary.md"
fi
if [[ -z "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$ROOT/ai_judge_service/.venv/bin/python"
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "python binary is not executable: $PYTHON_BIN" >&2
  exit 2
fi

"$PYTHON_BIN" - "$ANCHOR_JSON" "$MANIFEST_JSON" "$OUTPUT_DIR" "$EMIT_JSON" "$EMIT_MD" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ANCHOR_JSON = Path(sys.argv[1])
MANIFEST_JSON = Path(sys.argv[2]) if sys.argv[2] else None
OUTPUT_DIR = Path(sys.argv[3])
EMIT_JSON = Path(sys.argv[4])
EMIT_MD = Path(sys.argv[5])

BASE_COMPONENT_KEYS = (
    "caseCommitmentHash",
    "verdictAttestationHash",
    "challengeReviewHash",
    "kernelVersionHash",
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def extract_anchor(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("item"), dict):
        return dict(payload["item"])
    verify_payload = payload.get("verifyPayload")
    if isinstance(verify_payload, dict) and isinstance(verify_payload.get("auditAnchor"), dict):
        return dict(verify_payload["auditAnchor"])
    if isinstance(payload.get("auditAnchor"), dict):
        return dict(payload["auditAnchor"])
    return dict(payload)


def non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    errors: list[str] = []
    source_payload = load_json(ANCHOR_JSON)
    anchor = extract_anchor(source_payload)
    components = anchor.get("componentHashes")
    if not isinstance(components, dict):
        components = {}
        errors.append("componentHashes must be an object")

    status = str(anchor.get("anchorStatus") or "").strip()
    if not status:
        status = "artifact_ready" if non_empty(components.get("artifactManifestHash")) else "artifact_pending"
    if status not in {"artifact_ready", "artifact_pending"}:
        errors.append(f"anchorStatus must be artifact_ready or artifact_pending, got {status!r}")

    for key in BASE_COMPONENT_KEYS:
        if not non_empty(components.get(key)):
            errors.append(f"componentHashes.{key} is required")

    manifest: dict[str, Any] | None = None
    if isinstance(anchor.get("artifactManifest"), dict):
        manifest = dict(anchor["artifactManifest"])
    elif MANIFEST_JSON is not None:
        manifest = load_json(MANIFEST_JSON)

    anchor_hash = anchor.get("anchorHash")
    artifact_manifest_hash = components.get("artifactManifestHash")
    manifest_hash = manifest.get("manifestHash") if manifest else None

    if status == "artifact_ready":
        if not non_empty(anchor_hash):
            errors.append("anchorHash is required when anchorStatus is artifact_ready")
        if not non_empty(artifact_manifest_hash):
            errors.append(
                "componentHashes.artifactManifestHash is required when anchorStatus is artifact_ready"
            )
        if manifest is None:
            errors.append("artifactManifest or --manifest-json is required when anchorStatus is artifact_ready")
        elif not non_empty(manifest_hash):
            errors.append("artifactManifest.manifestHash is required when anchorStatus is artifact_ready")
        elif str(manifest_hash).strip() != str(artifact_manifest_hash or "").strip():
            errors.append("artifactManifest.manifestHash must match componentHashes.artifactManifestHash")
    else:
        if non_empty(anchor_hash):
            errors.append("anchorHash must be empty when anchorStatus is artifact_pending")
        if non_empty(artifact_manifest_hash):
            errors.append(
                "componentHashes.artifactManifestHash must be empty when anchorStatus is artifact_pending"
            )

    artifact_count = 0
    if manifest and isinstance(manifest.get("artifactRefs"), list):
        artifact_count = len(manifest["artifactRefs"])

    status_text = "pass_local_reference" if not errors else "fail"
    output_anchor_json = OUTPUT_DIR / "audit_anchor.item.json"
    output_manifest_json = OUTPUT_DIR / "artifact_manifest.json"
    output_export_json = OUTPUT_DIR / "audit_anchor_export.summary.json"

    summary = {
        "status": status_text,
        "anchorStatus": status,
        "exportMode": "local_reference",
        "externalAnchor": False,
        "anchorHash": anchor_hash if non_empty(anchor_hash) else None,
        "artifactManifestHash": artifact_manifest_hash if non_empty(artifact_manifest_hash) else None,
        "manifestHash": manifest_hash if non_empty(manifest_hash) else None,
        "artifactCount": artifact_count,
        "errors": errors,
        "outputs": {
            "exportDir": str(OUTPUT_DIR),
            "anchorJson": str(output_anchor_json),
            "manifestJson": str(output_manifest_json) if manifest else None,
            "exportSummaryJson": str(output_export_json),
            "summaryJson": str(EMIT_JSON),
            "summaryMd": str(EMIT_MD),
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(output_anchor_json, anchor)
    if manifest:
        write_json(output_manifest_json, manifest)
    write_json(output_export_json, summary)
    write_json(EMIT_JSON, summary)

    EMIT_MD.parent.mkdir(parents=True, exist_ok=True)
    EMIT_MD.write_text(
        "\n".join(
            [
                "# AI Judge Audit Anchor Local Export",
                "",
                f"- status: `{status_text}`",
                f"- anchor_status: `{status}`",
                "- export_mode: `local_reference`",
                "- external_anchor: `false`",
                f"- anchor_hash: `{summary['anchorHash'] or ''}`",
                f"- artifact_manifest_hash: `{summary['artifactManifestHash'] or ''}`",
                f"- manifest_hash: `{summary['manifestHash'] or ''}`",
                f"- artifact_count: `{artifact_count}`",
                f"- export_dir: `{OUTPUT_DIR}`",
                f"- summary_json: `{EMIT_JSON}`",
                f"- summary_md: `{EMIT_MD}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"ai_judge_audit_anchor_export_status: {status_text}")
    print(f"anchor_status: {status}")
    print("export_mode: local_reference")
    print("external_anchor: false")
    print(f"summary_json: {EMIT_JSON}")
    print(f"summary_md: {EMIT_MD}")
    print(f"export_dir: {OUTPUT_DIR}")
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY
