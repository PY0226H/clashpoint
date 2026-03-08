use crate::User;
use chrono::Utc;
use jsonwebtoken::{
    decode, encode, errors::ErrorKind as JsonWebTokenErrorKind, Algorithm,
    DecodingKey as JsonDecodingKey, EncodingKey as JsonEncodingKey, Header, Validation,
};
use jwt_simple::prelude::*;
use serde::{Deserialize, Serialize};
use std::{
    collections::HashSet,
    env,
    sync::atomic::{AtomicU64, Ordering},
};
use thiserror::Error;
use tracing::warn;

const JWT_DURATION: u64 = 60 * 60 * 24 * 7; // 1 week
const JWT_IMPL_ENV: &str = "JWT_IMPL";
const JWT_LEGACY_FALLBACK_ENABLED_ENV: &str = "JWT_LEGACY_FALLBACK_ENABLED";
pub const JWT_ISS: &str = "chat_server";
pub const JWT_AUD: &str = "chat_web";
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

    #[error("jwt-simple error: {0}")]
    JwtSimple(#[from] jwt_simple::Error),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum JwtImplementation {
    JsonWebToken,
    JwtSimple,
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

    fn observe_error_jwt_simple(&self) {
        self.verify_error_total.fetch_add(1, Ordering::Relaxed);
        self.verify_error_other_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_legacy_fallback_attempt(&self) {
        self.legacy_fallback_attempt_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_legacy_fallback_success(&self) {
        self.legacy_fallback_success_total
            .fetch_add(1, Ordering::Relaxed);
    }

    fn observe_legacy_fallback_failure(&self) {
        self.legacy_fallback_failure_total
            .fetch_add(1, Ordering::Relaxed);
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
            if !matches!(
                normalized.as_str(),
                "jwt_simple" | "jwt-simple" | "jsonwebtoken"
            ) {
                warn!(
                    jwt_impl = value,
                    "unknown JWT_IMPL value, fallback to jsonwebtoken"
                );
            }
        }
        Self::parse(raw)
    }

    fn parse(raw: Option<String>) -> Self {
        match raw
            .as_deref()
            .map(str::trim)
            .map(str::to_ascii_lowercase)
            .as_deref()
        {
            Some("jwt_simple") | Some("jwt-simple") => Self::JwtSimple,
            Some("jsonwebtoken") | None | Some("") => Self::JsonWebToken,
            Some(_) => Self::JsonWebToken,
        }
    }

    fn as_str(self) -> &'static str {
        match self {
            Self::JsonWebToken => "jsonwebtoken",
            Self::JwtSimple => "jwt_simple",
        }
    }
}

fn parse_legacy_fallback_enabled(raw: Option<String>) -> bool {
    match raw
        .as_deref()
        .map(str::trim)
        .map(str::to_ascii_lowercase)
        .as_deref()
    {
        Some("0") | Some("false") | Some("no") | Some("off") => false,
        Some("1") | Some("true") | Some("yes") | Some("on") | None | Some("") => true,
        Some(_) => true,
    }
}

fn legacy_fallback_enabled_from_env() -> bool {
    let raw = env::var(JWT_LEGACY_FALLBACK_ENABLED_ENV).ok();
    if let Some(value) = raw
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
    {
        let normalized = value.to_ascii_lowercase();
        if !matches!(
            normalized.as_str(),
            "1" | "true" | "yes" | "on" | "0" | "false" | "no" | "off"
        ) {
            warn!(
                legacy_fallback = value,
                "unknown JWT_LEGACY_FALLBACK_ENABLED value, fallback to true"
            );
        }
    }
    parse_legacy_fallback_enabled(raw)
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct UserClaims {
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

impl UserClaims {
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

impl From<UserClaims> for User {
    fn from(value: UserClaims) -> Self {
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
    legacy_fallback_enabled: bool,
    jsonwebtoken: JsonEncodingKey,
    jwt_simple: Ed25519KeyPair,
}

#[allow(unused)]
pub struct DecodingKey {
    implementation: JwtImplementation,
    legacy_fallback_enabled: bool,
    jsonwebtoken: JsonDecodingKey,
    jwt_simple: Ed25519PublicKey,
}

impl EncodingKey {
    pub fn load(pem: &str) -> Result<Self, JwtError> {
        Self::load_with_runtime(
            pem,
            JwtImplementation::from_env(),
            legacy_fallback_enabled_from_env(),
        )
    }

    fn load_with_runtime(
        pem: &str,
        implementation: JwtImplementation,
        legacy_fallback_enabled: bool,
    ) -> Result<Self, JwtError> {
        Ok(Self {
            implementation,
            legacy_fallback_enabled,
            jsonwebtoken: JsonEncodingKey::from_ed_pem(pem.as_bytes())?,
            jwt_simple: Ed25519KeyPair::from_pem(pem)?,
        })
    }

    pub fn runtime_config(&self) -> JwtRuntimeConfig {
        JwtRuntimeConfig {
            implementation: self.implementation.as_str(),
            legacy_fallback_enabled: self.legacy_fallback_enabled,
        }
    }

    pub fn sign(&self, user: impl Into<User>) -> Result<String, JwtError> {
        self.sign_with_audience(user, JWT_AUD, JWT_DURATION)
    }

    pub fn sign_with_audience(
        &self,
        user: impl Into<User>,
        audience: &str,
        ttl_secs: u64,
    ) -> Result<String, JwtError> {
        let user = user.into();
        match self.implementation {
            JwtImplementation::JsonWebToken => {
                let claims = UserClaims::from_user(user, audience, ttl_secs);
                let header = Header::new(Algorithm::EdDSA);
                Ok(encode(&header, &claims, &self.jsonwebtoken)?)
            }
            JwtImplementation::JwtSimple => {
                let claims = Claims::with_custom_claims(user, Duration::from_secs(ttl_secs))
                    .with_issuer(JWT_ISS)
                    .with_audience(audience);
                Ok(self.jwt_simple.sign(claims)?)
            }
        }
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
        self.sign_with_audience(user, JWT_AUD, ttl_secs)
    }
}

impl DecodingKey {
    pub fn load(pem: &str) -> Result<Self, JwtError> {
        Self::load_with_runtime(
            pem,
            JwtImplementation::from_env(),
            legacy_fallback_enabled_from_env(),
        )
    }

    fn load_with_runtime(
        pem: &str,
        implementation: JwtImplementation,
        legacy_fallback_enabled: bool,
    ) -> Result<Self, JwtError> {
        Ok(Self {
            implementation,
            legacy_fallback_enabled,
            jsonwebtoken: JsonDecodingKey::from_ed_pem(pem.as_bytes())?,
            jwt_simple: Ed25519PublicKey::from_pem(pem)?,
        })
    }

    pub fn runtime_config(&self) -> JwtRuntimeConfig {
        JwtRuntimeConfig {
            implementation: self.implementation.as_str(),
            legacy_fallback_enabled: self.legacy_fallback_enabled,
        }
    }

    fn verify_with_jsonwebtoken(&self, token: &str, audience: &str) -> Result<User, JwtError> {
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

        let claims = decode::<UserClaims>(token, &self.jsonwebtoken, &validation)?;
        Ok(claims.claims.into())
    }

    fn verify_with_jwt_simple(&self, token: &str, audience: &str) -> Result<User, JwtError> {
        let opts = VerificationOptions {
            allowed_issuers: Some(HashSet::from_strings(&[JWT_ISS])),
            allowed_audiences: Some(HashSet::from_strings(&[audience])),
            ..Default::default()
        };
        let claims = self.jwt_simple.verify_token::<User>(token, Some(opts))?;
        Ok(claims.custom)
    }

    fn verify_with_audience(&self, token: &str, audience: &str) -> Result<User, JwtError> {
        JWT_VERIFY_METRICS.observe_attempt();
        let result = match self.implementation {
            JwtImplementation::JsonWebToken => match self.verify_with_jsonwebtoken(token, audience)
            {
                Ok(user) => Ok(user),
                Err(JwtError::JsonWebToken(primary_error))
                    if self.legacy_fallback_enabled
                        && should_fallback_to_legacy(&primary_error) =>
                {
                    JWT_VERIFY_METRICS.observe_legacy_fallback_attempt();
                    self.verify_with_jwt_simple(token, audience)
                        .map_err(|_| {
                            JWT_VERIFY_METRICS.observe_legacy_fallback_failure();
                            JwtError::JsonWebToken(primary_error)
                        })
                        .inspect(|_| {
                            JWT_VERIFY_METRICS.observe_legacy_fallback_success();
                        })
                }
                Err(other) => Err(other),
            },
            JwtImplementation::JwtSimple => self.verify_with_jwt_simple(token, audience),
        };

        match &result {
            Ok(_) => JWT_VERIFY_METRICS.observe_success(),
            Err(JwtError::JsonWebToken(err)) => JWT_VERIFY_METRICS.observe_error_jsonwebtoken(err),
            Err(JwtError::JwtSimple(_)) => JWT_VERIFY_METRICS.observe_error_jwt_simple(),
        }

        result
    }

    #[allow(unused)]
    pub fn verify(&self, token: &str) -> Result<User, JwtError> {
        self.verify_with_audience(token, JWT_AUD)
    }

    pub fn verify_file_ticket(&self, token: &str) -> Result<User, JwtError> {
        self.verify_with_audience(token, JWT_AUD_FILE_TICKET)
    }

    pub fn verify_notify_ticket(&self, token: &str) -> Result<User, JwtError> {
        self.verify_with_audience(token, JWT_AUD_NOTIFY_TICKET)
    }
}

fn should_fallback_to_legacy(err: &jsonwebtoken::errors::Error) -> bool {
    matches!(
        err.kind(),
        JsonWebTokenErrorKind::MissingRequiredClaim(_)
            | JsonWebTokenErrorKind::InvalidClaimFormat(_)
            | JsonWebTokenErrorKind::Json(_)
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;
    use serde::Serialize;

    #[derive(Debug, Serialize)]
    struct MissingIatClaims {
        id: i64,
        ws_id: i64,
        ws_name: String,
        fullname: String,
        email: String,
        is_bot: bool,
        created_at: chrono::DateTime<chrono::Utc>,
        iss: String,
        aud: String,
        exp: usize,
        nbf: usize,
    }

    #[derive(Debug, Serialize)]
    struct NumericAudClaims {
        id: i64,
        ws_id: i64,
        ws_name: String,
        fullname: String,
        email: String,
        is_bot: bool,
        created_at: chrono::DateTime<chrono::Utc>,
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
    fn jwt_implementation_parse_should_support_legacy_alias() {
        assert_eq!(
            JwtImplementation::parse(Some("jwt_simple".to_string())),
            JwtImplementation::JwtSimple
        );
        assert_eq!(
            JwtImplementation::parse(Some("jwt-simple".to_string())),
            JwtImplementation::JwtSimple
        );
        assert_eq!(
            JwtImplementation::parse(Some("jsonwebtoken".to_string())),
            JwtImplementation::JsonWebToken
        );
    }

    #[test]
    fn legacy_fallback_parse_should_default_true() {
        assert!(parse_legacy_fallback_enabled(None));
        assert!(parse_legacy_fallback_enabled(Some("".to_string())));
        assert!(parse_legacy_fallback_enabled(Some("unknown".to_string())));
    }

    #[test]
    fn legacy_fallback_parse_should_support_false_aliases() {
        assert!(!parse_legacy_fallback_enabled(Some("0".to_string())));
        assert!(!parse_legacy_fallback_enabled(Some("false".to_string())));
        assert!(!parse_legacy_fallback_enabled(Some("off".to_string())));
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
        assert!(ek.runtime_config().legacy_fallback_enabled);
        assert!(dk.runtime_config().legacy_fallback_enabled);
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
        let token = ek.sign(user.clone())?;
        let user2 = dk.verify(&token)?;

        assert_eq!(user.id, user2.id);
        assert_eq!(user.fullname, user2.fullname);
        assert_eq!(user.email, user2.email);
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
        assert!(dk.verify(&file_token).is_err());
        let file_user = dk.verify_file_ticket(&file_token)?;
        assert_eq!(file_user.id, user.id);

        let notify_token = ek.sign_notify_ticket(user.clone(), 300)?;
        assert!(dk.verify(&notify_token).is_err());
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
        let claims = UserClaims {
            id: user.id,
            ws_id: user.ws_id,
            ws_name: user.ws_name,
            fullname: user.fullname,
            email: user.email,
            is_bot: user.is_bot,
            created_at: user.created_at,
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

        assert!(dk.verify(&token).is_err());
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
        let claims = UserClaims {
            id: user.id,
            ws_id: user.ws_id,
            ws_name: user.ws_name,
            fullname: user.fullname,
            email: user.email,
            is_bot: user.is_bot,
            created_at: user.created_at,
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

        assert!(dk.verify(&token).is_err());
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
            id: user.id,
            ws_id: user.ws_id,
            ws_name: user.ws_name,
            fullname: user.fullname,
            email: user.email,
            is_bot: user.is_bot,
            created_at: user.created_at,
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

        assert!(dk.verify(&token).is_err());
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
            id: user.id,
            ws_id: user.ws_id,
            ws_name: user.ws_name,
            fullname: user.fullname,
            email: user.email,
            is_bot: user.is_bot,
            created_at: user.created_at,
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

        assert!(dk.verify(&token).is_err());
        Ok(())
    }

    #[tokio::test]
    async fn jwt_verify_should_accept_legacy_jwt_simple_token_during_migration() -> Result<()> {
        let _guard = reset_metrics();
        let encoding_pem = include_str!("../../fixtures/encoding.pem");
        let decoding_pem = include_str!("../../fixtures/decoding.pem");
        let dk = DecodingKey::load(decoding_pem)?;
        let user = issue_test_user();
        let legacy_token = Ed25519KeyPair::from_pem(encoding_pem)?.sign(
            Claims::with_custom_claims(user.clone(), Duration::from_secs(300))
                .with_issuer(JWT_ISS)
                .with_audience(JWT_AUD),
        )?;

        let verified = dk.verify(&legacy_token)?;
        assert_eq!(verified.id, user.id);
        Ok(())
    }

    #[tokio::test]
    async fn jwt_metrics_should_capture_legacy_fallback_success() -> Result<()> {
        let _guard = reset_metrics();
        let encoding_pem = include_str!("../../fixtures/encoding.pem");
        let decoding_pem = include_str!("../../fixtures/decoding.pem");
        let dk =
            DecodingKey::load_with_runtime(decoding_pem, JwtImplementation::JsonWebToken, true)?;
        let user = issue_test_user();
        let legacy_token = Ed25519KeyPair::from_pem(encoding_pem)?.sign(
            Claims::with_custom_claims(user.clone(), Duration::from_secs(300))
                .with_issuer(JWT_ISS)
                .with_audience(JWT_AUD),
        )?;

        let verified = dk.verify(&legacy_token)?;
        assert_eq!(verified.id, user.id);
        let snapshot = get_jwt_verify_metrics_snapshot();
        assert_eq!(snapshot.verify_attempt_total, 1);
        assert_eq!(snapshot.verify_success_total, 1);
        assert_eq!(snapshot.verify_error_total, 0);
        assert_eq!(snapshot.legacy_fallback_attempt_total, 1);
        assert_eq!(snapshot.legacy_fallback_success_total, 1);
        assert_eq!(snapshot.legacy_fallback_failure_total, 0);
        Ok(())
    }

    #[tokio::test]
    async fn jwt_metrics_should_capture_invalid_audience_error() -> Result<()> {
        let _guard = reset_metrics();
        let encoding_pem = include_str!("../../fixtures/encoding.pem");
        let decoding_pem = include_str!("../../fixtures/decoding.pem");
        let ek =
            EncodingKey::load_with_runtime(encoding_pem, JwtImplementation::JsonWebToken, true)?;
        let dk =
            DecodingKey::load_with_runtime(decoding_pem, JwtImplementation::JsonWebToken, true)?;
        let user = issue_test_user();

        let file_token = ek.sign_file_ticket(user, 300)?;
        assert!(dk.verify(&file_token).is_err());

        let snapshot = get_jwt_verify_metrics_snapshot();
        assert_eq!(snapshot.verify_attempt_total, 1);
        assert_eq!(snapshot.verify_success_total, 0);
        assert_eq!(snapshot.verify_error_total, 1);
        assert_eq!(snapshot.verify_error_invalid_audience_total, 1);
        Ok(())
    }
}
