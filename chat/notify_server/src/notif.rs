use std::{collections::HashSet, sync::Arc};

use crate::AppState;
use chat_core::{Chat, Message};
use futures::StreamExt;
use serde::{Deserialize, Serialize};
use sqlx::postgres::PgListener;
use tracing::{info, warn};

#[derive(Debug, Serialize, Deserialize)]
#[serde(tag = "event")]
pub enum AppEvent {
    NewChat(Chat),
    AddToChat(Chat),
    RemoveFromChat(Chat),
    NewMessage(Message),
    DebateParticipantJoined(DebateParticipantJoined),
    DebateSessionStatusChanged(DebateSessionStatusChanged),
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

pub async fn setup_pg_listener(state: AppState) -> anyhow::Result<()> {
    let mut listener = PgListener::connect(&state.config.server.db_url).await?;
    listener.listen("chat_updated").await?;
    listener.listen("chat_message_created").await?;
    listener.listen("debate_participant_joined").await?;
    listener.listen("debate_session_status_changed").await?;

    let mut stream = listener.into_stream();

    tokio::spawn(async move {
        while let Some(Ok(notif)) = stream.next().await {
            info!("Received notification: {:?}", notif);
            let notification = Notification::load(notif.channel(), notif.payload())?;
            let users = &state.users;
            for user_id in notification.user_ids {
                if let Some(tx) = users.get(&user_id) {
                    info!("Sending notification to user {}", user_id);
                    if let Err(e) = tx.send(notification.event.clone()) {
                        warn!("Failed to send notification to user {}: {}", user_id, e);
                    }
                }
            }
        }
        Ok::<_, anyhow::Error>(())
    });

    Ok(())
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
        }
    }

    pub fn debate_session_id(&self) -> Option<i64> {
        match self {
            AppEvent::DebateParticipantJoined(v) => Some(v.session_id),
            AppEvent::DebateSessionStatusChanged(v) => Some(v.session_id),
            _ => None,
        }
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
}
