#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/harness/ai_judge_audit_anchor_export_local.sh"

if [[ ! -x "$SCRIPT" ]]; then
  chmod +x "$SCRIPT"
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

expect_contains() {
  local name="$1"
  local pattern="$2"
  local file="$3"
  if grep -Fq -- "$pattern" "$file"; then
    echo "[PASS] $name"
    return
  fi
  echo "[FAIL] $name: missing pattern '$pattern'"
  echo "--- output ---"
  cat "$file"
  exit 1
}

READY_ANCHOR="$TMP_DIR/ready_anchor.json"
cat >"$READY_ANCHOR" <<'JSON'
{
  "item": {
    "caseId": 2001,
    "dispatchType": "final",
    "traceId": "trace-ready",
    "anchorStatus": "artifact_ready",
    "anchorHash": "anchor-hash",
    "componentHashes": {
      "caseCommitmentHash": "case-hash",
      "verdictAttestationHash": "verdict-hash",
      "challengeReviewHash": "challenge-hash",
      "kernelVersionHash": "kernel-hash",
      "artifactManifestHash": "manifest-hash"
    },
    "artifactManifest": {
      "version": "artifact-manifest-v1",
      "manifestHash": "manifest-hash",
      "artifactRefs": [
        {
          "artifactId": "transcript-1",
          "kind": "transcript_snapshot",
          "uri": "local-artifact://ai_judge_service/2001/transcript-1.json",
          "sha256": "artifact-sha",
          "contentType": "application/json",
          "redactionLevel": "redacted"
        }
      ]
    }
  }
}
JSON

READY_STDOUT="$TMP_DIR/ready.stdout"
READY_JSON="$TMP_DIR/ready.summary.json"
READY_MD="$TMP_DIR/ready.summary.md"
READY_OUT="$TMP_DIR/ready-export"
bash "$SCRIPT" \
  --root "$ROOT" \
  --anchor-json "$READY_ANCHOR" \
  --output-dir "$READY_OUT" \
  --emit-json "$READY_JSON" \
  --emit-md "$READY_MD" >"$READY_STDOUT"

expect_contains "ready status" "ai_judge_audit_anchor_export_status: pass_local_reference" "$READY_STDOUT"
expect_contains "ready anchor status" "anchor_status: artifact_ready" "$READY_STDOUT"
expect_contains "ready local reference" "external_anchor: false" "$READY_STDOUT"
expect_contains "ready summary json" "\"anchorStatus\": \"artifact_ready\"" "$READY_JSON"

if [[ ! -f "$READY_OUT/audit_anchor.item.json" ]]; then
  echo "[FAIL] ready anchor item export missing"
  exit 1
fi
if [[ ! -f "$READY_OUT/artifact_manifest.json" ]]; then
  echo "[FAIL] ready manifest export missing"
  exit 1
fi

PENDING_ANCHOR="$TMP_DIR/pending_anchor.json"
cat >"$PENDING_ANCHOR" <<'JSON'
{
  "item": {
    "caseId": 2002,
    "dispatchType": "final",
    "traceId": "trace-pending",
    "anchorStatus": "artifact_pending",
    "anchorHash": null,
    "componentHashes": {
      "caseCommitmentHash": "case-hash",
      "verdictAttestationHash": "verdict-hash",
      "challengeReviewHash": "challenge-hash",
      "kernelVersionHash": "kernel-hash"
    },
    "artifactManifest": null
  }
}
JSON

PENDING_STDOUT="$TMP_DIR/pending.stdout"
PENDING_JSON="$TMP_DIR/pending.summary.json"
PENDING_MD="$TMP_DIR/pending.summary.md"
PENDING_OUT="$TMP_DIR/pending-export"
bash "$SCRIPT" \
  --root "$ROOT" \
  --anchor-json "$PENDING_ANCHOR" \
  --output-dir "$PENDING_OUT" \
  --emit-json "$PENDING_JSON" \
  --emit-md "$PENDING_MD" >"$PENDING_STDOUT"

expect_contains "pending status" "ai_judge_audit_anchor_export_status: pass_local_reference" "$PENDING_STDOUT"
expect_contains "pending anchor status" "anchor_status: artifact_pending" "$PENDING_STDOUT"
expect_contains "pending summary json" "\"anchorHash\": null" "$PENDING_JSON"

FAKE_PENDING="$TMP_DIR/fake_pending_anchor.json"
cat >"$FAKE_PENDING" <<'JSON'
{
  "item": {
    "caseId": 2003,
    "dispatchType": "final",
    "traceId": "trace-fake",
    "anchorStatus": "artifact_pending",
    "anchorHash": "fake-anchor",
    "componentHashes": {
      "caseCommitmentHash": "case-hash",
      "verdictAttestationHash": "verdict-hash",
      "challengeReviewHash": "challenge-hash",
      "kernelVersionHash": "kernel-hash"
    }
  }
}
JSON

FAKE_STDOUT="$TMP_DIR/fake.stdout"
FAKE_STDERR="$TMP_DIR/fake.stderr"
if bash "$SCRIPT" \
  --root "$ROOT" \
  --anchor-json "$FAKE_PENDING" \
  --output-dir "$TMP_DIR/fake-export" \
  --emit-json "$TMP_DIR/fake.summary.json" \
  --emit-md "$TMP_DIR/fake.summary.md" >"$FAKE_STDOUT" 2>"$FAKE_STDERR"; then
  echo "[FAIL] fake pending anchor should fail"
  exit 1
fi
expect_contains "fake pending failure" "anchorHash must be empty" "$FAKE_STDERR"

echo "all ai_judge_audit_anchor_export_local tests passed"
