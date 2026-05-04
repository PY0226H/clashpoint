use super::*;
use serde_json::{json, Value};

const NPC_ID: &str = "virtual_judge_default";

#[derive(Debug, Clone, Copy)]
struct SeedNpcConfig {
    enabled: bool,
    status: &'static str,
    allow_speak: bool,
    allow_praise: bool,
    allow_effect: bool,
    allow_state_change: bool,
    allow_pause: bool,
}

#[tokio::test]
async fn npc_unavailable_should_not_block_debate_message_creation() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;

    let message =
        seed_joined_message(&state, session_id, 1, "pro", "normal message without npc").await?;

    assert_eq!(message.session_id, session_id);
    assert_eq!(message.content, "normal message without npc");
    assert_eq!(npc_action_count(&state).await?, 0);
    Ok(())
}

#[tokio::test]
async fn npc_decision_context_should_return_public_room_messages_only() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
    let first = seed_joined_message(&state, session_id, 1, "pro", "first public point").await?;
    let user = state
        .find_user_by_id(1)
        .await?
        .expect("fixture user should exist");
    let second = state
        .create_debate_message(
            session_id as u64,
            &user,
            CreateDebateMessageInput {
                content: "second public point".to_string(),
            },
        )
        .await?;

    let context = state
        .get_debate_npc_decision_context(
            session_id as u64,
            GetDebateNpcDecisionContextQuery {
                trigger_message_id: Some(second.id as u64),
                public_call_id: None,
                source_event_id: Some("evt-message-2".to_string()),
                limit: Some(10),
            },
        )
        .await?;
    let payload = serde_json::to_value(&context)?;

    assert_eq!(context.session_id, session_id as u64);
    assert_eq!(context.npc_id, NPC_ID);
    assert!(!context.room_config.enabled);
    assert_eq!(context.room_config.status, "unavailable");
    assert_eq!(context.source_event_id.as_deref(), Some("evt-message-2"));
    assert_eq!(
        context
            .trigger_message
            .as_ref()
            .expect("trigger should exist")
            .message_id,
        second.id
    );
    assert_eq!(
        context
            .trigger_message
            .as_ref()
            .expect("trigger should exist")
            .content,
        "second public point"
    );
    assert!(context.public_call.is_none());
    assert_eq!(context.recent_messages.len(), 2);
    assert_eq!(context.recent_messages[0].message_id, first.id);
    assert_eq!(context.recent_messages[1].message_id, second.id);
    assert!(payload.get("phone").is_none());
    assert!(payload.get("email").is_none());
    assert!(payload.get("walletBalance").is_none());
    assert!(payload.get("winner").is_none());
    Ok(())
}

#[tokio::test]
async fn npc_decision_context_should_reject_trigger_message_from_other_session() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
    let (_other_topic_id, other_session_id) = seed_topic_and_session(&state, "open", 10).await?;
    let other_message =
        seed_joined_message(&state, other_session_id, 1, "pro", "other room point").await?;

    let err = state
        .get_debate_npc_decision_context(
            session_id as u64,
            GetDebateNpcDecisionContextQuery {
                trigger_message_id: Some(other_message.id as u64),
                public_call_id: None,
                source_event_id: None,
                limit: Some(10),
            },
        )
        .await
        .expect_err("cross-room trigger should be rejected");

    assert!(matches!(err, AppError::NotFound(_)));
    Ok(())
}

#[tokio::test]
async fn npc_action_candidate_should_create_and_replay_by_action_uid() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
    seed_npc_config(&state, session_id, true, true, true, true).await?;
    let message = seed_joined_message(&state, session_id, 1, "pro", "first point").await?;

    let first = state
        .submit_debate_npc_action_candidate(praise_candidate(
            "npc-act-001",
            session_id,
            message.id,
            "这段推进很有力，现场加一分气氛值。",
        ))
        .await?;
    assert!(first.accepted);
    assert_eq!(first.status, "created");
    let action_id = first.action_id.expect("created action should have id");

    let second = state
        .submit_debate_npc_action_candidate(praise_candidate(
            "npc-act-001",
            session_id,
            message.id,
            "这段推进很有力，现场加一分气氛值。",
        ))
        .await?;
    assert!(second.accepted);
    assert_eq!(second.status, "replayed");
    assert_eq!(second.action_id, Some(action_id));

    let stored: DebateNpcAction = sqlx::query_as(
        r#"
        SELECT
          id, action_uid, session_id, npc_id, display_name, action_type, public_text,
          target_message_id, target_user_id, target_side, effect_kind, npc_status,
          reason_code, source_event_id, source_message_id, policy_version,
          executor_kind, executor_version, created_at
        FROM debate_npc_actions
        WHERE id = $1
        "#,
    )
    .bind(action_id as i64)
    .fetch_one(&state.pool)
    .await?;

    assert_eq!(stored.action_uid, "npc-act-001");
    assert_eq!(stored.session_id, session_id);
    assert_eq!(stored.npc_id, NPC_ID);
    assert_eq!(stored.display_name, "虚拟裁判");
    assert_eq!(stored.action_type, "praise");
    assert_eq!(
        stored.public_text.as_deref(),
        Some("这段推进很有力，现场加一分气氛值。")
    );
    assert_eq!(stored.target_message_id, Some(message.id));
    assert_eq!(stored.target_user_id, Some(1));
    assert_eq!(stored.target_side.as_deref(), Some("pro"));
    assert_eq!(stored.executor_kind, "llm_executor_v1");
    Ok(())
}

#[tokio::test]
async fn npc_action_candidate_should_reject_disabled_room_npc() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
    seed_npc_config(&state, session_id, false, true, true, true).await?;
    let message = seed_joined_message(&state, session_id, 1, "pro", "opening").await?;

    let output = state
        .submit_debate_npc_action_candidate(praise_candidate(
            "npc-act-disabled",
            session_id,
            message.id,
            "这句不错。",
        ))
        .await?;

    assert!(!output.accepted);
    assert_eq!(output.status, "rejected");
    assert_eq!(output.reason_code.as_deref(), Some("npc_disabled"));
    assert_eq!(npc_action_count(&state).await?, 0);
    Ok(())
}

#[tokio::test]
async fn npc_action_candidate_should_reject_non_active_room_status() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
    seed_npc_config_with_status(
        &state,
        session_id,
        SeedNpcConfig {
            enabled: true,
            status: "manual_takeover",
            allow_speak: true,
            allow_praise: true,
            allow_effect: true,
            allow_state_change: true,
            allow_pause: false,
        },
    )
    .await?;
    let message = seed_joined_message(&state, session_id, 1, "pro", "opening").await?;

    let output = state
        .submit_debate_npc_action_candidate(praise_candidate(
            "npc-act-manual-takeover",
            session_id,
            message.id,
            "这句不错。",
        ))
        .await?;

    assert!(!output.accepted);
    assert_eq!(output.status, "rejected");
    assert_eq!(output.reason_code.as_deref(), Some("npc_status_blocked"));
    assert_eq!(npc_action_count(&state).await?, 0);
    Ok(())
}

#[tokio::test]
async fn npc_action_candidate_should_reject_disabled_state_change_capability() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
    seed_npc_config_with_status(
        &state,
        session_id,
        SeedNpcConfig {
            enabled: true,
            status: "active",
            allow_speak: true,
            allow_praise: true,
            allow_effect: true,
            allow_state_change: false,
            allow_pause: false,
        },
    )
    .await?;

    let output = state
        .submit_debate_npc_action_candidate(state_changed_candidate(
            "npc-act-state-disabled",
            session_id,
            "silent",
        ))
        .await?;

    assert!(!output.accepted);
    assert_eq!(
        output.reason_code.as_deref(),
        Some("npc_capability_disabled")
    );
    assert_eq!(npc_action_count(&state).await?, 0);
    Ok(())
}

#[tokio::test]
async fn ops_npc_config_should_publish_manual_takeover_state_change() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
    state.grant_platform_admin(1).await?;
    let owner = state
        .find_user_by_id(1)
        .await?
        .expect("fixture user should exist");

    let config = state
        .upsert_debate_npc_room_config_by_ops(
            &owner,
            session_id as u64,
            UpsertDebateNpcRoomConfigInput {
                npc_id: None,
                display_name: None,
                enabled: Some(true),
                persona_style: Some("energetic_host".to_string()),
                status: Some("manual_takeover".to_string()),
                allow_speak: Some(true),
                allow_praise: Some(false),
                allow_effect: Some(false),
                allow_state_change: Some(true),
                allow_warning: Some(true),
                allow_public_call: Some(false),
                allow_pause: Some(false),
                status_reason: Some("ops_takeover".to_string()),
            },
        )
        .await?;

    assert_eq!(config.status, "manual_takeover");
    assert_eq!(config.manual_takeover_by_user_id, Some(owner.id));
    assert!(!config.allow_praise);
    assert!(!config.allow_effect);
    let stored: DebateNpcAction = sqlx::query_as(
        r#"
        SELECT
          id, action_uid, session_id, npc_id, display_name, action_type, public_text,
          target_message_id, target_user_id, target_side, effect_kind, npc_status,
          reason_code, source_event_id, source_message_id, policy_version,
          executor_kind, executor_version, created_at
        FROM debate_npc_actions
        WHERE session_id = $1 AND action_type = 'state_changed'
        "#,
    )
    .bind(session_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(stored.npc_status.as_deref(), Some("manual_takeover"));
    assert_eq!(stored.executor_kind, "ops_control_plane");
    assert_eq!(
        stored.public_text.as_deref(),
        Some("虚拟裁判已进入人工接管状态。")
    );
    Ok(())
}

#[tokio::test]
async fn ops_npc_config_should_disable_praise_candidate_at_chat_boundary() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
    state.grant_platform_admin(1).await?;
    let owner = state
        .find_user_by_id(1)
        .await?
        .expect("fixture user should exist");
    state
        .upsert_debate_npc_room_config_by_ops(
            &owner,
            session_id as u64,
            UpsertDebateNpcRoomConfigInput {
                npc_id: None,
                display_name: None,
                enabled: Some(true),
                persona_style: None,
                status: Some("active".to_string()),
                allow_speak: Some(true),
                allow_praise: Some(false),
                allow_effect: Some(false),
                allow_state_change: Some(true),
                allow_warning: Some(true),
                allow_public_call: Some(false),
                allow_pause: Some(false),
                status_reason: None,
            },
        )
        .await?;
    let message = seed_joined_message(&state, session_id, 1, "pro", "sharp point").await?;

    let output = state
        .submit_debate_npc_action_candidate(praise_candidate(
            "npc-act-praise-disabled-by-ops",
            session_id,
            message.id,
            "这句不错。",
        ))
        .await?;

    assert!(!output.accepted);
    assert_eq!(
        output.reason_code.as_deref(),
        Some("npc_capability_disabled")
    );
    Ok(())
}

#[tokio::test]
async fn npc_action_candidate_should_create_pause_suggestion_without_mutating_session_state(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
    seed_npc_config_with_status(
        &state,
        session_id,
        SeedNpcConfig {
            enabled: true,
            status: "active",
            allow_speak: true,
            allow_praise: true,
            allow_effect: true,
            allow_state_change: true,
            allow_pause: true,
        },
    )
    .await?;
    let message = seed_joined_message(&state, session_id, 1, "pro", "刚才这轮有点跑题。").await?;

    let first = state
        .submit_debate_npc_action_candidate(pause_suggestion_candidate(
            "npc-act-pause-suggestion-001",
            session_id,
            message.id,
            "我建议先短暂停一下，把争议焦点对齐后再继续。",
            Some("heated_exchange"),
        ))
        .await?;
    assert!(first.accepted);
    assert_eq!(first.status, "created");
    let action_id = first.action_id.expect("created action should have id");

    let second = state
        .submit_debate_npc_action_candidate(pause_suggestion_candidate(
            "npc-act-pause-suggestion-001",
            session_id,
            message.id,
            "我建议先短暂停一下，把争议焦点对齐后再继续。",
            Some("heated_exchange"),
        ))
        .await?;
    assert!(second.accepted);
    assert_eq!(second.status, "replayed");
    assert_eq!(second.action_id, Some(action_id));

    let stored: DebateNpcAction = sqlx::query_as(
        r#"
        SELECT
          id, action_uid, session_id, npc_id, display_name, action_type, public_text,
          target_message_id, target_user_id, target_side, effect_kind, npc_status,
          reason_code, source_event_id, source_message_id, policy_version,
          executor_kind, executor_version, created_at
        FROM debate_npc_actions
        WHERE id = $1
        "#,
    )
    .bind(action_id as i64)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(stored.action_type, "pause_suggestion");
    assert_eq!(
        stored.public_text.as_deref(),
        Some("我建议先短暂停一下，把争议焦点对齐后再继续。")
    );
    assert_eq!(stored.reason_code.as_deref(), Some("heated_exchange"));
    assert_eq!(stored.source_message_id, Some(message.id));
    assert_eq!(stored.target_message_id, None);
    assert_eq!(stored.executor_kind, "llm_executor_v1");

    let session_status: String =
        sqlx::query_scalar("SELECT status FROM debate_sessions WHERE id = $1")
            .bind(session_id)
            .fetch_one(&state.pool)
            .await?;
    assert_eq!(session_status, "open");
    assert_eq!(npc_action_count(&state).await?, 1);
    Ok(())
}

#[tokio::test]
async fn npc_action_candidate_should_reject_disabled_pause_suggestion_capability() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
    seed_npc_config_with_status(
        &state,
        session_id,
        SeedNpcConfig {
            enabled: true,
            status: "active",
            allow_speak: true,
            allow_praise: true,
            allow_effect: true,
            allow_state_change: true,
            allow_pause: false,
        },
    )
    .await?;
    let message =
        seed_joined_message(&state, session_id, 1, "pro", "这一段出现了互相打断。").await?;

    let output = state
        .submit_debate_npc_action_candidate(pause_suggestion_candidate(
            "npc-act-pause-disabled",
            session_id,
            message.id,
            "建议先暂停一下。",
            Some("interruption"),
        ))
        .await?;

    assert!(!output.accepted);
    assert_eq!(
        output.reason_code.as_deref(),
        Some("npc_capability_disabled")
    );
    assert_eq!(npc_action_count(&state).await?, 0);
    Ok(())
}

#[tokio::test]
async fn npc_action_candidate_should_require_reason_for_pause_suggestion() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
    seed_npc_config_with_status(
        &state,
        session_id,
        SeedNpcConfig {
            enabled: true,
            status: "active",
            allow_speak: true,
            allow_praise: true,
            allow_effect: true,
            allow_state_change: true,
            allow_pause: true,
        },
    )
    .await?;
    let message = seed_joined_message(&state, session_id, 1, "pro", "这一段需要整理。").await?;

    let err = state
        .submit_debate_npc_action_candidate(pause_suggestion_candidate(
            "npc-act-pause-reason-required",
            session_id,
            message.id,
            "建议先暂停一下。",
            None,
        ))
        .await
        .expect_err("pause_suggestion must explain why it is suggested");

    assert!(matches!(
        err,
        AppError::ValidationError(ref code) if code == "debate_npc_action_reason_required"
    ));
    assert_eq!(npc_action_count(&state).await?, 0);
    Ok(())
}

#[tokio::test]
async fn npc_action_candidate_should_reject_target_message_from_other_session() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
    let (_other_topic_id, other_session_id) = seed_topic_and_session(&state, "open", 10).await?;
    seed_npc_config(&state, session_id, true, true, true, true).await?;
    let other_message =
        seed_joined_message(&state, other_session_id, 1, "pro", "wrong room").await?;

    let output = state
        .submit_debate_npc_action_candidate(praise_candidate(
            "npc-act-wrong-target",
            session_id,
            other_message.id,
            "这句不错。",
        ))
        .await?;

    assert!(!output.accepted);
    assert_eq!(
        output.reason_code.as_deref(),
        Some("npc_target_message_mismatch")
    );
    assert_eq!(npc_action_count(&state).await?, 0);
    Ok(())
}

#[tokio::test]
async fn npc_action_candidate_should_rate_limit_room_actions() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
    seed_npc_config(&state, session_id, true, true, true, true).await?;

    let first = state
        .submit_debate_npc_action_candidate(speak_candidate(
            "npc-act-speak-001",
            session_id,
            "这轮讨论开始升温了。",
        ))
        .await?;
    assert!(first.accepted);

    let second = state
        .submit_debate_npc_action_candidate(speak_candidate(
            "npc-act-speak-002",
            session_id,
            "我先安静观察一下。",
        ))
        .await?;
    assert!(!second.accepted);
    assert_eq!(second.reason_code.as_deref(), Some("npc_rate_limited"));
    assert_eq!(npc_action_count(&state).await?, 1);
    Ok(())
}

#[tokio::test]
async fn npc_action_candidate_should_reject_pause_suggestion_official_verdict_fields() -> Result<()>
{
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
    let payload = json!({
        "actionUid": "npc-act-official-field",
        "sessionId": session_id as u64,
        "npcId": NPC_ID,
        "actionType": "pause_suggestion",
        "publicText": "我建议先短暂停一下，但不会改变正式赛况。",
        "reasonCode": "heated_exchange",
        "policyVersion": "npc-mvp-v1",
        "executorKind": "llm_executor_v1",
        "executorVersion": "gpt-4.1-mini",
        "winner": "pro"
    });

    let output = state.submit_debate_npc_action_candidate(payload).await?;

    assert!(!output.accepted);
    assert_eq!(
        output.reason_code.as_deref(),
        Some("npc_forbidden_official_field")
    );
    assert_eq!(npc_action_count(&state).await?, 0);
    Ok(())
}

#[tokio::test]
async fn npc_public_call_should_create_room_public_trigger_context() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
    seed_npc_config(&state, session_id, true, true, true, true).await?;
    enable_public_call(&state, session_id, true).await?;
    let _message = seed_joined_message(
        &state,
        session_id,
        1,
        "pro",
        "请注意一下对方刚才的定义切换。",
    )
    .await?;
    let user = state
        .find_user_by_id(1)
        .await?
        .expect("fixture user should exist");

    let call = state
        .create_debate_npc_public_call(
            &user,
            session_id as u64,
            CreateDebateNpcPublicCallInput {
                call_type: "issue_summary".to_string(),
                content: "帮忙概括一下目前争议焦点。".to_string(),
            },
        )
        .await?;

    assert_eq!(call.session_id, session_id);
    assert_eq!(call.user_id, user.id);
    assert_eq!(call.status, "queued");
    assert_eq!(call.call_type, "issue_summary");

    let context = state
        .get_debate_npc_decision_context(
            session_id as u64,
            GetDebateNpcDecisionContextQuery {
                trigger_message_id: None,
                public_call_id: Some(call.id as u64),
                source_event_id: Some("evt-call-1".to_string()),
                limit: Some(10),
            },
        )
        .await?;
    assert!(context.trigger_message.is_none());
    assert_eq!(
        context
            .public_call
            .as_ref()
            .expect("public call should exist")
            .content,
        "帮忙概括一下目前争议焦点。"
    );
    assert_eq!(context.recent_messages.len(), 1);
    Ok(())
}

#[tokio::test]
async fn npc_public_call_should_accept_pause_review_when_only_pause_capability_enabled(
) -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
    seed_npc_config_with_status(
        &state,
        session_id,
        SeedNpcConfig {
            enabled: true,
            status: "active",
            allow_speak: false,
            allow_praise: false,
            allow_effect: false,
            allow_state_change: false,
            allow_pause: true,
        },
    )
    .await?;
    enable_public_call(&state, session_id, true).await?;
    let _message =
        seed_joined_message(&state, session_id, 1, "pro", "我想让裁判看看要不要停一下。").await?;
    let user = state
        .find_user_by_id(1)
        .await?
        .expect("fixture user should exist");

    let call = state
        .create_debate_npc_public_call(
            &user,
            session_id as u64,
            CreateDebateNpcPublicCallInput {
                call_type: "pause_review".to_string(),
                content: "现在是否应该短暂停一下？".to_string(),
            },
        )
        .await?;

    assert_eq!(call.status, "queued");
    assert_eq!(call.call_type, "pause_review");
    Ok(())
}

#[tokio::test]
async fn npc_public_call_should_reject_when_room_gate_disabled() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
    seed_npc_config(&state, session_id, true, true, true, true).await?;
    let _message = seed_joined_message(&state, session_id, 1, "pro", "opening").await?;
    let user = state
        .find_user_by_id(1)
        .await?
        .expect("fixture user should exist");

    let err = state
        .create_debate_npc_public_call(
            &user,
            session_id as u64,
            CreateDebateNpcPublicCallInput {
                call_type: "rules_help".to_string(),
                content: "这个回合规则是什么？".to_string(),
            },
        )
        .await
        .expect_err("disabled public call gate should reject");

    assert!(matches!(
        err,
        AppError::DebateConflict(ref code) if code == "debate_npc_public_call_disabled"
    ));
    Ok(())
}

#[tokio::test]
async fn npc_action_history_and_feedback_should_expose_public_loop_only() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
    seed_npc_config(&state, session_id, true, true, true, true).await?;
    let _message = seed_joined_message(&state, session_id, 1, "pro", "opening").await?;
    let user = state
        .find_user_by_id(1)
        .await?
        .expect("fixture user should exist");

    let created = state
        .submit_debate_npc_action_candidate(speak_candidate(
            "npc-act-history-001",
            session_id,
            "我先把现场节奏拉回来：请双方继续围绕论点展开。",
        ))
        .await?;
    let action_id = created.action_id.expect("action should be created");

    let history = state
        .list_debate_npc_actions(
            &user,
            session_id as u64,
            ListDebateNpcActions {
                last_id: None,
                limit: Some(10),
            },
        )
        .await?;
    assert_eq!(history.items.len(), 1);
    assert_eq!(history.items[0].action_id, action_id as i64);
    assert_eq!(history.items[0].action_uid, "npc-act-history-001");
    assert_eq!(history.items[0].action_type, "speak");
    assert_eq!(
        history.items[0].public_text.as_deref(),
        Some("我先把现场节奏拉回来：请双方继续围绕论点展开。")
    );

    let first = state
        .submit_debate_npc_action_feedback(
            &user,
            session_id as u64,
            action_id,
            SubmitDebateNpcActionFeedbackInput {
                feedback_type: "helpful".to_string(),
                comment: Some("节奏提醒有帮助".to_string()),
            },
        )
        .await?;
    let second = state
        .submit_debate_npc_action_feedback(
            &user,
            session_id as u64,
            action_id,
            SubmitDebateNpcActionFeedbackInput {
                feedback_type: "confusing".to_string(),
                comment: None,
            },
        )
        .await?;

    assert_eq!(first.id, second.id);
    assert_eq!(second.feedback_type, "confusing");
    assert_eq!(second.comment, None);
    let count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM debate_npc_action_feedback")
        .fetch_one(&state.pool)
        .await?;
    assert_eq!(count, 1);
    Ok(())
}

async fn seed_npc_config(
    state: &AppState,
    session_id: i64,
    enabled: bool,
    allow_speak: bool,
    allow_praise: bool,
    allow_effect: bool,
) -> Result<()> {
    seed_npc_config_with_status(
        state,
        session_id,
        SeedNpcConfig {
            enabled,
            status: "active",
            allow_speak,
            allow_praise,
            allow_effect,
            allow_state_change: true,
            allow_pause: false,
        },
    )
    .await
}

async fn seed_npc_config_with_status(
    state: &AppState,
    session_id: i64,
    config: SeedNpcConfig,
) -> Result<()> {
    sqlx::query(
        r#"
        INSERT INTO debate_npc_room_configs(
          session_id, npc_id, display_name, enabled, status,
          allow_speak, allow_praise, allow_effect, allow_state_change, allow_pause
        )
        VALUES ($1, $2, '虚拟裁判', $3, $4, $5, $6, $7, $8, $9)
        "#,
    )
    .bind(session_id)
    .bind(NPC_ID)
    .bind(config.enabled)
    .bind(config.status)
    .bind(config.allow_speak)
    .bind(config.allow_praise)
    .bind(config.allow_effect)
    .bind(config.allow_state_change)
    .bind(config.allow_pause)
    .execute(&state.pool)
    .await?;
    Ok(())
}

async fn enable_public_call(state: &AppState, session_id: i64, allowed: bool) -> Result<()> {
    sqlx::query(
        r#"
        UPDATE debate_npc_room_configs
        SET allow_public_call = $2
        WHERE session_id = $1 AND npc_id = $3
        "#,
    )
    .bind(session_id)
    .bind(allowed)
    .bind(NPC_ID)
    .execute(&state.pool)
    .await?;
    Ok(())
}

async fn seed_joined_message(
    state: &AppState,
    session_id: i64,
    user_id: i64,
    side: &str,
    content: &str,
) -> Result<DebateMessage> {
    let user = state
        .find_user_by_id(user_id)
        .await?
        .expect("fixture user should exist");
    state
        .join_debate_session(
            session_id as u64,
            &user,
            JoinDebateSessionInput {
                side: side.to_string(),
            },
        )
        .await?;
    let message = state
        .create_debate_message(
            session_id as u64,
            &user,
            CreateDebateMessageInput {
                content: content.to_string(),
            },
        )
        .await?;
    Ok(message)
}

fn praise_candidate(action_uid: &str, session_id: i64, message_id: i64, text: &str) -> Value {
    json!({
        "actionUid": action_uid,
        "sessionId": session_id as u64,
        "npcId": NPC_ID,
        "actionType": "praise",
        "publicText": text,
        "targetMessageId": message_id as u64,
        "sourceMessageId": message_id as u64,
        "policyVersion": "npc-mvp-v1",
        "executorKind": "llm_executor_v1",
        "executorVersion": "gpt-4.1-mini"
    })
}

fn speak_candidate(action_uid: &str, session_id: i64, text: &str) -> Value {
    json!({
        "actionUid": action_uid,
        "sessionId": session_id as u64,
        "npcId": NPC_ID,
        "actionType": "speak",
        "publicText": text,
        "policyVersion": "npc-mvp-v1",
        "executorKind": "llm_executor_v1",
        "executorVersion": "gpt-4.1-mini"
    })
}

fn state_changed_candidate(action_uid: &str, session_id: i64, status: &str) -> Value {
    json!({
        "actionUid": action_uid,
        "sessionId": session_id as u64,
        "npcId": NPC_ID,
        "actionType": "state_changed",
        "publicText": "状态更新。",
        "npcStatus": status,
        "policyVersion": "npc-mvp-v1",
        "executorKind": "llm_executor_v1",
        "executorVersion": "gpt-4.1-mini"
    })
}

fn pause_suggestion_candidate(
    action_uid: &str,
    session_id: i64,
    source_message_id: i64,
    text: &str,
    reason_code: Option<&str>,
) -> Value {
    json!({
        "actionUid": action_uid,
        "sessionId": session_id as u64,
        "npcId": NPC_ID,
        "actionType": "pause_suggestion",
        "publicText": text,
        "sourceMessageId": source_message_id as u64,
        "reasonCode": reason_code,
        "policyVersion": "npc-mvp-v1",
        "executorKind": "llm_executor_v1",
        "executorVersion": "gpt-4.1-mini"
    })
}

async fn npc_action_count(state: &AppState) -> Result<i64> {
    let count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM debate_npc_actions")
        .fetch_one(&state.pool)
        .await?;
    Ok(count)
}
