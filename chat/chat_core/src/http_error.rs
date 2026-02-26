use axum::{
    body::Body,
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
pub struct ErrorOutput {
    pub error: String,
}

impl ErrorOutput {
    pub fn new(error: impl Into<String>) -> Self {
        Self {
            error: error.into(),
        }
    }
}

pub fn json_error_response(status: StatusCode, error: impl Into<String>) -> Response<Body> {
    (status, Json(ErrorOutput::new(error))).into_response()
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::to_bytes;

    #[tokio::test]
    async fn json_error_response_should_keep_status_and_payload() {
        let res = json_error_response(StatusCode::BAD_REQUEST, "bad-request");
        assert_eq!(res.status(), StatusCode::BAD_REQUEST);
        let body = to_bytes(res.into_body(), usize::MAX)
            .await
            .expect("read body");
        let payload = String::from_utf8(body.to_vec()).expect("utf8 body");
        assert_eq!(payload, r#"{"error":"bad-request"}"#);
    }
}
