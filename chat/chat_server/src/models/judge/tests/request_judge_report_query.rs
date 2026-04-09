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
            session_id, phase_no, message_start_id, message_end_id, message_count,
            status, trace_id, idempotency_key, rubric_version, judge_policy_version,
            topic_domain, retrieval_profile, dispatch_attempts, last_dispatch_at, error_message
        )
        VALUES (
            $1, 1, $2, $3, 2,
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
    .bind(format!("judge_phase:{session_id}:1:v3:v3-default"))
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
            session_id, phase_start_no, phase_end_no,
            status, trace_id, idempotency_key, rubric_version, judge_policy_version,
            topic_domain, dispatch_attempts, last_dispatch_at,
            error_message, error_code, contract_failure_type
        )
        VALUES (
            $1, 1, 3,
            $2, $3, $4, 'v3', 'v3-default',
            'default', 2, NOW(),
            $5, $6, $7
        )
        ON CONFLICT (session_id)
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
    .bind(format!("judge_final:{session_id}:{status}:v3:v3-default"))
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
            final_job_id, session_id, winner, pro_score, con_score, dimension_scores,
            final_rationale, verdict_evidence_refs, phase_rollup_summary, retrieval_snapshot_rollup,
            winner_first, winner_second, rejudge_triggered, needs_draw_vote,
            judge_trace, audit_alerts, error_codes, degradation_level
        )
        VALUES (
            $1, $2, $3, 73.0, 70.0, '{"logic": 72.0}'::jsonb,
            'ready final rationale', '[]'::jsonb, '[]'::jsonb, '[]'::jsonb,
            'pro', 'con', false, false,
            '{}'::jsonb, '[]'::jsonb, '[]'::jsonb, 0
        )
        ON CONFLICT (session_id)
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
        .get_latest_judge_report(session_id as u64, &outsider)
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
        .get_latest_judge_report(session_id as u64, &ops_viewer)
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
        .get_latest_judge_report(session_id as u64, &participant)
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
        .get_latest_judge_report(session_id as u64, &participant)
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
        .get_latest_judge_report(session_id as u64, &participant)
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
        .get_latest_judge_final_report(session_id as u64, &participant)
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
