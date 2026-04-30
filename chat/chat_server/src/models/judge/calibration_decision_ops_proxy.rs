use super::*;
use crate::models::OpsPermission;
use reqwest::Client;
use serde_json::{json, Value};
use sha1::{Digest, Sha1};
use std::time::Duration;

const CALIBRATION_DECISION_LOG_VERSION: &str = "ai-judge-fairness-calibration-decision-log-v1";
const CALIBRATION_DECISION_STATUS_ACCEPTED: &str = "accepted";
const CALIBRATION_DECISION_STATUS_PROXY_ERROR: &str = "proxy_error";
const CALIBRATION_DECISION_REASON_ACCEPTED: &str = "calibration_decision_logged";
const CALIBRATION_DECISION_REASON_PROXY_FAILED: &str = "calibration_decision_proxy_failed";
const CALIBRATION_DECISION_REASON_CONTRACT_VIOLATION: &str =
    "calibration_decision_contract_violation";

fn normalized_key(key: &str) -> String {
    key.chars()
        .filter(|c| *c != '_' && *c != '-')
        .flat_map(char::to_lowercase)
        .collect()
}

fn calibration_decision_forbidden_key(key: &str) -> bool {
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

fn calibration_decision_contains_forbidden_key(value: &Value) -> bool {
    match value {
        Value::Object(map) => map.iter().any(|(key, value)| {
            calibration_decision_forbidden_key(key)
                || calibration_decision_contains_forbidden_key(value)
        }),
        Value::Array(items) => items
            .iter()
            .any(calibration_decision_contains_forbidden_key),
        _ => false,
    }
}

fn build_ai_judge_calibration_decisions_url(base_url: &str, path: &str) -> String {
    let base = base_url.trim_end_matches('/');
    let path = path.trim_start_matches('/');
    format!("{base}/{path}")
}

fn normalize_calibration_token(value: &str) -> String {
    value.trim().to_string()
}

fn normalize_calibration_decision(value: &str) -> Result<String, AppError> {
    let decision = value.trim().to_lowercase();
    match decision.as_str() {
        "accept_for_review" | "reject" | "defer" | "request_more_evidence" => Ok(decision),
        _ => Err(AppError::ValidationError(
            "invalid_calibration_decision".to_string(),
        )),
    }
}

fn normalize_calibration_reason_code(value: &str) -> Result<String, AppError> {
    let reason_code = value.trim().to_lowercase();
    match reason_code.as_str() {
        "calibration_real_samples_missing"
        | "calibration_shadow_drift"
        | "calibration_release_gate_blocked"
        | "calibration_local_reference_only"
        | "calibration_manual_reject" => Ok(reason_code),
        _ => Err(AppError::ValidationError(
            "invalid_calibration_decision_reason_code".to_string(),
        )),
    }
}

fn stable_decision_id(user_id: i64, idempotency_key: Option<&str>, payload: &Value) -> String {
    let mut hasher = Sha1::new();
    hasher.update(user_id.to_string().as_bytes());
    hasher.update(b":");
    if let Some(key) = idempotency_key {
        hasher.update(key.as_bytes());
    } else {
        hasher.update(payload.to_string().as_bytes());
    }
    format!("ops-calibration-decision-{:x}", hasher.finalize())
}

fn build_calibration_decision_payload(
    input: CreateJudgeCalibrationDecisionOpsInput,
    user: &chat_core::User,
    idempotency_key: Option<&str>,
) -> Result<Value, AppError> {
    let source_recommendation_id = normalize_calibration_token(&input.source_recommendation_id);
    if source_recommendation_id.is_empty() {
        return Err(AppError::ValidationError(
            "missing_calibration_decision_source_recommendation_id".to_string(),
        ));
    }
    let policy_version = input
        .policy_version
        .as_deref()
        .map(normalize_calibration_token)
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| "active".to_string());
    let decision = normalize_calibration_decision(&input.decision)?;
    let reason_code = normalize_calibration_reason_code(&input.reason_code)?;
    let local_reference_only = input.local_reference_only.unwrap_or(false);
    let environment_mode = input
        .environment_mode
        .as_deref()
        .map(normalize_calibration_token)
        .filter(|value| !value.is_empty());
    let mut payload = json!({
        "sourceRecommendationId": source_recommendation_id,
        "policyVersion": policy_version,
        "decision": decision,
        "reasonCode": reason_code,
        "evidenceRefs": input.evidence_refs,
        "localReferenceOnly": local_reference_only,
        "actor": {
            "id": user.id.to_string(),
            "type": "ops"
        }
    });
    if let Some(environment_mode) = environment_mode {
        payload["environmentMode"] = json!(environment_mode);
    }
    payload["decisionId"] = json!(stable_decision_id(user.id, idempotency_key, &payload));
    if calibration_decision_contains_forbidden_key(&payload) {
        return Err(AppError::ValidationError(
            "calibration_decision_forbidden_key".to_string(),
        ));
    }
    Ok(payload)
}

async fn fetch_ai_judge_calibration_decision_payload(
    base_url: &str,
    path: &str,
    timeout_ms: u64,
    internal_key: &str,
    payload: Value,
) -> Result<Value, &'static str> {
    let url = build_ai_judge_calibration_decisions_url(base_url, path);
    let client = Client::builder()
        .timeout(Duration::from_millis(timeout_ms.max(1)))
        .build()
        .map_err(|_| "calibration_decision_http_client_failed")?;
    let response = client
        .post(url)
        .header("x-ai-internal-key", internal_key)
        .json(&payload)
        .send()
        .await
        .map_err(|_| "calibration_decision_request_failed")?;
    if !response.status().is_success() {
        return Err("calibration_decision_bad_status");
    }
    response
        .json::<Value>()
        .await
        .map_err(|_| "calibration_decision_bad_json")
}

fn required_object(payload: &Value, key: &str) -> Result<Value, &'static str> {
    payload
        .get(key)
        .filter(|value| value.is_object())
        .cloned()
        .ok_or(CALIBRATION_DECISION_REASON_CONTRACT_VIOLATION)
}

fn validate_visibility_contract(visibility: &Value) -> Result<(), &'static str> {
    for flag in [
        "rawPromptVisible",
        "rawTraceVisible",
        "internalAuditPayloadVisible",
        "providerConfigVisible",
        "artifactRefsVisible",
        "officialVerdictSemanticsChanged",
        "autoPublishAllowed",
        "autoActivateAllowed",
    ] {
        if visibility.get(flag).and_then(Value::as_bool) != Some(false) {
            return Err(CALIBRATION_DECISION_REASON_CONTRACT_VIOLATION);
        }
    }
    Ok(())
}

fn build_calibration_decision_ops_output_from_payload(
    payload: Value,
) -> Result<CreateJudgeCalibrationDecisionOpsOutput, &'static str> {
    if payload.get("version").and_then(Value::as_str) != Some(CALIBRATION_DECISION_LOG_VERSION) {
        return Err(CALIBRATION_DECISION_REASON_CONTRACT_VIOLATION);
    }
    let entry = required_object(&payload, "entry")?;
    let decision_log = required_object(&payload, "decisionLog")?;
    let visibility_contract = required_object(&payload, "visibilityContract")?;
    validate_visibility_contract(&visibility_contract)?;
    let public_payload = json!({
        "entry": entry,
        "decisionLog": decision_log,
        "visibilityContract": visibility_contract,
    });
    if calibration_decision_contains_forbidden_key(&public_payload) {
        return Err(CALIBRATION_DECISION_REASON_CONTRACT_VIOLATION);
    }
    Ok(CreateJudgeCalibrationDecisionOpsOutput {
        version: CALIBRATION_DECISION_LOG_VERSION.to_string(),
        generated_at: payload
            .get("generatedAt")
            .and_then(Value::as_str)
            .map(str::to_string),
        status: CALIBRATION_DECISION_STATUS_ACCEPTED.to_string(),
        status_reason: CALIBRATION_DECISION_REASON_ACCEPTED.to_string(),
        entry: public_payload["entry"].clone(),
        decision_log: public_payload["decisionLog"].clone(),
        visibility_contract: public_payload["visibilityContract"].clone(),
    })
}

fn build_calibration_decision_ops_proxy_error_output(
    reason_code: &str,
) -> CreateJudgeCalibrationDecisionOpsOutput {
    CreateJudgeCalibrationDecisionOpsOutput {
        version: CALIBRATION_DECISION_LOG_VERSION.to_string(),
        generated_at: None,
        status: CALIBRATION_DECISION_STATUS_PROXY_ERROR.to_string(),
        status_reason: reason_code.to_string(),
        entry: json!({}),
        decision_log: json!({}),
        visibility_contract: json!({
            "rawPromptVisible": false,
            "rawTraceVisible": false,
            "internalAuditPayloadVisible": false,
            "providerConfigVisible": false,
            "artifactRefsVisible": false,
            "officialVerdictSemanticsChanged": false,
            "autoPublishAllowed": false,
            "autoActivateAllowed": false,
        }),
    }
}

impl AppState {
    pub async fn create_judge_calibration_decision_by_owner(
        &self,
        user: &chat_core::User,
        input: CreateJudgeCalibrationDecisionOpsInput,
        idempotency_key: Option<&str>,
    ) -> Result<CreateJudgeCalibrationDecisionOpsOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeReview)
            .await?;
        let request_payload = build_calibration_decision_payload(input, user, idempotency_key)?;
        let payload = match fetch_ai_judge_calibration_decision_payload(
            &self.config.ai_judge.service_base_url,
            &self.config.ai_judge.calibration_decisions_path,
            self.config.ai_judge.calibration_decisions_timeout_ms,
            &self.config.ai_judge.internal_key,
            request_payload,
        )
        .await
        {
            Ok(payload) => payload,
            Err(_) => {
                return Ok(build_calibration_decision_ops_proxy_error_output(
                    CALIBRATION_DECISION_REASON_PROXY_FAILED,
                ));
            }
        };
        match build_calibration_decision_ops_output_from_payload(payload) {
            Ok(output) => Ok(output),
            Err(reason) => Ok(build_calibration_decision_ops_proxy_error_output(reason)),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn calibration_decision_url_should_join_base_and_path_once() {
        assert_eq!(
            build_ai_judge_calibration_decisions_url(
                "http://127.0.0.1:9000/",
                "/internal/judge/fairness/policy-calibration-decisions",
            ),
            "http://127.0.0.1:9000/internal/judge/fairness/policy-calibration-decisions"
        );
    }

    #[test]
    fn calibration_decision_output_should_reject_forbidden_keys() {
        let payload = json!({
            "version": CALIBRATION_DECISION_LOG_VERSION,
            "generatedAt": "2026-04-30T00:00:00Z",
            "entry": {
                "decisionId": "decision-1",
                "rawTrace": "hidden"
            },
            "decisionLog": {},
            "visibilityContract": {
                "rawPromptVisible": false,
                "rawTraceVisible": false,
                "internalAuditPayloadVisible": false,
                "providerConfigVisible": false,
                "artifactRefsVisible": false,
                "officialVerdictSemanticsChanged": false,
                "autoPublishAllowed": false,
                "autoActivateAllowed": false
            }
        });

        assert_eq!(
            build_calibration_decision_ops_output_from_payload(payload).unwrap_err(),
            CALIBRATION_DECISION_REASON_CONTRACT_VIOLATION
        );
    }
}
