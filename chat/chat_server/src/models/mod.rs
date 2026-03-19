mod agent;
mod chat;
mod debate;
mod file;
mod judge;
mod judge_dispatch;
mod kafka_dlq;
mod messages;
mod ops_observability;
mod payment;
mod rbac;
mod user;

pub use agent::{CreateAgent, UpdateAgent};
pub use chat::{CreateChat, UpdateChat, UpdateChatMembers};
pub use debate::{
    CreateDebateMessageInput, DebateMessage, DebatePinnedMessage, DebateSessionSummary,
    DebateTopic, JoinDebateSessionInput, JoinDebateSessionOutput, ListDebateMessages,
    ListDebatePinnedMessages, ListDebateSessions, ListDebateTopics, OpsCreateDebateSessionInput,
    OpsCreateDebateTopicInput, OpsUpdateDebateSessionInput, OpsUpdateDebateTopicInput,
    PinDebateMessageInput, PinDebateMessageOutput,
};
pub use judge::{
    DrawVoteDetail, ExecuteJudgeReplayOpsInput, ExecuteJudgeReplayOpsOutput, GetDrawVoteOutput,
    GetJudgeFinalDispatchFailureStatsOutput, GetJudgeFinalDispatchFailureStatsQuery,
    GetJudgeReplayPreviewOpsOutput, GetJudgeReplayPreviewOpsQuery, GetJudgeReportOutput,
    GetJudgeReportQuery, JudgeFinalDispatchFailureTypeCount, JudgeGroundedSummaryPayload,
    JudgeJobSnapshot, JudgePhaseAgent1ScorePayload, JudgePhaseAgent2ScorePayload,
    JudgePhaseAgent3WeightedScorePayload, JudgeRagMeta, JudgeRagSourceItem,
    JudgeReplayActionOpsItem, JudgeReplayPreviewMeta, JudgeReportDetail,
    JudgeRetrievalBundleItemPayload, JudgeRetrievalBundlePayload, JudgeReviewOpsItem,
    JudgeStageSummariesMeta, JudgeStageSummaryDetail, JudgeStageSummaryInput,
    JudgeTraceReplayOpsItem, ListJudgeReplayActionsOpsOutput, ListJudgeReplayActionsOpsQuery,
    ListJudgeReviewOpsOutput, ListJudgeReviewOpsQuery, ListJudgeTraceReplayOpsOutput,
    ListJudgeTraceReplayOpsQuery, MarkJudgeJobFailedInput, MarkJudgeJobFailedOutput,
    RequestJudgeJobInput, RequestJudgeJobOutput, SubmitDrawVoteInput, SubmitDrawVoteOutput,
    SubmitJudgeFinalReportInput, SubmitJudgeFinalReportOutput, SubmitJudgePhaseReportInput,
    SubmitJudgePhaseReportOutput, SubmitJudgeReportInput, SubmitJudgeReportOutput,
};
pub(crate) use judge_dispatch::AiJudgeDispatchMetrics;
pub use judge_dispatch::GetJudgeDispatchMetricsOutput;
pub(crate) use judge_dispatch::JudgeDispatchTrigger;
pub use kafka_dlq::{
    KafkaDlqActionOutput, KafkaDlqEventItem, ListKafkaDlqEventsOutput, ListKafkaDlqEventsQuery,
};
pub use messages::{CreateMessage, ListMessages};
pub use ops_observability::{
    ApplyOpsObservabilityAnomalyActionInput, GetOpsMetricsDictionaryOutput,
    GetOpsObservabilityConfigOutput, GetOpsServiceSplitReadinessOutput, GetOpsSloSnapshotOutput,
    ListOpsAlertNotificationsOutput, ListOpsAlertNotificationsQuery,
    ListOpsServiceSplitReviewAuditsOutput, ListOpsServiceSplitReviewAuditsQuery,
    OpsAlertEvalReport, OpsAlertNotificationItem, OpsMetricsDictionaryItem,
    OpsObservabilityAnomalyStateValue, OpsObservabilityThresholds, OpsServiceSplitReviewAuditItem,
    OpsServiceSplitThresholdItem, OpsSloRuleSnapshotItem, OpsSloSignalSnapshot,
    RunOpsObservabilityEvaluationQuery, UpdateOpsObservabilityAnomalyStateInput,
    UpsertOpsServiceSplitReviewInput,
};
pub use payment::{
    GetIapOrderByTransaction, GetIapOrderByTransactionOutput, IapOrderSnapshot, IapProduct,
    ListIapProducts, ListWalletLedger, VerifyIapOrderInput, VerifyIapOrderOutput,
    WalletBalanceOutput, WalletLedgerItem,
};
pub(crate) use rbac::OpsPermission;
pub use rbac::{
    GetOpsRbacMeOutput, ListOpsRoleAssignmentsOutput, OpsPermissionFlags, OpsRoleAssignment,
    RevokeOpsRoleOutput, UpsertOpsRoleInput,
};
use serde::{Deserialize, Serialize};
pub use user::{CreateUser, CreateUserWithPhoneInput, SigninUser};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatFile {
    pub ext: String, // extract ext from filename or mime type
    pub hash: String,
}
