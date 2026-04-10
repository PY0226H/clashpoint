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

async fn seed_final_report_for_session(state: &AppState, session_id: i64) -> Result<()> {
    let final_job_id: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO judge_final_jobs(
            session_id, rejudge_run_no, phase_start_no, phase_end_no,
            status, trace_id, idempotency_key, rubric_version, judge_policy_version,
            topic_domain, dispatch_attempts
        )
        VALUES (
            $1, 1, 1, 1,
            'succeeded', $2, $3, 'v3', 'v3-default',
            'default', 1
        )
        ON CONFLICT (session_id, rejudge_run_no)
        DO UPDATE
        SET status = EXCLUDED.status,
            trace_id = EXCLUDED.trace_id,
            idempotency_key = EXCLUDED.idempotency_key,
            dispatch_attempts = EXCLUDED.dispatch_attempts,
            updated_at = NOW()
        RETURNING id
        "#,
    )
    .bind(session_id)
    .bind(format!("trace-final-report-{session_id}"))
    .bind(format!(
        "judge_final:{session_id}:1:succeeded:v3:v3-default"
    ))
    .fetch_one(&state.pool)
    .await?;

    sqlx::query(
        r#"
        INSERT INTO judge_final_reports(
            final_job_id, session_id, rejudge_run_no, winner, pro_score, con_score, dimension_scores,
            final_rationale, verdict_evidence_refs, phase_rollup_summary, retrieval_snapshot_rollup,
            winner_first, winner_second, rejudge_triggered, needs_draw_vote,
            judge_trace, audit_alerts, error_codes, degradation_level
        )
        VALUES (
            $1, $2, 1, 'pro', 73.0, 70.0, '{"logic":72.0}'::jsonb,
            'ready final rationale', '[]'::jsonb, '[]'::jsonb, '[]'::jsonb,
            'pro', 'con', false, false,
            '{}'::jsonb, '[]'::jsonb, '[]'::jsonb, 0
        )
        ON CONFLICT (session_id, rejudge_run_no)
        DO UPDATE
        SET final_job_id = EXCLUDED.final_job_id,
            winner = EXCLUDED.winner,
            pro_score = EXCLUDED.pro_score,
            con_score = EXCLUDED.con_score,
            dimension_scores = EXCLUDED.dimension_scores,
            final_rationale = EXCLUDED.final_rationale,
            verdict_evidence_refs = EXCLUDED.verdict_evidence_refs,
            phase_rollup_summary = EXCLUDED.phase_rollup_summary,
            retrieval_snapshot_rollup = EXCLUDED.retrieval_snapshot_rollup,
            winner_first = EXCLUDED.winner_first,
            winner_second = EXCLUDED.winner_second,
            rejudge_triggered = EXCLUDED.rejudge_triggered,
            needs_draw_vote = EXCLUDED.needs_draw_vote,
            judge_trace = EXCLUDED.judge_trace,
            audit_alerts = EXCLUDED.audit_alerts,
            error_codes = EXCLUDED.error_codes,
            degradation_level = EXCLUDED.degradation_level,
            updated_at = NOW()
        "#,
    )
    .bind(final_job_id.0)
    .bind(session_id)
    .execute(&state.pool)
    .await?;
    Ok(())
}

async fn seed_messages_for_session(state: &AppState, session_id: i64, count: usize) -> Result<()> {
    for idx in 0..count {
        let side = if idx % 2 == 0 { "pro" } else { "con" };
        sqlx::query(
            r#"
            INSERT INTO session_messages(session_id, user_id, side, content)
            VALUES ($1, $2, $3, $4)
            "#,
        )
        .bind(session_id)
        .bind((idx as i64) + 1)
        .bind(side)
        .bind(format!("rejudge-message-{idx}"))
        .execute(&state.pool)
        .await?;
    }
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

#[tokio::test]
async fn request_judge_rejudge_by_owner_should_require_judge_rejudge_permission() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let user = create_user(&state, "judge-rejudge-no-role@acme.org").await?;

    let err = state
        .request_judge_rejudge_by_owner(1, &user)
        .await
        .expect_err("should reject without judge rejudge permission");
    match err {
        AppError::DebateConflict(code) => {
            assert!(code.contains("ops_permission_denied:judge_rejudge"))
        }
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn request_judge_rejudge_by_owner_should_reject_session_status_not_allowed() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");
    let session_id = seed_topic_and_session(&state, "scheduled").await?;

    let err = state
        .request_judge_rejudge_by_owner(session_id as u64, &owner)
        .await
        .expect_err("scheduled session should be rejected");
    match err {
        AppError::DebateConflict(code) => assert_eq!(code, "judge_request_session_not_allowed"),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn request_judge_rejudge_by_owner_should_require_existing_final_report() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");
    let session_id = seed_topic_and_session(&state, "closed").await?;

    let err = state
        .request_judge_rejudge_by_owner(session_id as u64, &owner)
        .await
        .expect_err("should reject when no final report exists");
    match err {
        AppError::DebateConflict(code) => {
            assert_eq!(code, "judge_request_rejudge_requires_existing_report")
        }
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn request_judge_rejudge_by_owner_should_return_400_for_out_of_range_session_id() -> Result<()>
{
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");
    let overflow_session_id = (i64::MAX as u64).saturating_add(1);

    let err = state
        .request_judge_rejudge_by_owner(overflow_session_id, &owner)
        .await
        .expect_err("out-of-range session id should be rejected");
    match err {
        AppError::DebateError(code) => {
            assert_eq!(code, "ops_judge_rejudge_session_id_out_of_range")
        }
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn request_judge_rejudge_by_owner_should_accept_when_existing_final_report() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");
    let session_id = seed_topic_and_session(&state, "closed").await?;
    seed_final_report_for_session(&state, session_id).await?;

    let out = state
        .request_judge_rejudge_by_owner(session_id as u64, &owner)
        .await?;
    assert!(out.accepted);
    assert_eq!(out.session_id, session_id as u64);
    assert_eq!(out.trigger_mode, "ops_rejudge");
    Ok(())
}

#[tokio::test]
async fn request_judge_rejudge_by_owner_should_create_incremental_run_jobs() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");
    let session_id = seed_topic_and_session(&state, "closed").await?;
    seed_final_report_for_session(&state, session_id).await?;
    seed_messages_for_session(&state, session_id, 2).await?;

    state
        .request_judge_rejudge_by_owner(session_id as u64, &owner)
        .await?;
    sqlx::query(
        r#"
        UPDATE judge_phase_jobs
        SET status = 'succeeded', updated_at = NOW()
        WHERE session_id = $1 AND rejudge_run_no = 2
        "#,
    )
    .bind(session_id)
    .execute(&state.pool)
    .await?;
    let inserted_run2 = state.enqueue_due_judge_final_jobs_once().await?;
    assert_eq!(inserted_run2, 1);

    state
        .request_judge_rejudge_by_owner(session_id as u64, &owner)
        .await?;
    sqlx::query(
        r#"
        UPDATE judge_phase_jobs
        SET status = 'succeeded', updated_at = NOW()
        WHERE session_id = $1 AND rejudge_run_no = 3
        "#,
    )
    .bind(session_id)
    .execute(&state.pool)
    .await?;
    let inserted_run3 = state.enqueue_due_judge_final_jobs_once().await?;
    assert_eq!(inserted_run3, 1);

    let phase_runs: Vec<(i32,)> = sqlx::query_as(
        r#"
        SELECT DISTINCT rejudge_run_no
        FROM judge_phase_jobs
        WHERE session_id = $1
        ORDER BY rejudge_run_no ASC
        "#,
    )
    .bind(session_id)
    .fetch_all(&state.pool)
    .await?;
    assert_eq!(
        phase_runs.into_iter().map(|row| row.0).collect::<Vec<_>>(),
        vec![2, 3]
    );

    let final_runs: Vec<(i32,)> = sqlx::query_as(
        r#"
        SELECT rejudge_run_no
        FROM judge_final_jobs
        WHERE session_id = $1
        ORDER BY rejudge_run_no ASC
        "#,
    )
    .bind(session_id)
    .fetch_all(&state.pool)
    .await?;
    assert_eq!(
        final_runs.into_iter().map(|row| row.0).collect::<Vec<_>>(),
        vec![1, 2, 3]
    );
    Ok(())
}
