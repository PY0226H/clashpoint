use super::*;
use serde_json::{json, Value};

pub(super) const JUDGE_RUNTIME_READINESS_REASON_PROXY_FAILED: &str =
    "runtime_readiness_proxy_failed";

const JUDGE_RUNTIME_READINESS_CONTRACT_VERSION: &str = "ai-judge-runtime-readiness-v1";
const JUDGE_RUNTIME_READINESS_REASON_CONTRACT_VIOLATION: &str =
    "runtime_readiness_contract_violation";
const JUDGE_RUNTIME_READINESS_STATUS_PROXY_ERROR: &str = "proxy_error";

fn normalized_key(key: &str) -> String {
    key.chars()
        .filter(|c| *c != '_' && *c != '-')
        .flat_map(char::to_lowercase)
        .collect()
}

fn runtime_readiness_forbidden_key(key: &str) -> bool {
    matches!(
        normalized_key(key).as_str(),
        "apikey"
            | "secret"
            | "secretref"
            | "credential"
            | "provider"
            | "providerconfig"
            | "rawprompt"
            | "rawtrace"
            | "prompt"
            | "trace"
            | "traceid"
            | "internalauditpayload"
            | "privateaudit"
            | "auditpayload"
            | "artifactref"
            | "artifactrefs"
            | "objectkey"
            | "objectpath"
            | "objectstorelocator"
            | "objectstorepath"
            | "bucket"
            | "signedurl"
            | "endpoint"
            | "url"
            | "path"
    )
}

fn runtime_readiness_contains_forbidden_key(value: &Value) -> bool {
    match value {
        Value::Object(map) => map.iter().any(|(key, value)| {
            runtime_readiness_forbidden_key(key) || runtime_readiness_contains_forbidden_key(value)
        }),
        Value::Array(items) => items.iter().any(runtime_readiness_contains_forbidden_key),
        _ => false,
    }
}

fn required_object(payload: &Value, key: &str) -> Result<Value, &'static str> {
    payload
        .get(key)
        .filter(|value| value.is_object())
        .cloned()
        .ok_or(JUDGE_RUNTIME_READINESS_REASON_CONTRACT_VIOLATION)
}

fn required_array(payload: &Value, key: &str) -> Result<Vec<Value>, &'static str> {
    payload
        .get(key)
        .and_then(Value::as_array)
        .cloned()
        .ok_or(JUDGE_RUNTIME_READINESS_REASON_CONTRACT_VIOLATION)
}

fn required_string(payload: &Value, key: &str) -> Result<String, &'static str> {
    payload
        .get(key)
        .and_then(Value::as_str)
        .map(str::to_string)
        .ok_or(JUDGE_RUNTIME_READINESS_REASON_CONTRACT_VIOLATION)
}

fn validate_status(status: &str) -> Result<(), &'static str> {
    match status {
        "ready"
        | "watch"
        | "blocked"
        | "env_blocked"
        | "local_reference_only"
        | "not_configured" => Ok(()),
        _ => Err(JUDGE_RUNTIME_READINESS_REASON_CONTRACT_VIOLATION),
    }
}

fn validate_visibility_contract(visibility: &Value) -> Result<(), &'static str> {
    for flag in [
        "rawPromptVisible",
        "rawTraceVisible",
        "internalAuditPayloadVisible",
        "providerConfigVisible",
        "artifactRefsVisible",
        "officialVerdictSemanticsChanged",
    ] {
        if visibility.get(flag).and_then(Value::as_bool) != Some(false) {
            return Err(JUDGE_RUNTIME_READINESS_REASON_CONTRACT_VIOLATION);
        }
    }
    Ok(())
}

pub(super) fn build_judge_runtime_readiness_ops_output_from_payload(
    payload: Value,
) -> Result<GetJudgeRuntimeReadinessOpsOutput, &'static str> {
    let Some(object) = payload.as_object() else {
        return Err(JUDGE_RUNTIME_READINESS_REASON_CONTRACT_VIOLATION);
    };
    for key in [
        "version",
        "status",
        "statusReason",
        "summary",
        "releaseGate",
        "fairnessCalibration",
        "panelRuntime",
        "trustAndChallenge",
        "realEnv",
        "recommendedActions",
        "evidenceRefs",
        "visibilityContract",
        "cacheProfile",
    ] {
        if !object.contains_key(key) {
            return Err(JUDGE_RUNTIME_READINESS_REASON_CONTRACT_VIOLATION);
        }
    }
    if object.get("version").and_then(Value::as_str)
        != Some(JUDGE_RUNTIME_READINESS_CONTRACT_VERSION)
    {
        return Err(JUDGE_RUNTIME_READINESS_REASON_CONTRACT_VIOLATION);
    }

    let status = required_string(&payload, "status")?;
    validate_status(&status)?;
    let status_reason = required_string(&payload, "statusReason")?;
    let visibility_contract = required_object(&payload, "visibilityContract")?;
    validate_visibility_contract(&visibility_contract)?;

    let public_payload = json!({
        "summary": required_object(&payload, "summary")?,
        "releaseGate": required_object(&payload, "releaseGate")?,
        "fairnessCalibration": required_object(&payload, "fairnessCalibration")?,
        "panelRuntime": required_object(&payload, "panelRuntime")?,
        "trustAndChallenge": required_object(&payload, "trustAndChallenge")?,
        "realEnv": required_object(&payload, "realEnv")?,
        "recommendedActions": required_array(&payload, "recommendedActions")?,
        "evidenceRefs": required_array(&payload, "evidenceRefs")?,
        "visibilityContract": visibility_contract,
        "cacheProfile": required_object(&payload, "cacheProfile")?,
    });
    if runtime_readiness_contains_forbidden_key(&public_payload) {
        return Err(JUDGE_RUNTIME_READINESS_REASON_CONTRACT_VIOLATION);
    }

    Ok(GetJudgeRuntimeReadinessOpsOutput {
        version: JUDGE_RUNTIME_READINESS_CONTRACT_VERSION.to_string(),
        generated_at: payload
            .get("generatedAt")
            .and_then(Value::as_str)
            .map(str::to_string),
        status,
        status_reason,
        summary: public_payload["summary"].clone(),
        release_gate: public_payload["releaseGate"].clone(),
        fairness_calibration: public_payload["fairnessCalibration"].clone(),
        panel_runtime: public_payload["panelRuntime"].clone(),
        trust_and_challenge: public_payload["trustAndChallenge"].clone(),
        real_env: public_payload["realEnv"].clone(),
        recommended_actions: public_payload["recommendedActions"]
            .as_array()
            .cloned()
            .unwrap_or_default(),
        evidence_refs: public_payload["evidenceRefs"]
            .as_array()
            .cloned()
            .unwrap_or_default(),
        visibility_contract: public_payload["visibilityContract"].clone(),
        cache_profile: public_payload["cacheProfile"].clone(),
    })
}

pub(super) fn build_judge_runtime_readiness_ops_proxy_error_output(
    reason_code: &str,
) -> GetJudgeRuntimeReadinessOpsOutput {
    GetJudgeRuntimeReadinessOpsOutput {
        version: JUDGE_RUNTIME_READINESS_CONTRACT_VERSION.to_string(),
        generated_at: None,
        status: JUDGE_RUNTIME_READINESS_STATUS_PROXY_ERROR.to_string(),
        status_reason: reason_code.to_string(),
        summary: json!({}),
        release_gate: json!({}),
        fairness_calibration: json!({}),
        panel_runtime: json!({}),
        trust_and_challenge: json!({}),
        real_env: json!({}),
        recommended_actions: Vec::new(),
        evidence_refs: Vec::new(),
        visibility_contract: json!({
            "rawPromptVisible": false,
            "rawTraceVisible": false,
            "internalAuditPayloadVisible": false,
            "providerConfigVisible": false,
            "artifactRefsVisible": false,
            "officialVerdictSemanticsChanged": false,
        }),
        cache_profile: json!({}),
    }
}
