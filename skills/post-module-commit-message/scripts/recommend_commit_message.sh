#!/usr/bin/env bash
set -euo pipefail

ROOT=""
TASK_KIND=""
MODULE=""
SUMMARY=""
TITLE_ONLY=0

usage() {
  cat <<'USAGE'
用法:
  recommend_commit_message.sh \
    --root <repo-root> \
    --task-kind <dev|refactor|non-dev> \
    --module <module-id> \
    --summary <summary> \
    [--title-only]

说明:
  根据当前 Git 改动与任务参数生成 Conventional Commits 标题建议。
USAGE
}

lower_ascii() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

trim() {
  local value="$1"
  value="${value#${value%%[![:space:]]*}}"
  value="${value%${value##*[![:space:]]}}"
  printf '%s' "$value"
}

sanitize_scope() {
  local value="$1"
  value="$(printf '%s' "$value" | sed -E 's/[^a-zA-Z0-9]+/-/g; s/^-+//; s/-+$//')"
  value="$(lower_ascii "$value")"
  [[ -z "$value" ]] && value="repo"
  printf '%s' "$value"
}

short_scope_from_module() {
  local module
  module="$(sanitize_scope "$1")"
  case "$module" in
    ai-judge*) echo "ai-judge"; return 0 ;;
    post-module-commit-message*) echo "commit-message"; return 0 ;;
    post-module-plan-sync*) echo "plan-sync"; return 0 ;;
    post-module-test-guard*) echo "test-guard"; return 0 ;;
    pre-module-prd-goal-guard*) echo "prd-guard"; return 0 ;;
    auth-*) echo "auth"; return 0 ;;
    chat-*) echo "chat"; return 0 ;;
    frontend-*) echo "frontend"; return 0 ;;
    harness-*) echo "harness"; return 0 ;;
  esac

  local filtered
  filtered="$(printf '%s\n' "$module" | awk -F '-' '
    BEGIN {
      skip["pack"] = 1
      skip["phase"] = 1
      skip["batch"] = 1
      skip["execute"] = 1
      skip["workflow"] = 1
      skip["follow"] = 1
      skip["up"] = 1
      skip["current"] = 1
      skip["state"] = 1
      skip["sync"] = 1
    }
    {
      out = ""
      count = 0
      for (i = 1; i <= NF; i++) {
        token = $i
        if (token == "" || token ~ /^p[0-9]+$/ || token in skip) {
          continue
        }
        out = out (out == "" ? token : "-" token)
        count++
        if (count >= 2) {
          break
        }
      }
      print out
    }
  ')"
  [[ -z "$filtered" ]] && filtered="repo"
  printf '%s' "$filtered"
}

short_scope_from_files() {
  local files="$1"
  if [[ -z "$files" ]]; then
    echo "repo"
    return 0
  fi
  if printf '%s\n' "$files" | grep -qE '^skills/post-module-commit-message/'; then
    echo "commit-message"
  elif printf '%s\n' "$files" | grep -qE '^ai_judge_service/'; then
    echo "ai-judge"
  elif printf '%s\n' "$files" | grep -qE '^chat/'; then
    echo "chat"
  elif printf '%s\n' "$files" | grep -qE '^frontend/'; then
    echo "frontend"
  elif printf '%s\n' "$files" | grep -qE '^docs/'; then
    echo "docs"
  elif printf '%s\n' "$files" | grep -qE '^skills/'; then
    echo "skills"
  else
    echo "repo"
  fi
}

phase_from_context() {
  local module_key="$1"
  local summary_lower="$2"
  if [[ "$module_key" =~ p([0-9]+) ]]; then
    printf 'p%s' "${BASH_REMATCH[1]}"
    return 0
  fi
  if [[ "$summary_lower" =~ p([0-9]+) ]]; then
    printf 'p%s' "${BASH_REMATCH[1]}"
    return 0
  fi
  printf ''
}

infer_scope() {
  local files="$1"
  local scope
  scope="$(short_scope_from_module "$MODULE")"
  if [[ "$scope" != "repo" ]]; then
    printf '%s' "$scope"
    return 0
  fi
  short_scope_from_files "$files"
}

collect_changed_files() {
  {
    git -C "$ROOT" diff --name-only 2>/dev/null || true
    git -C "$ROOT" diff --cached --name-only 2>/dev/null || true
    git -C "$ROOT" ls-files --others --exclude-standard 2>/dev/null || true
  } | awk 'NF' | sort -u
}

detect_type() {
  local files="$1"
  local non_docs_count
  local module_key
  local summary_lower

  module_key="$(sanitize_scope "$MODULE")"
  summary_lower="$(lower_ascii "$SUMMARY")"

  case "$TASK_KIND" in
    refactor) echo "refactor"; return 0 ;;
    non-dev) echo "docs"; return 0 ;;
  esac

  if [[ "$module_key" == *"plan-bootstrap"* ||
        "$module_key" == *"completion-map"* ||
        "$summary_lower" == *"development plan"* ]]; then
    echo "docs"
    return 0
  fi

  if [[ -n "$files" ]]; then
    if ! printf '%s\n' "$files" | grep -qvE '^(docs/|AGENTS\.md$|README\.md$|.*\.md$)'; then
      echo "docs"
      return 0
    fi
    if printf '%s\n' "$files" | grep -qE '^(\.github/|.*\.ya?ml$)' &&
       ! printf '%s\n' "$files" | grep -qvE '^(\.github/|.*\.ya?ml$)'; then
      echo "ci"
      return 0
    fi
    if printf '%s\n' "$files" | grep -qE '(^|/)(Cargo\.toml|Cargo\.lock|package\.json|pnpm-lock\.yaml)$'; then
      non_docs_count="$(printf '%s\n' "$files" | grep -cvE '^(docs/|.*\.md$)' || true)"
      if [[ "$non_docs_count" -le 2 ]]; then
        echo "build"
        return 0
      fi
    fi
  fi

  if [[ "$module_key" == *"route-dependency-hotspot-split"* ||
        "$module_key" == *"registry-trust-route-hotspot-split"* ||
        "$summary_lower" == *"route projection"* ||
        "$summary_lower" == *"route projections"* ||
        "$summary_lower" == *"hotspot split"* ||
        "$summary_lower" == *"route dependency"* ]]; then
    echo "refactor"
    return 0
  fi
  if [[ "$module_key" == *"local-reference-regression"* ||
        "$summary_lower" == *"local reference"* ]]; then
    echo "docs"
    return 0
  fi

  echo "feat"
}

build_subject() {
  local scope="$1"
  local module_key
  local summary_lower
  module_key="$(sanitize_scope "$MODULE")"
  summary_lower="$(lower_ascii "$SUMMARY")"

  if [[ "$module_key" == *"release-readiness-artifact-export"* ||
          "$summary_lower" == *"release readiness artifact"* ]]; then
    echo "export release readiness artifacts"
  elif [[ "$module_key" == *"artifact-store"* || "$summary_lower" == *"artifact store"* ]]; then
    echo "add local artifact store adapter"
  elif [[ "$module_key" == *"stage-closure"* ||
          "$summary_lower" == *"stage closure"* ]]; then
    local phase
    phase="$(phase_from_context "$module_key" "$summary_lower")"
    if [[ -n "$phase" ]]; then
      echo "archive ${phase} stage closure"
    else
      echo "archive stage closure"
    fi
  elif [[ "$module_key" == *"plan-bootstrap"* ||
          "$summary_lower" == *"development plan"* ]]; then
    local phase
    phase="$(phase_from_context "$module_key" "$summary_lower")"
    if [[ "$summary_lower" == *"challenge"* || "$summary_lower" == *"review sync"* ]]; then
      if [[ -n "$phase" ]]; then
        echo "plan ${phase} challenge bridge"
      else
        echo "plan challenge bridge"
      fi
    elif [[ -n "$phase" ]]; then
      echo "plan ${phase} ai judge work"
    else
      echo "plan ai judge work"
    fi
  elif [[ "$module_key" == *"completion-map"* ||
          "$summary_lower" == *"completion map"* ]]; then
    local phase
    phase="$(phase_from_context "$module_key" "$summary_lower")"
    if [[ -n "$phase" ]]; then
      echo "refresh ${phase} completion map"
    else
      echo "refresh ai judge completion map"
    fi
  elif [[ "$module_key" == *"route-dependency-hotspot-split"* ||
          "$summary_lower" == *"route dependency"* ]]; then
    echo "split trust and ops route wiring"
  elif [[ "$module_key" == *"registry-trust-route-hotspot-split"* ||
          "$summary_lower" == *"route projection"* ||
          "$summary_lower" == *"route projections"* ||
          "$summary_lower" == *"hotspot split"* ]]; then
    echo "split registry trust route projections"
  elif [[ "$module_key" == *"local-reference-regression"* ||
          "$summary_lower" == *"local reference"* ]]; then
    if [[ "$module_key" == *"p39-local-reference-regression"* ||
          "$summary_lower" == *"p39"* ]]; then
      echo "record p39 local reference evidence"
    elif [[ "$module_key" == *"p36-local-reference-regression"* ||
            "$summary_lower" == *"p36"* ]]; then
      echo "record p36 local reference evidence"
    else
      echo "record local reference evidence"
    fi
  elif [[ "$module_key" == *"audit-anchor-export"* || "$summary_lower" == *"audit anchor"* ]]; then
    echo "export audit anchor manifest"
  elif [[ "$module_key" == *"ops-read-model-trust"* || "$summary_lower" == *"ops read model"* ]]; then
    echo "add trust coverage to ops read model"
  elif [[ "$module_key" == *"challenge-review-state-machine"* ]]; then
    echo "harden challenge review state machine"
  elif [[ "$module_key" == *"public-verify-redaction"* ]]; then
    echo "harden public verify redaction"
  elif [[ "$module_key" == *"public-verification-chat-proxy"* ||
          "$summary_lower" == *"public verification proxy"* ]]; then
    echo "proxy judge public verification"
  elif [[ "$module_key" == *"public-verification-client-read-model"* ||
          "$summary_lower" == *"public verification read model"* ]]; then
    echo "add judge public verification read model"
  elif [[ "$module_key" == *"challenge-eligibility-contract"* ||
          "$summary_lower" == *"challenge eligibility"* ||
          "$summary_lower" == *"challenge status contract"* ]]; then
    echo "add challenge eligibility status contract"
  elif [[ "$module_key" == *"citation-verifier"* ||
          "$summary_lower" == *"citation verifier"* ||
          "$summary_lower" == *"citation verification"* ]]; then
    echo "add citation verification evidence gate"
  elif [[ "$module_key" == *"trust-registry-write-through"* ]]; then
    echo "write trust registry from judge flow"
  elif [[ "$module_key" == *"trust-registry-store"* ]]; then
    echo "add durable trust registry store"
  elif [[ "$module_key" == *"commit-message"* || "$summary_lower" == *"commit message"* ]]; then
    echo "improve commit message recommendations"
  elif [[ "$summary_lower" == *"文档"* || "$summary_lower" == *"docs"* ]]; then
    echo "update ${scope} docs"
  elif [[ "$summary_lower" == *"lint"* ]]; then
    echo "tighten ${scope} lint rules"
  elif [[ "$summary_lower" == *"重构"* || "$summary_lower" == *"refactor"* ]]; then
    echo "improve ${scope} structure"
  elif [[ "$TASK_KIND" == "refactor" ]]; then
    echo "improve ${scope} maintainability"
  elif [[ "$TASK_KIND" == "non-dev" ]]; then
    echo "update ${scope} docs"
  else
    echo "add ${scope} capability"
  fi
}

build_alt_one_subject() {
  local scope="$1"
  local subject="$2"
  case "$subject" in
    "add local artifact store adapter") echo "add artifact refs and manifest" ;;
    "plan p40 challenge bridge") echo "outline p40 review sync" ;;
    "plan challenge bridge") echo "outline challenge review sync" ;;
    "refresh p40 completion map") echo "align p39 closure mapping" ;;
    "refresh ai judge completion map") echo "align closure mapping" ;;
    plan\ p[0-9]*\ ai\ judge\ work)
      local phase="${subject#plan }"
      phase="${phase% ai judge work}"
      echo "outline ${phase} ai judge modules"
      ;;
    "plan ai judge work") echo "outline ai judge modules" ;;
    archive\ p[0-9]*\ stage\ closure)
      local phase="${subject#archive }"
      phase="${phase% stage closure}"
      echo "record ${phase} closure state"
      ;;
    "archive stage closure") echo "record stage closure state" ;;
    "split trust and ops route wiring") echo "extract trust dependency builders" ;;
    "split registry trust route projections") echo "extract public verify projections" ;;
    "record p36 local reference evidence") echo "refresh runtime ops pack evidence" ;;
    "record p39 local reference evidence") echo "refresh p39 runtime ops evidence" ;;
    "record local reference evidence") echo "refresh runtime ops evidence" ;;
    "improve commit message recommendations") echo "tighten commit message scope inference" ;;
    "export audit anchor manifest") echo "attach artifact manifest to audit anchor" ;;
    "proxy judge public verification") echo "add chat public verify proxy" ;;
    "add judge public verification read model") echo "display judge verification readiness" ;;
    "add challenge eligibility status contract") echo "expose public challenge status" ;;
    "add citation verification evidence gate") echo "wire citation verifier into release evidence" ;;
    "export release readiness artifacts") echo "attach release readiness manifest" ;;
    *) echo "$subject" ;;
  esac
}

build_alt_two_subject() {
  local scope="$1"
  local subject="$2"
  case "$subject" in
    "add local artifact store adapter") echo "wire local artifact evidence" ;;
    "plan p40 challenge bridge") echo "prepare bounded challenge work"
    ;;
    "plan challenge bridge") echo "prepare bounded challenge work" ;;
    "refresh p40 completion map") echo "prepare challenge bridge map" ;;
    "refresh ai judge completion map") echo "prepare next ai judge map" ;;
    plan\ p[0-9]*\ ai\ judge\ work) echo "prepare ai judge next steps" ;;
    "plan ai judge work") echo "prepare ai judge next steps" ;;
    archive\ p[0-9]*\ stage\ closure) echo "reset active ai judge plan" ;;
    "archive stage closure") echo "reset active plan" ;;
    "split trust and ops route wiring") echo "thin app factory route assembly" ;;
    "split registry trust route projections") echo "thin registry and trust routes" ;;
    "record p36 local reference evidence") echo "mark p36 local reference ready" ;;
    "record p39 local reference evidence") echo "mark p39 local reference ready" ;;
    "record local reference evidence") echo "mark local reference ready" ;;
    "improve commit message recommendations") echo "prefer concise commit titles" ;;
    "export audit anchor manifest") echo "prepare audit anchor export" ;;
    "proxy judge public verification") echo "protect public verification contract" ;;
    "add judge public verification read model") echo "sync judge verification client state" ;;
    "add challenge eligibility status contract") echo "protect challenge status redaction" ;;
    "add citation verification evidence gate") echo "summarize citation gate readiness" ;;
    "export release readiness artifacts") echo "sync release readiness evidence" ;;
    *) echo "sync ${scope} follow-up" ;;
  esac
}

format_title() {
  local type="$1"
  local scope="$2"
  local subject="$3"
  subject="$(trim "$subject")"
  if [[ -z "$scope" || "$scope" == "repo" ]]; then
    printf '%s: %s' "$type" "$subject"
  else
    printf '%s(%s): %s' "$type" "$scope" "$subject"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT="$2"
      shift 2
      ;;
    --task-kind)
      TASK_KIND="$2"
      shift 2
      ;;
    --module)
      MODULE="$2"
      shift 2
      ;;
    --summary)
      SUMMARY="$2"
      shift 2
      ;;
    --title-only)
      TITLE_ONLY=1
      shift
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

if [[ -z "$ROOT" ]]; then
  ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
fi

changed_files="$(collect_changed_files)"
scope="$(infer_scope "$changed_files")"
type="$(detect_type "$changed_files")"
subject="$(build_subject "$scope")"
title="$(format_title "$type" "$scope" "$subject")"
alt_one="$(format_title "$type" "$scope" "$(build_alt_one_subject "$scope" "$subject")")"
alt_two="$(format_title "chore" "$scope" "$(build_alt_two_subject "$scope" "$subject")")"

if [[ "$TITLE_ONLY" -eq 1 ]]; then
  printf '%s\n' "$title"
  exit 0
fi

cat <<EOF_RECOMMEND
Recommended:
$title

Alternatives:
1. $alt_one
2. $alt_two
EOF_RECOMMEND
