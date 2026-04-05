use super::*;
use crate::models::CreateUser;
use anyhow::Result;

async fn create_user(state: &AppState, email: &str) -> Result<chat_core::User> {
    state
        .create_user(&CreateUser {
            fullname: format!("u-{}", uuid::Uuid::new_v4()),
            email: email.to_string(),
            password: "123456".to_string(),
        })
        .await
        .map_err(Into::into)
}

async fn add_participant(
    state: &AppState,
    session_id: i64,
    user_id: i64,
    side: &str,
) -> Result<()> {
    sqlx::query(
        r#"
        INSERT INTO session_participants(session_id, user_id, side)
        VALUES ($1, $2, $3)
        ON CONFLICT DO NOTHING
        "#,
    )
    .bind(session_id)
    .bind(user_id)
    .bind(side)
    .execute(&state.pool)
    .await?;
    Ok(())
}

#[tokio::test]
async fn request_judge_job_should_return_stable_conflict_when_not_participant() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "judging").await?;
    let user = create_user(&state, "judge-non-participant@acme.org").await?;

    let err = state
        .request_judge_job(
            session_id as u64,
            &user,
            RequestJudgeJobInput {
                allow_rejudge: false,
            },
            None,
        )
        .await
        .expect_err("should reject non participant");
    match err {
        AppError::DebateConflict(code) => assert_eq!(code, "judge_request_not_participant"),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn request_judge_job_should_return_reason_no_messages() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "judging").await?;
    let user = create_user(&state, "judge-no-messages@acme.org").await?;
    add_participant(&state, session_id, user.id, "pro").await?;

    let ret = state
        .request_judge_job(
            session_id as u64,
            &user,
            RequestJudgeJobInput {
                allow_rejudge: false,
            },
            None,
        )
        .await?;
    assert_eq!(ret.status, "noop");
    assert_eq!(ret.reason.as_deref(), Some("no_messages"));
    Ok(())
}

#[tokio::test]
async fn request_judge_job_should_replay_by_persistent_idempotency() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "judging").await?;
    let user = create_user(&state, "judge-idem@acme.org").await?;
    add_participant(&state, session_id, user.id, "pro").await?;

    let first = state
        .request_judge_job(
            session_id as u64,
            &user,
            RequestJudgeJobInput {
                allow_rejudge: false,
            },
            Some("judge-idem-k1"),
        )
        .await?;
    let second = state
        .request_judge_job(
            session_id as u64,
            &user,
            RequestJudgeJobInput {
                allow_rejudge: false,
            },
            Some("judge-idem-k1"),
        )
        .await?;

    assert_eq!(first.status, second.status);
    assert_eq!(first.reason, second.reason);
    assert_eq!(first.queued_phase_jobs, second.queued_phase_jobs);
    assert_eq!(first.queued_final_job, second.queued_final_job);

    let row: (String, bool) = sqlx::query_as(
        r#"
        SELECT status, response_snapshot IS NOT NULL
        FROM judge_job_request_idempotency
        WHERE session_id = $1 AND user_id = $2 AND idempotency_key = $3
        "#,
    )
    .bind(session_id)
    .bind(user.id)
    .bind("judge-idem-k1")
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(row.0, "completed");
    assert!(row.1);
    Ok(())
}

#[tokio::test]
async fn request_judge_job_automatically_should_skip_without_participant() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "judging").await?;

    let ret = state
        .request_judge_job_automatically(session_id as u64)
        .await?;
    assert!(ret.is_none());
    Ok(())
}
