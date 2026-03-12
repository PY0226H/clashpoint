use analytics_server::AnalyticsEventRow;
use chat_core::pb::{
    analytics_event::EventType, AnalyticsEvent, ChatCreatedEvent, EventContext, SystemInfo,
    UserRegisterEvent,
};

fn test_context() -> EventContext {
    EventContext {
        client_id: "client-1".to_string(),
        app_version: "1.0.0".to_string(),
        system: Some(SystemInfo {
            os: "iOS".to_string(),
            arch: "arm64".to_string(),
            locale: "zh-CN".to_string(),
            timezone: "Asia/Shanghai".to_string(),
        }),
        user_id: "u-1".to_string(),
        ip: "127.0.0.1".to_string(),
        user_agent: "test-agent".to_string(),
        geo: None,
        client_ts: 1,
        server_ts: 1,
    }
}

#[test]
fn user_register_event_should_convert_without_workspace_field() {
    let event = AnalyticsEvent {
        context: Some(test_context()),
        event_type: Some(EventType::UserRegister(UserRegisterEvent {
            email: "user@example.com".to_string(),
            account_type: "email".to_string(),
            account_identifier_hash: "abc123".to_string(),
            user_id: "u-1".to_string(),
        })),
    };

    let row = AnalyticsEventRow::try_from(event).expect("convert analytics event");

    assert_eq!(row.event_type, "user_register");
    assert_eq!(row.register_email.as_deref(), Some("user@example.com"));
    assert_eq!(row.register_account_type.as_deref(), Some("email"));
    assert_eq!(
        row.register_account_identifier_hash.as_deref(),
        Some("abc123")
    );
    assert_eq!(row.register_user_id.as_deref(), Some("u-1"));
}

#[test]
fn chat_created_event_should_convert_without_workspace_field() {
    let event = AnalyticsEvent {
        context: Some(test_context()),
        event_type: Some(EventType::ChatCreated(ChatCreatedEvent {})),
    };

    let row = AnalyticsEventRow::try_from(event).expect("convert analytics event");

    assert_eq!(row.event_type, "chat_created");
}
