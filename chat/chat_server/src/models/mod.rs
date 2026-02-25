mod agent;
mod chat;
mod debate;
mod file;
mod judge;
mod judge_dispatch;
mod messages;
mod payment;
mod user;
mod workspace;

pub use agent::{CreateAgent, UpdateAgent};
pub use chat::CreateChat;
pub use debate::{
    CreateDebateMessageInput, DebateMessage, DebateSessionSummary, DebateTopic,
    JoinDebateSessionInput, JoinDebateSessionOutput, ListDebateSessions, ListDebateTopics,
    PinDebateMessageInput, PinDebateMessageOutput,
};
pub use judge::{
    DrawVoteDetail, GetDrawVoteOutput, GetJudgeReportOutput, JudgeJobSnapshot, JudgeRagMeta,
    JudgeRagSourceItem, JudgeReportDetail, JudgeStageSummaryDetail, JudgeStageSummaryInput,
    MarkJudgeJobFailedInput, MarkJudgeJobFailedOutput, RequestJudgeJobInput, RequestJudgeJobOutput,
    SubmitDrawVoteInput, SubmitDrawVoteOutput, SubmitJudgeReportInput, SubmitJudgeReportOutput,
};
pub(crate) use judge_dispatch::AiJudgeDispatchMetrics;
pub use judge_dispatch::GetJudgeDispatchMetricsOutput;
pub use messages::{CreateMessage, ListMessages};
pub use payment::{
    IapProduct, ListIapProducts, ListWalletLedger, VerifyIapOrderInput, VerifyIapOrderOutput,
    WalletBalanceOutput, WalletLedgerItem,
};
use serde::{Deserialize, Serialize};
pub use user::{CreateUser, SigninUser};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatFile {
    pub ws_id: u64,
    pub ext: String, // extract ext from filename or mime type
    pub hash: String,
}
