use crate::{
    AppError, AppState, ApplyOpsObservabilityAnomalyActionInput, ListJudgeReviewOpsQuery,
    ListKafkaDlqEventsQuery, ListOpsAlertNotificationsQuery, OpsCreateDebateSessionInput,
    OpsCreateDebateTopicInput, OpsObservabilityThresholds, OpsUpdateDebateSessionInput,
    OpsUpdateDebateTopicInput, UpdateOpsObservabilityAnomalyStateInput, UpsertOpsRoleInput,
};
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::IntoResponse,
    Extension, Json,
};
use chat_core::User;

/// Create debate topic by authorized ops role.
#[utoipa::path(
    post,
    path = "/api/debate/ops/topics",
    request_body = OpsCreateDebateTopicInput,
    responses(
        (status = 201, description = "Created debate topic", body = crate::DebateTopic),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 404, description = "Workspace not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn create_debate_topic_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Json(input): Json<OpsCreateDebateTopicInput>,
) -> Result<impl IntoResponse, AppError> {
    let topic = state.create_debate_topic_by_owner(&user, input).await?;
    Ok((StatusCode::CREATED, Json(topic)))
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
        (status = 404, description = "Topic/workspace not found", body = crate::ErrorOutput),
        (status = 409, description = "Permission conflict", body = crate::ErrorOutput),
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
        (status = 404, description = "Topic/workspace not found", body = crate::ErrorOutput),
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
        (status = 404, description = "Session/workspace not found", body = crate::ErrorOutput),
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

/// List workspace ops role assignments (owner only).
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

/// Upsert ops observability thresholds for current workspace.
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

/// Upsert ops observability anomaly-state map for current workspace.
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

/// Apply anomaly-state action for a single alert key in current workspace.
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

/// List Kafka DLQ events for current workspace.
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
