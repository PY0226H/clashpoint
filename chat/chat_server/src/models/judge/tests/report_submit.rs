use super::*;

#[tokio::test]
async fn submit_judge_report_should_persist_report_and_mark_job_succeeded() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "judging").await?;
    let job_id = seed_running_judge_job(&state, session_id).await?;

    let ret = state
        .submit_judge_report(
            job_id as u64,
            SubmitJudgeReportInput {
                winner: "pro".to_string(),
                pro_score: 84,
                con_score: 76,
                logic_pro: 83,
                logic_con: 74,
                evidence_pro: 85,
                evidence_con: 78,
                rebuttal_pro: 82,
                rebuttal_con: 73,
                clarity_pro: 86,
                clarity_con: 79,
                pro_summary: "pro summary".to_string(),
                con_summary: "con summary".to_string(),
                rationale: "final rationale".to_string(),
                style_mode: Some("mixed".to_string()),
                needs_draw_vote: false,
                rejudge_triggered: false,
                payload: serde_json::json!({
                    "provider":"openai",
                    "traceId":"abc",
                    "rubricVersion":"v1-fairness-test"
                }),
                winner_first: Some("pro".to_string()),
                winner_second: Some("pro".to_string()),
                stage_summaries: vec![
                    JudgeStageSummaryInput {
                        stage_no: 1,
                        from_message_id: Some(1),
                        to_message_id: Some(100),
                        pro_score: 80,
                        con_score: 75,
                        summary: serde_json::json!({"brief":"s1"}),
                    },
                    JudgeStageSummaryInput {
                        stage_no: 2,
                        from_message_id: Some(101),
                        to_message_id: Some(200),
                        pro_score: 84,
                        con_score: 76,
                        summary: serde_json::json!({"brief":"s2"}),
                    },
                ],
            },
        )
        .await?;
    assert!(ret.newly_created);
    assert_eq!(ret.status, "succeeded");

    let row: (String, Option<String>, Option<String>, String) = sqlx::query_as(
        r#"
            SELECT status, winner_first, winner_second, rubric_version
            FROM judge_jobs
            JOIN judge_reports ON judge_reports.job_id = judge_jobs.id
            WHERE judge_jobs.id = $1
            "#,
    )
    .bind(job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(row.0, "succeeded");
    assert_eq!(row.1.as_deref(), Some("pro"));
    assert_eq!(row.2.as_deref(), Some("pro"));
    assert_eq!(row.3, "v1-fairness-test");

    let stage_cnt: (i64,) = sqlx::query_as(
        r#"
            SELECT COUNT(*)::bigint
            FROM judge_stage_summaries
            WHERE job_id = $1
            "#,
    )
    .bind(job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(stage_cnt.0, 2);
    Ok(())
}

#[tokio::test]
async fn submit_judge_report_should_be_idempotent_by_job_id() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "judging").await?;
    let job_id = seed_running_judge_job(&state, session_id).await?;
    let input = SubmitJudgeReportInput {
        winner: "con".to_string(),
        pro_score: 72,
        con_score: 81,
        logic_pro: 70,
        logic_con: 83,
        evidence_pro: 74,
        evidence_con: 82,
        rebuttal_pro: 71,
        rebuttal_con: 80,
        clarity_pro: 73,
        clarity_con: 79,
        pro_summary: "pro".to_string(),
        con_summary: "con".to_string(),
        rationale: "rationale".to_string(),
        style_mode: Some("rational".to_string()),
        needs_draw_vote: false,
        rejudge_triggered: false,
        payload: serde_json::json!({"x":1}),
        winner_first: Some("con".to_string()),
        winner_second: Some("con".to_string()),
        stage_summaries: vec![],
    };
    let first = state
        .submit_judge_report(job_id as u64, input.clone())
        .await?;
    let second = state.submit_judge_report(job_id as u64, input).await?;
    assert!(first.newly_created);
    assert!(!second.newly_created);
    assert_eq!(first.report_id, second.report_id);
    Ok(())
}

#[tokio::test]
async fn mark_judge_job_failed_should_update_status_and_be_idempotent() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "judging").await?;
    let job_id = seed_running_judge_job(&state, session_id).await?;
    let first = state
        .mark_judge_job_failed(
            job_id as u64,
            MarkJudgeJobFailedInput {
                error_message: "timeout".to_string(),
            },
        )
        .await?;
    let second = state
        .mark_judge_job_failed(
            job_id as u64,
            MarkJudgeJobFailedInput {
                error_message: "ignored".to_string(),
            },
        )
        .await?;
    assert!(first.newly_marked);
    assert!(!second.newly_marked);
    assert_eq!(second.error_message, "timeout");
    Ok(())
}

#[tokio::test]
async fn mark_judge_job_failed_should_reject_when_report_exists() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "closed").await?;
    let job_id = seed_running_judge_job(&state, session_id).await?;

    state
        .submit_judge_report(
            job_id as u64,
            SubmitJudgeReportInput {
                winner: "pro".to_string(),
                pro_score: 80,
                con_score: 70,
                logic_pro: 80,
                logic_con: 70,
                evidence_pro: 80,
                evidence_con: 70,
                rebuttal_pro: 80,
                rebuttal_con: 70,
                clarity_pro: 80,
                clarity_con: 70,
                pro_summary: "p".to_string(),
                con_summary: "c".to_string(),
                rationale: "r".to_string(),
                style_mode: Some("rational".to_string()),
                needs_draw_vote: false,
                rejudge_triggered: false,
                payload: serde_json::json!({}),
                winner_first: Some("pro".to_string()),
                winner_second: Some("pro".to_string()),
                stage_summaries: vec![],
            },
        )
        .await?;

    let err = state
        .mark_judge_job_failed(
            job_id as u64,
            MarkJudgeJobFailedInput {
                error_message: "should fail".to_string(),
            },
        )
        .await
        .expect_err("should reject");
    assert!(matches!(err, AppError::DebateConflict(_)));
    Ok(())
}

#[tokio::test]
async fn submit_judge_report_should_create_draw_vote_when_needed() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "closed").await?;
    join_user_to_session(&state, session_id, 1).await?;
    join_user_to_session(&state, session_id, 2).await?;
    join_user_to_session(&state, session_id, 3).await?;
    let job_id = seed_running_judge_job(&state, session_id).await?;

    state
        .submit_judge_report(
            job_id as u64,
            SubmitJudgeReportInput {
                winner: "draw".to_string(),
                pro_score: 80,
                con_score: 80,
                logic_pro: 80,
                logic_con: 80,
                evidence_pro: 80,
                evidence_con: 80,
                rebuttal_pro: 80,
                rebuttal_con: 80,
                clarity_pro: 80,
                clarity_con: 80,
                pro_summary: "pro".to_string(),
                con_summary: "con".to_string(),
                rationale: "rationale".to_string(),
                style_mode: Some("rational".to_string()),
                needs_draw_vote: true,
                rejudge_triggered: true,
                payload: serde_json::json!({}),
                winner_first: Some("pro".to_string()),
                winner_second: Some("con".to_string()),
                stage_summaries: vec![],
            },
        )
        .await?;

    let row: (i32, i32, String, String) = sqlx::query_as(
        r#"
            SELECT eligible_voters, required_voters, status, resolution
            FROM judge_draw_votes
            WHERE session_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            "#,
    )
    .bind(session_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(row.0, 3);
    assert_eq!(row.1, 3);
    assert_eq!(row.2, "open");
    assert_eq!(row.3, "pending");
    Ok(())
}
