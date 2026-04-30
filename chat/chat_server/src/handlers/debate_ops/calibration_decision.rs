use crate::{
    application::request_guard::{
        build_rate_limit_headers, enforce_rate_limit_with_disabled_fallback,
        rate_limit_exceeded_response, release_idempotency_best_effort,
        request_idempotency_key_from_headers, request_rate_limit_ip_key_with_user_fallback,
        try_acquire_idempotency_or_fail_open,
    },
    AppError, AppState, CreateJudgeCalibrationDecisionOpsInput,
};
use axum::{
    extract::State,
    http::{HeaderMap, StatusCode},
    response::{IntoResponse, Response},
    Extension, Json,
};
use chat_core::User;
use std::time::Instant;

#[cfg(test)]
use super::maybe_override_rate_limit_decision;
use super::request_id_from_headers;

const OPS_JUDGE_CALIBRATION_DECISION_USER_RATE_LIMIT_PER_WINDOW: u64 = 20;
const OPS_JUDGE_CALIBRATION_DECISION_IP_RATE_LIMIT_PER_WINDOW: u64 = 60;
const OPS_JUDGE_CALIBRATION_DECISION_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const OPS_JUDGE_CALIBRATION_DECISION_IDEMPOTENCY_TTL_SECS: u64 = 30;
const OPS_JUDGE_CALIBRATION_DECISION_IDEMPOTENCY_MAX_LEN: usize = 160;
const OPS_JUDGE_CALIBRATION_DECISION_IDEMPOTENCY_SCOPE: &str = "ops_judge_calibration_decision";

/// Record an Ops-only fairness calibration decision through the AI Judge decision log.
#[utoipa::path(
    post,
    path = "/api/debate/ops/judge-calibration-decisions",
    request_body = CreateJudgeCalibrationDecisionOpsInput,
    responses(
        (status = 200, description = "Ops judge calibration decision logged", body = crate::CreateJudgeCalibrationDecisionOpsOutput),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 401, description = "Auth error", body = crate::ErrorOutput),
        (status = 403, description = "Phone not bound", body = crate::ErrorOutput),
        (status = 409, description = "Permission or idempotency conflict", body = crate::ErrorOutput),
        (status = 429, description = "Rate limit exceeded", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn create_judge_calibration_decision_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(input): Json<CreateJudgeCalibrationDecisionOpsInput>,
) -> Result<Response, AppError> {
    let started_at = Instant::now();
    let request_id = request_id_from_headers(&headers);
    let source_recommendation_id = input.source_recommendation_id.clone();
    let decision = input.decision.clone();

    let user_decision = enforce_rate_limit_with_disabled_fallback(
        &state,
        "ops_judge_calibration_decision_user",
        &user.id.to_string(),
        OPS_JUDGE_CALIBRATION_DECISION_USER_RATE_LIMIT_PER_WINDOW,
        OPS_JUDGE_CALIBRATION_DECISION_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let user_decision = maybe_override_rate_limit_decision(
        &headers,
        "ops_judge_calibration_decision_user",
        user_decision,
    );
    if !user_decision.allowed {
        tracing::warn!(
            user_id = user.id,
            request_id = request_id.as_deref().unwrap_or_default(),
            source_recommendation_id = source_recommendation_id.as_str(),
            decision = "rate_limited_user",
            "create ops judge calibration decision blocked by user rate limiter"
        );
        return Ok(rate_limit_exceeded_response(
            "ops_judge_calibration_decision",
            build_rate_limit_headers(&user_decision)?,
        ));
    }

    let ip_limit_key = request_rate_limit_ip_key_with_user_fallback(
        &headers,
        user.id,
        &state.config.server.forwarded_header_trust,
    );
    let ip_decision = enforce_rate_limit_with_disabled_fallback(
        &state,
        "ops_judge_calibration_decision_ip",
        &ip_limit_key,
        OPS_JUDGE_CALIBRATION_DECISION_IP_RATE_LIMIT_PER_WINDOW,
        OPS_JUDGE_CALIBRATION_DECISION_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    #[cfg(test)]
    let ip_decision = maybe_override_rate_limit_decision(
        &headers,
        "ops_judge_calibration_decision_ip",
        ip_decision,
    );
    if !ip_decision.allowed {
        tracing::warn!(
            user_id = user.id,
            request_id = request_id.as_deref().unwrap_or_default(),
            source_recommendation_id = source_recommendation_id.as_str(),
            decision = "rate_limited_ip",
            "create ops judge calibration decision blocked by ip rate limiter"
        );
        return Ok(rate_limit_exceeded_response(
            "ops_judge_calibration_decision",
            build_rate_limit_headers(&ip_decision)?,
        ));
    }

    let request_idempotency_key = request_idempotency_key_from_headers(
        &headers,
        "ops_judge_calibration_decision_idempotency_key_invalid",
        "ops_judge_calibration_decision_idempotency_key_too_long",
        OPS_JUDGE_CALIBRATION_DECISION_IDEMPOTENCY_MAX_LEN,
    )?;
    let idempotency_lock_key = request_idempotency_key
        .as_deref()
        .map(|key| format!("u{}:{source_recommendation_id}:{key}", user.id));
    if let Some(lock_key) = idempotency_lock_key.as_deref() {
        let acquired = try_acquire_idempotency_or_fail_open(
            &state,
            OPS_JUDGE_CALIBRATION_DECISION_IDEMPOTENCY_SCOPE,
            lock_key,
            OPS_JUDGE_CALIBRATION_DECISION_IDEMPOTENCY_TTL_SECS,
        )
        .await;
        if !acquired {
            return Err(AppError::DebateConflict(
                "idempotency_conflict:ops_judge_calibration_decision".to_string(),
            ));
        }
    }

    let ret = state
        .create_judge_calibration_decision_by_owner(
            &user,
            input,
            request_idempotency_key.as_deref(),
        )
        .await;
    if let Some(lock_key) = idempotency_lock_key.as_deref() {
        release_idempotency_best_effort(
            &state,
            OPS_JUDGE_CALIBRATION_DECISION_IDEMPOTENCY_SCOPE,
            lock_key,
        )
        .await;
    }

    let ret = match ret {
        Ok(value) => value,
        Err(err) => {
            let latency_ms = started_at.elapsed().as_millis() as u64;
            tracing::warn!(
                user_id = user.id,
                request_id = request_id.as_deref().unwrap_or_default(),
                source_recommendation_id = source_recommendation_id.as_str(),
                requested_decision = decision.as_str(),
                latency_ms,
                decision = "failed",
                "create ops judge calibration decision failed: {}",
                err
            );
            return Err(err);
        }
    };

    let latency_ms = started_at.elapsed().as_millis() as u64;
    tracing::info!(
        user_id = user.id,
        request_id = request_id.as_deref().unwrap_or_default(),
        source_recommendation_id = source_recommendation_id.as_str(),
        requested_decision = decision.as_str(),
        status = ret.status.as_str(),
        status_reason = ret.status_reason.as_str(),
        latency_ms,
        decision = "success",
        "create ops judge calibration decision served"
    );
    Ok((StatusCode::OK, Json(ret)).into_response())
}
