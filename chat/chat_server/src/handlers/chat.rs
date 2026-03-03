use crate::{AppError, AppState, CreateChat, UpdateChat, UpdateChatMembers};
use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
    Extension, Json,
};
use chat_core::User;

/// List all chats in the workspace of the user.
#[utoipa::path(
    get,
    path = "/api/chats",
    responses(
        (status = 200, description = "List of chats", body = Vec<Chat>),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_chat_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let chat = state.fetch_chats(user.id as _, user.ws_id as _).await?;
    Ok((StatusCode::OK, Json(chat)))
}

/// Create a new chat in the workspace of the user.
#[utoipa::path(
    post,
    path = "/api/chats",
    responses(
        (status = 201, description = "Chat created", body = Chat),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn create_chat_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Json(input): Json<CreateChat>,
) -> Result<impl IntoResponse, AppError> {
    let chat = state
        .create_chat(input, user.id as _, user.ws_id as _)
        .await?;
    Ok((StatusCode::CREATED, Json(chat)))
}

/// Get the chat info by id.
#[utoipa::path(
    get,
    path = "/api/chats/{id}",
    params(
        ("id" = u64, Path, description = "Chat id")
    ),
    responses(
        (status = 200, description = "Chat found", body = Chat),
        (status = 404, description = "Chat not found", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_chat_handler(
    State(state): State<AppState>,
    Path(id): Path<u64>,
) -> Result<impl IntoResponse, AppError> {
    let chat = state.get_chat_by_id(id as _).await?;
    match chat {
        Some(chat) => Ok(Json(chat)),
        None => Err(AppError::NotFound(format!("chat id {id}"))),
    }
}

#[utoipa::path(
    patch,
    path = "/api/chats/{id}",
    params(
        ("id" = u64, Path, description = "Chat id")
    ),
    request_body = UpdateChat,
    responses(
        (status = 200, description = "Chat updated", body = Chat),
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 404, description = "Chat not found", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn update_chat_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<UpdateChat>,
) -> Result<impl IntoResponse, AppError> {
    let chat = state.update_chat(id, user.ws_id as u64, input).await?;
    Ok((StatusCode::OK, Json(chat)))
}

#[utoipa::path(
    delete,
    path = "/api/chats/{id}",
    params(
        ("id" = u64, Path, description = "Chat id")
    ),
    responses(
        (status = 204, description = "Chat deleted"),
        (status = 404, description = "Chat not found", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn delete_chat_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
) -> Result<impl IntoResponse, AppError> {
    state.delete_chat(id, user.ws_id as u64).await?;
    Ok(StatusCode::NO_CONTENT)
}

#[utoipa::path(
    post,
    path = "/api/chats/{id}/join",
    params(
        ("id" = u64, Path, description = "Chat id")
    ),
    responses(
        (status = 200, description = "Joined chat", body = Chat),
        (status = 400, description = "Invalid operation", body = ErrorOutput),
        (status = 404, description = "Chat not found", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn join_chat_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
) -> Result<impl IntoResponse, AppError> {
    let chat = state
        .join_chat(id, user.ws_id as u64, user.id as u64)
        .await?;
    Ok((StatusCode::OK, Json(chat)))
}

#[utoipa::path(
    post,
    path = "/api/chats/{id}/leave",
    params(
        ("id" = u64, Path, description = "Chat id")
    ),
    responses(
        (status = 200, description = "Left chat", body = Chat),
        (status = 400, description = "Invalid operation", body = ErrorOutput),
        (status = 403, description = "Not chat member", body = ErrorOutput),
        (status = 404, description = "Chat not found", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn leave_chat_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
) -> Result<impl IntoResponse, AppError> {
    let chat = state
        .leave_chat(id, user.ws_id as u64, user.id as u64)
        .await?;
    Ok((StatusCode::OK, Json(chat)))
}

#[utoipa::path(
    post,
    path = "/api/chats/{id}/members/add",
    params(
        ("id" = u64, Path, description = "Chat id")
    ),
    request_body = UpdateChatMembers,
    responses(
        (status = 200, description = "Members added", body = Chat),
        (status = 400, description = "Invalid operation", body = ErrorOutput),
        (status = 403, description = "Not chat member", body = ErrorOutput),
        (status = 404, description = "Chat not found", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn add_chat_members_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<UpdateChatMembers>,
) -> Result<impl IntoResponse, AppError> {
    let chat = state
        .add_chat_members(id, user.ws_id as u64, user.id as u64, input)
        .await?;
    Ok((StatusCode::OK, Json(chat)))
}

#[utoipa::path(
    post,
    path = "/api/chats/{id}/members/remove",
    params(
        ("id" = u64, Path, description = "Chat id")
    ),
    request_body = UpdateChatMembers,
    responses(
        (status = 200, description = "Members removed", body = Chat),
        (status = 400, description = "Invalid operation", body = ErrorOutput),
        (status = 403, description = "Not chat member", body = ErrorOutput),
        (status = 404, description = "Chat not found", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn remove_chat_members_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<UpdateChatMembers>,
) -> Result<impl IntoResponse, AppError> {
    let chat = state
        .remove_chat_members(id, user.ws_id as u64, user.id as u64, input)
        .await?;
    Ok((StatusCode::OK, Json(chat)))
}
