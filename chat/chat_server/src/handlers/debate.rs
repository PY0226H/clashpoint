use crate::{
    AppError, AppState, CreateDebateMessageInput, GetJudgeReportQuery, JoinDebateSessionInput,
    ListDebateMessages, ListDebatePinnedMessages, ListDebateSessions, ListDebateTopics,
    OpsCreateDebateSessionInput, OpsCreateDebateTopicInput, OpsUpdateDebateSessionInput,
    OpsUpdateDebateTopicInput, PinDebateMessageInput, RequestJudgeJobInput, SubmitDrawVoteInput,
};
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::IntoResponse,
    Extension, Json,
};
use chat_core::User;

/// List debate topics in the current workspace.
#[utoipa::path(
    get,
    path = "/api/debate/topics",
    params(
        ListDebateTopics
    ),
    responses(
        (status = 200, description = "List of debate topics", body = Vec<crate::DebateTopic>),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_debate_topics_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Query(input): Query<ListDebateTopics>,
) -> Result<impl IntoResponse, AppError> {
    let topics = state.list_debate_topics(user.ws_id as _, input).await?;
    Ok((StatusCode::OK, Json(topics)))
}

/// Create debate topic by workspace owner (ops).
#[utoipa::path(
    post,
    path = "/api/debate/ops/topics",
    request_body = OpsCreateDebateTopicInput,
    responses(
        (status = 201, description = "Created debate topic", body = crate::DebateTopic),
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 404, description = "Workspace not found", body = ErrorOutput),
        (status = 409, description = "Permission conflict", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn create_debate_topic_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Json(input): Json<OpsCreateDebateTopicInput>,
) -> Result<impl IntoResponse, AppError> {
    let topic = state.create_debate_topic_by_owner(&user, input).await?;
    Ok((StatusCode::CREATED, Json(topic)))
}

/// Update debate topic by workspace owner (ops).
#[utoipa::path(
    put,
    path = "/api/debate/ops/topics/{id}",
    params(
        ("id" = u64, Path, description = "Debate topic id")
    ),
    request_body = OpsUpdateDebateTopicInput,
    responses(
        (status = 200, description = "Updated debate topic", body = crate::DebateTopic),
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 404, description = "Topic/workspace not found", body = ErrorOutput),
        (status = 409, description = "Permission conflict", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn update_debate_topic_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<OpsUpdateDebateTopicInput>,
) -> Result<impl IntoResponse, AppError> {
    let topic = state.update_debate_topic_by_owner(&user, id, input).await?;
    Ok((StatusCode::OK, Json(topic)))
}

/// Create debate session by workspace owner (ops).
#[utoipa::path(
    post,
    path = "/api/debate/ops/sessions",
    request_body = OpsCreateDebateSessionInput,
    responses(
        (status = 201, description = "Created debate session", body = crate::DebateSessionSummary),
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 404, description = "Topic/workspace not found", body = ErrorOutput),
        (status = 409, description = "Permission conflict", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn create_debate_session_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Json(input): Json<OpsCreateDebateSessionInput>,
) -> Result<impl IntoResponse, AppError> {
    let session = state.create_debate_session_by_owner(&user, input).await?;
    Ok((StatusCode::CREATED, Json(session)))
}

/// Update debate session by workspace owner (ops).
#[utoipa::path(
    put,
    path = "/api/debate/ops/sessions/{id}",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    request_body = OpsUpdateDebateSessionInput,
    responses(
        (status = 200, description = "Updated debate session", body = crate::DebateSessionSummary),
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 404, description = "Session/workspace not found", body = ErrorOutput),
        (status = 409, description = "Permission conflict", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn update_debate_session_ops_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<OpsUpdateDebateSessionInput>,
) -> Result<impl IntoResponse, AppError> {
    let session = state
        .update_debate_session_by_owner(&user, id, input)
        .await?;
    Ok((StatusCode::OK, Json(session)))
}

/// List debate sessions in the current workspace.
#[utoipa::path(
    get,
    path = "/api/debate/sessions",
    params(
        ListDebateSessions
    ),
    responses(
        (status = 200, description = "List of debate sessions", body = Vec<crate::DebateSessionSummary>),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_debate_sessions_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Query(input): Query<ListDebateSessions>,
) -> Result<impl IntoResponse, AppError> {
    let sessions = state.list_debate_sessions(user.ws_id as _, input).await?;
    Ok((StatusCode::OK, Json(sessions)))
}

/// Join a debate session with selected side.
#[utoipa::path(
    post,
    path = "/api/debate/sessions/{id}/join",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    request_body = JoinDebateSessionInput,
    responses(
        (status = 200, description = "Join result", body = crate::JoinDebateSessionOutput),
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 404, description = "Debate session not found", body = ErrorOutput),
        (status = 409, description = "Join conflict", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn join_debate_session_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<JoinDebateSessionInput>,
) -> Result<impl IntoResponse, AppError> {
    let result = state.join_debate_session(id, &user, input).await?;
    Ok((StatusCode::OK, Json(result)))
}

/// Send a message in a debate session.
#[utoipa::path(
    post,
    path = "/api/debate/sessions/{id}/messages",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    request_body = CreateDebateMessageInput,
    responses(
        (status = 201, description = "Created message", body = crate::DebateMessage),
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 404, description = "Debate session not found", body = ErrorOutput),
        (status = 409, description = "Session conflict", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn create_debate_message_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<CreateDebateMessageInput>,
) -> Result<impl IntoResponse, AppError> {
    let msg = state.create_debate_message(id, &user, input).await?;
    Ok((StatusCode::CREATED, Json(msg)))
}

/// List messages in a debate session.
#[utoipa::path(
    get,
    path = "/api/debate/sessions/{id}/messages",
    params(
        ("id" = u64, Path, description = "Debate session id"),
        ListDebateMessages
    ),
    responses(
        (status = 200, description = "Debate messages", body = Vec<crate::DebateMessage>),
        (status = 404, description = "Debate session not found", body = ErrorOutput),
        (status = 409, description = "User cannot read in current session status", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_debate_messages_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Query(input): Query<ListDebateMessages>,
) -> Result<impl IntoResponse, AppError> {
    let messages = state.list_debate_messages(id, &user, input).await?;
    Ok((StatusCode::OK, Json(messages)))
}

/// Pin an existing debate message with wallet consume.
#[utoipa::path(
    post,
    path = "/api/debate/messages/{id}/pin",
    params(
        ("id" = u64, Path, description = "Debate message id")
    ),
    request_body = PinDebateMessageInput,
    responses(
        (status = 200, description = "Pin result", body = crate::PinDebateMessageOutput),
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 404, description = "Debate message not found", body = ErrorOutput),
        (status = 409, description = "Pin conflict", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn pin_debate_message_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<PinDebateMessageInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.pin_debate_message(id, &user, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// List pinned messages in a debate session.
#[utoipa::path(
    get,
    path = "/api/debate/sessions/{id}/pins",
    params(
        ("id" = u64, Path, description = "Debate session id"),
        ListDebatePinnedMessages
    ),
    responses(
        (status = 200, description = "Pinned debate messages", body = Vec<crate::DebatePinnedMessage>),
        (status = 404, description = "Debate session not found", body = ErrorOutput),
        (status = 409, description = "User cannot read in current session status", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_debate_pinned_messages_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Query(input): Query<ListDebatePinnedMessages>,
) -> Result<impl IntoResponse, AppError> {
    let pins = state.list_debate_pinned_messages(id, &user, input).await?;
    Ok((StatusCode::OK, Json(pins)))
}

/// Request an AI judge job for a debate session.
/// Note: `styleMode` in request body is kept for compatibility and no longer controls behavior.
/// Effective style is decided by server-side `ai_judge.style_mode` config and returned in `styleModeSource`.
#[utoipa::path(
    post,
    path = "/api/debate/sessions/{id}/judge/jobs",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    request_body = RequestJudgeJobInput,
    responses(
        (status = 202, description = "Judge job accepted", body = crate::RequestJudgeJobOutput),
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 404, description = "Debate session not found", body = ErrorOutput),
        (status = 409, description = "Request conflict", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn request_judge_job_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<RequestJudgeJobInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.request_judge_job(id, &user, input).await?;
    Ok((StatusCode::ACCEPTED, Json(ret)))
}

/// Get latest AI judge report for a debate session.
#[utoipa::path(
    get,
    path = "/api/debate/sessions/{id}/judge-report",
    params(
        ("id" = u64, Path, description = "Debate session id"),
        GetJudgeReportQuery
    ),
    responses(
        (status = 200, description = "Judge report query result", body = crate::GetJudgeReportOutput),
        (status = 404, description = "Debate session not found", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_latest_judge_report_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Query(input): Query<GetJudgeReportQuery>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.get_latest_judge_report(id, &user, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Get draw-vote status for latest draw-required judge report in a debate session.
#[utoipa::path(
    get,
    path = "/api/debate/sessions/{id}/draw-vote",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    responses(
        (status = 200, description = "Draw vote status", body = crate::GetDrawVoteOutput),
        (status = 404, description = "Debate session not found", body = ErrorOutput),
        (status = 409, description = "User is not participant", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn get_draw_vote_status_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.get_draw_vote_status(id, &user).await?;
    Ok((StatusCode::OK, Json(ret)))
}

/// Submit or update current user's draw vote.
#[utoipa::path(
    post,
    path = "/api/debate/sessions/{id}/draw-vote/ballots",
    params(
        ("id" = u64, Path, description = "Debate session id")
    ),
    request_body = SubmitDrawVoteInput,
    responses(
        (status = 200, description = "Draw vote submit result", body = crate::SubmitDrawVoteOutput),
        (status = 400, description = "Invalid input", body = ErrorOutput),
        (status = 404, description = "Debate session not found", body = ErrorOutput),
        (status = 409, description = "Vote conflict", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn submit_draw_vote_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<SubmitDrawVoteInput>,
) -> Result<impl IntoResponse, AppError> {
    let ret = state.submit_draw_vote(id, &user, input).await?;
    Ok((StatusCode::OK, Json(ret)))
}

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;
    use chrono::{Duration, Utc};
    use http_body_util::BodyExt;
    use std::sync::Arc;

    async fn seed_topic_and_session(state: &AppState, ws_id: i64, status: &str) -> Result<i64> {
        let topic_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO debate_topics(ws_id, title, description, category, stance_pro, stance_con, is_active, created_by)
            VALUES ($1, 'topic-handler', 'desc', 'game', 'pro', 'con', true, 1)
            RETURNING id
            "#,
        )
        .bind(ws_id)
        .fetch_one(&state.pool)
        .await?;

        let now = Utc::now();
        let session_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO debate_sessions(
                ws_id, topic_id, status, scheduled_start_at, actual_start_at, end_at, max_participants_per_side
            )
            VALUES ($1, $2, $3, $4, $5, $6, 500)
            RETURNING id
            "#,
        )
        .bind(ws_id)
        .bind(topic_id.0)
        .bind(status)
        .bind(now - Duration::minutes(20))
        .bind(now - Duration::minutes(15))
        .bind(now - Duration::minutes(1))
        .fetch_one(&state.pool)
        .await?;

        Ok(session_id.0)
    }

    async fn join_user_to_session(state: &AppState, session_id: i64, user_id: i64) -> Result<()> {
        sqlx::query(
            r#"
            INSERT INTO session_participants(session_id, user_id, side)
            VALUES ($1, $2, 'pro')
            "#,
        )
        .bind(session_id)
        .bind(user_id)
        .execute(&state.pool)
        .await?;
        Ok(())
    }

    async fn seed_running_judge_job(state: &AppState, session_id: i64) -> Result<i64> {
        let job_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO judge_jobs(
                ws_id, session_id, requested_by, status, style_mode, requested_at, started_at, created_at, updated_at
            )
            VALUES ($1, $2, $3, 'running', 'rational', NOW(), NOW(), NOW(), NOW())
            RETURNING id
            "#,
        )
        .bind(1_i64)
        .bind(session_id)
        .bind(1_i64)
        .fetch_one(&state.pool)
        .await?;
        Ok(job_id.0)
    }

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
    async fn get_latest_judge_report_handler_should_apply_max_stage_count_and_return_meta(
    ) -> Result<()> {
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
        assert_eq!(ret["report"]["stageSummariesMeta"]["totalCount"], 3);
        assert_eq!(ret["report"]["stageSummariesMeta"]["returnedCount"], 1);
        assert_eq!(ret["report"]["stageSummariesMeta"]["stageOffset"], 0);
        assert_eq!(ret["report"]["stageSummariesMeta"]["truncated"], true);
        assert_eq!(ret["report"]["stageSummariesMeta"]["hasMore"], true);
        assert_eq!(ret["report"]["stageSummariesMeta"]["nextOffset"], 1);
        assert_eq!(ret["report"]["stageSummariesMeta"]["maxStageCount"], 1);
        Ok(())
    }
}
