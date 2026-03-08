use crate::{
    application::request_guard::{
        build_rate_limit_headers, enforce_rate_limit, rate_limit_exceeded_response,
    },
    AppError, AppState, CreateDebateMessageInput, JoinDebateSessionInput, ListDebateMessages,
    ListDebatePinnedMessages, ListDebateSessions, PinDebateMessageInput,
};
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::IntoResponse,
    Extension, Json,
};
use chat_core::User;

const DEBATE_MESSAGE_RATE_LIMIT_PER_WINDOW: u64 = 120;
const DEBATE_MESSAGE_RATE_LIMIT_WINDOW_SECS: u64 = 60;

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
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 409, description = "Join conflict", body = crate::ErrorOutput),
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

/// Send a message in a debate session.
#[utoipa::path(
    post,
    path = "/api/debate/sessions/{id}/messages",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    request_body = CreateDebateMessageInput,
    responses(
        (status = 201, description = "Created message", body = crate::DebateMessage),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 409, description = "Session conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn create_debate_message_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<CreateDebateMessageInput>,
) -> Result<impl IntoResponse, AppError> {
    let limiter_key = format!("ws:{}:user:{}:session:{}", user.ws_id, user.id, id);
    let decision = enforce_rate_limit(
        &state,
        "debate_message_create",
        &limiter_key,
        DEBATE_MESSAGE_RATE_LIMIT_PER_WINDOW,
        DEBATE_MESSAGE_RATE_LIMIT_WINDOW_SECS,
    )
    .await;
    let headers = build_rate_limit_headers(&decision)?;
    if !decision.allowed {
        return Ok(rate_limit_exceeded_response(
            "debate_message_create",
            headers,
        ));
    }

    let msg = state.create_debate_message(id, &user, input).await?;
    Ok((StatusCode::CREATED, headers, Json(msg)).into_response())
}

/// List messages in a debate session.
#[utoipa::path(
    get,
    path = "/api/debate/sessions/{id}/messages",
    params(
        ("id" = u64, Path, description = "Debate session id"),
        ListDebateMessages
    ),
    responses(
        (status = 200, description = "Debate messages", body = Vec<crate::DebateMessage>),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 409, description = "User cannot read in current session status", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_debate_messages_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Query(input): Query<ListDebateMessages>,
) -> Result<impl IntoResponse, AppError> {
    let messages = state.list_debate_messages(id, &user, input).await?;
    Ok((StatusCode::OK, Json(messages)))
}

/// Pin an existing debate message with wallet consume.
#[utoipa::path(
    post,
    path = "/api/debate/messages/{id}/pin",
    params(
        ("id" = u64, Path, description = "Debate message id")
    ),
    request_body = PinDebateMessageInput,
    responses(
        (status = 200, description = "Pin result", body = crate::PinDebateMessageOutput),
        (status = 400, description = "Invalid input", body = crate::ErrorOutput),
        (status = 404, description = "Debate message not found", body = crate::ErrorOutput),
        (status = 409, description = "Pin conflict", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn pin_debate_message_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<PinDebateMessageInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.pin_debate_message(id, &user, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// List pinned messages in a debate session.
#[utoipa::path(
    get,
    path = "/api/debate/sessions/{id}/pins",
    params(
        ("id" = u64, Path, description = "Debate session id"),
        ListDebatePinnedMessages
    ),
    responses(
        (status = 200, description = "Pinned debate messages", body = Vec<crate::DebatePinnedMessage>),
        (status = 404, description = "Debate session not found", body = crate::ErrorOutput),
        (status = 409, description = "User cannot read in current session status", body = crate::ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_debate_pinned_messages_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Query(input): Query<ListDebatePinnedMessages>,
) -> Result<impl IntoResponse, AppError> {
    let pins = state.list_debate_pinned_messages(id, &user, input).await?;
    Ok((StatusCode::OK, Json(pins)))
}
