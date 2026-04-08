use axum::{
    body::Body,
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use utoipa::ToSchema;

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ErrorOutput {
    pub error: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub code: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub details: Option<Value>,
}

impl ErrorOutput {
    pub fn new(error: impl Into<String>) -> Self {
        Self::new_with_details(error, None)
    }

    pub fn new_with_details(error: impl Into<String>, details: Option<Value>) -> Self {
        let raw_error = error.into();
        let stripped = strip_error_prefix(raw_error.trim());
        let code = normalize_error_code(&stripped);
        Self {
            error: raw_error,
            code: Some(code),
            message: Some(stripped),
            details,
        }
    }
}

pub fn json_error_response(status: StatusCode, error: impl Into<String>) -> Response<Body> {
    (status, Json(ErrorOutput::new(error))).into_response()
}

fn strip_error_prefix(raw: &str) -> String {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return String::new();
    }
    let lower = trimmed.to_ascii_lowercase();
    let prefixes = [
        "debate conflict:",
        "debate error:",
        "payment conflict:",
        "payment error:",
        "not found:",
        "validation error:",
        "server error:",
        "auth error:",
    ];
    for prefix in prefixes {
        if lower.starts_with(prefix) {
            return trimmed[prefix.len()..].trim().to_string();
        }
    }
    trimmed.to_string()
}

fn normalize_error_code(raw: &str) -> String {
    let trimmed = raw.trim();
    if trimmed.starts_with("ops_permission_denied:") {
        let mut parts = trimmed.split(':');
        if let (Some(a), Some(b)) = (parts.next(), parts.next()) {
            return format!("{a}:{b}");
        }
    }
    if trimmed.starts_with("rate_limit_exceeded:") {
        let mut parts = trimmed.split(':');
        if let (Some(a), Some(b)) = (parts.next(), parts.next()) {
            return format!("{a}:{b}");
        }
    }
    if trimmed.starts_with("ops_role_target_user_not_found") {
        return "ops_role_target_user_not_found".to_string();
    }
    trimmed.to_string()
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
        let payload: ErrorOutput = serde_json::from_slice(&body).expect("payload");
        assert_eq!(payload.error, "bad-request");
        assert_eq!(payload.code.as_deref(), Some("bad-request"));
        assert_eq!(payload.message.as_deref(), Some("bad-request"));
        assert!(payload.details.is_none());
    }

    #[test]
    fn error_output_should_normalize_ops_permission_denied_code() {
        let payload =
            ErrorOutput::new("debate conflict: ops_permission_denied:role_manage:owner only");
        assert_eq!(
            payload.code.as_deref(),
            Some("ops_permission_denied:role_manage")
        );
        assert_eq!(
            payload.message.as_deref(),
            Some("ops_permission_denied:role_manage:owner only")
        );
    }

    #[test]
    fn error_output_should_normalize_not_found_code() {
        let payload = ErrorOutput::new("Not found: ops_role_target_user_not_found:123");
        assert_eq!(
            payload.code.as_deref(),
            Some("ops_role_target_user_not_found")
        );
        assert_eq!(
            payload.message.as_deref(),
            Some("ops_role_target_user_not_found:123")
        );
    }
}
