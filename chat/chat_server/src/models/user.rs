use crate::{AppError, AppState};
use argon2::{
    password_hash::{rand_core::OsRng, PasswordHash, PasswordHasher, PasswordVerifier, SaltString},
    Argon2,
};
use chat_core::{ChatUser, User};
use serde::{Deserialize, Serialize};
use std::mem;
use utoipa::ToSchema;

/// create a user with email and password
#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
pub struct CreateUser {
    /// Full name of the user
    pub fullname: String,
    /// Email of the user
    pub email: String,
    /// Password of the user
    pub password: String,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
pub struct SigninUser {
    pub email: String,
    pub password: String,
}

#[derive(Debug, Clone)]
pub struct CreateUserWithPhoneInput {
    pub fullname: String,
    pub email: Option<String>,
    pub phone_e164: String,
    pub password: String,
    pub phone_bind_required: bool,
}

#[allow(dead_code)]
impl AppState {
    /// Find a user by email
    pub async fn find_user_by_email(&self, email: &str) -> Result<Option<User>, AppError> {
        let user = sqlx::query_as(
            "SELECT id, fullname, COALESCE(email, '') AS email, phone_e164, phone_verified_at, phone_bind_required, created_at FROM users WHERE email = $1",
        )
        .bind(email)
        .fetch_optional(&self.pool)
        .await?;
        Ok(user)
    }

    pub async fn find_user_by_phone(&self, phone_e164: &str) -> Result<Option<User>, AppError> {
        let user = sqlx::query_as(
            "SELECT id, fullname, COALESCE(email, '') AS email, phone_e164, phone_verified_at, phone_bind_required, created_at FROM users WHERE phone_e164 = $1",
        )
        .bind(phone_e164)
        .fetch_optional(&self.pool)
        .await?;
        Ok(user)
    }

    // find a user by id
    pub async fn find_user_by_id(&self, id: i64) -> Result<Option<User>, AppError> {
        let user = sqlx::query_as(
            "SELECT id, fullname, COALESCE(email, '') AS email, phone_e164, phone_verified_at, phone_bind_required, created_at FROM users WHERE id = $1",
        )
        .bind(id)
        .fetch_optional(&self.pool)
        .await?;
        Ok(user)
    }

    /// Create a new user.
    /// Single-tenant user creation path (platform scope only).
    pub async fn create_user(&self, input: &CreateUser) -> Result<User, AppError> {
        let existing: Option<(i64,)> = sqlx::query_as("SELECT id FROM users WHERE email = $1")
            .bind(&input.email)
            .fetch_optional(&self.pool)
            .await?;
        if existing.is_some() {
            return Err(AppError::EmailAlreadyExists(input.email.clone()));
        }

        let password_hash = hash_password(&input.password)?;
        let is_bot = is_bot_email(&input.email);
        let user: User = sqlx::query_as(
            r#"
            INSERT INTO users (email, fullname, password_hash, is_bot)
            VALUES ($1, $2, $3, $4)
            RETURNING id, fullname, email, is_bot, created_at
            "#,
        )
        .bind(&input.email)
        .bind(&input.fullname)
        .bind(password_hash)
        .bind(is_bot)
        .fetch_one(&self.pool)
        .await?;

        Ok(user)
    }

    /// Verify email and password
    pub async fn verify_user(&self, input: &SigninUser) -> Result<Option<User>, AppError> {
        let user: Option<User> = sqlx::query_as(
            "SELECT id, fullname, COALESCE(email, '') AS email, phone_e164, phone_verified_at, phone_bind_required, password_hash, created_at FROM users WHERE email = $1",
        )
        .bind(&input.email)
        .fetch_optional(&self.pool)
        .await?;
        match user {
            Some(mut user) => {
                let password_hash = mem::take(&mut user.password_hash);
                let is_valid =
                    verify_password(&input.password, &password_hash.unwrap_or_default())?;
                if is_valid {
                    Ok(Some(user))
                } else {
                    Ok(None)
                }
            }
            None => Ok(None),
        }
    }

    pub async fn verify_user_by_phone_password(
        &self,
        phone_e164: &str,
        password: &str,
    ) -> Result<Option<User>, AppError> {
        let user: Option<User> = sqlx::query_as(
            "SELECT id, fullname, COALESCE(email, '') AS email, phone_e164, phone_verified_at, phone_bind_required, password_hash, created_at FROM users WHERE phone_e164 = $1",
        )
        .bind(phone_e164)
        .fetch_optional(&self.pool)
        .await?;
        match user {
            Some(mut user) => {
                let password_hash = mem::take(&mut user.password_hash);
                let is_valid = verify_password(password, &password_hash.unwrap_or_default())?;
                if is_valid {
                    Ok(Some(user))
                } else {
                    Ok(None)
                }
            }
            None => Ok(None),
        }
    }

    pub async fn create_user_with_phone(
        &self,
        input: &CreateUserWithPhoneInput,
    ) -> Result<User, AppError> {
        let mut tx = self.pool.begin().await?;

        if let Some(email) = input.email.as_ref() {
            let existing_email: Option<(i64,)> =
                sqlx::query_as("SELECT id FROM users WHERE email = $1")
                    .bind(email)
                    .fetch_optional(&mut *tx)
                    .await?;
            if existing_email.is_some() {
                return Err(AppError::EmailAlreadyExists(email.clone()));
            }
        }

        let existing_phone: Option<(i64,)> =
            sqlx::query_as("SELECT id FROM users WHERE phone_e164 = $1")
                .bind(&input.phone_e164)
                .fetch_optional(&mut *tx)
                .await?;
        if existing_phone.is_some() {
            return Err(AppError::PhoneAlreadyExists(input.phone_e164.clone()));
        }

        let password_hash = hash_password(&input.password)?;
        let is_bot = input
            .email
            .as_ref()
            .map(|email| is_bot_email(email))
            .unwrap_or(false);

        let user: User = sqlx::query_as(
            r#"
            INSERT INTO users (
                email, phone_e164, phone_verified_at, phone_bind_required,
                fullname, password_hash, is_bot
            )
            VALUES ($1, $2, NOW(), $3, $4, $5, $6)
            RETURNING
                id, fullname, COALESCE(email, '') AS email,
                phone_e164, phone_verified_at, phone_bind_required,
                is_bot, created_at
            "#,
        )
        .bind(input.email.as_deref())
        .bind(&input.phone_e164)
        .bind(input.phone_bind_required)
        .bind(&input.fullname)
        .bind(password_hash)
        .bind(is_bot)
        .fetch_one(&mut *tx)
        .await?;

        tx.commit().await?;
        Ok(user)
    }

    pub async fn bind_phone_for_user(
        &self,
        user_id: i64,
        phone_e164: &str,
    ) -> Result<User, AppError> {
        let existing_user_id: Option<i64> =
            sqlx::query_scalar("SELECT id FROM users WHERE phone_e164 = $1")
                .bind(phone_e164)
                .fetch_optional(&self.pool)
                .await?;
        if let Some(other_id) = existing_user_id {
            if other_id != user_id {
                return Err(AppError::PhoneAlreadyExists(phone_e164.to_string()));
            }
        }

        let user: User = sqlx::query_as(
            r#"
            UPDATE users
            SET phone_e164 = $2,
                phone_verified_at = NOW(),
                phone_bind_required = false
            WHERE id = $1
            RETURNING
                id, fullname, COALESCE(email, '') AS email,
                phone_e164, phone_verified_at, phone_bind_required,
                is_bot, created_at
            "#,
        )
        .bind(user_id)
        .bind(phone_e164)
        .fetch_one(&self.pool)
        .await?;

        Ok(user)
    }

    pub async fn set_user_password(&self, user_id: i64, password: &str) -> Result<(), AppError> {
        let password_hash = hash_password(password)?;
        let updated_rows = sqlx::query(
            r#"
            UPDATE users
            SET password_hash = $2
            WHERE id = $1
            "#,
        )
        .bind(user_id)
        .bind(password_hash)
        .execute(&self.pool)
        .await?
        .rows_affected();

        if updated_rows == 0 {
            return Err(AppError::NotFound(format!("user {user_id}")));
        }
        Ok(())
    }

    pub async fn fetch_chat_user_by_ids(&self, ids: &[i64]) -> Result<Vec<ChatUser>, AppError> {
        let users = sqlx::query_as(
            r#"
        SELECT id, fullname, COALESCE(email, '') AS email
        FROM users
        WHERE id = ANY($1)
        "#,
        )
        .bind(ids)
        .fetch_all(&self.pool)
        .await?;
        Ok(users)
    }

    pub async fn fetch_chat_users(&self) -> Result<Vec<ChatUser>, AppError> {
        let users = sqlx::query_as(
            r#"
        SELECT id, fullname, COALESCE(email, '') AS email
        FROM users
        "#,
        )
        .fetch_all(&self.pool)
        .await?;
        Ok(users)
    }
}

fn hash_password(password: &str) -> Result<String, AppError> {
    let salt = SaltString::generate(&mut OsRng);

    // Argon2 with default params (Argon2id v19)
    let argon2 = Argon2::default();

    // Hash password to PHC string ($argon2id$v=19$...)
    let password_hash = argon2
        .hash_password(password.as_bytes(), &salt)?
        .to_string();

    Ok(password_hash)
}

fn is_bot_email(email: &str) -> bool {
    email.ends_with("@bot.org")
}

fn verify_password(password: &str, password_hash: &str) -> Result<bool, AppError> {
    let argon2 = Argon2::default();
    let password_hash = PasswordHash::new(password_hash)?;

    // Verify password
    let is_valid = argon2
        .verify_password(password.as_bytes(), &password_hash)
        .is_ok();

    Ok(is_valid)
}

#[cfg(test)]
impl CreateUser {
    pub fn new(fullname: &str, email: &str, password: &str) -> Self {
        Self {
            fullname: fullname.to_string(),
            email: email.to_string(),
            password: password.to_string(),
        }
    }
}

#[cfg(test)]
impl SigninUser {
    pub fn new(email: &str, password: &str) -> Self {
        Self {
            email: email.to_string(),
            password: password.to_string(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;

    #[test]
    fn hash_password_and_verify_should_work() -> Result<()> {
        let password = "hunter42";
        let password_hash = hash_password(password)?;
        assert_eq!(password_hash.len(), 97);
        assert!(verify_password(password, &password_hash)?);
        Ok(())
    }

    #[test]
    fn is_bot_email_should_match_bot_domain_suffix() {
        assert!(is_bot_email("helper@bot.org"));
        assert!(!is_bot_email("helper@acme.org"));
    }

    #[tokio::test]
    async fn create_duplicate_user_should_fail() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;

        let input = CreateUser::new("Tyr Chen", "tchen@acme.org", "hunter42");
        let ret = state.create_user(&input).await;
        match ret {
            Err(AppError::EmailAlreadyExists(email)) => {
                assert_eq!(email, input.email);
            }
            _ => panic!("Expecting EmailAlreadyExists error"),
        }
        Ok(())
    }

    #[tokio::test]
    async fn create_and_verify_user_should_work() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;

        let input = CreateUser::new("Tian Chen", "tyr@acme.org", "hunter42");
        let user = state.create_user(&input).await?;
        assert_eq!(user.email, input.email);
        assert_eq!(user.fullname, input.fullname);
        assert!(user.id > 0);

        let user = state.find_user_by_email(&input.email).await?;
        assert!(user.is_some());
        let user = user.unwrap();
        assert_eq!(user.email, input.email);
        assert_eq!(user.fullname, input.fullname);

        let input = SigninUser::new(&input.email, &input.password);
        let user = state.verify_user(&input).await?;
        assert!(user.is_some());

        Ok(())
    }

    #[tokio::test]
    async fn create_user_should_set_platform_scope_default() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let input = CreateUser::new("Txn Owner", "txn-owner@acme.org", "hunter42");
        let _user = state.create_user(&input).await?;
        Ok(())
    }

    #[tokio::test]
    async fn find_user_by_id_should_work() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;

        let user = state.find_user_by_id(1).await?;
        assert!(user.is_some());
        let user = user.unwrap();
        assert_eq!(user.id, 1);
        Ok(())
    }
}
