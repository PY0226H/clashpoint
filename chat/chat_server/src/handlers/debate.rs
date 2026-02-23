use crate::{AppError, AppState, JoinDebateSessionInput, ListDebateSessions, ListDebateTopics};
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::IntoResponse,
    Extension, Json,
};
use chat_core::User;

/// List debate topics in the current workspace.
#[utoipa::path(
    get,
    path = "/api/debate/topics",
    params(
        ListDebateTopics
    ),
    responses(
        (status = 200, description = "List of debate topics", body = Vec<crate::DebateTopic>),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_debate_topics_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Query(input): Query<ListDebateTopics>,
) -> Result<impl IntoResponse, AppError> {
    let topics = state.list_debate_topics(user.ws_id as _, input).await?;
    Ok((StatusCode::OK, Json(topics)))
}

/// List debate sessions in the current workspace.
#[utoipa::path(
    get,
    path = "/api/debate/sessions",
    params(
        ListDebateSessions
    ),
    responses(
        (status = 200, description = "List of debate sessions", body = Vec<crate::DebateSessionSummary>),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_debate_sessions_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Query(input): Query<ListDebateSessions>,
) -> Result<impl IntoResponse, AppError> {
    let sessions = state.list_debate_sessions(user.ws_id as _, input).await?;
    Ok((StatusCode::OK, Json(sessions)))
}

/// Join a debate session with selected side.
#[utoipa::path(
    post,
    path = "/api/debate/sessions/{id}/join",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    request_body = JoinDebateSessionInput,
    responses(
        (status = 200, description = "Join result", body = crate::JoinDebateSessionOutput),
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 404, description = "Debate session not found", body = ErrorOutput),
        (status = 409, description = "Join conflict", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn join_debate_session_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<JoinDebateSessionInput>,
) -> Result<impl IntoResponse, AppError> {
    let result = state.join_debate_session(id, &user, input).await?;
    Ok((StatusCode::OK, Json(result)))
}
