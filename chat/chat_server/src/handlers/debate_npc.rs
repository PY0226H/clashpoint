use crate::{AppError, AppState};
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::IntoResponse,
    Extension, Json,
};
use chat_core::User;
use serde_json::Value;

#[utoipa::path(
    get,
    path = "/api/debate/sessions/{session_id}/npc/actions",
    params(
        ("session_id" = u64, Path, description = "Debate session id"),
        crate::ListDebateNpcActions,
    ),
    responses(
        (status = 200, description = "Recent public virtual judge NPC actions", body = crate::ListDebateNpcActionsOutput),
        (status = 401, description = "Missing or invalid token", body = crate::ErrorOutput),
        (status = 404, description = "Session not found", body = crate::ErrorOutput),
        (status = 409, description = "Room is not readable", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(("token" = []))
)]
pub(crate) async fn list_debate_npc_actions_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(session_id): Path<u64>,
    Query(query): Query<crate::ListDebateNpcActions>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state
        .list_debate_npc_actions(&user, session_id, query)
        .await?;
    Ok((StatusCode::OK, Json(ret)))
}

#[utoipa::path(
    post,
    path = "/api/debate/sessions/{session_id}/npc/public-calls",
    params(
        ("session_id" = u64, Path, description = "Debate session id"),
    ),
    request_body = crate::CreateDebateNpcPublicCallInput,
    responses(
        (status = 201, description = "Room-visible virtual judge NPC call queued", body = crate::DebateNpcPublicCall),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 401, description = "Missing or invalid token", body = crate::ErrorOutput),
        (status = 404, description = "Session not found", body = crate::ErrorOutput),
        (status = 409, description = "NPC public call is not allowed", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(("token" = []))
)]
pub(crate) async fn create_debate_npc_public_call_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(session_id): Path<u64>,
    Json(input): Json<crate::CreateDebateNpcPublicCallInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state
        .create_debate_npc_public_call(&user, session_id, input)
        .await?;
    Ok((StatusCode::CREATED, Json(ret)))
}

#[utoipa::path(
    post,
    path = "/api/debate/sessions/{session_id}/npc/actions/{action_id}/feedback",
    params(
        ("session_id" = u64, Path, description = "Debate session id"),
        ("action_id" = u64, Path, description = "NPC action id"),
    ),
    request_body = crate::SubmitDebateNpcActionFeedbackInput,
    responses(
        (status = 200, description = "Private feedback recorded", body = crate::DebateNpcActionFeedback),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 401, description = "Missing or invalid token", body = crate::ErrorOutput),
        (status = 404, description = "Session or action not found", body = crate::ErrorOutput),
        (status = 409, description = "Room is not readable or action mismatch", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(("token" = []))
)]
pub(crate) async fn submit_debate_npc_action_feedback_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path((session_id, action_id)): Path<(u64, u64)>,
    Json(input): Json<crate::SubmitDebateNpcActionFeedbackInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state
        .submit_debate_npc_action_feedback(&user, session_id, action_id, input)
        .await?;
    Ok((StatusCode::OK, Json(ret)))
}

#[utoipa::path(
    get,
    path = "/api/debate/ops/npc/sessions/{session_id}/config",
    params(
        ("session_id" = u64, Path, description = "Debate session id"),
    ),
    responses(
        (status = 200, description = "Virtual judge NPC room config", body = crate::DebateNpcRoomConfig),
        (status = 401, description = "Missing or invalid token", body = crate::ErrorOutput),
        (status = 404, description = "Session not found", body = crate::ErrorOutput),
        (status = 409, description = "Missing debate_manage permission", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(("token" = []))
)]
pub(crate) async fn get_debate_npc_room_config_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(session_id): Path<u64>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state
        .get_debate_npc_room_config_by_ops(&user, session_id, None)
        .await?;
    Ok((StatusCode::OK, Json(ret)))
}

#[utoipa::path(
    put,
    path = "/api/debate/ops/npc/sessions/{session_id}/config",
    params(
        ("session_id" = u64, Path, description = "Debate session id"),
    ),
    request_body = crate::UpsertDebateNpcRoomConfigInput,
    responses(
        (status = 200, description = "Updated virtual judge NPC room config", body = crate::DebateNpcRoomConfig),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 401, description = "Missing or invalid token", body = crate::ErrorOutput),
        (status = 404, description = "Session not found", body = crate::ErrorOutput),
        (status = 409, description = "Missing debate_manage permission", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(("token" = []))
)]
pub(crate) async fn upsert_debate_npc_room_config_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(session_id): Path<u64>,
    Json(input): Json<crate::UpsertDebateNpcRoomConfigInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state
        .upsert_debate_npc_room_config_by_ops(&user, session_id, input)
        .await?;
    Ok((StatusCode::OK, Json(ret)))
}

#[utoipa::path(
    get,
    path = "/api/internal/ai/debate/npc/sessions/{session_id}/context",
    params(
        ("session_id" = u64, Path, description = "Debate session id"),
        crate::GetDebateNpcDecisionContextQuery,
    ),
    responses(
        (status = 200, description = "Public debate context for NPC decision", body = crate::GetDebateNpcDecisionContextOutput),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 401, description = "Missing or invalid internal key", body = crate::ErrorOutput),
        (status = 404, description = "Session or trigger message not found", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(("internal_key" = []))
)]
pub(crate) async fn get_debate_npc_decision_context_handler(
    State(state): State<AppState>,
    Path(session_id): Path<u64>,
    Query(query): Query<crate::GetDebateNpcDecisionContextQuery>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state
        .get_debate_npc_decision_context(session_id, query)
        .await?;
    Ok((StatusCode::OK, Json(ret)))
}

#[utoipa::path(
    post,
    path = "/api/internal/ai/debate/npc/actions/candidates",
    request_body = crate::SubmitDebateNpcActionCandidateInput,
    responses(
        (status = 200, description = "NPC action candidate accepted or rejected", body = crate::SubmitDebateNpcActionCandidateOutput),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 401, description = "Missing or invalid internal key", body = crate::ErrorOutput),
        (status = 500, description = "Internal server error", body = crate::ErrorOutput),
    ),
    security(("internal_key" = []))
)]
pub(crate) async fn submit_debate_npc_action_candidate_handler(
    State(state): State<AppState>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.submit_debate_npc_action_candidate(payload).await?;
    Ok((StatusCode::OK, Json(ret)))
}
