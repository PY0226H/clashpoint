use super::*;
use crate::models::OpsPermission;

const PHASE_WINDOW_SIZE: i64 = 100;
const PHASE_RUBRIC_VERSION: &str = "v3";
const PHASE_POLICY_VERSION: &str = "v3-default";
const PHASE_TOPIC_DOMAIN: &str = "default";
const PHASE_RETRIEVAL_PROFILE: &str = "hybrid_v1";

impl AppState {
    pub(crate) async fn request_judge_job_automatically(
        &self,
        session_id: u64,
    ) -> Result<Option<RequestJudgeJobOutput>, AppError> {
        let requester: Option<AutoJudgeRequesterRow> = sqlx::query_as(
            r#"
            SELECT
                COALESCE(
                    (
                        SELECT sp.user_id
                        FROM session_participants sp
                        WHERE sp.session_id = s.id
                        ORDER BY sp.joined_at ASC
                        LIMIT 1
                    ),
                    (
                        SELECT u.id
                        FROM users u
                        ORDER BY u.id ASC
                        LIMIT 1
                    )
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
                "auto judge trigger skipped: no available requester in platform scope"
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
                false,
                false,
                "auto",
            )
            .await?;
        Ok(Some(ret))
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
    ) -> Result<u32, AppError> {
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
            return Ok(0);
        }

        let mut phase_count = total_messages / PHASE_WINDOW_SIZE;
        if session_status == "closed" && total_messages % PHASE_WINDOW_SIZE != 0 {
            phase_count += 1;
        }
        if phase_count <= 0 {
            return Ok(0);
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
        Ok(inserted)
    }

    async fn request_judge_job_internal(
        &self,
        session_id: u64,
        user: &User,
        input: RequestJudgeJobInput,
        require_participant: bool,
        require_existing_report: bool,
        trigger_mode: &str,
    ) -> Result<RequestJudgeJobOutput, AppError> {
        let mut tx = self.pool.begin().await?;

        let Some(session): Option<DebateSessionForJudge> = sqlx::query_as(
            r#"
            SELECT status
            FROM debate_sessions
            WHERE id = $1
            FOR UPDATE
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
            return Err(AppError::DebateConflict(format!(
                "session {} is not in judging/closed status",
                session_id
            )));
        }

        if require_participant {
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
                return Err(AppError::DebateConflict(format!(
                    "user {} has not joined session {}",
                    user.id, session_id
                )));
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

        if require_existing_report && !report_exists {
            return Err(AppError::DebateConflict(format!(
                "session {} has no judge final report, cannot trigger rejudge",
                session_id
            )));
        }
        if report_exists && !input.allow_rejudge {
            return Err(AppError::DebateConflict(format!(
                "session {} already has final report, set allowRejudge=true to re-trigger",
                session_id
            )));
        }

        let queued_phase_jobs = self
            .enqueue_missing_phase_jobs_for_session(&mut tx, session_id as i64, &session.status)
            .await?;

        tx.commit().await?;
        self.trigger_judge_dispatch(JudgeDispatchTrigger {
            job_id: session_id as i64,
            source: "event:v3_request",
        });

        let _ = self.enqueue_due_judge_final_jobs_once().await;
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

        let status = if queued_phase_jobs > 0 {
            "phase_jobs_queued"
        } else if queued_final_job {
            "already_queued"
        } else {
            "noop"
        }
        .to_string();

        Ok(RequestJudgeJobOutput {
            accepted: true,
            session_id,
            status,
            reason: None,
            queued_phase_jobs,
            queued_final_job,
            trigger_mode: trigger_mode.to_string(),
        })
    }

    pub async fn request_judge_job(
        &self,
        session_id: u64,
        user: &User,
        input: RequestJudgeJobInput,
    ) -> Result<RequestJudgeJobOutput, AppError> {
        self.request_judge_job_internal(session_id, user, input, true, false, "manual")
            .await
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
            false,
            true,
            "ops_rejudge",
        )
        .await
    }
}
