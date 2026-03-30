use std::{collections::HashSet, sync::Arc, time::Duration};

use crate::AppState;
use chat_core::{Chat, Message};
use chrono::{DateTime, Utc};
use futures::StreamExt;
use serde::{Deserialize, Serialize};
use sqlx::postgres::PgListener;
use tokio::time::{Instant, MissedTickBehavior};
use tracing::{info, warn};

const PG_LISTENER_RECONNECT_BASE_MS: u64 = 1_000;
const PG_LISTENER_RECONNECT_MAX_MS: u64 = 30_000;
const PG_LISTENER_HEALTH_LOG_INTERVAL_SECS: u64 = 30;

const PG_LISTEN_CHANNELS: [&str; 9] = [
    "chat_updated",
    "chat_message_created",
    "debate_participant_joined",
    "debate_session_status_changed",
    "debate_message_created",
    "debate_message_pinned",
    "debate_judge_report_ready",
    "debate_draw_vote_resolved",
    "ops_observability_alert",
];

#[derive(Debug, Serialize, Deserialize)]
#[serde(tag = "event")]
pub enum AppEvent {
    NewChat(Chat),
    AddToChat(Chat),
    RemoveFromChat(Chat),
    NewMessage(Message),
    DebateParticipantJoined(DebateParticipantJoined),
    DebateSessionStatusChanged(DebateSessionStatusChanged),
    DebateMessageCreated(DebateMessageCreated),
    DebateMessagePinned(DebateMessagePinned),
    DebateJudgeReportReady(DebateJudgeReportReady),
    DebateDrawVoteResolved(DebateDrawVoteResolved),
    OpsObservabilityAlert(OpsObservabilityAlert),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DebateParticipantJoined {
    pub session_id: i64,
    pub user_id: i64,
    pub side: String,
    pub pro_count: i64,
    pub con_count: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DebateSessionStatusChanged {
    pub session_id: i64,
    pub from_status: String,
    pub to_status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DebateMessageCreated {
    pub message_id: i64,
    pub session_id: i64,
    pub user_id: i64,
    pub side: String,
    pub content: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DebateMessagePinned {
    pub pin_id: i64,
    pub session_id: i64,
    pub message_id: i64,
    pub user_id: i64,
    pub cost_coins: i64,
    pub pin_seconds: i32,
    pub expires_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DebateJudgeReportReady {
    pub report_id: i64,
    pub session_id: i64,
    pub job_id: i64,
    pub winner: String,
    pub pro_score: i32,
    pub con_score: i32,
    pub needs_draw_vote: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DebateDrawVoteResolved {
    pub vote_id: i64,
    pub session_id: i64,
    pub report_id: i64,
    pub status: String,
    pub resolution: String,
    pub decision_source: String,
    pub participated_voters: i32,
    pub agree_votes: i32,
    pub disagree_votes: i32,
    pub required_voters: i32,
    pub decided_at: Option<DateTime<Utc>>,
    pub rematch_session_id: Option<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OpsObservabilityAlert {
    pub scope_id: i64,
    pub alert_key: String,
    pub rule_type: String,
    pub severity: String,
    pub status: String,
    pub title: String,
    pub message: String,
    pub metrics: serde_json::Value,
}

#[derive(Debug)]
struct Notification {
    // users being impacted, so we should send the notification to them
    user_ids: HashSet<u64>,
    event: Arc<AppEvent>,
}

// pg_notify('chat_updated', json_build_object('op', TG_OP, 'old', OLD, 'new', NEW)::text);
#[derive(Debug, Serialize, Deserialize)]
struct ChatUpdated {
    op: String,
    old: Option<Chat>,
    new: Option<Chat>,
}

// pg_notify('chat_message_created', row_to_json(NEW)::text);
#[derive(Debug, Serialize, Deserialize)]
struct ChatMessageCreated {
    message: Message,
    members: Vec<i64>,
}

#[derive(Debug, Serialize, Deserialize)]
struct DebateParticipantJoinedPayload {
    session_id: i64,
    user_id: i64,
    side: String,
    pro_count: i64,
    con_count: i64,
    user_ids: Vec<i64>,
}

#[derive(Debug, Serialize, Deserialize)]
struct DebateSessionStatusChangedPayload {
    session_id: i64,
    from_status: String,
    to_status: String,
    user_ids: Vec<i64>,
}

#[derive(Debug, Serialize, Deserialize)]
struct DebateMessageCreatedPayload {
    message_id: i64,
    session_id: i64,
    user_id: i64,
    side: String,
    content: String,
    created_at: DateTime<Utc>,
    user_ids: Vec<i64>,
}

#[derive(Debug, Serialize, Deserialize)]
struct DebateMessagePinnedPayload {
    pin_id: i64,
    session_id: i64,
    message_id: i64,
    user_id: i64,
    cost_coins: i64,
    pin_seconds: i32,
    expires_at: DateTime<Utc>,
    user_ids: Vec<i64>,
}

#[derive(Debug, Serialize, Deserialize)]
struct DebateJudgeReportReadyPayload {
    report_id: i64,
    session_id: i64,
    job_id: i64,
    winner: String,
    pro_score: i32,
    con_score: i32,
    needs_draw_vote: bool,
    user_ids: Vec<i64>,
}

#[derive(Debug, Serialize, Deserialize)]
struct DebateDrawVoteResolvedPayload {
    vote_id: i64,
    session_id: i64,
    report_id: i64,
    status: String,
    resolution: String,
    #[serde(default)]
    decision_source: Option<String>,
    participated_voters: i32,
    agree_votes: i32,
    disagree_votes: i32,
    required_voters: i32,
    decided_at: Option<DateTime<Utc>>,
    rematch_session_id: Option<i64>,
    user_ids: Vec<i64>,
}

#[derive(Debug, Serialize, Deserialize)]
struct OpsObservabilityAlertPayload {
    #[serde(default)]
    scope_id: Option<i64>,
    alert_key: String,
    rule_type: String,
    severity: String,
    status: String,
    title: String,
    message: String,
    #[serde(default)]
    metrics: serde_json::Value,
    user_ids: Vec<i64>,
}

pub async fn setup_pg_listener(state: AppState) -> anyhow::Result<()> {
    let db_url = state.config.server.db_url.clone();
    tokio::spawn(async move {
        let mut reconnect_attempt: u32 = 0;
        loop {
            match connect_and_listen(&db_url).await {
                Ok(listener) => {
                    reconnect_attempt = 0;
                    info!(
                        "pg listener connected: channels={}",
                        PG_LISTEN_CHANNELS.join(",")
                    );
                    let mut stream = listener.into_stream();
                    let mut processed_events: u64 = 0;
                    let mut last_event_at = Instant::now();
                    let mut health_tick = tokio::time::interval(Duration::from_secs(
                        PG_LISTENER_HEALTH_LOG_INTERVAL_SECS,
                    ));
                    health_tick.set_missed_tick_behavior(MissedTickBehavior::Skip);
                    health_tick.tick().await;
                    loop {
                        tokio::select! {
                            maybe_notif = stream.next() => {
                                match maybe_notif {
                                    Some(Ok(notif)) => {
                                        last_event_at = Instant::now();
                                        processed_events = processed_events.saturating_add(1);
                                        if let Err(e) = dispatch_notification(&state, &notif).await {
                                            warn!(
                                                "pg listener drop invalid payload: channel={}, err={}",
                                                notif.channel(),
                                                e
                                            );
                                        }
                                    }
                                    Some(Err(e)) => {
                                        warn!("pg listener stream error (will reconnect): {}", e);
                                        break;
                                    }
                                    None => {
                                        warn!("pg listener stream ended (will reconnect)");
                                        break;
                                    }
                                }
                            }
                            _ = health_tick.tick() => {
                                let idle_ms = Instant::now()
                                    .saturating_duration_since(last_event_at)
                                    .as_millis();
                                info!(
                                    "pg listener healthy: processed_events={}, idle_ms={}",
                                    processed_events, idle_ms
                                );
                            }
                        }
                    }
                }
                Err(e) => {
                    reconnect_attempt = reconnect_attempt.saturating_add(1);
                    let delay = compute_pg_listener_reconnect_delay(reconnect_attempt);
                    warn!(
                        "pg listener connect failed (attempt={}): {}. retry in {}ms",
                        reconnect_attempt,
                        e,
                        delay.as_millis()
                    );
                    tokio::time::sleep(delay).await;
                    continue;
                }
            }
            reconnect_attempt = reconnect_attempt.saturating_add(1);
            let delay = compute_pg_listener_reconnect_delay(reconnect_attempt);
            warn!(
                "pg listener restarting after stream exit (attempt={}, backoff={}ms)",
                reconnect_attempt,
                delay.as_millis()
            );
            tokio::time::sleep(delay).await;
        }
    });

    Ok(())
}

async fn connect_and_listen(db_url: &str) -> anyhow::Result<PgListener> {
    let mut listener = PgListener::connect(db_url).await?;
    for channel in PG_LISTEN_CHANNELS {
        listener.listen(channel).await?;
    }
    Ok(listener)
}

async fn dispatch_notification(
    state: &AppState,
    notif: &sqlx::postgres::PgNotification,
) -> anyhow::Result<()> {
    let notification = Notification::load(notif.channel(), notif.payload())?;
    let replay_event = match state
        .persist_debate_event(notification.event.as_ref())
        .await
    {
        Ok(v) => v,
        Err(e) => {
            warn!(
                "persist debate replay event failed, fallback to memory-only replay: {}",
                e
            );
            None
        }
    };
    let users = &state.users;
    for user_id in notification.user_ids {
        let user_event = Arc::new(state.build_user_event_for_recipient(
            user_id,
            notification.event.clone(),
            replay_event.clone(),
        ));
        if let Some(tx) = users.get(&user_id) {
            if let Err(e) = tx.send(user_event) {
                warn!("failed to send notification to user {}: {}", user_id, e);
            }
        }
    }
    Ok(())
}

fn compute_pg_listener_reconnect_delay(attempt: u32) -> Duration {
    let power = attempt.saturating_sub(1).min(10);
    let exp = PG_LISTENER_RECONNECT_BASE_MS.saturating_mul(2_u64.saturating_pow(power));
    Duration::from_millis(exp.min(PG_LISTENER_RECONNECT_MAX_MS))
}

impl Notification {
    fn load(r#type: &str, payload: &str) -> anyhow::Result<Self> {
        match r#type {
            "chat_updated" => {
                let payload: ChatUpdated = serde_json::from_str(payload)?;
                info!("ChatUpdated: {:?}", payload);
                let user_ids =
                    get_affected_chat_user_ids(payload.old.as_ref(), payload.new.as_ref());
                let event = match payload.op.as_str() {
                    "INSERT" => AppEvent::NewChat(payload.new.expect("new should exist")),
                    "UPDATE" => AppEvent::AddToChat(payload.new.expect("new should exist")),
                    "DELETE" => AppEvent::RemoveFromChat(payload.old.expect("old should exist")),
                    _ => return Err(anyhow::anyhow!("Invalid operation")),
                };
                Ok(Self {
                    user_ids,
                    event: Arc::new(event),
                })
            }
            "chat_message_created" => {
                let payload: ChatMessageCreated = serde_json::from_str(payload)?;
                let user_ids = payload.members.iter().map(|v| *v as u64).collect();
                Ok(Self {
                    user_ids,
                    event: Arc::new(AppEvent::NewMessage(payload.message)),
                })
            }
            "debate_participant_joined" => {
                let payload: DebateParticipantJoinedPayload = serde_json::from_str(payload)?;
                let event = DebateParticipantJoined {
                    session_id: payload.session_id,
                    user_id: payload.user_id,
                    side: payload.side,
                    pro_count: payload.pro_count,
                    con_count: payload.con_count,
                };
                let user_ids = payload.user_ids.iter().map(|v| *v as u64).collect();
                Ok(Self {
                    user_ids,
                    event: Arc::new(AppEvent::DebateParticipantJoined(event)),
                })
            }
            "debate_session_status_changed" => {
                let payload: DebateSessionStatusChangedPayload = serde_json::from_str(payload)?;
                let event = DebateSessionStatusChanged {
                    session_id: payload.session_id,
                    from_status: payload.from_status,
                    to_status: payload.to_status,
                };
                let user_ids = payload.user_ids.iter().map(|v| *v as u64).collect();
                Ok(Self {
                    user_ids,
                    event: Arc::new(AppEvent::DebateSessionStatusChanged(event)),
                })
            }
            "debate_message_created" => {
                let payload: DebateMessageCreatedPayload = serde_json::from_str(payload)?;
                let event = DebateMessageCreated {
                    message_id: payload.message_id,
                    session_id: payload.session_id,
                    user_id: payload.user_id,
                    side: payload.side,
                    content: payload.content,
                    created_at: payload.created_at,
                };
                let user_ids = payload.user_ids.iter().map(|v| *v as u64).collect();
                Ok(Self {
                    user_ids,
                    event: Arc::new(AppEvent::DebateMessageCreated(event)),
                })
            }
            "debate_message_pinned" => {
                let payload: DebateMessagePinnedPayload = serde_json::from_str(payload)?;
                let event = DebateMessagePinned {
                    pin_id: payload.pin_id,
                    session_id: payload.session_id,
                    message_id: payload.message_id,
                    user_id: payload.user_id,
                    cost_coins: payload.cost_coins,
                    pin_seconds: payload.pin_seconds,
                    expires_at: payload.expires_at,
                };
                let user_ids = payload.user_ids.iter().map(|v| *v as u64).collect();
                Ok(Self {
                    user_ids,
                    event: Arc::new(AppEvent::DebateMessagePinned(event)),
                })
            }
            "debate_judge_report_ready" => {
                let payload: DebateJudgeReportReadyPayload = serde_json::from_str(payload)?;
                let event = DebateJudgeReportReady {
                    report_id: payload.report_id,
                    session_id: payload.session_id,
                    job_id: payload.job_id,
                    winner: payload.winner,
                    pro_score: payload.pro_score,
                    con_score: payload.con_score,
                    needs_draw_vote: payload.needs_draw_vote,
                };
                let user_ids = payload.user_ids.iter().map(|v| *v as u64).collect();
                Ok(Self {
                    user_ids,
                    event: Arc::new(AppEvent::DebateJudgeReportReady(event)),
                })
            }
            "debate_draw_vote_resolved" => {
                let payload: DebateDrawVoteResolvedPayload = serde_json::from_str(payload)?;
                let event = DebateDrawVoteResolved {
                    vote_id: payload.vote_id,
                    session_id: payload.session_id,
                    report_id: payload.report_id,
                    decision_source: normalize_draw_vote_decision_source(
                        payload.decision_source.as_deref(),
                        &payload.status,
                    ),
                    status: payload.status,
                    resolution: payload.resolution,
                    participated_voters: payload.participated_voters,
                    agree_votes: payload.agree_votes,
                    disagree_votes: payload.disagree_votes,
                    required_voters: payload.required_voters,
                    decided_at: payload.decided_at,
                    rematch_session_id: payload.rematch_session_id,
                };
                let user_ids = payload.user_ids.iter().map(|v| *v as u64).collect();
                Ok(Self {
                    user_ids,
                    event: Arc::new(AppEvent::DebateDrawVoteResolved(event)),
                })
            }
            "ops_observability_alert" => {
                let payload: OpsObservabilityAlertPayload = serde_json::from_str(payload)?;
                let event = OpsObservabilityAlert {
                    scope_id: payload.scope_id.unwrap_or(1),
                    alert_key: payload.alert_key,
                    rule_type: payload.rule_type,
                    severity: payload.severity,
                    status: payload.status,
                    title: payload.title,
                    message: payload.message,
                    metrics: payload.metrics,
                };
                let user_ids = payload.user_ids.iter().map(|v| *v as u64).collect();
                Ok(Self {
                    user_ids,
                    event: Arc::new(AppEvent::OpsObservabilityAlert(event)),
                })
            }
            _ => Err(anyhow::anyhow!("Invalid notification type")),
        }
    }
}

impl AppEvent {
    pub fn event_name(&self) -> &'static str {
        match self {
            AppEvent::NewChat(_) => "NewChat",
            AppEvent::AddToChat(_) => "AddToChat",
            AppEvent::RemoveFromChat(_) => "RemoveFromChat",
            AppEvent::NewMessage(_) => "NewMessage",
            AppEvent::DebateParticipantJoined(_) => "DebateParticipantJoined",
            AppEvent::DebateSessionStatusChanged(_) => "DebateSessionStatusChanged",
            AppEvent::DebateMessageCreated(_) => "DebateMessageCreated",
            AppEvent::DebateMessagePinned(_) => "DebateMessagePinned",
            AppEvent::DebateJudgeReportReady(_) => "DebateJudgeReportReady",
            AppEvent::DebateDrawVoteResolved(_) => "DebateDrawVoteResolved",
            AppEvent::OpsObservabilityAlert(_) => "OpsObservabilityAlert",
        }
    }

    pub fn debate_session_id(&self) -> Option<i64> {
        match self {
            AppEvent::DebateParticipantJoined(v) => Some(v.session_id),
            AppEvent::DebateSessionStatusChanged(v) => Some(v.session_id),
            AppEvent::DebateMessageCreated(v) => Some(v.session_id),
            AppEvent::DebateMessagePinned(v) => Some(v.session_id),
            AppEvent::DebateJudgeReportReady(v) => Some(v.session_id),
            AppEvent::DebateDrawVoteResolved(v) => Some(v.session_id),
            _ => None,
        }
    }

    pub fn debate_dedupe_key(&self) -> Option<String> {
        match self {
            AppEvent::DebateParticipantJoined(v) => Some(format!(
                "join:{}:{}:{}:{}:{}",
                v.session_id, v.user_id, v.side, v.pro_count, v.con_count
            )),
            AppEvent::DebateSessionStatusChanged(v) => Some(format!(
                "status:{}:{}:{}",
                v.session_id, v.from_status, v.to_status
            )),
            AppEvent::DebateMessageCreated(v) => Some(format!("message:{}", v.message_id)),
            AppEvent::DebateMessagePinned(v) => Some(format!("pin:{}", v.pin_id)),
            AppEvent::DebateJudgeReportReady(v) => Some(format!("report:{}", v.report_id)),
            AppEvent::DebateDrawVoteResolved(v) => Some(format!("vote:{}", v.vote_id)),
            _ => None,
        }
    }

    pub fn is_debate_event(&self) -> bool {
        matches!(
            self,
            AppEvent::DebateParticipantJoined(_)
                | AppEvent::DebateSessionStatusChanged(_)
                | AppEvent::DebateMessageCreated(_)
                | AppEvent::DebateMessagePinned(_)
                | AppEvent::DebateJudgeReportReady(_)
                | AppEvent::DebateDrawVoteResolved(_)
        )
    }
}

fn get_affected_chat_user_ids(old: Option<&Chat>, new: Option<&Chat>) -> HashSet<u64> {
    match (old, new) {
        (Some(old), Some(new)) => {
            // diff old/new members, if identical, no need to notify, otherwise notify the union of both
            let old_user_ids: HashSet<_> = old.members.iter().map(|v| *v as u64).collect();
            let new_user_ids: HashSet<_> = new.members.iter().map(|v| *v as u64).collect();
            if old_user_ids == new_user_ids {
                HashSet::new()
            } else {
                old_user_ids.union(&new_user_ids).copied().collect()
            }
        }
        (Some(old), None) => old.members.iter().map(|v| *v as u64).collect(),
        (None, Some(new)) => new.members.iter().map(|v| *v as u64).collect(),
        _ => HashSet::new(),
    }
}

fn normalize_draw_vote_decision_source(raw: Option<&str>, status: &str) -> String {
    let normalized = raw.unwrap_or_default().trim().to_ascii_lowercase();
    if matches!(
        normalized.as_str(),
        "threshold_reached" | "vote_timeout" | "pending"
    ) {
        return normalized;
    }
    match status.trim().to_ascii_lowercase().as_str() {
        "decided" => "threshold_reached".to_string(),
        "expired" => "vote_timeout".to_string(),
        _ => "pending".to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn notification_load_should_parse_debate_participant_joined() {
        let payload = r#"{
            "session_id": 11,
            "user_id": 7,
            "side": "pro",
            "pro_count": 3,
            "con_count": 2,
            "user_ids": [7, 8]
        }"#;
        let notif = Notification::load("debate_participant_joined", payload).unwrap();
        assert_eq!(notif.user_ids, HashSet::from([7_u64, 8_u64]));
        match notif.event.as_ref() {
            AppEvent::DebateParticipantJoined(v) => {
                assert_eq!(v.session_id, 11);
                assert_eq!(v.user_id, 7);
                assert_eq!(v.side, "pro");
                assert_eq!(v.pro_count, 3);
                assert_eq!(v.con_count, 2);
            }
            _ => panic!("expected DebateParticipantJoined event"),
        }
    }

    #[test]
    fn notification_load_should_parse_debate_session_status_changed() {
        let payload = r#"{
            "session_id": 15,
            "from_status": "running",
            "to_status": "judging",
            "user_ids": [7, 8, 9]
        }"#;
        let notif = Notification::load("debate_session_status_changed", payload).unwrap();
        assert_eq!(notif.user_ids, HashSet::from([7_u64, 8_u64, 9_u64]));
        match notif.event.as_ref() {
            AppEvent::DebateSessionStatusChanged(v) => {
                assert_eq!(v.session_id, 15);
                assert_eq!(v.from_status, "running");
                assert_eq!(v.to_status, "judging");
            }
            _ => panic!("expected DebateSessionStatusChanged event"),
        }
    }

    #[test]
    fn notification_load_should_parse_debate_message_created() {
        let payload = r#"{
            "message_id": 100,
            "session_id": 15,
            "user_id": 7,
            "side": "pro",
            "content": "hello",
            "created_at": "2026-02-23T12:00:00Z",
            "user_ids": [7, 8, 9]
        }"#;
        let notif = Notification::load("debate_message_created", payload).unwrap();
        assert_eq!(notif.user_ids, HashSet::from([7_u64, 8_u64, 9_u64]));
        match notif.event.as_ref() {
            AppEvent::DebateMessageCreated(v) => {
                assert_eq!(v.message_id, 100);
                assert_eq!(v.session_id, 15);
                assert_eq!(v.user_id, 7);
                assert_eq!(v.side, "pro");
            }
            _ => panic!("expected DebateMessageCreated event"),
        }
    }

    #[test]
    fn notification_load_should_parse_debate_message_pinned() {
        let payload = r#"{
            "pin_id": 21,
            "session_id": 15,
            "message_id": 100,
            "user_id": 7,
            "cost_coins": 20,
            "pin_seconds": 45,
            "expires_at": "2026-02-23T12:10:00Z",
            "user_ids": [7, 8, 9]
        }"#;
        let notif = Notification::load("debate_message_pinned", payload).unwrap();
        assert_eq!(notif.user_ids, HashSet::from([7_u64, 8_u64, 9_u64]));
        match notif.event.as_ref() {
            AppEvent::DebateMessagePinned(v) => {
                assert_eq!(v.pin_id, 21);
                assert_eq!(v.session_id, 15);
                assert_eq!(v.message_id, 100);
                assert_eq!(v.cost_coins, 20);
            }
            _ => panic!("expected DebateMessagePinned event"),
        }
    }

    #[test]
    fn notification_load_should_parse_debate_judge_report_ready() {
        let payload = r#"{
            "report_id": 31,
            "session_id": 15,
            "job_id": 77,
            "winner": "pro",
            "pro_score": 81,
            "con_score": 76,
            "needs_draw_vote": false,
            "user_ids": [7, 8, 9]
        }"#;
        let notif = Notification::load("debate_judge_report_ready", payload).unwrap();
        assert_eq!(notif.user_ids, HashSet::from([7_u64, 8_u64, 9_u64]));
        match notif.event.as_ref() {
            AppEvent::DebateJudgeReportReady(v) => {
                assert_eq!(v.report_id, 31);
                assert_eq!(v.session_id, 15);
                assert_eq!(v.job_id, 77);
                assert_eq!(v.winner, "pro");
                assert!(!v.needs_draw_vote);
            }
            _ => panic!("expected DebateJudgeReportReady event"),
        }
    }

    #[test]
    fn notification_load_should_parse_debate_draw_vote_resolved() {
        let payload = r#"{
            "vote_id": 41,
            "session_id": 15,
            "report_id": 31,
            "status": "decided",
            "resolution": "open_rematch",
            "decision_source": "threshold_reached",
            "participated_voters": 7,
            "agree_votes": 2,
            "disagree_votes": 5,
            "required_voters": 7,
            "decided_at": "2026-02-24T10:00:00Z",
            "rematch_session_id": 88,
            "user_ids": [7, 8, 9]
        }"#;
        let notif = Notification::load("debate_draw_vote_resolved", payload).unwrap();
        assert_eq!(notif.user_ids, HashSet::from([7_u64, 8_u64, 9_u64]));
        match notif.event.as_ref() {
            AppEvent::DebateDrawVoteResolved(v) => {
                assert_eq!(v.vote_id, 41);
                assert_eq!(v.session_id, 15);
                assert_eq!(v.report_id, 31);
                assert_eq!(v.status, "decided");
                assert_eq!(v.resolution, "open_rematch");
                assert_eq!(v.decision_source, "threshold_reached");
                assert_eq!(v.agree_votes, 2);
                assert_eq!(v.disagree_votes, 5);
                assert_eq!(v.required_voters, 7);
                assert_eq!(v.rematch_session_id, Some(88));
            }
            _ => panic!("expected DebateDrawVoteResolved event"),
        }
    }

    #[test]
    fn notification_load_should_default_decision_source_when_missing() {
        let payload = r#"{
            "vote_id": 42,
            "session_id": 15,
            "report_id": 31,
            "status": "expired",
            "resolution": "open_rematch",
            "participated_voters": 0,
            "agree_votes": 0,
            "disagree_votes": 0,
            "required_voters": 7,
            "decided_at": "2026-02-24T10:00:00Z",
            "rematch_session_id": 89,
            "user_ids": [7, 8, 9]
        }"#;
        let notif = Notification::load("debate_draw_vote_resolved", payload).unwrap();
        assert_eq!(notif.user_ids, HashSet::from([7_u64, 8_u64, 9_u64]));
        match notif.event.as_ref() {
            AppEvent::DebateDrawVoteResolved(v) => {
                assert_eq!(v.vote_id, 42);
                assert_eq!(v.status, "expired");
                assert_eq!(v.decision_source, "vote_timeout");
            }
            _ => panic!("expected DebateDrawVoteResolved event"),
        }
    }

    #[test]
    fn notification_load_should_parse_ops_observability_alert() {
        let payload = r#"{
            "scope_id": 1,
            "alert_key": "high_retry",
            "rule_type": "high_retry",
            "severity": "warning",
            "status": "raised",
            "title": "判决分发重试偏高",
            "message": "avg attempts too high",
            "metrics": {"avgDispatchAttempts": 2.2},
            "user_ids": [1, 2, 3]
        }"#;
        let notif = Notification::load("ops_observability_alert", payload).unwrap();
        assert_eq!(notif.user_ids, HashSet::from([1_u64, 2_u64, 3_u64]));
        match notif.event.as_ref() {
            AppEvent::OpsObservabilityAlert(v) => {
                assert_eq!(v.scope_id, 1);
                assert_eq!(v.alert_key, "high_retry");
                assert_eq!(v.status, "raised");
                assert_eq!(v.metrics["avgDispatchAttempts"], 2.2);
            }
            _ => panic!("expected OpsObservabilityAlert event"),
        }
    }

    #[test]
    fn notification_load_should_ignore_unknown_scope_field_for_ops_observability_alert() {
        let payload = r#"{
            "legacyScopeId": 99,
            "alert_key": "high_retry",
            "rule_type": "high_retry",
            "severity": "warning",
            "status": "raised",
            "title": "legacy scope id",
            "message": "legacy field should be ignored",
            "metrics": {"avgDispatchAttempts": 2.2},
            "user_ids": [1]
        }"#;
        let notif = Notification::load("ops_observability_alert", payload).unwrap();
        assert_eq!(notif.user_ids, HashSet::from([1_u64]));
        match notif.event.as_ref() {
            AppEvent::OpsObservabilityAlert(v) => {
                assert_eq!(
                    v.scope_id, 1,
                    "unknown scope field should not drive scope_id"
                );
                assert_eq!(v.alert_key, "high_retry");
            }
            _ => panic!("expected OpsObservabilityAlert event"),
        }
    }

    #[test]
    fn app_event_is_debate_event_should_match_debate_variants() {
        let debate_event = AppEvent::DebateMessagePinned(DebateMessagePinned {
            pin_id: 1,
            session_id: 11,
            message_id: 22,
            user_id: 3,
            cost_coins: 30,
            pin_seconds: 60,
            expires_at: chrono::DateTime::parse_from_rfc3339("2026-02-23T12:10:00Z")
                .expect("valid timestamp")
                .with_timezone(&Utc),
        });
        assert!(debate_event.is_debate_event());

        let non_debate_event = AppEvent::OpsObservabilityAlert(OpsObservabilityAlert {
            scope_id: 1,
            alert_key: "high_retry".to_string(),
            rule_type: "high_retry".to_string(),
            severity: "warning".to_string(),
            status: "raised".to_string(),
            title: "title".to_string(),
            message: "message".to_string(),
            metrics: serde_json::json!({}),
        });
        assert!(!non_debate_event.is_debate_event());
    }

    #[test]
    fn compute_pg_listener_reconnect_delay_should_backoff_and_cap() {
        assert_eq!(
            compute_pg_listener_reconnect_delay(1),
            Duration::from_millis(1_000)
        );
        assert_eq!(
            compute_pg_listener_reconnect_delay(2),
            Duration::from_millis(2_000)
        );
        assert_eq!(
            compute_pg_listener_reconnect_delay(3),
            Duration::from_millis(4_000)
        );
        assert_eq!(
            compute_pg_listener_reconnect_delay(10),
            Duration::from_millis(30_000)
        );
        assert_eq!(
            compute_pg_listener_reconnect_delay(99),
            Duration::from_millis(30_000)
        );
    }
}
