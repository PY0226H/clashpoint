use super::*;

#[tokio::test]
async fn submit_draw_vote_should_decide_after_threshold_reached() -> Result<()> {
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
                pro_score: 79,
                con_score: 79,
                logic_pro: 79,
                logic_con: 79,
                evidence_pro: 79,
                evidence_con: 79,
                rebuttal_pro: 79,
                rebuttal_con: 79,
                clarity_pro: 79,
                clarity_con: 79,
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

    let user1 = state.find_user_by_id(1).await?.expect("user1 should exist");
    let user2 = state.find_user_by_id(2).await?.expect("user2 should exist");
    let user3 = state.find_user_by_id(3).await?.expect("user3 should exist");

    let vote1 = state
        .submit_draw_vote(
            session_id as u64,
            &user1,
            SubmitDrawVoteInput { agree_draw: true },
        )
        .await?;
    assert_eq!(vote1.status, "open");
    assert_eq!(vote1.vote.decision_source, "pending");

    let vote2 = state
        .submit_draw_vote(
            session_id as u64,
            &user2,
            SubmitDrawVoteInput { agree_draw: true },
        )
        .await?;
    assert_eq!(vote2.status, "open");
    assert_eq!(vote2.vote.decision_source, "pending");

    let vote3 = state
        .submit_draw_vote(
            session_id as u64,
            &user3,
            SubmitDrawVoteInput { agree_draw: false },
        )
        .await?;
    assert_eq!(vote3.status, "decided");
    assert_eq!(vote3.vote.resolution, "accept_draw");
    assert_eq!(vote3.vote.participated_voters, 3);
    assert_eq!(vote3.vote.agree_votes, 2);
    assert_eq!(vote3.vote.disagree_votes, 1);
    assert_eq!(vote3.vote.decision_source, "threshold_reached");
    assert!(vote3.vote.rematch_session_id.is_none());
    Ok(())
}

#[tokio::test]
async fn get_draw_vote_status_should_auto_expire_to_open_rematch() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "closed").await?;
    join_user_to_session(&state, session_id, 1).await?;
    join_user_to_session(&state, session_id, 2).await?;
    let job_id = seed_running_judge_job(&state, session_id).await?;

    state
        .submit_judge_report(
            job_id as u64,
            SubmitJudgeReportInput {
                winner: "draw".to_string(),
                pro_score: 75,
                con_score: 75,
                logic_pro: 75,
                logic_con: 75,
                evidence_pro: 75,
                evidence_con: 75,
                rebuttal_pro: 75,
                rebuttal_con: 75,
                clarity_pro: 75,
                clarity_con: 75,
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

    sqlx::query(
        r#"
            UPDATE judge_draw_votes
            SET voting_ends_at = NOW() - INTERVAL '1 second',
                updated_at = NOW()
            WHERE session_id = $1
            "#,
    )
    .bind(session_id)
    .execute(&state.pool)
    .await?;

    let user1 = state.find_user_by_id(1).await?.expect("user1 should exist");
    let status = state
        .get_draw_vote_status(session_id as u64, &user1)
        .await?;
    assert_eq!(status.status, "expired");
    let vote = status.vote.expect("vote should exist");
    assert_eq!(vote.resolution, "open_rematch");
    assert_eq!(vote.participated_voters, 0);
    assert_eq!(vote.decision_source, "vote_timeout");
    let rematch_session_id = vote
        .rematch_session_id
        .expect("expired open_rematch should create rematch session");
    let rematch_row: (String, Option<i64>, i32) = sqlx::query_as(
        r#"
            SELECT status, parent_session_id, rematch_round
            FROM debate_sessions
            WHERE id = $1
            "#,
    )
    .bind(rematch_session_id as i64)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(rematch_row.0, "scheduled");
    assert_eq!(rematch_row.1, Some(session_id));
    assert_eq!(rematch_row.2, 1);
    Ok(())
}

#[tokio::test]
async fn submit_draw_vote_should_open_rematch_when_disagree_majority() -> Result<()> {
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
                pro_score: 78,
                con_score: 78,
                logic_pro: 78,
                logic_con: 78,
                evidence_pro: 78,
                evidence_con: 78,
                rebuttal_pro: 78,
                rebuttal_con: 78,
                clarity_pro: 78,
                clarity_con: 78,
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

    let user1 = state.find_user_by_id(1).await?.expect("user1 should exist");
    let user2 = state.find_user_by_id(2).await?.expect("user2 should exist");
    let user3 = state.find_user_by_id(3).await?.expect("user3 should exist");

    state
        .submit_draw_vote(
            session_id as u64,
            &user1,
            SubmitDrawVoteInput { agree_draw: false },
        )
        .await?;
    state
        .submit_draw_vote(
            session_id as u64,
            &user2,
            SubmitDrawVoteInput { agree_draw: false },
        )
        .await?;
    let final_vote = state
        .submit_draw_vote(
            session_id as u64,
            &user3,
            SubmitDrawVoteInput { agree_draw: true },
        )
        .await?;
    assert_eq!(final_vote.status, "decided");
    assert_eq!(final_vote.vote.resolution, "open_rematch");
    assert_eq!(final_vote.vote.agree_votes, 1);
    assert_eq!(final_vote.vote.disagree_votes, 2);
    assert_eq!(final_vote.vote.decision_source, "threshold_reached");
    let rematch_session_id = final_vote
        .vote
        .rematch_session_id
        .expect("open_rematch decision should create rematch session");
    let rematch_row: (String, Option<i64>, i32) = sqlx::query_as(
        r#"
            SELECT status, parent_session_id, rematch_round
            FROM debate_sessions
            WHERE id = $1
            "#,
    )
    .bind(rematch_session_id as i64)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(rematch_row.0, "scheduled");
    assert_eq!(rematch_row.1, Some(session_id));
    assert_eq!(rematch_row.2, 1);
    Ok(())
}

#[tokio::test]
async fn submit_draw_vote_should_reject_non_participant() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "closed").await?;
    join_user_to_session(&state, session_id, 1).await?;
    let job_id = seed_running_judge_job(&state, session_id).await?;

    state
        .submit_judge_report(
            job_id as u64,
            SubmitJudgeReportInput {
                winner: "draw".to_string(),
                pro_score: 70,
                con_score: 70,
                logic_pro: 70,
                logic_con: 70,
                evidence_pro: 70,
                evidence_con: 70,
                rebuttal_pro: 70,
                rebuttal_con: 70,
                clarity_pro: 70,
                clarity_con: 70,
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

    let user4 = state.find_user_by_id(4).await?.expect("user4 should exist");
    let err = state
        .submit_draw_vote(
            session_id as u64,
            &user4,
            SubmitDrawVoteInput { agree_draw: true },
        )
        .await
        .expect_err("non participant should be rejected");
    assert!(matches!(err, AppError::DebateConflict(_)));
    Ok(())
}

#[tokio::test]
async fn get_draw_vote_status_should_create_expected_next_round_rematch() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "closed").await?;
    join_user_to_session(&state, session_id, 1).await?;
    let job_id = seed_running_judge_job(&state, session_id).await?;

    state
        .submit_judge_report(
            job_id as u64,
            SubmitJudgeReportInput {
                winner: "draw".to_string(),
                pro_score: 74,
                con_score: 74,
                logic_pro: 74,
                logic_con: 74,
                evidence_pro: 74,
                evidence_con: 74,
                rebuttal_pro: 74,
                rebuttal_con: 74,
                clarity_pro: 74,
                clarity_con: 74,
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

    let unexpected_round_session: (i64,) = sqlx::query_as(
        r#"
            INSERT INTO debate_sessions(
                topic_id, status, scheduled_start_at, actual_start_at, end_at,
                max_participants_per_side, pro_count, con_count, hot_score,
                parent_session_id, rematch_round, created_at, updated_at
            )
            SELECT
                topic_id, 'scheduled', NOW() + INTERVAL '30 minute', NULL, NOW() + INTERVAL '90 minute',
                max_participants_per_side, 0, 0, 0,
                id, 2, NOW(), NOW()
            FROM debate_sessions
            WHERE id = $1
            RETURNING id
            "#,
    )
    .bind(session_id)
    .fetch_one(&state.pool)
    .await?;

    sqlx::query(
        r#"
            UPDATE judge_draw_votes
            SET voting_ends_at = NOW() - INTERVAL '1 second',
                updated_at = NOW()
            WHERE session_id = $1
            "#,
    )
    .bind(session_id)
    .execute(&state.pool)
    .await?;

    let user1 = state.find_user_by_id(1).await?.expect("user1 should exist");
    let status = state
        .get_draw_vote_status(session_id as u64, &user1)
        .await?;
    assert_eq!(status.status, "expired");
    let vote = status.vote.expect("vote should exist");
    assert_eq!(vote.resolution, "open_rematch");
    assert_eq!(vote.decision_source, "vote_timeout");
    let rematch_session_id = vote
        .rematch_session_id
        .expect("open_rematch should resolve to rematch session");
    assert_ne!(rematch_session_id as i64, unexpected_round_session.0);
    let rematch_round: (i32,) = sqlx::query_as(
        r#"
            SELECT rematch_round
            FROM debate_sessions
            WHERE id = $1
            "#,
    )
    .bind(rematch_session_id as i64)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(rematch_round.0, 1);
    Ok(())
}

#[tokio::test]
async fn get_draw_vote_status_should_not_duplicate_rematch_on_concurrent_expire_finalize(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "closed").await?;
    join_user_to_session(&state, session_id, 1).await?;
    join_user_to_session(&state, session_id, 2).await?;
    let job_id = seed_running_judge_job(&state, session_id).await?;

    state
        .submit_judge_report(
            job_id as u64,
            SubmitJudgeReportInput {
                winner: "draw".to_string(),
                pro_score: 73,
                con_score: 73,
                logic_pro: 73,
                logic_con: 73,
                evidence_pro: 73,
                evidence_con: 73,
                rebuttal_pro: 73,
                rebuttal_con: 73,
                clarity_pro: 73,
                clarity_con: 73,
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

    sqlx::query(
        r#"
            UPDATE judge_draw_votes
            SET voting_ends_at = NOW() - INTERVAL '1 second',
                updated_at = NOW()
            WHERE session_id = $1
            "#,
    )
    .bind(session_id)
    .execute(&state.pool)
    .await?;

    let user1 = state.find_user_by_id(1).await?.expect("user1 should exist");
    let user2 = state.find_user_by_id(2).await?.expect("user2 should exist");
    let (result1, result2) = tokio::join!(
        state.get_draw_vote_status(session_id as u64, &user1),
        state.get_draw_vote_status(session_id as u64, &user2)
    );
    let output1 = result1?;
    let output2 = result2?;
    let vote1 = output1.vote.expect("vote should exist for user1");
    let vote2 = output2.vote.expect("vote should exist for user2");
    assert_eq!(vote1.status, "expired");
    assert_eq!(vote2.status, "expired");
    assert_eq!(vote1.decision_source, "vote_timeout");
    assert_eq!(vote2.decision_source, "vote_timeout");
    assert_eq!(vote1.rematch_session_id, vote2.rematch_session_id);

    let rematch_count: (i64,) = sqlx::query_as(
        r#"
            SELECT COUNT(*)::bigint
            FROM debate_sessions
            WHERE parent_session_id = $1 AND rematch_round = 1
            "#,
    )
    .bind(session_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(rematch_count.0, 1);
    Ok(())
}

#[tokio::test]
async fn get_draw_vote_status_should_keep_single_rematch_under_high_concurrency() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "closed").await?;
    join_user_to_session(&state, session_id, 1).await?;
    join_user_to_session(&state, session_id, 2).await?;
    let job_id = seed_running_judge_job(&state, session_id).await?;

    state
        .submit_judge_report(
            job_id as u64,
            SubmitJudgeReportInput {
                winner: "draw".to_string(),
                pro_score: 72,
                con_score: 72,
                logic_pro: 72,
                logic_con: 72,
                evidence_pro: 72,
                evidence_con: 72,
                rebuttal_pro: 72,
                rebuttal_con: 72,
                clarity_pro: 72,
                clarity_con: 72,
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

    sqlx::query(
        r#"
            UPDATE judge_draw_votes
            SET voting_ends_at = NOW() - INTERVAL '1 second',
                updated_at = NOW()
            WHERE session_id = $1
            "#,
    )
    .bind(session_id)
    .execute(&state.pool)
    .await?;

    let user1 = state.find_user_by_id(1).await?.expect("user1 should exist");
    let user2 = state.find_user_by_id(2).await?.expect("user2 should exist");
    let mut tasks = tokio::task::JoinSet::new();
    for i in 0..24 {
        let state = state.clone();
        let user = if i % 2 == 0 {
            user1.clone()
        } else {
            user2.clone()
        };
        tasks.spawn(async move { state.get_draw_vote_status(session_id as u64, &user).await });
    }

    let mut rematch_ids: Vec<u64> = Vec::new();
    while let Some(joined) = tasks.join_next().await {
        let output = joined.expect("draw vote status task should not panic")?;
        let vote = output.vote.expect("vote should exist");
        assert_eq!(vote.status, "expired");
        assert_eq!(vote.decision_source, "vote_timeout");
        rematch_ids.push(
            vote.rematch_session_id
                .expect("expired open_rematch should have rematch session"),
        );
    }
    assert_eq!(rematch_ids.len(), 24);
    let first = rematch_ids[0];
    assert!(rematch_ids.iter().all(|id| *id == first));

    let rematch_count: (i64,) = sqlx::query_as(
        r#"
            SELECT COUNT(*)::bigint
            FROM debate_sessions
            WHERE parent_session_id = $1 AND rematch_round = 1
            "#,
    )
    .bind(session_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(rematch_count.0, 1);
    Ok(())
}
