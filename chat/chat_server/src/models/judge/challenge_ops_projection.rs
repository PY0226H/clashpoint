use super::*;
use serde_json::{json, Value};

pub(super) const JUDGE_CHALLENGE_OPS_REASON_PROXY_FAILED: &str = "challenge_ops_queue_proxy_failed";

const JUDGE_CHALLENGE_OPS_STATUS_READY: &str = "ready";
const JUDGE_CHALLENGE_OPS_STATUS_PROXY_ERROR: &str = "proxy_error";
const JUDGE_CHALLENGE_OPS_REASON_READY: &str = "challenge_ops_queue_ready";
const JUDGE_CHALLENGE_OPS_REASON_CONTRACT_VIOLATION: &str =
    "challenge_ops_queue_contract_violation";

fn normalized_key(key: &str) -> String {
    key.chars()
        .filter(|c| *c != '_' && *c != '-')
        .flat_map(char::to_lowercase)
        .collect()
}

fn ops_projection_forbidden_key(key: &str) -> bool {
    matches!(
        normalized_key(key).as_str(),
        "provider"
            | "rawtrace"
            | "prompt"
            | "privateaudit"
            | "bucket"
            | "endpoint"
            | "path"
            | "secret"
            | "secretref"
            | "credential"
            | "internalkey"
            | "xaiinternalkey"
            | "objectkey"
            | "objectpath"
            | "objectstorelocator"
            | "objectstorepath"
            | "secretkey"
            | "signedurl"
            | "url"
    )
}

fn ops_projection_contains_forbidden_key(value: &Value) -> bool {
    match value {
        Value::Object(map) => map.iter().any(|(key, value)| {
            ops_projection_forbidden_key(key) || ops_projection_contains_forbidden_key(value)
        }),
        Value::Array(items) => items.iter().any(ops_projection_contains_forbidden_key),
        _ => false,
    }
}

fn value_u32(payload: &Value, key: &str) -> u32 {
    payload
        .get(key)
        .and_then(Value::as_u64)
        .and_then(|value| u32::try_from(value).ok())
        .unwrap_or(0)
}

fn object_value(payload: &Value, key: &str) -> Value {
    payload
        .get(key)
        .filter(|value| value.is_object())
        .cloned()
        .unwrap_or_else(|| json!({}))
}

fn array_values(payload: &Value, key: &str) -> Vec<Value> {
    payload
        .get(key)
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default()
}

fn sanitized_challenge_ops_summary(payload: &Value) -> Result<Value, &'static str> {
    let Some(summary) = payload.get("summary").filter(|value| value.is_object()) else {
        return Err(JUDGE_CHALLENGE_OPS_REASON_CONTRACT_VIOLATION);
    };
    Ok(json!({
        "openCount": value_u32(summary, "openCount"),
        "urgentCount": value_u32(summary, "urgentCount"),
        "highPriorityCount": value_u32(summary, "highPriorityCount"),
        "oldestOpenAgeMinutes": summary.get("oldestOpenAgeMinutes").cloned().unwrap_or(Value::Null),
        "stateCounts": object_value(summary, "stateCounts"),
        "reviewStateCounts": object_value(summary, "reviewStateCounts"),
        "priorityLevelCounts": object_value(summary, "priorityLevelCounts"),
        "slaBucketCounts": object_value(summary, "slaBucketCounts"),
        "reasonCodeCounts": object_value(summary, "reasonCodeCounts"),
        "actionHintCounts": object_value(summary, "actionHintCounts"),
    }))
}

fn sanitized_challenge_ops_filters(payload: &Value) -> Value {
    let filters = payload.get("filters").unwrap_or(&Value::Null);
    json!({
        "status": filters.get("status").cloned().unwrap_or(Value::Null),
        "dispatchType": filters.get("dispatchType").cloned().unwrap_or(Value::Null),
        "challengeState": filters.get("challengeState").cloned().unwrap_or(Value::Null),
        "reviewState": filters.get("reviewState").cloned().unwrap_or(Value::Null),
        "priorityLevel": filters.get("priorityLevel").cloned().unwrap_or(Value::Null),
        "slaBucket": filters.get("slaBucket").cloned().unwrap_or(Value::Null),
        "hasOpenAlert": filters.get("hasOpenAlert").cloned().unwrap_or(Value::Null),
        "sortBy": filters.get("sortBy").cloned().unwrap_or(Value::Null),
        "sortOrder": filters.get("sortOrder").cloned().unwrap_or(Value::Null),
        "scanLimit": filters.get("scanLimit").cloned().unwrap_or(Value::Null),
        "offset": filters.get("offset").cloned().unwrap_or(Value::Null),
        "limit": filters.get("limit").cloned().unwrap_or(Value::Null),
    })
}

fn sanitized_challenge_ops_item(item: &Value) -> Option<Value> {
    let item = item.as_object()?;
    let item_value = Value::Object(item.clone());
    let workflow = item_value.get("workflow").unwrap_or(&Value::Null);
    let trace = item_value.get("trace").unwrap_or(&Value::Null);
    let challenge_review = item_value.get("challengeReview").unwrap_or(&Value::Null);
    let priority = item_value.get("priorityProfile").unwrap_or(&Value::Null);
    let review = item_value.get("review").unwrap_or(&Value::Null);
    Some(json!({
        "caseId": item_value.get("caseId").cloned().unwrap_or(Value::Null),
        "dispatchType": item_value.get("dispatchType").cloned().unwrap_or(Value::Null),
        "traceId": item_value.get("traceId").cloned().unwrap_or(Value::Null),
        "workflow": {
            "caseId": workflow.get("caseId").cloned().unwrap_or(Value::Null),
            "dispatchType": workflow.get("dispatchType").cloned().unwrap_or(Value::Null),
            "status": workflow.get("status").cloned().unwrap_or(Value::Null),
            "scopeId": workflow.get("scopeId").cloned().unwrap_or(Value::Null),
            "sessionId": workflow.get("sessionId").cloned().unwrap_or(Value::Null),
            "rubricVersion": workflow.get("rubricVersion").cloned().unwrap_or(Value::Null),
            "judgePolicyVersion": workflow.get("judgePolicyVersion").cloned().unwrap_or(Value::Null),
            "topicDomain": workflow.get("topicDomain").cloned().unwrap_or(Value::Null),
            "createdAt": workflow.get("createdAt").cloned().unwrap_or(Value::Null),
            "updatedAt": workflow.get("updatedAt").cloned().unwrap_or(Value::Null),
        },
        "trace": {
            "status": trace.get("status").cloned().unwrap_or(Value::Null),
            "callbackStatus": trace.get("callbackStatus").cloned().unwrap_or(Value::Null),
            "updatedAt": trace.get("updatedAt").cloned().unwrap_or(Value::Null),
        },
        "challengeReview": {
            "state": challenge_review.get("state").cloned().unwrap_or(Value::Null),
            "activeChallengeId": challenge_review.get("activeChallengeId").cloned().unwrap_or(Value::Null),
            "totalChallenges": challenge_review.get("totalChallenges").cloned().unwrap_or(Value::Null),
            "reviewState": challenge_review.get("reviewState").cloned().unwrap_or(Value::Null),
            "reviewRequired": challenge_review.get("reviewRequired").cloned().unwrap_or(Value::Null),
            "challengeReasons": challenge_review.get("challengeReasons").cloned().unwrap_or_else(|| json!([])),
            "alertSummary": object_value(challenge_review, "alertSummary"),
        },
        "priorityProfile": {
            "score": priority.get("score").cloned().unwrap_or(Value::Null),
            "level": priority.get("level").cloned().unwrap_or(Value::Null),
            "tags": priority.get("tags").cloned().unwrap_or_else(|| json!([])),
            "ageMinutes": priority.get("ageMinutes").cloned().unwrap_or(Value::Null),
            "slaBucket": priority.get("slaBucket").cloned().unwrap_or(Value::Null),
            "challengeState": priority.get("challengeState").cloned().unwrap_or(Value::Null),
            "reviewState": priority.get("reviewState").cloned().unwrap_or(Value::Null),
            "reviewRequired": priority.get("reviewRequired").cloned().unwrap_or(Value::Null),
            "totalChallenges": priority.get("totalChallenges").cloned().unwrap_or(Value::Null),
            "openAlertCount": priority.get("openAlertCount").cloned().unwrap_or(Value::Null),
        },
        "review": {
            "required": review.get("required").cloned().unwrap_or(Value::Null),
            "state": review.get("state").cloned().unwrap_or(Value::Null),
            "workflowStatus": review.get("workflowStatus").cloned().unwrap_or(Value::Null),
        },
        "actionHints": item_value.get("actionHints").cloned().unwrap_or_else(|| json!([])),
    }))
}

fn sanitized_challenge_ops_errors(payload: &Value) -> Vec<Value> {
    array_values(payload, "errors")
        .into_iter()
        .filter_map(|error| {
            Some(json!({
                "caseId": error.get("caseId")?.clone(),
                "statusCode": error.get("statusCode").cloned().unwrap_or(Value::Null),
                "errorCode": error.get("errorCode").cloned().unwrap_or(Value::Null),
            }))
        })
        .collect()
}

pub(super) fn build_judge_challenge_ops_queue_output_from_payload(
    payload: Value,
) -> Result<ListJudgeChallengeOpsQueueOutput, &'static str> {
    let Some(object) = payload.as_object() else {
        return Err(JUDGE_CHALLENGE_OPS_REASON_CONTRACT_VIOLATION);
    };
    for key in [
        "count",
        "returned",
        "scanned",
        "skipped",
        "errorCount",
        "summary",
        "items",
        "errors",
        "filters",
    ] {
        if !object.contains_key(key) {
            return Err(JUDGE_CHALLENGE_OPS_REASON_CONTRACT_VIOLATION);
        }
    }
    let items = array_values(&payload, "items")
        .iter()
        .filter_map(sanitized_challenge_ops_item)
        .collect::<Vec<_>>();
    let summary = sanitized_challenge_ops_summary(&payload)?;
    let filters = sanitized_challenge_ops_filters(&payload);
    let errors = sanitized_challenge_ops_errors(&payload);
    let public_payload = json!({
        "summary": summary,
        "items": items,
        "errors": errors,
        "filters": filters,
    });
    if ops_projection_contains_forbidden_key(&public_payload) {
        return Err(JUDGE_CHALLENGE_OPS_REASON_CONTRACT_VIOLATION);
    }
    Ok(ListJudgeChallengeOpsQueueOutput {
        status: JUDGE_CHALLENGE_OPS_STATUS_READY.to_string(),
        status_reason: JUDGE_CHALLENGE_OPS_REASON_READY.to_string(),
        count: value_u32(&payload, "count"),
        returned: value_u32(&payload, "returned"),
        scanned: value_u32(&payload, "scanned"),
        skipped: value_u32(&payload, "skipped"),
        error_count: value_u32(&payload, "errorCount"),
        summary: public_payload["summary"].clone(),
        items: public_payload["items"]
            .as_array()
            .cloned()
            .unwrap_or_default(),
        errors: public_payload["errors"]
            .as_array()
            .cloned()
            .unwrap_or_default(),
        filters: public_payload["filters"].clone(),
    })
}

pub(super) fn build_judge_challenge_ops_queue_proxy_error_output(
    reason_code: &str,
) -> ListJudgeChallengeOpsQueueOutput {
    ListJudgeChallengeOpsQueueOutput {
        status: JUDGE_CHALLENGE_OPS_STATUS_PROXY_ERROR.to_string(),
        status_reason: reason_code.to_string(),
        count: 0,
        returned: 0,
        scanned: 0,
        skipped: 0,
        error_count: 0,
        summary: json!({
            "openCount": 0,
            "urgentCount": 0,
            "highPriorityCount": 0,
            "oldestOpenAgeMinutes": Value::Null,
            "stateCounts": {},
            "reviewStateCounts": {},
            "priorityLevelCounts": {},
            "slaBucketCounts": {},
            "reasonCodeCounts": {},
            "actionHintCounts": {},
        }),
        items: Vec::new(),
        errors: Vec::new(),
        filters: json!({}),
    }
}
