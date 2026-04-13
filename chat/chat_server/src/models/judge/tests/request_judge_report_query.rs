use super::*;
use crate::models::UpsertOpsRoleInput;
use anyhow::{Context, Result};
use chrono::{Duration, Utc};
use serde_json::json;

const JUDGE_REPORT_READ_FORBIDDEN: &str = "judge_report_read_forbidden";

async fn find_user(state: &AppState, user_id: i64) -> Result<chat_core::User> {
    state
        .find_user_by_id(user_id)
        .await?
        .with_context(|| format!("seeded user {user_id} should exist"))
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

async fn seed_messages(state: &AppState, session_id: i64, count: i64) -> Result<Vec<i64>> {
    for idx in 0..count {
        let side = if idx % 2 == 0 { "pro" } else { "con" };
        sqlx::query(
            r#"
            INSERT INTO session_messages(session_id, user_id, side, content)
            VALUES ($1, 1, $2, $3)
            "#,
        )
        .bind(session_id)
        .bind(side)
        .bind(format!("judge-report-phase-msg-{idx}"))
        .execute(&state.pool)
        .await?;
    }

    let rows: Vec<(i64,)> = sqlx::query_as(
        r#"
        SELECT id
        FROM session_messages
        WHERE session_id = $1
        ORDER BY id ASC
        "#,
    )
    .bind(session_id)
    .fetch_all(&state.pool)
    .await?;
    Ok(rows.into_iter().map(|row| row.0).collect())
}

async fn seed_failed_phase_job(state: &AppState, session_id: i64) -> Result<i64> {
    let message_ids = seed_messages(state, session_id, 2).await?;
    let row: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO judge_phase_jobs(
            session_id, rejudge_run_no, phase_no, message_start_id, message_end_id, message_count,
            status, trace_id, idempotency_key, rubric_version, judge_policy_version,
            topic_domain, retrieval_profile, dispatch_attempts, last_dispatch_at, error_message
        )
        VALUES (
            $1, 1, 1, $2, $3, 2,
            'failed', $4, $5, 'v3', 'v3-default',
            'default', 'hybrid_v1', 2, NOW(), $6
        )
        RETURNING id
        "#,
    )
    .bind(session_id)
    .bind(message_ids[0])
    .bind(message_ids[1])
    .bind(format!("trace-phase-failed-{session_id}"))
    .bind(format!("judge_phase:{session_id}:1:1:v3:v3-default"))
    .bind("[phase_artifact_incomplete] phase report mismatch")
    .fetch_one(&state.pool)
    .await?;
    Ok(row.0)
}

async fn upsert_final_job(
    state: &AppState,
    session_id: i64,
    status: &str,
    error_message: Option<&str>,
    error_code: Option<&str>,
    contract_failure_type: Option<&str>,
) -> Result<i64> {
    let row: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO judge_final_jobs(
            session_id, rejudge_run_no, phase_start_no, phase_end_no,
            status, trace_id, idempotency_key, rubric_version, judge_policy_version,
            topic_domain, dispatch_attempts, last_dispatch_at,
            error_message, error_code, contract_failure_type
        )
        VALUES (
            $1, 1, 1, 3,
            $2, $3, $4, 'v3', 'v3-default',
            'default', 2, NOW(),
            $5, $6, $7
        )
        ON CONFLICT (session_id, rejudge_run_no)
        DO UPDATE
        SET status = EXCLUDED.status,
            trace_id = EXCLUDED.trace_id,
            idempotency_key = EXCLUDED.idempotency_key,
            dispatch_attempts = EXCLUDED.dispatch_attempts,
            last_dispatch_at = EXCLUDED.last_dispatch_at,
            error_message = EXCLUDED.error_message,
            error_code = EXCLUDED.error_code,
            contract_failure_type = EXCLUDED.contract_failure_type,
            updated_at = NOW()
        RETURNING id
        "#,
    )
    .bind(session_id)
    .bind(status)
    .bind(format!("trace-final-{session_id}-{status}"))
    .bind(format!("judge_final:{session_id}:1:{status}:v3:v3-default"))
    .bind(error_message)
    .bind(error_code)
    .bind(contract_failure_type)
    .fetch_one(&state.pool)
    .await?;
    Ok(row.0)
}

async fn upsert_final_report(
    state: &AppState,
    session_id: i64,
    final_job_id: i64,
    winner: &str,
) -> Result<i64> {
    let row: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO judge_final_reports(
            final_job_id, session_id, rejudge_run_no, winner, pro_score, con_score, dimension_scores,
            debate_summary, side_analysis, verdict_reason, verdict_evidence_refs, phase_rollup_summary, retrieval_snapshot_rollup,
            winner_first, winner_second, rejudge_triggered, needs_draw_vote,
            judge_trace, audit_alerts, error_codes, degradation_level
        )
        VALUES (
            $1, $2, 1, $3, 73.0, 70.0, '{"logic": 72.0}'::jsonb,
            'ready final rationale', '{"pro":"pro analysis","con":"con analysis"}'::jsonb, 'verdict reason', '[]'::jsonb, '[]'::jsonb, '[]'::jsonb,
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
            debate_summary = EXCLUDED.debate_summary,
            side_analysis = EXCLUDED.side_analysis,
            verdict_reason = EXCLUDED.verdict_reason,
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
        RETURNING id
        "#,
    )
    .bind(final_job_id)
    .bind(session_id)
    .bind(winner)
    .fetch_one(&state.pool)
    .await?;
    Ok(row.0)
}

#[derive(Debug, Clone)]
struct OpsReviewSeedInput {
    winner: &'static str,
    pro_score: i32,
    con_score: i32,
    verdict_evidence_count: u32,
    needs_draw_vote: bool,
    winner_first: Option<&'static str>,
    winner_second: Option<&'static str>,
    rejudge_triggered: bool,
    created_at: chrono::DateTime<Utc>,
}

fn default_ops_review_query() -> ListJudgeReviewOpsQuery {
    ListJudgeReviewOpsQuery {
        from: None,
        to: None,
        winner: None,
        rejudge_triggered: None,
        has_verdict_evidence: None,
        anomaly_only: false,
        limit: Some(50),
    }
}

fn default_failure_stats_query() -> GetJudgeFinalDispatchFailureStatsQuery {
    GetJudgeFinalDispatchFailureStatsQuery {
        from: None,
        to: None,
        limit: Some(500),
    }
}

fn default_trace_replay_query() -> ListJudgeTraceReplayOpsQuery {
    ListJudgeTraceReplayOpsQuery {
        from: None,
        to: None,
        session_id: None,
        scope: None,
        status: None,
        limit: Some(100),
    }
}

fn default_replay_actions_query() -> ListJudgeReplayActionsOpsQuery {
    ListJudgeReplayActionsOpsQuery {
        from: None,
        to: None,
        scope: None,
        session_id: None,
        job_id: None,
        requested_by: None,
        previous_status: None,
        new_status: None,
        reason_keyword: None,
        trace_keyword: None,
        limit: Some(50),
        offset: Some(0),
    }
}

fn replay_preview_query(scope: &str, job_id: u64) -> GetJudgeReplayPreviewOpsQuery {
    GetJudgeReplayPreviewOpsQuery {
        scope: scope.to_string(),
        job_id,
    }
}

fn replay_execute_input(
    scope: &str,
    job_id: u64,
    reason: Option<String>,
) -> ExecuteJudgeReplayOpsInput {
    ExecuteJudgeReplayOpsInput {
        scope: scope.to_string(),
        job_id,
        reason,
    }
}

async fn insert_phase_report_for_job(state: &AppState, phase_job_id: i64) -> Result<i64> {
    let (session_id, rejudge_run_no, phase_no, message_start_id, message_end_id, message_count): (
        i64,
        i32,
        i32,
        i64,
        i64,
        i32,
    ) = sqlx::query_as(
        r#"
        SELECT
            session_id,
            rejudge_run_no,
            phase_no,
            message_start_id,
            message_end_id,
            message_count
        FROM judge_phase_jobs
        WHERE id = $1
        "#,
    )
    .bind(phase_job_id)
    .fetch_one(&state.pool)
    .await?;

    let row: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO judge_phase_reports(
            phase_job_id,
            session_id,
            rejudge_run_no,
            phase_no,
            message_start_id,
            message_end_id,
            message_count,
            pro_summary_grounded,
            con_summary_grounded,
            pro_retrieval_bundle,
            con_retrieval_bundle,
            agent1_score,
            agent2_score,
            agent3_weighted_score,
            prompt_hashes,
            token_usage,
            latency_ms,
            error_codes,
            degradation_level,
            judge_trace,
            created_at,
            updated_at
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7,
            $8, $9, $10, $11,
            $12, $13, $14,
            $15, $16, $17, $18,
            $19, $20, NOW(), NOW()
        )
        RETURNING id
        "#,
    )
    .bind(phase_job_id)
    .bind(session_id)
    .bind(rejudge_run_no)
    .bind(phase_no)
    .bind(message_start_id)
    .bind(message_end_id)
    .bind(message_count)
    .bind(json!([{"side": "pro", "summary": "summary"}]))
    .bind(json!([{"side": "con", "summary": "summary"}]))
    .bind(json!([]))
    .bind(json!([]))
    .bind(json!({"pro": 72.0}))
    .bind(json!({"con": 68.0}))
    .bind(json!({"pro": 0.52, "con": 0.48}))
    .bind(json!({"system": "prompt-hash"}))
    .bind(json!({"input": 1, "output": 1}))
    .bind(json!({"total": 1}))
    .bind(json!([]))
    .bind(0_i32)
    .bind(json!({"trace": "ok"}))
    .fetch_one(&state.pool)
    .await?;
    Ok(row.0)
}

async fn seed_failed_final_job_for_stats(
    state: &AppState,
    created_at: chrono::DateTime<Utc>,
    error_message: Option<&str>,
    error_code: Option<&str>,
    contract_failure_type: Option<&str>,
) -> Result<i64> {
    let session_id = seed_topic_and_session(state, "judging").await?;
    let final_job_id = upsert_final_job(
        state,
        session_id,
        "failed",
        error_message,
        error_code,
        contract_failure_type,
    )
    .await?;
    sqlx::query(
        r#"
        UPDATE judge_final_jobs
        SET created_at = $1, updated_at = $1
        WHERE id = $2
        "#,
    )
    .bind(created_at)
    .bind(final_job_id)
    .execute(&state.pool)
    .await?;
    Ok(final_job_id)
}

async fn seed_phase_job_for_trace_replay(
    state: &AppState,
    created_at: chrono::DateTime<Utc>,
    status: &str,
    error_message: Option<&str>,
) -> Result<(i64, i64)> {
    let session_id = seed_topic_and_session(state, "judging").await?;
    let message_ids = seed_messages(state, session_id, 2).await?;
    let row: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO judge_phase_jobs(
            session_id, rejudge_run_no, phase_no, message_start_id, message_end_id, message_count,
            status, trace_id, idempotency_key, rubric_version, judge_policy_version,
            topic_domain, retrieval_profile, dispatch_attempts, last_dispatch_at, error_message
        )
        VALUES (
            $1, 1, 1, $2, $3, 2,
            $4, $5, $6, 'v3', 'v3-default',
            'default', 'hybrid_v1', 2, $7, $8
        )
        RETURNING id
        "#,
    )
    .bind(session_id)
    .bind(message_ids[0])
    .bind(message_ids[1])
    .bind(status)
    .bind(format!("trace-phase-{session_id}-{status}"))
    .bind(format!("judge_phase:{session_id}:1:{status}:v3:v3-default"))
    .bind(created_at)
    .bind(error_message)
    .fetch_one(&state.pool)
    .await?;
    let phase_job_id = row.0;
    sqlx::query(
        r#"
        UPDATE judge_phase_jobs
        SET created_at = $1, updated_at = $1
        WHERE id = $2
        "#,
    )
    .bind(created_at)
    .bind(phase_job_id)
    .execute(&state.pool)
    .await?;
    Ok((session_id, phase_job_id))
}

async fn seed_final_job_for_trace_replay(
    state: &AppState,
    created_at: chrono::DateTime<Utc>,
    status: &str,
    error_message: Option<&str>,
    error_code: Option<&str>,
    contract_failure_type: Option<&str>,
) -> Result<(i64, i64)> {
    let session_id = seed_topic_and_session(state, "judging").await?;
    let final_job_id = upsert_final_job(
        state,
        session_id,
        status,
        error_message,
        error_code,
        contract_failure_type,
    )
    .await?;
    sqlx::query(
        r#"
        UPDATE judge_final_jobs
        SET created_at = $1, updated_at = $1
        WHERE id = $2
        "#,
    )
    .bind(created_at)
    .bind(final_job_id)
    .execute(&state.pool)
    .await?;
    Ok((session_id, final_job_id))
}

async fn seed_replay_action_for_trace_replay(
    state: &AppState,
    scope: &str,
    job_id: i64,
    session_id: i64,
    created_at: chrono::DateTime<Utc>,
    reason: Option<&str>,
) -> Result<i64> {
    let row: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO judge_replay_actions(
            scope, job_id, session_id, requested_by, reason,
            previous_status, new_status,
            previous_trace_id, new_trace_id,
            previous_idempotency_key, new_idempotency_key,
            created_at
        )
        VALUES (
            $1, $2, $3, 1, $4,
            'failed', 'queued',
            $5, $6,
            $7, $8,
            $9
        )
        RETURNING id
        "#,
    )
    .bind(scope)
    .bind(job_id)
    .bind(session_id)
    .bind(reason)
    .bind(format!("prev-trace-{scope}-{job_id}"))
    .bind(format!("new-trace-{scope}-{job_id}"))
    .bind(format!("prev-idemp-{scope}-{job_id}"))
    .bind(format!("new-idemp-{scope}-{job_id}"))
    .bind(created_at)
    .fetch_one(&state.pool)
    .await?;
    Ok(row.0)
}

async fn seed_ops_review_case(state: &AppState, input: OpsReviewSeedInput) -> Result<u64> {
    let session_id = seed_topic_and_session(state, "judging").await?;
    let final_job_id = upsert_final_job(state, session_id, "succeeded", None, None, None).await?;
    let report_id = upsert_final_report(state, session_id, final_job_id, input.winner).await?;
    let verdict_evidence_refs = (0..input.verdict_evidence_count)
        .map(|idx| json!({"id": format!("evidence-{session_id}-{idx}")}))
        .collect::<Vec<_>>();
    sqlx::query(
        r#"
        UPDATE judge_final_reports
        SET pro_score = $1,
            con_score = $2,
            winner_first = $3,
            winner_second = $4,
            rejudge_triggered = $5,
            needs_draw_vote = $6,
            verdict_evidence_refs = $7::jsonb,
            created_at = $8,
            updated_at = $8
        WHERE id = $9
        "#,
    )
    .bind(input.pro_score as f64)
    .bind(input.con_score as f64)
    .bind(input.winner_first)
    .bind(input.winner_second)
    .bind(input.rejudge_triggered)
    .bind(input.needs_draw_vote)
    .bind(json!(verdict_evidence_refs))
    .bind(input.created_at)
    .bind(report_id)
    .execute(&state.pool)
    .await?;
    Ok(report_id as u64)
}

#[tokio::test]
async fn get_latest_judge_report_should_forbid_non_participant_non_ops() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "judging").await?;
    let outsider = find_user(&state, 2).await?;

    let err = state
        .get_latest_judge_report(session_id as u64, &outsider, None)
        .await
        .expect_err("non participant should be forbidden");
    match err {
        AppError::DebateConflict(code) => assert_eq!(code, JUDGE_REPORT_READ_FORBIDDEN),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn get_latest_judge_report_should_allow_ops_viewer_non_participant() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "judging").await?;
    state.grant_platform_admin(1).await?;
    let owner = find_user(&state, 1).await?;
    let ops_viewer = find_user(&state, 2).await?;
    state
        .upsert_ops_role_assignment_by_owner(
            &owner,
            ops_viewer.id as u64,
            UpsertOpsRoleInput {
                role: "ops_viewer".to_string(),
            },
        )
        .await?;

    let out = state
        .get_latest_judge_report(session_id as u64, &ops_viewer, None)
        .await?;
    assert_eq!(out.status, "absent");
    assert_eq!(out.status_reason, "no_judge_jobs");
    Ok(())
}

#[tokio::test]
async fn get_latest_judge_report_should_return_blocked_when_phase_failed_without_final(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "judging").await?;
    let participant = find_user(&state, 2).await?;
    add_participant(&state, session_id, participant.id, "pro").await?;
    seed_failed_phase_job(&state, session_id).await?;

    let out = state
        .get_latest_judge_report(session_id as u64, &participant, None)
        .await?;
    assert_eq!(out.status, "blocked");
    assert_eq!(out.status_reason, "phase_failed_waiting_replay");
    assert_eq!(out.progress.total_phase_jobs, 1);
    assert_eq!(out.progress.failed_phase_jobs, 1);
    assert!(!out.progress.has_final_job);
    Ok(())
}

#[tokio::test]
async fn get_latest_judge_report_should_return_degraded_with_structured_final_failure() -> Result<()>
{
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "judging").await?;
    let participant = find_user(&state, 2).await?;
    add_participant(&state, session_id, participant.id, "pro").await?;
    upsert_final_job(
        &state,
        session_id,
        "failed",
        Some("[response_accepted_false] accepted=false"),
        Some("response_accepted_false"),
        Some("response_accepted_false"),
    )
    .await?;

    let out = state
        .get_latest_judge_report(session_id as u64, &participant, None)
        .await?;
    assert_eq!(out.status, "degraded");
    assert_eq!(out.status_reason, "final_dispatch_failed");
    let latest_final_job = out
        .latest_final_job
        .as_ref()
        .expect("latest final job should exist");
    assert_eq!(
        latest_final_job.error_code.as_deref(),
        Some("response_accepted_false")
    );
    let diagnostics = out
        .final_dispatch_diagnostics
        .as_ref()
        .expect("diagnostics should exist");
    assert_eq!(
        diagnostics.contract_failure_type.as_deref(),
        Some("response_accepted_false")
    );
    Ok(())
}

#[tokio::test]
async fn judge_report_overview_and_final_detail_should_be_consistent_when_ready() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "judging").await?;
    let participant = find_user(&state, 2).await?;
    add_participant(&state, session_id, participant.id, "pro").await?;
    let final_job_id = upsert_final_job(&state, session_id, "succeeded", None, None, None).await?;
    let final_report_id = upsert_final_report(&state, session_id, final_job_id, "pro").await?;

    let overview = state
        .get_latest_judge_report(session_id as u64, &participant, None)
        .await?;
    assert_eq!(overview.status, "ready");
    assert_eq!(overview.status_reason, "final_report_ready");
    assert!(overview.progress.has_final_job);
    assert!(overview.progress.has_final_report);
    let summary = overview
        .final_report_summary
        .as_ref()
        .expect("final report summary should exist");
    assert_eq!(summary.final_report_id, final_report_id as u64);
    assert_eq!(summary.winner, "pro");

    let detail = state
        .get_latest_judge_final_report(session_id as u64, &participant, None)
        .await?;
    let final_report = detail
        .final_report
        .as_ref()
        .expect("final report detail should exist");
    assert_eq!(final_report.final_report_id, final_report_id as u64);
    assert_eq!(final_report.final_job_id, final_job_id as u64);
    assert_eq!(final_report.winner, "pro");
    assert_eq!(final_report.dimension_scores, json!({"logic": 72.0}));
    Ok(())
}

#[tokio::test]
async fn get_latest_judge_report_should_support_explicit_rejudge_run_no() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;
    let participant = find_user(&state, 2).await?;
    let session_id = seed_topic_and_session(&state, "closed").await?;
    add_participant(&state, session_id, participant.id, "pro").await?;
    seed_messages(&state, session_id, 2).await?;

    let final_job_id = upsert_final_job(&state, session_id, "succeeded", None, None, None).await?;
    let final_report_id = upsert_final_report(&state, session_id, final_job_id, "pro").await?;

    state
        .request_judge_rejudge_by_owner(session_id as u64, &owner)
        .await?;

    let latest = state
        .get_latest_judge_report(session_id as u64, &participant, None)
        .await?;
    assert_eq!(latest.status, "pending");
    assert!(latest.final_report_summary.is_none());

    let run1 = state
        .get_latest_judge_report(session_id as u64, &participant, Some(1))
        .await?;
    assert_eq!(run1.status, "ready");
    assert_eq!(
        run1.final_report_summary
            .as_ref()
            .map(|summary| summary.final_report_id),
        Some(final_report_id as u64)
    );

    let run1_final = state
        .get_latest_judge_final_report(session_id as u64, &participant, Some(1))
        .await?;
    assert_eq!(
        run1_final
            .final_report
            .as_ref()
            .map(|report| report.final_job_id),
        Some(final_job_id as u64)
    );

    let run2_final = state
        .get_latest_judge_final_report(session_id as u64, &participant, Some(2))
        .await?;
    assert!(run2_final.final_report.is_none());
    Ok(())
}

#[tokio::test]
async fn get_latest_judge_report_should_reject_invalid_rejudge_run_no() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let participant = find_user(&state, 2).await?;
    let session_id = seed_topic_and_session(&state, "judging").await?;
    add_participant(&state, session_id, participant.id, "pro").await?;

    let err = state
        .get_latest_judge_report(session_id as u64, &participant, Some(0))
        .await
        .expect_err("run_no=0 should be rejected");
    match err {
        AppError::DebateError(msg) => assert_eq!(msg, "judge_report_run_no_invalid"),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn list_judge_reviews_by_owner_should_reject_invalid_winner_filter() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;
    let mut query = default_ops_review_query();
    query.winner = Some("invalid".to_string());

    let err = state
        .list_judge_reviews_by_owner(&owner, query)
        .await
        .expect_err("invalid winner should be rejected");
    match err {
        AppError::DebateError(msg) => assert!(msg.contains("invalid winner")),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn list_judge_reviews_by_owner_should_require_judge_review_permission() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let outsider = find_user(&state, 2).await?;

    let err = state
        .list_judge_reviews_by_owner(&outsider, default_ops_review_query())
        .await
        .expect_err("missing role should be denied");
    match err {
        AppError::DebateConflict(code) => {
            assert!(code.contains("ops_permission_denied:judge_review"))
        }
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn get_judge_final_dispatch_failure_stats_by_owner_should_require_judge_review_permission(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let outsider = find_user(&state, 2).await?;

    let err = state
        .get_judge_final_dispatch_failure_stats_by_owner(&outsider, default_failure_stats_query())
        .await
        .expect_err("missing role should be denied");
    match err {
        AppError::DebateConflict(code) => {
            assert!(code.contains("ops_permission_denied:judge_review"))
        }
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn get_judge_final_dispatch_failure_stats_by_owner_should_reject_invalid_window() -> Result<()>
{
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;

    let err = state
        .get_judge_final_dispatch_failure_stats_by_owner(
            &owner,
            GetJudgeFinalDispatchFailureStatsQuery {
                from: Some(Utc::now()),
                to: Some(Utc::now() - Duration::seconds(1)),
                limit: Some(10),
            },
        )
        .await
        .expect_err("invalid window should be rejected");
    match err {
        AppError::DebateError(msg) => assert!(msg.contains("from must be <= to")),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn get_judge_final_dispatch_failure_stats_by_owner_should_return_zero_for_empty_window(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;

    let out = state
        .get_judge_final_dispatch_failure_stats_by_owner(
            &owner,
            GetJudgeFinalDispatchFailureStatsQuery {
                from: Some(Utc::now() + Duration::days(1)),
                to: Some(Utc::now() + Duration::days(2)),
                limit: Some(20),
            },
        )
        .await?;
    assert_eq!(out.total_failed_jobs, 0);
    assert_eq!(out.scanned_failed_jobs, 0);
    assert!(!out.truncated);
    assert_eq!(out.unknown_failed_jobs, 0);
    assert!(out.by_type.is_empty());
    Ok(())
}

#[tokio::test]
async fn get_judge_final_dispatch_failure_stats_by_owner_should_mark_truncated_when_scan_limited(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;
    let now = Utc::now();
    for idx in 0..3_i64 {
        seed_failed_final_job_for_stats(
            &state,
            now - Duration::seconds(idx),
            Some("[response_accepted_false] accepted=false"),
            None,
            None,
        )
        .await?;
    }

    let out = state
        .get_judge_final_dispatch_failure_stats_by_owner(
            &owner,
            GetJudgeFinalDispatchFailureStatsQuery {
                from: None,
                to: None,
                limit: Some(2),
            },
        )
        .await?;
    assert_eq!(out.total_failed_jobs, 3);
    assert_eq!(out.scanned_failed_jobs, 2);
    assert!(out.truncated);
    assert_eq!(out.unknown_failed_jobs, 0);
    Ok(())
}

#[tokio::test]
async fn get_judge_final_dispatch_failure_stats_by_owner_should_prefer_structured_failure_type(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;
    let now = Utc::now();

    seed_failed_final_job_for_stats(
        &state,
        now - Duration::seconds(1),
        Some("[response_accepted_false] accepted=false"),
        Some("response_accepted_false"),
        Some("final_contract_blocked"),
    )
    .await?;
    seed_failed_final_job_for_stats(
        &state,
        now - Duration::seconds(2),
        Some("[response_job_id_mismatch] job_id mismatch"),
        None,
        None,
    )
    .await?;
    seed_failed_final_job_for_stats(
        &state,
        now - Duration::seconds(3),
        Some("unrecognized transport timeout"),
        None,
        None,
    )
    .await?;

    let out = state
        .get_judge_final_dispatch_failure_stats_by_owner(&owner, default_failure_stats_query())
        .await?;

    assert_eq!(out.total_failed_jobs, 3);
    assert_eq!(out.scanned_failed_jobs, 3);
    assert!(!out.truncated);
    assert_eq!(out.unknown_failed_jobs, 1);
    let types = out
        .by_type
        .iter()
        .map(|item| item.failure_type.as_str())
        .collect::<Vec<_>>();
    assert!(types.contains(&"final_contract_blocked"));
    assert!(types.contains(&"response_job_id_mismatch"));
    assert!(types.contains(&"unknown_contract_failure"));
    // 所有分组 count 都为 1 时，应该按 failure_type 字典序稳定排序。
    assert_eq!(
        types,
        vec![
            "final_contract_blocked",
            "response_job_id_mismatch",
            "unknown_contract_failure"
        ]
    );
    Ok(())
}

#[tokio::test]
async fn list_judge_trace_replay_by_owner_should_require_judge_review_permission() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let outsider = find_user(&state, 2).await?;

    let err = state
        .list_judge_trace_replay_by_owner(&outsider, default_trace_replay_query())
        .await
        .expect_err("missing role should be denied");
    match err {
        AppError::DebateConflict(code) => {
            assert!(code.contains("ops_permission_denied:judge_review"))
        }
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn list_judge_trace_replay_by_owner_should_reject_invalid_window() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;

    let err = state
        .list_judge_trace_replay_by_owner(
            &owner,
            ListJudgeTraceReplayOpsQuery {
                from: Some(Utc::now()),
                to: Some(Utc::now() - Duration::seconds(1)),
                ..default_trace_replay_query()
            },
        )
        .await
        .expect_err("invalid window should be rejected");
    match err {
        AppError::DebateError(msg) => assert!(msg.contains("from must be <= to")),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn list_judge_trace_replay_by_owner_should_reject_invalid_scope_filter() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;

    let err = state
        .list_judge_trace_replay_by_owner(
            &owner,
            ListJudgeTraceReplayOpsQuery {
                scope: Some("invalid".to_string()),
                ..default_trace_replay_query()
            },
        )
        .await
        .expect_err("invalid scope should be rejected");
    match err {
        AppError::DebateError(msg) => assert!(msg.contains("scope must be one of: phase, final")),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn list_judge_trace_replay_by_owner_should_reject_invalid_status_filter() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;

    let err = state
        .list_judge_trace_replay_by_owner(
            &owner,
            ListJudgeTraceReplayOpsQuery {
                status: Some("invalid".to_string()),
                ..default_trace_replay_query()
            },
        )
        .await
        .expect_err("invalid status should be rejected");
    match err {
        AppError::DebateError(msg) => {
            assert!(msg.contains("status must be one of: queued, dispatched, succeeded, failed"))
        }
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn list_judge_trace_replay_by_owner_should_aggregate_counts_and_replay_eligibility(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;
    let now = Utc::now();
    seed_phase_job_for_trace_replay(
        &state,
        now - Duration::seconds(1),
        "failed",
        Some("[phase_artifact_incomplete] report missing"),
    )
    .await?;
    seed_final_job_for_trace_replay(
        &state,
        now - Duration::seconds(2),
        "dispatched",
        None,
        None,
        None,
    )
    .await?;

    let out = state
        .list_judge_trace_replay_by_owner(&owner, default_trace_replay_query())
        .await?;
    assert_eq!(out.scanned_count, 2);
    assert_eq!(out.returned_count, 2);
    assert_eq!(out.phase_count, 1);
    assert_eq!(out.final_count, 1);
    assert_eq!(out.failed_count, 1);
    assert_eq!(out.replay_eligible_count, 1);

    let phase_item = out
        .items
        .iter()
        .find(|item| item.scope == "phase")
        .expect("phase item should exist");
    assert!(phase_item.replay_eligible);
    assert_eq!(
        phase_item.replay_recommendation.as_deref(),
        Some("replay_phase_job")
    );
    let final_item = out
        .items
        .iter()
        .find(|item| item.scope == "final")
        .expect("final item should exist");
    assert!(!final_item.replay_eligible);
    assert!(final_item.replay_recommendation.is_none());
    Ok(())
}

#[tokio::test]
async fn list_judge_trace_replay_by_owner_should_prefer_structured_fields_and_map_replay_summary(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;
    let now = Utc::now();
    let (session_id, final_job_id) = seed_final_job_for_trace_replay(
        &state,
        now,
        "failed",
        Some("[response_accepted_false] accepted=false"),
        Some("response_job_id_mismatch"),
        Some("final_contract_blocked"),
    )
    .await?;
    let _old_audit_id = seed_replay_action_for_trace_replay(
        &state,
        "final",
        final_job_id,
        session_id,
        now - Duration::seconds(2),
        Some("old replay"),
    )
    .await?;
    let latest_audit_id = seed_replay_action_for_trace_replay(
        &state,
        "final",
        final_job_id,
        session_id,
        now - Duration::seconds(1),
        Some("latest replay"),
    )
    .await?;

    let out = state
        .list_judge_trace_replay_by_owner(
            &owner,
            ListJudgeTraceReplayOpsQuery {
                session_id: Some(session_id as u64),
                ..default_trace_replay_query()
            },
        )
        .await?;
    assert_eq!(out.scanned_count, 1);
    assert_eq!(out.returned_count, 1);
    let item = out.items.first().expect("one item should exist");
    assert_eq!(item.scope, "final");
    assert_eq!(item.error_code.as_deref(), Some("response_job_id_mismatch"));
    assert_eq!(
        item.contract_failure_type.as_deref(),
        Some("final_contract_blocked")
    );
    assert_eq!(item.replay_action_count, 2);
    assert_eq!(item.latest_replay_action_id, Some(latest_audit_id as u64));
    assert_eq!(item.latest_replay_at, Some(now - Duration::seconds(1)));
    Ok(())
}

#[tokio::test]
async fn list_judge_trace_replay_by_owner_should_fallback_to_error_message_when_structured_missing(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;
    let now = Utc::now();
    let (session_id, _final_job_id) = seed_final_job_for_trace_replay(
        &state,
        now,
        "failed",
        Some("[response_accepted_false] accepted=false"),
        None,
        None,
    )
    .await?;

    let out = state
        .list_judge_trace_replay_by_owner(
            &owner,
            ListJudgeTraceReplayOpsQuery {
                session_id: Some(session_id as u64),
                ..default_trace_replay_query()
            },
        )
        .await?;
    assert_eq!(out.scanned_count, 1);
    let item = out.items.first().expect("one item should exist");
    assert_eq!(item.error_code.as_deref(), Some("response_accepted_false"));
    assert_eq!(
        item.contract_failure_type.as_deref(),
        Some("response_accepted_false")
    );
    Ok(())
}

#[tokio::test]
async fn list_judge_trace_replay_by_owner_should_keep_stable_order_when_created_at_ties(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;
    let tie_time = Utc::now();
    seed_phase_job_for_trace_replay(&state, tie_time, "succeeded", None).await?;
    seed_final_job_for_trace_replay(
        &state,
        tie_time,
        "failed",
        Some("[response_job_id_mismatch] job_id mismatch"),
        None,
        None,
    )
    .await?;
    seed_phase_job_for_trace_replay(
        &state,
        tie_time,
        "failed",
        Some("[phase_artifact_incomplete] report missing"),
    )
    .await?;

    let out = state
        .list_judge_trace_replay_by_owner(
            &owner,
            ListJudgeTraceReplayOpsQuery {
                limit: Some(10),
                ..default_trace_replay_query()
            },
        )
        .await?;
    assert_eq!(out.scanned_count, 3);
    assert_eq!(out.returned_count, 3);

    let observed = out
        .items
        .iter()
        .map(|item| (item.created_at, item.job_id, item.scope.clone()))
        .collect::<Vec<_>>();
    let mut expected = observed.clone();
    expected.sort_by(|a, b| {
        b.0.cmp(&a.0)
            .then_with(|| b.1.cmp(&a.1))
            .then_with(|| b.2.cmp(&a.2))
    });
    assert_eq!(observed, expected);
    Ok(())
}

#[tokio::test]
async fn list_judge_replay_actions_by_owner_should_require_judge_review_permission() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let outsider = find_user(&state, 2).await?;

    let err = state
        .list_judge_replay_actions_by_owner(&outsider, default_replay_actions_query())
        .await
        .expect_err("missing role should be denied");
    match err {
        AppError::DebateConflict(code) => {
            assert!(code.contains("ops_permission_denied:judge_review"))
        }
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn list_judge_replay_actions_by_owner_should_reject_invalid_window() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;

    let err = state
        .list_judge_replay_actions_by_owner(
            &owner,
            ListJudgeReplayActionsOpsQuery {
                from: Some(Utc::now()),
                to: Some(Utc::now() - Duration::seconds(1)),
                ..default_replay_actions_query()
            },
        )
        .await
        .expect_err("invalid window should be rejected");
    match err {
        AppError::DebateError(msg) => assert!(msg.contains("from must be <= to")),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn list_judge_replay_actions_by_owner_should_reject_out_of_range_filters() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;
    let overflow_u64 = (i64::MAX as u64).saturating_add(1);

    let session_err = state
        .list_judge_replay_actions_by_owner(
            &owner,
            ListJudgeReplayActionsOpsQuery {
                session_id: Some(overflow_u64),
                ..default_replay_actions_query()
            },
        )
        .await
        .expect_err("overflow session_id should fail");
    match session_err {
        AppError::DebateError(msg) => {
            assert_eq!(msg, "ops_judge_replay_actions_session_id_out_of_range")
        }
        other => panic!("unexpected error: {other}"),
    }

    let job_err = state
        .list_judge_replay_actions_by_owner(
            &owner,
            ListJudgeReplayActionsOpsQuery {
                job_id: Some(overflow_u64),
                ..default_replay_actions_query()
            },
        )
        .await
        .expect_err("overflow job_id should fail");
    match job_err {
        AppError::DebateError(msg) => {
            assert_eq!(msg, "ops_judge_replay_actions_job_id_out_of_range")
        }
        other => panic!("unexpected error: {other}"),
    }

    let requested_by_err = state
        .list_judge_replay_actions_by_owner(
            &owner,
            ListJudgeReplayActionsOpsQuery {
                requested_by: Some(overflow_u64),
                ..default_replay_actions_query()
            },
        )
        .await
        .expect_err("overflow requested_by should fail");
    match requested_by_err {
        AppError::DebateError(msg) => {
            assert_eq!(msg, "ops_judge_replay_actions_requested_by_out_of_range")
        }
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn list_judge_replay_actions_by_owner_should_apply_filters_and_keep_stable_order(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;
    let now = Utc::now();

    let (phase_session_id, phase_job_id) =
        seed_phase_job_for_trace_replay(&state, now - Duration::seconds(10), "failed", None)
            .await?;
    let _phase_old = seed_replay_action_for_trace_replay(
        &state,
        "phase",
        phase_job_id,
        phase_session_id,
        now - Duration::seconds(2),
        Some("alpha replay old"),
    )
    .await?;
    let phase_latest = seed_replay_action_for_trace_replay(
        &state,
        "phase",
        phase_job_id,
        phase_session_id,
        now - Duration::seconds(1),
        Some("alpha replay latest"),
    )
    .await?;

    let (final_session_id, final_job_id) = seed_final_job_for_trace_replay(
        &state,
        now - Duration::seconds(10),
        "failed",
        None,
        None,
        None,
    )
    .await?;
    let _final_audit_id = seed_replay_action_for_trace_replay(
        &state,
        "final",
        final_job_id,
        final_session_id,
        now - Duration::seconds(3),
        Some("beta replay"),
    )
    .await?;

    let output = state
        .list_judge_replay_actions_by_owner(
            &owner,
            ListJudgeReplayActionsOpsQuery {
                scope: Some("phase".to_string()),
                session_id: Some(phase_session_id as u64),
                job_id: Some(phase_job_id as u64),
                requested_by: Some(1),
                previous_status: Some("FAILED".to_string()),
                new_status: Some("queued".to_string()),
                reason_keyword: Some("alpha".to_string()),
                trace_keyword: Some(format!("phase-{phase_job_id}")),
                ..default_replay_actions_query()
            },
        )
        .await?;

    assert_eq!(output.scanned_count, 2);
    assert_eq!(output.returned_count, 2);
    assert!(!output.has_more);
    assert_eq!(output.items.len(), 2);
    assert!(output.items[0].created_at >= output.items[1].created_at);
    assert_eq!(output.items[0].scope, "phase");
    assert_eq!(output.items[0].session_id, phase_session_id as u64);
    assert_eq!(output.items[0].job_id, phase_job_id as u64);
    assert_eq!(output.items[0].requested_by, 1);
    assert_eq!(output.items[0].previous_status, "failed");
    assert_eq!(output.items[0].new_status, "queued");
    assert_eq!(output.items[0].audit_id, phase_latest as u64);
    Ok(())
}

#[tokio::test]
async fn list_judge_replay_actions_by_owner_should_apply_limit_and_offset_clamp() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;
    let now = Utc::now();
    let (phase_session_id, phase_job_id) =
        seed_phase_job_for_trace_replay(&state, now - Duration::seconds(10), "failed", None)
            .await?;
    seed_replay_action_for_trace_replay(
        &state,
        "phase",
        phase_job_id,
        phase_session_id,
        now - Duration::seconds(3),
        Some("alpha replay 1"),
    )
    .await?;
    seed_replay_action_for_trace_replay(
        &state,
        "phase",
        phase_job_id,
        phase_session_id,
        now - Duration::seconds(2),
        Some("alpha replay 2"),
    )
    .await?;
    seed_replay_action_for_trace_replay(
        &state,
        "phase",
        phase_job_id,
        phase_session_id,
        now - Duration::seconds(1),
        Some("alpha replay 3"),
    )
    .await?;

    let clamped_limit_out = state
        .list_judge_replay_actions_by_owner(
            &owner,
            ListJudgeReplayActionsOpsQuery {
                limit: Some(0),
                ..default_replay_actions_query()
            },
        )
        .await?;
    assert_eq!(clamped_limit_out.scanned_count, 3);
    assert_eq!(clamped_limit_out.returned_count, 1);
    assert!(clamped_limit_out.has_more);

    let clamped_offset_out = state
        .list_judge_replay_actions_by_owner(
            &owner,
            ListJudgeReplayActionsOpsQuery {
                offset: Some(20_000),
                ..default_replay_actions_query()
            },
        )
        .await?;
    assert_eq!(clamped_offset_out.scanned_count, 3);
    assert_eq!(clamped_offset_out.returned_count, 0);
    assert!(!clamped_offset_out.has_more);
    assert!(clamped_offset_out.items.is_empty());
    Ok(())
}

#[tokio::test]
async fn list_judge_replay_actions_by_owner_should_validate_status_and_keyword_input() -> Result<()>
{
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;

    let status_err = state
        .list_judge_replay_actions_by_owner(
            &owner,
            ListJudgeReplayActionsOpsQuery {
                previous_status: Some("invalid$status".to_string()),
                ..default_replay_actions_query()
            },
        )
        .await
        .expect_err("invalid status should fail");
    match status_err {
        AppError::DebateError(msg) => {
            assert!(msg.contains("previousStatus contains unsupported characters"))
        }
        other => panic!("unexpected error: {other}"),
    }

    let keyword_err = state
        .list_judge_replay_actions_by_owner(
            &owner,
            ListJudgeReplayActionsOpsQuery {
                reason_keyword: Some("k".repeat(101)),
                ..default_replay_actions_query()
            },
        )
        .await
        .expect_err("too long reason keyword should fail");
    match keyword_err {
        AppError::DebateError(msg) => assert!(msg.contains("reasonKeyword is too long")),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn get_judge_replay_preview_by_owner_should_reject_invalid_scope() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;

    let err = state
        .get_judge_replay_preview_by_owner(&owner, replay_preview_query("invalid", 1))
        .await
        .expect_err("invalid scope should be rejected");
    match err {
        AppError::DebateError(msg) => assert!(msg.contains("scope must be one of: phase, final")),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn get_judge_replay_preview_by_owner_should_return_not_found_for_missing_jobs() -> Result<()>
{
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;

    let phase_err = state
        .get_judge_replay_preview_by_owner(&owner, replay_preview_query("phase", 999_999))
        .await
        .expect_err("missing phase job should be rejected");
    match phase_err {
        AppError::NotFound(msg) => assert!(msg.contains("judge phase job id 999999")),
        other => panic!("unexpected error: {other}"),
    }

    let final_err = state
        .get_judge_replay_preview_by_owner(&owner, replay_preview_query("final", 999_999))
        .await
        .expect_err("missing final job should be rejected");
    match final_err {
        AppError::NotFound(msg) => assert!(msg.contains("judge final job id 999999")),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn get_judge_replay_preview_by_owner_should_reject_phase_message_count_mismatch() -> Result<()>
{
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;
    let (_session_id, phase_job_id) =
        seed_phase_job_for_trace_replay(&state, Utc::now(), "failed", None).await?;
    sqlx::query(
        r#"
        UPDATE judge_phase_jobs
        SET message_count = message_count + 1
        WHERE id = $1
        "#,
    )
    .bind(phase_job_id)
    .execute(&state.pool)
    .await?;

    let err = state
        .get_judge_replay_preview_by_owner(
            &owner,
            replay_preview_query("phase", phase_job_id as u64),
        )
        .await
        .expect_err("message count mismatch should fail");
    match err {
        AppError::DebateError(msg) => assert!(msg.contains("message_count mismatch")),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn get_judge_replay_preview_by_owner_should_reject_invalid_final_phase_range() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;
    let (_session_id, final_job_id) =
        seed_final_job_for_trace_replay(&state, Utc::now(), "failed", None, None, None).await?;
    // 生产库由 check constraint 兜底，这里临时移除约束以覆盖防御分支。
    sqlx::query("ALTER TABLE judge_final_jobs DROP CONSTRAINT IF EXISTS judge_final_jobs_check")
        .execute(&state.pool)
        .await?;
    sqlx::query(
        r#"
        UPDATE judge_final_jobs
        SET phase_start_no = 4, phase_end_no = 3
        WHERE id = $1
        "#,
    )
    .bind(final_job_id)
    .execute(&state.pool)
    .await?;

    let err = state
        .get_judge_replay_preview_by_owner(
            &owner,
            replay_preview_query("final", final_job_id as u64),
        )
        .await
        .expect_err("invalid final phase range should fail");
    match err {
        AppError::DebateError(msg) => assert!(msg.contains("phase range invalid")),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn get_judge_replay_preview_by_owner_should_mark_replay_block_reason_for_non_terminal_status(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;
    let (_session_id, final_job_id) =
        seed_final_job_for_trace_replay(&state, Utc::now(), "dispatched", None, None, None).await?;

    let out = state
        .get_judge_replay_preview_by_owner(
            &owner,
            replay_preview_query("final", final_job_id as u64),
        )
        .await?;
    assert_eq!(out.meta.scope, "final");
    assert_eq!(out.meta.job_id, final_job_id as u64);
    assert!(!out.meta.replay_eligible);
    assert_eq!(
        out.meta.replay_block_reason.as_deref(),
        Some("job_status_not_terminal")
    );
    Ok(())
}

#[tokio::test]
async fn get_judge_replay_preview_by_owner_should_reject_out_of_range_job_id() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;
    let overflow_job_id = (i64::MAX as u64).saturating_add(1);

    let err = state
        .get_judge_replay_preview_by_owner(&owner, replay_preview_query("phase", overflow_job_id))
        .await
        .expect_err("overflow job id should fail");
    match err {
        AppError::DebateError(msg) => {
            assert_eq!(msg, "ops_judge_replay_preview_job_id_out_of_range")
        }
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn execute_judge_replay_by_owner_should_require_judge_rejudge_permission() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let outsider = find_user(&state, 2).await?;

    let err = state
        .execute_judge_replay_by_owner(&outsider, replay_execute_input("phase", 1, None))
        .await
        .expect_err("missing role should be denied");
    match err {
        AppError::DebateConflict(code) => {
            assert!(code.contains("ops_permission_denied:judge_rejudge"))
        }
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn execute_judge_replay_by_owner_should_reject_invalid_scope() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;

    let err = state
        .execute_judge_replay_by_owner(&owner, replay_execute_input("invalid", 1, None))
        .await
        .expect_err("invalid scope should be rejected");
    match err {
        AppError::DebateError(msg) => assert!(msg.contains("scope must be one of: phase, final")),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn execute_judge_replay_by_owner_should_reject_too_long_reason() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;

    let err = state
        .execute_judge_replay_by_owner(
            &owner,
            replay_execute_input("phase", 1, Some("r".repeat(501))),
        )
        .await
        .expect_err("too long reason should be rejected");
    match err {
        AppError::DebateError(msg) => assert!(msg.contains("reason is too long, max 500 chars")),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn execute_judge_replay_by_owner_should_return_not_found_for_missing_jobs() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;

    let phase_err = state
        .execute_judge_replay_by_owner(&owner, replay_execute_input("phase", 999_999, None))
        .await
        .expect_err("missing phase job should fail");
    match phase_err {
        AppError::NotFound(msg) => assert!(msg.contains("judge phase job id 999999")),
        other => panic!("unexpected error: {other}"),
    }

    let final_err = state
        .execute_judge_replay_by_owner(&owner, replay_execute_input("final", 999_999, None))
        .await
        .expect_err("missing final job should fail");
    match final_err {
        AppError::NotFound(msg) => assert!(msg.contains("judge final job id 999999")),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn execute_judge_replay_by_owner_should_reject_non_failed_status() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;
    let (_phase_session_id, phase_job_id) =
        seed_phase_job_for_trace_replay(&state, Utc::now(), "dispatched", None).await?;
    let (_final_session_id, final_job_id) =
        seed_final_job_for_trace_replay(&state, Utc::now(), "dispatched", None, None, None).await?;

    let phase_err = state
        .execute_judge_replay_by_owner(
            &owner,
            replay_execute_input("phase", phase_job_id as u64, None),
        )
        .await
        .expect_err("non-failed phase should fail");
    match phase_err {
        AppError::DebateConflict(msg) => {
            assert!(msg.contains("replay execute requires failed phase job"))
        }
        other => panic!("unexpected error: {other}"),
    }

    let final_err = state
        .execute_judge_replay_by_owner(
            &owner,
            replay_execute_input("final", final_job_id as u64, None),
        )
        .await
        .expect_err("non-failed final should fail");
    match final_err {
        AppError::DebateConflict(msg) => {
            assert!(msg.contains("replay execute requires failed final job"))
        }
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn execute_judge_replay_by_owner_should_reject_when_phase_report_exists() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;
    let session_id = seed_topic_and_session(&state, "judging").await?;
    let phase_job_id = seed_failed_phase_job(&state, session_id).await?;
    insert_phase_report_for_job(&state, phase_job_id).await?;

    let err = state
        .execute_judge_replay_by_owner(
            &owner,
            replay_execute_input("phase", phase_job_id as u64, None),
        )
        .await
        .expect_err("phase report exists should fail");
    match err {
        AppError::DebateConflict(msg) => assert!(msg.contains("already has report")),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn execute_judge_replay_by_owner_should_reject_when_final_report_exists() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;
    let session_id = seed_topic_and_session(&state, "judging").await?;
    let final_job_id = upsert_final_job(
        &state,
        session_id,
        "failed",
        Some("[response_accepted_false] accepted=false"),
        Some("response_accepted_false"),
        Some("final_contract_blocked"),
    )
    .await?;
    upsert_final_report(&state, session_id, final_job_id, "pro").await?;

    let err = state
        .execute_judge_replay_by_owner(
            &owner,
            replay_execute_input("final", final_job_id as u64, None),
        )
        .await
        .expect_err("final report exists should fail");
    match err {
        AppError::DebateConflict(msg) => assert!(msg.contains("already has report")),
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn execute_judge_replay_by_owner_should_reject_out_of_range_job_id() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;
    let overflow_job_id = (i64::MAX as u64).saturating_add(1);

    let err = state
        .execute_judge_replay_by_owner(&owner, replay_execute_input("phase", overflow_job_id, None))
        .await
        .expect_err("overflow job id should fail");
    match err {
        AppError::DebateError(msg) => {
            assert_eq!(msg, "ops_judge_replay_execute_job_id_out_of_range")
        }
        other => panic!("unexpected error: {other}"),
    }
    Ok(())
}

#[tokio::test]
async fn execute_judge_replay_by_owner_should_reset_phase_and_final_jobs_and_write_audit(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;

    let phase_session_id = seed_topic_and_session(&state, "judging").await?;
    let phase_job_id = seed_failed_phase_job(&state, phase_session_id).await?;
    let phase_out = state
        .execute_judge_replay_by_owner(
            &owner,
            replay_execute_input(
                "phase",
                phase_job_id as u64,
                Some("  manual replay for phase  ".to_string()),
            ),
        )
        .await?;
    assert_eq!(phase_out.scope, "phase");
    assert_eq!(phase_out.job_id, phase_job_id as u64);
    assert_eq!(phase_out.previous_status, "failed");
    assert_eq!(phase_out.new_status, "queued");
    assert!(phase_out.new_trace_id.starts_with("judge-replay-phase-"));
    assert!(phase_out
        .new_idempotency_key
        .starts_with("judge-replay:phase:"));

    let phase_row: (String, i32, Option<String>, String, String) = sqlx::query_as(
        r#"
        SELECT status, dispatch_attempts, error_message, trace_id, idempotency_key
        FROM judge_phase_jobs
        WHERE id = $1
        "#,
    )
    .bind(phase_job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(phase_row.0, "queued");
    assert_eq!(phase_row.1, 0);
    assert!(phase_row.2.is_none());
    assert_eq!(phase_row.3, phase_out.new_trace_id);
    assert_eq!(phase_row.4, phase_out.new_idempotency_key);

    let phase_audit: (String, Option<String>, String, String) = sqlx::query_as(
        r#"
        SELECT scope, reason, previous_status, new_status
        FROM judge_replay_actions
        WHERE id = $1
        "#,
    )
    .bind(phase_out.audit_id as i64)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(phase_audit.0, "phase");
    assert_eq!(phase_audit.1.as_deref(), Some("manual replay for phase"));
    assert_eq!(phase_audit.2, "failed");
    assert_eq!(phase_audit.3, "queued");

    let final_session_id = seed_topic_and_session(&state, "judging").await?;
    let final_job_id = upsert_final_job(
        &state,
        final_session_id,
        "failed",
        Some("[response_accepted_false] accepted=false"),
        Some("response_accepted_false"),
        Some("final_contract_blocked"),
    )
    .await?;
    let final_out = state
        .execute_judge_replay_by_owner(
            &owner,
            replay_execute_input(
                "final",
                final_job_id as u64,
                Some("manual replay for final".to_string()),
            ),
        )
        .await?;
    assert_eq!(final_out.scope, "final");
    assert_eq!(final_out.job_id, final_job_id as u64);
    assert_eq!(final_out.previous_status, "failed");
    assert_eq!(final_out.new_status, "queued");
    assert!(final_out.new_trace_id.starts_with("judge-replay-final-"));
    assert!(final_out
        .new_idempotency_key
        .starts_with("judge-replay:final:"));

    let final_row: (
        String,
        i32,
        Option<String>,
        Option<String>,
        Option<String>,
        String,
        String,
    ) = sqlx::query_as(
        r#"
        SELECT
            status,
            dispatch_attempts,
            error_message,
            error_code,
            contract_failure_type,
            trace_id,
            idempotency_key
        FROM judge_final_jobs
        WHERE id = $1
        "#,
    )
    .bind(final_job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(final_row.0, "queued");
    assert_eq!(final_row.1, 0);
    assert!(final_row.2.is_none());
    assert!(final_row.3.is_none());
    assert!(final_row.4.is_none());
    assert_eq!(final_row.5, final_out.new_trace_id);
    assert_eq!(final_row.6, final_out.new_idempotency_key);
    Ok(())
}

#[tokio::test]
async fn list_judge_reviews_by_owner_should_apply_anomaly_only_scan_limit_multiplier() -> Result<()>
{
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;
    let now = Utc::now();

    for idx in 0..8_i64 {
        let is_abnormal = idx == 0;
        seed_ops_review_case(
            &state,
            OpsReviewSeedInput {
                winner: "pro",
                pro_score: 90,
                con_score: 60,
                verdict_evidence_count: if is_abnormal { 0 } else { 1 },
                needs_draw_vote: false,
                winner_first: Some("pro"),
                winner_second: Some("pro"),
                rejudge_triggered: false,
                created_at: now - Duration::seconds(idx),
            },
        )
        .await?;
    }

    for idx in 8..12_i64 {
        seed_ops_review_case(
            &state,
            OpsReviewSeedInput {
                winner: "pro",
                pro_score: 90,
                con_score: 60,
                verdict_evidence_count: 0,
                needs_draw_vote: false,
                winner_first: Some("pro"),
                winner_second: Some("pro"),
                rejudge_triggered: false,
                created_at: now - Duration::seconds(idx),
            },
        )
        .await?;
    }

    let output = state
        .list_judge_reviews_by_owner(
            &owner,
            ListJudgeReviewOpsQuery {
                anomaly_only: true,
                limit: Some(2),
                ..default_ops_review_query()
            },
        )
        .await?;

    assert_eq!(output.scanned_count, 8);
    assert_eq!(output.returned_count, 1);
    assert_eq!(output.items.len(), 1);
    assert!(output.items[0]
        .abnormal_flags
        .iter()
        .any(|flag| flag == "missing_verdict_evidence_refs"));
    Ok(())
}

#[tokio::test]
async fn list_judge_reviews_by_owner_should_mark_abnormal_flags_and_mark_missing_winner_pass(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let owner = find_user(&state, 1).await?;
    let now = Utc::now();

    let missing_evidence_report_id = seed_ops_review_case(
        &state,
        OpsReviewSeedInput {
            winner: "pro",
            pro_score: 95,
            con_score: 70,
            verdict_evidence_count: 0,
            needs_draw_vote: false,
            winner_first: Some("pro"),
            winner_second: Some("pro"),
            rejudge_triggered: false,
            created_at: now,
        },
    )
    .await?;
    let narrow_gap_report_id = seed_ops_review_case(
        &state,
        OpsReviewSeedInput {
            winner: "pro",
            pro_score: 72,
            con_score: 70,
            verdict_evidence_count: 1,
            needs_draw_vote: false,
            winner_first: Some("pro"),
            winner_second: Some("pro"),
            rejudge_triggered: false,
            created_at: now - Duration::seconds(1),
        },
    )
    .await?;
    let draw_without_vote_report_id = seed_ops_review_case(
        &state,
        OpsReviewSeedInput {
            winner: "draw",
            pro_score: 71,
            con_score: 71,
            verdict_evidence_count: 1,
            needs_draw_vote: false,
            winner_first: Some("draw"),
            winner_second: Some("draw"),
            rejudge_triggered: false,
            created_at: now - Duration::seconds(2),
        },
    )
    .await?;
    let winner_conflict_report_id = seed_ops_review_case(
        &state,
        OpsReviewSeedInput {
            winner: "pro",
            pro_score: 90,
            con_score: 70,
            verdict_evidence_count: 1,
            needs_draw_vote: false,
            winner_first: Some("pro"),
            winner_second: Some("con"),
            rejudge_triggered: false,
            created_at: now - Duration::seconds(3),
        },
    )
    .await?;
    let winner_pass_missing_report_id = seed_ops_review_case(
        &state,
        OpsReviewSeedInput {
            winner: "pro",
            pro_score: 88,
            con_score: 70,
            verdict_evidence_count: 1,
            needs_draw_vote: false,
            winner_first: None,
            winner_second: Some("pro"),
            rejudge_triggered: false,
            created_at: now - Duration::seconds(4),
        },
    )
    .await?;

    let output = state
        .list_judge_reviews_by_owner(&owner, default_ops_review_query())
        .await?;
    let items_by_id = output
        .items
        .iter()
        .map(|item| (item.report_id, item))
        .collect::<std::collections::HashMap<_, _>>();

    let missing_evidence_item = items_by_id
        .get(&missing_evidence_report_id)
        .expect("missing evidence item should exist");
    assert!(missing_evidence_item
        .abnormal_flags
        .iter()
        .any(|flag| flag == "missing_verdict_evidence_refs"));

    let narrow_gap_item = items_by_id
        .get(&narrow_gap_report_id)
        .expect("narrow score gap item should exist");
    assert!(narrow_gap_item
        .abnormal_flags
        .iter()
        .any(|flag| flag == "narrow_score_gap"));

    let draw_without_vote_item = items_by_id
        .get(&draw_without_vote_report_id)
        .expect("draw without vote item should exist");
    assert!(draw_without_vote_item
        .abnormal_flags
        .iter()
        .any(|flag| flag == "draw_without_vote_flow"));

    let winner_conflict_item = items_by_id
        .get(&winner_conflict_report_id)
        .expect("winner conflict item should exist");
    assert!(winner_conflict_item
        .abnormal_flags
        .iter()
        .any(|flag| flag == "winner_inconsistent_between_two_passes"));

    let winner_pass_missing_item = items_by_id
        .get(&winner_pass_missing_report_id)
        .expect("winner pass missing item should exist");
    assert!(winner_pass_missing_item
        .abnormal_flags
        .iter()
        .any(|flag| flag == "winner_pass_missing"));
    assert!(!winner_pass_missing_item
        .abnormal_flags
        .iter()
        .any(|flag| flag == "winner_inconsistent_between_two_passes"));
    Ok(())
}
