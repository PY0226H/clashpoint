use crate::{AppError, AppState};
use axum::{extract::State, http::StatusCode, response::IntoResponse, Json};
use serde_json::Value;

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
