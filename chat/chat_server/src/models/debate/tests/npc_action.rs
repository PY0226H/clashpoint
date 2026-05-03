use super::*;
use serde_json::{json, Value};

const NPC_ID: &str = "virtual_judge_default";

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
async fn npc_action_candidate_should_reject_official_verdict_fields() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let (_topic_id, session_id) = seed_topic_and_session(&state, "open", 10).await?;
    let payload = json!({
        "actionUid": "npc-act-official-field",
        "sessionId": session_id as u64,
        "npcId": NPC_ID,
        "actionType": "speak",
        "publicText": "我只负责活跃气氛，不生成正式裁决。",
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

async fn seed_npc_config(
    state: &AppState,
    session_id: i64,
    enabled: bool,
    allow_speak: bool,
    allow_praise: bool,
    allow_effect: bool,
) -> Result<()> {
    sqlx::query(
        r#"
        INSERT INTO debate_npc_room_configs(
          session_id, npc_id, display_name, enabled, allow_speak, allow_praise, allow_effect
        )
        VALUES ($1, $2, '虚拟裁判', $3, $4, $5, $6)
        "#,
    )
    .bind(session_id)
    .bind(NPC_ID)
    .bind(enabled)
    .bind(allow_speak)
    .bind(allow_praise)
    .bind(allow_effect)
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

async fn npc_action_count(state: &AppState) -> Result<i64> {
    let count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM debate_npc_actions")
        .fetch_one(&state.pool)
        .await?;
    Ok(count)
}
