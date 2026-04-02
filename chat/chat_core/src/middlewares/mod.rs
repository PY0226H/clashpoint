mod auth;
mod request_id;
mod server_time;

use crate::User;

use self::{request_id::set_request_id, server_time::ServerTimeLayer};
use axum::{middleware::from_fn, Router};
use tower::ServiceBuilder;
use tower_http::{
    compression::CompressionLayer,
    trace::{DefaultMakeSpan, DefaultOnRequest, DefaultOnResponse, TraceLayer},
    LatencyUnit,
};
use tracing::Level;

pub use auth::{extract_user, extract_user_header_only, verify_token, verify_token_header_only};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AuthVerifyError {
    AccessInvalid,
    AccessExpired,
    TokenVersionMismatch,
    SessionRevoked,
    Internal,
}

impl AuthVerifyError {
    pub fn code(self) -> &'static str {
        match self {
            Self::AccessInvalid => "auth_access_invalid",
            Self::AccessExpired => "auth_access_expired",
            Self::TokenVersionMismatch => "auth_token_version_mismatch",
            Self::SessionRevoked => "auth_session_revoked",
            Self::Internal => "auth_access_invalid",
        }
    }
}

#[derive(Debug, Clone)]
pub struct AuthContext {
    pub user: User,
    pub sid: String,
}

pub trait TokenVerify {
    #[allow(async_fn_in_trait)]
    async fn verify(&self, token: &str) -> Result<AuthContext, AuthVerifyError>;
}

const REQUEST_ID_HEADER: &str = "x-request-id";
const SERVER_TIME_HEADER: &str = "x-server-time";

pub fn set_layer(app: Router) -> Router {
    app.layer(
        ServiceBuilder::new()
            .layer(
                TraceLayer::new_for_http()
                    .make_span_with(DefaultMakeSpan::new().include_headers(true))
                    .on_request(DefaultOnRequest::new().level(Level::INFO))
                    .on_response(
                        DefaultOnResponse::new()
                            .level(Level::INFO)
                            .latency_unit(LatencyUnit::Micros),
                    ),
            )
            .layer(CompressionLayer::new().gzip(true).br(true).deflate(true))
            .layer(from_fn(set_request_id))
            .layer(ServerTimeLayer),
    )
}
