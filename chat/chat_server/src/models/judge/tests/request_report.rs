use super::*;

#[tokio::test]
async fn request_judge_job_should_create_running_job_with_default_style() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, 1, "judging").await?;
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
    let session_id = seed_topic_and_session(&state, 1, "closed").await?;
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

    let session_id = seed_topic_and_session(&state, 1, "closed").await?;
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

    let session_id = seed_topic_and_session(&state, 1, "closed").await?;
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
    let session_id = seed_topic_and_session(&state, 1, "judging").await?;
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
    let session_id = seed_topic_and_session(&state, 1, "running").await?;
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
    let session_id = seed_topic_and_session(&state, 1, "judging").await?;
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
    let session_id = seed_topic_and_session(&state, 1, "closed").await?;
    join_user_to_session(&state, session_id, 1).await?;
    let user = state.find_user_by_id(1).await?.expect("user should exist");

    let job_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO judge_jobs(
                ws_id, session_id, requested_by, status, style_mode, requested_at, started_at, finished_at
            )
            VALUES ($1, $2, $3, 'succeeded', 'rational', NOW(), NOW(), NOW())
            RETURNING id
            "#,
        )
        .bind(1_i64)
        .bind(session_id)
        .bind(1_i64)
        .fetch_one(&state.pool)
        .await?;

    sqlx::query(
        r#"
            INSERT INTO judge_reports(
                ws_id, session_id, job_id, winner, pro_score, con_score,
                logic_pro, logic_con, evidence_pro, evidence_con, rebuttal_pro, rebuttal_con,
                clarity_pro, clarity_con, pro_summary, con_summary, rationale, style_mode,
                needs_draw_vote, rejudge_triggered, payload
            )
            VALUES (
                $1, $2, $3, 'pro', 82, 74,
                80, 72, 85, 76, 79, 71,
                84, 77, 'pro summary', 'con summary', 'rationale', 'rational',
                false, false, '{"trace":"ok"}'::jsonb
            )
            "#,
    )
    .bind(1_i64)
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
async fn get_latest_judge_report_should_include_stage_summaries() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, 1, "closed").await?;
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
    let session_id = seed_topic_and_session(&state, 1, "closed").await?;
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
    let session_id = seed_topic_and_session(&state, 1, "closed").await?;
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
