use super::*;
use reqwest::Client;
use std::collections::HashMap;
use tracing::warn;

impl AppState {
    pub async fn dispatch_pending_judge_jobs_once(
        &self,
    ) -> Result<JudgeDispatchTickReport, AppError> {
        let timed_out_failed = self.mark_timed_out_dispatch_jobs_failed().await?;
        let jobs = self.claim_pending_dispatch_jobs().await?;
        let mut report = JudgeDispatchTickReport {
            timed_out_failed,
            claimed: jobs.len(),
            ..Default::default()
        };

        for job in jobs.into_iter() {
            let payload = match self.load_dispatch_payload(&job).await {
                Ok(v) => v,
                Err(err) => {
                    report.failed += 1;
                    report.retryable_failed += 1;
                    report.failed_internal += 1;
                    let coded_msg = coded_error_message(
                        DispatchFailureCode::PayloadBuildFailed,
                        &err.to_string(),
                    );
                    if self
                        .mark_dispatch_failure(job.id, job.dispatch_attempts, &coded_msg)
                        .await?
                    {
                        report.marked_failed += 1;
                    }
                    continue;
                }
            };
            match self.send_dispatch_request(&payload).await {
                Ok(_) => {
                    self.mark_dispatch_sent(job.id).await?;
                    report.dispatched += 1;
                }
                Err(err) => {
                    report.failed += 1;
                    if err.terminal {
                        report.terminal_failed += 1;
                        if self
                            .mark_dispatch_terminal_failure(job.id, &err.message)
                            .await?
                        {
                            report.marked_failed += 1;
                        }
                    } else if self
                        .mark_dispatch_failure(job.id, job.dispatch_attempts, &err.message)
                        .await?
                    {
                        report.retryable_failed += 1;
                        report.marked_failed += 1;
                    } else {
                        report.retryable_failed += 1;
                    }
                    match err.code {
                        DispatchFailureCode::ResponseAcceptedFalse
                        | DispatchFailureCode::ResponseJobIdMismatch => report.failed_contract += 1,
                        DispatchFailureCode::Http4xx => report.failed_http_4xx += 1,
                        DispatchFailureCode::Http429 => report.failed_http_429 += 1,
                        DispatchFailureCode::Http5xx
                        | DispatchFailureCode::HttpUnexpectedStatus => report.failed_http_5xx += 1,
                        DispatchFailureCode::NetworkSendFailed => report.failed_network += 1,
                        DispatchFailureCode::BuildClientFailed
                        | DispatchFailureCode::PayloadBuildFailed => report.failed_internal += 1,
                    }
                }
            }
        }

        self.observe_dispatch_tick_success(&report);
        Ok(report)
    }

    pub fn get_judge_dispatch_metrics(&self) -> GetJudgeDispatchMetricsOutput {
        self.dispatch_metrics.snapshot()
    }

    pub(crate) fn observe_dispatch_worker_error(&self) {
        self.dispatch_metrics.observe_tick_error();
    }

    fn observe_dispatch_tick_success(&self, report: &JudgeDispatchTickReport) {
        self.dispatch_metrics.observe_tick_success(report);
    }

    async fn mark_timed_out_dispatch_jobs_failed(&self) -> Result<usize, AppError> {
        let max_attempts = self.config.ai_judge.dispatch_max_attempts.max(1);
        let rows_affected = sqlx::query(
            r#"
            UPDATE judge_jobs j
            SET status = 'failed',
                error_message = COALESCE(
                    NULLIF(j.error_message, ''),
                    format(
                        'dispatch callback timeout after %s attempts',
                        j.dispatch_attempts::text
                    )
                ),
                finished_at = NOW(),
                dispatch_locked_until = NULL,
                updated_at = NOW()
            WHERE j.status = 'running'
              AND NOT EXISTS (
                SELECT 1
                FROM judge_reports r
                WHERE r.job_id = j.id
              )
              AND j.dispatch_attempts >= $1
              AND j.dispatch_locked_until IS NOT NULL
              AND j.dispatch_locked_until <= NOW()
            "#,
        )
        .bind(max_attempts)
        .execute(&self.pool)
        .await?
        .rows_affected() as usize;
        Ok(rows_affected)
    }

    async fn claim_pending_dispatch_jobs(&self) -> Result<Vec<PendingDispatchJob>, AppError> {
        let max_attempts = self.config.ai_judge.dispatch_max_attempts.max(1);
        let batch_size = self.config.ai_judge.dispatch_batch_size.max(1);
        let lock_secs = self.config.ai_judge.dispatch_lock_secs.max(1);
        let rows = sqlx::query_as(
            r#"
            WITH due AS (
                SELECT j.id
                FROM judge_jobs j
                WHERE j.status = 'running'
                  AND NOT EXISTS (
                    SELECT 1
                    FROM judge_reports r
                    WHERE r.job_id = j.id
                  )
                  AND (j.dispatch_locked_until IS NULL OR j.dispatch_locked_until <= NOW())
                  AND j.dispatch_attempts < $1
                ORDER BY j.requested_at ASC
                LIMIT $2
                FOR UPDATE SKIP LOCKED
            )
            UPDATE judge_jobs j
            SET dispatch_attempts = j.dispatch_attempts + 1,
                last_dispatch_at = NOW(),
                dispatch_locked_until = NOW() + ($3::bigint * INTERVAL '1 second'),
                updated_at = NOW()
            FROM due
            WHERE j.id = due.id
            RETURNING
                j.id,
                j.ws_id,
                j.session_id,
                j.requested_by,
                j.style_mode,
                j.rejudge_triggered,
                j.requested_at,
                j.dispatch_attempts
            "#,
        )
        .bind(max_attempts)
        .bind(batch_size)
        .bind(lock_secs)
        .fetch_all(&self.pool)
        .await?;
        Ok(rows)
    }

    pub(super) async fn load_dispatch_payload(
        &self,
        job: &PendingDispatchJob,
    ) -> Result<AiJudgeDispatchRequest, AppError> {
        let session_topic: SessionTopicRow = sqlx::query_as(
            r#"
            SELECT
                s.status,
                s.scheduled_start_at,
                s.actual_start_at,
                s.end_at,
                t.title,
                t.description,
                t.category,
                t.stance_pro,
                t.stance_con,
                t.context_seed
            FROM debate_sessions s
            JOIN debate_topics t ON t.id = s.topic_id
            WHERE s.id = $1 AND s.ws_id = $2
            "#,
        )
        .bind(job.session_id)
        .bind(job.ws_id)
        .fetch_optional(&self.pool)
        .await?
        .ok_or_else(|| {
            AppError::NotFound(format!(
                "dispatch session {} in workspace {}",
                job.session_id, job.ws_id
            ))
        })?;

        let mut messages: Vec<SessionMessageRow> = sqlx::query_as(
            r#"
            SELECT id, user_id, side, content, created_at
            FROM session_messages
            WHERE session_id = $1
            ORDER BY id DESC
            LIMIT $2
            "#,
        )
        .bind(job.session_id)
        .bind(DISPATCH_MESSAGE_WINDOW_LIMIT)
        .fetch_all(&self.pool)
        .await?;
        messages.reverse();

        let mut speaker_aliases: HashMap<i64, String> = HashMap::new();
        let mut speaker_seq: u32 = 1;
        let mut dispatch_messages = Vec::with_capacity(messages.len());
        for v in messages.into_iter() {
            let speaker_tag = speaker_aliases
                .entry(v.user_id)
                .or_insert_with(|| {
                    let alias = format!("speaker-{speaker_seq}");
                    speaker_seq = speaker_seq.saturating_add(1);
                    alias
                })
                .clone();
            dispatch_messages.push(AiJudgeDispatchMessage {
                message_id: v.id as u64,
                speaker_tag,
                side: v.side,
                content: v.content,
                created_at: v.created_at,
            });
        }

        Ok(AiJudgeDispatchRequest {
            job: AiJudgeDispatchJob {
                job_id: job.id as u64,
                ws_id: job.ws_id as u64,
                session_id: job.session_id as u64,
                requested_by: job.requested_by as u64,
                style_mode: job.style_mode.clone(),
                rejudge_triggered: job.rejudge_triggered,
                requested_at: job.requested_at,
            },
            session: AiJudgeDispatchSession {
                status: session_topic.status,
                scheduled_start_at: session_topic.scheduled_start_at,
                actual_start_at: session_topic.actual_start_at,
                end_at: session_topic.end_at,
            },
            topic: AiJudgeDispatchTopic {
                title: session_topic.title,
                description: session_topic.description,
                category: session_topic.category,
                stance_pro: session_topic.stance_pro,
                stance_con: session_topic.stance_con,
                context_seed: session_topic.context_seed,
            },
            messages: dispatch_messages,
            message_window_size: DISPATCH_MESSAGE_WINDOW_LIMIT,
            rubric_version: "v1-logic-evidence-rebuttal-clarity".to_string(),
        })
    }

    async fn send_dispatch_request(
        &self,
        payload: &AiJudgeDispatchRequest,
    ) -> Result<(), DispatchSendError> {
        let url = build_dispatch_url(
            &self.config.ai_judge.service_base_url,
            &self.config.ai_judge.dispatch_path,
        );
        let client = Client::builder()
            .timeout(std::time::Duration::from_millis(
                self.config.ai_judge.dispatch_timeout_ms.max(1),
            ))
            .build()
            .map_err(|e| {
                DispatchSendError::terminal(
                    DispatchFailureCode::BuildClientFailed,
                    coded_error_message(
                        DispatchFailureCode::BuildClientFailed,
                        &format!("build dispatch client failed: {e}"),
                    ),
                )
            })?;
        let resp = client
            .post(&url)
            .header("x-ai-internal-key", &self.config.ai_judge.internal_key)
            .json(payload)
            .send()
            .await
            .map_err(|e| {
                DispatchSendError::retryable(
                    DispatchFailureCode::NetworkSendFailed,
                    coded_error_message(
                        DispatchFailureCode::NetworkSendFailed,
                        &format!("dispatch request io failed: {e}"),
                    ),
                )
            })?;
        if resp.status().is_success() {
            let body = resp.text().await.unwrap_or_default();
            if let Err(err) = validate_dispatch_response(&body, payload.job.job_id) {
                let (code, msg) = match err {
                    DispatchResponseViolation::AcceptedFalse { status } => (
                        DispatchFailureCode::ResponseAcceptedFalse,
                        format!("dispatch response rejected: accepted=false, status={status}"),
                    ),
                    DispatchResponseViolation::JobIdMismatch { expected, got } => (
                        DispatchFailureCode::ResponseJobIdMismatch,
                        format!(
                            "dispatch response job_id mismatch: expected={}, got={}",
                            expected, got
                        ),
                    ),
                };
                return Err(DispatchSendError::terminal(
                    code,
                    coded_error_message(code, &msg),
                ));
            }
            Ok(())
        } else {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            let message = format!("dispatch request failed: status={}, body={}", status, body);
            if status == reqwest::StatusCode::TOO_MANY_REQUESTS {
                let code = DispatchFailureCode::Http429;
                Err(DispatchSendError::retryable(
                    code,
                    coded_error_message(code, &message),
                ))
            } else if status.is_client_error() {
                let code = DispatchFailureCode::Http4xx;
                Err(DispatchSendError::terminal(
                    code,
                    coded_error_message(code, &message),
                ))
            } else if status.is_server_error() {
                let code = DispatchFailureCode::Http5xx;
                Err(DispatchSendError::retryable(
                    code,
                    coded_error_message(code, &message),
                ))
            } else {
                let code = DispatchFailureCode::HttpUnexpectedStatus;
                Err(DispatchSendError::retryable(
                    code,
                    coded_error_message(code, &message),
                ))
            }
        }
    }

    async fn mark_dispatch_sent(&self, job_id: i64) -> Result<(), AppError> {
        let callback_wait_secs = self.config.ai_judge.dispatch_callback_wait_secs.max(1);
        sqlx::query(
            r#"
            UPDATE judge_jobs
            SET started_at = COALESCE(started_at, NOW()),
                error_message = NULL,
                dispatch_locked_until = NOW() + ($2::bigint * INTERVAL '1 second'),
                updated_at = NOW()
            WHERE id = $1 AND status = 'running'
            "#,
        )
        .bind(job_id)
        .bind(callback_wait_secs)
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    async fn mark_dispatch_failure(
        &self,
        job_id: i64,
        dispatch_attempts: i32,
        err_msg: &str,
    ) -> Result<bool, AppError> {
        let err_msg = sanitize_error_message(err_msg);
        let max_attempts = self.config.ai_judge.dispatch_max_attempts.max(1);
        if dispatch_attempts >= max_attempts {
            sqlx::query(
                r#"
                UPDATE judge_jobs
                SET status = 'failed',
                    error_message = $2,
                    finished_at = NOW(),
                    dispatch_locked_until = NULL,
                    updated_at = NOW()
                WHERE id = $1
                  AND status = 'running'
                "#,
            )
            .bind(job_id)
            .bind(&err_msg)
            .execute(&self.pool)
            .await?;
            warn!(
                job_id,
                "judge dispatch failed and marked job as failed: {}", err_msg
            );
            Ok(true)
        } else {
            let retry_lock_secs = calc_retry_lock_secs(
                job_id,
                dispatch_attempts,
                self.config.ai_judge.dispatch_lock_secs,
                self.config.ai_judge.dispatch_retry_backoff_max_multiplier,
                self.config.ai_judge.dispatch_retry_jitter_ratio,
            );
            sqlx::query(
                r#"
                UPDATE judge_jobs
                SET error_message = $2,
                    dispatch_locked_until = NOW() + ($3::bigint * INTERVAL '1 second'),
                    updated_at = NOW()
                WHERE id = $1
                  AND status = 'running'
                "#,
            )
            .bind(job_id)
            .bind(&err_msg)
            .bind(retry_lock_secs)
            .execute(&self.pool)
            .await?;
            warn!(
                job_id,
                retry_lock_secs, "judge dispatch failed, waiting next retry: {}", err_msg
            );
            Ok(false)
        }
    }

    async fn mark_dispatch_terminal_failure(
        &self,
        job_id: i64,
        err_msg: &str,
    ) -> Result<bool, AppError> {
        let err_msg = sanitize_error_message(err_msg);
        let rows_affected = sqlx::query(
            r#"
            UPDATE judge_jobs
            SET status = 'failed',
                error_message = $2,
                finished_at = NOW(),
                dispatch_locked_until = NULL,
                updated_at = NOW()
            WHERE id = $1
              AND status = 'running'
            "#,
        )
        .bind(job_id)
        .bind(&err_msg)
        .execute(&self.pool)
        .await?
        .rows_affected();
        if rows_affected > 0 {
            warn!(
                job_id,
                "judge dispatch terminal failure, job marked failed: {}", err_msg
            );
            Ok(true)
        } else {
            Ok(false)
        }
    }
}
