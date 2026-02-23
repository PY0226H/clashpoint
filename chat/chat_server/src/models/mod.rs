mod agent;
mod chat;
mod debate;
mod file;
mod messages;
mod user;
mod workspace;

pub use agent::{CreateAgent, UpdateAgent};
pub use chat::CreateChat;
pub use debate::{
    DebateSessionSummary, DebateTopic, JoinDebateSessionInput, JoinDebateSessionOutput,
    ListDebateSessions, ListDebateTopics,
};
pub use messages::{CreateMessage, ListMessages};
use serde::{Deserialize, Serialize};
pub use user::{CreateUser, SigninUser};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatFile {
    pub ws_id: u64,
    pub ext: String, // extract ext from filename or mime type
    pub hash: String,
}
