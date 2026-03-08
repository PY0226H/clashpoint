use chat_core::{JwtRuntimeConfig, JwtVerifyMetricsSnapshot};
use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct GetJwtLegacyRetirementGateOutput {
    pub implementation: String,
    pub legacy_fallback_enabled: bool,
    pub verify_attempt_total: u64,
    pub verify_success_total: u64,
    pub verify_error_total: u64,
    pub legacy_fallback_attempt_total: u64,
    pub legacy_fallback_success_total: u64,
    pub legacy_fallback_failure_total: u64,
    pub legacy_fallback_hit_rate: f64,
    pub verify_error_rate: f64,
    pub gate_ready: bool,
}

impl GetJwtLegacyRetirementGateOutput {
    pub fn from_runtime_and_metrics(
        runtime: JwtRuntimeConfig,
        metrics: JwtVerifyMetricsSnapshot,
    ) -> Self {
        let attempts = metrics.verify_attempt_total as f64;
        let fallback_attempts = metrics.legacy_fallback_attempt_total as f64;
        let legacy_fallback_hit_rate = if fallback_attempts > 0.0 {
            metrics.legacy_fallback_success_total as f64 / fallback_attempts
        } else {
            0.0
        };
        let verify_error_rate = if attempts > 0.0 {
            metrics.verify_error_total as f64 / attempts
        } else {
            0.0
        };
        // 退场门禁：已经关闭 fallback，或观测窗口内 fallback 成功命中为 0。
        let gate_ready =
            !runtime.legacy_fallback_enabled || metrics.legacy_fallback_success_total == 0;

        Self {
            implementation: runtime.implementation.to_string(),
            legacy_fallback_enabled: runtime.legacy_fallback_enabled,
            verify_attempt_total: metrics.verify_attempt_total,
            verify_success_total: metrics.verify_success_total,
            verify_error_total: metrics.verify_error_total,
            legacy_fallback_attempt_total: metrics.legacy_fallback_attempt_total,
            legacy_fallback_success_total: metrics.legacy_fallback_success_total,
            legacy_fallback_failure_total: metrics.legacy_fallback_failure_total,
            legacy_fallback_hit_rate,
            verify_error_rate,
            gate_ready,
        }
    }
}
