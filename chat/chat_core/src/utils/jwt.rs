use crate::User;
use chrono::Utc;
use jsonwebtoken::{
    decode, encode, Algorithm, DecodingKey as JsonDecodingKey, EncodingKey as JsonEncodingKey,
    Header, Validation,
};
use jwt_simple::prelude::*;
use serde::{Deserialize, Serialize};
use std::{collections::HashSet, env};
use thiserror::Error;

const JWT_DURATION: u64 = 60 * 60 * 24 * 7; // 1 week
const JWT_IMPL_ENV: &str = "JWT_IMPL";
pub const JWT_ISS: &str = "chat_server";
pub const JWT_AUD: &str = "chat_web";
pub const JWT_AUD_FILE_TICKET: &str = "chat_file_ticket";
pub const JWT_AUD_NOTIFY_TICKET: &str = "chat_notify_ticket";

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

impl JwtImplementation {
    fn from_env() -> Self {
        Self::parse(env::var(JWT_IMPL_ENV).ok())
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
    jsonwebtoken: JsonEncodingKey,
    jwt_simple: Ed25519KeyPair,
}

#[allow(unused)]
pub struct DecodingKey {
    implementation: JwtImplementation,
    jsonwebtoken: JsonDecodingKey,
    jwt_simple: Ed25519PublicKey,
}

impl EncodingKey {
    pub fn load(pem: &str) -> Result<Self, JwtError> {
        Ok(Self {
            implementation: JwtImplementation::from_env(),
            jsonwebtoken: JsonEncodingKey::from_ed_pem(pem.as_bytes())?,
            jwt_simple: Ed25519KeyPair::from_pem(pem)?,
        })
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
        Ok(Self {
            implementation: JwtImplementation::from_env(),
            jsonwebtoken: JsonDecodingKey::from_ed_pem(pem.as_bytes())?,
            jwt_simple: Ed25519PublicKey::from_pem(pem)?,
        })
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
        match self.implementation {
            JwtImplementation::JsonWebToken => self
                .verify_with_jsonwebtoken(token, audience)
                .or_else(|primary_error| {
                    self.verify_with_jwt_simple(token, audience)
                        .map_err(|_| primary_error)
                }),
            JwtImplementation::JwtSimple => self.verify_with_jwt_simple(token, audience),
        }
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

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;

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

    #[tokio::test]
    async fn jwt_sign_verify_should_work() -> Result<()> {
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
}
