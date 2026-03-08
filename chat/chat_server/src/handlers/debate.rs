use crate::{AppError, AppState, ListDebateTopics};
use axum::{
    extract::{Query, State},
    http::StatusCode,
    response::IntoResponse,
    Extension, Json,
};
use chat_core::User;

#[cfg(test)]
use crate::{
    GetJudgeReportQuery, ListJudgeReviewOpsQuery, ListKafkaDlqEventsQuery,
    ListOpsAlertNotificationsQuery, OpsObservabilityThresholds, RequestJudgeJobInput,
    UpdateOpsObservabilityAnomalyStateInput, UpsertOpsRoleInput,
};
#[cfg(test)]
use axum::extract::Path;
#[cfg(test)]
use axum::http::HeaderMap;

pub(crate) use super::debate_room::{
    create_debate_message_handler, join_debate_session_handler, list_debate_messages_handler,
    list_debate_pinned_messages_handler, list_debate_sessions_handler, pin_debate_message_handler,
};

pub(crate) use super::debate_judge::{
    get_draw_vote_status_handler, get_latest_judge_report_handler, request_judge_job_handler,
    submit_draw_vote_handler,
};
pub(crate) use super::debate_ops::{
    create_debate_session_ops_handler, create_debate_topic_ops_handler,
    discard_kafka_dlq_event_handler, get_ops_observability_config_handler, get_ops_rbac_me_handler,
    list_judge_reviews_ops_handler, list_kafka_dlq_events_handler,
    list_ops_alert_notifications_handler, list_ops_role_assignments_handler,
    replay_kafka_dlq_event_handler, request_judge_rejudge_ops_handler,
    revoke_ops_role_assignment_handler, update_debate_session_ops_handler,
    update_debate_topic_ops_handler, upsert_ops_observability_anomaly_state_handler,
    upsert_ops_observability_thresholds_handler, upsert_ops_role_assignment_handler,
};

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

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;
    use chrono::{Duration, Utc};
    use http_body_util::BodyExt;
    use std::collections::HashMap;
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

    async fn insert_kafka_dlq_event(
        state: &AppState,
        ws_id: i64,
        event_id: &str,
        payload: serde_json::Value,
    ) -> Result<i64> {
        let row: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO kafka_dlq_events(
                ws_id, consumer_group, topic, partition, message_offset,
                event_id, event_type, aggregate_id, payload,
                status, failure_count, error_message, first_failed_at, last_failed_at, created_at, updated_at
            )
            VALUES (
                $1, 'chat-server-worker', 'aicomm.ai.judge.job.created.v1', 0, 1,
                $2, 'ai.judge.job.created', 'session:1', $3,
                'pending', 1, 'seed', NOW(), NOW(), NOW(), NOW()
            )
            RETURNING id
            "#,
        )
        .bind(ws_id)
        .bind(event_id)
        .bind(payload)
        .fetch_one(&state.pool)
        .await?;
        Ok(row.0)
    }

    async fn insert_ops_alert_notification(state: &AppState, ws_id: i64, key: &str) -> Result<i64> {
        let row: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO ops_alert_notifications(
                ws_id, alert_key, rule_type, severity, alert_status,
                title, message, metrics_json, recipients_json, delivery_status, created_at, updated_at
            )
            VALUES (
                $1, $2, $2, 'warning', 'raised',
                't', 'm', '{}'::jsonb, '[1]'::jsonb, 'sent', NOW(), NOW()
            )
            RETURNING id
            "#,
        )
        .bind(ws_id)
        .bind(key)
        .fetch_one(&state.pool)
        .await?;
        Ok(row.0)
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

    #[tokio::test]
    async fn list_judge_reviews_ops_handler_should_require_workspace_owner() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let non_owner = state.find_user_by_id(2).await?.expect("user should exist");

        let result = list_judge_reviews_ops_handler(
            Extension(non_owner),
            State(state),
            Query(ListJudgeReviewOpsQuery {
                from: None,
                to: None,
                winner: None,
                rejudge_triggered: None,
                has_verdict_evidence: None,
                anomaly_only: false,
                limit: Some(20),
            }),
        )
        .await;
        match result {
            Ok(_) => panic!("non owner should be rejected"),
            Err(err) => assert!(matches!(err, AppError::DebateConflict(_))),
        }
        Ok(())
    }

    #[tokio::test]
    async fn request_judge_rejudge_ops_handler_should_accept_when_report_exists() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let session_id = seed_topic_and_session(&state, 1, "closed").await?;
        let job_id = seed_running_judge_job(&state, session_id).await?;
        state
            .submit_judge_report(
                job_id as u64,
                crate::SubmitJudgeReportInput {
                    winner: "pro".to_string(),
                    pro_score: 82,
                    con_score: 76,
                    logic_pro: 82,
                    logic_con: 75,
                    evidence_pro: 84,
                    evidence_con: 77,
                    rebuttal_pro: 81,
                    rebuttal_con: 74,
                    clarity_pro: 83,
                    clarity_con: 78,
                    pro_summary: "pro".to_string(),
                    con_summary: "con".to_string(),
                    rationale: "rationale".to_string(),
                    style_mode: Some("rational".to_string()),
                    needs_draw_vote: false,
                    rejudge_triggered: false,
                    payload: serde_json::json!({"trace":"ops-rejudge"}),
                    winner_first: Some("pro".to_string()),
                    winner_second: Some("pro".to_string()),
                    stage_summaries: vec![],
                },
            )
            .await?;

        let response = request_judge_rejudge_ops_handler(
            Extension(owner),
            State(state),
            Path(session_id as u64),
        )
        .await?
        .into_response();

        assert_eq!(response.status(), StatusCode::ACCEPTED);
        let body = response.into_body().collect().await?.to_bytes();
        let ret: serde_json::Value = serde_json::from_slice(&body)?;
        assert_eq!(ret["rejudgeTriggered"], true);
        Ok(())
    }

    #[tokio::test]
    async fn ops_rbac_role_handlers_should_upsert_list_and_revoke() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");

        let upsert_resp = upsert_ops_role_assignment_handler(
            Extension(owner.clone()),
            State(state.clone()),
            Path(2_u64),
            Json(UpsertOpsRoleInput {
                role: "ops_reviewer".to_string(),
            }),
        )
        .await?
        .into_response();
        assert_eq!(upsert_resp.status(), StatusCode::OK);
        let upsert_body = upsert_resp.into_body().collect().await?.to_bytes();
        let upsert_json: serde_json::Value = serde_json::from_slice(&upsert_body)?;
        assert_eq!(upsert_json["userId"], 2);
        assert_eq!(upsert_json["role"], "ops_reviewer");

        let list_resp =
            list_ops_role_assignments_handler(Extension(owner.clone()), State(state.clone()))
                .await?
                .into_response();
        assert_eq!(list_resp.status(), StatusCode::OK);
        let list_body = list_resp.into_body().collect().await?.to_bytes();
        let list_json: serde_json::Value = serde_json::from_slice(&list_body)?;
        assert_eq!(list_json["items"].as_array().map(Vec::len), Some(1));

        let revoke_resp =
            revoke_ops_role_assignment_handler(Extension(owner), State(state), Path(2_u64))
                .await?
                .into_response();
        assert_eq!(revoke_resp.status(), StatusCode::OK);
        let revoke_body = revoke_resp.into_body().collect().await?.to_bytes();
        let revoke_json: serde_json::Value = serde_json::from_slice(&revoke_body)?;
        assert_eq!(revoke_json["removed"], true);
        Ok(())
    }

    #[tokio::test]
    async fn get_ops_rbac_me_handler_should_return_owner_and_role_snapshot() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let viewer = state
            .find_user_by_id(2)
            .await?
            .expect("viewer should exist");

        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                viewer.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_viewer".to_string(),
                },
            )
            .await?;

        let owner_resp = get_ops_rbac_me_handler(Extension(owner), State(state.clone()))
            .await?
            .into_response();
        assert_eq!(owner_resp.status(), StatusCode::OK);
        let owner_body = owner_resp.into_body().collect().await?.to_bytes();
        let owner_json: serde_json::Value = serde_json::from_slice(&owner_body)?;
        assert_eq!(owner_json["isOwner"], true);
        assert_eq!(owner_json["permissions"]["debateManage"], true);
        assert_eq!(owner_json["permissions"]["judgeReview"], true);
        assert_eq!(owner_json["permissions"]["judgeRejudge"], true);
        assert_eq!(owner_json["permissions"]["roleManage"], true);

        let viewer_resp = get_ops_rbac_me_handler(Extension(viewer), State(state))
            .await?
            .into_response();
        assert_eq!(viewer_resp.status(), StatusCode::OK);
        let viewer_body = viewer_resp.into_body().collect().await?.to_bytes();
        let viewer_json: serde_json::Value = serde_json::from_slice(&viewer_body)?;
        assert_eq!(viewer_json["isOwner"], false);
        assert_eq!(viewer_json["role"], "ops_viewer");
        assert_eq!(viewer_json["permissions"]["debateManage"], false);
        assert_eq!(viewer_json["permissions"]["judgeReview"], true);
        assert_eq!(viewer_json["permissions"]["judgeRejudge"], false);
        assert_eq!(viewer_json["permissions"]["roleManage"], false);
        Ok(())
    }

    #[tokio::test]
    async fn list_ops_role_assignments_handler_should_return_standardized_denied_error_for_non_owner(
    ) -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let non_owner = state.find_user_by_id(2).await?.expect("user should exist");

        let result = list_ops_role_assignments_handler(Extension(non_owner), State(state)).await;
        match result {
            Ok(_) => panic!("non owner should be rejected"),
            Err(AppError::DebateConflict(msg)) => {
                assert!(msg.starts_with("ops_permission_denied:role_manage:"));
            }
            Err(other) => panic!("unexpected error: {}", other),
        }
        Ok(())
    }

    #[tokio::test]
    async fn get_ops_observability_config_handler_should_return_default_snapshot() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");

        let response = get_ops_observability_config_handler(Extension(owner), State(state))
            .await?
            .into_response();
        assert_eq!(response.status(), StatusCode::OK);
        let body = response.into_body().collect().await?.to_bytes();
        let ret: serde_json::Value = serde_json::from_slice(&body)?;
        assert_eq!(ret["thresholds"]["lowSuccessRateThreshold"], 80.0);
        assert_eq!(ret["anomalyState"].as_object().map(|v| v.len()), Some(0));
        Ok(())
    }

    #[tokio::test]
    async fn ops_observability_config_handlers_should_require_judge_review_permission() -> Result<()>
    {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let non_owner = state.find_user_by_id(3).await?.expect("user should exist");

        let get_err = match get_ops_observability_config_handler(
            Extension(non_owner.clone()),
            State(state.clone()),
        )
        .await
        {
            Ok(_) => panic!("user without ops role should be rejected"),
            Err(err) => err,
        };
        match get_err {
            AppError::DebateConflict(msg) => {
                assert!(msg.starts_with("ops_permission_denied:judge_review:"));
            }
            other => panic!("unexpected get error: {}", other),
        }

        let put_err = match upsert_ops_observability_thresholds_handler(
            Extension(non_owner),
            State(state),
            Json(OpsObservabilityThresholds::default()),
        )
        .await
        {
            Ok(_) => panic!("user without ops role should be rejected"),
            Err(err) => err,
        };
        match put_err {
            AppError::DebateConflict(msg) => {
                assert!(msg.starts_with("ops_permission_denied:judge_review:"));
            }
            other => panic!("unexpected put error: {}", other),
        }
        Ok(())
    }

    #[tokio::test]
    async fn ops_observability_config_handlers_should_allow_ops_viewer_update() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let viewer = state
            .find_user_by_id(2)
            .await?
            .expect("viewer should exist");
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                viewer.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_viewer".to_string(),
                },
            )
            .await?;

        let threshold_resp = upsert_ops_observability_thresholds_handler(
            Extension(viewer.clone()),
            State(state.clone()),
            Json(OpsObservabilityThresholds {
                low_success_rate_threshold: 76.0,
                high_retry_threshold: 1.2,
                high_coalesced_threshold: 2.2,
                high_db_latency_threshold_ms: 1300,
                low_cache_hit_rate_threshold: 18.0,
                min_request_for_cache_hit_check: 26,
            }),
        )
        .await?
        .into_response();
        assert_eq!(threshold_resp.status(), StatusCode::OK);

        let anomaly_resp = upsert_ops_observability_anomaly_state_handler(
            Extension(viewer),
            State(state),
            Json(UpdateOpsObservabilityAnomalyStateInput {
                anomaly_state: HashMap::from([(
                    "high_retry:8".to_string(),
                    crate::OpsObservabilityAnomalyStateValue {
                        acknowledged_at_ms: 1000,
                        suppress_until_ms: Utc::now().timestamp_millis() + 10_000,
                    },
                )]),
            }),
        )
        .await?
        .into_response();
        assert_eq!(anomaly_resp.status(), StatusCode::OK);
        let body = anomaly_resp.into_body().collect().await?.to_bytes();
        let ret: serde_json::Value = serde_json::from_slice(&body)?;
        assert_eq!(ret["thresholds"]["lowSuccessRateThreshold"], 76.0);
        assert!(ret["anomalyState"]["high_retry:8"].is_object());
        Ok(())
    }

    #[tokio::test]
    async fn list_kafka_dlq_events_handler_should_require_judge_review_permission() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let non_owner = state.find_user_by_id(3).await?.expect("user should exist");

        let result = list_kafka_dlq_events_handler(
            Extension(non_owner),
            State(state),
            Query(ListKafkaDlqEventsQuery {
                status: None,
                event_type: None,
                limit: Some(20),
                offset: Some(0),
            }),
        )
        .await;

        match result {
            Ok(_) => panic!("user without ops role should be rejected"),
            Err(AppError::DebateConflict(msg)) => {
                assert!(msg.starts_with("ops_permission_denied:judge_review:"));
            }
            Err(other) => panic!("unexpected error: {}", other),
        }
        Ok(())
    }

    #[tokio::test]
    async fn kafka_dlq_handlers_should_list_replay_and_discard() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let viewer = state
            .find_user_by_id(2)
            .await?
            .expect("viewer should exist");
        let reviewer = state
            .find_user_by_id(3)
            .await?
            .expect("reviewer should exist");

        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                viewer.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_viewer".to_string(),
                },
            )
            .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                reviewer.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_reviewer".to_string(),
                },
            )
            .await?;

        let session_id = seed_topic_and_session(&state, 1, "judging").await?;
        let job_id = seed_running_judge_job(&state, session_id).await?;
        let envelope = crate::event_bus::EventEnvelope::new(
            "ai.judge.job.created",
            "chat-server",
            format!("session:{}", session_id),
            serde_json::json!({
                "wsId": 1,
                "sessionId": session_id,
                "jobId": job_id,
                "requestedBy": 1,
                "styleMode": "rational",
                "rejudgeTriggered": false,
                "requestedAt": Utc::now(),
            }),
        );
        let replay_id = insert_kafka_dlq_event(
            &state,
            1,
            "replay-event-1",
            serde_json::to_value(&envelope)?,
        )
        .await?;
        let discard_id = insert_kafka_dlq_event(
            &state,
            1,
            "discard-event-1",
            serde_json::to_value(&envelope)?,
        )
        .await?;

        let list_resp = list_kafka_dlq_events_handler(
            Extension(viewer.clone()),
            State(state.clone()),
            Query(ListKafkaDlqEventsQuery {
                status: Some("pending".to_string()),
                event_type: None,
                limit: Some(50),
                offset: Some(0),
            }),
        )
        .await?
        .into_response();
        assert_eq!(list_resp.status(), StatusCode::OK);
        let list_body = list_resp.into_body().collect().await?.to_bytes();
        let list_json: serde_json::Value = serde_json::from_slice(&list_body)?;
        assert!(list_json["items"]
            .as_array()
            .map(|v| !v.is_empty())
            .unwrap_or(false));

        let replay_resp = replay_kafka_dlq_event_handler(
            Extension(reviewer.clone()),
            State(state.clone()),
            Path(replay_id as u64),
        )
        .await?
        .into_response();
        assert_eq!(replay_resp.status(), StatusCode::OK);
        let replay_body = replay_resp.into_body().collect().await?.to_bytes();
        let replay_json: serde_json::Value = serde_json::from_slice(&replay_body)?;
        assert_eq!(replay_json["status"], "replayed");

        let discard_resp = discard_kafka_dlq_event_handler(
            Extension(reviewer),
            State(state),
            Path(discard_id as u64),
        )
        .await?
        .into_response();
        assert_eq!(discard_resp.status(), StatusCode::OK);
        let discard_body = discard_resp.into_body().collect().await?.to_bytes();
        let discard_json: serde_json::Value = serde_json::from_slice(&discard_body)?;
        assert_eq!(discard_json["status"], "discarded");
        Ok(())
    }

    #[tokio::test]
    async fn list_ops_alert_notifications_handler_should_return_rows() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.update_workspace_owner(1, 1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        insert_ops_alert_notification(&state, 1, "high_retry").await?;

        let response = list_ops_alert_notifications_handler(
            Extension(owner),
            State(state),
            Query(ListOpsAlertNotificationsQuery {
                status: Some("raised".to_string()),
                limit: Some(20),
                offset: Some(0),
            }),
        )
        .await?
        .into_response();
        assert_eq!(response.status(), StatusCode::OK);
        let body = response.into_body().collect().await?.to_bytes();
        let ret: serde_json::Value = serde_json::from_slice(&body)?;
        assert_eq!(ret["total"], 1);
        assert_eq!(ret["items"].as_array().map(|v| v.len()), Some(1));
        assert_eq!(ret["items"][0]["alertKey"], "high_retry");
        Ok(())
    }
}
