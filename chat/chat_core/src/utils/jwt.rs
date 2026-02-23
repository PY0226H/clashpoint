use crate::User;
use jwt_simple::prelude::*;

const JWT_DURATION: u64 = 60 * 60 * 24 * 7; // 1 week
pub const JWT_ISS: &str = "chat_server";
pub const JWT_AUD: &str = "chat_web";
pub const JWT_AUD_FILE_TICKET: &str = "chat_file_ticket";
pub const JWT_AUD_NOTIFY_TICKET: &str = "chat_notify_ticket";

pub struct EncodingKey(Ed25519KeyPair);

#[allow(unused)]
pub struct DecodingKey(Ed25519PublicKey);

impl EncodingKey {
    pub fn load(pem: &str) -> Result<Self, jwt_simple::Error> {
        Ok(Self(Ed25519KeyPair::from_pem(pem)?))
    }

    pub fn sign(&self, user: impl Into<User>) -> Result<String, jwt_simple::Error> {
        self.sign_with_audience(user, JWT_AUD, JWT_DURATION)
    }

    pub fn sign_with_audience(
        &self,
        user: impl Into<User>,
        audience: &str,
        ttl_secs: u64,
    ) -> Result<String, jwt_simple::Error> {
        let claims = Claims::with_custom_claims(user.into(), Duration::from_secs(ttl_secs));
        let claims = claims.with_issuer(JWT_ISS).with_audience(audience);
        self.0.sign(claims)
    }

    pub fn sign_file_ticket(
        &self,
        user: impl Into<User>,
        ttl_secs: u64,
    ) -> Result<String, jwt_simple::Error> {
        self.sign_with_audience(user, JWT_AUD_FILE_TICKET, ttl_secs)
    }

    pub fn sign_notify_ticket(
        &self,
        user: impl Into<User>,
        ttl_secs: u64,
    ) -> Result<String, jwt_simple::Error> {
        self.sign_with_audience(user, JWT_AUD_NOTIFY_TICKET, ttl_secs)
    }

    pub fn sign_short_lived(
        &self,
        user: impl Into<User>,
        ttl_secs: u64,
    ) -> Result<String, jwt_simple::Error> {
        self.sign_with_audience(user, JWT_AUD, ttl_secs)
    }
}

impl DecodingKey {
    pub fn load(pem: &str) -> Result<Self, jwt_simple::Error> {
        Ok(Self(Ed25519PublicKey::from_pem(pem)?))
    }

    fn verify_with_audience(&self, token: &str, audience: &str) -> Result<User, jwt_simple::Error> {
        let opts = VerificationOptions {
            allowed_issuers: Some(HashSet::from_strings(&[JWT_ISS])),
            allowed_audiences: Some(HashSet::from_strings(&[audience])),
            // use default time tolerance which is 15 minutes
            // time_tolerance: Some(Duration::from_secs(10)),
            ..Default::default()
        };

        let claims = self.0.verify_token::<User>(token, Some(opts))?;
        Ok(claims.custom)
    }

    #[allow(unused)]
    pub fn verify(&self, token: &str) -> Result<User, jwt_simple::Error> {
        self.verify_with_audience(token, JWT_AUD)
    }

    pub fn verify_file_ticket(&self, token: &str) -> Result<User, jwt_simple::Error> {
        self.verify_with_audience(token, JWT_AUD_FILE_TICKET)
    }

    pub fn verify_notify_ticket(&self, token: &str) -> Result<User, jwt_simple::Error> {
        self.verify_with_audience(token, JWT_AUD_NOTIFY_TICKET)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;

    #[tokio::test]
    async fn jwt_sign_verify_should_work() -> Result<()> {
        let encoding_pem = include_str!("../../fixtures/encoding.pem");
        let decoding_pem = include_str!("../../fixtures/decoding.pem");
        let ek = EncodingKey::load(encoding_pem)?;
        let dk = DecodingKey::load(decoding_pem)?;

        let user = User::new(1, "Tyr Chen", "tchen@acme.org");

        let token = ek.sign(user.clone())?;
        let user2 = dk.verify(&token)?;

        assert_eq!(user, user2);
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
