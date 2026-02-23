use crate::{AppError, AppState};
use axum::{extract::State, http::StatusCode, response::IntoResponse, Extension, Json};
use chat_core::User;
use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

const ACCESS_TICKET_TTL_SECS: u64 = 60 * 10;

#[derive(Debug, Serialize, ToSchema, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AccessTicketsOutput {
    file_token: String,
    notify_token: String,
    expires_in_secs: u64,
}

#[utoipa::path(
    post,
    path = "/api/tickets",
    responses(
        (status = 200, description = "Issue short-lived access tickets", body = AccessTicketsOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn create_access_tickets_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let file_token = state
        .ek
        .sign_file_ticket(user.clone(), ACCESS_TICKET_TTL_SECS)?;
    let notify_token = state.ek.sign_notify_ticket(user, ACCESS_TICKET_TTL_SECS)?;
    Ok((
        StatusCode::OK,
        Json(AccessTicketsOutput {
            file_token,
            notify_token,
            expires_in_secs: ACCESS_TICKET_TTL_SECS,
        }),
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;
    use http_body_util::BodyExt;
    use std::path::PathBuf;

    fn test_state() -> Result<AppState> {
        let config = crate::AppConfig {
            server: crate::config::ServerConfig {
                port: 0,
                db_url: "postgres://localhost:5432/chat".to_string(),
                base_dir: PathBuf::from("/tmp/chat"),
            },
            auth: crate::config::AuthConfig {
                sk: include_str!("../../../chat_core/fixtures/encoding.pem").to_string(),
                pk: include_str!("../../../chat_core/fixtures/decoding.pem").to_string(),
            },
        };
        Ok(AppState::new_for_unit_test(config)?)
    }

    #[tokio::test]
    async fn create_access_tickets_should_return_audience_scoped_tickets() -> Result<()> {
        let state = test_state()?;
        let mut user = chat_core::User::new(1, "Tyr Chen", "tchen@acme.org");
        user.ws_id = 1;
        user.ws_name = "acme".to_string();

        let response = create_access_tickets_handler(Extension(user.clone()), State(state.clone()))
            .await?
            .into_response();
        assert_eq!(response.status(), StatusCode::OK);
        let body = response.into_body().collect().await?.to_bytes();
        let ret: AccessTicketsOutput = serde_json::from_slice(&body)?;

        assert_eq!(ret.expires_in_secs, ACCESS_TICKET_TTL_SECS);
        assert!(state.dk.verify(&ret.file_token).is_err());
        assert!(state.dk.verify(&ret.notify_token).is_err());
        assert_eq!(state.dk.verify_file_ticket(&ret.file_token)?.id, user.id);
        assert_eq!(
            state.dk.verify_notify_ticket(&ret.notify_token)?.id,
            user.id
        );
        Ok(())
    }
}
