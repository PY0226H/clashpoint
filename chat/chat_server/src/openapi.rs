use crate::handlers::*;
use crate::{
    AppState, CreateChat, CreateDebateMessageInput, CreateMessage, CreateUser, DebateMessage,
    DebatePinnedMessage, DebateSessionSummary, DebateTopic, DrawVoteDetail, ErrorOutput,
    GetDrawVoteOutput, GetIapOrderByTransaction, GetIapOrderByTransactionOutput,
    GetJudgeDispatchMetricsOutput, GetJudgeReportOutput, GetJudgeReportQuery,
    GetOpsObservabilityConfigOutput, GetOpsRbacMeOutput, IapOrderSnapshot, IapProduct,
    JoinDebateSessionInput, JoinDebateSessionOutput, JudgeJobSnapshot, JudgeRagMeta,
    JudgeRagSourceItem, JudgeReportDetail, JudgeReviewOpsItem, JudgeStageSummariesMeta,
    JudgeStageSummaryDetail, JudgeStageSummaryInput, KafkaDlqActionOutput, KafkaDlqEventItem,
    ListDebateMessages, ListDebatePinnedMessages, ListDebateSessions, ListDebateTopics,
    ListIapProducts, ListJudgeReviewOpsOutput, ListJudgeReviewOpsQuery, ListKafkaDlqEventsOutput,
    ListKafkaDlqEventsQuery, ListMessages, ListOpsRoleAssignmentsOutput, ListWalletLedger,
    MarkJudgeJobFailedInput, MarkJudgeJobFailedOutput, OpsCreateDebateSessionInput,
    OpsCreateDebateTopicInput, OpsObservabilityAnomalyStateValue, OpsObservabilityThresholds,
    OpsPermissionFlags, OpsRoleAssignment, OpsUpdateDebateSessionInput, OpsUpdateDebateTopicInput,
    PinDebateMessageInput, PinDebateMessageOutput, RedisHealthOutput, RequestJudgeJobInput,
    RequestJudgeJobOutput, RevokeOpsRoleOutput, SigninUser, SubmitDrawVoteInput,
    SubmitDrawVoteOutput, SubmitJudgeReportInput, SubmitJudgeReportOutput, UpdateChat,
    UpdateChatMembers, UpdateOpsObservabilityAnomalyStateInput, UpsertOpsRoleInput,
    VerifyIapOrderInput, VerifyIapOrderOutput, WalletBalanceOutput, WalletLedgerItem,
};
use axum::Router;
use chat_core::{AgentType, Chat, ChatAgent, ChatType, ChatUser, Message, User, Workspace};
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
            create_access_tickets_handler,
            list_debate_topics_handler,
            create_debate_topic_ops_handler,
            update_debate_topic_ops_handler,
            create_debate_session_ops_handler,
            update_debate_session_ops_handler,
            get_ops_rbac_me_handler,
            get_ops_observability_config_handler,
            upsert_ops_observability_thresholds_handler,
            upsert_ops_observability_anomaly_state_handler,
            list_kafka_dlq_events_handler,
            replay_kafka_dlq_event_handler,
            discard_kafka_dlq_event_handler,
            list_ops_role_assignments_handler,
            upsert_ops_role_assignment_handler,
            revoke_ops_role_assignment_handler,
            list_judge_reviews_ops_handler,
            request_judge_rejudge_ops_handler,
            list_debate_sessions_handler,
            join_debate_session_handler,
            list_debate_messages_handler,
            create_debate_message_handler,
            list_debate_pinned_messages_handler,
            pin_debate_message_handler,
            request_judge_job_handler,
            get_latest_judge_report_handler,
            get_draw_vote_status_handler,
            submit_draw_vote_handler,
            submit_judge_report_handler,
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
                User, Chat, ChatType, ChatAgent, AgentType, ChatUser, Message, Workspace,
                DebateTopic, DebateSessionSummary, ListDebateTopics, ListDebateSessions,
                OpsCreateDebateTopicInput, OpsCreateDebateSessionInput,
                OpsUpdateDebateTopicInput, OpsUpdateDebateSessionInput,
                UpsertOpsRoleInput, OpsRoleAssignment, ListOpsRoleAssignmentsOutput,
                RevokeOpsRoleOutput, OpsPermissionFlags, GetOpsRbacMeOutput,
                OpsObservabilityThresholds, OpsObservabilityAnomalyStateValue,
                UpdateOpsObservabilityAnomalyStateInput, GetOpsObservabilityConfigOutput,
                ListKafkaDlqEventsQuery, KafkaDlqEventItem, ListKafkaDlqEventsOutput, KafkaDlqActionOutput,
                ListJudgeReviewOpsQuery, JudgeReviewOpsItem, ListJudgeReviewOpsOutput,
                JoinDebateSessionInput, JoinDebateSessionOutput,
                DebateMessage, CreateDebateMessageInput, ListDebateMessages,
                DebatePinnedMessage, ListDebatePinnedMessages, PinDebateMessageInput, PinDebateMessageOutput,
                RequestJudgeJobInput, RequestJudgeJobOutput, JudgeJobSnapshot, GetJudgeReportQuery,
                JudgeRagSourceItem, JudgeRagMeta, JudgeStageSummaryDetail,
                JudgeStageSummariesMeta, JudgeReportDetail, GetJudgeReportOutput,
                DrawVoteDetail, GetDrawVoteOutput, SubmitDrawVoteInput, SubmitDrawVoteOutput,
                SubmitJudgeReportInput, SubmitJudgeReportOutput, JudgeStageSummaryInput,
                MarkJudgeJobFailedInput, MarkJudgeJobFailedOutput,
                GetJudgeDispatchMetricsOutput, RedisHealthOutput,
                IapProduct, ListIapProducts, GetIapOrderByTransaction, IapOrderSnapshot,
                GetIapOrderByTransactionOutput, VerifyIapOrderInput, VerifyIapOrderOutput,
                WalletBalanceOutput, ListWalletLedger, WalletLedgerItem,
                SigninUser, CreateUser, CreateChat, UpdateChat, UpdateChatMembers,
                CreateMessage, ListMessages, AuthOutput, AccessTicketsOutput, ErrorOutput
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
