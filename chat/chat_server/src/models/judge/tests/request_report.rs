use super::*;

async fn seed_session_message(
    state: &AppState,
    session_id: i64,
    user_id: i64,
    side: &str,
    content: &str,
) -> Result<i64> {
    let row: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO session_messages(session_id, user_id, side, content)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        "#,
    )
    .bind(session_id)
    .bind(user_id)
    .bind(side)
    .bind(content)
    .fetch_one(&state.pool)
    .await?;
    Ok(row.0)
}

async fn seed_dispatched_final_job(
    state: &AppState,
    session_id: i64,
    phase_start_no: i32,
    phase_end_no: i32,
) -> Result<i64> {
    let row: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO judge_final_jobs(
            session_id, phase_start_no, phase_end_no,
            status, trace_id, idempotency_key, rubric_version, judge_policy_version,
            topic_domain, dispatch_attempts
        )
        VALUES (
            $1, $2, $3,
            'dispatched', $4, $5, 'v3', 'v3-default',
            'default', 1
        )
        RETURNING id
        "#,
    )
    .bind(session_id)
    .bind(phase_start_no)
    .bind(phase_end_no)
    .bind(format!("trace-final-{session_id}-{phase_end_no}"))
    .bind(format!(
        "judge_final:{session_id}:{phase_start_no}:{phase_end_no}:v3:v3-default"
    ))
    .fetch_one(&state.pool)
    .await?;
    Ok(row.0)
}

async fn seed_failed_final_job(
    state: &AppState,
    session_id: i64,
    phase_start_no: i32,
    phase_end_no: i32,
    error_message: &str,
) -> Result<i64> {
    let row: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO judge_final_jobs(
            session_id, phase_start_no, phase_end_no,
            status, trace_id, idempotency_key, rubric_version, judge_policy_version,
            topic_domain, dispatch_attempts, last_dispatch_at, error_message
        )
        VALUES (
            $1, $2, $3,
            'failed', $4, $5, 'v3', 'v3-default',
            'default', 2, NOW(), $6
        )
        RETURNING id
        "#,
    )
    .bind(session_id)
    .bind(phase_start_no)
    .bind(phase_end_no)
    .bind(format!("trace-final-failed-{session_id}-{phase_end_no}"))
    .bind(format!(
        "judge_final_failed:{session_id}:{phase_start_no}:{phase_end_no}:v3:v3-default"
    ))
    .bind(error_message)
    .fetch_one(&state.pool)
    .await?;
    Ok(row.0)
}

#[tokio::test]
async fn request_judge_job_should_create_running_job_with_default_style() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "judging").await?;
    join_user_to_session(&state, session_id, 1).await?;
    let user = state.find_user_by_id(1).await?.expect("user should exist");

    let ret = state
        .request_judge_job(
            session_id as u64,
            &user,
            RequestJudgeJobInput {
                style_mode: None,
                allow_rejudge: false,
            },
        )
        .await?;

    assert!(ret.newly_created);
    assert_eq!(ret.style_mode, "rational");
    assert_eq!(ret.style_mode_source, "system_config");
    assert_eq!(ret.status, "running");
    Ok(())
}

#[tokio::test]
async fn request_judge_job_should_be_idempotent_with_running_job() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "closed").await?;
    join_user_to_session(&state, session_id, 1).await?;
    let user = state.find_user_by_id(1).await?.expect("user should exist");

    let first = state
        .request_judge_job(
            session_id as u64,
            &user,
            RequestJudgeJobInput {
                style_mode: Some("mixed".to_string()),
                allow_rejudge: false,
            },
        )
        .await?;
    let second = state
        .request_judge_job(
            session_id as u64,
            &user,
            RequestJudgeJobInput {
                style_mode: Some("mixed".to_string()),
                allow_rejudge: false,
            },
        )
        .await?;

    assert!(first.newly_created);
    assert!(!second.newly_created);
    assert_eq!(first.job_id, second.job_id);
    assert_eq!(first.style_mode, "rational");
    assert_eq!(first.style_mode_source, "system_config");
    assert_eq!(second.style_mode, "rational");
    assert_eq!(second.style_mode_source, "existing_running_job");
    Ok(())
}

#[tokio::test]
async fn request_judge_job_should_use_system_style_mode_instead_of_request_value() -> Result<()> {
    let (_tdb, mut state) = AppState::new_for_test().await?;
    let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
    inner.config.ai_judge.style_mode = "entertaining".to_string();

    let session_id = seed_topic_and_session(&state, "closed").await?;
    join_user_to_session(&state, session_id, 1).await?;
    let user = state.find_user_by_id(1).await?.expect("user should exist");

    let ret = state
        .request_judge_job(
            session_id as u64,
            &user,
            RequestJudgeJobInput {
                style_mode: Some("mixed".to_string()),
                allow_rejudge: false,
            },
        )
        .await?;

    assert_eq!(ret.style_mode, "entertaining");
    assert_eq!(ret.style_mode_source, "system_config");
    Ok(())
}

#[tokio::test]
async fn request_judge_job_should_fallback_to_rational_when_system_style_invalid() -> Result<()> {
    let (_tdb, mut state) = AppState::new_for_test().await?;
    let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
    inner.config.ai_judge.style_mode = "invalid-style".to_string();

    let session_id = seed_topic_and_session(&state, "closed").await?;
    join_user_to_session(&state, session_id, 1).await?;
    let user = state.find_user_by_id(1).await?.expect("user should exist");

    let ret = state
        .request_judge_job(
            session_id as u64,
            &user,
            RequestJudgeJobInput {
                style_mode: Some("mixed".to_string()),
                allow_rejudge: false,
            },
        )
        .await?;

    assert_eq!(ret.style_mode, "rational");
    assert_eq!(ret.style_mode_source, "system_config_fallback_default");
    Ok(())
}

#[tokio::test]
async fn request_judge_job_should_reject_user_not_joined() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "judging").await?;
    let user = state.find_user_by_id(1).await?.expect("user should exist");

    let err = state
        .request_judge_job(
            session_id as u64,
            &user,
            RequestJudgeJobInput {
                style_mode: None,
                allow_rejudge: false,
            },
        )
        .await
        .expect_err("should reject non participant");
    assert!(matches!(err, AppError::DebateConflict(_)));
    Ok(())
}

#[tokio::test]
async fn request_judge_job_should_reject_non_judging_session() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "running").await?;
    join_user_to_session(&state, session_id, 1).await?;
    let user = state.find_user_by_id(1).await?.expect("user should exist");

    let err = state
        .request_judge_job(
            session_id as u64,
            &user,
            RequestJudgeJobInput {
                style_mode: None,
                allow_rejudge: false,
            },
        )
        .await
        .expect_err("running status should reject");
    assert!(matches!(err, AppError::DebateConflict(_)));
    Ok(())
}

#[tokio::test]
async fn get_latest_judge_report_should_return_pending_when_job_running() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "judging").await?;
    join_user_to_session(&state, session_id, 1).await?;
    let user = state.find_user_by_id(1).await?.expect("user should exist");

    state
        .request_judge_job(
            session_id as u64,
            &user,
            RequestJudgeJobInput {
                style_mode: None,
                allow_rejudge: false,
            },
        )
        .await?;

    let ret = state
        .get_latest_judge_report(
            session_id as u64,
            &user,
            GetJudgeReportQuery {
                max_stage_count: None,
                stage_offset: None,
            },
        )
        .await?;
    assert_eq!(ret.status, "pending");
    assert!(ret.latest_job.is_some());
    assert!(ret.report.is_none());
    Ok(())
}

#[tokio::test]
async fn get_latest_judge_report_should_return_ready_when_report_exists() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "closed").await?;
    join_user_to_session(&state, session_id, 1).await?;
    let user = state.find_user_by_id(1).await?.expect("user should exist");

    let job_id: (i64,) = sqlx::query_as(
        r#"
            INSERT INTO judge_jobs(
                session_id, requested_by, status, style_mode, requested_at, started_at, finished_at
            )
            VALUES ($1, $2, 'succeeded', 'rational', NOW(), NOW(), NOW())
            RETURNING id
            "#,
    )
    .bind(session_id)
    .bind(1_i64)
    .fetch_one(&state.pool)
    .await?;

    sqlx::query(
        r#"
            INSERT INTO judge_reports(
                session_id, job_id, winner, pro_score, con_score,
                logic_pro, logic_con, evidence_pro, evidence_con, rebuttal_pro, rebuttal_con,
                clarity_pro, clarity_con, pro_summary, con_summary, rationale, style_mode,
                needs_draw_vote, rejudge_triggered, payload
            )
            VALUES (
                $1, $2, 'pro', 82, 74,
                80, 72, 85, 76, 79, 71,
                84, 77, 'pro summary', 'con summary', 'rationale', 'rational',
                false, false, '{"trace":"ok"}'::jsonb
            )
            "#,
    )
    .bind(session_id)
    .bind(job_id.0)
    .execute(&state.pool)
    .await?;

    let ret = state
        .get_latest_judge_report(
            session_id as u64,
            &user,
            GetJudgeReportQuery {
                max_stage_count: None,
                stage_offset: None,
            },
        )
        .await?;
    assert_eq!(ret.status, "ready");
    let report = ret.report.expect("report should exist");
    assert_eq!(report.job_id, job_id.0 as u64);
    assert_eq!(report.winner, "pro");
    assert_eq!(report.pro_score, 82);
    assert_eq!(report.rubric_version, "v1-logic-evidence-rebuttal-clarity");
    assert!(report.verdict_evidence.is_empty());
    assert!(report.stage_summaries.is_empty());
    let meta = report
        .stage_summaries_meta
        .expect("stage summaries meta should exist");
    assert_eq!(meta.total_count, 0);
    assert_eq!(meta.returned_count, 0);
    assert_eq!(meta.stage_offset, 0);
    assert!(!meta.truncated);
    assert!(!meta.has_more);
    assert_eq!(meta.next_offset, None);
    assert_eq!(meta.max_stage_count, None);
    Ok(())
}

#[tokio::test]
async fn get_latest_judge_report_should_return_v3_final_report_when_available() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "closed").await?;
    let user = state.find_user_by_id(1).await?.expect("user should exist");
    let final_job_id = seed_dispatched_final_job(&state, session_id, 1, 2).await?;

    state
        .submit_judge_final_report(
            final_job_id as u64,
            SubmitJudgeFinalReportInput {
                session_id: session_id as u64,
                winner: "draw".to_string(),
                pro_score: 81.5,
                con_score: 81.0,
                dimension_scores: serde_json::json!({
                    "logic": 82.0,
                    "evidence": 80.0,
                    "rebuttal": 79.0,
                    "clarity": 83.0
                }),
                final_rationale: "终局展示文案".to_string(),
                verdict_evidence_refs: vec![serde_json::json!({
                    "phaseNo": 1,
                    "side": "pro",
                    "type": "agent2_hit",
                    "item": "chunk-1"
                })],
                phase_rollup_summary: vec![serde_json::json!({"phaseNo": 1, "winnerHint": "pro"})],
                retrieval_snapshot_rollup: vec![
                    serde_json::json!({"phaseNo": 1, "chunkId": "c-1"}),
                ],
                winner_first: Some("pro".to_string()),
                winner_second: Some("con".to_string()),
                rejudge_triggered: true,
                needs_draw_vote: true,
                judge_trace: serde_json::json!({
                    "pipelineVersion": "v3-final-a9a10-rollup-v2",
                    "factLock": {"winner":"draw"}
                }),
                audit_alerts: vec![serde_json::json!({"type":"consistency_conflict"})],
                error_codes: vec!["consistency_conflict".to_string()],
                degradation_level: 1,
            },
        )
        .await?;

    let ret = state
        .get_latest_judge_report(
            session_id as u64,
            &user,
            GetJudgeReportQuery {
                max_stage_count: None,
                stage_offset: None,
            },
        )
        .await?;
    assert_eq!(ret.status, "ready");
    assert!(ret.report.is_none());
    let final_report = ret.final_report_v3.expect("v3 final report should exist");
    assert_eq!(final_report.final_job_id, final_job_id as u64);
    assert_eq!(final_report.winner, "draw");
    assert!(final_report.needs_draw_vote);
    assert_eq!(final_report.winner_first.as_deref(), Some("pro"));
    assert_eq!(final_report.winner_second.as_deref(), Some("con"));
    assert_eq!(
        final_report.error_codes,
        vec!["consistency_conflict".to_string()]
    );
    assert_eq!(final_report.degradation_level, 1);
    assert_eq!(final_report.verdict_evidence_refs.len(), 1);
    assert_eq!(final_report.phase_rollup_summary.len(), 1);
    let diagnostics = ret
        .final_dispatch_diagnostics
        .expect("final dispatch diagnostics should exist");
    assert_eq!(diagnostics.final_job_id, final_job_id as u64);
    assert_eq!(diagnostics.status, "succeeded");
    assert!(!diagnostics.contract_violation_blocked);
    assert!(diagnostics.error_message.is_none());
    assert!(diagnostics.contract_failure_type.is_none());
    assert!(diagnostics.contract_failure_hint.is_none());
    assert!(diagnostics.contract_failure_action.is_none());
    assert!(ret.final_dispatch_failure_stats.is_none());
    Ok(())
}

#[tokio::test]
async fn get_latest_judge_report_should_surface_final_contract_block_diagnostics() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "closed").await?;
    let user = state.find_user_by_id(1).await?.expect("user should exist");
    let final_job_id = seed_failed_final_job(
        &state,
        session_id,
        1,
        3,
        "[http_5xx] final dispatch request failed: status=502 Bad Gateway, body={\"detail\":\"final_contract_blocked: missing_critical_fields\"}",
    )
    .await?;

    let ret = state
        .get_latest_judge_report(
            session_id as u64,
            &user,
            GetJudgeReportQuery {
                max_stage_count: None,
                stage_offset: None,
            },
        )
        .await?;
    assert_eq!(ret.status, "failed");
    assert!(ret.report.is_none());
    assert!(ret.final_report_v3.is_none());

    let diagnostics = ret
        .final_dispatch_diagnostics
        .expect("final dispatch diagnostics should exist");
    assert_eq!(diagnostics.final_job_id, final_job_id as u64);
    assert_eq!(diagnostics.status, "failed");
    assert_eq!(diagnostics.error_code.as_deref(), Some("http_5xx"));
    assert_eq!(
        diagnostics.contract_failure_type.as_deref(),
        Some("final_contract_blocked")
    );
    assert_eq!(
        diagnostics.contract_failure_action.as_deref(),
        Some("check_phase_artifacts_then_retry")
    );
    assert!(diagnostics
        .contract_failure_hint
        .as_deref()
        .unwrap_or_default()
        .contains("合同校验阻断"));
    assert!(diagnostics.contract_violation_blocked);
    assert!(diagnostics
        .error_message
        .unwrap_or_default()
        .contains("final_contract_blocked"));
    let stats = ret
        .final_dispatch_failure_stats
        .expect("failure stats should exist");
    assert_eq!(stats.total_failed_jobs, 1);
    assert_eq!(stats.unknown_failed_jobs, 0);
    assert_eq!(stats.by_type.len(), 1);
    assert_eq!(stats.by_type[0].failure_type, "final_contract_blocked");
    assert_eq!(stats.by_type[0].count, 1);
    Ok(())
}

#[tokio::test]
async fn get_latest_judge_report_should_map_contract_failure_type_for_accepted_false() -> Result<()>
{
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "closed").await?;
    let user = state.find_user_by_id(1).await?.expect("user should exist");
    seed_failed_final_job(
        &state,
        session_id,
        1,
        2,
        "[response_accepted_false] final dispatch response rejected: accepted=false, status=queued",
    )
    .await?;

    let ret = state
        .get_latest_judge_report(
            session_id as u64,
            &user,
            GetJudgeReportQuery {
                max_stage_count: None,
                stage_offset: None,
            },
        )
        .await?;
    assert_eq!(ret.status, "failed");
    let diagnostics = ret
        .final_dispatch_diagnostics
        .expect("final dispatch diagnostics should exist");
    assert_eq!(
        diagnostics.contract_failure_type.as_deref(),
        Some("response_accepted_false")
    );
    assert_eq!(
        diagnostics.contract_failure_action.as_deref(),
        Some("check_ai_judge_acceptance_then_retry")
    );
    assert!(!diagnostics.contract_violation_blocked);
    let stats = ret
        .final_dispatch_failure_stats
        .expect("failure stats should exist");
    assert_eq!(stats.total_failed_jobs, 1);
    assert_eq!(stats.unknown_failed_jobs, 0);
    assert_eq!(stats.by_type[0].failure_type, "response_accepted_false");
    Ok(())
}

#[tokio::test]
async fn get_latest_judge_report_should_map_contract_failure_type_for_job_id_mismatch() -> Result<()>
{
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "closed").await?;
    let user = state.find_user_by_id(1).await?.expect("user should exist");
    seed_failed_final_job(
        &state,
        session_id,
        1,
        2,
        "[response_job_id_mismatch] final dispatch response job_id mismatch: expected=100, got=101",
    )
    .await?;

    let ret = state
        .get_latest_judge_report(
            session_id as u64,
            &user,
            GetJudgeReportQuery {
                max_stage_count: None,
                stage_offset: None,
            },
        )
        .await?;
    assert_eq!(ret.status, "failed");
    let diagnostics = ret
        .final_dispatch_diagnostics
        .expect("final dispatch diagnostics should exist");
    assert_eq!(
        diagnostics.contract_failure_type.as_deref(),
        Some("response_job_id_mismatch")
    );
    assert_eq!(
        diagnostics.contract_failure_action.as_deref(),
        Some("check_dispatch_contract_alignment")
    );
    assert!(!diagnostics.contract_violation_blocked);
    Ok(())
}

#[tokio::test]
async fn get_latest_judge_report_should_fallback_unknown_contract_failure_type_for_failed_job(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "closed").await?;
    let user = state.find_user_by_id(1).await?.expect("user should exist");
    seed_failed_final_job(
        &state,
        session_id,
        1,
        2,
        "[http_5xx] final dispatch request failed: status=502 Bad Gateway, body={\"detail\":\"runtime_timeout_without_contract_code\"}",
    )
    .await?;

    let ret = state
        .get_latest_judge_report(
            session_id as u64,
            &user,
            GetJudgeReportQuery {
                max_stage_count: None,
                stage_offset: None,
            },
        )
        .await?;
    assert_eq!(ret.status, "failed");
    let diagnostics = ret
        .final_dispatch_diagnostics
        .expect("final dispatch diagnostics should exist");
    assert_eq!(
        diagnostics.contract_failure_type.as_deref(),
        Some("unknown_contract_failure")
    );
    assert_eq!(
        diagnostics.contract_failure_action.as_deref(),
        Some("inspect_error_then_retry_or_escalate")
    );
    assert!(diagnostics
        .contract_failure_hint
        .as_deref()
        .unwrap_or_default()
        .contains("未识别"));

    let stats = ret
        .final_dispatch_failure_stats
        .expect("failure stats should exist");
    assert_eq!(stats.total_failed_jobs, 1);
    assert_eq!(stats.unknown_failed_jobs, 1);
    assert_eq!(stats.by_type[0].failure_type, "unknown_contract_failure");
    assert_eq!(stats.by_type[0].count, 1);
    Ok(())
}

#[tokio::test]
async fn get_latest_judge_report_should_include_stage_summaries() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "closed").await?;
    let user = state.find_user_by_id(1).await?.expect("user should exist");
    let job_id = seed_running_judge_job(&state, session_id).await?;

    state
        .submit_judge_report(
            job_id as u64,
            SubmitJudgeReportInput {
                winner: "pro".to_string(),
                pro_score: 83,
                con_score: 77,
                logic_pro: 82,
                logic_con: 75,
                evidence_pro: 84,
                evidence_con: 78,
                rebuttal_pro: 81,
                rebuttal_con: 76,
                clarity_pro: 85,
                clarity_con: 79,
                pro_summary: "pro summary".to_string(),
                con_summary: "con summary".to_string(),
                rationale: "rationale".to_string(),
                style_mode: Some("rational".to_string()),
                needs_draw_vote: false,
                rejudge_triggered: false,
                payload: serde_json::json!({"trace":"with-stages"}),
                winner_first: Some("pro".to_string()),
                winner_second: Some("pro".to_string()),
                stage_summaries: vec![
                    JudgeStageSummaryInput {
                        stage_no: 2,
                        from_message_id: Some(101),
                        to_message_id: Some(200),
                        pro_score: 84,
                        con_score: 77,
                        summary: serde_json::json!({"brief":"s2"}),
                    },
                    JudgeStageSummaryInput {
                        stage_no: 1,
                        from_message_id: Some(1),
                        to_message_id: Some(100),
                        pro_score: 82,
                        con_score: 76,
                        summary: serde_json::json!({"brief":"s1"}),
                    },
                ],
            },
        )
        .await?;

    let ret = state
        .get_latest_judge_report(
            session_id as u64,
            &user,
            GetJudgeReportQuery {
                max_stage_count: None,
                stage_offset: None,
            },
        )
        .await?;
    assert_eq!(ret.status, "ready");
    let report = ret.report.expect("report should exist");
    assert_eq!(report.rubric_version, "v1-logic-evidence-rebuttal-clarity");
    assert!(report.verdict_evidence.is_empty());
    assert_eq!(report.stage_summaries.len(), 2);
    assert_eq!(report.stage_summaries[0].stage_no, 1);
    assert_eq!(report.stage_summaries[0].from_message_id, Some(1));
    assert_eq!(report.stage_summaries[0].to_message_id, Some(100));
    assert_eq!(report.stage_summaries[1].stage_no, 2);
    assert_eq!(report.stage_summaries[1].from_message_id, Some(101));
    assert_eq!(report.stage_summaries[1].to_message_id, Some(200));
    let meta = report
        .stage_summaries_meta
        .expect("stage summaries meta should exist");
    assert_eq!(meta.total_count, 2);
    assert_eq!(meta.returned_count, 2);
    assert_eq!(meta.stage_offset, 0);
    assert!(!meta.truncated);
    assert!(!meta.has_more);
    assert_eq!(meta.next_offset, None);
    assert_eq!(meta.max_stage_count, None);
    Ok(())
}

#[tokio::test]
async fn get_latest_judge_report_should_limit_stage_summaries_by_query() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "closed").await?;
    let user = state.find_user_by_id(1).await?.expect("user should exist");
    let job_id = seed_running_judge_job(&state, session_id).await?;

    state
        .submit_judge_report(
            job_id as u64,
            SubmitJudgeReportInput {
                winner: "con".to_string(),
                pro_score: 70,
                con_score: 85,
                logic_pro: 72,
                logic_con: 84,
                evidence_pro: 69,
                evidence_con: 86,
                rebuttal_pro: 71,
                rebuttal_con: 83,
                clarity_pro: 68,
                clarity_con: 87,
                pro_summary: "pro".to_string(),
                con_summary: "con".to_string(),
                rationale: "rationale".to_string(),
                style_mode: Some("rational".to_string()),
                needs_draw_vote: false,
                rejudge_triggered: false,
                payload: serde_json::json!({"trace":"limit-stages"}),
                winner_first: Some("con".to_string()),
                winner_second: Some("con".to_string()),
                stage_summaries: vec![
                    JudgeStageSummaryInput {
                        stage_no: 1,
                        from_message_id: Some(1),
                        to_message_id: Some(100),
                        pro_score: 70,
                        con_score: 80,
                        summary: serde_json::json!({"brief":"s1"}),
                    },
                    JudgeStageSummaryInput {
                        stage_no: 2,
                        from_message_id: Some(101),
                        to_message_id: Some(200),
                        pro_score: 71,
                        con_score: 82,
                        summary: serde_json::json!({"brief":"s2"}),
                    },
                    JudgeStageSummaryInput {
                        stage_no: 3,
                        from_message_id: Some(201),
                        to_message_id: Some(300),
                        pro_score: 72,
                        con_score: 85,
                        summary: serde_json::json!({"brief":"s3"}),
                    },
                ],
            },
        )
        .await?;

    let ret = state
        .get_latest_judge_report(
            session_id as u64,
            &user,
            GetJudgeReportQuery {
                max_stage_count: Some(1),
                stage_offset: None,
            },
        )
        .await?;
    let report = ret.report.expect("report should exist");
    assert_eq!(report.stage_summaries.len(), 1);
    assert_eq!(report.stage_summaries[0].stage_no, 1);
    let meta = report
        .stage_summaries_meta
        .expect("stage summaries meta should exist");
    assert_eq!(meta.total_count, 3);
    assert_eq!(meta.returned_count, 1);
    assert_eq!(meta.stage_offset, 0);
    assert!(meta.truncated);
    assert!(meta.has_more);
    assert_eq!(meta.next_offset, Some(1));
    assert_eq!(meta.max_stage_count, Some(1));
    Ok(())
}

#[tokio::test]
async fn get_latest_judge_report_should_apply_stage_offset() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "closed").await?;
    let user = state.find_user_by_id(1).await?.expect("user should exist");
    let job_id = seed_running_judge_job(&state, session_id).await?;

    state
        .submit_judge_report(
            job_id as u64,
            SubmitJudgeReportInput {
                winner: "pro".to_string(),
                pro_score: 88,
                con_score: 77,
                logic_pro: 87,
                logic_con: 76,
                evidence_pro: 89,
                evidence_con: 78,
                rebuttal_pro: 86,
                rebuttal_con: 75,
                clarity_pro: 90,
                clarity_con: 79,
                pro_summary: "pro".to_string(),
                con_summary: "con".to_string(),
                rationale: "rationale".to_string(),
                style_mode: Some("rational".to_string()),
                needs_draw_vote: false,
                rejudge_triggered: false,
                payload: serde_json::json!({"trace":"offset-stages"}),
                winner_first: Some("pro".to_string()),
                winner_second: Some("pro".to_string()),
                stage_summaries: vec![
                    JudgeStageSummaryInput {
                        stage_no: 1,
                        from_message_id: Some(1),
                        to_message_id: Some(100),
                        pro_score: 85,
                        con_score: 76,
                        summary: serde_json::json!({"brief":"s1"}),
                    },
                    JudgeStageSummaryInput {
                        stage_no: 2,
                        from_message_id: Some(101),
                        to_message_id: Some(200),
                        pro_score: 88,
                        con_score: 77,
                        summary: serde_json::json!({"brief":"s2"}),
                    },
                    JudgeStageSummaryInput {
                        stage_no: 3,
                        from_message_id: Some(201),
                        to_message_id: Some(300),
                        pro_score: 89,
                        con_score: 78,
                        summary: serde_json::json!({"brief":"s3"}),
                    },
                ],
            },
        )
        .await?;

    let ret = state
        .get_latest_judge_report(
            session_id as u64,
            &user,
            GetJudgeReportQuery {
                max_stage_count: Some(1),
                stage_offset: Some(1),
            },
        )
        .await?;
    let report = ret.report.expect("report should exist");
    assert_eq!(report.stage_summaries.len(), 1);
    assert_eq!(report.stage_summaries[0].stage_no, 2);
    let meta = report
        .stage_summaries_meta
        .expect("stage summaries meta should exist");
    assert_eq!(meta.total_count, 3);
    assert_eq!(meta.returned_count, 1);
    assert_eq!(meta.stage_offset, 1);
    assert!(meta.truncated);
    assert!(meta.has_more);
    assert_eq!(meta.next_offset, Some(2));
    assert_eq!(meta.max_stage_count, Some(1));
    Ok(())
}

#[tokio::test]
async fn get_latest_judge_report_should_resolve_verdict_evidence_refs() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "closed").await?;
    let user = state.find_user_by_id(1).await?.expect("user should exist");
    let job_id = seed_running_judge_job(&state, session_id).await?;
    let msg1 = seed_session_message(&state, session_id, 1, "pro", "pro evidence with data").await?;
    let msg2 = seed_session_message(&state, session_id, 2, "con", "con rebuttal however").await?;

    state
        .submit_judge_report(
            job_id as u64,
            SubmitJudgeReportInput {
                winner: "pro".to_string(),
                pro_score: 88,
                con_score: 80,
                logic_pro: 87,
                logic_con: 79,
                evidence_pro: 89,
                evidence_con: 81,
                rebuttal_pro: 86,
                rebuttal_con: 78,
                clarity_pro: 90,
                clarity_con: 82,
                pro_summary: "pro".to_string(),
                con_summary: "con".to_string(),
                rationale: "rationale".to_string(),
                style_mode: Some("rational".to_string()),
                needs_draw_vote: false,
                rejudge_triggered: false,
                payload: serde_json::json!({
                    "trace":"evidence-refs",
                    "verdictEvidenceRefs":[
                        {"messageId": msg1, "side":"pro", "role":"winner_support", "reason":"包含数据"},
                        {"messageId": msg2, "side":"con", "role":"opponent_point", "reason":"包含反驳"}
                    ]
                }),
                winner_first: Some("pro".to_string()),
                winner_second: Some("pro".to_string()),
                stage_summaries: vec![],
            },
        )
        .await?;

    let ret = state
        .get_latest_judge_report(
            session_id as u64,
            &user,
            GetJudgeReportQuery {
                max_stage_count: None,
                stage_offset: None,
            },
        )
        .await?;
    let report = ret.report.expect("report should exist");
    assert_eq!(report.verdict_evidence.len(), 2);
    assert_eq!(report.verdict_evidence[0].message_id, msg1 as u64);
    assert_eq!(report.verdict_evidence[0].side, "pro");
    assert_eq!(
        report.verdict_evidence[0].role.as_deref(),
        Some("winner_support")
    );
    assert_eq!(report.verdict_evidence[1].message_id, msg2 as u64);
    assert_eq!(report.verdict_evidence[1].side, "con");
    assert_eq!(
        report.verdict_evidence[1].reason.as_deref(),
        Some("包含反驳")
    );
    Ok(())
}

#[tokio::test]
async fn list_judge_reviews_by_owner_should_filter_anomaly_and_evidence() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");

    let normal_session = seed_topic_and_session(&state, "closed").await?;
    let normal_job = seed_running_judge_job(&state, normal_session).await?;
    let normal_msg =
        seed_session_message(&state, normal_session, 1, "pro", "normal evidence line").await?;
    state
        .submit_judge_report(
            normal_job as u64,
            SubmitJudgeReportInput {
                winner: "pro".to_string(),
                pro_score: 90,
                con_score: 70,
                logic_pro: 89,
                logic_con: 71,
                evidence_pro: 91,
                evidence_con: 72,
                rebuttal_pro: 88,
                rebuttal_con: 73,
                clarity_pro: 90,
                clarity_con: 74,
                pro_summary: "pro".to_string(),
                con_summary: "con".to_string(),
                rationale: "rationale".to_string(),
                style_mode: Some("rational".to_string()),
                needs_draw_vote: false,
                rejudge_triggered: false,
                payload: serde_json::json!({
                    "verdictEvidenceRefs":[
                        {"messageId": normal_msg, "side":"pro", "role":"winner_support", "reason":"evidence"}
                    ]
                }),
                winner_first: Some("pro".to_string()),
                winner_second: Some("pro".to_string()),
                stage_summaries: vec![],
            },
        )
        .await?;

    let abnormal_session = seed_topic_and_session(&state, "closed").await?;
    let abnormal_job = seed_running_judge_job(&state, abnormal_session).await?;
    state
        .submit_judge_report(
            abnormal_job as u64,
            SubmitJudgeReportInput {
                winner: "pro".to_string(),
                pro_score: 81,
                con_score: 79,
                logic_pro: 80,
                logic_con: 78,
                evidence_pro: 80,
                evidence_con: 79,
                rebuttal_pro: 81,
                rebuttal_con: 78,
                clarity_pro: 80,
                clarity_con: 79,
                pro_summary: "pro".to_string(),
                con_summary: "con".to_string(),
                rationale: "rationale".to_string(),
                style_mode: Some("rational".to_string()),
                needs_draw_vote: false,
                rejudge_triggered: false,
                payload: serde_json::json!({"trace":"abnormal-no-evidence"}),
                winner_first: Some("pro".to_string()),
                winner_second: Some("con".to_string()),
                stage_summaries: vec![],
            },
        )
        .await?;

    let ret = state
        .list_judge_reviews_by_owner(
            &owner,
            ListJudgeReviewOpsQuery {
                from: None,
                to: None,
                winner: Some("pro".to_string()),
                rejudge_triggered: Some(false),
                has_verdict_evidence: Some(false),
                anomaly_only: true,
                limit: Some(20),
            },
        )
        .await?;

    assert!(ret.scanned_count >= 1);
    assert_eq!(ret.returned_count, 1);
    assert_eq!(ret.items.len(), 1);
    let item = &ret.items[0];
    assert_eq!(item.session_id, abnormal_session as u64);
    assert!(!item.has_verdict_evidence);
    assert!(item
        .abnormal_flags
        .iter()
        .any(|v| v == "missing_verdict_evidence_refs"));
    assert!(item
        .abnormal_flags
        .iter()
        .any(|v| v == "winner_inconsistent_between_two_passes"));
    Ok(())
}

#[tokio::test]
async fn get_judge_final_dispatch_failure_stats_by_owner_should_aggregate_by_type() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");

    let session_a = seed_topic_and_session(&state, "closed").await?;
    let session_b = seed_topic_and_session(&state, "closed").await?;
    let session_c = seed_topic_and_session(&state, "closed").await?;
    seed_failed_final_job(
        &state,
        session_a,
        1,
        2,
        "[response_accepted_false] final dispatch response rejected: accepted=false, status=queued",
    )
    .await?;
    seed_failed_final_job(
        &state,
        session_b,
        1,
        2,
        "[response_job_id_mismatch] final dispatch response job_id mismatch: expected=100, got=101",
    )
    .await?;
    seed_failed_final_job(
        &state,
        session_c,
        1,
        2,
        "[http_5xx] final dispatch request failed: status=500, body={\"detail\":\"opaque_runtime_error\"}",
    )
    .await?;

    let ret = state
        .get_judge_final_dispatch_failure_stats_by_owner(
            &owner,
            GetJudgeFinalDispatchFailureStatsQuery {
                from: None,
                to: None,
                limit: None,
            },
        )
        .await?;

    assert_eq!(ret.total_failed_jobs, 3);
    assert_eq!(ret.scanned_failed_jobs, 3);
    assert!(!ret.truncated);
    assert_eq!(ret.unknown_failed_jobs, 1);
    assert_eq!(ret.by_type.len(), 3);
    assert!(ret
        .by_type
        .iter()
        .any(|item| item.failure_type == "response_accepted_false" && item.count == 1));
    assert!(ret
        .by_type
        .iter()
        .any(|item| item.failure_type == "response_job_id_mismatch" && item.count == 1));
    assert!(ret
        .by_type
        .iter()
        .any(|item| item.failure_type == "unknown_contract_failure" && item.count == 1));
    Ok(())
}

#[tokio::test]
async fn get_judge_final_dispatch_failure_stats_by_owner_should_apply_scan_limit_and_mark_truncated(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");

    let session_a = seed_topic_and_session(&state, "closed").await?;
    let session_b = seed_topic_and_session(&state, "closed").await?;
    let session_c = seed_topic_and_session(&state, "closed").await?;
    seed_failed_final_job(
        &state,
        session_a,
        1,
        2,
        "[response_accepted_false] final dispatch response rejected: accepted=false, status=queued",
    )
    .await?;
    seed_failed_final_job(
        &state,
        session_b,
        1,
        2,
        "[response_accepted_false] final dispatch response rejected: accepted=false, status=queued",
    )
    .await?;
    seed_failed_final_job(
        &state,
        session_c,
        1,
        2,
        "[response_accepted_false] final dispatch response rejected: accepted=false, status=queued",
    )
    .await?;

    let ret = state
        .get_judge_final_dispatch_failure_stats_by_owner(
            &owner,
            GetJudgeFinalDispatchFailureStatsQuery {
                from: None,
                to: None,
                limit: Some(2),
            },
        )
        .await?;

    assert_eq!(ret.total_failed_jobs, 3);
    assert_eq!(ret.scanned_failed_jobs, 2);
    assert!(ret.truncated);
    assert_eq!(ret.unknown_failed_jobs, 0);
    assert_eq!(ret.by_type.len(), 1);
    assert_eq!(ret.by_type[0].failure_type, "response_accepted_false");
    assert_eq!(ret.by_type[0].count, 2);
    Ok(())
}

#[tokio::test]
async fn list_judge_trace_replay_by_owner_should_aggregate_phase_and_final() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");
    let session_id = seed_topic_and_session(&state, "closed").await?;

    let message_start = seed_session_message(&state, session_id, 1, "pro", "phase start").await?;
    let message_end = seed_session_message(&state, session_id, 1, "con", "phase end").await?;
    let phase_job_id: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO judge_phase_jobs(
            session_id, phase_no, message_start_id, message_end_id, message_count,
            status, trace_id, idempotency_key, rubric_version, judge_policy_version,
            topic_domain, retrieval_profile, dispatch_attempts, last_dispatch_at, error_message
        )
        VALUES (
            $1, 1, $2, $3, 100,
            'failed', $4, $5, 'v3', 'v3-default',
            'default', 'default', 2, NOW(), $6
        )
        RETURNING id
        "#,
    )
    .bind(session_id)
    .bind(message_start)
    .bind(message_end)
    .bind(format!("trace-phase-{session_id}-1"))
    .bind(format!("judge_phase:{session_id}:1:v3:v3-default"))
    .bind("[http_5xx] phase dispatch request failed: status=500")
    .fetch_one(&state.pool)
    .await?;
    let phase_report_id: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO judge_phase_reports(
            phase_job_id, session_id, phase_no, message_start_id, message_end_id, message_count,
            pro_summary_grounded, con_summary_grounded,
            pro_retrieval_bundle, con_retrieval_bundle,
            agent1_score, agent2_score, agent3_weighted_score,
            prompt_hashes, token_usage, latency_ms, error_codes, degradation_level, judge_trace
        )
        VALUES (
            $1, $2, 1, $3, $4, 100,
            '{}'::jsonb, '{}'::jsonb,
            '{}'::jsonb, '{}'::jsonb,
            '{}'::jsonb, '{}'::jsonb, '{}'::jsonb,
            '{}'::jsonb, '{}'::jsonb, '{}'::jsonb, '[]'::jsonb, 0, '{}'::jsonb
        )
        RETURNING id
        "#,
    )
    .bind(phase_job_id.0)
    .bind(session_id)
    .bind(message_start)
    .bind(message_end)
    .fetch_one(&state.pool)
    .await?;

    let final_job_id = seed_failed_final_job(
        &state,
        session_id,
        1,
        1,
        "[final_contract_blocked] missing final report fields",
    )
    .await?;
    let final_report_id: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO judge_final_reports(
            final_job_id, session_id, winner, pro_score, con_score,
            dimension_scores, final_rationale, verdict_evidence_refs,
            phase_rollup_summary, retrieval_snapshot_rollup,
            winner_first, winner_second, rejudge_triggered, needs_draw_vote,
            judge_trace, audit_alerts, error_codes, degradation_level
        )
        VALUES (
            $1, $2, 'draw', 75, 75,
            '{}'::jsonb, 'trace replay test', '[]'::jsonb,
            '[]'::jsonb, '[]'::jsonb,
            'draw', 'draw', false, true,
            '{}'::jsonb, '[]'::jsonb, '[]'::jsonb, 0
        )
        RETURNING id
        "#,
    )
    .bind(final_job_id)
    .bind(session_id)
    .fetch_one(&state.pool)
    .await?;

    let ret = state
        .list_judge_trace_replay_by_owner(
            &owner,
            ListJudgeTraceReplayOpsQuery {
                from: None,
                to: None,
                session_id: None,
                scope: None,
                status: None,
                limit: Some(20),
            },
        )
        .await?;

    assert_eq!(ret.returned_count, 2);
    assert_eq!(ret.phase_count, 1);
    assert_eq!(ret.final_count, 1);
    assert_eq!(ret.failed_count, 2);
    assert_eq!(ret.replay_eligible_count, 2);

    let phase_item = ret
        .items
        .iter()
        .find(|item| item.scope == "phase")
        .expect("phase item should exist");
    assert_eq!(phase_item.phase_job_id, Some(phase_job_id.0 as u64));
    assert_eq!(phase_item.phase_report_id, Some(phase_report_id.0 as u64));
    assert_eq!(phase_item.error_code.as_deref(), Some("http_5xx"));
    assert!(phase_item.contract_failure_type.is_none());
    assert_eq!(
        phase_item.replay_recommendation.as_deref(),
        Some("replay_phase_job")
    );

    let final_item = ret
        .items
        .iter()
        .find(|item| item.scope == "final")
        .expect("final item should exist");
    assert_eq!(final_item.final_job_id, Some(final_job_id as u64));
    assert_eq!(final_item.final_report_id, Some(final_report_id.0 as u64));
    assert_eq!(
        final_item.contract_failure_type.as_deref(),
        Some("final_contract_blocked")
    );
    assert_eq!(
        final_item.replay_recommendation.as_deref(),
        Some("replay_final_job")
    );
    Ok(())
}

#[tokio::test]
async fn list_judge_trace_replay_by_owner_should_apply_scope_status_and_session_filters(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");

    let session_a = seed_topic_and_session(&state, "closed").await?;
    let session_b = seed_topic_and_session(&state, "closed").await?;
    seed_failed_final_job(
        &state,
        session_a,
        1,
        1,
        "[response_accepted_false] final dispatch response rejected: accepted=false, status=queued",
    )
    .await?;
    seed_dispatched_final_job(&state, session_b, 1, 1).await?;

    let ret = state
        .list_judge_trace_replay_by_owner(
            &owner,
            ListJudgeTraceReplayOpsQuery {
                from: None,
                to: None,
                session_id: Some(session_a as u64),
                scope: Some("final".to_string()),
                status: Some("failed".to_string()),
                limit: Some(20),
            },
        )
        .await?;

    assert_eq!(ret.returned_count, 1);
    assert_eq!(ret.phase_count, 0);
    assert_eq!(ret.final_count, 1);
    assert_eq!(ret.failed_count, 1);
    assert_eq!(ret.items[0].session_id, session_a as u64);
    assert_eq!(ret.items[0].scope, "final");
    assert_eq!(ret.items[0].status, "failed");
    Ok(())
}

#[tokio::test]
async fn get_judge_replay_preview_by_owner_should_return_phase_snapshot() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");
    let session_id = seed_topic_and_session(&state, "closed").await?;

    let message_start =
        seed_session_message(&state, session_id, 1, "pro", "preview phase start").await?;
    let message_end =
        seed_session_message(&state, session_id, 2, "con", "preview phase end").await?;
    let phase_job_id: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO judge_phase_jobs(
            session_id, phase_no, message_start_id, message_end_id, message_count,
            status, trace_id, idempotency_key, rubric_version, judge_policy_version,
            topic_domain, retrieval_profile, dispatch_attempts, last_dispatch_at, error_message
        )
        VALUES (
            $1, 1, $2, $3, 2,
            'failed', $4, $5, 'v3', 'v3-default',
            'default', 'default', 2, NOW(), $6
        )
        RETURNING id
        "#,
    )
    .bind(session_id)
    .bind(message_start)
    .bind(message_end)
    .bind(format!("trace-phase-preview-{session_id}"))
    .bind(format!("judge_phase_preview:{session_id}:1:v3:v3-default"))
    .bind("[http_5xx] phase dispatch request failed")
    .fetch_one(&state.pool)
    .await?;

    let ret = state
        .get_judge_replay_preview_by_owner(
            &owner,
            GetJudgeReplayPreviewOpsQuery {
                scope: "phase".to_string(),
                job_id: phase_job_id.0 as u64,
            },
        )
        .await?;

    assert!(ret.side_effect_free);
    assert_eq!(ret.meta.scope, "phase");
    assert_eq!(ret.meta.job_id, phase_job_id.0 as u64);
    assert_eq!(ret.meta.phase_no, Some(1));
    assert!(ret.meta.replay_eligible);
    assert!(ret.meta.replay_block_reason.is_none());
    assert_eq!(ret.request_snapshot["job_id"], phase_job_id.0 as u64);
    assert_eq!(
        ret.request_snapshot["messages"]
            .as_array()
            .expect("messages should be array")
            .len(),
        2
    );
    assert_eq!(ret.snapshot_hash.len(), 40);
    Ok(())
}

#[tokio::test]
async fn get_judge_replay_preview_by_owner_should_return_final_snapshot_and_terminal_hint(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");
    let session_id = seed_topic_and_session(&state, "closed").await?;
    let final_job_id = seed_dispatched_final_job(&state, session_id, 1, 2).await?;

    let ret = state
        .get_judge_replay_preview_by_owner(
            &owner,
            GetJudgeReplayPreviewOpsQuery {
                scope: "final".to_string(),
                job_id: final_job_id as u64,
            },
        )
        .await?;

    assert!(ret.side_effect_free);
    assert_eq!(ret.meta.scope, "final");
    assert_eq!(ret.meta.job_id, final_job_id as u64);
    assert_eq!(ret.meta.phase_start_no, Some(1));
    assert_eq!(ret.meta.phase_end_no, Some(2));
    assert!(!ret.meta.replay_eligible);
    assert_eq!(
        ret.meta.replay_block_reason.as_deref(),
        Some("job_status_not_terminal")
    );
    assert_eq!(ret.request_snapshot["job_id"], final_job_id as u64);
    assert_eq!(ret.request_snapshot["phase_start_no"], 1);
    assert_eq!(ret.request_snapshot["phase_end_no"], 2);
    assert_eq!(ret.snapshot_hash.len(), 40);
    Ok(())
}

#[tokio::test]
async fn execute_judge_replay_by_owner_should_requeue_failed_phase_and_write_audit() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");
    let session_id = seed_topic_and_session(&state, "closed").await?;

    let message_start = seed_session_message(&state, session_id, 1, "pro", "replay start").await?;
    let message_end = seed_session_message(&state, session_id, 2, "con", "replay end").await?;
    let old_trace_id = format!("trace-phase-replay-exec-{session_id}");
    let old_idempotency_key = format!("judge_phase_replay_exec:{session_id}:1:v3:v3-default");
    let phase_job_id: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO judge_phase_jobs(
            session_id, phase_no, message_start_id, message_end_id, message_count,
            status, trace_id, idempotency_key, rubric_version, judge_policy_version,
            topic_domain, retrieval_profile, dispatch_attempts, last_dispatch_at, error_message
        )
        VALUES (
            $1, 1, $2, $3, 2,
            'failed', $4, $5, 'v3', 'v3-default',
            'default', 'default', 3, NOW(), $6
        )
        RETURNING id
        "#,
    )
    .bind(session_id)
    .bind(message_start)
    .bind(message_end)
    .bind(&old_trace_id)
    .bind(&old_idempotency_key)
    .bind("[http_5xx] phase dispatch request failed")
    .fetch_one(&state.pool)
    .await?;

    let ret = state
        .execute_judge_replay_by_owner(
            &owner,
            ExecuteJudgeReplayOpsInput {
                scope: "phase".to_string(),
                job_id: phase_job_id.0 as u64,
                reason: Some("manual replay".to_string()),
            },
        )
        .await?;

    assert_eq!(ret.scope, "phase");
    assert_eq!(ret.job_id, phase_job_id.0 as u64);
    assert_eq!(ret.previous_status, "failed");
    assert_eq!(ret.new_status, "queued");
    assert_ne!(ret.new_trace_id, old_trace_id);
    assert_ne!(ret.new_idempotency_key, old_idempotency_key);

    let phase_row: (String, i32, Option<String>, String, String) = sqlx::query_as(
        r#"
        SELECT status, dispatch_attempts, error_message, trace_id, idempotency_key
        FROM judge_phase_jobs
        WHERE id = $1
        "#,
    )
    .bind(phase_job_id.0)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(phase_row.0, "queued");
    assert_eq!(phase_row.1, 0);
    assert!(phase_row.2.is_none());
    assert_eq!(phase_row.3, ret.new_trace_id);
    assert_eq!(phase_row.4, ret.new_idempotency_key);

    let audit_row: (String, i64, i64, String, String) = sqlx::query_as(
        r#"
        SELECT scope, job_id, session_id, previous_status, new_status
        FROM judge_replay_actions
        WHERE id = $1
        "#,
    )
    .bind(ret.audit_id as i64)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(audit_row.0, "phase");
    assert_eq!(audit_row.1, phase_job_id.0);
    assert_eq!(audit_row.2, session_id);
    assert_eq!(audit_row.3, "failed");
    assert_eq!(audit_row.4, "queued");
    Ok(())
}

#[tokio::test]
async fn execute_judge_replay_by_owner_should_reject_non_failed_final_job() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");
    let session_id = seed_topic_and_session(&state, "closed").await?;
    let final_job_id = seed_dispatched_final_job(&state, session_id, 1, 2).await?;

    let err = state
        .execute_judge_replay_by_owner(
            &owner,
            ExecuteJudgeReplayOpsInput {
                scope: "final".to_string(),
                job_id: final_job_id as u64,
                reason: Some("should fail".to_string()),
            },
        )
        .await
        .expect_err("dispatched job should be rejected");
    assert!(matches!(err, AppError::DebateConflict(_)));
    Ok(())
}

#[tokio::test]
async fn request_judge_rejudge_by_owner_should_enforce_owner_and_report_requirements() -> Result<()>
{
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");
    let non_owner = state
        .find_user_by_id(2)
        .await?
        .expect("non owner should exist");

    let session_id = seed_topic_and_session(&state, "closed").await?;

    let non_owner_err = state
        .request_judge_rejudge_by_owner(session_id as u64, &non_owner)
        .await
        .expect_err("non owner should be rejected");
    assert!(matches!(non_owner_err, AppError::DebateConflict(_)));

    let no_report_err = state
        .request_judge_rejudge_by_owner(session_id as u64, &owner)
        .await
        .expect_err("should require existing report first");
    assert!(matches!(no_report_err, AppError::DebateConflict(_)));

    let job_id = seed_running_judge_job(&state, session_id).await?;
    state
        .submit_judge_report(
            job_id as u64,
            SubmitJudgeReportInput {
                winner: "con".to_string(),
                pro_score: 70,
                con_score: 89,
                logic_pro: 71,
                logic_con: 88,
                evidence_pro: 69,
                evidence_con: 90,
                rebuttal_pro: 72,
                rebuttal_con: 87,
                clarity_pro: 70,
                clarity_con: 89,
                pro_summary: "pro".to_string(),
                con_summary: "con".to_string(),
                rationale: "rationale".to_string(),
                style_mode: Some("rational".to_string()),
                needs_draw_vote: false,
                rejudge_triggered: false,
                payload: serde_json::json!({"trace":"initial-report"}),
                winner_first: Some("con".to_string()),
                winner_second: Some("con".to_string()),
                stage_summaries: vec![],
            },
        )
        .await?;

    let first = state
        .request_judge_rejudge_by_owner(session_id as u64, &owner)
        .await?;
    assert!(first.newly_created);
    assert!(first.rejudge_triggered);
    assert_eq!(first.status, "running");

    let second = state
        .request_judge_rejudge_by_owner(session_id as u64, &owner)
        .await?;
    assert!(!second.newly_created);
    assert_eq!(second.job_id, first.job_id);
    assert_eq!(second.style_mode_source, "existing_running_job");
    Ok(())
}

#[tokio::test]
async fn list_judge_reviews_by_owner_should_allow_ops_viewer_but_forbid_rejudge() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");
    let ops_viewer = state
        .find_user_by_id(2)
        .await?
        .expect("viewer should exist");

    state
        .upsert_ops_role_assignment_by_owner(
            &owner,
            ops_viewer.id as u64,
            crate::UpsertOpsRoleInput {
                role: "ops_viewer".to_string(),
            },
        )
        .await?;

    let session_id = seed_topic_and_session(&state, "closed").await?;
    let job_id = seed_running_judge_job(&state, session_id).await?;
    state
        .submit_judge_report(
            job_id as u64,
            SubmitJudgeReportInput {
                winner: "pro".to_string(),
                pro_score: 83,
                con_score: 78,
                logic_pro: 82,
                logic_con: 77,
                evidence_pro: 84,
                evidence_con: 79,
                rebuttal_pro: 81,
                rebuttal_con: 76,
                clarity_pro: 85,
                clarity_con: 80,
                pro_summary: "pro".to_string(),
                con_summary: "con".to_string(),
                rationale: "rationale".to_string(),
                style_mode: Some("rational".to_string()),
                needs_draw_vote: false,
                rejudge_triggered: false,
                payload: serde_json::json!({"trace":"viewer-review"}),
                winner_first: Some("pro".to_string()),
                winner_second: Some("pro".to_string()),
                stage_summaries: vec![],
            },
        )
        .await?;

    let reviews = state
        .list_judge_reviews_by_owner(
            &ops_viewer,
            ListJudgeReviewOpsQuery {
                from: None,
                to: None,
                winner: None,
                rejudge_triggered: None,
                has_verdict_evidence: None,
                anomaly_only: false,
                limit: Some(20),
            },
        )
        .await?;
    assert!(!reviews.items.is_empty());

    let rejudge_err = state
        .request_judge_rejudge_by_owner(session_id as u64, &ops_viewer)
        .await
        .expect_err("ops_viewer should not trigger rejudge");
    assert!(matches!(rejudge_err, AppError::DebateConflict(_)));
    Ok(())
}
