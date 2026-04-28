#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
SCRIPT="$ROOT/skills/post-module-commit-message/scripts/recommend_commit_message.sh"
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

expect_not_contains() {
  local name="$1"
  local pattern="$2"
  local file="$3"
  if ! grep -Fq -- "$pattern" "$file"; then
    echo "[PASS] $name"
    return
  fi
  echo "[FAIL] $name: unexpected pattern '$pattern'"
  echo "--- output ---"
  cat "$file"
  exit 1
}

DEV_OUT="$TMP_DIR/dev.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind dev \
  --module ai-judge-p36-artifact-store-port-local-pack \
  --summary "Add local artifact store port and adapter for AI Judge trust and audit artifacts" >"$DEV_OUT"

expect_contains "dev output includes recommended label" "Recommended:" "$DEV_OUT"
expect_contains "dev output uses concise ai-judge scope" "feat(ai-judge): add local artifact store adapter" "$DEV_OUT"
expect_not_contains "dev output avoids long module scope" "(ai-judge-p36-artifact-store-port-local-pack):" "$DEV_OUT"
expect_not_contains "dev output avoids mechanical subject" "advance ai-judge-p36-artifact-store-port-local-pack workflow" "$DEV_OUT"
expect_contains "dev output includes alternatives" "Alternatives:" "$DEV_OUT"

ROUTE_OUT="$TMP_DIR/route.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind dev \
  --module ai-judge-p36-route-dependency-hotspot-split-pack \
  --summary "Split AI Judge trust and ops route dependency assembly out of app_factory without changing route behavior" >"$ROUTE_OUT"

expect_contains "route split uses refactor type" "refactor(ai-judge): split trust and ops route wiring" "$ROUTE_OUT"
expect_not_contains "route split avoids generic capability subject" "add ai-judge capability" "$ROUTE_OUT"
expect_not_contains "route split avoids sync follow-up alternative" "sync ai-judge follow-up" "$ROUTE_OUT"

REGISTRY_TRUST_OUT="$TMP_DIR/registry-trust.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind dev \
  --module ai-judge-p39-registry-trust-route-hotspot-split-pack \
  --summary "Split AI Judge release readiness and public verification route projections without changing contracts" >"$REGISTRY_TRUST_OUT"

expect_contains "registry trust split uses refactor type" "refactor(ai-judge): split registry trust route projections" "$REGISTRY_TRUST_OUT"
expect_contains "registry trust split includes concrete alternative" "refactor(ai-judge): extract public verify projections" "$REGISTRY_TRUST_OUT"
expect_not_contains "registry trust split avoids generic capability subject" "add ai-judge capability" "$REGISTRY_TRUST_OUT"
expect_not_contains "registry trust split avoids sync follow-up alternative" "sync ai-judge follow-up" "$REGISTRY_TRUST_OUT"

LOCAL_REF_OUT="$TMP_DIR/local-reference.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind dev \
  --module ai-judge-p36-local-reference-regression-pack \
  --summary "Record P36 AI Judge local reference regression evidence and runtime ops pack status without claiming real environment pass" >"$LOCAL_REF_OUT"

expect_contains "local reference uses docs type" "docs(ai-judge): record p36 local reference evidence" "$LOCAL_REF_OUT"
expect_not_contains "local reference avoids generic capability subject" "add ai-judge capability" "$LOCAL_REF_OUT"
expect_not_contains "local reference avoids sync follow-up alternative" "sync ai-judge follow-up" "$LOCAL_REF_OUT"

P39_LOCAL_REF_OUT="$TMP_DIR/p39-local-reference.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind dev \
  --module ai-judge-p39-local-reference-regression-pack \
  --summary "Run P39 AI Judge local reference regression without claiming real environment pass" >"$P39_LOCAL_REF_OUT"

expect_contains "p39 local reference uses p39 docs title" "docs(ai-judge): record p39 local reference evidence" "$P39_LOCAL_REF_OUT"
expect_contains "p39 local reference uses p39 alternative" "docs(ai-judge): refresh p39 runtime ops evidence" "$P39_LOCAL_REF_OUT"
expect_not_contains "p39 local reference avoids stale p36 subject" "record p36 local reference evidence" "$P39_LOCAL_REF_OUT"
expect_not_contains "p39 local reference avoids sync follow-up alternative" "sync ai-judge follow-up" "$P39_LOCAL_REF_OUT"

STAGE_OUT="$TMP_DIR/stage.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind non-dev \
  --module ai-judge-p36-stage-closure-execute \
  --summary "Archive P36 AI Judge stage closure, reset active plan, and record real environment follow-up" >"$STAGE_OUT"

expect_contains "stage closure uses specific docs title" "docs(ai-judge): archive p36 stage closure" "$STAGE_OUT"
expect_not_contains "stage closure avoids generic docs subject" "update ai-judge docs" "$STAGE_OUT"
expect_not_contains "stage closure avoids sync follow-up alternative" "sync ai-judge follow-up" "$STAGE_OUT"

P39_STAGE_OUT="$TMP_DIR/p39-stage.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind non-dev \
  --module ai-judge-p39-stage-closure-execute \
  --summary "Archive P39 AI Judge stage closure and reset active plan while preserving real environment follow-up" >"$P39_STAGE_OUT"

expect_contains "p39 stage closure uses current phase title" "docs(ai-judge): archive p39 stage closure" "$P39_STAGE_OUT"
expect_contains "p39 stage closure uses current phase alternative" "docs(ai-judge): record p39 closure state" "$P39_STAGE_OUT"
expect_not_contains "p39 stage closure avoids stale p36 subject" "archive p36 stage closure" "$P39_STAGE_OUT"
expect_not_contains "p39 stage closure avoids sync follow-up alternative" "sync ai-judge follow-up" "$P39_STAGE_OUT"

P40_PLAN_OUT="$TMP_DIR/p40-plan.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind dev \
  --module ai-judge-p40-plan-bootstrap-current-state \
  --summary "Generate P40 AI Judge development plan for bounded challenge product bridge and review sync" >"$P40_PLAN_OUT"

expect_contains "p40 plan uses docs title" "docs(ai-judge): plan p40 challenge bridge" "$P40_PLAN_OUT"
expect_contains "p40 plan includes review sync alternative" "docs(ai-judge): outline p40 review sync" "$P40_PLAN_OUT"
expect_not_contains "p40 plan avoids generic capability subject" "add ai-judge capability" "$P40_PLAN_OUT"
expect_not_contains "p40 plan avoids generic docs subject" "update ai-judge docs" "$P40_PLAN_OUT"

P40_COMPLETION_OUT="$TMP_DIR/p40-completion.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind dev \
  --module ai-judge-p40-completion-map-refresh-p39-closure \
  --summary "Refresh AI Judge enterprise agent completion map to P39 closure and P40 bounded challenge bridge start" >"$P40_COMPLETION_OUT"

expect_contains "p40 completion map uses docs title" "docs(ai-judge): refresh p40 completion map" "$P40_COMPLETION_OUT"
expect_contains "p40 completion map includes closure alternative" "docs(ai-judge): align p39 closure mapping" "$P40_COMPLETION_OUT"
expect_not_contains "p40 completion map avoids generic capability subject" "add ai-judge capability" "$P40_COMPLETION_OUT"
expect_not_contains "p40 completion map avoids generic docs subject" "update ai-judge docs" "$P40_COMPLETION_OUT"

P40_CHALLENGE_OUT="$TMP_DIR/p40-challenge.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind dev \
  --module ai-judge-p40-challenge-eligibility-contract-pack \
  --summary "Add public-safe AI Judge challenge eligibility and status contract with internal status route" >"$P40_CHALLENGE_OUT"

expect_contains "p40 challenge eligibility uses feature title" "feat(ai-judge): add challenge eligibility status contract" "$P40_CHALLENGE_OUT"
expect_contains "p40 challenge eligibility has concrete alternative" "feat(ai-judge): expose public challenge status" "$P40_CHALLENGE_OUT"
expect_not_contains "p40 challenge eligibility avoids generic capability subject" "add ai-judge capability" "$P40_CHALLENGE_OUT"
expect_not_contains "p40 challenge eligibility avoids sync follow-up alternative" "sync ai-judge follow-up" "$P40_CHALLENGE_OUT"

P40_CHAT_CHALLENGE_OUT="$TMP_DIR/p40-chat-challenge.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind dev \
  --module ai-judge-p40-chat-challenge-proxy-pack \
  --summary "Add chat challenge proxy for participant-visible AI Judge challenge status and request flow" >"$P40_CHAT_CHALLENGE_OUT"

expect_contains "p40 chat challenge proxy uses feature title" "feat(ai-judge): proxy judge challenges through chat" "$P40_CHAT_CHALLENGE_OUT"
expect_contains "p40 chat challenge proxy has concrete alternative" "feat(ai-judge): add chat challenge proxy" "$P40_CHAT_CHALLENGE_OUT"
expect_contains "p40 chat challenge proxy has contract alternative" "chore(ai-judge): protect challenge request contract" "$P40_CHAT_CHALLENGE_OUT"
expect_not_contains "p40 chat challenge proxy avoids generic capability subject" "add ai-judge capability" "$P40_CHAT_CHALLENGE_OUT"
expect_not_contains "p40 chat challenge proxy avoids sync follow-up alternative" "sync ai-judge follow-up" "$P40_CHAT_CHALLENGE_OUT"

P40_CLIENT_CHALLENGE_OUT="$TMP_DIR/p40-client-challenge.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind dev \
  --module ai-judge-p40-client-challenge-read-model-pack \
  --summary "Add frontend shared challenge read model and Debate Room challenge status/action view" >"$P40_CLIENT_CHALLENGE_OUT"

expect_contains "p40 client challenge read model uses feature title" "feat(ai-judge): add judge challenge read model" "$P40_CLIENT_CHALLENGE_OUT"
expect_contains "p40 client challenge read model has display alternative" "feat(ai-judge): display judge challenge status" "$P40_CLIENT_CHALLENGE_OUT"
expect_contains "p40 client challenge read model has sync alternative" "chore(ai-judge): sync challenge client state" "$P40_CLIENT_CHALLENGE_OUT"
expect_not_contains "p40 client challenge read model avoids generic capability subject" "add ai-judge capability" "$P40_CLIENT_CHALLENGE_OUT"
expect_not_contains "p40 client challenge read model avoids sync follow-up alternative" "sync ai-judge follow-up" "$P40_CLIENT_CHALLENGE_OUT"

P40_REVIEW_SYNC_OUT="$TMP_DIR/p40-review-sync.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind dev \
  --module ai-judge-p40-review-decision-sync-contract-pack \
  --summary "Add review decision sync contract for AI Judge challenge outcomes and user-visible verdict state" >"$P40_REVIEW_SYNC_OUT"

expect_contains "p40 review sync uses feature title" "feat(ai-judge): add review decision sync contract" "$P40_REVIEW_SYNC_OUT"
expect_contains "p40 review sync has judge report alternative" "feat(ai-judge): surface review sync in judge reports" "$P40_REVIEW_SYNC_OUT"
expect_contains "p40 review sync has verdict protection alternative" "chore(ai-judge): protect review verdict sync" "$P40_REVIEW_SYNC_OUT"
expect_not_contains "p40 review sync avoids generic capability subject" "add ai-judge capability" "$P40_REVIEW_SYNC_OUT"
expect_not_contains "p40 review sync avoids sync follow-up alternative" "sync ai-judge follow-up" "$P40_REVIEW_SYNC_OUT"

P40_CHALLENGE_OPS_OUT="$TMP_DIR/p40-challenge-ops.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind dev \
  --module ai-judge-p40-challenge-ops-read-model-bridge-pack \
  --summary "Bridge AI Trust Challenge ops queue into chat ops and frontend ops-domain read model with public-safe summary and judge_review RBAC" >"$P40_CHALLENGE_OPS_OUT"

expect_contains "p40 challenge ops bridge uses feature title" "feat(ai-judge): bridge challenge ops queue" "$P40_CHALLENGE_OPS_OUT"
expect_contains "p40 challenge ops bridge has ops alternative" "feat(ai-judge): surface challenge queue in ops" "$P40_CHALLENGE_OPS_OUT"
expect_contains "p40 challenge ops bridge has projection alternative" "chore(ai-judge): protect challenge ops projection" "$P40_CHALLENGE_OPS_OUT"
expect_not_contains "p40 challenge ops bridge avoids generic capability subject" "add ai-judge capability" "$P40_CHALLENGE_OPS_OUT"
expect_not_contains "p40 challenge ops bridge avoids sync follow-up alternative" "sync ai-judge follow-up" "$P40_CHALLENGE_OPS_OUT"

P40_CHALLENGE_ROUTE_SPLIT_OUT="$TMP_DIR/p40-challenge-route-split.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind dev \
  --module ai-judge-p40-challenge-route-hotspot-split-pack \
  --summary "Split P40 challenge ops and read-model projection helpers without changing public contracts" >"$P40_CHALLENGE_ROUTE_SPLIT_OUT"

expect_contains "p40 challenge route split uses refactor title" "refactor(ai-judge): split challenge ops projections" "$P40_CHALLENGE_ROUTE_SPLIT_OUT"
expect_contains "p40 challenge route split has helper alternative" "refactor(ai-judge): extract challenge ops helpers" "$P40_CHALLENGE_ROUTE_SPLIT_OUT"
expect_contains "p40 challenge route split has thin projection alternative" "chore(ai-judge): thin challenge proxy projections" "$P40_CHALLENGE_ROUTE_SPLIT_OUT"
expect_not_contains "p40 challenge route split avoids challenge ops bridge subject" "bridge challenge ops queue" "$P40_CHALLENGE_ROUTE_SPLIT_OUT"
expect_not_contains "p40 challenge route split avoids generic capability subject" "add ai-judge capability" "$P40_CHALLENGE_ROUTE_SPLIT_OUT"

TITLE_OUT="$TMP_DIR/title.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind refactor \
  --module post-module-commit-message-humanized-output \
  --summary "Tune post-module commit message skill to prefer concise human commit messages" \
  --title-only >"$TITLE_OUT"

expect_contains "title-only uses concise refactor title" "refactor(commit-message): improve commit message recommendations" "$TITLE_OUT"
expect_not_contains "title-only avoids long commit-message module scope" "(post-module-commit-message-humanized-output):" "$TITLE_OUT"

echo "all post-module-commit-message script tests passed"
