use crate::{AppError, AppState, ListDebateTopics};
use axum::{
    extract::{Query, State},
    http::StatusCode,
    response::IntoResponse,
    Extension, Json,
};
use chat_core::User;

pub(crate) use super::debate_room::{
    create_debate_message_handler, join_debate_session_handler, list_debate_messages_handler,
    list_debate_pinned_messages_handler, list_debate_sessions_handler, pin_debate_message_handler,
};

pub(crate) use super::debate_judge::{
    get_draw_vote_status_handler, get_latest_judge_report_handler, request_judge_job_handler,
    submit_draw_vote_handler,
};
pub(crate) use super::debate_ops::{
    create_debate_session_ops_handler, create_debate_topic_ops_handler,
    discard_kafka_dlq_event_handler, get_ops_observability_config_handler, get_ops_rbac_me_handler,
    list_judge_reviews_ops_handler, list_kafka_dlq_events_handler,
    list_ops_alert_notifications_handler, list_ops_role_assignments_handler,
    replay_kafka_dlq_event_handler, request_judge_rejudge_ops_handler,
    revoke_ops_role_assignment_handler, update_debate_session_ops_handler,
    update_debate_topic_ops_handler, upsert_ops_observability_anomaly_state_handler,
    upsert_ops_observability_thresholds_handler, upsert_ops_role_assignment_handler,
};

/// List debate topics in the current workspace.
#[utoipa::path(
    get,
    path = "/api/debate/topics",
    params(
        ListDebateTopics
    ),
    responses(
        (status = 200, description = "List of debate topics", body = Vec<crate::DebateTopic>),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_debate_topics_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Query(input): Query<ListDebateTopics>,
) -> Result<impl IntoResponse, AppError> {
    let topics = state.list_debate_topics(user.ws_id as _, input).await?;
    Ok((StatusCode::OK, Json(topics)))
}

#[cfg(test)]
mod tests;
