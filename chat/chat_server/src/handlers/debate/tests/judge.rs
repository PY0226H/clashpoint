use super::super::{get_latest_judge_report_handler, request_judge_job_handler};
use super::test_support::{join_user_to_session, seed_running_judge_job, seed_topic_and_session};
use crate::{AppState, GetJudgeReportQuery, RequestJudgeJobInput};
use anyhow::Result;
use axum::{
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    Extension, Json,
};
use http_body_util::BodyExt;
use std::sync::Arc;

#[tokio::test]
async fn request_judge_job_handler_should_return_style_mode_source() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, 1, "judging").await?;
    join_user_to_session(&state, session_id, 1).await?;
    let user = state.find_user_by_id(1).await?.expect("user should exist");

    let response = request_judge_job_handler(
        Extension(user),
        State(state),
        Path(session_id as u64),
        HeaderMap::new(),
        Json(RequestJudgeJobInput {
            style_mode: Some("mixed".to_string()),
            allow_rejudge: false,
        }),
    )
    .await?
    .into_response();

    assert_eq!(response.status(), StatusCode::ACCEPTED);
    let body = response.into_body().collect().await?.to_bytes();
    let ret: serde_json::Value = serde_json::from_slice(&body)?;
    assert_eq!(ret["styleMode"], "rational");
    assert_eq!(ret["styleModeSource"], "system_config");
    Ok(())
}

#[tokio::test]
async fn request_judge_job_handler_should_ignore_request_style_mode() -> Result<()> {
    let (_tdb, mut state) = AppState::new_for_test().await?;
    let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
    inner.config.ai_judge.style_mode = "entertaining".to_string();

    let session_id = seed_topic_and_session(&state, 1, "closed").await?;
    join_user_to_session(&state, session_id, 1).await?;
    let user = state.find_user_by_id(1).await?.expect("user should exist");

    let response = request_judge_job_handler(
        Extension(user),
        State(state),
        Path(session_id as u64),
        HeaderMap::new(),
        Json(RequestJudgeJobInput {
            style_mode: Some("rational".to_string()),
            allow_rejudge: false,
        }),
    )
    .await?
    .into_response();

    assert_eq!(response.status(), StatusCode::ACCEPTED);
    let body = response.into_body().collect().await?.to_bytes();
    let ret: serde_json::Value = serde_json::from_slice(&body)?;
    assert_eq!(ret["styleMode"], "entertaining");
    assert_eq!(ret["styleModeSource"], "system_config");
    Ok(())
}

#[tokio::test]
async fn get_latest_judge_report_handler_should_apply_max_stage_count_and_return_meta() -> Result<()>
{
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, 1, "closed").await?;
    let user = state.find_user_by_id(1).await?.expect("user should exist");
    let job_id = seed_running_judge_job(&state, session_id).await?;

    state
        .submit_judge_report(
            job_id as u64,
            crate::SubmitJudgeReportInput {
                winner: "pro".to_string(),
                pro_score: 85,
                con_score: 75,
                logic_pro: 84,
                logic_con: 74,
                evidence_pro: 86,
                evidence_con: 76,
                rebuttal_pro: 83,
                rebuttal_con: 73,
                clarity_pro: 87,
                clarity_con: 77,
                pro_summary: "pro".to_string(),
                con_summary: "con".to_string(),
                rationale: "rationale".to_string(),
                style_mode: Some("rational".to_string()),
                needs_draw_vote: false,
                rejudge_triggered: false,
                payload: serde_json::json!({"trace":"handler-limit"}),
                winner_first: Some("pro".to_string()),
                winner_second: Some("pro".to_string()),
                stage_summaries: vec![
                    crate::JudgeStageSummaryInput {
                        stage_no: 1,
                        from_message_id: Some(1),
                        to_message_id: Some(100),
                        pro_score: 80,
                        con_score: 70,
                        summary: serde_json::json!({"brief":"s1"}),
                    },
                    crate::JudgeStageSummaryInput {
                        stage_no: 2,
                        from_message_id: Some(101),
                        to_message_id: Some(200),
                        pro_score: 83,
                        con_score: 73,
                        summary: serde_json::json!({"brief":"s2"}),
                    },
                    crate::JudgeStageSummaryInput {
                        stage_no: 3,
                        from_message_id: Some(201),
                        to_message_id: Some(300),
                        pro_score: 85,
                        con_score: 75,
                        summary: serde_json::json!({"brief":"s3"}),
                    },
                ],
            },
        )
        .await?;

    let response = get_latest_judge_report_handler(
        Extension(user),
        State(state),
        Path(session_id as u64),
        Query(GetJudgeReportQuery {
            max_stage_count: Some(1),
            stage_offset: None,
        }),
    )
    .await?
    .into_response();

    assert_eq!(response.status(), StatusCode::OK);
    let body = response.into_body().collect().await?.to_bytes();
    let ret: serde_json::Value = serde_json::from_slice(&body)?;
    assert_eq!(
        ret["report"]["stageSummaries"].as_array().map(Vec::len),
        Some(1)
    );
    assert_eq!(
        ret["report"]["verdictEvidence"].as_array().map(Vec::len),
        Some(0)
    );
    assert_eq!(ret["report"]["stageSummariesMeta"]["totalCount"], 3);
    assert_eq!(ret["report"]["stageSummariesMeta"]["returnedCount"], 1);
    assert_eq!(ret["report"]["stageSummariesMeta"]["stageOffset"], 0);
    assert_eq!(ret["report"]["stageSummariesMeta"]["truncated"], true);
    assert_eq!(ret["report"]["stageSummariesMeta"]["hasMore"], true);
    assert_eq!(ret["report"]["stageSummariesMeta"]["nextOffset"], 1);
    assert_eq!(ret["report"]["stageSummariesMeta"]["maxStageCount"], 1);
    Ok(())
}
