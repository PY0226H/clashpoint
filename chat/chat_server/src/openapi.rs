use crate::handlers::*;
use crate::{
    AppState, CreateChat, CreateMessage, CreateUser, DebateSessionSummary, DebateTopic,
    ErrorOutput, JoinDebateSessionInput, JoinDebateSessionOutput, ListDebateSessions,
    ListDebateTopics, ListMessages, SigninUser,
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
            list_debate_sessions_handler,
            join_debate_session_handler,
            list_chat_handler,
            create_chat_handler,
            get_chat_handler,
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
                JoinDebateSessionInput, JoinDebateSessionOutput,
                SigninUser, CreateUser, CreateChat, CreateMessage, ListMessages, AuthOutput, AccessTicketsOutput, ErrorOutput
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
            )
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
