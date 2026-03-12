use crate::{AppError, AppState};
use axum::{
    extract::{FromRequestParts, Path, Request, State},
    middleware::Next,
    response::{IntoResponse, Response},
};
use chat_core::User;
use tracing::warn;

pub async fn verify_chat(State(state): State<AppState>, req: Request, next: Next) -> Response {
    let (mut parts, body) = req.into_parts();
    let Path(chat_id) = Path::<u64>::from_request_parts(&mut parts, &state)
        .await
        .unwrap();

    let Some(user) = parts.extensions.get::<User>() else {
        warn!("user not found in request");
        return AppError::NotLoggedIn.into_response();
    };

    if !state
        .is_chat_member(chat_id, user.id as _)
        .await
        .unwrap_or_default()
    {
        let err = AppError::NotChatMemberError {
            user_id: user.id as _,
            chat_id,
        };
        return err.into_response();
    }

    let req = Request::from_parts(parts, body);
    next.run(req).await
}

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;
    use axum::{
        body::Body, http::StatusCode, middleware::from_fn_with_state, routing::get, Router,
    };
    use chat_core::middlewares::verify_token;
    use tower::ServiceExt;

    async fn handler(_req: Request) -> impl IntoResponse {
        (StatusCode::OK, "ok")
    }

    #[tokio::test]
    async fn verify_chat_middleware_should_work() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;

        let user = state.find_user_by_id(1).await?.expect("user should exist");
        let sid = "test-chat-sid";
        let family_id = "test-chat-family";
        let refresh_jti = "test-chat-refresh-jti";
        let access_jti = "test-chat-access-jti";
        sqlx::query(
            r#"
            INSERT INTO auth_refresh_sessions (
                user_id, sid, family_id, current_jti, expires_at, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, NOW() + interval '1 day', NOW(), NOW())
            ON CONFLICT (sid) DO UPDATE
            SET current_jti = EXCLUDED.current_jti,
                family_id = EXCLUDED.family_id,
                revoked_at = NULL,
                revoke_reason = NULL,
                expires_at = EXCLUDED.expires_at,
                updated_at = NOW()
            "#,
        )
        .bind(user.id)
        .bind(sid)
        .bind(family_id)
        .bind(refresh_jti)
        .execute(&state.pool)
        .await?;

        let token = state
            .ek
            .sign_access_token_with_jti(user.id, sid, 0, access_jti, 900)?;

        let app = Router::new()
            .route("/chat/:id/messages", get(handler))
            .layer(from_fn_with_state(state.clone(), verify_chat))
            .layer(from_fn_with_state(state.clone(), verify_token::<AppState>))
            .with_state(state);

        // user in chat
        let req = Request::builder()
            .uri("/chat/1/messages")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.clone().oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::OK);

        // user not in chat
        let req = Request::builder()
            .uri("/chat/5/messages")
            .header("Authorization", format!("Bearer {}", token))
            .body(Body::empty())?;
        let res = app.oneshot(req).await?;
        assert_eq!(res.status(), StatusCode::FORBIDDEN);

        Ok(())
    }
}
