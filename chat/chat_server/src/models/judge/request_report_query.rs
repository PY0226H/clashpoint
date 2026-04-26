use super::*;
use crate::models::OpsPermission;
use reqwest::Client;
use serde_json::{json, Value};
use sha1::{Digest, Sha1};
use std::collections::HashMap;
use std::time::Duration;
use uuid::Uuid;

const CONTRACT_FAILURE_FINAL_BLOCKED: &str = "final_contract_blocked";
const CONTRACT_FAILURE_PHASE_INCOMPLETE: &str = "phase_artifact_incomplete";
const CONTRACT_FAILURE_ACCEPTED_FALSE: &str = "response_accepted_false";
const CONTRACT_FAILURE_CASE_ID_MISMATCH: &str = "response_case_id_mismatch";
const CONTRACT_FAILURE_UNKNOWN: &str = "unknown_contract_failure";
const DEFAULT_OPS_FAILURE_STATS_SCAN_LIMIT: u32 = 500;
const MAX_OPS_FAILURE_STATS_SCAN_LIMIT: u32 = 5000;
const DEFAULT_OPS_TRACE_REPLAY_LIMIT: u32 = 100;
const MAX_OPS_TRACE_REPLAY_LIMIT: u32 = 500;
const DEFAULT_OPS_REPLAY_ACTIONS_LIMIT: u32 = 100;
const MAX_OPS_REPLAY_ACTIONS_LIMIT: u32 = 500;
const MAX_OPS_REPLAY_ACTIONS_OFFSET: u32 = 10_000;
const MAX_REPLAY_REASON_LEN: usize = 500;
const MAX_OPS_REPLAY_ACTIONS_KEYWORD_LEN: usize = 100;
const MAX_OPS_REPLAY_ACTIONS_STATUS_LEN: usize = 32;
const JUDGE_REPORT_READ_FORBIDDEN: &str = "judge_report_read_forbidden";
const OPS_JUDGE_REPLAY_PREVIEW_CASE_ID_OUT_OF_RANGE: &str =
    "ops_judge_replay_preview_case_id_out_of_range";
const OPS_JUDGE_REPLAY_EXECUTE_CASE_ID_OUT_OF_RANGE: &str =
    "ops_judge_replay_execute_case_id_out_of_range";
const OPS_JUDGE_REPLAY_ACTIONS_SESSION_ID_OUT_OF_RANGE: &str =
    "ops_judge_replay_actions_session_id_out_of_range";
const OPS_JUDGE_REPLAY_ACTIONS_CASE_ID_OUT_OF_RANGE: &str =
    "ops_judge_replay_actions_case_id_out_of_range";
const OPS_JUDGE_REPLAY_ACTIONS_REQUESTED_BY_OUT_OF_RANGE: &str =
    "ops_judge_replay_actions_requested_by_out_of_range";
const JUDGE_REPORT_RUN_NO_OUT_OF_RANGE: &str = "judge_report_run_no_out_of_range";
const JUDGE_REPORT_RUN_NO_INVALID: &str = "judge_report_run_no_invalid";

const JUDGE_REPORT_STATUS_READY: &str = "ready";
const JUDGE_REPORT_STATUS_PENDING: &str = "pending";
const JUDGE_REPORT_STATUS_BLOCKED: &str = "blocked";
const JUDGE_REPORT_STATUS_DEGRADED: &str = "degraded";
const JUDGE_REPORT_STATUS_ABSENT: &str = "absent";
const JUDGE_REPORT_STATUS_REVIEW_REQUIRED: &str = "review_required";

const JUDGE_REPORT_REASON_FINAL_REPORT_READY: &str = "final_report_ready";
const JUDGE_REPORT_REASON_FINAL_REPORT_REVIEW_REQUIRED: &str = "final_report_review_required";
const JUDGE_REPORT_REASON_DRAW_PENDING_VOTE: &str = "draw_pending_vote";
const JUDGE_REPORT_REASON_FINAL_JOB_IN_PROGRESS: &str = "final_job_in_progress";
const JUDGE_REPORT_REASON_FINAL_DISPATCH_FAILED: &str = "final_dispatch_failed";
const JUDGE_REPORT_REASON_FINAL_REPORT_MISSING: &str = "final_report_missing_after_dispatch";
const JUDGE_REPORT_REASON_PHASE_FAILED_WAITING_REPLAY: &str = "phase_failed_waiting_replay";
const JUDGE_REPORT_REASON_PHASE_IN_PROGRESS: &str = "phase_jobs_in_progress";
const JUDGE_REPORT_REASON_NO_JUDGE_JOBS: &str = "no_judge_jobs";

const JUDGE_PUBLIC_VERIFY_STATUS_READY: &str = "ready";
const JUDGE_PUBLIC_VERIFY_STATUS_NOT_READY: &str = "not_ready";
const JUDGE_PUBLIC_VERIFY_STATUS_ABSENT: &str = "absent";
const JUDGE_PUBLIC_VERIFY_STATUS_PROXY_ERROR: &str = "proxy_error";
const JUDGE_PUBLIC_VERIFY_REASON_READY: &str = "public_verify_ready";
const JUDGE_PUBLIC_VERIFY_REASON_NOT_READY: &str = "public_verify_not_ready";
const JUDGE_PUBLIC_VERIFY_REASON_CASE_ABSENT: &str = "public_verify_case_absent";
const JUDGE_PUBLIC_VERIFY_REASON_PROXY_FAILED: &str = "public_verify_proxy_failed";
const JUDGE_PUBLIC_VERIFY_REASON_CONTRACT_VIOLATION: &str = "public_verify_contract_violation";

fn normalize_ops_review_limit(limit: Option<u32>) -> i64 {
    let requested = limit.unwrap_or(DEFAULT_OPS_JUDGE_REVIEW_LIMIT);
    requested.clamp(1, MAX_OPS_JUDGE_REVIEW_LIMIT) as i64
}

fn normalize_ops_failure_stats_scan_limit(limit: Option<u32>) -> i64 {
    let requested = limit.unwrap_or(DEFAULT_OPS_FAILURE_STATS_SCAN_LIMIT);
    requested.clamp(1, MAX_OPS_FAILURE_STATS_SCAN_LIMIT) as i64
}

fn normalize_ops_trace_replay_limit(limit: Option<u32>) -> i64 {
    let requested = limit.unwrap_or(DEFAULT_OPS_TRACE_REPLAY_LIMIT);
    requested.clamp(1, MAX_OPS_TRACE_REPLAY_LIMIT) as i64
}

fn normalize_ops_replay_actions_limit(limit: Option<u32>) -> i64 {
    let requested = limit.unwrap_or(DEFAULT_OPS_REPLAY_ACTIONS_LIMIT);
    requested.clamp(1, MAX_OPS_REPLAY_ACTIONS_LIMIT) as i64
}

fn normalize_ops_replay_actions_offset(offset: Option<u32>) -> i64 {
    offset.unwrap_or(0).clamp(0, MAX_OPS_REPLAY_ACTIONS_OFFSET) as i64
}

fn normalize_optional_trace_scope_filter(
    scope: Option<String>,
) -> Result<Option<String>, AppError> {
    match scope {
        Some(value) => {
            let trimmed = value.trim().to_ascii_lowercase();
            if trimmed.is_empty() {
                Ok(None)
            } else if trimmed == "phase" || trimmed == "final" {
                Ok(Some(trimmed))
            } else {
                Err(AppError::DebateError(
                    "scope must be one of: phase, final".to_string(),
                ))
            }
        }
        None => Ok(None),
    }
}

fn normalize_optional_trace_status_filter(
    status: Option<String>,
) -> Result<Option<String>, AppError> {
    match status {
        Some(value) => {
            let trimmed = value.trim().to_ascii_lowercase();
            if trimmed.is_empty() {
                Ok(None)
            } else if matches!(
                trimmed.as_str(),
                "queued" | "dispatched" | "succeeded" | "failed"
            ) {
                Ok(Some(trimmed))
            } else {
                Err(AppError::DebateError(
                    "status must be one of: queued, dispatched, succeeded, failed".to_string(),
                ))
            }
        }
        None => Ok(None),
    }
}

fn normalize_optional_replay_actions_status_filter(
    field_name: &str,
    status: Option<String>,
) -> Result<Option<String>, AppError> {
    match status {
        Some(value) => {
            let normalized = value.trim().to_ascii_lowercase();
            if normalized.is_empty() {
                return Ok(None);
            }
            if normalized.chars().count() > MAX_OPS_REPLAY_ACTIONS_STATUS_LEN {
                return Err(AppError::DebateError(format!(
                    "{field_name} is too long, max {} chars",
                    MAX_OPS_REPLAY_ACTIONS_STATUS_LEN
                )));
            }
            if !normalized
                .chars()
                .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '_' || c == '-')
            {
                return Err(AppError::DebateError(format!(
                    "{field_name} contains unsupported characters"
                )));
            }
            Ok(Some(normalized))
        }
        None => Ok(None),
    }
}

fn normalize_optional_replay_actions_keyword(
    field_name: &str,
    keyword: Option<String>,
) -> Result<Option<String>, AppError> {
    match keyword {
        Some(value) => {
            let trimmed = value.trim();
            if trimmed.is_empty() {
                return Ok(None);
            }
            if trimmed.chars().count() > MAX_OPS_REPLAY_ACTIONS_KEYWORD_LEN {
                return Err(AppError::DebateError(format!(
                    "{field_name} is too long, max {} chars",
                    MAX_OPS_REPLAY_ACTIONS_KEYWORD_LEN
                )));
            }
            Ok(Some(trimmed.to_string()))
        }
        None => Ok(None),
    }
}

fn normalize_replay_scope(scope: &str) -> Result<String, AppError> {
    let normalized = scope.trim().to_ascii_lowercase();
    if normalized == "phase" || normalized == "final" {
        Ok(normalized)
    } else {
        Err(AppError::DebateError(
            "scope must be one of: phase, final".to_string(),
        ))
    }
}

fn checked_u64_to_i64(value: u64, code: &'static str) -> Result<i64, AppError> {
    i64::try_from(value).map_err(|_| AppError::DebateError(code.to_string()))
}

async fn resolve_target_rejudge_run_no(
    tx: &mut Transaction<'_, Postgres>,
    session_id: i64,
    requested_run_no: Option<u32>,
) -> Result<i32, AppError> {
    if let Some(run_no) = requested_run_no {
        if run_no == 0 {
            return Err(AppError::DebateError(
                JUDGE_REPORT_RUN_NO_INVALID.to_string(),
            ));
        }
        return i32::try_from(run_no)
            .map_err(|_| AppError::DebateError(JUDGE_REPORT_RUN_NO_OUT_OF_RANGE.to_string()));
    }

    let latest_run_no: i32 = sqlx::query_scalar(
        r#"
        SELECT GREATEST(
            COALESCE((SELECT MAX(rejudge_run_no) FROM judge_phase_jobs WHERE session_id = $1), 0),
            COALESCE((SELECT MAX(rejudge_run_no) FROM judge_final_jobs WHERE session_id = $1), 0),
            COALESCE((SELECT MAX(rejudge_run_no) FROM judge_final_reports WHERE session_id = $1), 0)
        )::int
        "#,
    )
    .bind(session_id)
    .fetch_one(&mut **tx)
    .await?;
    Ok(latest_run_no)
}

fn normalize_public_verify_dispatch_type(
    dispatch_type: Option<String>,
) -> Result<String, AppError> {
    let normalized = dispatch_type
        .unwrap_or_else(|| "final".to_string())
        .trim()
        .to_ascii_lowercase();
    if normalized.is_empty() || normalized == "final" {
        Ok("final".to_string())
    } else if normalized == "phase" {
        Ok(normalized)
    } else {
        Err(AppError::DebateError(
            "dispatchType must be one of: phase, final".to_string(),
        ))
    }
}

fn build_ai_judge_http_url(base_url: &str, path: &str, case_id: u64) -> String {
    let resolved_path = path
        .replace("{case_id}", &case_id.to_string())
        .replace(":case_id", &case_id.to_string());
    let resolved_path = if resolved_path.starts_with('/') {
        resolved_path
    } else {
        format!("/{resolved_path}")
    };
    format!("{}{}", base_url.trim_end_matches('/'), resolved_path)
}

fn default_public_verify_readiness(ready: bool, status: &str, blocker: Option<&str>) -> Value {
    let blockers = blocker
        .map(|item| json!([item]))
        .unwrap_or_else(|| json!([]));
    json!({
        "ready": ready,
        "status": status,
        "blockers": blockers,
        "externalizable": ready
    })
}

fn default_public_verify_cache_profile(session_id: u64, dispatch_type: &str) -> Value {
    json!({
        "cacheable": false,
        "ttlSeconds": 0,
        "staleWhileRevalidateSeconds": 0,
        "cacheKey": format!(
            "public-verify:chat-proxy:session:{session_id}:dispatch:{dispatch_type}"
        ),
        "varyBy": ["authorization", "rejudgeRunNo", "dispatchType"]
    })
}

fn build_public_verify_absent_output(
    session_id: u64,
    dispatch_type: String,
) -> GetJudgePublicVerifyOutput {
    GetJudgePublicVerifyOutput {
        session_id,
        status: JUDGE_PUBLIC_VERIFY_STATUS_ABSENT.to_string(),
        status_reason: JUDGE_PUBLIC_VERIFY_REASON_CASE_ABSENT.to_string(),
        case_id: None,
        dispatch_type: dispatch_type.clone(),
        verification_readiness: default_public_verify_readiness(
            false,
            JUDGE_PUBLIC_VERIFY_STATUS_ABSENT,
            Some(JUDGE_PUBLIC_VERIFY_REASON_CASE_ABSENT),
        ),
        cache_profile: default_public_verify_cache_profile(session_id, &dispatch_type),
        public_verify: json!({}),
    }
}

fn build_public_verify_proxy_error_output(
    session_id: u64,
    case_id: u64,
    dispatch_type: String,
    reason_code: &str,
) -> GetJudgePublicVerifyOutput {
    GetJudgePublicVerifyOutput {
        session_id,
        status: JUDGE_PUBLIC_VERIFY_STATUS_PROXY_ERROR.to_string(),
        status_reason: reason_code.to_string(),
        case_id: Some(case_id),
        dispatch_type: dispatch_type.clone(),
        verification_readiness: default_public_verify_readiness(
            false,
            JUDGE_PUBLIC_VERIFY_STATUS_PROXY_ERROR,
            Some(reason_code),
        ),
        cache_profile: default_public_verify_cache_profile(session_id, &dispatch_type),
        public_verify: json!({}),
    }
}

async fn fetch_ai_judge_public_verify_payload(
    base_url: &str,
    path: &str,
    timeout_ms: u64,
    internal_key: &str,
    case_id: u64,
    dispatch_type: &str,
) -> Result<Value, &'static str> {
    let url = build_ai_judge_http_url(base_url, path, case_id);
    let client = Client::builder()
        .timeout(Duration::from_millis(timeout_ms.max(1)))
        .build()
        .map_err(|_| "public_verify_proxy_http_client_failed")?;
    let response = client
        .get(url)
        .header("x-ai-internal-key", internal_key)
        .query(&[("dispatch_type", dispatch_type)])
        .send()
        .await
        .map_err(|_| "public_verify_proxy_request_failed")?;
    if !response.status().is_success() {
        return Err("public_verify_proxy_bad_status");
    }
    response
        .json::<Value>()
        .await
        .map_err(|_| "public_verify_proxy_bad_json")
}

fn is_public_verify_forbidden_key(key: &str) -> bool {
    let normalized: String = key
        .chars()
        .filter(|c| *c != '_' && *c != '-')
        .flat_map(char::to_lowercase)
        .collect();
    matches!(
        normalized.as_str(),
        "provider"
            | "rawtrace"
            | "prompt"
            | "privateaudit"
            | "bucket"
            | "endpoint"
            | "path"
            | "secret"
            | "secretref"
            | "credential"
            | "internalkey"
            | "xaiinternalkey"
    )
}

fn public_verify_value_contains_forbidden_key(value: &Value) -> bool {
    match value {
        Value::Object(map) => map.iter().any(|(key, value)| {
            is_public_verify_forbidden_key(key) || public_verify_value_contains_forbidden_key(value)
        }),
        Value::Array(items) => items.iter().any(public_verify_value_contains_forbidden_key),
        _ => false,
    }
}

fn validate_public_verify_payload(
    payload: &Value,
    expected_case_id: u64,
    dispatch_type: &str,
) -> Result<(), &'static str> {
    let Some(object) = payload.as_object() else {
        return Err(JUDGE_PUBLIC_VERIFY_REASON_CONTRACT_VIOLATION);
    };
    if !object
        .get("proxyRequired")
        .and_then(Value::as_bool)
        .unwrap_or(false)
    {
        return Err(JUDGE_PUBLIC_VERIFY_REASON_CONTRACT_VIOLATION);
    }
    if object.get("caseId").and_then(Value::as_u64) != Some(expected_case_id) {
        return Err(JUDGE_PUBLIC_VERIFY_REASON_CONTRACT_VIOLATION);
    }
    if object.get("dispatchType").and_then(Value::as_str) != Some(dispatch_type) {
        return Err(JUDGE_PUBLIC_VERIFY_REASON_CONTRACT_VIOLATION);
    }
    if !object.contains_key("verificationReadiness") || !object.contains_key("cacheProfile") {
        return Err(JUDGE_PUBLIC_VERIFY_REASON_CONTRACT_VIOLATION);
    }
    if public_verify_value_contains_forbidden_key(payload) {
        return Err(JUDGE_PUBLIC_VERIFY_REASON_CONTRACT_VIOLATION);
    }
    Ok(())
}

fn resolve_public_verify_status(payload: &Value) -> (String, String) {
    let readiness = payload
        .get("verificationReadiness")
        .cloned()
        .unwrap_or_else(|| default_public_verify_readiness(false, "missing", None));
    if readiness
        .get("ready")
        .and_then(Value::as_bool)
        .unwrap_or(false)
    {
        return (
            JUDGE_PUBLIC_VERIFY_STATUS_READY.to_string(),
            JUDGE_PUBLIC_VERIFY_REASON_READY.to_string(),
        );
    }

    let reason = readiness
        .get("status")
        .and_then(Value::as_str)
        .filter(|value| !value.trim().is_empty())
        .unwrap_or(JUDGE_PUBLIC_VERIFY_REASON_NOT_READY);
    (
        JUDGE_PUBLIC_VERIFY_STATUS_NOT_READY.to_string(),
        reason.to_string(),
    )
}

fn is_replay_eligible_status(status: &str) -> bool {
    matches!(status, "failed" | "succeeded")
}

fn compute_snapshot_hash(snapshot: &Value) -> Result<String, AppError> {
    let encoded = serde_json::to_vec(snapshot)
        .map_err(|e| AppError::DebateError(format!("serialize replay snapshot failed: {e}")))?;
    let mut hasher = Sha1::new();
    hasher.update(encoded);
    Ok(format!("{:x}", hasher.finalize()))
}

fn normalize_optional_replay_reason(reason: Option<String>) -> Result<Option<String>, AppError> {
    let Some(value) = reason else {
        return Ok(None);
    };
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return Ok(None);
    }
    if trimmed.chars().count() > MAX_REPLAY_REASON_LEN {
        return Err(AppError::DebateError(format!(
            "reason is too long, max {} chars",
            MAX_REPLAY_REASON_LEN
        )));
    }
    Ok(Some(trimmed.to_string()))
}

fn build_replay_trace_id(scope: &str, case_id: u64) -> String {
    format!("judge-replay-{scope}-{case_id}-{}", Uuid::now_v7())
}

fn build_replay_idempotency_key(scope: &str, case_id: u64) -> String {
    format!("judge-replay:{scope}:{case_id}:{}", Uuid::now_v7())
}

fn normalize_optional_winner_filter(winner: Option<String>) -> Result<Option<String>, AppError> {
    match winner {
        Some(value) => {
            let trimmed = value.trim();
            if trimmed.is_empty() {
                Ok(None)
            } else {
                Ok(Some(normalize_winner(trimmed, "winner")?))
            }
        }
        None => Ok(None),
    }
}

fn detect_ops_review_abnormal_flags(item: &JudgeReviewOpsItem) -> Vec<String> {
    let mut flags = Vec::new();
    let winner_first_missing = item
        .winner_first
        .as_deref()
        .map(str::trim)
        .filter(|v| !v.is_empty())
        .is_none();
    let winner_second_missing = item
        .winner_second
        .as_deref()
        .map(str::trim)
        .filter(|v| !v.is_empty())
        .is_none();
    if item.verdict_evidence_count == 0 {
        flags.push("missing_verdict_evidence_refs".to_string());
    }
    if item.winner != "draw" && item.score_gap <= 3 {
        flags.push("narrow_score_gap".to_string());
    }
    if item.review_required {
        flags.push("review_required_pending_decision".to_string());
    }
    if item.winner == "draw" && !item.needs_draw_vote {
        flags.push("draw_without_vote_flow".to_string());
    }
    if let (Some(first), Some(second)) =
        (item.winner_first.as_deref(), item.winner_second.as_deref())
    {
        if first != second {
            flags.push("winner_inconsistent_between_two_passes".to_string());
        }
    }
    if winner_first_missing || winner_second_missing {
        flags.push("winner_pass_missing".to_string());
    }
    flags
}

fn extract_dispatch_error_code(error_message: &str) -> Option<String> {
    let trimmed = error_message.trim();
    let coded = trimmed.strip_prefix('[')?;
    let end = coded.find(']')?;
    let code = coded[..end].trim();
    if code.is_empty() {
        None
    } else {
        Some(code.to_string())
    }
}

fn detect_contract_violation_blocked(error_message: &str) -> bool {
    let normalized = error_message.to_ascii_lowercase();
    normalized.contains("final_contract_blocked")
        || normalized.contains("final_contract_violation")
        || normalized.contains("phase_artifact_incomplete")
}

fn infer_contract_failure_type(
    error_code: Option<&str>,
    error_message: Option<&str>,
) -> Option<String> {
    let code = error_code.unwrap_or_default().trim();
    if code == CONTRACT_FAILURE_ACCEPTED_FALSE {
        return Some(CONTRACT_FAILURE_ACCEPTED_FALSE.to_string());
    }
    if code == CONTRACT_FAILURE_CASE_ID_MISMATCH {
        return Some(CONTRACT_FAILURE_CASE_ID_MISMATCH.to_string());
    }

    let normalized = error_message
        .unwrap_or_default()
        .trim()
        .to_ascii_lowercase();
    if normalized.is_empty() {
        return None;
    }
    if normalized.contains("final_contract_blocked") {
        return Some(CONTRACT_FAILURE_FINAL_BLOCKED.to_string());
    }
    if normalized.contains("final_contract_violation")
        || normalized.contains("phase_artifact_incomplete")
    {
        return Some(CONTRACT_FAILURE_PHASE_INCOMPLETE.to_string());
    }
    if normalized.contains("accepted=false") {
        return Some(CONTRACT_FAILURE_ACCEPTED_FALSE.to_string());
    }
    if normalized.contains("case_id mismatch") {
        return Some(CONTRACT_FAILURE_CASE_ID_MISMATCH.to_string());
    }
    None
}

fn resolve_contract_failure_type(
    status: &str,
    error_code: Option<&str>,
    error_message: Option<&str>,
) -> Option<String> {
    if let Some(mapped) = infer_contract_failure_type(error_code, error_message) {
        return Some(mapped);
    }
    if status.trim().eq_ignore_ascii_case("failed") {
        return Some(CONTRACT_FAILURE_UNKNOWN.to_string());
    }
    None
}

fn resolve_contract_failure_hint_and_action(
    contract_failure_type: Option<&str>,
) -> (Option<String>, Option<String>) {
    match contract_failure_type {
        Some(CONTRACT_FAILURE_FINAL_BLOCKED) | Some(CONTRACT_FAILURE_PHASE_INCOMPLETE) => (
            Some("终局派发被合同校验阻断，请先补齐阶段产物后重试。".to_string()),
            Some("check_phase_artifacts_then_retry".to_string()),
        ),
        Some(CONTRACT_FAILURE_ACCEPTED_FALSE) => (
            Some("AI 服务返回 accepted=false，请检查请求参数或服务可用性后重试。".to_string()),
            Some("check_ai_judge_acceptance_then_retry".to_string()),
        ),
        Some(CONTRACT_FAILURE_CASE_ID_MISMATCH) => (
            Some("AI 服务返回 case_id 不一致，请核对 dispatch 契约版本。".to_string()),
            Some("check_dispatch_contract_alignment".to_string()),
        ),
        Some(CONTRACT_FAILURE_UNKNOWN) => (
            Some("终局派发失败语义未识别，请结合 errorMessage 排障后重试或升级处理。".to_string()),
            Some("inspect_error_then_retry_or_escalate".to_string()),
        ),
        Some(_) => (
            Some("终局派发失败，请结合 errorMessage 排障。".to_string()),
            Some("inspect_error_then_retry".to_string()),
        ),
        None => (None, None),
    }
}

fn map_final_dispatch_diagnostics(row: JudgeFinalJobSnapshotRow) -> JudgeFinalDispatchDiagnostics {
    let status = row.status;
    let error_message = row.error_message;
    let error_code = row.error_code.or_else(|| {
        error_message
            .as_deref()
            .and_then(extract_dispatch_error_code)
    });
    let contract_failure_type = row.contract_failure_type.or_else(|| {
        resolve_contract_failure_type(
            status.as_str(),
            error_code.as_deref(),
            error_message.as_deref(),
        )
    });
    let (contract_failure_hint, contract_failure_action) =
        resolve_contract_failure_hint_and_action(contract_failure_type.as_deref());
    let contract_violation_blocked = error_message
        .as_deref()
        .map(detect_contract_violation_blocked)
        .unwrap_or(false);
    JudgeFinalDispatchDiagnostics {
        final_job_id: row.id as u64,
        status,
        phase_start_no: row.phase_start_no,
        phase_end_no: row.phase_end_no,
        dispatch_attempts: row.dispatch_attempts,
        last_dispatch_at: row.last_dispatch_at,
        error_message,
        error_code,
        contract_failure_type,
        contract_failure_hint,
        contract_failure_action,
        contract_violation_blocked,
    }
}

#[derive(Debug, Clone, sqlx::FromRow)]
struct FinalDispatchFailureSampleRow {
    status: String,
    error_message: Option<String>,
    error_code: Option<String>,
    contract_failure_type: Option<String>,
}

fn build_final_dispatch_failure_stats(
    rows: Vec<FinalDispatchFailureSampleRow>,
) -> Option<JudgeFinalDispatchFailureStats> {
    if rows.is_empty() {
        return None;
    }
    let mut counters: HashMap<String, u32> = HashMap::new();
    for row in rows {
        let structured_failure_type = row
            .contract_failure_type
            .as_deref()
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .map(ToString::to_string);
        let error_code = row
            .error_code
            .as_deref()
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .map(ToString::to_string)
            .or_else(|| {
                row.error_message
                    .as_deref()
                    .and_then(extract_dispatch_error_code)
            });
        let failure_type = structured_failure_type
            .or_else(|| {
                resolve_contract_failure_type(
                    row.status.as_str(),
                    error_code.as_deref(),
                    row.error_message.as_deref(),
                )
            })
            .unwrap_or_else(|| CONTRACT_FAILURE_UNKNOWN.to_string());
        let entry = counters.entry(failure_type).or_insert(0);
        *entry = entry.saturating_add(1);
    }

    let mut by_type: Vec<JudgeFinalDispatchFailureTypeCount> = counters
        .into_iter()
        .map(|(failure_type, count)| JudgeFinalDispatchFailureTypeCount {
            failure_type,
            count,
        })
        .collect();
    by_type.sort_by(|a, b| {
        b.count
            .cmp(&a.count)
            .then_with(|| a.failure_type.cmp(&b.failure_type))
    });

    let total_failed_jobs: u32 = by_type.iter().map(|item| item.count).sum();
    let unknown_failed_jobs = by_type
        .iter()
        .find(|item| item.failure_type == CONTRACT_FAILURE_UNKNOWN)
        .map(|item| item.count)
        .unwrap_or(0);

    Some(JudgeFinalDispatchFailureStats {
        total_failed_jobs,
        unknown_failed_jobs,
        by_type,
    })
}

#[derive(Debug, Clone, sqlx::FromRow)]
struct JudgePhaseProgressCountsRow {
    total_phase_jobs: i64,
    queued_phase_jobs: i64,
    dispatched_phase_jobs: i64,
    succeeded_phase_jobs: i64,
    failed_phase_jobs: i64,
}

fn to_u32_count(v: i64) -> u32 {
    if v <= 0 {
        0
    } else {
        u32::try_from(v).unwrap_or(u32::MAX)
    }
}

fn map_final_report_summary(v: &JudgeFinalReportDetail) -> JudgeFinalReportSummary {
    JudgeFinalReportSummary {
        final_report_id: v.final_report_id,
        winner: v.winner.clone(),
        pro_score: v.pro_score,
        con_score: v.con_score,
        rejudge_triggered: v.rejudge_triggered,
        needs_draw_vote: v.needs_draw_vote,
        review_required: v.review_required,
        degradation_level: v.degradation_level,
        created_at: v.created_at,
    }
}

fn resolve_judge_report_status(
    latest_final_job: Option<&JudgeFinalJobSnapshotRow>,
    progress: &JudgeReportProgress,
    final_report: Option<&JudgeFinalReportDetail>,
) -> (String, String) {
    if let Some(report) = final_report {
        if report.review_required {
            return (
                JUDGE_REPORT_STATUS_REVIEW_REQUIRED.to_string(),
                JUDGE_REPORT_REASON_FINAL_REPORT_REVIEW_REQUIRED.to_string(),
            );
        }
        if report.winner == "draw" && report.needs_draw_vote {
            return (
                JUDGE_REPORT_STATUS_READY.to_string(),
                JUDGE_REPORT_REASON_DRAW_PENDING_VOTE.to_string(),
            );
        }
        return (
            JUDGE_REPORT_STATUS_READY.to_string(),
            JUDGE_REPORT_REASON_FINAL_REPORT_READY.to_string(),
        );
    }

    if let Some(final_job) = latest_final_job {
        return match final_job.status.as_str() {
            "failed" => (
                JUDGE_REPORT_STATUS_DEGRADED.to_string(),
                JUDGE_REPORT_REASON_FINAL_DISPATCH_FAILED.to_string(),
            ),
            "queued" | "dispatched" => (
                JUDGE_REPORT_STATUS_PENDING.to_string(),
                JUDGE_REPORT_REASON_FINAL_JOB_IN_PROGRESS.to_string(),
            ),
            "succeeded" => (
                JUDGE_REPORT_STATUS_BLOCKED.to_string(),
                JUDGE_REPORT_REASON_FINAL_REPORT_MISSING.to_string(),
            ),
            _ => (
                JUDGE_REPORT_STATUS_PENDING.to_string(),
                JUDGE_REPORT_REASON_FINAL_JOB_IN_PROGRESS.to_string(),
            ),
        };
    }

    if progress.failed_phase_jobs > 0 {
        return (
            JUDGE_REPORT_STATUS_BLOCKED.to_string(),
            JUDGE_REPORT_REASON_PHASE_FAILED_WAITING_REPLAY.to_string(),
        );
    }

    if progress.total_phase_jobs > 0 {
        return (
            JUDGE_REPORT_STATUS_PENDING.to_string(),
            JUDGE_REPORT_REASON_PHASE_IN_PROGRESS.to_string(),
        );
    }

    (
        JUDGE_REPORT_STATUS_ABSENT.to_string(),
        JUDGE_REPORT_REASON_NO_JUDGE_JOBS.to_string(),
    )
}

fn map_judge_trace_replay_ops_item(row: JudgeTraceReplayOpsRow) -> JudgeTraceReplayOpsItem {
    let case_id = row
        .phase_job_id
        .or(row.final_job_id)
        .and_then(|v| u64::try_from(v).ok())
        .unwrap_or(0);
    let report_id = row
        .phase_report_id
        .or(row.final_report_id)
        .and_then(|v| u64::try_from(v).ok());
    let replay_action_count = if row.replay_action_count <= 0 {
        0
    } else {
        u32::try_from(row.replay_action_count).unwrap_or(u32::MAX)
    };
    let scope = row.scope;
    let status = row.status;
    let error_message = row.error_message;
    let error_code = row.error_code.or_else(|| {
        error_message
            .as_deref()
            .and_then(extract_dispatch_error_code)
    });
    let contract_failure_type = if scope == "final" {
        row.contract_failure_type.or_else(|| {
            resolve_contract_failure_type(
                status.as_str(),
                error_code.as_deref(),
                error_message.as_deref(),
            )
        })
    } else {
        None
    };
    let replay_eligible = matches!(status.as_str(), "failed" | "succeeded");
    let replay_recommendation = if replay_eligible {
        if scope == "phase" {
            Some("replay_phase_case".to_string())
        } else {
            Some("replay_final_case".to_string())
        }
    } else {
        None
    };

    JudgeTraceReplayOpsItem {
        scope,
        session_id: row.session_id as u64,
        trace_id: row.trace_id,
        idempotency_key: row.idempotency_key,
        status,
        created_at: row.created_at,
        dispatch_attempts: row.dispatch_attempts,
        last_dispatch_at: row.last_dispatch_at,
        error_message,
        error_code,
        contract_failure_type,
        phase_case_id: row.phase_job_id.map(|v| v as u64),
        final_case_id: row.final_job_id.map(|v| v as u64),
        phase_no: row.phase_no,
        phase_start_no: row.phase_start_no,
        phase_end_no: row.phase_end_no,
        phase_report_id: row.phase_report_id.map(|v| v as u64),
        final_report_id: row.final_report_id.map(|v| v as u64),
        case_id,
        report_id,
        replay_action_count,
        latest_replay_action_id: row.latest_replay_action_id.map(|v| v as u64),
        latest_replay_at: row.latest_replay_at,
        replay_eligible,
        replay_recommendation,
    }
}

fn map_judge_replay_action_ops_item(row: JudgeReplayActionOpsRow) -> JudgeReplayActionOpsItem {
    JudgeReplayActionOpsItem {
        audit_id: row.audit_id as u64,
        scope: row.scope,
        case_id: row.job_id as u64,
        session_id: row.session_id as u64,
        requested_by: row.requested_by as u64,
        reason: row.reason,
        previous_status: row.previous_status,
        new_status: row.new_status,
        previous_trace_id: row.previous_trace_id,
        new_trace_id: row.new_trace_id,
        previous_idempotency_key: row.previous_idempotency_key,
        new_idempotency_key: row.new_idempotency_key,
        created_at: row.created_at,
    }
}

impl AppState {
    pub async fn list_judge_reviews_by_owner(
        &self,
        user: &User,
        query: ListJudgeReviewOpsQuery,
    ) -> Result<ListJudgeReviewOpsOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeReview)
            .await?;
        if let (Some(from), Some(to)) = (query.from, query.to) {
            if from > to {
                return Err(AppError::DebateError("from must be <= to".to_string()));
            }
        }

        let winner_filter = normalize_optional_winner_filter(query.winner)?;
        let row_limit = normalize_ops_review_limit(query.limit);
        let scan_limit = if query.anomaly_only {
            (row_limit * 4).min((MAX_OPS_JUDGE_REVIEW_LIMIT as i64) * 4)
        } else {
            row_limit
        };

        let rows: Vec<JudgeReviewOpsRow> = sqlx::query_as(
            r#"
            SELECT
                r.id AS report_id,
                r.session_id,
                r.final_job_id AS job_id,
                r.winner,
                r.winner_first,
                r.winner_second,
                r.winner_third,
                ROUND(r.pro_score)::int AS pro_score,
                ROUND(r.con_score)::int AS con_score,
                'v3'::varchar AS style_mode,
                f.rubric_version,
                r.needs_draw_vote,
                r.review_required,
                r.rejudge_triggered,
                CASE
                    WHEN jsonb_typeof(r.verdict_evidence_refs) = 'array'
                    THEN jsonb_array_length(r.verdict_evidence_refs)
                    ELSE 0
                END AS verdict_evidence_count,
                r.created_at
            FROM judge_final_reports r
            JOIN judge_final_jobs f ON f.id = r.final_job_id
            WHERE ($1::timestamptz IS NULL OR r.created_at >= $1)
              AND ($2::timestamptz IS NULL OR r.created_at <= $2)
              AND ($3::varchar IS NULL OR r.winner = $3)
              AND ($4::boolean IS NULL OR r.rejudge_triggered = $4)
              AND (
                $5::boolean IS NULL
                OR (
                    CASE
                        WHEN jsonb_typeof(r.verdict_evidence_refs) = 'array'
                        THEN jsonb_array_length(r.verdict_evidence_refs) > 0
                        ELSE FALSE
                    END
                ) = $5
              )
            ORDER BY r.created_at DESC
            LIMIT $6
            "#,
        )
        .bind(query.from)
        .bind(query.to)
        .bind(winner_filter)
        .bind(query.rejudge_triggered)
        .bind(query.has_verdict_evidence)
        .bind(scan_limit)
        .fetch_all(&self.pool)
        .await?;

        let scanned_count = u32::try_from(rows.len()).unwrap_or(u32::MAX);
        let mut items = Vec::new();
        for row in rows {
            let verdict_evidence_count = if row.verdict_evidence_count <= 0 {
                0
            } else {
                u32::try_from(row.verdict_evidence_count).unwrap_or(u32::MAX)
            };
            let score_gap = row.pro_score.abs_diff(row.con_score) as i32;
            let mut item = JudgeReviewOpsItem {
                report_id: row.report_id as u64,
                session_id: row.session_id as u64,
                job_id: row.job_id as u64,
                winner: row.winner,
                winner_first: row.winner_first,
                winner_second: row.winner_second,
                winner_third: row.winner_third,
                pro_score: row.pro_score,
                con_score: row.con_score,
                score_gap,
                style_mode: row.style_mode,
                rubric_version: row.rubric_version,
                needs_draw_vote: row.needs_draw_vote,
                review_required: row.review_required,
                rejudge_triggered: row.rejudge_triggered,
                has_verdict_evidence: verdict_evidence_count > 0,
                verdict_evidence_count,
                abnormal_flags: Vec::new(),
                created_at: row.created_at,
            };
            item.abnormal_flags = detect_ops_review_abnormal_flags(&item);
            if query.anomaly_only && item.abnormal_flags.is_empty() {
                continue;
            }
            items.push(item);
            if i64::try_from(items.len()).unwrap_or(i64::MAX) >= row_limit {
                break;
            }
        }

        Ok(ListJudgeReviewOpsOutput {
            scanned_count,
            returned_count: u32::try_from(items.len()).unwrap_or(u32::MAX),
            items,
        })
    }

    pub async fn get_judge_final_dispatch_failure_stats_by_owner(
        &self,
        user: &User,
        query: GetJudgeFinalDispatchFailureStatsQuery,
    ) -> Result<GetJudgeFinalDispatchFailureStatsOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeReview)
            .await?;
        if let (Some(from), Some(to)) = (query.from, query.to) {
            if from > to {
                return Err(AppError::DebateError("from must be <= to".to_string()));
            }
        }

        let scan_limit = normalize_ops_failure_stats_scan_limit(query.limit);
        let total_failed_jobs_i64: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(*)::bigint
            FROM judge_final_jobs
            WHERE status = 'failed'
              AND ($1::timestamptz IS NULL OR created_at >= $1)
              AND ($2::timestamptz IS NULL OR created_at <= $2)
            "#,
        )
        .bind(query.from)
        .bind(query.to)
        .fetch_one(&self.pool)
        .await?;
        let sampled_rows: Vec<FinalDispatchFailureSampleRow> = sqlx::query_as(
            r#"
            SELECT status, error_message, error_code, contract_failure_type
            FROM judge_final_jobs
            WHERE status = 'failed'
              AND ($1::timestamptz IS NULL OR created_at >= $1)
              AND ($2::timestamptz IS NULL OR created_at <= $2)
            ORDER BY created_at DESC
            LIMIT $3
            "#,
        )
        .bind(query.from)
        .bind(query.to)
        .bind(scan_limit)
        .fetch_all(&self.pool)
        .await?;

        let sampled_stats = build_final_dispatch_failure_stats(sampled_rows).unwrap_or(
            JudgeFinalDispatchFailureStats {
                total_failed_jobs: 0,
                unknown_failed_jobs: 0,
                by_type: Vec::new(),
            },
        );
        let total_failed_jobs = if total_failed_jobs_i64 <= 0 {
            0
        } else {
            u32::try_from(total_failed_jobs_i64).unwrap_or(u32::MAX)
        };
        let scanned_failed_jobs = sampled_stats.total_failed_jobs;

        Ok(GetJudgeFinalDispatchFailureStatsOutput {
            window_from: query.from,
            window_to: query.to,
            total_failed_jobs,
            scanned_failed_jobs,
            truncated: total_failed_jobs > scanned_failed_jobs,
            unknown_failed_jobs: sampled_stats.unknown_failed_jobs,
            by_type: sampled_stats.by_type,
        })
    }

    pub async fn list_judge_trace_replay_by_owner(
        &self,
        user: &User,
        query: ListJudgeTraceReplayOpsQuery,
    ) -> Result<ListJudgeTraceReplayOpsOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeReview)
            .await?;
        if let (Some(from), Some(to)) = (query.from, query.to) {
            if from > to {
                return Err(AppError::DebateError("from must be <= to".to_string()));
            }
        }

        let scope_filter = normalize_optional_trace_scope_filter(query.scope)?;
        let status_filter = normalize_optional_trace_status_filter(query.status)?;
        let row_limit = normalize_ops_trace_replay_limit(query.limit);
        let session_id_filter = query.session_id.map(|v| v as i64);

        let rows: Vec<JudgeTraceReplayOpsRow> = sqlx::query_as(
            r#"
            SELECT
                item.scope,
                item.session_id,
                item.trace_id,
                item.idempotency_key,
                item.status,
                item.created_at,
                item.dispatch_attempts,
                item.last_dispatch_at,
                item.error_message,
                item.error_code,
                item.contract_failure_type,
                item.phase_job_id,
                item.final_job_id,
                item.phase_no,
                item.phase_start_no,
                item.phase_end_no,
                item.phase_report_id,
                item.final_report_id,
                item.replay_action_count,
                item.latest_replay_action_id,
                item.latest_replay_at
            FROM (
                SELECT
                    'phase'::varchar AS scope,
                    p.session_id,
                    p.trace_id,
                    p.idempotency_key,
                    p.status,
                    p.created_at,
                    p.dispatch_attempts,
                    p.last_dispatch_at,
                    p.error_message,
                    NULL::varchar AS error_code,
                    NULL::varchar AS contract_failure_type,
                    p.id AS phase_job_id,
                    NULL::bigint AS final_job_id,
                    p.phase_no,
                    NULL::int AS phase_start_no,
                    NULL::int AS phase_end_no,
                    r.id AS phase_report_id,
                    NULL::bigint AS final_report_id,
                    (
                        SELECT COUNT(*)::bigint
                        FROM judge_replay_actions a
                        WHERE a.scope = 'phase' AND a.job_id = p.id
                    ) AS replay_action_count,
                    (
                        SELECT a.id
                        FROM judge_replay_actions a
                        WHERE a.scope = 'phase' AND a.job_id = p.id
                        ORDER BY a.created_at DESC, a.id DESC
                        LIMIT 1
                    ) AS latest_replay_action_id,
                    (
                        SELECT a.created_at
                        FROM judge_replay_actions a
                        WHERE a.scope = 'phase' AND a.job_id = p.id
                        ORDER BY a.created_at DESC, a.id DESC
                        LIMIT 1
                    ) AS latest_replay_at
                FROM judge_phase_jobs p
                LEFT JOIN judge_phase_reports r ON r.phase_job_id = p.id
                WHERE ($1::timestamptz IS NULL OR p.created_at >= $1)
                  AND ($2::timestamptz IS NULL OR p.created_at <= $2)
                  AND ($3::bigint IS NULL OR p.session_id = $3)

                UNION ALL

                SELECT
                    'final'::varchar AS scope,
                    f.session_id,
                    f.trace_id,
                    f.idempotency_key,
                    f.status,
                    f.created_at,
                    f.dispatch_attempts,
                    f.last_dispatch_at,
                    f.error_message,
                    f.error_code,
                    f.contract_failure_type,
                    NULL::bigint AS phase_job_id,
                    f.id AS final_job_id,
                    NULL::int AS phase_no,
                    f.phase_start_no,
                    f.phase_end_no,
                    NULL::bigint AS phase_report_id,
                    r.id AS final_report_id,
                    (
                        SELECT COUNT(*)::bigint
                        FROM judge_replay_actions a
                        WHERE a.scope = 'final' AND a.job_id = f.id
                    ) AS replay_action_count,
                    (
                        SELECT a.id
                        FROM judge_replay_actions a
                        WHERE a.scope = 'final' AND a.job_id = f.id
                        ORDER BY a.created_at DESC, a.id DESC
                        LIMIT 1
                    ) AS latest_replay_action_id,
                    (
                        SELECT a.created_at
                        FROM judge_replay_actions a
                        WHERE a.scope = 'final' AND a.job_id = f.id
                        ORDER BY a.created_at DESC, a.id DESC
                        LIMIT 1
                    ) AS latest_replay_at
                FROM judge_final_jobs f
                LEFT JOIN judge_final_reports r ON r.final_job_id = f.id
                WHERE ($1::timestamptz IS NULL OR f.created_at >= $1)
                  AND ($2::timestamptz IS NULL OR f.created_at <= $2)
                  AND ($3::bigint IS NULL OR f.session_id = $3)
            ) AS item
            WHERE ($4::varchar IS NULL OR item.scope = $4)
              AND ($5::varchar IS NULL OR item.status = $5)
            ORDER BY
                item.created_at DESC,
                COALESCE(item.phase_job_id, item.final_job_id) DESC,
                item.scope DESC
            LIMIT $6
            "#,
        )
        .bind(query.from)
        .bind(query.to)
        .bind(session_id_filter)
        .bind(scope_filter)
        .bind(status_filter)
        .bind(row_limit)
        .fetch_all(&self.pool)
        .await?;

        let scanned_count = u32::try_from(rows.len()).unwrap_or(u32::MAX);
        let items: Vec<JudgeTraceReplayOpsItem> = rows
            .into_iter()
            .map(map_judge_trace_replay_ops_item)
            .collect();

        let mut phase_count = 0_u32;
        let mut final_count = 0_u32;
        let mut failed_count = 0_u32;
        let mut replay_eligible_count = 0_u32;
        for item in &items {
            if item.scope == "phase" {
                phase_count = phase_count.saturating_add(1);
            } else if item.scope == "final" {
                final_count = final_count.saturating_add(1);
            }
            if item.status == "failed" {
                failed_count = failed_count.saturating_add(1);
            }
            if item.replay_eligible {
                replay_eligible_count = replay_eligible_count.saturating_add(1);
            }
        }

        Ok(ListJudgeTraceReplayOpsOutput {
            window_from: query.from,
            window_to: query.to,
            scanned_count,
            returned_count: u32::try_from(items.len()).unwrap_or(u32::MAX),
            phase_count,
            final_count,
            failed_count,
            replay_eligible_count,
            items,
        })
    }

    pub async fn get_judge_replay_preview_by_owner(
        &self,
        user: &User,
        query: GetJudgeReplayPreviewOpsQuery,
    ) -> Result<GetJudgeReplayPreviewOpsOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeReview)
            .await?;
        let scope = normalize_replay_scope(query.scope.as_str())?;
        let case_id_i64 =
            checked_u64_to_i64(query.case_id, OPS_JUDGE_REPLAY_PREVIEW_CASE_ID_OUT_OF_RANGE)?;
        if scope == "phase" {
            let job: JudgePhaseReplayJobRow = sqlx::query_as(
                r#"
                SELECT
                    id,
                    session_id,
                    rejudge_run_no,
                    phase_no,
                    message_start_id,
                    message_end_id,
                    message_count,
                    status,
                    trace_id,
                    idempotency_key,
                    rubric_version,
                    judge_policy_version,
                    topic_domain,
                    retrieval_profile,
                    dispatch_attempts,
                    last_dispatch_at,
                    error_message,
                    created_at
                FROM judge_phase_jobs
                WHERE id = $1
                LIMIT 1
                "#,
            )
            .bind(case_id_i64)
            .fetch_optional(&self.pool)
            .await?
            .ok_or_else(|| AppError::NotFound(format!("judge phase case id {}", query.case_id)))?;

            let messages: Vec<(i64, i64, String, String, DateTime<Utc>)> = sqlx::query_as(
                r#"
                SELECT id, user_id, side, content, created_at
                FROM session_messages
                WHERE session_id = $1
                  AND id >= $2
                  AND id <= $3
                ORDER BY id ASC
                "#,
            )
            .bind(job.session_id)
            .bind(job.message_start_id)
            .bind(job.message_end_id)
            .fetch_all(&self.pool)
            .await?;
            if messages.len() != job.message_count as usize {
                return Err(AppError::DebateError(format!(
                    "phase replay preview message_count mismatch, expected={}, got={}",
                    job.message_count,
                    messages.len()
                )));
            }

            let mut speaker_aliases: HashMap<i64, String> = HashMap::new();
            let mut speaker_seq: u32 = 1;
            let mut message_items = Vec::with_capacity(messages.len());
            for (message_id, user_id, side, content, created_at) in messages {
                let speaker_tag = speaker_aliases
                    .entry(user_id)
                    .or_insert_with(|| {
                        let alias = format!("speaker-{speaker_seq}");
                        speaker_seq = speaker_seq.saturating_add(1);
                        alias
                    })
                    .clone();
                message_items.push(serde_json::json!({
                    "message_id": message_id as u64,
                    "speaker_tag": speaker_tag,
                    "side": side,
                    "content": content,
                    "created_at": created_at,
                }));
            }

            let request_snapshot = serde_json::json!({
                "case_id": job.id as u64,
                "scope_id": 1_u64,
                "session_id": job.session_id as u64,
                "phase_no": job.phase_no,
                "message_start_id": job.message_start_id as u64,
                "message_end_id": job.message_end_id as u64,
                "message_count": job.message_count,
                "messages": message_items,
                "rubric_version": job.rubric_version,
                "judge_policy_version": job.judge_policy_version,
                "topic_domain": job.topic_domain,
                "retrieval_profile": job.retrieval_profile,
                "trace_id": job.trace_id,
                "idempotency_key": job.idempotency_key,
            });
            let status = job.status.to_ascii_lowercase();
            let replay_eligible = is_replay_eligible_status(status.as_str());
            let snapshot_hash = compute_snapshot_hash(&request_snapshot)?;

            return Ok(GetJudgeReplayPreviewOpsOutput {
                side_effect_free: true,
                snapshot_hash,
                meta: JudgeReplayPreviewMeta {
                    scope: "phase".to_string(),
                    case_id: job.id as u64,
                    session_id: job.session_id as u64,
                    status,
                    trace_id: job.trace_id,
                    idempotency_key: job.idempotency_key,
                    rubric_version: job.rubric_version,
                    judge_policy_version: job.judge_policy_version,
                    topic_domain: job.topic_domain,
                    retrieval_profile: Some(job.retrieval_profile),
                    phase_no: Some(job.phase_no),
                    phase_start_no: None,
                    phase_end_no: None,
                    message_start_id: Some(job.message_start_id as u64),
                    message_end_id: Some(job.message_end_id as u64),
                    message_count: Some(job.message_count),
                    created_at: job.created_at,
                    dispatch_attempts: job.dispatch_attempts,
                    last_dispatch_at: job.last_dispatch_at,
                    error_message: job.error_message,
                    replay_eligible,
                    replay_block_reason: if replay_eligible {
                        None
                    } else {
                        Some("job_status_not_terminal".to_string())
                    },
                },
                request_snapshot,
            });
        }

        let job: JudgeFinalReplayJobRow = sqlx::query_as(
            r#"
            SELECT
                id,
                session_id,
                rejudge_run_no,
                phase_start_no,
                phase_end_no,
                status,
                trace_id,
                idempotency_key,
                rubric_version,
                judge_policy_version,
                topic_domain,
                dispatch_attempts,
                last_dispatch_at,
                error_message,
                created_at
            FROM judge_final_jobs
            WHERE id = $1
            LIMIT 1
            "#,
        )
        .bind(case_id_i64)
        .fetch_optional(&self.pool)
        .await?
        .ok_or_else(|| AppError::NotFound(format!("judge final case id {}", query.case_id)))?;
        if job.phase_end_no < job.phase_start_no {
            return Err(AppError::DebateError(format!(
                "final replay preview phase range invalid, start={}, end={}",
                job.phase_start_no, job.phase_end_no
            )));
        }

        let request_snapshot = serde_json::json!({
            "case_id": job.id as u64,
            "scope_id": 1_u64,
            "session_id": job.session_id as u64,
            "phase_start_no": job.phase_start_no,
            "phase_end_no": job.phase_end_no,
            "rubric_version": job.rubric_version,
            "judge_policy_version": job.judge_policy_version,
            "topic_domain": job.topic_domain,
            "trace_id": job.trace_id,
            "idempotency_key": job.idempotency_key,
        });
        let status = job.status.to_ascii_lowercase();
        let replay_eligible = is_replay_eligible_status(status.as_str());
        let snapshot_hash = compute_snapshot_hash(&request_snapshot)?;

        Ok(GetJudgeReplayPreviewOpsOutput {
            side_effect_free: true,
            snapshot_hash,
            meta: JudgeReplayPreviewMeta {
                scope: "final".to_string(),
                case_id: job.id as u64,
                session_id: job.session_id as u64,
                status,
                trace_id: job.trace_id,
                idempotency_key: job.idempotency_key,
                rubric_version: job.rubric_version,
                judge_policy_version: job.judge_policy_version,
                topic_domain: job.topic_domain,
                retrieval_profile: None,
                phase_no: None,
                phase_start_no: Some(job.phase_start_no),
                phase_end_no: Some(job.phase_end_no),
                message_start_id: None,
                message_end_id: None,
                message_count: None,
                created_at: job.created_at,
                dispatch_attempts: job.dispatch_attempts,
                last_dispatch_at: job.last_dispatch_at,
                error_message: job.error_message,
                replay_eligible,
                replay_block_reason: if replay_eligible {
                    None
                } else {
                    Some("job_status_not_terminal".to_string())
                },
            },
            request_snapshot,
        })
    }

    pub async fn execute_judge_replay_by_owner(
        &self,
        user: &User,
        input: ExecuteJudgeReplayOpsInput,
    ) -> Result<ExecuteJudgeReplayOpsOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeRejudge)
            .await?;
        let scope = normalize_replay_scope(input.scope.as_str())?;
        let reason = normalize_optional_replay_reason(input.reason)?;
        let case_id = input.case_id;
        let case_id_i64 =
            checked_u64_to_i64(case_id, OPS_JUDGE_REPLAY_EXECUTE_CASE_ID_OUT_OF_RANGE)?;
        let new_status = "queued".to_string();

        if scope == "phase" {
            let mut tx = self.pool.begin().await?;
            let job: JudgePhaseReplayJobRow = sqlx::query_as(
                r#"
                SELECT
                    id,
                    session_id,
                    rejudge_run_no,
                    phase_no,
                    message_start_id,
                    message_end_id,
                    message_count,
                    status,
                    trace_id,
                    idempotency_key,
                    rubric_version,
                    judge_policy_version,
                    topic_domain,
                    retrieval_profile,
                    dispatch_attempts,
                    last_dispatch_at,
                    error_message,
                    created_at
                FROM judge_phase_jobs
                WHERE id = $1
                FOR UPDATE
                "#,
            )
            .bind(case_id_i64)
            .fetch_optional(&mut *tx)
            .await?
            .ok_or_else(|| AppError::NotFound(format!("judge phase case id {}", case_id)))?;

            let previous_status = job.status.to_ascii_lowercase();
            if previous_status != "failed" {
                return Err(AppError::DebateConflict(format!(
                    "replay execute requires failed phase job, current status={}",
                    previous_status
                )));
            }
            let existing_report_id: Option<i64> = sqlx::query_scalar(
                r#"
                SELECT id
                FROM judge_phase_reports
                WHERE phase_job_id = $1
                LIMIT 1
                "#,
            )
            .bind(job.id)
            .fetch_optional(&mut *tx)
            .await?;
            if existing_report_id.is_some() {
                return Err(AppError::DebateConflict(format!(
                    "phase job {} already has report, replay execute is not allowed",
                    job.id
                )));
            }

            let new_trace_id = build_replay_trace_id("phase", case_id);
            let new_idempotency_key = build_replay_idempotency_key("phase", case_id);
            sqlx::query(
                r#"
                UPDATE judge_phase_jobs
                SET
                    status = 'queued',
                    trace_id = $2,
                    idempotency_key = $3,
                    dispatch_attempts = 0,
                    last_dispatch_at = NULL,
                    dispatch_locked_until = NULL,
                    error_message = NULL,
                    updated_at = NOW()
                WHERE id = $1
                "#,
            )
            .bind(job.id)
            .bind(&new_trace_id)
            .bind(&new_idempotency_key)
            .execute(&mut *tx)
            .await?;

            let audit: JudgeReplayActionRow = sqlx::query_as(
                r#"
                INSERT INTO judge_replay_actions(
                    scope,
                    job_id,
                    session_id,
                    rejudge_run_no,
                    requested_by,
                    reason,
                    previous_status,
                    new_status,
                    previous_trace_id,
                    new_trace_id,
                    previous_idempotency_key,
                    new_idempotency_key,
                    created_at
                )
                VALUES (
                    'phase',
                    $1,
                    $2,
                    $3,
                    $4,
                    $5,
                    $6,
                    'queued',
                    $7,
                    $8,
                    $9,
                    $10,
                    NOW()
                )
                RETURNING id, created_at
                "#,
            )
            .bind(job.id)
            .bind(job.session_id)
            .bind(job.rejudge_run_no)
            .bind(user.id)
            .bind(reason)
            .bind(&previous_status)
            .bind(&job.trace_id)
            .bind(&new_trace_id)
            .bind(&job.idempotency_key)
            .bind(&new_idempotency_key)
            .fetch_one(&mut *tx)
            .await?;
            tx.commit().await?;

            return Ok(ExecuteJudgeReplayOpsOutput {
                audit_id: audit.id as u64,
                scope: "phase".to_string(),
                case_id: job.id as u64,
                session_id: job.session_id as u64,
                previous_status,
                new_status,
                previous_trace_id: job.trace_id,
                new_trace_id,
                previous_idempotency_key: job.idempotency_key,
                new_idempotency_key,
                replay_triggered_at: audit.created_at,
            });
        }

        let mut tx = self.pool.begin().await?;
        let job: JudgeFinalReplayJobRow = sqlx::query_as(
            r#"
            SELECT
                id,
                session_id,
                rejudge_run_no,
                phase_start_no,
                phase_end_no,
                status,
                trace_id,
                idempotency_key,
                rubric_version,
                judge_policy_version,
                topic_domain,
                dispatch_attempts,
                last_dispatch_at,
                error_message,
                created_at
            FROM judge_final_jobs
            WHERE id = $1
            FOR UPDATE
            "#,
        )
        .bind(case_id_i64)
        .fetch_optional(&mut *tx)
        .await?
        .ok_or_else(|| AppError::NotFound(format!("judge final case id {}", case_id)))?;

        let previous_status = job.status.to_ascii_lowercase();
        if previous_status != "failed" {
            return Err(AppError::DebateConflict(format!(
                "replay execute requires failed final job, current status={}",
                previous_status
            )));
        }
        let existing_report_id: Option<i64> = sqlx::query_scalar(
            r#"
            SELECT id
            FROM judge_final_reports
            WHERE final_job_id = $1
            LIMIT 1
            "#,
        )
        .bind(job.id)
        .fetch_optional(&mut *tx)
        .await?;
        if existing_report_id.is_some() {
            return Err(AppError::DebateConflict(format!(
                "final job {} already has report, replay execute is not allowed",
                job.id
            )));
        }

        let new_trace_id = build_replay_trace_id("final", case_id);
        let new_idempotency_key = build_replay_idempotency_key("final", case_id);
        sqlx::query(
            r#"
            UPDATE judge_final_jobs
            SET
                status = 'queued',
                trace_id = $2,
                idempotency_key = $3,
                dispatch_attempts = 0,
                last_dispatch_at = NULL,
                dispatch_locked_until = NULL,
                error_message = NULL,
                error_code = NULL,
                contract_failure_type = NULL,
                updated_at = NOW()
            WHERE id = $1
            "#,
        )
        .bind(job.id)
        .bind(&new_trace_id)
        .bind(&new_idempotency_key)
        .execute(&mut *tx)
        .await?;

        let audit: JudgeReplayActionRow = sqlx::query_as(
            r#"
            INSERT INTO judge_replay_actions(
                scope,
                job_id,
                session_id,
                rejudge_run_no,
                requested_by,
                reason,
                previous_status,
                new_status,
                previous_trace_id,
                new_trace_id,
                previous_idempotency_key,
                new_idempotency_key,
                created_at
            )
            VALUES (
                'final',
                $1,
                $2,
                $3,
                $4,
                $5,
                $6,
                'queued',
                $7,
                $8,
                $9,
                $10,
                NOW()
            )
            RETURNING id, created_at
            "#,
        )
        .bind(job.id)
        .bind(job.session_id)
        .bind(job.rejudge_run_no)
        .bind(user.id)
        .bind(reason)
        .bind(&previous_status)
        .bind(&job.trace_id)
        .bind(&new_trace_id)
        .bind(&job.idempotency_key)
        .bind(&new_idempotency_key)
        .fetch_one(&mut *tx)
        .await?;
        tx.commit().await?;

        Ok(ExecuteJudgeReplayOpsOutput {
            audit_id: audit.id as u64,
            scope: "final".to_string(),
            case_id: job.id as u64,
            session_id: job.session_id as u64,
            previous_status,
            new_status,
            previous_trace_id: job.trace_id,
            new_trace_id,
            previous_idempotency_key: job.idempotency_key,
            new_idempotency_key,
            replay_triggered_at: audit.created_at,
        })
    }

    pub async fn list_judge_replay_actions_by_owner(
        &self,
        user: &User,
        query: ListJudgeReplayActionsOpsQuery,
    ) -> Result<ListJudgeReplayActionsOpsOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeReview)
            .await?;
        if let (Some(from), Some(to)) = (query.from, query.to) {
            if from > to {
                return Err(AppError::DebateError("from must be <= to".to_string()));
            }
        }

        let scope_filter = normalize_optional_trace_scope_filter(query.scope)?;
        let session_id_filter = query
            .session_id
            .map(|value| {
                checked_u64_to_i64(value, OPS_JUDGE_REPLAY_ACTIONS_SESSION_ID_OUT_OF_RANGE)
            })
            .transpose()?;
        let case_id_filter = query
            .case_id
            .map(|value| checked_u64_to_i64(value, OPS_JUDGE_REPLAY_ACTIONS_CASE_ID_OUT_OF_RANGE))
            .transpose()?;
        let requested_by_filter = query
            .requested_by
            .map(|value| {
                checked_u64_to_i64(value, OPS_JUDGE_REPLAY_ACTIONS_REQUESTED_BY_OUT_OF_RANGE)
            })
            .transpose()?;
        let previous_status_filter = normalize_optional_replay_actions_status_filter(
            "previousStatus",
            query.previous_status,
        )?;
        let new_status_filter =
            normalize_optional_replay_actions_status_filter("newStatus", query.new_status)?;
        let reason_keyword_filter =
            normalize_optional_replay_actions_keyword("reasonKeyword", query.reason_keyword)?;
        let trace_keyword_filter =
            normalize_optional_replay_actions_keyword("traceKeyword", query.trace_keyword)?;
        let reason_keyword_pattern = reason_keyword_filter
            .as_ref()
            .map(|keyword| format!("%{keyword}%"));
        let trace_keyword_pattern = trace_keyword_filter
            .as_ref()
            .map(|keyword| format!("%{keyword}%"));
        let row_limit = normalize_ops_replay_actions_limit(query.limit);
        let row_offset = normalize_ops_replay_actions_offset(query.offset);

        let total_count_i64: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(*)::bigint
            FROM judge_replay_actions
            WHERE ($1::timestamptz IS NULL OR created_at >= $1)
              AND ($2::timestamptz IS NULL OR created_at <= $2)
              AND ($3::varchar IS NULL OR scope = $3)
              AND ($4::bigint IS NULL OR session_id = $4)
              AND ($5::bigint IS NULL OR job_id = $5)
              AND ($6::bigint IS NULL OR requested_by = $6)
              AND ($7::varchar IS NULL OR previous_status = $7)
              AND ($8::varchar IS NULL OR new_status = $8)
              AND ($9::varchar IS NULL OR reason ILIKE $9)
              AND (
                    $10::varchar IS NULL
                    OR previous_trace_id ILIKE $10
                    OR new_trace_id ILIKE $10
                  )
            "#,
        )
        .bind(query.from)
        .bind(query.to)
        .bind(scope_filter.as_deref())
        .bind(session_id_filter)
        .bind(case_id_filter)
        .bind(requested_by_filter)
        .bind(previous_status_filter.as_deref())
        .bind(new_status_filter.as_deref())
        .bind(reason_keyword_pattern.as_deref())
        .bind(trace_keyword_pattern.as_deref())
        .fetch_one(&self.pool)
        .await?;

        let rows: Vec<JudgeReplayActionOpsRow> = sqlx::query_as(
            r#"
            SELECT
                id AS audit_id,
                scope,
                job_id,
                session_id,
                requested_by,
                reason,
                previous_status,
                new_status,
                previous_trace_id,
                new_trace_id,
                previous_idempotency_key,
                new_idempotency_key,
                created_at
            FROM judge_replay_actions
            WHERE ($1::timestamptz IS NULL OR created_at >= $1)
              AND ($2::timestamptz IS NULL OR created_at <= $2)
              AND ($3::varchar IS NULL OR scope = $3)
              AND ($4::bigint IS NULL OR session_id = $4)
              AND ($5::bigint IS NULL OR job_id = $5)
              AND ($6::bigint IS NULL OR requested_by = $6)
              AND ($7::varchar IS NULL OR previous_status = $7)
              AND ($8::varchar IS NULL OR new_status = $8)
              AND ($9::varchar IS NULL OR reason ILIKE $9)
              AND (
                    $10::varchar IS NULL
                    OR previous_trace_id ILIKE $10
                    OR new_trace_id ILIKE $10
                  )
            ORDER BY created_at DESC, id DESC
            LIMIT $11 OFFSET $12
            "#,
        )
        .bind(query.from)
        .bind(query.to)
        .bind(scope_filter.as_deref())
        .bind(session_id_filter)
        .bind(case_id_filter)
        .bind(requested_by_filter)
        .bind(previous_status_filter.as_deref())
        .bind(new_status_filter.as_deref())
        .bind(reason_keyword_pattern.as_deref())
        .bind(trace_keyword_pattern.as_deref())
        .bind(row_limit)
        .bind(row_offset)
        .fetch_all(&self.pool)
        .await?;

        let items: Vec<JudgeReplayActionOpsItem> = rows
            .into_iter()
            .map(map_judge_replay_action_ops_item)
            .collect();
        let returned_count = u32::try_from(items.len()).unwrap_or(u32::MAX);
        let scanned_count = if total_count_i64 <= 0 {
            0
        } else {
            u32::try_from(total_count_i64).unwrap_or(u32::MAX)
        };
        let has_more = row_offset.saturating_add(i64::from(returned_count)) < total_count_i64;

        Ok(ListJudgeReplayActionsOpsOutput {
            window_from: query.from,
            window_to: query.to,
            scanned_count,
            returned_count,
            has_more,
            items,
        })
    }

    async fn ensure_judge_report_read_access(
        &self,
        tx: &mut Transaction<'_, Postgres>,
        session_id: i64,
        user: &User,
    ) -> Result<(), AppError> {
        let participant_exists: Option<i32> = sqlx::query_scalar(
            r#"
            SELECT 1
            FROM session_participants
            WHERE session_id = $1
              AND user_id = $2
            LIMIT 1
            "#,
        )
        .bind(session_id)
        .bind(user.id)
        .fetch_optional(&mut **tx)
        .await?;
        if participant_exists.is_some() {
            return Ok(());
        }

        let rbac = self.get_ops_rbac_me(user).await?;
        if rbac.is_owner || rbac.permissions.judge_review {
            return Ok(());
        }

        Err(AppError::DebateConflict(
            JUDGE_REPORT_READ_FORBIDDEN.to_string(),
        ))
    }

    pub async fn get_latest_judge_report(
        &self,
        session_id: u64,
        user: &User,
        requested_run_no: Option<u32>,
    ) -> Result<GetJudgeReportOutput, AppError> {
        let mut tx = self.pool.begin().await?;
        sqlx::query("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            .execute(&mut *tx)
            .await?;

        let session_id_i64 = session_id as i64;
        let session_exists = sqlx::query_scalar::<_, i32>(
            r#"
            SELECT 1
            FROM debate_sessions
            WHERE id = $1
            LIMIT 1
            "#,
        )
        .bind(session_id_i64)
        .fetch_optional(&mut *tx)
        .await?;
        if session_exists.is_none() {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        }
        self.ensure_judge_report_read_access(&mut tx, session_id_i64, user)
            .await?;

        let latest_run_no =
            resolve_target_rejudge_run_no(&mut tx, session_id_i64, requested_run_no).await?;

        let latest_phase_job: Option<JudgePhaseJobSnapshotRow> = sqlx::query_as(
            r#"
            SELECT
                id,
                phase_no,
                status,
                message_count,
                dispatch_attempts,
                last_dispatch_at,
                error_message
            FROM judge_phase_jobs
            WHERE session_id = $1
              AND rejudge_run_no = $2
            ORDER BY created_at DESC
            LIMIT 1
            "#,
        )
        .bind(session_id_i64)
        .bind(latest_run_no)
        .fetch_optional(&mut *tx)
        .await?;

        let latest_final_job: Option<JudgeFinalJobSnapshotRow> = sqlx::query_as(
            r#"
            SELECT
                id,
                status,
                phase_start_no,
                phase_end_no,
                dispatch_attempts,
                last_dispatch_at,
                error_message,
                error_code,
                contract_failure_type
            FROM judge_final_jobs
            WHERE session_id = $1
              AND rejudge_run_no = $2
            ORDER BY created_at DESC
            LIMIT 1
            "#,
        )
        .bind(session_id_i64)
        .bind(latest_run_no)
        .fetch_optional(&mut *tx)
        .await?;

        let phase_progress_row: JudgePhaseProgressCountsRow = sqlx::query_as(
            r#"
            SELECT
                COUNT(*)::bigint AS total_phase_jobs,
                COUNT(*) FILTER (WHERE status = 'queued')::bigint AS queued_phase_jobs,
                COUNT(*) FILTER (WHERE status = 'dispatched')::bigint AS dispatched_phase_jobs,
                COUNT(*) FILTER (WHERE status = 'succeeded')::bigint AS succeeded_phase_jobs,
                COUNT(*) FILTER (WHERE status = 'failed')::bigint AS failed_phase_jobs
            FROM judge_phase_jobs
            WHERE session_id = $1
              AND rejudge_run_no = $2
            "#,
        )
        .bind(session_id_i64)
        .bind(latest_run_no)
        .fetch_one(&mut *tx)
        .await?;

        let final_report_row: Option<JudgeFinalReportRow> = sqlx::query_as(
            r#"
            SELECT
                id,
                final_job_id,
                winner,
                pro_score,
                con_score,
                dimension_scores,
                debate_summary,
                side_analysis,
                verdict_reason,
                verdict_evidence_refs,
                phase_rollup_summary,
                retrieval_snapshot_rollup,
                winner_first,
                winner_second,
                winner_third,
                rejudge_triggered,
                needs_draw_vote,
                review_required,
                claim_graph,
                claim_graph_summary,
                evidence_ledger,
                verdict_ledger,
                opinion_pack,
                fairness_summary,
                trust_attestation,
                judge_trace,
                audit_alerts,
                error_codes,
                degradation_level,
                created_at
            FROM judge_final_reports
            WHERE session_id = $1
              AND rejudge_run_no = $2
            ORDER BY created_at DESC
            LIMIT 1
            "#,
        )
        .bind(session_id_i64)
        .bind(latest_run_no)
        .fetch_optional(&mut *tx)
        .await?;

        tx.commit().await?;

        let final_report = final_report_row.map(map_final_report_detail);
        let progress = JudgeReportProgress {
            total_phase_jobs: to_u32_count(phase_progress_row.total_phase_jobs),
            queued_phase_jobs: to_u32_count(phase_progress_row.queued_phase_jobs),
            dispatched_phase_jobs: to_u32_count(phase_progress_row.dispatched_phase_jobs),
            succeeded_phase_jobs: to_u32_count(phase_progress_row.succeeded_phase_jobs),
            failed_phase_jobs: to_u32_count(phase_progress_row.failed_phase_jobs),
            has_final_job: latest_final_job.is_some(),
            has_final_report: final_report.is_some(),
        };

        let final_dispatch_diagnostics = latest_final_job
            .as_ref()
            .map(|job| map_final_dispatch_diagnostics(job.clone()));
        let final_dispatch_failure_stats = final_dispatch_diagnostics
            .as_ref()
            .filter(|item| item.status == "failed")
            .map(|item| JudgeFinalDispatchFailureStats {
                total_failed_jobs: 1,
                unknown_failed_jobs: u32::from(
                    item.contract_failure_type.as_deref() == Some(CONTRACT_FAILURE_UNKNOWN),
                ),
                by_type: vec![JudgeFinalDispatchFailureTypeCount {
                    failure_type: item
                        .contract_failure_type
                        .clone()
                        .unwrap_or_else(|| CONTRACT_FAILURE_UNKNOWN.to_string()),
                    count: 1,
                }],
            });
        let (status, status_reason) = resolve_judge_report_status(
            latest_final_job.as_ref(),
            &progress,
            final_report.as_ref(),
        );

        Ok(GetJudgeReportOutput {
            session_id,
            status,
            status_reason,
            latest_phase_job: latest_phase_job.map(|job| JudgePhaseJobSnapshot {
                phase_job_id: job.id as u64,
                phase_no: job.phase_no,
                status: job.status,
                message_count: job.message_count,
                dispatch_attempts: job.dispatch_attempts,
                last_dispatch_at: job.last_dispatch_at,
                error_message: job.error_message,
            }),
            latest_final_job: latest_final_job.map(|job| JudgeFinalJobSnapshot {
                final_job_id: job.id as u64,
                status: job.status,
                phase_start_no: job.phase_start_no,
                phase_end_no: job.phase_end_no,
                dispatch_attempts: job.dispatch_attempts,
                last_dispatch_at: job.last_dispatch_at,
                error_message: job.error_message,
                error_code: job.error_code,
                contract_failure_type: job.contract_failure_type,
            }),
            final_dispatch_diagnostics,
            final_dispatch_failure_stats,
            progress,
            final_report_summary: final_report.as_ref().map(map_final_report_summary),
        })
    }

    pub async fn get_judge_public_verify(
        &self,
        session_id: u64,
        user: &User,
        query: GetJudgePublicVerifyQuery,
    ) -> Result<GetJudgePublicVerifyOutput, AppError> {
        let dispatch_type = normalize_public_verify_dispatch_type(query.dispatch_type)?;
        let report = self
            .get_latest_judge_report(session_id, user, query.rejudge_run_no)
            .await?;
        let case_id = if dispatch_type == "phase" {
            report.latest_phase_job.map(|job| job.phase_job_id)
        } else {
            report.latest_final_job.map(|job| job.final_job_id)
        };
        let Some(case_id) = case_id else {
            return Ok(build_public_verify_absent_output(session_id, dispatch_type));
        };

        let payload = match fetch_ai_judge_public_verify_payload(
            &self.config.ai_judge.service_base_url,
            &self.config.ai_judge.public_verify_path,
            self.config.ai_judge.public_verify_timeout_ms,
            &self.config.ai_judge.internal_key,
            case_id,
            &dispatch_type,
        )
        .await
        {
            Ok(payload) => payload,
            Err(reason_code) => {
                tracing::warn!(
                    session_id,
                    case_id,
                    dispatch_type,
                    reason_code,
                    "AI judge public verification proxy request failed"
                );
                return Ok(build_public_verify_proxy_error_output(
                    session_id,
                    case_id,
                    dispatch_type,
                    JUDGE_PUBLIC_VERIFY_REASON_PROXY_FAILED,
                ));
            }
        };

        if let Err(reason_code) = validate_public_verify_payload(&payload, case_id, &dispatch_type)
        {
            // 代理层二次校验公开合同，避免 AI 内部字段被穿透到客户端。
            tracing::warn!(
                session_id,
                case_id,
                dispatch_type,
                reason_code,
                "AI judge public verification contract violation blocked"
            );
            return Ok(build_public_verify_proxy_error_output(
                session_id,
                case_id,
                dispatch_type,
                reason_code,
            ));
        }

        let (status, status_reason) = resolve_public_verify_status(&payload);
        let verification_readiness = payload
            .get("verificationReadiness")
            .cloned()
            .unwrap_or_else(|| default_public_verify_readiness(false, &status, None));
        let cache_profile = payload
            .get("cacheProfile")
            .cloned()
            .unwrap_or_else(|| default_public_verify_cache_profile(session_id, &dispatch_type));

        Ok(GetJudgePublicVerifyOutput {
            session_id,
            status,
            status_reason,
            case_id: Some(case_id),
            dispatch_type,
            verification_readiness,
            cache_profile,
            public_verify: payload,
        })
    }

    pub async fn get_latest_judge_final_report(
        &self,
        session_id: u64,
        user: &User,
        requested_run_no: Option<u32>,
    ) -> Result<GetJudgeReportFinalOutput, AppError> {
        let mut tx = self.pool.begin().await?;
        sqlx::query("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            .execute(&mut *tx)
            .await?;

        let session_id_i64 = session_id as i64;
        let session_exists = sqlx::query_scalar::<_, i32>(
            r#"
            SELECT 1
            FROM debate_sessions
            WHERE id = $1
            LIMIT 1
            "#,
        )
        .bind(session_id_i64)
        .fetch_optional(&mut *tx)
        .await?;
        if session_exists.is_none() {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        }
        self.ensure_judge_report_read_access(&mut tx, session_id_i64, user)
            .await?;

        let latest_run_no =
            resolve_target_rejudge_run_no(&mut tx, session_id_i64, requested_run_no).await?;

        let final_report_row: Option<JudgeFinalReportRow> = sqlx::query_as(
            r#"
            SELECT
                id,
                final_job_id,
                winner,
                pro_score,
                con_score,
                dimension_scores,
                debate_summary,
                side_analysis,
                verdict_reason,
                verdict_evidence_refs,
                phase_rollup_summary,
                retrieval_snapshot_rollup,
                winner_first,
                winner_second,
                winner_third,
                rejudge_triggered,
                needs_draw_vote,
                review_required,
                claim_graph,
                claim_graph_summary,
                evidence_ledger,
                verdict_ledger,
                opinion_pack,
                fairness_summary,
                trust_attestation,
                judge_trace,
                audit_alerts,
                error_codes,
                degradation_level,
                created_at
            FROM judge_final_reports
            WHERE session_id = $1
              AND rejudge_run_no = $2
            ORDER BY created_at DESC
            LIMIT 1
            "#,
        )
        .bind(session_id_i64)
        .bind(latest_run_no)
        .fetch_optional(&mut *tx)
        .await?;
        tx.commit().await?;

        Ok(GetJudgeReportFinalOutput {
            session_id,
            final_report: final_report_row.map(map_final_report_detail),
        })
    }
}
