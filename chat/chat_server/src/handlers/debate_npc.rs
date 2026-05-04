use crate::{AppError, AppState};
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use serde_json::Value;

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
