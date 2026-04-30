use super::*;
use crate::AppError;
use reqwest::Client;
use serde_json::{json, Map, Value};
use std::time::Duration;

pub(super) const JUDGE_ASSISTANT_ADVISORY_FORBIDDEN: &str = "judge_assistant_advisory_forbidden";
pub(super) const JUDGE_ASSISTANT_ADVISORY_CASE_MISMATCH: &str =
    "judge_assistant_advisory_case_mismatch";
pub(super) const JUDGE_ASSISTANT_ADVISORY_REASON_PROXY_FAILED: &str =
    "assistant_advisory_proxy_failed";
pub(super) const JUDGE_ASSISTANT_ADVISORY_REASON_CONTRACT_VIOLATION: &str =
    "assistant_advisory_contract_violation";
pub(super) const JUDGE_ASSISTANT_CONTRACT_VERSION: &str = "assistant_advisory_contract_v1";
pub(super) const JUDGE_ASSISTANT_AGENT_KIND_NPC_COACH: &str = "npc_coach";
pub(super) const JUDGE_ASSISTANT_AGENT_KIND_ROOM_QA: &str = "room_qa";

const MAX_ASSISTANT_TRACE_ID_LEN: usize = 160;
const MAX_ASSISTANT_QUERY_LEN: usize = 2_000;

pub(super) struct NormalizedNpcCoachAdviceInput {
    pub trace_id: Option<String>,
    pub query: String,
    pub side: Option<String>,
    pub case_id: Option<u64>,
}

pub(super) struct NormalizedRoomQaAnswerInput {
    pub trace_id: Option<String>,
    pub question: String,
    pub case_id: Option<u64>,
}

pub(super) struct AssistantAdvisoryProxyParams<'a> {
    pub base_url: &'a str,
    pub path: &'a str,
    pub timeout_ms: u64,
    pub internal_key: &'a str,
    pub session_id: u64,
    pub case_id: Option<u64>,
    pub trace_id: &'a str,
    pub query: Option<&'a str>,
    pub question: Option<&'a str>,
    pub side: Option<&'a str>,
}

pub(super) fn normalize_npc_coach_advice_input(
    input: RequestNpcCoachAdviceInput,
) -> Result<NormalizedNpcCoachAdviceInput, AppError> {
    let query = normalize_required_assistant_text("query", input.query)?;
    let trace_id = normalize_optional_assistant_token("traceId", input.trace_id)?;
    let side = match input.side {
        Some(value) => {
            let normalized = value.trim().to_ascii_lowercase();
            if normalized == "pro" || normalized == "con" {
                Some(normalized)
            } else {
                return Err(AppError::DebateError(
                    "side must be one of: pro, con".to_string(),
                ));
            }
        }
        None => None,
    };
    Ok(NormalizedNpcCoachAdviceInput {
        trace_id,
        query,
        side,
        case_id: input.case_id,
    })
}

pub(super) fn normalize_room_qa_answer_input(
    input: RequestRoomQaAnswerInput,
) -> Result<NormalizedRoomQaAnswerInput, AppError> {
    let question = normalize_required_assistant_text("question", input.question)?;
    let trace_id = normalize_optional_assistant_token("traceId", input.trace_id)?;
    Ok(NormalizedRoomQaAnswerInput {
        trace_id,
        question,
        case_id: input.case_id,
    })
}

pub(super) fn build_assistant_advisory_proxy_error_output(
    session_id: u64,
    case_id: Option<u64>,
    agent_kind: &str,
    reason_code: &str,
) -> JudgeAssistantAdvisoryOutput {
    JudgeAssistantAdvisoryOutput {
        version: JUDGE_ASSISTANT_CONTRACT_VERSION.to_string(),
        agent_kind: agent_kind.to_string(),
        session_id,
        case_id,
        advisory_only: true,
        status: "proxy_error".to_string(),
        status_reason: reason_code.to_string(),
        accepted: false,
        error_code: Some(reason_code.to_string()),
        error_message: Some("assistant advisory proxy request failed".to_string()),
        capability_boundary: default_assistant_capability_boundary(),
        shared_context: json!({}),
        advisory_context: json!({}),
        output: json!({}),
        cache_profile: default_assistant_cache_profile(session_id, agent_kind),
    }
}

pub(super) fn build_assistant_advisory_output_from_payload(
    session_id: u64,
    agent_kind: &str,
    payload: Value,
) -> JudgeAssistantAdvisoryOutput {
    let case_id = payload.get("caseId").and_then(Value::as_u64);
    let status = payload
        .get("status")
        .and_then(Value::as_str)
        .unwrap_or("proxy_error")
        .to_string();
    let error_code = payload
        .get("errorCode")
        .and_then(Value::as_str)
        .map(ToString::to_string);
    let status_reason = if status == "not_ready" {
        error_code
            .clone()
            .unwrap_or_else(|| "agent_not_enabled".to_string())
    } else if status == "ok" {
        "assistant_advisory_ready".to_string()
    } else {
        error_code
            .clone()
            .unwrap_or_else(|| format!("assistant_advisory_{status}"))
    };
    JudgeAssistantAdvisoryOutput {
        version: payload
            .get("version")
            .and_then(Value::as_str)
            .unwrap_or(JUDGE_ASSISTANT_CONTRACT_VERSION)
            .to_string(),
        agent_kind: payload
            .get("agentKind")
            .and_then(Value::as_str)
            .unwrap_or(agent_kind)
            .to_string(),
        session_id,
        case_id,
        advisory_only: payload
            .get("advisoryOnly")
            .and_then(Value::as_bool)
            .unwrap_or(false),
        status,
        status_reason,
        accepted: payload
            .get("accepted")
            .and_then(Value::as_bool)
            .unwrap_or(false),
        error_code,
        error_message: payload
            .get("errorMessage")
            .and_then(Value::as_str)
            .map(ToString::to_string),
        capability_boundary: payload
            .get("capabilityBoundary")
            .cloned()
            .unwrap_or_else(default_assistant_capability_boundary),
        shared_context: payload
            .get("sharedContext")
            .cloned()
            .unwrap_or_else(|| json!({})),
        advisory_context: payload
            .get("advisoryContext")
            .cloned()
            .unwrap_or_else(|| json!({})),
        output: payload.get("output").cloned().unwrap_or_else(|| json!({})),
        cache_profile: payload
            .get("cacheProfile")
            .cloned()
            .unwrap_or_else(|| default_assistant_cache_profile(session_id, agent_kind)),
    }
}

pub(super) async fn fetch_ai_judge_assistant_advisory_payload(
    params: AssistantAdvisoryProxyParams<'_>,
) -> Result<Value, &'static str> {
    let url = build_assistant_advisory_http_url(params.base_url, params.path, params.session_id);
    let client = Client::builder()
        .timeout(Duration::from_millis(params.timeout_ms.max(1)))
        .build()
        .map_err(|_| "assistant_advisory_proxy_http_client_failed")?;
    let mut body = Map::new();
    body.insert("trace_id".to_string(), json!(params.trace_id));
    if let Some(case_id) = params.case_id {
        body.insert("caseId".to_string(), json!(case_id));
    }
    if let Some(query) = params.query {
        body.insert("query".to_string(), json!(query));
    }
    if let Some(question) = params.question {
        body.insert("question".to_string(), json!(question));
    }
    if let Some(side) = params.side {
        body.insert("side".to_string(), json!(side));
    }

    let response = client
        .post(url)
        .header("x-ai-internal-key", params.internal_key)
        .json(&Value::Object(body))
        .send()
        .await
        .map_err(|_| "assistant_advisory_proxy_request_failed")?;
    if !response.status().is_success() {
        return Err("assistant_advisory_proxy_bad_status");
    }
    response
        .json::<Value>()
        .await
        .map_err(|_| "assistant_advisory_proxy_bad_json")
}

pub(super) fn validate_assistant_advisory_payload(
    payload: &Value,
    expected_session_id: u64,
    expected_case_id: Option<u64>,
    expected_agent_kind: &str,
) -> Result<(), &'static str> {
    let Some(object) = payload.as_object() else {
        return Err(JUDGE_ASSISTANT_ADVISORY_REASON_CONTRACT_VIOLATION);
    };
    if !assistant_top_level_keys_match(object) {
        return Err(JUDGE_ASSISTANT_ADVISORY_REASON_CONTRACT_VIOLATION);
    }
    if object.get("version").and_then(Value::as_str) != Some(JUDGE_ASSISTANT_CONTRACT_VERSION) {
        return Err(JUDGE_ASSISTANT_ADVISORY_REASON_CONTRACT_VIOLATION);
    }
    if object.get("agentKind").and_then(Value::as_str) != Some(expected_agent_kind) {
        return Err(JUDGE_ASSISTANT_ADVISORY_REASON_CONTRACT_VIOLATION);
    }
    if object.get("sessionId").and_then(Value::as_u64) != Some(expected_session_id) {
        return Err(JUDGE_ASSISTANT_ADVISORY_REASON_CONTRACT_VIOLATION);
    }
    if let Some(expected_case_id) = expected_case_id {
        if object.get("caseId").and_then(Value::as_u64) != Some(expected_case_id) {
            return Err(JUDGE_ASSISTANT_ADVISORY_REASON_CONTRACT_VIOLATION);
        }
    }
    if object.get("advisoryOnly").and_then(Value::as_bool) != Some(true) {
        return Err(JUDGE_ASSISTANT_ADVISORY_REASON_CONTRACT_VIOLATION);
    }
    if object.get("accepted").and_then(Value::as_bool).is_none() {
        return Err(JUDGE_ASSISTANT_ADVISORY_REASON_CONTRACT_VIOLATION);
    }
    let Some(boundary) = object.get("capabilityBoundary").and_then(Value::as_object) else {
        return Err(JUDGE_ASSISTANT_ADVISORY_REASON_CONTRACT_VIOLATION);
    };
    if boundary.get("mode").and_then(Value::as_str) != Some("advisory_only")
        || boundary.get("advisoryOnly").and_then(Value::as_bool) != Some(true)
        || boundary
            .get("officialVerdictAuthority")
            .and_then(Value::as_bool)
            != Some(false)
        || boundary.get("writesVerdictLedger").and_then(Value::as_bool) != Some(false)
        || boundary.get("writesJudgeTrace").and_then(Value::as_bool) != Some(false)
        || boundary
            .get("canTriggerOfficialJudgeRoles")
            .and_then(Value::as_bool)
            != Some(false)
    {
        return Err(JUDGE_ASSISTANT_ADVISORY_REASON_CONTRACT_VIOLATION);
    }
    if !matches!(object.get("sharedContext"), Some(Value::Object(_)))
        || !matches!(object.get("advisoryContext"), Some(Value::Object(_)))
        || !matches!(object.get("output"), Some(Value::Object(_)))
        || !matches!(object.get("cacheProfile"), Some(Value::Object(_)))
    {
        return Err(JUDGE_ASSISTANT_ADVISORY_REASON_CONTRACT_VIOLATION);
    }
    for key in ["sharedContext", "advisoryContext", "output"] {
        if assistant_value_contains_forbidden_key(
            object.get(key).unwrap_or(&Value::Null),
            key == "output",
        ) {
            return Err(JUDGE_ASSISTANT_ADVISORY_REASON_CONTRACT_VIOLATION);
        }
    }
    if object.get("status").and_then(Value::as_str) == Some("not_ready")
        && (object.get("accepted").and_then(Value::as_bool) != Some(false)
            || object.get("errorCode").and_then(Value::as_str) != Some("agent_not_enabled"))
    {
        return Err(JUDGE_ASSISTANT_ADVISORY_REASON_CONTRACT_VIOLATION);
    }
    Ok(())
}

fn normalize_required_assistant_text(field: &str, value: String) -> Result<String, AppError> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return Err(AppError::DebateError(format!("{field} is required")));
    }
    if trimmed.chars().count() > MAX_ASSISTANT_QUERY_LEN {
        return Err(AppError::DebateError(format!(
            "{field} is too long, max {MAX_ASSISTANT_QUERY_LEN} chars"
        )));
    }
    Ok(trimmed.to_string())
}

fn normalize_optional_assistant_token(
    field: &str,
    value: Option<String>,
) -> Result<Option<String>, AppError> {
    match value {
        Some(raw) => {
            let trimmed = raw.trim();
            if trimmed.is_empty() {
                return Ok(None);
            }
            if trimmed.chars().count() > MAX_ASSISTANT_TRACE_ID_LEN {
                return Err(AppError::DebateError(format!(
                    "{field} is too long, max {MAX_ASSISTANT_TRACE_ID_LEN} chars"
                )));
            }
            Ok(Some(trimmed.to_string()))
        }
        None => Ok(None),
    }
}

fn build_assistant_advisory_http_url(base_url: &str, path: &str, session_id: u64) -> String {
    let resolved_path = path
        .replace("{session_id}", &session_id.to_string())
        .replace(":session_id", &session_id.to_string());
    let resolved_path = if resolved_path.starts_with('/') {
        resolved_path
    } else {
        format!("/{resolved_path}")
    };
    format!("{}{}", base_url.trim_end_matches('/'), resolved_path)
}

fn default_assistant_capability_boundary() -> Value {
    json!({
        "mode": "advisory_only",
        "advisoryOnly": true,
        "officialVerdictAuthority": false,
        "writesVerdictLedger": false,
        "writesJudgeTrace": false,
        "canTriggerOfficialJudgeRoles": false
    })
}

fn default_assistant_cache_profile(session_id: u64, agent_kind: &str) -> Value {
    json!({
        "cacheable": false,
        "ttlSeconds": 0,
        "cacheKey": format!("assistant-advisory:chat-proxy:session:{session_id}:agent:{agent_kind}"),
        "varyBy": ["authorization", "agentKind", "caseId"]
    })
}

fn assistant_top_level_keys_match(object: &Map<String, Value>) -> bool {
    const KEYS: &[&str] = &[
        "version",
        "agentKind",
        "sessionId",
        "caseId",
        "advisoryOnly",
        "status",
        "accepted",
        "errorCode",
        "errorMessage",
        "capabilityBoundary",
        "sharedContext",
        "advisoryContext",
        "output",
        "cacheProfile",
    ];
    object.len() == KEYS.len() && KEYS.iter().all(|key| object.contains_key(*key))
}

fn normalize_assistant_contract_key(key: &str) -> String {
    key.chars()
        .filter(|c| *c != '_' && *c != '-')
        .flat_map(char::to_lowercase)
        .collect()
}

fn assistant_value_contains_forbidden_key(value: &Value, output_scope: bool) -> bool {
    match value {
        Value::Object(map) => map.iter().any(|(key, value)| {
            is_assistant_forbidden_key(key, output_scope)
                || assistant_value_contains_forbidden_key(value, output_scope)
        }),
        Value::Array(items) => items
            .iter()
            .any(|item| assistant_value_contains_forbidden_key(item, output_scope)),
        _ => false,
    }
}

fn is_assistant_forbidden_key(key: &str, output_scope: bool) -> bool {
    let normalized = normalize_assistant_contract_key(key);
    let private_or_official = matches!(
        normalized.as_str(),
        "winner"
            | "verdictreason"
            | "verdictledger"
            | "fairnessgate"
            | "trustattestation"
            | "rawprompt"
            | "rawtrace"
            | "artifactref"
            | "artifactrefs"
            | "providerconfig"
            | "secret"
            | "secretref"
            | "credential"
            | "internalkey"
            | "xaiinternalkey"
    );
    if private_or_official {
        return true;
    }
    output_scope
        && matches!(
            normalized.as_str(),
            "proscore"
                | "conscore"
                | "dimensionscores"
                | "verdictevidencerefs"
                | "auditalerts"
                | "errorcodes"
                | "degradationlevel"
                | "debatesummary"
                | "sideanalysis"
                | "finalrationale"
                | "fairnesssummary"
                | "needsdrawvote"
                | "reviewrequired"
                | "dispatchtype"
                | "judgepolicyversion"
                | "rubricversion"
                | "ruleversion"
                | "officialverdictauthority"
                | "writesverdictledger"
                | "writesjudgetrace"
                | "cantriggerofficialjudgeroles"
        )
}
