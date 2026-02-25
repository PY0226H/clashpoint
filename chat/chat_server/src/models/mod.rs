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
    CreateDebateMessageInput, DebateMessage, DebatePinnedMessage, DebateSessionSummary,
    DebateTopic, JoinDebateSessionInput, JoinDebateSessionOutput, ListDebateMessages,
    ListDebatePinnedMessages, ListDebateSessions, ListDebateTopics, OpsCreateDebateSessionInput,
    OpsCreateDebateTopicInput, OpsUpdateDebateSessionInput, OpsUpdateDebateTopicInput,
    PinDebateMessageInput, PinDebateMessageOutput,
};
pub use judge::{
    DrawVoteDetail, GetDrawVoteOutput, GetJudgeReportOutput, GetJudgeReportQuery, JudgeJobSnapshot,
    JudgeRagMeta, JudgeRagSourceItem, JudgeReportDetail, JudgeStageSummariesMeta,
    JudgeStageSummaryDetail, JudgeStageSummaryInput, MarkJudgeJobFailedInput,
    MarkJudgeJobFailedOutput, RequestJudgeJobInput, RequestJudgeJobOutput, SubmitDrawVoteInput,
    SubmitDrawVoteOutput, SubmitJudgeReportInput, SubmitJudgeReportOutput,
};
pub(crate) use judge_dispatch::AiJudgeDispatchMetrics;
pub use judge_dispatch::GetJudgeDispatchMetricsOutput;
pub use messages::{CreateMessage, ListMessages};
pub use payment::{
    GetIapOrderByTransaction, GetIapOrderByTransactionOutput, IapOrderSnapshot, IapProduct,
    ListIapProducts, ListWalletLedger, VerifyIapOrderInput, VerifyIapOrderOutput,
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
