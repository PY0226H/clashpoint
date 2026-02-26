use super::{
    AppError, DEBATE_MESSAGE_DEFAULT_LIMIT, DEBATE_MESSAGE_MAX_LEN, DEBATE_MESSAGE_MAX_LIMIT,
    DEBATE_PIN_DEFAULT_LIMIT, DEBATE_PIN_MAX_LIMIT, DEFAULT_LIMIT, MAX_LIMIT,
    PIN_BILLING_UNIT_SECONDS, PIN_COST_PER_UNIT_COINS, PIN_MAX_SECONDS, PIN_MIN_SECONDS,
};

pub(super) fn normalize_limit(limit: Option<u64>) -> i64 {
    let limit = limit.unwrap_or(DEFAULT_LIMIT).clamp(1, MAX_LIMIT);
    limit as i64
}

pub(super) fn normalize_debate_message_limit(limit: Option<u64>) -> i64 {
    let limit = limit
        .unwrap_or(DEBATE_MESSAGE_DEFAULT_LIMIT)
        .clamp(1, DEBATE_MESSAGE_MAX_LIMIT);
    limit as i64
}

pub(super) fn normalize_debate_pin_limit(limit: Option<u64>) -> i64 {
    let limit = limit
        .unwrap_or(DEBATE_PIN_DEFAULT_LIMIT)
        .clamp(1, DEBATE_PIN_MAX_LIMIT);
    limit as i64
}

pub(super) fn valid_join_side(side: &str) -> bool {
    matches!(side, "pro" | "con")
}

pub(super) fn can_join_status(status: &str) -> bool {
    matches!(status, "open" | "running")
}

pub(super) fn normalize_ops_topic_field(
    value: &str,
    field: &str,
    max_len: usize,
) -> Result<String, AppError> {
    let text = value.trim();
    if text.is_empty() {
        return Err(AppError::DebateError(format!("{field} cannot be empty")));
    }
    if text.len() > max_len {
        return Err(AppError::DebateError(format!(
            "{field} is too long, max {max_len}"
        )));
    }
    Ok(text.to_string())
}

pub(super) fn normalize_ops_session_status(status: Option<String>) -> Result<String, AppError> {
    let status = status
        .unwrap_or_else(|| "scheduled".to_string())
        .trim()
        .to_lowercase();
    if matches!(status.as_str(), "scheduled" | "open") {
        return Ok(status);
    }
    Err(AppError::DebateError(
        "status must be `scheduled` or `open`".to_string(),
    ))
}

pub(super) fn normalize_ops_manage_session_status(
    status: Option<String>,
) -> Result<Option<String>, AppError> {
    let Some(status) = status else {
        return Ok(None);
    };
    let status = status.trim().to_lowercase();
    if matches!(
        status.as_str(),
        "scheduled" | "open" | "running" | "judging" | "closed" | "canceled"
    ) {
        return Ok(Some(status));
    }
    Err(AppError::DebateError(
        "status must be one of `scheduled|open|running|judging|closed|canceled`".to_string(),
    ))
}

pub(super) fn normalize_message_content(content: &str) -> Result<String, AppError> {
    let content = content.trim();
    if content.is_empty() {
        return Err(AppError::DebateError(
            "message content cannot be empty".to_string(),
        ));
    }
    if content.len() > DEBATE_MESSAGE_MAX_LEN {
        return Err(AppError::DebateError(format!(
            "message content too long, max {} chars",
            DEBATE_MESSAGE_MAX_LEN
        )));
    }
    Ok(content.to_string())
}

pub(super) fn normalize_pin_seconds(pin_seconds: i32) -> Result<i32, AppError> {
    if !(PIN_MIN_SECONDS..=PIN_MAX_SECONDS).contains(&pin_seconds) {
        return Err(AppError::PaymentError(format!(
            "pin_seconds must be between {} and {}",
            PIN_MIN_SECONDS, PIN_MAX_SECONDS
        )));
    }
    Ok(pin_seconds)
}

pub(super) fn pin_cost_coins(pin_seconds: i32) -> i64 {
    let units = (pin_seconds + PIN_BILLING_UNIT_SECONDS - 1) / PIN_BILLING_UNIT_SECONDS;
    units as i64 * PIN_COST_PER_UNIT_COINS
}
