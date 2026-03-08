use std::time::Duration;

use tokio::{
    sync::mpsc::UnboundedReceiver,
    time::{sleep, MissedTickBehavior},
};
use tracing::{debug, warn};

use crate::{models::JudgeDispatchTrigger, AppState};

const DEBATE_SESSION_WORKER_INTERVAL_SECS: u64 = 2;
const DEBATE_SESSION_WORKER_BATCH_SIZE: i64 = 200;
const OPS_OBSERVABILITY_WORKER_INTERVAL_SECS: u64 = 30;

pub(crate) fn spawn_background_workers(
    state: AppState,
    dispatch_trigger_rx: UnboundedReceiver<JudgeDispatchTrigger>,
) {
    spawn_debate_session_worker(state.clone());
    spawn_ai_judge_dispatch_worker(state.clone(), dispatch_trigger_rx);
    spawn_ops_observability_alert_worker(state.clone());
    spawn_ai_judge_alert_outbox_bridge_worker(state);
}

fn spawn_debate_session_worker(state: AppState) {
    tokio::spawn(async move {
        loop {
            if let Err(err) = state
                .advance_debate_sessions(DEBATE_SESSION_WORKER_BATCH_SIZE)
                .await
            {
                warn!("debate session worker tick failed: {}", err);
            } else {
                debug!("debate session worker tick success");
            }
            sleep(Duration::from_secs(DEBATE_SESSION_WORKER_INTERVAL_SECS)).await;
        }
    });
}

async fn run_ai_judge_dispatch_tick(
    state: &AppState,
    trigger_source: &str,
    trigger_job_id: Option<i64>,
) {
    if state.config.ai_judge.dispatch_enabled {
        match state.dispatch_pending_judge_jobs_once().await {
            Ok(report) => {
                debug!(
                    trigger_source,
                    trigger_job_id,
                    claimed = report.claimed,
                    dispatched = report.dispatched,
                    failed = report.failed,
                    marked_failed = report.marked_failed,
                    timed_out_failed = report.timed_out_failed,
                    terminal_failed = report.terminal_failed,
                    retryable_failed = report.retryable_failed,
                    failed_contract = report.failed_contract,
                    failed_http_4xx = report.failed_http_4xx,
                    failed_http_429 = report.failed_http_429,
                    failed_http_5xx = report.failed_http_5xx,
                    failed_network = report.failed_network,
                    failed_internal = report.failed_internal,
                    "ai judge dispatch worker tick success"
                );
            }
            Err(err) => {
                state.observe_dispatch_worker_error();
                warn!(
                    trigger_source,
                    trigger_job_id, "ai judge dispatch worker tick failed: {}", err
                );
            }
        }
    }
}

fn spawn_ai_judge_dispatch_worker(
    state: AppState,
    mut dispatch_trigger_rx: UnboundedReceiver<JudgeDispatchTrigger>,
) {
    tokio::spawn(async move {
        let mut ticker = tokio::time::interval(Duration::from_secs(
            state.config.ai_judge.dispatch_interval_secs.max(1),
        ));
        ticker.set_missed_tick_behavior(MissedTickBehavior::Delay);
        let _ = ticker.tick().await;
        loop {
            tokio::select! {
                _ = ticker.tick() => {
                    run_ai_judge_dispatch_tick(&state, "polling", None).await;
                }
                maybe_trigger = dispatch_trigger_rx.recv() => {
                    match maybe_trigger {
                        Some(trigger) => {
                            run_ai_judge_dispatch_tick(&state, trigger.source, Some(trigger.job_id)).await;
                        }
                        None => {
                            warn!("judge dispatch trigger channel closed, fallback to polling only");
                            sleep(Duration::from_secs(1)).await;
                        }
                    }
                }
            }
        }
    });
}

fn spawn_ops_observability_alert_worker(state: AppState) {
    tokio::spawn(async move {
        loop {
            match state.evaluate_ops_observability_alerts_once().await {
                Ok(report) => {
                    debug!(
                        workspaces_scanned = report.workspaces_scanned,
                        alerts_raised = report.alerts_raised,
                        alerts_cleared = report.alerts_cleared,
                        alerts_suppressed = report.alerts_suppressed,
                        "ops observability alert worker tick success"
                    );
                }
                Err(err) => warn!("ops observability alert worker tick failed: {}", err),
            }
            sleep(Duration::from_secs(OPS_OBSERVABILITY_WORKER_INTERVAL_SECS)).await;
        }
    });
}

fn spawn_ai_judge_alert_outbox_bridge_worker(state: AppState) {
    if !state.config.ai_judge.alert_outbox_bridge_enabled {
        return;
    }
    tokio::spawn(async move {
        loop {
            match state.bridge_ai_judge_alert_outbox_once().await {
                Ok(report) => {
                    debug!(
                        fetched = report.fetched,
                        delivered = report.delivered,
                        delivery_failed = report.delivery_failed,
                        callback_failed = report.callback_failed,
                        skipped_duplicate = report.skipped_duplicate,
                        "ai judge alert outbox bridge worker tick success"
                    );
                }
                Err(err) => warn!("ai judge alert outbox bridge worker tick failed: {}", err),
            }
            sleep(Duration::from_secs(
                state.config.ai_judge.alert_outbox_poll_interval_secs.max(1),
            ))
            .await;
        }
    });
}
