use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
pub use chat_core::ErrorOutput;
use chat_core::{json_error_response, JwtError};
use thiserror::Error;
use tracing::warn;

#[derive(Error, Debug)]
pub enum AppError {
    #[error("clickhouse error: {0}")]
    ClickhouseError(#[from] clickhouse::error::Error),

    #[error("missing event context")]
    MissingEventContext,

    #[error("missing event data")]
    MissingEventData,

    #[error("missing system info")]
    MissingSystemInfo,

    #[error("general error: {0}")]
    AnyError(#[from] anyhow::Error),

    #[error("jwt error: {0}")]
    JwtError(#[from] JwtError),
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response<axum::body::Body> {
        let status = match &self {
            Self::MissingEventContext => StatusCode::BAD_REQUEST,
            Self::MissingEventData => StatusCode::BAD_REQUEST,
            Self::MissingSystemInfo => StatusCode::BAD_REQUEST,
            Self::ClickhouseError(_) => StatusCode::INTERNAL_SERVER_ERROR,
            Self::AnyError(_) => StatusCode::INTERNAL_SERVER_ERROR,
            Self::JwtError(_) => StatusCode::UNAUTHORIZED,
        };
        let msg = self.to_string();
        warn!("Status: {}, error: {}", status, msg);

        json_error_response(status, msg)
    }
}
