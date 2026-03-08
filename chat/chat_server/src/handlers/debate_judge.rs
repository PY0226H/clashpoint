use crate::{
    application::request_guard::{
        build_rate_limit_headers, enforce_rate_limit, rate_limit_exceeded_response,
        release_idempotency_best_effort, try_acquire_idempotency_or_fail_open,
    },
    AppError, AppState, GetJudgeReportQuery, RequestJudgeJobInput, SubmitDrawVoteInput,
};
use axum::{
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    Extension, Json,
};
use chat_core::User;

const JUDGE_REQUEST_RATE_LIMIT_PER_WINDOW: u64 = 10;
const JUDGE_REQUEST_RATE_LIMIT_WINDOW_SECS: u64 = 300;
const JUDGE_REQUEST_IDEMPOTENCY_TTL_SECS: u64 = 30;

/// Request an AI judge job for a debate session.
/// Note: `styleMode` in request body is kept for compatibility and no longer controls behavior.
/// Effective style is decided by server-side `ai_judge.style_mode` config and returned in `styleModeSource`.
#[utoipa::path(
    post,
    path = "/api/debate/sessions/{id}/judge/jobs",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    request_body = RequestJudgeJobInput,
    responses(
        (status = 202, description = "Judge job accepted", body = crate::RequestJudgeJobOutput),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 409, description = "Request conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn request_judge_job_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    headers: HeaderMap,
    Json(input): Json<RequestJudgeJobInput>,
) -> Result<impl IntoResponse, AppError> {
    let limiter_key = format!("ws:{}:user:{}:session:{}", user.ws_id, user.id, id);
    let decision = enforce_rate_limit(
        &state,
        "judge_job_request",
        &limiter_key,
        JUDGE_REQUEST_RATE_LIMIT_PER_WINDOW,
        JUDGE_REQUEST_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    let rate_headers = build_rate_limit_headers(&decision)?;
    if !decision.allowed {
        return Ok(rate_limit_exceeded_response(
            "judge_job_request",
            rate_headers,
        ));
    }

    let request_idempotency_key = headers
        .get("idempotency-key")
        .and_then(|v| v.to_str().ok())
        .map(str::trim)
        .filter(|v| !v.is_empty())
        .map(ToOwned::to_owned)
        .unwrap_or_else(|| limiter_key.clone());
    let acquired = try_acquire_idempotency_or_fail_open(
        &state,
        "judge_job_request",
        &request_idempotency_key,
        JUDGE_REQUEST_IDEMPOTENCY_TTL_SECS,
    )
    .await;
    if !acquired {
        return Ok((
            StatusCode::CONFLICT,
            rate_headers,
            Json(crate::ErrorOutput::new(
                "idempotency_conflict:judge_job_request",
            )),
        )
            .into_response());
    }

    let ret = match state.request_judge_job(id, &user, input).await {
        Ok(v) => v,
        Err(err) => {
            release_idempotency_best_effort(&state, "judge_job_request", &request_idempotency_key)
                .await;
            return Err(err);
        }
    };
    Ok((StatusCode::ACCEPTED, rate_headers, Json(ret)).into_response())
}

/// Get latest AI judge report for a debate session.
#[utoipa::path(
    get,
    path = "/api/debate/sessions/{id}/judge-report",
    params(
        ("id" = u64, Path, description = "Debate session id"),
        GetJudgeReportQuery
    ),
    responses(
        (status = 200, description = "Judge report query result", body = crate::GetJudgeReportOutput),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_latest_judge_report_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Query(input): Query<GetJudgeReportQuery>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.get_latest_judge_report(id, &user, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Get draw-vote status for latest draw-required judge report in a debate session.
#[utoipa::path(
    get,
    path = "/api/debate/sessions/{id}/draw-vote",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    responses(
        (status = 200, description = "Draw vote status", body = crate::GetDrawVoteOutput),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 409, description = "User is not participant", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_draw_vote_status_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.get_draw_vote_status(id, &user).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Submit or update current user's draw vote.
#[utoipa::path(
    post,
    path = "/api/debate/sessions/{id}/draw-vote/ballots",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    request_body = SubmitDrawVoteInput,
    responses(
        (status = 200, description = "Draw vote submit result", body = crate::SubmitDrawVoteOutput),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 409, description = "Vote conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn submit_draw_vote_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<SubmitDrawVoteInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.submit_draw_vote(id, &user, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}
