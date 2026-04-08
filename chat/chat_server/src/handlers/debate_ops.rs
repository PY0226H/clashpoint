use crate::{
    application::request_guard::{
        build_rate_limit_headers, enforce_rate_limit, rate_limit_exceeded_response,
        release_idempotency_best_effort, request_idempotency_key_from_headers,
        request_rate_limit_ip_key_from_headers, try_acquire_idempotency_or_fail_open,
    },
    AppError, AppState, ApplyOpsObservabilityAnomalyActionInput, ExecuteJudgeReplayOpsInput,
    GetJudgeFinalDispatchFailureStatsQuery, GetJudgeReplayPreviewOpsQuery,
    ListJudgeReplayActionsOpsQuery, ListJudgeReviewOpsQuery, ListJudgeTraceReplayOpsQuery,
    ListKafkaDlqEventsQuery, ListOpsAlertNotificationsQuery, ListOpsServiceSplitReviewAuditsQuery,
    OpsCreateDebateSessionInput, OpsCreateDebateTopicInput, OpsObservabilityThresholds,
    OpsUpdateDebateSessionInput, OpsUpdateDebateTopicInput, RunOpsObservabilityEvaluationQuery,
    UpdateOpsObservabilityAnomalyStateInput, UpsertOpsRoleInput, UpsertOpsServiceSplitReviewInput,
};
use axum::{
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode},
    response::{IntoResponse, Response},
    Extension, Json,
};
use chat_core::User;

const OPS_DEBATE_TOPIC_CREATE_USER_RATE_LIMIT_PER_WINDOW: u64 = 30;
const OPS_DEBATE_TOPIC_CREATE_IP_RATE_LIMIT_PER_WINDOW: u64 = 90;
const OPS_DEBATE_TOPIC_CREATE_RATE_LIMIT_WINDOW_SECS: u64 = 60;
const OPS_DEBATE_TOPIC_CREATE_IDEMPOTENCY_TTL_SECS: u64 = 30;
const OPS_DEBATE_TOPIC_CREATE_IDEMPOTENCY_MAX_LEN: usize = 160;
const OPS_OBSERVABILITY_EVAL_RATE_LIMIT_PER_WINDOW: u64 = 6;
const OPS_OBSERVABILITY_EVAL_RATE_LIMIT_WINDOW_SECS: u64 = 60;

/// Create debate topic by authorized ops role.
#[utoipa::path(
    post,
    path = "/api/debate/ops/topics",
    request_body = OpsCreateDebateTopicInput,
    responses(
        (status = 201, description = "Created debate topic", body = crate::DebateTopic),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 401, description = "Auth error", body = crate::ErrorOutput),
        (status = 403, description = "Phone not bound", body = crate::ErrorOutput),
        (status = 404, description = "Resource not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
        (status = 429, description = "Rate limited", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn create_debate_topic_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(input): Json<OpsCreateDebateTopicInput>,
) -> Result<Response, AppError> {
    let user_decision = enforce_rate_limit(
        &state,
        "ops_debate_topic_create_user",
        &user.id.to_string(),
        OPS_DEBATE_TOPIC_CREATE_USER_RATE_LIMIT_PER_WINDOW,
        OPS_DEBATE_TOPIC_CREATE_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    let user_rate_headers = build_rate_limit_headers(&user_decision)?;
    if !user_decision.allowed {
        return Ok(rate_limit_exceeded_response(
            "ops_debate_topic_create",
            user_rate_headers,
        ));
    }

    let ip_limit_key =
        request_rate_limit_ip_key_from_headers(&headers).unwrap_or_else(|| "unknown".to_string());
    let ip_decision = enforce_rate_limit(
        &state,
        "ops_debate_topic_create_ip",
        &ip_limit_key,
        OPS_DEBATE_TOPIC_CREATE_IP_RATE_LIMIT_PER_WINDOW,
        OPS_DEBATE_TOPIC_CREATE_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    if !ip_decision.allowed {
        return Ok(rate_limit_exceeded_response(
            "ops_debate_topic_create",
            build_rate_limit_headers(&ip_decision)?,
        ));
    }

    let request_idempotency_key = request_idempotency_key_from_headers(
        &headers,
        "ops_debate_topic_create_idempotency_key_invalid",
        "ops_debate_topic_create_idempotency_key_too_long",
        OPS_DEBATE_TOPIC_CREATE_IDEMPOTENCY_MAX_LEN,
    )?;
    let idempotency_lock_key = request_idempotency_key
        .as_deref()
        .map(|key| format!("u{}:{key}", user.id));
    if let Some(lock_key) = idempotency_lock_key.as_deref() {
        let acquired = try_acquire_idempotency_or_fail_open(
            &state,
            "ops_debate_topic_create",
            lock_key,
            OPS_DEBATE_TOPIC_CREATE_IDEMPOTENCY_TTL_SECS,
        )
        .await;
        if !acquired {
            return Err(AppError::DebateConflict(
                "idempotency_conflict:ops_debate_topic_create".to_string(),
            ));
        }
    }

    let ret = state
        .create_debate_topic_by_owner_with_meta(&user, input, request_idempotency_key.as_deref())
        .await;
    if let Some(lock_key) = idempotency_lock_key.as_deref() {
        release_idempotency_best_effort(&state, "ops_debate_topic_create", lock_key).await;
    }
    let (topic, _) = ret?;
    Ok((StatusCode::CREATED, user_rate_headers, Json(topic)).into_response())
}

/// Update debate topic by authorized ops role.
#[utoipa::path(
    put,
    path = "/api/debate/ops/topics/{id}",
    params(
        ("id" = u64, Path, description = "Debate topic id")
    ),
    request_body = OpsUpdateDebateTopicInput,
    responses(
        (status = 200, description = "Updated debate topic", body = crate::DebateTopic),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 401, description = "Auth error", body = crate::ErrorOutput),
        (status = 403, description = "Phone not bound", body = crate::ErrorOutput),
        (status = 422, description = "Body parse error", body = crate::ErrorOutput),
        (status = 404, description = "Topic not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn update_debate_topic_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<OpsUpdateDebateTopicInput>,
) -> Result<impl IntoResponse, AppError> {
    let topic = state.update_debate_topic_by_owner(&user, id, input).await?;
    Ok((StatusCode::OK, Json(topic)))
}

/// Create debate session by authorized ops role.
#[utoipa::path(
    post,
    path = "/api/debate/ops/sessions",
    request_body = OpsCreateDebateSessionInput,
    responses(
        (status = 201, description = "Created debate session", body = crate::DebateSessionSummary),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 404, description = "Topic not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn create_debate_session_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Json(input): Json<OpsCreateDebateSessionInput>,
) -> Result<impl IntoResponse, AppError> {
    let session = state.create_debate_session_by_owner(&user, input).await?;
    Ok((StatusCode::CREATED, Json(session)))
}

/// Update debate session by authorized ops role.
#[utoipa::path(
    put,
    path = "/api/debate/ops/sessions/{id}",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    request_body = OpsUpdateDebateSessionInput,
    responses(
        (status = 200, description = "Updated debate session", body = crate::DebateSessionSummary),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 404, description = "Session not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn update_debate_session_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<OpsUpdateDebateSessionInput>,
) -> Result<impl IntoResponse, AppError> {
    let session = state
        .update_debate_session_by_owner(&user, id, input)
        .await?;
    Ok((StatusCode::OK, Json(session)))
}

/// List platform ops role assignments (platform admin only).
#[utoipa::path(
    get,
    path = "/api/debate/ops/rbac/roles",
    responses(
        (status = 200, description = "Ops role assignments", body = crate::ListOpsRoleAssignmentsOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_ops_role_assignments_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.list_ops_role_assignments_by_owner(&user).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Get current user's ops RBAC capability snapshot.
#[utoipa::path(
    get,
    path = "/api/debate/ops/rbac/me",
    responses(
        (status = 200, description = "Current ops RBAC capabilities", body = crate::GetOpsRbacMeOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_ops_rbac_me_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.get_ops_rbac_me(&user).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Get current ops observability config snapshot.
#[utoipa::path(
    get,
    path = "/api/debate/ops/observability/config",
    responses(
        (status = 200, description = "Ops observability config", body = crate::GetOpsObservabilityConfigOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_ops_observability_config_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.get_ops_observability_config(&user).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Get canonical ops metrics dictionary for observability and SLO governance.
#[utoipa::path(
    get,
    path = "/api/debate/ops/observability/metrics-dictionary",
    responses(
        (status = 200, description = "Ops metrics dictionary", body = crate::GetOpsMetricsDictionaryOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_ops_observability_metrics_dictionary_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.get_ops_metrics_dictionary(&user).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Get current SLO snapshot for ops observability.
#[utoipa::path(
    get,
    path = "/api/debate/ops/observability/slo-snapshot",
    responses(
        (status = 200, description = "Ops SLO snapshot", body = crate::GetOpsSloSnapshotOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_ops_observability_slo_snapshot_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.get_ops_observability_slo_snapshot(&user).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Evaluate service split readiness by R6 threshold rules.
#[utoipa::path(
    get,
    path = "/api/debate/ops/observability/split-readiness",
    responses(
        (status = 200, description = "Service split readiness snapshot", body = crate::GetOpsServiceSplitReadinessOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_ops_service_split_readiness_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.get_ops_service_split_readiness(&user).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// List split-readiness manual review audit history for platform scope.
#[utoipa::path(
    get,
    path = "/api/debate/ops/observability/split-readiness/reviews",
    params(
        ListOpsServiceSplitReviewAuditsQuery
    ),
    responses(
        (status = 200, description = "Service split readiness review audits", body = crate::ListOpsServiceSplitReviewAuditsOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_ops_service_split_review_audits_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Query(query): Query<ListOpsServiceSplitReviewAuditsQuery>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state
        .list_ops_service_split_review_audits(&user, query)
        .await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Upsert manual review input for split-readiness compliance threshold.
#[utoipa::path(
    put,
    path = "/api/debate/ops/observability/split-readiness/review",
    request_body = UpsertOpsServiceSplitReviewInput,
    responses(
        (status = 200, description = "Service split readiness snapshot", body = crate::GetOpsServiceSplitReadinessOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn upsert_ops_service_split_review_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Json(input): Json<UpsertOpsServiceSplitReviewInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.upsert_ops_service_split_review(&user, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Upsert ops observability thresholds for platform scope.
#[utoipa::path(
    put,
    path = "/api/debate/ops/observability/thresholds",
    request_body = OpsObservabilityThresholds,
    responses(
        (status = 200, description = "Updated ops observability config", body = crate::GetOpsObservabilityConfigOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn upsert_ops_observability_thresholds_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Json(input): Json<OpsObservabilityThresholds>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state
        .upsert_ops_observability_thresholds(&user, input)
        .await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Upsert ops observability anomaly-state map for platform scope.
#[utoipa::path(
    put,
    path = "/api/debate/ops/observability/anomaly-state",
    request_body = UpdateOpsObservabilityAnomalyStateInput,
    responses(
        (status = 200, description = "Updated ops observability config", body = crate::GetOpsObservabilityConfigOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn upsert_ops_observability_anomaly_state_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Json(input): Json<UpdateOpsObservabilityAnomalyStateInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state
        .upsert_ops_observability_anomaly_state(&user, input)
        .await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Apply anomaly-state action for a single alert key in platform scope.
#[utoipa::path(
    post,
    path = "/api/debate/ops/observability/anomaly-state/actions",
    request_body = ApplyOpsObservabilityAnomalyActionInput,
    responses(
        (status = 200, description = "Updated ops observability config", body = crate::GetOpsObservabilityConfigOutput),
        (status = 400, description = "Invalid action input", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn apply_ops_observability_anomaly_action_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Json(input): Json<ApplyOpsObservabilityAnomalyActionInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state
        .apply_ops_observability_anomaly_action(&user, input)
        .await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Trigger one-shot observability evaluation for platform scope.
#[utoipa::path(
    post,
    path = "/api/debate/ops/observability/evaluate-once",
    params(
        RunOpsObservabilityEvaluationQuery
    ),
    responses(
        (status = 200, description = "Ops alert evaluation report", body = crate::OpsAlertEvalReport),
        (status = 429, description = "Rate limit exceeded", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn run_ops_observability_evaluation_once_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Query(query): Query<RunOpsObservabilityEvaluationQuery>,
) -> Result<impl IntoResponse, AppError> {
    let limiter_key = format!("user:{}", user.id);
    let decision = enforce_rate_limit(
        &state,
        "ops_observability_evaluate_once",
        &limiter_key,
        OPS_OBSERVABILITY_EVAL_RATE_LIMIT_PER_WINDOW,
        OPS_OBSERVABILITY_EVAL_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    let rate_headers = build_rate_limit_headers(&decision)?;
    if !decision.allowed {
        return Ok(rate_limit_exceeded_response(
            "ops_observability_evaluate_once",
            rate_headers,
        ));
    }
    let ret = if query.dry_run.unwrap_or(false) {
        state.preview_ops_observability_alerts_by_ops(&user).await?
    } else {
        state
            .evaluate_ops_observability_alerts_by_ops(&user)
            .await?
    };
    Ok((StatusCode::OK, rate_headers, Json(ret)).into_response())
}

/// List ops observability alert notifications.
#[utoipa::path(
    get,
    path = "/api/debate/ops/observability/alerts",
    params(
        ListOpsAlertNotificationsQuery
    ),
    responses(
        (status = 200, description = "Ops alert notifications", body = crate::ListOpsAlertNotificationsOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_ops_alert_notifications_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Query(input): Query<ListOpsAlertNotificationsQuery>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.list_ops_alert_notifications(&user, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// List Kafka DLQ events for platform scope.
#[utoipa::path(
    get,
    path = "/api/debate/ops/kafka/dlq",
    params(
        ListKafkaDlqEventsQuery
    ),
    responses(
        (status = 200, description = "Kafka DLQ events", body = crate::ListKafkaDlqEventsOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_kafka_dlq_events_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Query(input): Query<ListKafkaDlqEventsQuery>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.list_kafka_dlq_events(&user, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Get Kafka transport cutover readiness and outbox relay metrics snapshot.
#[utoipa::path(
    get,
    path = "/api/debate/ops/kafka/readiness",
    responses(
        (status = 200, description = "Kafka transport readiness", body = crate::GetKafkaTransportReadinessOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_kafka_transport_readiness_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.get_kafka_transport_readiness(&user).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Replay Kafka DLQ event by id.
#[utoipa::path(
    post,
    path = "/api/debate/ops/kafka/dlq/{id}/replay",
    params(
        ("id" = u64, Path, description = "Kafka DLQ event id")
    ),
    responses(
        (status = 200, description = "Replay result", body = crate::KafkaDlqActionOutput),
        (status = 404, description = "DLQ event not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission or state conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn replay_kafka_dlq_event_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.replay_kafka_dlq_event(&user, id).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Discard Kafka DLQ event by id.
#[utoipa::path(
    post,
    path = "/api/debate/ops/kafka/dlq/{id}/discard",
    params(
        ("id" = u64, Path, description = "Kafka DLQ event id")
    ),
    responses(
        (status = 200, description = "Discard result", body = crate::KafkaDlqActionOutput),
        (status = 404, description = "DLQ event not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission or state conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn discard_kafka_dlq_event_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.discard_kafka_dlq_event(&user, id).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Upsert an ops role assignment (owner only).
#[utoipa::path(
    put,
    path = "/api/debate/ops/rbac/roles/{userId}",
    params(
        ("userId" = u64, Path, description = "Target user id")
    ),
    request_body = UpsertOpsRoleInput,
    responses(
        (status = 200, description = "Updated ops role assignment", body = crate::OpsRoleAssignment),
        (status = 404, description = "Target user not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn upsert_ops_role_assignment_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(user_id): Path<u64>,
    Json(input): Json<UpsertOpsRoleInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state
        .upsert_ops_role_assignment_by_owner(&user, user_id, input)
        .await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Revoke an ops role assignment (owner only).
#[utoipa::path(
    delete,
    path = "/api/debate/ops/rbac/roles/{userId}",
    params(
        ("userId" = u64, Path, description = "Target user id")
    ),
    responses(
        (status = 200, description = "Revoke result", body = crate::RevokeOpsRoleOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn revoke_ops_role_assignment_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(user_id): Path<u64>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state
        .revoke_ops_role_assignment_by_owner(&user, user_id)
        .await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// List judge reports for ops review with evidence/anomaly filters.
#[utoipa::path(
    get,
    path = "/api/debate/ops/judge-reviews",
    params(
        ListJudgeReviewOpsQuery
    ),
    responses(
        (status = 200, description = "Ops judge review list", body = crate::ListJudgeReviewOpsOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_judge_reviews_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Query(input): Query<ListJudgeReviewOpsQuery>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.list_judge_reviews_by_owner(&user, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Aggregate final dispatch failure types by ops time window.
#[utoipa::path(
    get,
    path = "/api/debate/ops/judge-final-dispatch/failure-stats",
    params(
        GetJudgeFinalDispatchFailureStatsQuery
    ),
    responses(
        (status = 200, description = "Ops final dispatch failure type stats", body = crate::GetJudgeFinalDispatchFailureStatsOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_judge_final_dispatch_failure_stats_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Query(input): Query<GetJudgeFinalDispatchFailureStatsQuery>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state
        .get_judge_final_dispatch_failure_stats_by_owner(&user, input)
        .await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Aggregate judge trace/replay records for ops diagnostics.
#[utoipa::path(
    get,
    path = "/api/debate/ops/judge-trace-replay",
    params(
        ListJudgeTraceReplayOpsQuery
    ),
    responses(
        (status = 200, description = "Ops judge trace/replay aggregation", body = crate::ListJudgeTraceReplayOpsOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_judge_trace_replay_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Query(input): Query<ListJudgeTraceReplayOpsQuery>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.list_judge_trace_replay_by_owner(&user, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Preview replay dispatch payload by scope/job id (no side effects).
#[utoipa::path(
    get,
    path = "/api/debate/ops/judge-replay/preview",
    params(
        GetJudgeReplayPreviewOpsQuery
    ),
    responses(
        (status = 200, description = "Ops replay preview snapshot", body = crate::GetJudgeReplayPreviewOpsOutput),
        (status = 404, description = "Replay target not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_judge_replay_preview_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Query(input): Query<GetJudgeReplayPreviewOpsQuery>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state
        .get_judge_replay_preview_by_owner(&user, input)
        .await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Execute replay for a failed phase/final dispatch job.
#[utoipa::path(
    post,
    path = "/api/debate/ops/judge-replay/execute",
    request_body = ExecuteJudgeReplayOpsInput,
    responses(
        (status = 200, description = "Replay execute accepted", body = crate::ExecuteJudgeReplayOpsOutput),
        (status = 404, description = "Replay target not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission or state conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn execute_judge_replay_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Json(input): Json<ExecuteJudgeReplayOpsInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.execute_judge_replay_by_owner(&user, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// List replay execute audit actions for ops diagnostics.
#[utoipa::path(
    get,
    path = "/api/debate/ops/judge-replay/actions",
    params(
        ListJudgeReplayActionsOpsQuery
    ),
    responses(
        (status = 200, description = "Replay execute audit actions", body = crate::ListJudgeReplayActionsOpsOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_judge_replay_actions_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Query(input): Query<ListJudgeReplayActionsOpsQuery>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state
        .list_judge_replay_actions_by_owner(&user, input)
        .await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Trigger an ops rejudge job for a finished session.
#[utoipa::path(
    post,
    path = "/api/debate/ops/sessions/{id}/judge/rejudge",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    responses(
        (status = 202, description = "Rejudge job accepted", body = crate::RequestJudgeJobOutput),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission or state conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn request_judge_rejudge_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.request_judge_rejudge_by_owner(id, &user).await?;
    Ok((StatusCode::ACCEPTED, Json(ret)))
}
