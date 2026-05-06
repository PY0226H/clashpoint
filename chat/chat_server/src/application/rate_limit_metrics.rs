use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::{
    collections::HashMap,
    sync::{
        atomic::{AtomicU64, Ordering},
        Mutex,
    },
};
use utoipa::ToSchema;

use crate::RateLimitDecision;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum RateLimitRuntimeOutcome {
    Redis,
    FallbackAfterRedisError,
    FallbackRedisDisabled,
}

#[derive(Debug, Default)]
pub(crate) struct RateLimitRuntimeMetrics {
    request_total: AtomicU64,
    allowed_total: AtomicU64,
    rejected_total: AtomicU64,
    redis_allowed_total: AtomicU64,
    redis_rejected_total: AtomicU64,
    fallback_allowed_total: AtomicU64,
    fallback_rejected_total: AtomicU64,
    redis_error_total: AtomicU64,
    redis_disabled_fallback_total: AtomicU64,
    near_limit_total: AtomicU64,
    scopes: Mutex<HashMap<String, RateLimitScopeRuntimeMetrics>>,
}

pub(crate) struct RateLimitRuntimeObservation<'a> {
    pub(crate) scope: &'a str,
    pub(crate) limit: u64,
    pub(crate) window_secs: u64,
    pub(crate) burst_limit: u64,
    pub(crate) outcome: RateLimitRuntimeOutcome,
    pub(crate) decision: &'a RateLimitDecision,
    pub(crate) observed_at_ms: i64,
}

#[derive(Debug, Clone, Default)]
struct RateLimitScopeRuntimeMetrics {
    limit: u64,
    window_secs: u64,
    burst_limit: u64,
    request_total: u64,
    allowed_total: u64,
    rejected_total: u64,
    fallback_total: u64,
    redis_error_total: u64,
    near_limit_total: u64,
    last_rejected_at_ms: Option<i64>,
    last_redis_error_at_ms: Option<i64>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct RateLimitGlobalMetricsOutput {
    pub request_total: u64,
    pub allowed_total: u64,
    pub rejected_total: u64,
    pub redis_allowed_total: u64,
    pub redis_rejected_total: u64,
    pub fallback_allowed_total: u64,
    pub fallback_rejected_total: u64,
    pub redis_error_total: u64,
    pub redis_disabled_fallback_total: u64,
    pub near_limit_total: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct RateLimitScopeMetricsOutput {
    pub scope: String,
    pub limit: u64,
    pub window_secs: u64,
    pub burst_limit: u64,
    pub request_total: u64,
    pub allowed_total: u64,
    pub rejected_total: u64,
    pub fallback_total: u64,
    pub redis_error_total: u64,
    pub near_limit_total: u64,
    pub last_rejected_at_ms: Option<i64>,
    pub last_redis_error_at_ms: Option<i64>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct GetRateLimitMetricsOutput {
    pub generated_at_ms: i64,
    pub global: RateLimitGlobalMetricsOutput,
    pub scopes: Vec<RateLimitScopeMetricsOutput>,
}

impl RateLimitRuntimeMetrics {
    pub(crate) fn observe(
        &self,
        scope: &str,
        limit: u64,
        window_secs: u64,
        burst_limit: u64,
        outcome: RateLimitRuntimeOutcome,
        decision: &RateLimitDecision,
    ) {
        self.observe_observation(RateLimitRuntimeObservation {
            scope,
            limit,
            window_secs,
            burst_limit,
            outcome,
            decision,
            observed_at_ms: now_epoch_ms(),
        });
    }

    pub(crate) fn observe_observation(&self, observation: RateLimitRuntimeObservation<'_>) {
        let scope = observation.scope;
        let limit = observation.limit;
        let window_secs = observation.window_secs;
        let burst_limit = observation.burst_limit;
        let outcome = observation.outcome;
        let decision = observation.decision;
        let now_ms = observation.observed_at_ms;

        self.request_total.fetch_add(1, Ordering::Relaxed);
        if decision.allowed {
            self.allowed_total.fetch_add(1, Ordering::Relaxed);
        } else {
            self.rejected_total.fetch_add(1, Ordering::Relaxed);
        }

        match outcome {
            RateLimitRuntimeOutcome::Redis => {
                if decision.allowed {
                    self.redis_allowed_total.fetch_add(1, Ordering::Relaxed);
                } else {
                    self.redis_rejected_total.fetch_add(1, Ordering::Relaxed);
                }
            }
            RateLimitRuntimeOutcome::FallbackAfterRedisError => {
                self.redis_error_total.fetch_add(1, Ordering::Relaxed);
                if decision.allowed {
                    self.fallback_allowed_total.fetch_add(1, Ordering::Relaxed);
                } else {
                    self.fallback_rejected_total.fetch_add(1, Ordering::Relaxed);
                }
            }
            RateLimitRuntimeOutcome::FallbackRedisDisabled => {
                self.redis_disabled_fallback_total
                    .fetch_add(1, Ordering::Relaxed);
                if decision.allowed {
                    self.fallback_allowed_total.fetch_add(1, Ordering::Relaxed);
                } else {
                    self.fallback_rejected_total.fetch_add(1, Ordering::Relaxed);
                }
            }
        }

        let near_limit = decision.allowed && limit > 0 && decision.remaining == 0;
        if near_limit {
            self.near_limit_total.fetch_add(1, Ordering::Relaxed);
        }

        let normalized_scope = normalize_scope(scope);
        let mut scopes = match self.scopes.lock() {
            Ok(v) => v,
            Err(poisoned) => poisoned.into_inner(),
        };
        let entry = scopes.entry(normalized_scope).or_default();
        entry.limit = limit;
        entry.window_secs = window_secs;
        entry.burst_limit = burst_limit;
        entry.request_total = entry.request_total.saturating_add(1);
        if decision.allowed {
            entry.allowed_total = entry.allowed_total.saturating_add(1);
        } else {
            entry.rejected_total = entry.rejected_total.saturating_add(1);
            entry.last_rejected_at_ms = Some(now_ms);
        }
        match outcome {
            RateLimitRuntimeOutcome::Redis => {}
            RateLimitRuntimeOutcome::FallbackAfterRedisError => {
                entry.fallback_total = entry.fallback_total.saturating_add(1);
                entry.redis_error_total = entry.redis_error_total.saturating_add(1);
                entry.last_redis_error_at_ms = Some(now_ms);
            }
            RateLimitRuntimeOutcome::FallbackRedisDisabled => {
                entry.fallback_total = entry.fallback_total.saturating_add(1);
            }
        }
        if near_limit {
            entry.near_limit_total = entry.near_limit_total.saturating_add(1);
        }
    }

    pub(crate) fn snapshot(&self) -> GetRateLimitMetricsOutput {
        self.snapshot_at_ms(now_epoch_ms())
    }

    pub(crate) fn snapshot_at_ms(&self, generated_at_ms: i64) -> GetRateLimitMetricsOutput {
        let scopes = match self.scopes.lock() {
            Ok(v) => v,
            Err(poisoned) => poisoned.into_inner(),
        };
        let mut scopes: Vec<_> = scopes
            .iter()
            .map(|(scope, metrics)| RateLimitScopeMetricsOutput {
                scope: scope.clone(),
                limit: metrics.limit,
                window_secs: metrics.window_secs,
                burst_limit: metrics.burst_limit,
                request_total: metrics.request_total,
                allowed_total: metrics.allowed_total,
                rejected_total: metrics.rejected_total,
                fallback_total: metrics.fallback_total,
                redis_error_total: metrics.redis_error_total,
                near_limit_total: metrics.near_limit_total,
                last_rejected_at_ms: metrics.last_rejected_at_ms,
                last_redis_error_at_ms: metrics.last_redis_error_at_ms,
            })
            .collect();
        scopes.sort_by(|a, b| a.scope.cmp(&b.scope));

        GetRateLimitMetricsOutput {
            generated_at_ms,
            global: RateLimitGlobalMetricsOutput {
                request_total: self.request_total.load(Ordering::Relaxed),
                allowed_total: self.allowed_total.load(Ordering::Relaxed),
                rejected_total: self.rejected_total.load(Ordering::Relaxed),
                redis_allowed_total: self.redis_allowed_total.load(Ordering::Relaxed),
                redis_rejected_total: self.redis_rejected_total.load(Ordering::Relaxed),
                fallback_allowed_total: self.fallback_allowed_total.load(Ordering::Relaxed),
                fallback_rejected_total: self.fallback_rejected_total.load(Ordering::Relaxed),
                redis_error_total: self.redis_error_total.load(Ordering::Relaxed),
                redis_disabled_fallback_total: self
                    .redis_disabled_fallback_total
                    .load(Ordering::Relaxed),
                near_limit_total: self.near_limit_total.load(Ordering::Relaxed),
            },
            scopes,
        }
    }
}

fn normalize_scope(scope: &str) -> String {
    let normalized = scope.trim();
    if normalized.is_empty() || normalized.len() > 128 {
        return "unknown".to_string();
    }
    normalized.to_string()
}

fn now_epoch_ms() -> i64 {
    Utc::now().timestamp_millis().max(0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rate_limit_runtime_metrics_should_snapshot_global_and_scope_outcomes() {
        let metrics = RateLimitRuntimeMetrics::default();
        metrics.observe_observation(RateLimitRuntimeObservation {
            scope: " judge_job_request ",
            limit: 10,
            window_secs: 300,
            burst_limit: 3,
            outcome: RateLimitRuntimeOutcome::Redis,
            decision: &RateLimitDecision {
                allowed: true,
                limit: 10,
                remaining: 0,
                reset_at_epoch_secs: 1_700,
            },
            observed_at_ms: 1_700_000,
        });
        metrics.observe_observation(RateLimitRuntimeObservation {
            scope: "judge_job_request",
            limit: 10,
            window_secs: 300,
            burst_limit: 3,
            outcome: RateLimitRuntimeOutcome::FallbackAfterRedisError,
            decision: &RateLimitDecision {
                allowed: false,
                limit: 10,
                remaining: 0,
                reset_at_epoch_secs: 1_701,
            },
            observed_at_ms: 1_700_500,
        });
        metrics.observe_observation(RateLimitRuntimeObservation {
            scope: " ",
            limit: 5,
            window_secs: 60,
            burst_limit: 1,
            outcome: RateLimitRuntimeOutcome::FallbackRedisDisabled,
            decision: &RateLimitDecision {
                allowed: true,
                limit: 5,
                remaining: 4,
                reset_at_epoch_secs: 1_702,
            },
            observed_at_ms: 1_701_000,
        });

        assert_eq!(
            metrics.snapshot_at_ms(1_702_000),
            GetRateLimitMetricsOutput {
                generated_at_ms: 1_702_000,
                global: RateLimitGlobalMetricsOutput {
                    request_total: 3,
                    allowed_total: 2,
                    rejected_total: 1,
                    redis_allowed_total: 1,
                    redis_rejected_total: 0,
                    fallback_allowed_total: 1,
                    fallback_rejected_total: 1,
                    redis_error_total: 1,
                    redis_disabled_fallback_total: 1,
                    near_limit_total: 1,
                },
                scopes: vec![
                    RateLimitScopeMetricsOutput {
                        scope: "judge_job_request".to_string(),
                        limit: 10,
                        window_secs: 300,
                        burst_limit: 3,
                        request_total: 2,
                        allowed_total: 1,
                        rejected_total: 1,
                        fallback_total: 1,
                        redis_error_total: 1,
                        near_limit_total: 1,
                        last_rejected_at_ms: Some(1_700_500),
                        last_redis_error_at_ms: Some(1_700_500),
                    },
                    RateLimitScopeMetricsOutput {
                        scope: "unknown".to_string(),
                        limit: 5,
                        window_secs: 60,
                        burst_limit: 1,
                        request_total: 1,
                        allowed_total: 1,
                        rejected_total: 0,
                        fallback_total: 1,
                        redis_error_total: 0,
                        near_limit_total: 0,
                        last_rejected_at_ms: None,
                        last_redis_error_at_ms: None,
                    },
                ],
            }
        );
    }

    #[test]
    fn rate_limit_runtime_metrics_should_not_treat_disabled_limit_as_near_limit() {
        let metrics = RateLimitRuntimeMetrics::default();
        metrics.observe_observation(RateLimitRuntimeObservation {
            scope: "disabled_scope",
            limit: 0,
            window_secs: 60,
            burst_limit: 0,
            outcome: RateLimitRuntimeOutcome::Redis,
            decision: &RateLimitDecision {
                allowed: true,
                limit: 0,
                remaining: 0,
                reset_at_epoch_secs: 1,
            },
            observed_at_ms: 1_000,
        });

        let snapshot = metrics.snapshot_at_ms(2_000);
        assert_eq!(snapshot.global.near_limit_total, 0);
        assert_eq!(snapshot.scopes[0].near_limit_total, 0);
    }
}
