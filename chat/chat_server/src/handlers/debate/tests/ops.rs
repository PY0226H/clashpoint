use super::super::{
    apply_ops_observability_anomaly_action_handler, discard_kafka_dlq_event_handler,
    get_judge_replay_preview_ops_handler, get_ops_observability_config_handler,
    get_ops_observability_metrics_dictionary_handler, get_ops_observability_slo_snapshot_handler,
    get_ops_rbac_me_handler, get_ops_service_split_readiness_handler,
    list_judge_final_dispatch_failure_stats_ops_handler, list_judge_reviews_ops_handler,
    list_judge_trace_replay_ops_handler, list_kafka_dlq_events_handler,
    list_ops_alert_notifications_handler, list_ops_role_assignments_handler,
    list_ops_service_split_review_audits_handler, replay_kafka_dlq_event_handler,
    request_judge_rejudge_ops_handler, revoke_ops_role_assignment_handler,
    run_ops_observability_evaluation_once_handler, upsert_ops_observability_anomaly_state_handler,
    upsert_ops_observability_thresholds_handler, upsert_ops_role_assignment_handler,
    upsert_ops_service_split_review_handler,
};
use super::test_support::{
    assert_debate_conflict_prefix, assert_is_debate_conflict, insert_kafka_dlq_event,
    insert_ops_alert_notification, json_body_with_status, seed_running_judge_job,
    seed_topic_and_session,
};
use crate::{
    AppState, ApplyOpsObservabilityAnomalyActionInput, GetJudgeFinalDispatchFailureStatsQuery,
    GetJudgeReplayPreviewOpsQuery, ListJudgeReviewOpsQuery, ListJudgeTraceReplayOpsQuery,
    ListKafkaDlqEventsQuery, ListOpsAlertNotificationsQuery, ListOpsServiceSplitReviewAuditsQuery,
    OpsObservabilityThresholds, RunOpsObservabilityEvaluationQuery,
    UpdateOpsObservabilityAnomalyStateInput, UpsertOpsRoleInput, UpsertOpsServiceSplitReviewInput,
};
use anyhow::Result;
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::IntoResponse,
    Extension, Json,
};
use chrono::Utc;
use std::collections::HashMap;

#[tokio::test]
async fn list_judge_reviews_ops_handler_should_require_platform_admin() -> Result<()> {
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
    assert_is_debate_conflict(result);
    Ok(())
}

#[tokio::test]
async fn list_judge_final_dispatch_failure_stats_ops_handler_should_require_platform_admin(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let non_owner = state.find_user_by_id(2).await?.expect("user should exist");

    let result = list_judge_final_dispatch_failure_stats_ops_handler(
        Extension(non_owner),
        State(state),
        Query(GetJudgeFinalDispatchFailureStatsQuery {
            from: None,
            to: None,
            limit: Some(100),
        }),
    )
    .await;
    assert_is_debate_conflict(result);
    Ok(())
}

#[tokio::test]
async fn list_judge_final_dispatch_failure_stats_ops_handler_should_return_aggregated_stats(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");

    let session_id = seed_topic_and_session(&state, "closed").await?;
    sqlx::query(
        r#"
        INSERT INTO judge_final_jobs(
            session_id, phase_start_no, phase_end_no,
            status, trace_id, idempotency_key, rubric_version, judge_policy_version,
            topic_domain, dispatch_attempts, last_dispatch_at, error_message
        )
        VALUES (
            $1, 1, 2,
            'failed', $2, $3, 'v3', 'v3-default',
            'default', 1, NOW(), $4
        )
        "#,
    )
    .bind(session_id)
    .bind(format!("trace-final-failed-ops-{session_id}"))
    .bind(format!(
        "judge_final_failed_ops:{session_id}:1:2:v3:v3-default"
    ))
    .bind(
        "[response_accepted_false] final dispatch response rejected: accepted=false, status=queued",
    )
    .execute(&state.pool)
    .await?;

    let response = list_judge_final_dispatch_failure_stats_ops_handler(
        Extension(owner),
        State(state),
        Query(GetJudgeFinalDispatchFailureStatsQuery {
            from: None,
            to: None,
            limit: Some(100),
        }),
    )
    .await?
    .into_response();
    let ret = json_body_with_status(response, StatusCode::OK).await?;
    assert_eq!(ret["totalFailedJobs"], 1);
    assert_eq!(ret["scannedFailedJobs"], 1);
    assert_eq!(ret["unknownFailedJobs"], 0);
    assert_eq!(ret["byType"][0]["failureType"], "response_accepted_false");
    assert_eq!(ret["byType"][0]["count"], 1);
    Ok(())
}

#[tokio::test]
async fn list_judge_trace_replay_ops_handler_should_require_platform_admin() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let non_owner = state.find_user_by_id(2).await?.expect("user should exist");

    let result = list_judge_trace_replay_ops_handler(
        Extension(non_owner),
        State(state),
        Query(ListJudgeTraceReplayOpsQuery {
            from: None,
            to: None,
            session_id: None,
            scope: None,
            status: None,
            limit: Some(20),
        }),
    )
    .await;
    assert_is_debate_conflict(result);
    Ok(())
}

#[tokio::test]
async fn list_judge_trace_replay_ops_handler_should_return_phase_and_final_items() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");
    let session_id = seed_topic_and_session(&state, "closed").await?;

    let message_a: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO session_messages(session_id, user_id, side, content)
        VALUES ($1, 1, 'pro', 'trace replay message a')
        RETURNING id
        "#,
    )
    .bind(session_id)
    .fetch_one(&state.pool)
    .await?;
    let message_b: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO session_messages(session_id, user_id, side, content)
        VALUES ($1, 1, 'con', 'trace replay message b')
        RETURNING id
        "#,
    )
    .bind(session_id)
    .fetch_one(&state.pool)
    .await?;

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
    .bind(message_a.0)
    .bind(message_b.0)
    .bind(format!("trace-phase-ops-{session_id}"))
    .bind(format!("judge_phase_ops:{session_id}:1:v3:v3-default"))
    .bind("[http_5xx] phase dispatch request failed")
    .fetch_one(&state.pool)
    .await?;
    sqlx::query(
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
        "#,
    )
    .bind(phase_job_id.0)
    .bind(session_id)
    .bind(message_a.0)
    .bind(message_b.0)
    .execute(&state.pool)
    .await?;

    let final_job_id: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO judge_final_jobs(
            session_id, phase_start_no, phase_end_no,
            status, trace_id, idempotency_key, rubric_version, judge_policy_version,
            topic_domain, dispatch_attempts, last_dispatch_at, error_message
        )
        VALUES (
            $1, 1, 1,
            'failed', $2, $3, 'v3', 'v3-default',
            'default', 1, NOW(), $4
        )
        RETURNING id
        "#,
    )
    .bind(session_id)
    .bind(format!("trace-final-ops-{session_id}"))
    .bind(format!("judge_final_ops:{session_id}:1:1:v3:v3-default"))
    .bind("[final_contract_blocked] missing final report fields")
    .fetch_one(&state.pool)
    .await?;
    sqlx::query(
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
            '{}'::jsonb, 'ops trace replay', '[]'::jsonb,
            '[]'::jsonb, '[]'::jsonb,
            'draw', 'draw', false, true,
            '{}'::jsonb, '[]'::jsonb, '[]'::jsonb, 0
        )
        "#,
    )
    .bind(final_job_id.0)
    .bind(session_id)
    .execute(&state.pool)
    .await?;

    let response = list_judge_trace_replay_ops_handler(
        Extension(owner),
        State(state),
        Query(ListJudgeTraceReplayOpsQuery {
            from: None,
            to: None,
            session_id: None,
            scope: None,
            status: None,
            limit: Some(50),
        }),
    )
    .await?
    .into_response();
    let ret = json_body_with_status(response, StatusCode::OK).await?;
    assert_eq!(ret["returnedCount"], 2);
    assert_eq!(ret["phaseCount"], 1);
    assert_eq!(ret["finalCount"], 1);
    assert_eq!(ret["failedCount"], 2);
    assert_eq!(ret["replayEligibleCount"], 2);

    let items = ret["items"].as_array().expect("items should be array");
    let phase_item = items
        .iter()
        .find(|item| item["scope"] == "phase")
        .expect("phase item should exist");
    assert_eq!(
        phase_item["phaseJobId"].as_u64(),
        Some(phase_job_id.0 as u64)
    );
    assert_eq!(
        phase_item["replayRecommendation"].as_str(),
        Some("replay_phase_job")
    );
    assert_eq!(phase_item["errorCode"].as_str(), Some("http_5xx"));

    let final_item = items
        .iter()
        .find(|item| item["scope"] == "final")
        .expect("final item should exist");
    assert_eq!(
        final_item["finalJobId"].as_u64(),
        Some(final_job_id.0 as u64)
    );
    assert_eq!(
        final_item["contractFailureType"].as_str(),
        Some("final_contract_blocked")
    );
    assert_eq!(
        final_item["replayRecommendation"].as_str(),
        Some("replay_final_job")
    );
    Ok(())
}

#[tokio::test]
async fn get_judge_replay_preview_ops_handler_should_require_platform_admin() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let non_owner = state.find_user_by_id(2).await?.expect("user should exist");

    let result = get_judge_replay_preview_ops_handler(
        Extension(non_owner),
        State(state),
        Query(GetJudgeReplayPreviewOpsQuery {
            scope: "final".to_string(),
            job_id: 1,
        }),
    )
    .await;
    assert_is_debate_conflict(result);
    Ok(())
}

#[tokio::test]
async fn get_judge_replay_preview_ops_handler_should_return_phase_snapshot() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");
    let session_id = seed_topic_and_session(&state, "closed").await?;

    let message_a: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO session_messages(session_id, user_id, side, content)
        VALUES ($1, 1, 'pro', 'replay preview message a')
        RETURNING id
        "#,
    )
    .bind(session_id)
    .fetch_one(&state.pool)
    .await?;
    let message_b: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO session_messages(session_id, user_id, side, content)
        VALUES ($1, 2, 'con', 'replay preview message b')
        RETURNING id
        "#,
    )
    .bind(session_id)
    .fetch_one(&state.pool)
    .await?;
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
    .bind(message_a.0)
    .bind(message_b.0)
    .bind(format!("trace-phase-preview-{session_id}"))
    .bind(format!("judge_phase_preview:{session_id}:1:v3:v3-default"))
    .bind("[http_5xx] phase dispatch request failed")
    .fetch_one(&state.pool)
    .await?;

    let response = get_judge_replay_preview_ops_handler(
        Extension(owner),
        State(state),
        Query(GetJudgeReplayPreviewOpsQuery {
            scope: "phase".to_string(),
            job_id: phase_job_id.0 as u64,
        }),
    )
    .await?
    .into_response();
    let ret = json_body_with_status(response, StatusCode::OK).await?;
    assert_eq!(ret["sideEffectFree"], true);
    assert_eq!(ret["meta"]["scope"], "phase");
    assert_eq!(ret["meta"]["replayEligible"], true);
    assert_eq!(
        ret["requestSnapshot"]["job_id"].as_u64(),
        Some(phase_job_id.0 as u64)
    );
    assert_eq!(
        ret["requestSnapshot"]["messages"].as_array().unwrap().len(),
        2
    );
    assert_eq!(ret["snapshotHash"].as_str().map(str::len), Some(40));
    Ok(())
}

#[tokio::test]
async fn request_judge_rejudge_ops_handler_should_accept_when_report_exists() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");
    let session_id = seed_topic_and_session(&state, "closed").await?;
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

    let response =
        request_judge_rejudge_ops_handler(Extension(owner), State(state), Path(session_id as u64))
            .await?
            .into_response();

    let ret = json_body_with_status(response, StatusCode::ACCEPTED).await?;
    assert_eq!(ret["rejudgeTriggered"], true);
    Ok(())
}

#[tokio::test]
async fn ops_rbac_role_handlers_should_upsert_list_and_revoke() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
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
    let upsert_json = json_body_with_status(upsert_resp, StatusCode::OK).await?;
    assert_eq!(upsert_json["userId"], 2);
    assert_eq!(upsert_json["role"], "ops_reviewer");

    let list_resp =
        list_ops_role_assignments_handler(Extension(owner.clone()), State(state.clone()))
            .await?
            .into_response();
    let list_json = json_body_with_status(list_resp, StatusCode::OK).await?;
    let items = list_json["items"].as_array().cloned().unwrap_or_default();
    assert!(!items.is_empty());
    assert!(items.iter().any(|item| {
        item["userId"].as_u64() == Some(2) && item["role"].as_str() == Some("ops_reviewer")
    }));

    let revoke_resp =
        revoke_ops_role_assignment_handler(Extension(owner), State(state), Path(2_u64))
            .await?
            .into_response();
    let revoke_json = json_body_with_status(revoke_resp, StatusCode::OK).await?;
    assert_eq!(revoke_json["removed"], true);
    Ok(())
}

#[tokio::test]
async fn get_ops_rbac_me_handler_should_return_owner_and_role_snapshot() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
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
    let owner_json = json_body_with_status(owner_resp, StatusCode::OK).await?;
    assert_eq!(owner_json["isOwner"], true);
    assert_eq!(owner_json["permissions"]["debateManage"], true);
    assert_eq!(owner_json["permissions"]["judgeReview"], true);
    assert_eq!(owner_json["permissions"]["judgeRejudge"], true);
    assert_eq!(owner_json["permissions"]["roleManage"], true);

    let viewer_resp = get_ops_rbac_me_handler(Extension(viewer), State(state))
        .await?
        .into_response();
    let viewer_json = json_body_with_status(viewer_resp, StatusCode::OK).await?;
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
    state.grant_platform_admin(1).await?;
    let non_owner = state.find_user_by_id(2).await?.expect("user should exist");

    let result = list_ops_role_assignments_handler(Extension(non_owner), State(state)).await;
    assert_debate_conflict_prefix(result, "ops_permission_denied:role_manage:");
    Ok(())
}

#[tokio::test]
async fn get_ops_observability_config_handler_should_return_default_snapshot() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");

    let response = get_ops_observability_config_handler(Extension(owner), State(state))
        .await?
        .into_response();
    let ret = json_body_with_status(response, StatusCode::OK).await?;
    assert_eq!(ret["thresholds"]["lowSuccessRateThreshold"], 80.0);
    assert_eq!(ret["anomalyState"].as_object().map(|v| v.len()), Some(0));
    Ok(())
}

#[tokio::test]
async fn ops_observability_config_handlers_should_require_judge_review_permission() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let non_owner = state.find_user_by_id(3).await?.expect("user should exist");

    let get_result =
        get_ops_observability_config_handler(Extension(non_owner.clone()), State(state.clone()))
            .await;
    assert_debate_conflict_prefix(get_result, "ops_permission_denied:judge_review:");

    let put_result = upsert_ops_observability_thresholds_handler(
        Extension(non_owner.clone()),
        State(state.clone()),
        Json(OpsObservabilityThresholds::default()),
    )
    .await;
    assert_debate_conflict_prefix(put_result, "ops_permission_denied:judge_review:");

    let dict_result = get_ops_observability_metrics_dictionary_handler(
        Extension(non_owner.clone()),
        State(state.clone()),
    )
    .await;
    assert_debate_conflict_prefix(dict_result, "ops_permission_denied:judge_review:");

    let slo_result = get_ops_observability_slo_snapshot_handler(
        Extension(non_owner.clone()),
        State(state.clone()),
    )
    .await;
    assert_debate_conflict_prefix(slo_result, "ops_permission_denied:judge_review:");

    let split_result =
        get_ops_service_split_readiness_handler(Extension(non_owner.clone()), State(state.clone()))
            .await;
    assert_debate_conflict_prefix(split_result, "ops_permission_denied:judge_review:");

    let split_reviews_result = list_ops_service_split_review_audits_handler(
        Extension(non_owner.clone()),
        State(state.clone()),
        Query(ListOpsServiceSplitReviewAuditsQuery {
            limit: None,
            offset: None,
        }),
    )
    .await;
    assert_debate_conflict_prefix(split_reviews_result, "ops_permission_denied:judge_review:");

    let split_review_result = upsert_ops_service_split_review_handler(
        Extension(non_owner.clone()),
        State(state.clone()),
        Json(UpsertOpsServiceSplitReviewInput {
            payment_compliance_required: Some(true),
            review_note: Some("compliance required".to_string()),
        }),
    )
    .await;
    assert_debate_conflict_prefix(split_review_result, "ops_permission_denied:judge_review:");

    let action_result = apply_ops_observability_anomaly_action_handler(
        Extension(non_owner.clone()),
        State(state.clone()),
        Json(ApplyOpsObservabilityAnomalyActionInput {
            alert_key: "high_retry".to_string(),
            action: "suppress".to_string(),
            suppress_minutes: Some(5),
        }),
    )
    .await;
    assert_debate_conflict_prefix(action_result, "ops_permission_denied:judge_review:");

    let eval_result = run_ops_observability_evaluation_once_handler(
        Extension(non_owner),
        State(state),
        Query(RunOpsObservabilityEvaluationQuery { dry_run: None }),
    )
    .await;
    assert_debate_conflict_prefix(eval_result, "ops_permission_denied:judge_review:");
    Ok(())
}

#[tokio::test]
async fn get_ops_observability_metrics_dictionary_handler_should_return_canonical_items(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");

    let response = get_ops_observability_metrics_dictionary_handler(Extension(owner), State(state))
        .await?
        .into_response();
    let ret = json_body_with_status(response, StatusCode::OK).await?;
    assert_eq!(ret["version"], "v1");
    let items = ret["items"].as_array().expect("items should be array");
    assert!(items.len() >= 10);
    assert!(items.iter().any(|v| v["key"] == "api.request_total"));
    assert!(items
        .iter()
        .any(|v| v["key"] == "judge.dispatch.failed_total"));
    assert!(items.iter().any(|v| v["key"] == "ws.replay.backlog_size"));
    assert!(items.iter().any(|v| v["key"] == "iap.verify.error_total"));
    Ok(())
}

#[tokio::test]
async fn get_ops_observability_slo_snapshot_handler_should_return_signal_and_rules() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");

    let response = get_ops_observability_slo_snapshot_handler(Extension(owner), State(state))
        .await?
        .into_response();
    let ret = json_body_with_status(response, StatusCode::OK).await?;
    assert_eq!(ret["windowMinutes"], 10);
    let signal = ret["signal"].as_object().expect("signal should be object");
    assert!(signal.contains_key("successCount"));
    assert!(signal.contains_key("failedCount"));
    assert!(signal.contains_key("completedCount"));
    assert!(signal.contains_key("successRatePct"));
    assert!(signal.contains_key("avgDispatchAttempts"));
    assert!(signal.contains_key("p95LatencyMs"));
    assert!(signal.contains_key("pendingDlqCount"));
    let rules = ret["rules"].as_array().expect("rules should be array");
    assert!(rules.len() >= 4);
    assert!(rules.iter().any(|v| v["alertKey"] == "low_success_rate"));
    assert!(rules.iter().any(|v| v["alertKey"] == "high_retry"));
    assert!(rules.iter().any(|v| v["alertKey"] == "high_db_latency"));
    assert!(rules.iter().any(|v| v["alertKey"] == "dlq_pending"));
    Ok(())
}

#[tokio::test]
async fn get_ops_service_split_readiness_handler_should_return_thresholds() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");

    let response = get_ops_service_split_readiness_handler(Extension(owner), State(state))
        .await?
        .into_response();
    let ret = json_body_with_status(response, StatusCode::OK).await?;
    assert!(ret["generatedAtMs"].as_i64().unwrap_or_default() > 0);
    let thresholds = ret["thresholds"]
        .as_array()
        .expect("thresholds should be array");
    assert_eq!(thresholds.len(), 3);
    assert!(thresholds
        .iter()
        .any(|v| v["key"] == "judge_dispatch_pressure"));
    assert!(thresholds
        .iter()
        .any(|v| v["key"] == "payment_compliance_isolation"));
    assert!(thresholds
        .iter()
        .any(|v| v["key"] == "ws_online_scale_limit"));
    assert!(
        ret["overallStatus"] == "hold" || ret["overallStatus"] == "review_required",
        "unexpected overall status: {}",
        ret["overallStatus"]
    );
    Ok(())
}

#[tokio::test]
async fn upsert_ops_service_split_review_handler_should_update_compliance_threshold() -> Result<()>
{
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");

    let response = upsert_ops_service_split_review_handler(
        Extension(owner),
        State(state),
        Json(UpsertOpsServiceSplitReviewInput {
            payment_compliance_required: Some(true),
            review_note: Some("payment compliance requires isolated deployment".to_string()),
        }),
    )
    .await?
    .into_response();
    let ret = json_body_with_status(response, StatusCode::OK).await?;
    let thresholds = ret["thresholds"]
        .as_array()
        .expect("thresholds should be array");
    let compliance = thresholds
        .iter()
        .find(|v| v["key"] == "payment_compliance_isolation")
        .expect("payment threshold should exist");
    assert_eq!(compliance["status"], "met");
    assert_eq!(compliance["triggered"], true);
    assert_eq!(
        compliance["evidence"]["paymentComplianceRequired"],
        serde_json::Value::Bool(true)
    );
    assert_eq!(
        ret["overallStatus"], "review_required",
        "payment compliance requirement should trigger review"
    );
    Ok(())
}

#[tokio::test]
async fn upsert_ops_service_split_review_handler_should_emit_transition_alert_once() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");

    let baseline =
        get_ops_service_split_readiness_handler(Extension(owner.clone()), State(state.clone()))
            .await?
            .into_response();
    let baseline_json = json_body_with_status(baseline, StatusCode::OK).await?;
    assert_eq!(
        baseline_json["overallStatus"], "hold",
        "fresh platform scope should start from hold status in this test setup"
    );

    upsert_ops_service_split_review_handler(
        Extension(owner.clone()),
        State(state.clone()),
        Json(UpsertOpsServiceSplitReviewInput {
            payment_compliance_required: Some(true),
            review_note: Some("trigger split review required".to_string()),
        }),
    )
    .await?;

    let alert_count_after_first: i64 = sqlx::query_scalar(
        r#"
        SELECT COUNT(1)::bigint
        FROM ops_alert_notifications
        WHERE alert_key = 'split_readiness_review_required'
          AND alert_status = 'raised'
        "#,
    )
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(
        alert_count_after_first, 1,
        "hold -> review_required transition should emit one alert"
    );

    upsert_ops_service_split_review_handler(
        Extension(owner),
        State(state.clone()),
        Json(UpsertOpsServiceSplitReviewInput {
            payment_compliance_required: Some(true),
            review_note: Some("still review required".to_string()),
        }),
    )
    .await?;

    let alert_count_after_second: i64 = sqlx::query_scalar(
        r#"
        SELECT COUNT(1)::bigint
        FROM ops_alert_notifications
        WHERE alert_key = 'split_readiness_review_required'
          AND alert_status = 'raised'
        "#,
    )
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(
        alert_count_after_second, 1,
        "non-transition update should not emit duplicate alert"
    );
    Ok(())
}

#[tokio::test]
async fn upsert_ops_service_split_review_handler_should_emit_cleared_alert_once_on_review_required_to_hold(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");

    upsert_ops_service_split_review_handler(
        Extension(owner.clone()),
        State(state.clone()),
        Json(UpsertOpsServiceSplitReviewInput {
            payment_compliance_required: Some(true),
            review_note: Some("enter review required".to_string()),
        }),
    )
    .await?;

    upsert_ops_service_split_review_handler(
        Extension(owner.clone()),
        State(state.clone()),
        Json(UpsertOpsServiceSplitReviewInput {
            payment_compliance_required: Some(false),
            review_note: Some("back to hold".to_string()),
        }),
    )
    .await?;

    let cleared_count_after_first: i64 = sqlx::query_scalar(
        r#"
        SELECT COUNT(1)::bigint
        FROM ops_alert_notifications
        WHERE alert_key = 'split_readiness_review_required'
          AND alert_status = 'cleared'
        "#,
    )
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(
        cleared_count_after_first, 1,
        "review_required -> hold transition should emit one cleared alert"
    );

    upsert_ops_service_split_review_handler(
        Extension(owner),
        State(state.clone()),
        Json(UpsertOpsServiceSplitReviewInput {
            payment_compliance_required: Some(false),
            review_note: Some("still hold".to_string()),
        }),
    )
    .await?;

    let cleared_count_after_second: i64 = sqlx::query_scalar(
        r#"
        SELECT COUNT(1)::bigint
        FROM ops_alert_notifications
        WHERE alert_key = 'split_readiness_review_required'
          AND alert_status = 'cleared'
        "#,
    )
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(
        cleared_count_after_second, 1,
        "non-transition hold update should not emit duplicate cleared alert"
    );

    let is_active: bool = sqlx::query_scalar(
        r#"
        SELECT is_active
        FROM ops_alert_states
        WHERE alert_key = 'split_readiness_review_required'
        "#,
    )
    .fetch_one(&state.pool)
    .await?;
    assert!(
        !is_active,
        "split readiness alert state should become inactive after cleared transition"
    );
    Ok(())
}

#[tokio::test]
async fn list_ops_service_split_review_audits_handler_should_return_latest_first() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");

    upsert_ops_service_split_review_handler(
        Extension(owner.clone()),
        State(state.clone()),
        Json(UpsertOpsServiceSplitReviewInput {
            payment_compliance_required: Some(true),
            review_note: Some("first-review".to_string()),
        }),
    )
    .await?;
    upsert_ops_service_split_review_handler(
        Extension(owner.clone()),
        State(state.clone()),
        Json(UpsertOpsServiceSplitReviewInput {
            payment_compliance_required: Some(false),
            review_note: Some("second-review".to_string()),
        }),
    )
    .await?;

    let response = list_ops_service_split_review_audits_handler(
        Extension(owner),
        State(state),
        Query(ListOpsServiceSplitReviewAuditsQuery {
            limit: Some(10),
            offset: Some(0),
        }),
    )
    .await?
    .into_response();
    let ret = json_body_with_status(response, StatusCode::OK).await?;
    assert_eq!(ret["total"], 2);
    let items = ret["items"].as_array().expect("items should be array");
    assert_eq!(items.len(), 2);
    assert_eq!(items[0]["reviewNote"], "second-review");
    assert_eq!(items[0]["paymentComplianceRequired"], false);
    assert_eq!(items[1]["reviewNote"], "first-review");
    assert_eq!(items[1]["paymentComplianceRequired"], true);
    Ok(())
}

#[tokio::test]
async fn apply_ops_observability_anomaly_action_handler_should_update_single_alert_key(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");

    let suppress_response = apply_ops_observability_anomaly_action_handler(
        Extension(owner.clone()),
        State(state.clone()),
        Json(ApplyOpsObservabilityAnomalyActionInput {
            alert_key: "high_retry".to_string(),
            action: "suppress".to_string(),
            suppress_minutes: Some(5),
        }),
    )
    .await?
    .into_response();
    let suppress_json = json_body_with_status(suppress_response, StatusCode::OK).await?;
    let suppress_until_ms = suppress_json["anomalyState"]["high_retry"]["suppressUntilMs"]
        .as_i64()
        .unwrap_or_default();
    assert!(suppress_until_ms > Utc::now().timestamp_millis());

    let clear_response = apply_ops_observability_anomaly_action_handler(
        Extension(owner),
        State(state),
        Json(ApplyOpsObservabilityAnomalyActionInput {
            alert_key: "high_retry".to_string(),
            action: "clear".to_string(),
            suppress_minutes: None,
        }),
    )
    .await?
    .into_response();
    let clear_json = json_body_with_status(clear_response, StatusCode::OK).await?;
    assert!(clear_json["anomalyState"]["high_retry"].is_null());
    Ok(())
}

#[tokio::test]
async fn run_ops_observability_evaluation_once_handler_should_return_report() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");

    let response = run_ops_observability_evaluation_once_handler(
        Extension(owner),
        State(state),
        Query(RunOpsObservabilityEvaluationQuery { dry_run: None }),
    )
    .await?
    .into_response();
    let ret = json_body_with_status(response, StatusCode::OK).await?;
    assert_eq!(ret["scopesScanned"], 1);
    assert!(ret.get("alertsRaised").is_some());
    assert!(ret.get("alertsCleared").is_some());
    assert!(ret.get("alertsSuppressed").is_some());
    Ok(())
}

#[tokio::test]
async fn run_ops_observability_evaluation_once_handler_should_include_rate_limit_headers(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");

    let response = run_ops_observability_evaluation_once_handler(
        Extension(owner),
        State(state),
        Query(RunOpsObservabilityEvaluationQuery { dry_run: None }),
    )
    .await?
    .into_response();
    assert_eq!(response.status(), StatusCode::OK);
    assert!(response.headers().contains_key("x-ratelimit-limit"));
    assert!(response.headers().contains_key("x-ratelimit-remaining"));
    assert!(response.headers().contains_key("x-ratelimit-reset"));
    Ok(())
}

#[tokio::test]
async fn run_ops_observability_evaluation_once_handler_with_dry_run_should_not_emit_alerts(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");
    state
        .upsert_ops_observability_thresholds(
            &owner,
            OpsObservabilityThresholds {
                low_success_rate_threshold: 80.0,
                high_retry_threshold: 1.0,
                high_coalesced_threshold: 0.0,
                high_db_latency_threshold_ms: 1200,
                low_cache_hit_rate_threshold: 20.0,
                min_request_for_cache_hit_check: 1,
            },
        )
        .await?;
    insert_kafka_dlq_event(&state, "dry-run-dlq-1", serde_json::json!({"k":"v"})).await?;

    let before_count: i64 = sqlx::query_scalar(
        r#"
        SELECT COUNT(1)::bigint
        FROM ops_alert_notifications
        "#,
    )
    .fetch_one(&state.pool)
    .await?;

    let response = run_ops_observability_evaluation_once_handler(
        Extension(owner),
        State(state.clone()),
        Query(RunOpsObservabilityEvaluationQuery {
            dry_run: Some(true),
        }),
    )
    .await?
    .into_response();
    let ret = json_body_with_status(response, StatusCode::OK).await?;
    assert_eq!(ret["scopesScanned"], 1);
    assert_eq!(ret["alertsRaised"], 1);

    let after_count: i64 = sqlx::query_scalar(
        r#"
        SELECT COUNT(1)::bigint
        FROM ops_alert_notifications
        "#,
    )
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(after_count, before_count);
    Ok(())
}

#[tokio::test]
async fn ops_observability_config_handlers_should_allow_ops_viewer_update() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
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
    let ret = json_body_with_status(anomaly_resp, StatusCode::OK).await?;
    assert_eq!(ret["thresholds"]["lowSuccessRateThreshold"], 76.0);
    assert!(ret["anomalyState"]["high_retry:8"].is_object());
    Ok(())
}

#[tokio::test]
async fn list_kafka_dlq_events_handler_should_require_judge_review_permission() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
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

    assert_debate_conflict_prefix(result, "ops_permission_denied:judge_review:");
    Ok(())
}

#[tokio::test]
async fn kafka_dlq_handlers_should_list_replay_and_discard() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
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

    let session_id = seed_topic_and_session(&state, "judging").await?;
    let job_id = seed_running_judge_job(&state, session_id).await?;
    let envelope = crate::event_bus::EventEnvelope::new(
        "ai.judge.job.created",
        "chat-server",
        format!("session:{}", session_id),
        serde_json::json!({
            "scopeId": 1,
            "sessionId": session_id,
            "jobId": job_id,
            "requestedBy": 1,
            "styleMode": "rational",
            "rejudgeTriggered": false,
            "requestedAt": Utc::now(),
        }),
    );
    let replay_id =
        insert_kafka_dlq_event(&state, "replay-event-1", serde_json::to_value(&envelope)?).await?;
    let discard_id =
        insert_kafka_dlq_event(&state, "discard-event-1", serde_json::to_value(&envelope)?).await?;

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
    let list_json = json_body_with_status(list_resp, StatusCode::OK).await?;
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
    let replay_json = json_body_with_status(replay_resp, StatusCode::OK).await?;
    assert_eq!(replay_json["status"], "replayed");

    let discard_resp =
        discard_kafka_dlq_event_handler(Extension(reviewer), State(state), Path(discard_id as u64))
            .await?
            .into_response();
    let discard_json = json_body_with_status(discard_resp, StatusCode::OK).await?;
    assert_eq!(discard_json["status"], "discarded");
    Ok(())
}

#[tokio::test]
async fn list_ops_alert_notifications_handler_should_return_rows() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    state.grant_platform_admin(1).await?;
    let owner = state.find_user_by_id(1).await?.expect("owner should exist");
    insert_ops_alert_notification(&state, "high_retry").await?;

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
    let ret = json_body_with_status(response, StatusCode::OK).await?;
    assert_eq!(ret["total"], 1);
    assert_eq!(ret["items"].as_array().map(|v| v.len()), Some(1));
    assert_eq!(ret["items"][0]["alertKey"], "high_retry");
    Ok(())
}
