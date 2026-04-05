use super::*;
use crate::models::OpsPermission;
use serde_json::Value;

const PHASE_WINDOW_SIZE: i64 = 100;
const PHASE_RUBRIC_VERSION: &str = "v3";
const PHASE_POLICY_VERSION: &str = "v3-default";
const PHASE_TOPIC_DOMAIN: &str = "default";
const PHASE_RETRIEVAL_PROFILE: &str = "hybrid_v1";

const JUDGE_REQUEST_CONFLICT_SESSION_NOT_ALLOWED: &str = "judge_request_session_not_allowed";
const JUDGE_REQUEST_CONFLICT_NOT_PARTICIPANT: &str = "judge_request_not_participant";
const JUDGE_REQUEST_CONFLICT_REQUIRE_EXISTING_REPORT: &str =
    "judge_request_rejudge_requires_existing_report";
const JUDGE_REQUEST_CONFLICT_FINAL_REPORT_EXISTS: &str =
    "judge_request_final_report_exists_require_allow_rejudge";
const JUDGE_REQUEST_CONFLICT_IDEMPOTENCY_INFLIGHT: &str = "judge_request_idempotency_inflight";
const JUDGE_REQUEST_CONFLICT_IDEMPOTENCY_PAYLOAD_MISMATCH: &str =
    "judge_request_idempotency_payload_mismatch";

const JUDGE_REQUEST_REASON_PHASE_JOBS_QUEUED: &str = "phase_jobs_queued";
const JUDGE_REQUEST_REASON_ALREADY_QUEUED: &str = "already_queued";
const JUDGE_REQUEST_REASON_NO_MESSAGES: &str = "no_messages";
const JUDGE_REQUEST_REASON_FINAL_REPORT_EXISTS: &str = "final_report_exists";
const JUDGE_REQUEST_REASON_NOOP: &str = "noop";
const JUDGE_REQUEST_REASON_DEGRADED_ENQUEUE_FINAL_FAILED: &str = "degraded_enqueue_final_failed";

#[derive(Debug, Clone, Copy)]
struct EnqueuePhaseJobsResult {
    inserted: u32,
    total_messages: i64,
}

#[derive(Debug, Clone, Copy)]
struct JudgeJobRequestFlow<'a> {
    require_participant: bool,
    require_existing_report: bool,
    trigger_mode: &'a str,
    request_idempotency_key: Option<&'a str>,
}

impl AppState {
    pub(crate) async fn request_judge_job_automatically(
        &self,
        session_id: u64,
    ) -> Result<Option<RequestJudgeJobOutput>, AppError> {
        let requester: Option<AutoJudgeRequesterRow> = sqlx::query_as(
            r#"
            SELECT
                (
                    SELECT sp.user_id
                    FROM session_participants sp
                    WHERE sp.session_id = s.id
                    ORDER BY sp.joined_at ASC
                    LIMIT 1
                ) AS requester_id
            FROM debate_sessions s
            WHERE s.id = $1
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&self.pool)
        .await?;

        let Some(requester) = requester else {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        };
        let Some(requester_id) = requester.requester_id else {
            warn!(
                session_id,
                reason = "judge_request_auto_no_participant",
                "auto judge trigger skipped: no participant requester"
            );
            return Ok(None);
        };

        let auto_user = User::new(requester_id, "__auto_judge__", "auto_judge@system.local");

        let ret = self
            .request_judge_job_internal(
                session_id,
                &auto_user,
                RequestJudgeJobInput {
                    allow_rejudge: false,
                },
                JudgeJobRequestFlow {
                    require_participant: false,
                    require_existing_report: false,
                    trigger_mode: "auto",
                    request_idempotency_key: None,
                },
            )
            .await?;
        Ok(Some(ret))
    }

    pub async fn load_judge_job_request_idempotency_replay(
        &self,
        session_id: u64,
        user_id: u64,
        idempotency_key: &str,
    ) -> Result<Option<RequestJudgeJobOutput>, AppError> {
        let row: Option<JudgeJobRequestIdempotencyRow> = sqlx::query_as(
            r#"
            SELECT request_hash, status, response_snapshot
            FROM judge_job_request_idempotency
            WHERE session_id = $1
              AND user_id = $2
              AND idempotency_key = $3
            "#,
        )
        .bind(session_id as i64)
        .bind(user_id as i64)
        .bind(idempotency_key)
        .fetch_optional(&self.pool)
        .await?;

        let Some(row) = row else {
            return Ok(None);
        };
        if row.status != "completed" {
            return Ok(None);
        }
        decode_judge_request_snapshot(row.response_snapshot)
    }

    async fn prepare_judge_job_request_idempotency(
        &self,
        session_id: u64,
        user_id: u64,
        idempotency_key: &str,
        request_hash: &str,
    ) -> Result<Option<RequestJudgeJobOutput>, AppError> {
        let inserted: Option<i64> = sqlx::query_scalar(
            r#"
            INSERT INTO judge_job_request_idempotency(
                session_id, user_id, idempotency_key,
                request_hash, status, response_snapshot, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, 'processing', NULL, NOW(), NOW())
            ON CONFLICT (session_id, user_id, idempotency_key) DO NOTHING
            RETURNING id
            "#,
        )
        .bind(session_id as i64)
        .bind(user_id as i64)
        .bind(idempotency_key)
        .bind(request_hash)
        .fetch_optional(&self.pool)
        .await?;
        if inserted.is_some() {
            return Ok(None);
        }

        let row: JudgeJobRequestIdempotencyRow = sqlx::query_as(
            r#"
            SELECT request_hash, status, response_snapshot
            FROM judge_job_request_idempotency
            WHERE session_id = $1
              AND user_id = $2
              AND idempotency_key = $3
            "#,
        )
        .bind(session_id as i64)
        .bind(user_id as i64)
        .bind(idempotency_key)
        .fetch_one(&self.pool)
        .await?;

        if row.request_hash != request_hash {
            return Err(AppError::DebateConflict(
                JUDGE_REQUEST_CONFLICT_IDEMPOTENCY_PAYLOAD_MISMATCH.to_string(),
            ));
        }
        if row.status == "completed" {
            return decode_judge_request_snapshot(row.response_snapshot);
        }
        if row.status == "processing" {
            return Err(AppError::DebateConflict(
                JUDGE_REQUEST_CONFLICT_IDEMPOTENCY_INFLIGHT.to_string(),
            ));
        }

        sqlx::query(
            r#"
            UPDATE judge_job_request_idempotency
            SET status = 'processing',
                request_hash = $4,
                response_snapshot = NULL,
                updated_at = NOW()
            WHERE session_id = $1
              AND user_id = $2
              AND idempotency_key = $3
            "#,
        )
        .bind(session_id as i64)
        .bind(user_id as i64)
        .bind(idempotency_key)
        .bind(request_hash)
        .execute(&self.pool)
        .await?;
        Ok(None)
    }

    async fn complete_judge_job_request_idempotency(
        &self,
        session_id: u64,
        user_id: u64,
        idempotency_key: &str,
        request_hash: &str,
        output: &RequestJudgeJobOutput,
    ) -> Result<(), AppError> {
        let snapshot = serde_json::to_value(output).map_err(|err| {
            AppError::ServerError(format!("judge_request_snapshot_serialize_failed:{err}"))
        })?;
        sqlx::query(
            r#"
            UPDATE judge_job_request_idempotency
            SET status = 'completed',
                response_snapshot = $5,
                updated_at = NOW()
            WHERE session_id = $1
              AND user_id = $2
              AND idempotency_key = $3
              AND request_hash = $4
            "#,
        )
        .bind(session_id as i64)
        .bind(user_id as i64)
        .bind(idempotency_key)
        .bind(request_hash)
        .bind(snapshot)
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    async fn clear_judge_job_request_idempotency_on_error(
        &self,
        session_id: u64,
        user_id: u64,
        idempotency_key: &str,
    ) {
        if let Err(err) = sqlx::query(
            r#"
            DELETE FROM judge_job_request_idempotency
            WHERE session_id = $1
              AND user_id = $2
              AND idempotency_key = $3
              AND status = 'processing'
            "#,
        )
        .bind(session_id as i64)
        .bind(user_id as i64)
        .bind(idempotency_key)
        .execute(&self.pool)
        .await
        {
            warn!(
                session_id,
                user_id,
                idempotency_key,
                err = %err,
                "clear judge request idempotency processing row failed"
            );
        }
    }

    async fn resolve_phase_boundaries(
        &self,
        tx: &mut Transaction<'_, Postgres>,
        session_id: i64,
        phase_no: i32,
        total_messages: i64,
    ) -> Result<(i64, i64, i32), AppError> {
        let phase_no_i64 = i64::from(phase_no.max(1));
        let start_offset = (phase_no_i64 - 1) * PHASE_WINDOW_SIZE;
        let end_offset = (phase_no_i64 * PHASE_WINDOW_SIZE).min(total_messages) - 1;
        if end_offset < start_offset {
            return Err(AppError::DebateError(format!(
                "invalid phase range: phase_no={phase_no}, total_messages={total_messages}"
            )));
        }

        let message_start_id: i64 = sqlx::query_scalar(
            r#"
            SELECT id
            FROM session_messages
            WHERE session_id = $1
            ORDER BY id ASC
            OFFSET $2
            LIMIT 1
            "#,
        )
        .bind(session_id)
        .bind(start_offset)
        .fetch_one(&mut **tx)
        .await?;

        let message_end_id: i64 = sqlx::query_scalar(
            r#"
            SELECT id
            FROM session_messages
            WHERE session_id = $1
            ORDER BY id ASC
            OFFSET $2
            LIMIT 1
            "#,
        )
        .bind(session_id)
        .bind(end_offset)
        .fetch_one(&mut **tx)
        .await?;

        let message_count = i32::try_from(end_offset - start_offset + 1)
            .map_err(|_| AppError::DebateError("phase message_count overflow".to_string()))?;

        Ok((message_start_id, message_end_id, message_count))
    }

    async fn enqueue_missing_phase_jobs_for_session(
        &self,
        tx: &mut Transaction<'_, Postgres>,
        session_id: i64,
        session_status: &str,
    ) -> Result<EnqueuePhaseJobsResult, AppError> {
        let total_messages: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(1)
            FROM session_messages
            WHERE session_id = $1
            "#,
        )
        .bind(session_id)
        .fetch_one(&mut **tx)
        .await?;

        if total_messages <= 0 {
            return Ok(EnqueuePhaseJobsResult {
                inserted: 0,
                total_messages,
            });
        }

        let mut phase_count = total_messages / PHASE_WINDOW_SIZE;
        if session_status == "closed" && total_messages % PHASE_WINDOW_SIZE != 0 {
            phase_count += 1;
        }
        if phase_count <= 0 {
            return Ok(EnqueuePhaseJobsResult {
                inserted: 0,
                total_messages,
            });
        }

        let mut inserted = 0_u32;
        for phase_no in 1..=i32::try_from(phase_count).unwrap_or(i32::MAX) {
            let (message_start_id, message_end_id, message_count) = self
                .resolve_phase_boundaries(tx, session_id, phase_no, total_messages)
                .await?;

            let trace_id = format!("judge-phase-{session_id}-{phase_no}");
            let idempotency_key = format!(
                "judge_phase:{session_id}:{phase_no}:{PHASE_RUBRIC_VERSION}:{PHASE_POLICY_VERSION}"
            );

            let inserted_id: Option<i64> = sqlx::query_scalar(
                r#"
                INSERT INTO judge_phase_jobs(
                    session_id, phase_no, message_start_id, message_end_id, message_count,
                    status, trace_id, idempotency_key, rubric_version, judge_policy_version,
                    topic_domain, retrieval_profile, dispatch_attempts,
                    created_at, updated_at
                )
                VALUES (
                    $1, $2, $3, $4, $5,
                    'queued', $6, $7, $8, $9,
                    $10, $11, 0,
                    NOW(), NOW()
                )
                ON CONFLICT (session_id, phase_no) DO NOTHING
                RETURNING id
                "#,
            )
            .bind(session_id)
            .bind(phase_no)
            .bind(message_start_id)
            .bind(message_end_id)
            .bind(message_count)
            .bind(trace_id)
            .bind(idempotency_key)
            .bind(PHASE_RUBRIC_VERSION)
            .bind(PHASE_POLICY_VERSION)
            .bind(PHASE_TOPIC_DOMAIN)
            .bind(PHASE_RETRIEVAL_PROFILE)
            .fetch_optional(&mut **tx)
            .await?;

            if inserted_id.is_some() {
                inserted = inserted.saturating_add(1);
            }
        }
        Ok(EnqueuePhaseJobsResult {
            inserted,
            total_messages,
        })
    }

    async fn request_judge_job_internal(
        &self,
        session_id: u64,
        user: &User,
        input: RequestJudgeJobInput,
        flow: JudgeJobRequestFlow<'_>,
    ) -> Result<RequestJudgeJobOutput, AppError> {
        let request_hash = build_judge_job_request_hash(&input);
        if let Some(idempotency_key) = flow.request_idempotency_key {
            if let Some(replayed) = self
                .prepare_judge_job_request_idempotency(
                    session_id,
                    user.id as u64,
                    idempotency_key,
                    &request_hash,
                )
                .await?
            {
                return Ok(replayed);
            }
        }

        let mut tx = self.pool.begin().await?;
        let Some(session): Option<DebateSessionForJudge> = sqlx::query_as(
            r#"
            SELECT status
            FROM debate_sessions
            WHERE id = $1
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&mut *tx)
        .await?
        else {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        };

        if !can_request_judge(&session.status) {
            return Err(AppError::DebateConflict(
                JUDGE_REQUEST_CONFLICT_SESSION_NOT_ALLOWED.to_string(),
            ));
        }

        if flow.require_participant {
            let joined: Option<(i32,)> = sqlx::query_as(
                r#"
                SELECT 1
                FROM session_participants
                WHERE session_id = $1 AND user_id = $2
                "#,
            )
            .bind(session_id as i64)
            .bind(user.id)
            .fetch_optional(&mut *tx)
            .await?;
            if joined.is_none() {
                return Err(AppError::DebateConflict(
                    JUDGE_REQUEST_CONFLICT_NOT_PARTICIPANT.to_string(),
                ));
            }
        }

        let report_exists = sqlx::query_scalar::<_, i64>(
            r#"
            SELECT id
            FROM judge_final_reports
            WHERE session_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&mut *tx)
        .await?
        .is_some();

        if flow.require_existing_report && !report_exists {
            return Err(AppError::DebateConflict(
                JUDGE_REQUEST_CONFLICT_REQUIRE_EXISTING_REPORT.to_string(),
            ));
        }
        if report_exists && !input.allow_rejudge {
            return Err(AppError::DebateConflict(
                JUDGE_REQUEST_CONFLICT_FINAL_REPORT_EXISTS.to_string(),
            ));
        }

        let phase_enqueue = self
            .enqueue_missing_phase_jobs_for_session(&mut tx, session_id as i64, &session.status)
            .await?;
        tx.commit().await?;

        self.trigger_judge_dispatch(JudgeDispatchTrigger {
            job_id: session_id as i64,
            source: "event:v3_request",
        });

        let enqueue_final_err = self.enqueue_due_judge_final_jobs_once().await.err();
        if let Some(err) = enqueue_final_err.as_ref() {
            warn!(
                session_id,
                trigger_mode = flow.trigger_mode,
                err = %err,
                reason = JUDGE_REQUEST_REASON_DEGRADED_ENQUEUE_FINAL_FAILED,
                "enqueue due judge final jobs failed after request"
            );
        }
        let queued_final_job = sqlx::query_scalar::<_, i64>(
            r#"
            SELECT id
            FROM judge_final_jobs
            WHERE session_id = $1
            LIMIT 1
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&self.pool)
        .await?
        .is_some();

        let (status, reason) = if enqueue_final_err.is_some() {
            (
                "degraded".to_string(),
                JUDGE_REQUEST_REASON_DEGRADED_ENQUEUE_FINAL_FAILED.to_string(),
            )
        } else if phase_enqueue.inserted > 0 {
            (
                "phase_jobs_queued".to_string(),
                JUDGE_REQUEST_REASON_PHASE_JOBS_QUEUED.to_string(),
            )
        } else if queued_final_job {
            (
                "already_queued".to_string(),
                JUDGE_REQUEST_REASON_ALREADY_QUEUED.to_string(),
            )
        } else if phase_enqueue.total_messages <= 0 {
            (
                "noop".to_string(),
                JUDGE_REQUEST_REASON_NO_MESSAGES.to_string(),
            )
        } else if report_exists {
            (
                "noop".to_string(),
                JUDGE_REQUEST_REASON_FINAL_REPORT_EXISTS.to_string(),
            )
        } else {
            ("noop".to_string(), JUDGE_REQUEST_REASON_NOOP.to_string())
        };

        let output = RequestJudgeJobOutput {
            accepted: true,
            session_id,
            status,
            reason: Some(reason),
            queued_phase_jobs: phase_enqueue.inserted,
            queued_final_job,
            trigger_mode: flow.trigger_mode.to_string(),
        };

        if let Some(idempotency_key) = flow.request_idempotency_key {
            if let Err(err) = self
                .complete_judge_job_request_idempotency(
                    session_id,
                    user.id as u64,
                    idempotency_key,
                    &request_hash,
                    &output,
                )
                .await
            {
                warn!(
                    session_id,
                    user_id = user.id,
                    idempotency_key,
                    err = %err,
                    "complete judge request idempotency row failed"
                );
            }
        }
        Ok(output)
    }

    pub async fn request_judge_job(
        &self,
        session_id: u64,
        user: &User,
        input: RequestJudgeJobInput,
        request_idempotency_key: Option<&str>,
    ) -> Result<RequestJudgeJobOutput, AppError> {
        let ret = self
            .request_judge_job_internal(
                session_id,
                user,
                input,
                JudgeJobRequestFlow {
                    require_participant: true,
                    require_existing_report: false,
                    trigger_mode: "manual",
                    request_idempotency_key,
                },
            )
            .await;
        if ret.is_err() {
            let should_clear = !matches!(
                &ret,
                Err(AppError::DebateConflict(code))
                    if code == JUDGE_REQUEST_CONFLICT_IDEMPOTENCY_INFLIGHT
                        || code == JUDGE_REQUEST_CONFLICT_IDEMPOTENCY_PAYLOAD_MISMATCH
            );
            if should_clear {
                if let Some(idempotency_key) = request_idempotency_key {
                    self.clear_judge_job_request_idempotency_on_error(
                        session_id,
                        user.id as u64,
                        idempotency_key,
                    )
                    .await;
                }
            }
        }
        ret
    }

    pub async fn request_judge_rejudge_by_owner(
        &self,
        session_id: u64,
        user: &User,
    ) -> Result<RequestJudgeJobOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeRejudge)
            .await?;
        self.request_judge_job_internal(
            session_id,
            user,
            RequestJudgeJobInput {
                allow_rejudge: true,
            },
            JudgeJobRequestFlow {
                require_participant: false,
                require_existing_report: true,
                trigger_mode: "ops_rejudge",
                request_idempotency_key: None,
            },
        )
        .await
    }
}

fn build_judge_job_request_hash(input: &RequestJudgeJobInput) -> String {
    format!("allow_rejudge={}", input.allow_rejudge)
}

fn decode_judge_request_snapshot(
    snapshot: Option<Value>,
) -> Result<Option<RequestJudgeJobOutput>, AppError> {
    let Some(snapshot) = snapshot else {
        return Err(AppError::DebateConflict(
            JUDGE_REQUEST_CONFLICT_IDEMPOTENCY_INFLIGHT.to_string(),
        ));
    };
    let output = serde_json::from_value::<RequestJudgeJobOutput>(snapshot).map_err(|err| {
        AppError::ServerError(format!("judge_request_snapshot_decode_failed:{err}"))
    })?;
    Ok(Some(output))
}
