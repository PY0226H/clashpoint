use crate::handlers::*;
use crate::{
    AppState, ApplyOpsObservabilityAnomalyActionInput, AuthSessionItem, BindPhoneV2Input,
    BindPhoneV2Output, CreateChat, CreateDebateMessageInput, CreateMessage, CreateUser,
    DebateMessage, DebatePinnedMessage, DebateSessionSummary, DebateTopic, DrawVoteDetail,
    ErrorOutput, ExecuteJudgeReplayOpsInput, ExecuteJudgeReplayOpsOutput, GetDrawVoteOutput,
    GetIapOrderByTransaction, GetIapOrderByTransactionOutput, GetJudgeDispatchMetricsOutput,
    GetJudgeFinalDispatchFailureStatsOutput, GetJudgeFinalDispatchFailureStatsQuery,
    GetJudgeReplayPreviewOpsOutput, GetJudgeReplayPreviewOpsQuery, GetJudgeReportOutput,
    GetJudgeReportQuery, GetOpsMetricsDictionaryOutput, GetOpsObservabilityConfigOutput,
    GetOpsRbacMeOutput, GetOpsServiceSplitReadinessOutput, GetOpsSloSnapshotOutput,
    IapOrderSnapshot, IapProduct, JoinDebateSessionInput, JoinDebateSessionOutput,
    JudgeFinalDispatchFailureTypeCount, JudgeGroundedSummaryPayload, JudgeJobSnapshot,
    JudgePhaseAgent1ScorePayload, JudgePhaseAgent2ScorePayload,
    JudgePhaseAgent3WeightedScorePayload, JudgeRagMeta, JudgeRagSourceItem,
    JudgeReplayActionOpsItem, JudgeReplayPreviewMeta, JudgeReportDetail,
    JudgeRetrievalBundleItemPayload, JudgeRetrievalBundlePayload, JudgeReviewOpsItem,
    JudgeStageSummariesMeta, JudgeStageSummaryDetail, JudgeStageSummaryInput,
    JudgeTraceReplayOpsItem, KafkaDlqActionOutput, KafkaDlqEventItem, ListAuthSessionsOutput,
    ListDebateMessages, ListDebatePinnedMessages, ListDebateSessions, ListDebateTopics,
    ListIapProducts, ListJudgeReplayActionsOpsOutput, ListJudgeReplayActionsOpsQuery,
    ListJudgeReviewOpsOutput, ListJudgeReviewOpsQuery, ListJudgeTraceReplayOpsOutput,
    ListJudgeTraceReplayOpsQuery, ListKafkaDlqEventsOutput, ListKafkaDlqEventsQuery, ListMessages,
    ListOpsAlertNotificationsOutput, ListOpsAlertNotificationsQuery, ListOpsRoleAssignmentsOutput,
    ListOpsServiceSplitReviewAuditsOutput, ListOpsServiceSplitReviewAuditsQuery, ListWalletLedger,
    LogoutAllOutput, LogoutOutput, MarkJudgeJobFailedInput, MarkJudgeJobFailedOutput,
    OpsAlertEvalReport, OpsAlertNotificationItem, OpsCreateDebateSessionInput,
    OpsCreateDebateTopicInput, OpsMetricsDictionaryItem, OpsObservabilityAnomalyStateValue,
    OpsObservabilityThresholds, OpsPermissionFlags, OpsRoleAssignment,
    OpsServiceSplitReviewAuditItem, OpsServiceSplitThresholdItem, OpsSloRuleSnapshotItem,
    OpsSloSignalSnapshot, OpsUpdateDebateSessionInput, OpsUpdateDebateTopicInput,
    PinDebateMessageInput, PinDebateMessageOutput, RedisHealthOutput, RefreshOutput,
    RequestJudgeJobInput, RequestJudgeJobOutput, RevokeOpsRoleOutput,
    RunOpsObservabilityEvaluationQuery, SendSmsCodeV2Input, SendSmsCodeV2Output, SigninOtpV2Input,
    SigninPasswordV2Input, SigninUser, SignupEmailV2Input, SignupPhoneV2Input, SubmitDrawVoteInput,
    SubmitDrawVoteOutput, SubmitJudgeFinalReportInput, SubmitJudgeFinalReportOutput,
    SubmitJudgePhaseReportInput, SubmitJudgePhaseReportOutput, SubmitJudgeReportInput,
    SubmitJudgeReportOutput, UpdateChat, UpdateChatMembers,
    UpdateOpsObservabilityAnomalyStateInput, UpsertOpsRoleInput, UpsertOpsServiceSplitReviewInput,
    VerifyIapOrderInput, VerifyIapOrderOutput, WalletBalanceOutput, WalletLedgerItem,
    WechatBindPhoneV2Input, WechatChallengeV2Output, WechatSigninV2Input, WechatSigninV2Output,
};
use axum::Router;
use chat_core::{AgentType, Chat, ChatAgent, ChatType, ChatUser, Message, User};
use utoipa::{
    openapi::security::{HttpAuthScheme, HttpBuilder, SecurityScheme},
    Modify, OpenApi,
};
use utoipa_rapidoc::RapiDoc;
use utoipa_redoc::{Redoc, Servable};
use utoipa_swagger_ui::SwaggerUi;

pub(crate) trait OpenApiRouter {
    fn openapi(self) -> Self;
}

#[derive(OpenApi)]
#[openapi(
        paths(
            signup_handler,
            signin_handler,
            send_sms_code_v2_handler,
            signup_phone_v2_handler,
            signup_email_v2_handler,
            signin_password_v2_handler,
            signin_otp_v2_handler,
            wechat_challenge_v2_handler,
            wechat_signin_v2_handler,
            wechat_bind_phone_v2_handler,
            bind_phone_v2_handler,
            refresh_handler,
            logout_handler,
            logout_all_handler,
            list_auth_sessions_handler,
            revoke_auth_session_handler,
            create_access_tickets_handler,
            list_debate_topics_handler,
            get_analytics_judge_refresh_summary_handler,
            get_analytics_judge_refresh_summary_metrics_handler,
            crate::handlers::debate_ops::create_debate_topic_ops_handler,
            crate::handlers::debate_ops::update_debate_topic_ops_handler,
            crate::handlers::debate_ops::create_debate_session_ops_handler,
            crate::handlers::debate_ops::update_debate_session_ops_handler,
            crate::handlers::debate_ops::get_ops_rbac_me_handler,
            crate::handlers::debate_ops::get_ops_observability_config_handler,
            crate::handlers::debate_ops::get_ops_observability_metrics_dictionary_handler,
            crate::handlers::debate_ops::get_ops_observability_slo_snapshot_handler,
            crate::handlers::debate_ops::get_ops_service_split_readiness_handler,
            crate::handlers::debate_ops::list_ops_service_split_review_audits_handler,
            crate::handlers::debate_ops::upsert_ops_service_split_review_handler,
            crate::handlers::debate_ops::upsert_ops_observability_thresholds_handler,
            crate::handlers::debate_ops::upsert_ops_observability_anomaly_state_handler,
            crate::handlers::debate_ops::apply_ops_observability_anomaly_action_handler,
            crate::handlers::debate_ops::run_ops_observability_evaluation_once_handler,
            crate::handlers::debate_ops::list_ops_alert_notifications_handler,
            crate::handlers::debate_ops::list_kafka_dlq_events_handler,
            crate::handlers::debate_ops::replay_kafka_dlq_event_handler,
            crate::handlers::debate_ops::discard_kafka_dlq_event_handler,
            crate::handlers::debate_ops::list_ops_role_assignments_handler,
            crate::handlers::debate_ops::upsert_ops_role_assignment_handler,
            crate::handlers::debate_ops::revoke_ops_role_assignment_handler,
            crate::handlers::debate_ops::list_judge_reviews_ops_handler,
            crate::handlers::debate_ops::list_judge_final_dispatch_failure_stats_ops_handler,
            crate::handlers::debate_ops::list_judge_trace_replay_ops_handler,
            crate::handlers::debate_ops::get_judge_replay_preview_ops_handler,
            crate::handlers::debate_ops::execute_judge_replay_ops_handler,
            crate::handlers::debate_ops::list_judge_replay_actions_ops_handler,
            crate::handlers::debate_ops::request_judge_rejudge_ops_handler,
            crate::handlers::debate_room::list_debate_sessions_handler,
            crate::handlers::debate_room::join_debate_session_handler,
            crate::handlers::debate_room::list_debate_messages_handler,
            crate::handlers::debate_room::create_debate_message_handler,
            crate::handlers::debate_room::list_debate_pinned_messages_handler,
            crate::handlers::debate_room::pin_debate_message_handler,
            crate::handlers::debate_judge::request_judge_job_handler,
            crate::handlers::debate_judge::get_latest_judge_report_handler,
            crate::handlers::debate_judge::get_draw_vote_status_handler,
            crate::handlers::debate_judge::submit_draw_vote_handler,
            submit_judge_report_handler,
            submit_judge_phase_report_handler,
            submit_judge_final_report_handler,
            mark_judge_job_failed_handler,
            get_redis_health_handler,
            get_judge_dispatch_metrics_handler,
            list_iap_products_handler,
            get_iap_order_by_transaction_handler,
            verify_iap_order_handler,
            get_wallet_balance_handler,
            list_wallet_ledger_handler,
            list_chat_handler,
            create_chat_handler,
            get_chat_handler,
            update_chat_handler,
            delete_chat_handler,
            join_chat_handler,
            leave_chat_handler,
            add_chat_members_handler,
            remove_chat_members_handler,
            create_agent_handler,
            update_agent_handler,
            list_agent_handler,
            list_message_handler,
            send_message_handler,
            list_chat_users_handler,
        ),
        components(
            schemas(
                User, Chat, ChatType, ChatAgent, AgentType, ChatUser, Message,
                DebateTopic, DebateSessionSummary, ListDebateTopics, ListDebateSessions,
                JudgeRefreshSummaryItem, JudgeRefreshSummaryOutput,
                JudgeRefreshSummaryMetricsOutput,
                OpsCreateDebateTopicInput, OpsCreateDebateSessionInput,
                OpsUpdateDebateTopicInput, OpsUpdateDebateSessionInput,
                UpsertOpsRoleInput, OpsRoleAssignment, ListOpsRoleAssignmentsOutput,
                RevokeOpsRoleOutput, OpsPermissionFlags, GetOpsRbacMeOutput,
                OpsObservabilityThresholds, OpsObservabilityAnomalyStateValue,
                UpdateOpsObservabilityAnomalyStateInput, ApplyOpsObservabilityAnomalyActionInput,
                RunOpsObservabilityEvaluationQuery, GetOpsObservabilityConfigOutput, OpsAlertEvalReport,
                OpsMetricsDictionaryItem, GetOpsMetricsDictionaryOutput,
                OpsSloSignalSnapshot, OpsSloRuleSnapshotItem, GetOpsSloSnapshotOutput,
                OpsServiceSplitThresholdItem, GetOpsServiceSplitReadinessOutput,
                UpsertOpsServiceSplitReviewInput, ListOpsServiceSplitReviewAuditsQuery,
                OpsServiceSplitReviewAuditItem, ListOpsServiceSplitReviewAuditsOutput,
                ListOpsAlertNotificationsQuery, OpsAlertNotificationItem, ListOpsAlertNotificationsOutput,
                ListKafkaDlqEventsQuery, KafkaDlqEventItem, ListKafkaDlqEventsOutput, KafkaDlqActionOutput,
                ListJudgeReviewOpsQuery, JudgeReviewOpsItem, ListJudgeReviewOpsOutput,
                GetJudgeFinalDispatchFailureStatsQuery, JudgeFinalDispatchFailureTypeCount,
                GetJudgeFinalDispatchFailureStatsOutput,
                ListJudgeTraceReplayOpsQuery, JudgeTraceReplayOpsItem, ListJudgeTraceReplayOpsOutput,
                GetJudgeReplayPreviewOpsQuery, JudgeReplayPreviewMeta, GetJudgeReplayPreviewOpsOutput,
                ExecuteJudgeReplayOpsInput, ExecuteJudgeReplayOpsOutput,
                ListJudgeReplayActionsOpsQuery, JudgeReplayActionOpsItem, ListJudgeReplayActionsOpsOutput,
                JoinDebateSessionInput, JoinDebateSessionOutput,
                DebateMessage, CreateDebateMessageInput, ListDebateMessages,
                DebatePinnedMessage, ListDebatePinnedMessages, PinDebateMessageInput, PinDebateMessageOutput,
                RequestJudgeJobInput, RequestJudgeJobOutput, JudgeJobSnapshot, GetJudgeReportQuery,
                JudgeRagSourceItem, JudgeRagMeta, JudgeStageSummaryDetail,
                JudgeStageSummariesMeta, JudgeReportDetail, GetJudgeReportOutput,
                DrawVoteDetail, GetDrawVoteOutput, SubmitDrawVoteInput, SubmitDrawVoteOutput,
                SubmitJudgeReportInput, SubmitJudgeReportOutput, JudgeStageSummaryInput,
                JudgeGroundedSummaryPayload, JudgeRetrievalBundleItemPayload,
                JudgeRetrievalBundlePayload, JudgePhaseAgent1ScorePayload,
                JudgePhaseAgent2ScorePayload, JudgePhaseAgent3WeightedScorePayload,
                SubmitJudgePhaseReportInput, SubmitJudgePhaseReportOutput,
                SubmitJudgeFinalReportInput, SubmitJudgeFinalReportOutput,
                MarkJudgeJobFailedInput, MarkJudgeJobFailedOutput,
                GetJudgeDispatchMetricsOutput, RedisHealthOutput,
                IapProduct, ListIapProducts, GetIapOrderByTransaction, IapOrderSnapshot,
                GetIapOrderByTransactionOutput, VerifyIapOrderInput, VerifyIapOrderOutput,
                WalletBalanceOutput, ListWalletLedger, WalletLedgerItem,
                SigninUser, CreateUser, CreateChat, UpdateChat, UpdateChatMembers,
                SendSmsCodeV2Input, SendSmsCodeV2Output,
                SignupPhoneV2Input, SignupEmailV2Input,
                SigninPasswordV2Input, SigninOtpV2Input,
                WechatChallengeV2Output, WechatSigninV2Input, WechatSigninV2Output, WechatBindPhoneV2Input,
                BindPhoneV2Input, BindPhoneV2Output,
                CreateMessage, ListMessages, AuthOutput, RefreshOutput, LogoutOutput,
                LogoutAllOutput, AuthSessionItem, ListAuthSessionsOutput, AccessTicketsOutput, ErrorOutput
            ),
        ),
        modifiers(&SecurityAddon),
        tags(
            (name = "chat", description = "Chat related operations"),
        )
    )]
pub(crate) struct ApiDoc;

struct SecurityAddon;

impl Modify for SecurityAddon {
    fn modify(&self, openapi: &mut utoipa::openapi::OpenApi) {
        if let Some(components) = openapi.components.as_mut() {
            components.add_security_scheme(
                "token",
                SecurityScheme::Http(HttpBuilder::new().scheme(HttpAuthScheme::Bearer).build()),
            );
            components.add_security_scheme(
                "internal_key",
                SecurityScheme::ApiKey(utoipa::openapi::security::ApiKey::Header(
                    utoipa::openapi::security::ApiKeyValue::new("x-ai-internal-key"),
                )),
            );
        }
    }
}

impl OpenApiRouter for Router<AppState> {
    fn openapi(self) -> Self {
        self.merge(SwaggerUi::new("/swagger-ui").url("/api-docs/openapi.json", ApiDoc::openapi()))
            .merge(Redoc::with_url("/redoc", ApiDoc::openapi()))
            .merge(RapiDoc::new("/api-docs/openapi.json").path("/rapidoc"))
    }
}
