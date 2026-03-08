use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use chat_core::{json_error_response, JwtError};
use thiserror::Error;

#[derive(Error, Debug)]
pub enum AppError {
    #[error("io error: {0}")]
    IoError(#[from] std::io::Error),

    #[error("jwt error: {0}")]
    JwtError(#[from] JwtError),
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response<axum::body::Body> {
        let status = match &self {
            Self::JwtError(_) => StatusCode::FORBIDDEN,
            Self::IoError(_) => StatusCode::INTERNAL_SERVER_ERROR,
        };

        json_error_response(status, self.to_string())
    }
}
