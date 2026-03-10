use crate::User;
use chrono::Utc;
use jsonwebtoken::{
    decode, encode, errors::ErrorKind as JsonWebTokenErrorKind, Algorithm,
    DecodingKey as JsonDecodingKey, EncodingKey as JsonEncodingKey, Header, Validation,
};
use serde::{Deserialize, Serialize};
use std::{
    collections::HashSet,
    env,
    sync::atomic::{AtomicU64, Ordering},
};
use thiserror::Error;
use tracing::warn;
use uuid::Uuid;

use crate::middlewares::AuthVerifyError;

const JWT_ACCESS_DURATION: u64 = 60 * 15; // 15 minutes
const JWT_REFRESH_DURATION: u64 = 60 * 60 * 24 * 30; // 30 days
const JWT_IMPL_ENV: &str = "JWT_IMPL";
pub const JWT_ISS: &str = "chat_server";
pub const JWT_AUD: &str = "chat_web";
pub const JWT_AUD_REFRESH: &str = "chat_refresh";
pub const JWT_AUD_FILE_TICKET: &str = "chat_file_ticket";
pub const JWT_AUD_NOTIFY_TICKET: &str = "chat_notify_ticket";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct JwtRuntimeConfig {
    pub implementation: &'static str,
    pub legacy_fallback_enabled: bool,
}

#[derive(Debug, Default, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JwtVerifyMetricsSnapshot {
    pub verify_attempt_total: u64,
    pub verify_success_total: u64,
    pub verify_error_total: u64,
    pub legacy_fallback_attempt_total: u64,
    pub legacy_fallback_success_total: u64,
    pub legacy_fallback_failure_total: u64,
    pub verify_error_missing_required_claim_total: u64,
    pub verify_error_invalid_claim_format_total: u64,
    pub verify_error_invalid_token_total: u64,
    pub verify_error_expired_signature_total: u64,
    pub verify_error_immature_signature_total: u64,
    pub verify_error_invalid_issuer_total: u64,
    pub verify_error_invalid_audience_total: u64,
    pub verify_error_invalid_signature_total: u64,
    pub verify_error_other_total: u64,
}

#[derive(Debug, Error)]
pub enum JwtError {
    #[error("jsonwebtoken error: {0}")]
    JsonWebToken(#[from] jsonwebtoken::errors::Error),
}

impl JwtError {
    pub fn to_auth_verify_error(&self) -> AuthVerifyError {
        match self {
            Self::JsonWebToken(err) => match err.kind() {
                JsonWebTokenErrorKind::ExpiredSignature => AuthVerifyError::AccessExpired,
                _ => AuthVerifyError::AccessInvalid,
            },
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum JwtImplementation {
    JsonWebToken,
}

#[derive(Debug)]
struct JwtVerifyMetrics {
    verify_attempt_total: AtomicU64,
    verify_success_total: AtomicU64,
    verify_error_total: AtomicU64,
    legacy_fallback_attempt_total: AtomicU64,
    legacy_fallback_success_total: AtomicU64,
    legacy_fallback_failure_total: AtomicU64,
    verify_error_missing_required_claim_total: AtomicU64,
    verify_error_invalid_claim_format_total: AtomicU64,
    verify_error_invalid_token_total: AtomicU64,
    verify_error_expired_signature_total: AtomicU64,
    verify_error_immature_signature_total: AtomicU64,
    verify_error_invalid_issuer_total: AtomicU64,
    verify_error_invalid_audience_total: AtomicU64,
    verify_error_invalid_signature_total: AtomicU64,
    verify_error_other_total: AtomicU64,
}

impl JwtVerifyMetrics {
    const fn new() -> Self {
        Self {
            verify_attempt_total: AtomicU64::new(0),
            verify_success_total: AtomicU64::new(0),
            verify_error_total: AtomicU64::new(0),
            legacy_fallback_attempt_total: AtomicU64::new(0),
            legacy_fallback_success_total: AtomicU64::new(0),
            legacy_fallback_failure_total: AtomicU64::new(0),
            verify_error_missing_required_claim_total: AtomicU64::new(0),
            verify_error_invalid_claim_format_total: AtomicU64::new(0),
            verify_error_invalid_token_total: AtomicU64::new(0),
            verify_error_expired_signature_total: AtomicU64::new(0),
            verify_error_immature_signature_total: AtomicU64::new(0),
            verify_error_invalid_issuer_total: AtomicU64::new(0),
            verify_error_invalid_audience_total: AtomicU64::new(0),
            verify_error_invalid_signature_total: AtomicU64::new(0),
            verify_error_other_total: AtomicU64::new(0),
        }
    }

    fn observe_attempt(&self) {
        self.verify_attempt_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_success(&self) {
        self.verify_success_total.fetch_add(1, Ordering::Relaxed);
    }

    fn observe_error_jsonwebtoken(&self, err: &jsonwebtoken::errors::Error) {
        self.verify_error_total.fetch_add(1, Ordering::Relaxed);
        match err.kind() {
            JsonWebTokenErrorKind::MissingRequiredClaim(_) => {
                self.verify_error_missing_required_claim_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            JsonWebTokenErrorKind::InvalidClaimFormat(_) => {
                self.verify_error_invalid_claim_format_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            JsonWebTokenErrorKind::InvalidToken => {
                self.verify_error_invalid_token_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            JsonWebTokenErrorKind::ExpiredSignature => {
                self.verify_error_expired_signature_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            JsonWebTokenErrorKind::ImmatureSignature => {
                self.verify_error_immature_signature_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            JsonWebTokenErrorKind::InvalidIssuer => {
                self.verify_error_invalid_issuer_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            JsonWebTokenErrorKind::InvalidAudience => {
                self.verify_error_invalid_audience_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            JsonWebTokenErrorKind::InvalidSignature => {
                self.verify_error_invalid_signature_total
                    .fetch_add(1, Ordering::Relaxed);
            }
            _ => {
                self.verify_error_other_total
                    .fetch_add(1, Ordering::Relaxed);
            }
        }
    }

    fn snapshot(&self) -> JwtVerifyMetricsSnapshot {
        JwtVerifyMetricsSnapshot {
            verify_attempt_total: self.verify_attempt_total.load(Ordering::Relaxed),
            verify_success_total: self.verify_success_total.load(Ordering::Relaxed),
            verify_error_total: self.verify_error_total.load(Ordering::Relaxed),
            legacy_fallback_attempt_total: self
                .legacy_fallback_attempt_total
                .load(Ordering::Relaxed),
            legacy_fallback_success_total: self
                .legacy_fallback_success_total
                .load(Ordering::Relaxed),
            legacy_fallback_failure_total: self
                .legacy_fallback_failure_total
                .load(Ordering::Relaxed),
            verify_error_missing_required_claim_total: self
                .verify_error_missing_required_claim_total
                .load(Ordering::Relaxed),
            verify_error_invalid_claim_format_total: self
                .verify_error_invalid_claim_format_total
                .load(Ordering::Relaxed),
            verify_error_invalid_token_total: self
                .verify_error_invalid_token_total
                .load(Ordering::Relaxed),
            verify_error_expired_signature_total: self
                .verify_error_expired_signature_total
                .load(Ordering::Relaxed),
            verify_error_immature_signature_total: self
                .verify_error_immature_signature_total
                .load(Ordering::Relaxed),
            verify_error_invalid_issuer_total: self
                .verify_error_invalid_issuer_total
                .load(Ordering::Relaxed),
            verify_error_invalid_audience_total: self
                .verify_error_invalid_audience_total
                .load(Ordering::Relaxed),
            verify_error_invalid_signature_total: self
                .verify_error_invalid_signature_total
                .load(Ordering::Relaxed),
            verify_error_other_total: self.verify_error_other_total.load(Ordering::Relaxed),
        }
    }

    #[cfg(test)]
    fn reset(&self) {
        self.verify_attempt_total.store(0, Ordering::Relaxed);
        self.verify_success_total.store(0, Ordering::Relaxed);
        self.verify_error_total.store(0, Ordering::Relaxed);
        self.legacy_fallback_attempt_total
            .store(0, Ordering::Relaxed);
        self.legacy_fallback_success_total
            .store(0, Ordering::Relaxed);
        self.legacy_fallback_failure_total
            .store(0, Ordering::Relaxed);
        self.verify_error_missing_required_claim_total
            .store(0, Ordering::Relaxed);
        self.verify_error_invalid_claim_format_total
            .store(0, Ordering::Relaxed);
        self.verify_error_invalid_token_total
            .store(0, Ordering::Relaxed);
        self.verify_error_expired_signature_total
            .store(0, Ordering::Relaxed);
        self.verify_error_immature_signature_total
            .store(0, Ordering::Relaxed);
        self.verify_error_invalid_issuer_total
            .store(0, Ordering::Relaxed);
        self.verify_error_invalid_audience_total
            .store(0, Ordering::Relaxed);
        self.verify_error_invalid_signature_total
            .store(0, Ordering::Relaxed);
        self.verify_error_other_total.store(0, Ordering::Relaxed);
    }
}

static JWT_VERIFY_METRICS: JwtVerifyMetrics = JwtVerifyMetrics::new();

pub fn get_jwt_verify_metrics_snapshot() -> JwtVerifyMetricsSnapshot {
    JWT_VERIFY_METRICS.snapshot()
}

#[cfg(test)]
pub(crate) fn reset_jwt_verify_metrics_for_test() {
    JWT_VERIFY_METRICS.reset();
}

impl JwtImplementation {
    fn from_env() -> Self {
        let raw = env::var(JWT_IMPL_ENV).ok();
        if let Some(value) = raw
            .as_deref()
            .map(str::trim)
            .filter(|value| !value.is_empty())
        {
            let normalized = value.to_ascii_lowercase();
            if matches!(normalized.as_str(), "jwt_simple" | "jwt-simple") {
                warn!(
                    jwt_impl = value,
                    "JWT_IMPL=jwt_simple is retired, force using jsonwebtoken"
                );
            } else if !matches!(normalized.as_str(), "jsonwebtoken") {
                warn!(
                    jwt_impl = value,
                    "unknown JWT_IMPL value, fallback to jsonwebtoken"
                );
            }
        }
        Self::parse(raw)
    }

    fn parse(raw: Option<String>) -> Self {
        let _ = raw;
        Self::JsonWebToken
    }

    fn as_str(self) -> &'static str {
        match self {
            Self::JsonWebToken => "jsonwebtoken",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct AccessClaims {
    pub sub: String,
    pub ws_id: i64,
    pub sid: String,
    pub jti: String,
    pub ver: i64,
    pub iss: String,
    pub aud: String,
    pub exp: usize,
    pub nbf: usize,
    pub iat: usize,
}

impl AccessClaims {
    fn from_parts(
        user_id: i64,
        ws_id: i64,
        sid: impl Into<String>,
        jti: impl Into<String>,
        ver: i64,
        ttl_secs: u64,
    ) -> Self {
        let now = Utc::now().timestamp().max(0) as usize;
        Self {
            sub: user_id.to_string(),
            ws_id,
            sid: sid.into(),
            jti: jti.into(),
            ver: ver.max(0),
            iss: JWT_ISS.to_string(),
            aud: JWT_AUD.to_string(),
            exp: now + ttl_secs as usize,
            nbf: now,
            iat: now,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct TicketClaims {
    pub id: i64,
    pub ws_id: i64,
    pub ws_name: String,
    pub fullname: String,
    pub email: String,
    pub is_bot: bool,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub iss: String,
    pub aud: String,
    pub exp: usize,
    pub nbf: usize,
    pub iat: usize,
}

impl TicketClaims {
    fn from_user(user: User, audience: &str, ttl_secs: u64) -> Self {
        let now = Utc::now().timestamp().max(0) as usize;
        Self {
            id: user.id,
            ws_id: user.ws_id,
            ws_name: user.ws_name,
            fullname: user.fullname,
            email: user.email,
            is_bot: user.is_bot,
            created_at: user.created_at,
            iss: JWT_ISS.to_string(),
            aud: audience.to_string(),
            exp: now + ttl_secs as usize,
            nbf: now,
            iat: now,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RefreshClaims {
    pub sub: String,
    pub sid: String,
    pub family_id: String,
    pub jti: String,
    pub iss: String,
    pub aud: String,
    pub exp: usize,
    pub nbf: usize,
    pub iat: usize,
}

impl RefreshClaims {
    fn from_parts(
        user_id: i64,
        sid: impl Into<String>,
        family_id: impl Into<String>,
        jti: impl Into<String>,
        ttl_secs: u64,
    ) -> Self {
        let now = Utc::now().timestamp().max(0) as usize;
        Self {
            sub: user_id.to_string(),
            sid: sid.into(),
            family_id: family_id.into(),
            jti: jti.into(),
            iss: JWT_ISS.to_string(),
            aud: JWT_AUD_REFRESH.to_string(),
            exp: now + ttl_secs as usize,
            nbf: now,
            iat: now,
        }
    }
}

pub struct DecodedAccessToken {
    pub user: User,
    pub sid: String,
    pub jti: String,
    pub ver: i64,
    pub exp: usize,
}

pub struct DecodedRefreshToken {
    pub user_id: i64,
    pub sid: String,
    pub family_id: String,
    pub jti: String,
    pub exp: usize,
}

impl From<TicketClaims> for User {
    fn from(value: TicketClaims) -> Self {
        Self {
            id: value.id,
            ws_id: value.ws_id,
            ws_name: value.ws_name,
            fullname: value.fullname,
            email: value.email,
            password_hash: None,
            is_bot: value.is_bot,
            created_at: value.created_at,
        }
    }
}

pub struct EncodingKey {
    implementation: JwtImplementation,
    jsonwebtoken: JsonEncodingKey,
}

#[allow(unused)]
pub struct DecodingKey {
    implementation: JwtImplementation,
    jsonwebtoken: JsonDecodingKey,
}

impl EncodingKey {
    pub fn load(pem: &str) -> Result<Self, JwtError> {
        Self::load_with_runtime(pem, JwtImplementation::from_env())
    }

    fn load_with_runtime(pem: &str, implementation: JwtImplementation) -> Result<Self, JwtError> {
        Ok(Self {
            implementation,
            jsonwebtoken: JsonEncodingKey::from_ed_pem(pem.as_bytes())?,
        })
    }

    pub fn runtime_config(&self) -> JwtRuntimeConfig {
        JwtRuntimeConfig {
            implementation: self.implementation.as_str(),
            legacy_fallback_enabled: false,
        }
    }

    pub fn sign_access_token(
        &self,
        user_id: i64,
        ws_id: i64,
        sid: impl Into<String>,
        token_version: i64,
    ) -> Result<String, JwtError> {
        self.sign_access_token_with_jti(
            user_id,
            ws_id,
            sid,
            token_version,
            Uuid::now_v7().to_string(),
            JWT_ACCESS_DURATION,
        )
    }

    pub fn sign_access_token_with_jti(
        &self,
        user_id: i64,
        ws_id: i64,
        sid: impl Into<String>,
        token_version: i64,
        jti: impl Into<String>,
        ttl_secs: u64,
    ) -> Result<String, JwtError> {
        let claims = AccessClaims::from_parts(user_id, ws_id, sid, jti, token_version, ttl_secs);
        let header = Header::new(Algorithm::EdDSA);
        Ok(encode(&header, &claims, &self.jsonwebtoken)?)
    }

    pub fn sign_refresh_token(
        &self,
        user_id: i64,
        sid: impl Into<String>,
        family_id: impl Into<String>,
    ) -> Result<String, JwtError> {
        self.sign_refresh_token_with_jti(
            user_id,
            sid,
            family_id,
            Uuid::now_v7().to_string(),
            JWT_REFRESH_DURATION,
        )
    }

    pub fn sign_refresh_token_with_jti(
        &self,
        user_id: i64,
        sid: impl Into<String>,
        family_id: impl Into<String>,
        jti: impl Into<String>,
        ttl_secs: u64,
    ) -> Result<String, JwtError> {
        let claims = RefreshClaims::from_parts(user_id, sid, family_id, jti, ttl_secs);
        let header = Header::new(Algorithm::EdDSA);
        Ok(encode(&header, &claims, &self.jsonwebtoken)?)
    }

    pub fn sign_with_audience(
        &self,
        user: impl Into<User>,
        audience: &str,
        ttl_secs: u64,
    ) -> Result<String, JwtError> {
        let user = user.into();
        let claims = TicketClaims::from_user(user, audience, ttl_secs);
        let header = Header::new(Algorithm::EdDSA);
        Ok(encode(&header, &claims, &self.jsonwebtoken)?)
    }

    pub fn sign_file_ticket(
        &self,
        user: impl Into<User>,
        ttl_secs: u64,
    ) -> Result<String, JwtError> {
        self.sign_with_audience(user, JWT_AUD_FILE_TICKET, ttl_secs)
    }

    pub fn sign_notify_ticket(
        &self,
        user: impl Into<User>,
        ttl_secs: u64,
    ) -> Result<String, JwtError> {
        self.sign_with_audience(user, JWT_AUD_NOTIFY_TICKET, ttl_secs)
    }

    pub fn sign_short_lived(
        &self,
        user: impl Into<User>,
        ttl_secs: u64,
    ) -> Result<String, JwtError> {
        let user = user.into();
        self.sign_access_token_with_jti(
            user.id,
            user.ws_id,
            "short-lived",
            0,
            Uuid::now_v7().to_string(),
            ttl_secs,
        )
    }
}

impl DecodingKey {
    pub fn load(pem: &str) -> Result<Self, JwtError> {
        Self::load_with_runtime(pem, JwtImplementation::from_env())
    }

    fn load_with_runtime(pem: &str, implementation: JwtImplementation) -> Result<Self, JwtError> {
        Ok(Self {
            implementation,
            jsonwebtoken: JsonDecodingKey::from_ed_pem(pem.as_bytes())?,
        })
    }

    pub fn runtime_config(&self) -> JwtRuntimeConfig {
        JwtRuntimeConfig {
            implementation: self.implementation.as_str(),
            legacy_fallback_enabled: false,
        }
    }

    fn verify_ticket_with_jsonwebtoken(
        &self,
        token: &str,
        audience: &str,
    ) -> Result<User, JwtError> {
        let mut validation = Validation::new(Algorithm::EdDSA);
        validation.set_issuer(&[JWT_ISS]);
        validation.set_audience(&[audience]);
        validation.required_spec_claims = HashSet::from_iter(
            ["iss", "aud", "exp", "nbf", "iat"]
                .iter()
                .map(ToString::to_string),
        );
        validation.validate_exp = true;
        validation.validate_nbf = true;

        let claims = decode::<TicketClaims>(token, &self.jsonwebtoken, &validation)?;
        Ok(claims.claims.into())
    }

    fn verify_ticket_with_audience(&self, token: &str, audience: &str) -> Result<User, JwtError> {
        JWT_VERIFY_METRICS.observe_attempt();
        let result = self.verify_ticket_with_jsonwebtoken(token, audience);

        match &result {
            Ok(_) => JWT_VERIFY_METRICS.observe_success(),
            Err(JwtError::JsonWebToken(err)) => JWT_VERIFY_METRICS.observe_error_jsonwebtoken(err),
        }

        result
    }

    pub fn verify_access(&self, token: &str) -> Result<DecodedAccessToken, JwtError> {
        JWT_VERIFY_METRICS.observe_attempt();
        let result = self.verify_access_inner(token);
        match &result {
            Ok(_) => JWT_VERIFY_METRICS.observe_success(),
            Err(JwtError::JsonWebToken(err)) => JWT_VERIFY_METRICS.observe_error_jsonwebtoken(err),
        }
        result
    }

    fn verify_access_inner(&self, token: &str) -> Result<DecodedAccessToken, JwtError> {
        let mut validation = Validation::new(Algorithm::EdDSA);
        validation.set_issuer(&[JWT_ISS]);
        validation.set_audience(&[JWT_AUD]);
        validation.required_spec_claims = HashSet::from_iter(
            [
                "iss", "aud", "sub", "ws_id", "sid", "jti", "ver", "exp", "nbf", "iat",
            ]
            .iter()
            .map(ToString::to_string),
        );
        validation.validate_exp = true;
        validation.validate_nbf = true;
        let claims = decode::<AccessClaims>(token, &self.jsonwebtoken, &validation)?;
        let user_id =
            claims.claims.sub.parse::<i64>().map_err(|_| {
                jsonwebtoken::errors::Error::from(JsonWebTokenErrorKind::InvalidToken)
            })?;
        Ok(DecodedAccessToken {
            user: User {
                id: user_id,
                ws_id: claims.claims.ws_id,
                ws_name: String::new(),
                fullname: String::new(),
                email: String::new(),
                password_hash: None,
                is_bot: false,
                created_at: chrono::DateTime::<chrono::Utc>::from_timestamp(0, 0)
                    .unwrap_or_else(Utc::now),
            },
            sid: claims.claims.sid,
            jti: claims.claims.jti,
            ver: claims.claims.ver.max(0),
            exp: claims.claims.exp,
        })
    }

    pub fn verify_refresh(&self, token: &str) -> Result<DecodedRefreshToken, JwtError> {
        let mut validation = Validation::new(Algorithm::EdDSA);
        validation.set_issuer(&[JWT_ISS]);
        validation.set_audience(&[JWT_AUD_REFRESH]);
        validation.required_spec_claims = HashSet::from_iter(
            [
                "iss",
                "aud",
                "sub",
                "sid",
                "family_id",
                "jti",
                "exp",
                "nbf",
                "iat",
            ]
            .iter()
            .map(ToString::to_string),
        );
        validation.validate_exp = true;
        validation.validate_nbf = true;
        let claims = decode::<RefreshClaims>(token, &self.jsonwebtoken, &validation)?;
        let user_id =
            claims.claims.sub.parse::<i64>().map_err(|_| {
                jsonwebtoken::errors::Error::from(JsonWebTokenErrorKind::InvalidToken)
            })?;
        Ok(DecodedRefreshToken {
            user_id,
            sid: claims.claims.sid,
            family_id: claims.claims.family_id,
            jti: claims.claims.jti,
            exp: claims.claims.exp,
        })
    }

    pub fn verify_file_ticket(&self, token: &str) -> Result<User, JwtError> {
        self.verify_ticket_with_audience(token, JWT_AUD_FILE_TICKET)
    }

    pub fn verify_notify_ticket(&self, token: &str) -> Result<User, JwtError> {
        self.verify_ticket_with_audience(token, JWT_AUD_NOTIFY_TICKET)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;
    use serde::Serialize;

    #[derive(Debug, Serialize)]
    struct MissingIatClaims {
        sub: String,
        ws_id: i64,
        sid: String,
        jti: String,
        ver: i64,
        iss: String,
        aud: String,
        exp: usize,
        nbf: usize,
    }

    #[derive(Debug, Serialize)]
    struct NumericAudClaims {
        sub: String,
        ws_id: i64,
        sid: String,
        jti: String,
        ver: i64,
        iss: String,
        aud: usize,
        exp: usize,
        nbf: usize,
        iat: usize,
    }

    fn issue_test_user() -> User {
        User::new(1, "Tyr Chen", "tchen@acme.org")
    }

    fn now_ts() -> usize {
        Utc::now().timestamp().max(0) as usize
    }

    fn reset_metrics() -> std::sync::MutexGuard<'static, ()> {
        static METRICS_TEST_GUARD: std::sync::Mutex<()> = std::sync::Mutex::new(());
        let guard = METRICS_TEST_GUARD
            .lock()
            .expect("lock jwt metrics test guard");
        reset_jwt_verify_metrics_for_test();
        guard
    }

    #[test]
    fn jwt_implementation_parse_should_default_jsonwebtoken() {
        assert_eq!(
            JwtImplementation::parse(None),
            JwtImplementation::JsonWebToken
        );
        assert_eq!(
            JwtImplementation::parse(Some("".to_string())),
            JwtImplementation::JsonWebToken
        );
        assert_eq!(
            JwtImplementation::parse(Some("unknown".to_string())),
            JwtImplementation::JsonWebToken
        );
    }

    #[test]
    fn jwt_implementation_parse_should_ignore_legacy_alias() {
        assert_eq!(
            JwtImplementation::parse(Some("jwt_simple".to_string())),
            JwtImplementation::JsonWebToken
        );
        assert_eq!(
            JwtImplementation::parse(Some("jwt-simple".to_string())),
            JwtImplementation::JsonWebToken
        );
        assert_eq!(
            JwtImplementation::parse(Some("jsonwebtoken".to_string())),
            JwtImplementation::JsonWebToken
        );
    }

    #[test]
    fn runtime_config_should_follow_loaded_impl_and_fallback_defaults() -> Result<()> {
        let _guard = reset_metrics();
        let encoding_pem = include_str!("../../fixtures/encoding.pem");
        let decoding_pem = include_str!("../../fixtures/decoding.pem");
        let ek = EncodingKey::load(encoding_pem)?;
        let dk = DecodingKey::load(decoding_pem)?;

        assert_eq!(ek.runtime_config().implementation, "jsonwebtoken");
        assert_eq!(dk.runtime_config().implementation, "jsonwebtoken");
        assert!(!ek.runtime_config().legacy_fallback_enabled);
        assert!(!dk.runtime_config().legacy_fallback_enabled);
        Ok(())
    }

    #[tokio::test]
    async fn jwt_sign_verify_should_work() -> Result<()> {
        let _guard = reset_metrics();
        let encoding_pem = include_str!("../../fixtures/encoding.pem");
        let decoding_pem = include_str!("../../fixtures/decoding.pem");
        let ek = EncodingKey::load(encoding_pem)?;
        let dk = DecodingKey::load(decoding_pem)?;

        let user = User::new(1, "Tyr Chen", "tchen@acme.org");
        let token = ek.sign_access_token(user.id, user.ws_id, "sid-sign-verify", 0)?;
        let user2 = dk.verify_access(&token)?.user;

        assert_eq!(user.id, user2.id);
        assert_eq!(user.ws_id, user2.ws_id);
        Ok(())
    }

    #[tokio::test]
    async fn audience_scoped_ticket_should_work() -> Result<()> {
        let _guard = reset_metrics();
        let encoding_pem = include_str!("../../fixtures/encoding.pem");
        let decoding_pem = include_str!("../../fixtures/decoding.pem");
        let ek = EncodingKey::load(encoding_pem)?;
        let dk = DecodingKey::load(decoding_pem)?;
        let user = User::new(1, "Tyr Chen", "tchen@acme.org");

        let file_token = ek.sign_file_ticket(user.clone(), 300)?;
        assert!(dk.verify_access(&file_token).is_err());
        let file_user = dk.verify_file_ticket(&file_token)?;
        assert_eq!(file_user.id, user.id);

        let notify_token = ek.sign_notify_ticket(user.clone(), 300)?;
        assert!(dk.verify_access(&notify_token).is_err());
        let notify_user = dk.verify_notify_ticket(&notify_token)?;
        assert_eq!(notify_user.id, user.id);

        Ok(())
    }

    #[tokio::test]
    async fn jwt_verify_should_reject_expired_claims() -> Result<()> {
        let _guard = reset_metrics();
        let encoding_pem = include_str!("../../fixtures/encoding.pem");
        let decoding_pem = include_str!("../../fixtures/decoding.pem");
        let dk = DecodingKey::load(decoding_pem)?;
        let user = issue_test_user();
        let now = now_ts();
        let claims = AccessClaims {
            sub: user.id.to_string(),
            ws_id: user.ws_id,
            sid: "sid-expired".to_string(),
            jti: "jti-expired".to_string(),
            ver: 0,
            iss: JWT_ISS.to_string(),
            aud: JWT_AUD.to_string(),
            exp: now.saturating_sub(3600),
            nbf: now.saturating_sub(7200),
            iat: now.saturating_sub(7200),
        };
        let token = encode(
            &Header::new(Algorithm::EdDSA),
            &claims,
            &JsonEncodingKey::from_ed_pem(encoding_pem.as_bytes())?,
        )?;

        assert!(dk.verify_access(&token).is_err());
        Ok(())
    }

    #[tokio::test]
    async fn jwt_verify_should_reject_not_yet_valid_claims() -> Result<()> {
        let _guard = reset_metrics();
        let encoding_pem = include_str!("../../fixtures/encoding.pem");
        let decoding_pem = include_str!("../../fixtures/decoding.pem");
        let dk = DecodingKey::load(decoding_pem)?;
        let user = issue_test_user();
        let now = now_ts();
        let claims = AccessClaims {
            sub: user.id.to_string(),
            ws_id: user.ws_id,
            sid: "sid-nbf".to_string(),
            jti: "jti-nbf".to_string(),
            ver: 0,
            iss: JWT_ISS.to_string(),
            aud: JWT_AUD.to_string(),
            exp: now + 600,
            nbf: now + 300,
            iat: now,
        };
        let token = encode(
            &Header::new(Algorithm::EdDSA),
            &claims,
            &JsonEncodingKey::from_ed_pem(encoding_pem.as_bytes())?,
        )?;

        assert!(dk.verify_access(&token).is_err());
        Ok(())
    }

    #[tokio::test]
    async fn jwt_verify_should_reject_missing_iat_claim() -> Result<()> {
        let _guard = reset_metrics();
        let encoding_pem = include_str!("../../fixtures/encoding.pem");
        let decoding_pem = include_str!("../../fixtures/decoding.pem");
        let dk = DecodingKey::load(decoding_pem)?;
        let user = issue_test_user();
        let now = now_ts();
        let claims = MissingIatClaims {
            sub: user.id.to_string(),
            ws_id: user.ws_id,
            sid: "sid-missing-iat".to_string(),
            jti: "jti-missing-iat".to_string(),
            ver: 0,
            iss: JWT_ISS.to_string(),
            aud: JWT_AUD.to_string(),
            exp: now + 600,
            nbf: now,
        };
        let token = encode(
            &Header::new(Algorithm::EdDSA),
            &claims,
            &JsonEncodingKey::from_ed_pem(encoding_pem.as_bytes())?,
        )?;

        assert!(dk.verify_access(&token).is_err());
        Ok(())
    }

    #[tokio::test]
    async fn jwt_verify_should_reject_aud_type_confusion_claim() -> Result<()> {
        let _guard = reset_metrics();
        let encoding_pem = include_str!("../../fixtures/encoding.pem");
        let decoding_pem = include_str!("../../fixtures/decoding.pem");
        let dk = DecodingKey::load(decoding_pem)?;
        let user = issue_test_user();
        let now = now_ts();
        let claims = NumericAudClaims {
            sub: user.id.to_string(),
            ws_id: user.ws_id,
            sid: "sid-aud".to_string(),
            jti: "jti-aud".to_string(),
            ver: 0,
            iss: JWT_ISS.to_string(),
            aud: 123,
            exp: now + 600,
            nbf: now,
            iat: now,
        };
        let token = encode(
            &Header::new(Algorithm::EdDSA),
            &claims,
            &JsonEncodingKey::from_ed_pem(encoding_pem.as_bytes())?,
        )?;

        assert!(dk.verify_access(&token).is_err());
        Ok(())
    }

    #[tokio::test]
    async fn jwt_metrics_should_keep_legacy_fallback_counters_zero() -> Result<()> {
        let _guard = reset_metrics();
        let encoding_pem = include_str!("../../fixtures/encoding.pem");
        let decoding_pem = include_str!("../../fixtures/decoding.pem");
        let ek = EncodingKey::load(encoding_pem)?;
        let dk = DecodingKey::load(decoding_pem)?;
        let user = issue_test_user();
        let token = ek.sign_access_token(user.id, user.ws_id, "sid-metrics", 0)?;
        let verified = dk.verify_access(&token)?.user;
        assert_eq!(verified.id, 1);
        let snapshot = get_jwt_verify_metrics_snapshot();
        assert_eq!(snapshot.verify_attempt_total, 1);
        assert_eq!(snapshot.verify_success_total, 1);
        assert_eq!(snapshot.verify_error_total, 0);
        assert_eq!(snapshot.legacy_fallback_attempt_total, 0);
        assert_eq!(snapshot.legacy_fallback_success_total, 0);
        assert_eq!(snapshot.legacy_fallback_failure_total, 0);
        Ok(())
    }

    #[tokio::test]
    async fn jwt_metrics_should_capture_invalid_audience_error() -> Result<()> {
        let _guard = reset_metrics();
        let encoding_pem = include_str!("../../fixtures/encoding.pem");
        let decoding_pem = include_str!("../../fixtures/decoding.pem");
        let dk = DecodingKey::load_with_runtime(decoding_pem, JwtImplementation::JsonWebToken)?;
        let now = Utc::now().timestamp() as usize;
        let claims = AccessClaims {
            sub: "1".to_string(),
            ws_id: 1,
            sid: "sid-invalid-aud".to_string(),
            jti: "jti-invalid-aud".to_string(),
            ver: 0,
            iss: JWT_ISS.to_string(),
            aud: JWT_AUD_FILE_TICKET.to_string(),
            exp: now + 300,
            nbf: now.saturating_sub(1),
            iat: now,
        };
        let token = encode(
            &Header::new(Algorithm::EdDSA),
            &claims,
            &JsonEncodingKey::from_ed_pem(encoding_pem.as_bytes())?,
        )?;
        assert!(dk.verify_access(&token).is_err());

        let snapshot = get_jwt_verify_metrics_snapshot();
        assert_eq!(snapshot.verify_attempt_total, 1);
        assert_eq!(snapshot.verify_success_total, 0);
        assert_eq!(snapshot.verify_error_total, 1);
        assert_eq!(snapshot.verify_error_invalid_audience_total, 1);
        Ok(())
    }
}
