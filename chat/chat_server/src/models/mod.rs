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
    ListDebateMessagesOutput, ListDebatePinnedMessages, ListDebatePinnedMessagesOutput,
    ListDebateSessions, ListDebateSessionsOutput, ListDebateTopics, ListDebateTopicsOutput,
    OpsCreateDebateSessionInput, OpsCreateDebateTopicInput, OpsUpdateDebateSessionInput,
    OpsUpdateDebateTopicInput, PinDebateMessageInput, PinDebateMessageOutput,
};
pub use judge::{
    DrawVoteDetail, ExecuteJudgeReplayOpsInput, ExecuteJudgeReplayOpsOutput, GetDrawVoteOutput,
    GetJudgeFinalDispatchFailureStatsOutput, GetJudgeFinalDispatchFailureStatsQuery,
    GetJudgeReplayPreviewOpsOutput, GetJudgeReplayPreviewOpsQuery, GetJudgeReportFinalOutput,
    GetJudgeReportOutput, JudgeFinalDispatchFailureTypeCount, JudgeFinalJobSnapshot,
    JudgeFinalReportSummary, JudgeGroundedSummaryPayload, JudgePhaseAgent1ScorePayload,
    JudgePhaseAgent2ScorePayload, JudgePhaseAgent3WeightedScorePayload, JudgePhaseJobSnapshot,
    JudgeRagMeta, JudgeRagSourceItem, JudgeReplayActionOpsItem, JudgeReplayPreviewMeta,
    JudgeReportDetail, JudgeReportProgress, JudgeRetrievalBundleItemPayload,
    JudgeRetrievalBundlePayload, JudgeReviewOpsItem, JudgeStageSummariesMeta,
    JudgeStageSummaryDetail, JudgeStageSummaryInput, JudgeTraceReplayOpsItem,
    ListJudgeReplayActionsOpsOutput, ListJudgeReplayActionsOpsQuery, ListJudgeReviewOpsOutput,
    ListJudgeReviewOpsQuery, ListJudgeTraceReplayOpsOutput, ListJudgeTraceReplayOpsQuery,
    RequestJudgeJobInput, RequestJudgeJobOutput, SubmitDrawVoteInput, SubmitDrawVoteOutput,
    SubmitJudgeFinalReportInput, SubmitJudgeFinalReportOutput, SubmitJudgePhaseReportInput,
    SubmitJudgePhaseReportOutput,
};
pub(crate) use judge_dispatch::AiJudgeDispatchMetrics;
pub use judge_dispatch::GetJudgeDispatchMetricsOutput;
pub(crate) use judge_dispatch::JudgeDispatchTrigger;
pub use kafka_dlq::{
    GetKafkaTransportReadinessOutput, KafkaConsumerRuntimeMetricsSnapshotOutput,
    KafkaDlqActionOutput, KafkaDlqEventItem, KafkaOutboxRelayMetricsSnapshotOutput,
    ListKafkaDlqEventsOutput, ListKafkaDlqEventsQuery,
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
    GetIapOrderByTransaction, GetIapOrderByTransactionOutput, IapOrderProbeStatus,
    IapOrderSnapshot, IapProduct, IapProductsEmptyReason, ListIapProducts, ListIapProductsOutput,
    ListWalletLedger, VerifyIapErrorOutput, VerifyIapOrderInput, VerifyIapOrderOutput,
    WalletBalanceOutput, WalletLedgerItem, WalletLedgerListOutput,
};
pub use rbac::{
    GetOpsRbacMeOutput, ListOpsRoleAssignmentsOutput, ListOpsRoleAssignmentsQuery,
    OpsPermissionFlags, OpsRbacPiiLevel, OpsRbacRevokeMeta, OpsRbacUpsertMeta, OpsRoleAssignment,
    RevokeOpsRoleOutput, UpsertOpsRoleInput,
};
pub(crate) use rbac::{OpsPermission, OPS_RBAC_PERMISSION_DENIED_ROLE_MANAGE_CODE};
use serde::{Deserialize, Serialize};
pub use user::{
    CreateUser, CreateUserWithPhoneAndSessionInput, CreateUserWithPhoneInput, SigninUser,
};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatFile {
    pub ext: String, // extract ext from filename or mime type
    pub hash: String,
}
