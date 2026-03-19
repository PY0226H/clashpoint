use super::*;
use crate::models::OpsPermission;
use crate::{DomainEvent, EventPublisher};

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
                    style_mode: None,
                    allow_rejudge: false,
                },
                false,
                false,
            )
            .await?;
        Ok(Some(ret))
    }

    async fn request_judge_job_internal(
        &self,
        session_id: u64,
        user: &User,
        input: RequestJudgeJobInput,
        require_participant: bool,
        require_existing_report: bool,
    ) -> Result<RequestJudgeJobOutput, AppError> {
        let configured_style_mode = self.config.ai_judge.style_mode.clone();
        let (style_mode, style_mode_source) =
            match normalize_style_mode(Some(configured_style_mode.clone())) {
                Ok(mode) => (mode, STYLE_SOURCE_SYSTEM_CONFIG),
                Err(_) => {
                    warn!(
                        configured_style_mode,
                        "invalid ai_judge.style_mode config, fallback to rational"
                    );
                    (
                        STYLE_RATIONAL.to_string(),
                        STYLE_SOURCE_SYSTEM_CONFIG_FALLBACK_DEFAULT,
                    )
                }
            };
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

        let existing_running: Option<JudgeJobRow> = sqlx::query_as(
            r#"
            SELECT id, status, style_mode, rejudge_triggered, requested_at
            FROM judge_jobs
            WHERE session_id = $1 AND status = 'running'
            ORDER BY requested_at DESC
            LIMIT 1
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&mut *tx)
        .await?;
        if let Some(job) = existing_running {
            tx.commit().await?;
            self.trigger_judge_dispatch(JudgeDispatchTrigger {
                job_id: job.id,
                source: "event:existing_running_job",
            });
            return Ok(RequestJudgeJobOutput {
                session_id,
                job_id: job.id as u64,
                status: job.status,
                style_mode: job.style_mode,
                style_mode_source: STYLE_SOURCE_EXISTING_RUNNING_JOB.to_string(),
                rejudge_triggered: job.rejudge_triggered,
                requested_at: job.requested_at,
                newly_created: false,
            });
        }

        let report_exists = sqlx::query_scalar::<_, i64>(
            r#"
            SELECT id
            FROM judge_reports
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
                "session {} has no judge report, cannot trigger rejudge",
                session_id
            )));
        }
        if report_exists && !input.allow_rejudge {
            return Err(AppError::DebateConflict(format!(
                "session {} already has judge report, set allowRejudge=true to create rejudge job",
                session_id
            )));
        }

        let rejudge_triggered = report_exists && input.allow_rejudge;
        let job: JudgeJobRow = sqlx::query_as(
            r#"
            INSERT INTO judge_jobs(
                session_id, requested_by, status, style_mode, rejudge_triggered,
                requested_at, started_at, created_at, updated_at
            )
            VALUES ($1, $2, 'running', $3, $4, NOW(), NULL, NOW(), NOW())
            RETURNING id, status, style_mode, rejudge_triggered, requested_at
            "#,
        )
        .bind(session_id as i64)
        .bind(user.id)
        .bind(&style_mode)
        .bind(rejudge_triggered)
        .fetch_one(&mut *tx)
        .await?;

        self.event_bus
            .enqueue_in_tx(
                &mut tx,
                DomainEvent::AiJudgeJobCreated(AiJudgeJobCreatedEvent {
                    session_id,
                    job_id: job.id as u64,
                    requested_by: user.id as u64,
                    style_mode: style_mode.clone(),
                    rejudge_triggered,
                    requested_at: job.requested_at,
                }),
            )
            .await?;

        tx.commit().await?;
        self.trigger_judge_dispatch(JudgeDispatchTrigger {
            job_id: job.id,
            source: "event:judge_job_created",
        });

        Ok(RequestJudgeJobOutput {
            session_id,
            job_id: job.id as u64,
            status: job.status,
            style_mode: job.style_mode,
            style_mode_source: style_mode_source.to_string(),
            rejudge_triggered: job.rejudge_triggered,
            requested_at: job.requested_at,
            newly_created: true,
        })
    }

    pub async fn request_judge_job(
        &self,
        session_id: u64,
        user: &User,
        input: RequestJudgeJobInput,
    ) -> Result<RequestJudgeJobOutput, AppError> {
        self.request_judge_job_internal(session_id, user, input, true, false)
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
                style_mode: None,
                allow_rejudge: true,
            },
            false,
            true,
        )
        .await
    }
}
