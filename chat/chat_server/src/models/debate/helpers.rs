use super::{
    AppError, DEBATE_MESSAGE_DEFAULT_LIMIT, DEBATE_MESSAGE_MAX_LEN, DEBATE_MESSAGE_MAX_LIMIT,
    DEBATE_PIN_DEFAULT_LIMIT, DEBATE_PIN_MAX_LIMIT, DEFAULT_LIMIT, MAX_LIMIT,
    PIN_BILLING_UNIT_SECONDS, PIN_COST_PER_UNIT_COINS, PIN_MAX_SECONDS, PIN_MIN_SECONDS,
};
use chrono::{DateTime, Duration, Utc};

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

pub(super) fn normalize_join_side(raw: &str) -> Result<String, AppError> {
    let normalized = raw.trim().to_ascii_lowercase();
    if valid_join_side(&normalized) {
        return Ok(normalized);
    }
    Err(AppError::ValidationError(
        "debate_join_invalid_side".to_string(),
    ))
}

pub(super) fn can_join_status(status: &str) -> bool {
    matches!(status, "open" | "running")
}

pub(super) fn can_spectate_status(status: &str) -> bool {
    matches!(status, "running" | "judging" | "closed")
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

pub(super) fn normalize_topic_category(value: &str, max_len: usize) -> Result<String, AppError> {
    let text = normalize_ops_topic_field(value, "category", max_len)?;
    Ok(text.to_lowercase())
}

pub(super) fn normalize_topic_category_filter(raw: Option<String>) -> Option<String> {
    raw.and_then(|value| {
        let normalized = value.trim().to_lowercase();
        if normalized.is_empty() {
            None
        } else {
            Some(normalized)
        }
    })
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

pub(super) fn normalize_list_session_status(
    status: Option<String>,
) -> Result<Option<String>, AppError> {
    let Some(status) = status else {
        return Ok(None);
    };
    let status = status.trim().to_lowercase();
    if status.is_empty() {
        return Ok(None);
    }
    if matches!(
        status.as_str(),
        "scheduled" | "open" | "running" | "judging" | "closed" | "canceled"
    ) {
        return Ok(Some(status));
    }
    Err(AppError::ValidationError(
        "debate_sessions_invalid_status".to_string(),
    ))
}

pub(super) fn validate_list_debate_sessions_time_range(
    from: Option<DateTime<Utc>>,
    to: Option<DateTime<Utc>>,
    max_window_days: i64,
) -> Result<(), AppError> {
    let (Some(from), Some(to)) = (from, to) else {
        return Ok(());
    };
    if from > to {
        return Err(AppError::ValidationError(
            "debate_sessions_invalid_time_range".to_string(),
        ));
    }
    if to.signed_duration_since(from) > Duration::days(max_window_days.max(1)) {
        return Err(AppError::ValidationError(
            "debate_sessions_time_window_too_large".to_string(),
        ));
    }
    Ok(())
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

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(super) struct PhaseTriggerCheckpoint {
    pub phase_no: i32,
    pub message_start_index: i64,
    pub message_end_index: i64,
}

pub(super) fn evaluate_phase_trigger_checkpoint(
    message_count: i64,
    window_size: i64,
) -> Option<PhaseTriggerCheckpoint> {
    if message_count <= 0 || window_size <= 0 || message_count % window_size != 0 {
        return None;
    }
    let phase_no = (message_count / window_size) as i32;
    let message_start_index = ((phase_no as i64 - 1) * window_size) + 1;
    Some(PhaseTriggerCheckpoint {
        phase_no,
        message_start_index,
        message_end_index: message_count,
    })
}

pub(super) fn build_phase_trigger_idempotency_key(
    session_id: i64,
    phase_no: i32,
    rubric_version: &str,
    judge_policy_version: &str,
) -> String {
    format!(
        "judge_phase:{}:{}:{}:{}",
        session_id, phase_no, rubric_version, judge_policy_version
    )
}

pub(super) fn build_phase_trigger_trace_id(session_id: i64, phase_no: i32) -> String {
    format!("judge-phase-{}-{}", session_id, phase_no)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn evaluate_phase_trigger_checkpoint_should_only_fire_on_window_boundary() {
        assert_eq!(
            evaluate_phase_trigger_checkpoint(100, 100),
            Some(PhaseTriggerCheckpoint {
                phase_no: 1,
                message_start_index: 1,
                message_end_index: 100,
            })
        );
        assert_eq!(
            evaluate_phase_trigger_checkpoint(200, 100),
            Some(PhaseTriggerCheckpoint {
                phase_no: 2,
                message_start_index: 101,
                message_end_index: 200,
            })
        );
        assert_eq!(evaluate_phase_trigger_checkpoint(199, 100), None);
        assert_eq!(evaluate_phase_trigger_checkpoint(0, 100), None);
    }

    #[test]
    fn phase_trigger_key_builders_should_be_stable() {
        assert_eq!(
            build_phase_trigger_idempotency_key(88, 3, "v3", "v3-default"),
            "judge_phase:88:3:v3:v3-default"
        );
        assert_eq!(build_phase_trigger_trace_id(88, 3), "judge-phase-88-3");
    }
}
