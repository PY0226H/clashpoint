use super::*;
use reqwest::Client;
use std::collections::HashMap;
use tracing::warn;

impl AppState {
    pub async fn dispatch_pending_judge_phase_jobs_once(
        &self,
    ) -> Result<JudgePhaseDispatchTickReport, AppError> {
        let jobs = self.claim_pending_phase_dispatch_jobs().await?;
        let mut report = JudgePhaseDispatchTickReport {
            claimed: jobs.len(),
            ..Default::default()
        };

        for job in jobs.into_iter() {
            let payload = match self.load_phase_dispatch_payload(&job).await {
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
                        .mark_phase_dispatch_failure(job.id, job.dispatch_attempts, &coded_msg)
                        .await?
                    {
                        report.marked_failed += 1;
                    }
                    continue;
                }
            };
            match self.send_phase_dispatch_request(&payload).await {
                Ok(_) => {
                    self.mark_phase_dispatch_sent(job.id).await?;
                    report.dispatched += 1;
                }
                Err(err) => {
                    report.failed += 1;
                    if err.terminal {
                        report.terminal_failed += 1;
                        if self
                            .mark_phase_dispatch_terminal_failure(job.id, &err.message)
                            .await?
                        {
                            report.marked_failed += 1;
                        }
                    } else if self
                        .mark_phase_dispatch_failure(job.id, job.dispatch_attempts, &err.message)
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

        self.dispatch_metrics
            .observe_tick_success(&JudgeDispatchTickReport {
                claimed: report.claimed,
                dispatched: report.dispatched,
                failed: report.failed,
                marked_failed: report.marked_failed,
                timed_out_failed: 0,
                terminal_failed: report.terminal_failed,
                retryable_failed: report.retryable_failed,
                failed_contract: report.failed_contract,
                failed_http_4xx: report.failed_http_4xx,
                failed_http_429: report.failed_http_429,
                failed_http_5xx: report.failed_http_5xx,
                failed_network: report.failed_network,
                failed_internal: report.failed_internal,
            });
        Ok(report)
    }

    pub async fn enqueue_due_judge_final_jobs_once(&self) -> Result<usize, AppError> {
        let batch_size = self.config.ai_judge.dispatch_batch_size.max(1);
        let rows_affected = sqlx::query(
            r#"
            WITH due AS (
                SELECT
                    p.session_id,
                    p.rejudge_run_no,
                    MIN(p.phase_no) AS phase_start_no,
                    MAX(p.phase_no) AS phase_end_no
                FROM judge_phase_jobs p
                JOIN debate_sessions s ON s.id = p.session_id
                WHERE s.status = 'closed'
                  AND NOT EXISTS(
                    SELECT 1
                    FROM judge_final_jobs f
                    WHERE f.session_id = p.session_id
                      AND f.rejudge_run_no = p.rejudge_run_no
                  )
                GROUP BY p.session_id, p.rejudge_run_no
                HAVING COUNT(*) FILTER (WHERE p.status <> 'succeeded') = 0
                   AND COUNT(*) > 0
                ORDER BY MAX(p.updated_at) ASC
                LIMIT $1
            )
            INSERT INTO judge_final_jobs(
                session_id, rejudge_run_no, phase_start_no, phase_end_no,
                status, trace_id, idempotency_key, rubric_version, judge_policy_version,
                topic_domain, dispatch_attempts
            )
            SELECT
                d.session_id,
                d.rejudge_run_no,
                d.phase_start_no,
                d.phase_end_no,
                'queued',
                format(
                    'judge-final-%s-r%s-%s',
                    d.session_id::text,
                    d.rejudge_run_no::text,
                    d.phase_end_no::text
                ),
                format(
                    'judge_final:%s:%s:%s:%s:%s:%s',
                    d.session_id::text,
                    d.rejudge_run_no::text,
                    d.phase_start_no::text,
                    d.phase_end_no::text,
                    'v3',
                    'v3-default'
                ),
                'v3',
                'v3-default',
                'default',
                0
            FROM due d
            ON CONFLICT (session_id, rejudge_run_no) DO NOTHING
            "#,
        )
        .bind(batch_size)
        .execute(&self.pool)
        .await?
        .rows_affected() as usize;
        Ok(rows_affected)
    }

    pub async fn dispatch_pending_judge_final_jobs_once(
        &self,
    ) -> Result<JudgeFinalDispatchTickReport, AppError> {
        let jobs = self.claim_pending_final_dispatch_jobs().await?;
        let mut report = JudgeFinalDispatchTickReport {
            claimed: jobs.len(),
            ..Default::default()
        };

        for job in jobs.into_iter() {
            let payload = match self.load_final_dispatch_payload(&job).await {
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
                        .mark_final_dispatch_failure(
                            job.id,
                            job.dispatch_attempts,
                            &coded_msg,
                            DispatchFailureCode::PayloadBuildFailed,
                        )
                        .await?
                    {
                        report.marked_failed += 1;
                    }
                    continue;
                }
            };
            match self.send_final_dispatch_request(&payload).await {
                Ok(_) => {
                    self.mark_final_dispatch_sent(job.id).await?;
                    report.dispatched += 1;
                }
                Err(err) => {
                    report.failed += 1;
                    if err.terminal {
                        report.terminal_failed += 1;
                        if self
                            .mark_final_dispatch_terminal_failure(job.id, &err.message, err.code)
                            .await?
                        {
                            report.marked_failed += 1;
                        }
                    } else if self
                        .mark_final_dispatch_failure(
                            job.id,
                            job.dispatch_attempts,
                            &err.message,
                            err.code,
                        )
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

        self.dispatch_metrics
            .observe_tick_success(&JudgeDispatchTickReport {
                claimed: report.claimed,
                dispatched: report.dispatched,
                failed: report.failed,
                marked_failed: report.marked_failed,
                timed_out_failed: 0,
                terminal_failed: report.terminal_failed,
                retryable_failed: report.retryable_failed,
                failed_contract: report.failed_contract,
                failed_http_4xx: report.failed_http_4xx,
                failed_http_429: report.failed_http_429,
                failed_http_5xx: report.failed_http_5xx,
                failed_network: report.failed_network,
                failed_internal: report.failed_internal,
            });
        Ok(report)
    }

    pub fn get_judge_dispatch_metrics(&self) -> GetJudgeDispatchMetricsOutput {
        self.dispatch_metrics.snapshot()
    }

    pub(crate) fn observe_dispatch_worker_error(&self) {
        self.dispatch_metrics.observe_tick_error();
    }

    async fn claim_pending_phase_dispatch_jobs(
        &self,
    ) -> Result<Vec<PendingPhaseDispatchJob>, AppError> {
        let max_attempts = self.config.ai_judge.dispatch_max_attempts.max(1);
        let batch_size = self.config.ai_judge.dispatch_batch_size.max(1);
        let lock_secs = self.config.ai_judge.dispatch_lock_secs.max(1);
        let rows = sqlx::query_as(
            r#"
            WITH due AS (
                SELECT p.id
                FROM judge_phase_jobs p
                WHERE p.status = 'queued'
                  AND (p.dispatch_locked_until IS NULL OR p.dispatch_locked_until <= NOW())
                  AND p.dispatch_attempts < $1
                ORDER BY p.created_at ASC
                LIMIT $2
                FOR UPDATE SKIP LOCKED
            )
            UPDATE judge_phase_jobs p
            SET dispatch_attempts = p.dispatch_attempts + 1,
                last_dispatch_at = NOW(),
                dispatch_locked_until = NOW() + ($3::bigint * INTERVAL '1 second'),
                updated_at = NOW()
            FROM due
            WHERE p.id = due.id
            RETURNING
                p.id,
                p.session_id,
                p.phase_no,
                p.message_start_id,
                p.message_end_id,
                p.message_count,
                p.trace_id,
                p.idempotency_key,
                p.rubric_version,
                p.judge_policy_version,
                p.topic_domain,
                p.retrieval_profile,
                p.dispatch_attempts
            "#,
        )
        .bind(max_attempts)
        .bind(batch_size)
        .bind(lock_secs)
        .fetch_all(&self.pool)
        .await?;
        Ok(rows)
    }

    async fn claim_pending_final_dispatch_jobs(
        &self,
    ) -> Result<Vec<PendingFinalDispatchJob>, AppError> {
        let max_attempts = self.config.ai_judge.dispatch_max_attempts.max(1);
        let batch_size = self.config.ai_judge.dispatch_batch_size.max(1);
        let lock_secs = self.config.ai_judge.dispatch_lock_secs.max(1);
        let rows = sqlx::query_as(
            r#"
            WITH due AS (
                SELECT f.id
                FROM judge_final_jobs f
                WHERE f.status = 'queued'
                  AND (f.dispatch_locked_until IS NULL OR f.dispatch_locked_until <= NOW())
                  AND f.dispatch_attempts < $1
                ORDER BY f.created_at ASC
                LIMIT $2
                FOR UPDATE SKIP LOCKED
            )
            UPDATE judge_final_jobs f
            SET dispatch_attempts = f.dispatch_attempts + 1,
                last_dispatch_at = NOW(),
                dispatch_locked_until = NOW() + ($3::bigint * INTERVAL '1 second'),
                updated_at = NOW()
            FROM due
            WHERE f.id = due.id
            RETURNING
                f.id,
                f.session_id,
                f.phase_start_no,
                f.phase_end_no,
                f.trace_id,
                f.idempotency_key,
                f.rubric_version,
                f.judge_policy_version,
                f.topic_domain,
                f.dispatch_attempts
            "#,
        )
        .bind(max_attempts)
        .bind(batch_size)
        .bind(lock_secs)
        .fetch_all(&self.pool)
        .await?;
        Ok(rows)
    }

    async fn load_phase_dispatch_payload(
        &self,
        job: &PendingPhaseDispatchJob,
    ) -> Result<AiJudgePhaseDispatchRequest, AppError> {
        let mut messages: Vec<SessionMessageRow> = sqlx::query_as(
            r#"
            SELECT id, user_id, side, content, created_at
            FROM session_messages
            WHERE session_id = $1
              AND id >= $2
              AND id <= $3
            ORDER BY id ASC
            "#,
        )
        .bind(job.session_id)
        .bind(job.message_start_id)
        .bind(job.message_end_id)
        .fetch_all(&self.pool)
        .await?;
        if messages.len() != job.message_count as usize {
            return Err(AppError::DebateError(format!(
                "phase payload message_count mismatch, expected={}, got={}",
                job.message_count,
                messages.len()
            )));
        }

        let mut speaker_aliases: HashMap<i64, String> = HashMap::new();
        let mut speaker_seq: u32 = 1;
        let mut dispatch_messages = Vec::with_capacity(messages.len());
        for v in messages.drain(..) {
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

        Ok(AiJudgePhaseDispatchRequest {
            job_id: job.id as u64,
            scope_id: PHASE_DISPATCH_SCOPE_ID,
            session_id: job.session_id as u64,
            phase_no: job.phase_no,
            message_start_id: job.message_start_id as u64,
            message_end_id: job.message_end_id as u64,
            message_count: job.message_count,
            messages: dispatch_messages,
            rubric_version: job.rubric_version.clone(),
            judge_policy_version: job.judge_policy_version.clone(),
            topic_domain: job.topic_domain.clone(),
            retrieval_profile: job.retrieval_profile.clone(),
            trace_id: job.trace_id.clone(),
            idempotency_key: job.idempotency_key.clone(),
        })
    }

    async fn load_final_dispatch_payload(
        &self,
        job: &PendingFinalDispatchJob,
    ) -> Result<AiJudgeFinalDispatchRequest, AppError> {
        if job.phase_end_no < job.phase_start_no {
            return Err(AppError::DebateError(format!(
                "final payload phase range invalid, start={}, end={}",
                job.phase_start_no, job.phase_end_no
            )));
        }
        Ok(AiJudgeFinalDispatchRequest {
            job_id: job.id as u64,
            scope_id: FINAL_DISPATCH_SCOPE_ID,
            session_id: job.session_id as u64,
            phase_start_no: job.phase_start_no,
            phase_end_no: job.phase_end_no,
            rubric_version: job.rubric_version.clone(),
            judge_policy_version: job.judge_policy_version.clone(),
            topic_domain: job.topic_domain.clone(),
            trace_id: job.trace_id.clone(),
            idempotency_key: job.idempotency_key.clone(),
        })
    }

    async fn send_phase_dispatch_request(
        &self,
        payload: &AiJudgePhaseDispatchRequest,
    ) -> Result<(), DispatchSendError> {
        let url = build_dispatch_url(&self.config.ai_judge.service_base_url, PHASE_DISPATCH_PATH);
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
                        &format!("build phase dispatch client failed: {e}"),
                    ),
                )
            })?;
        let resp = client
            .post(&url)
            .header("x-ai-internal-key", &self.config.ai_judge.internal_key)
            .header("x-trace-id", &payload.trace_id)
            .json(payload)
            .send()
            .await
            .map_err(|e| {
                DispatchSendError::retryable(
                    DispatchFailureCode::NetworkSendFailed,
                    coded_error_message(
                        DispatchFailureCode::NetworkSendFailed,
                        &format!("phase dispatch request io failed: {e}"),
                    ),
                )
            })?;

        if resp.status().is_success() {
            let body = resp.text().await.unwrap_or_default();
            if let Err(err) = validate_dispatch_response(&body, payload.job_id) {
                let (code, msg) = match err {
                    DispatchResponseViolation::InvalidPayload => (
                        DispatchFailureCode::ResponseAcceptedFalse,
                        "phase dispatch response is not valid json".to_string(),
                    ),
                    DispatchResponseViolation::AcceptedFalse { status } => (
                        DispatchFailureCode::ResponseAcceptedFalse,
                        format!(
                            "phase dispatch response rejected: accepted=false, status={status}"
                        ),
                    ),
                    DispatchResponseViolation::JobIdMismatch { expected, got } => (
                        DispatchFailureCode::ResponseJobIdMismatch,
                        format!(
                            "phase dispatch response job_id mismatch: expected={}, got={}",
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
            let message = format!(
                "phase dispatch request failed: status={}, body={}",
                status, body
            );
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

    async fn send_final_dispatch_request(
        &self,
        payload: &AiJudgeFinalDispatchRequest,
    ) -> Result<(), DispatchSendError> {
        let url = build_dispatch_url(&self.config.ai_judge.service_base_url, FINAL_DISPATCH_PATH);
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
                        &format!("build final dispatch client failed: {e}"),
                    ),
                )
            })?;
        let resp = client
            .post(&url)
            .header("x-ai-internal-key", &self.config.ai_judge.internal_key)
            .header("x-trace-id", &payload.trace_id)
            .json(payload)
            .send()
            .await
            .map_err(|e| {
                DispatchSendError::retryable(
                    DispatchFailureCode::NetworkSendFailed,
                    coded_error_message(
                        DispatchFailureCode::NetworkSendFailed,
                        &format!("final dispatch request io failed: {e}"),
                    ),
                )
            })?;

        if resp.status().is_success() {
            let body = resp.text().await.unwrap_or_default();
            if let Err(err) = validate_dispatch_response(&body, payload.job_id) {
                let (code, msg) = match err {
                    DispatchResponseViolation::InvalidPayload => (
                        DispatchFailureCode::ResponseAcceptedFalse,
                        "final dispatch response is not valid json".to_string(),
                    ),
                    DispatchResponseViolation::AcceptedFalse { status } => (
                        DispatchFailureCode::ResponseAcceptedFalse,
                        format!(
                            "final dispatch response rejected: accepted=false, status={status}"
                        ),
                    ),
                    DispatchResponseViolation::JobIdMismatch { expected, got } => (
                        DispatchFailureCode::ResponseJobIdMismatch,
                        format!(
                            "final dispatch response job_id mismatch: expected={}, got={}",
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
            let message = format!(
                "final dispatch request failed: status={}, body={}",
                status, body
            );
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

    async fn mark_phase_dispatch_sent(&self, phase_job_id: i64) -> Result<(), AppError> {
        sqlx::query(
            r#"
            UPDATE judge_phase_jobs
            SET status = 'dispatched',
                error_message = NULL,
                dispatch_locked_until = NULL,
                updated_at = NOW()
            WHERE id = $1 AND status = 'queued'
            "#,
        )
        .bind(phase_job_id)
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    async fn mark_phase_dispatch_failure(
        &self,
        phase_job_id: i64,
        dispatch_attempts: i32,
        err_msg: &str,
    ) -> Result<bool, AppError> {
        let err_msg = sanitize_error_message(err_msg);
        let max_attempts = self.config.ai_judge.dispatch_max_attempts.max(1);
        if dispatch_attempts >= max_attempts {
            sqlx::query(
                r#"
                UPDATE judge_phase_jobs
                SET status = 'failed',
                    error_message = $2,
                    dispatch_locked_until = NULL,
                    updated_at = NOW()
                WHERE id = $1
                  AND status = 'queued'
                "#,
            )
            .bind(phase_job_id)
            .bind(&err_msg)
            .execute(&self.pool)
            .await?;
            warn!(
                phase_job_id,
                "judge phase dispatch failed and marked job as failed: {}", err_msg
            );
            Ok(true)
        } else {
            let retry_lock_secs = calc_retry_lock_secs(
                phase_job_id,
                dispatch_attempts,
                self.config.ai_judge.dispatch_lock_secs,
                self.config.ai_judge.dispatch_retry_backoff_max_multiplier,
                self.config.ai_judge.dispatch_retry_jitter_ratio,
            );
            sqlx::query(
                r#"
                UPDATE judge_phase_jobs
                SET error_message = $2,
                    dispatch_locked_until = NOW() + ($3::bigint * INTERVAL '1 second'),
                    updated_at = NOW()
                WHERE id = $1
                  AND status = 'queued'
                "#,
            )
            .bind(phase_job_id)
            .bind(&err_msg)
            .bind(retry_lock_secs)
            .execute(&self.pool)
            .await?;
            warn!(
                phase_job_id,
                retry_lock_secs, "judge phase dispatch failed, waiting next retry: {}", err_msg
            );
            Ok(false)
        }
    }

    async fn mark_phase_dispatch_terminal_failure(
        &self,
        phase_job_id: i64,
        err_msg: &str,
    ) -> Result<bool, AppError> {
        let err_msg = sanitize_error_message(err_msg);
        let rows_affected = sqlx::query(
            r#"
            UPDATE judge_phase_jobs
            SET status = 'failed',
                error_message = $2,
                dispatch_locked_until = NULL,
                updated_at = NOW()
            WHERE id = $1
              AND status = 'queued'
            "#,
        )
        .bind(phase_job_id)
        .bind(&err_msg)
        .execute(&self.pool)
        .await?
        .rows_affected();
        if rows_affected > 0 {
            warn!(
                phase_job_id,
                "judge phase dispatch terminal failure, phase job marked failed: {}", err_msg
            );
            Ok(true)
        } else {
            Ok(false)
        }
    }

    async fn mark_final_dispatch_sent(&self, final_job_id: i64) -> Result<(), AppError> {
        sqlx::query(
            r#"
            UPDATE judge_final_jobs
            SET status = 'dispatched',
                error_message = NULL,
                error_code = NULL,
                contract_failure_type = NULL,
                dispatch_locked_until = NULL,
                updated_at = NOW()
            WHERE id = $1 AND status = 'queued'
            "#,
        )
        .bind(final_job_id)
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    async fn mark_final_dispatch_failure(
        &self,
        final_job_id: i64,
        dispatch_attempts: i32,
        err_msg: &str,
        code: DispatchFailureCode,
    ) -> Result<bool, AppError> {
        let err_msg = sanitize_error_message(err_msg);
        let error_code = Some(code.as_str().to_string());
        let contract_failure_type = contract_failure_type_from_dispatch_code(code);
        let max_attempts = self.config.ai_judge.dispatch_max_attempts.max(1);
        if dispatch_attempts >= max_attempts {
            sqlx::query(
                r#"
                UPDATE judge_final_jobs
                SET status = 'failed',
                    error_message = $2,
                    error_code = $3,
                    contract_failure_type = $4,
                    dispatch_locked_until = NULL,
                    updated_at = NOW()
                WHERE id = $1
                  AND status = 'queued'
                "#,
            )
            .bind(final_job_id)
            .bind(&err_msg)
            .bind(error_code.as_deref())
            .bind(contract_failure_type)
            .execute(&self.pool)
            .await?;
            warn!(
                final_job_id,
                "judge final dispatch failed and marked job as failed: {}", err_msg
            );
            Ok(true)
        } else {
            let retry_lock_secs = calc_retry_lock_secs(
                final_job_id,
                dispatch_attempts,
                self.config.ai_judge.dispatch_lock_secs,
                self.config.ai_judge.dispatch_retry_backoff_max_multiplier,
                self.config.ai_judge.dispatch_retry_jitter_ratio,
            );
            sqlx::query(
                r#"
                UPDATE judge_final_jobs
                SET error_message = $2,
                    error_code = $3,
                    contract_failure_type = $4,
                    dispatch_locked_until = NOW() + ($5::bigint * INTERVAL '1 second'),
                    updated_at = NOW()
                WHERE id = $1
                  AND status = 'queued'
                "#,
            )
            .bind(final_job_id)
            .bind(&err_msg)
            .bind(error_code.as_deref())
            .bind(contract_failure_type)
            .bind(retry_lock_secs)
            .execute(&self.pool)
            .await?;
            warn!(
                final_job_id,
                retry_lock_secs, "judge final dispatch failed, waiting next retry: {}", err_msg
            );
            Ok(false)
        }
    }

    async fn mark_final_dispatch_terminal_failure(
        &self,
        final_job_id: i64,
        err_msg: &str,
        code: DispatchFailureCode,
    ) -> Result<bool, AppError> {
        let err_msg = sanitize_error_message(err_msg);
        let error_code = Some(code.as_str().to_string());
        let contract_failure_type = contract_failure_type_from_dispatch_code(code);
        let rows_affected = sqlx::query(
            r#"
            UPDATE judge_final_jobs
            SET status = 'failed',
                error_message = $2,
                error_code = $3,
                contract_failure_type = $4,
                dispatch_locked_until = NULL,
                updated_at = NOW()
            WHERE id = $1
              AND status = 'queued'
            "#,
        )
        .bind(final_job_id)
        .bind(&err_msg)
        .bind(error_code.as_deref())
        .bind(contract_failure_type)
        .execute(&self.pool)
        .await?
        .rows_affected();
        if rows_affected > 0 {
            warn!(
                final_job_id,
                "judge final dispatch terminal failure, final job marked failed: {}", err_msg
            );
            Ok(true)
        } else {
            Ok(false)
        }
    }
}

fn contract_failure_type_from_dispatch_code(code: DispatchFailureCode) -> Option<&'static str> {
    match code {
        DispatchFailureCode::ResponseAcceptedFalse => Some("response_accepted_false"),
        DispatchFailureCode::ResponseJobIdMismatch => Some("response_job_id_mismatch"),
        _ => None,
    }
}
