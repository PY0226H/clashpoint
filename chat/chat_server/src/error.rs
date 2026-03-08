use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
pub use chat_core::ErrorOutput;
use chat_core::{json_error_response, AgentError, JwtError};
use thiserror::Error;

#[derive(Error, Debug)]
pub enum AppError {
    #[error("email already exists: {0}")]
    EmailAlreadyExists(String),

    #[error("create chat error: {0}")]
    CreateChatError(String),

    #[error("create agent error: {0}")]
    CreateAgentError(String),

    #[error("update agent error: {0}")]
    UpdateAgentError(String),

    #[error("user {user_id} is not member of chat {chat_id}")]
    NotChatMemberError { user_id: u64, chat_id: u64 },

    #[error("create message error: {0}")]
    CreateMessageError(String),

    #[error("debate error: {0}")]
    DebateError(String),

    #[error("debate conflict: {0}")]
    DebateConflict(String),

    #[error("payment error: {0}")]
    PaymentError(String),

    #[error("payment conflict: {0}")]
    PaymentConflict(String),

    #[error("{0}")]
    ChatFileError(String),

    #[error("not logged in")]
    NotLoggedIn,

    #[error("Not found: {0}")]
    NotFound(String),

    #[error("io error: {0}")]
    IoError(#[from] std::io::Error),

    #[error("sql error: {0}")]
    SqlxError(#[from] sqlx::Error),

    #[error("password hash error: {0}")]
    PasswordHashError(#[from] argon2::password_hash::Error),

    #[error("general error: {0}")]
    AnyError(#[from] anyhow::Error),

    #[error("http header parse error: {0}")]
    HttpHeaderError(#[from] axum::http::header::InvalidHeaderValue),

    #[error("ai agent error: {0}")]
    AiAgentError(#[from] AgentError),

    #[error("jwt error: {0}")]
    JwtError(#[from] JwtError),
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response<axum::body::Body> {
        let status = match &self {
            Self::SqlxError(_) => StatusCode::INTERNAL_SERVER_ERROR,
            Self::PasswordHashError(_) => StatusCode::UNPROCESSABLE_ENTITY,
            Self::AnyError(_) => StatusCode::INTERNAL_SERVER_ERROR,
            Self::HttpHeaderError(_) => StatusCode::UNPROCESSABLE_ENTITY,
            Self::EmailAlreadyExists(_) => StatusCode::CONFLICT,
            Self::CreateChatError(_) => StatusCode::BAD_REQUEST,
            Self::CreateAgentError(_) => StatusCode::BAD_REQUEST,
            Self::UpdateAgentError(_) => StatusCode::BAD_REQUEST,
            Self::DebateError(_) => StatusCode::BAD_REQUEST,
            Self::DebateConflict(_) => StatusCode::CONFLICT,
            Self::PaymentError(_) => StatusCode::BAD_REQUEST,
            Self::PaymentConflict(_) => StatusCode::CONFLICT,
            Self::NotChatMemberError { .. } => StatusCode::FORBIDDEN,
            Self::NotLoggedIn => StatusCode::UNAUTHORIZED,
            Self::NotFound(_) => StatusCode::NOT_FOUND,
            Self::IoError(_) => StatusCode::INTERNAL_SERVER_ERROR,
            Self::CreateMessageError(_) => StatusCode::BAD_REQUEST,
            Self::ChatFileError(_) => StatusCode::BAD_REQUEST,
            Self::AiAgentError(_) => StatusCode::INTERNAL_SERVER_ERROR,
            Self::JwtError(_) => StatusCode::UNAUTHORIZED,
        };

        json_error_response(status, self.to_string())
    }
}
