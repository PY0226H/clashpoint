use super::*;

impl AppState {
    pub async fn request_judge_job(
        &self,
        session_id: u64,
        user: &User,
        input: RequestJudgeJobInput,
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
            SELECT ws_id, status
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

        if session.ws_id != user.ws_id {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        }

        if !can_request_judge(&session.status) {
            return Err(AppError::DebateConflict(format!(
                "session {} is not in judging/closed status",
                session_id
            )));
        }

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
                ws_id, session_id, requested_by, status, style_mode, rejudge_triggered,
                requested_at, started_at, created_at, updated_at
            )
            VALUES ($1, $2, $3, 'running', $4, $5, NOW(), NULL, NOW(), NOW())
            RETURNING id, status, style_mode, rejudge_triggered, requested_at
            "#,
        )
        .bind(user.ws_id)
        .bind(session_id as i64)
        .bind(user.id)
        .bind(&style_mode)
        .bind(rejudge_triggered)
        .fetch_one(&mut *tx)
        .await?;

        tx.commit().await?;

        if let Err(err) = self
            .event_bus
            .publish_ai_judge_job_created(AiJudgeJobCreatedEvent {
                ws_id: user.ws_id as u64,
                session_id,
                job_id: job.id as u64,
                requested_by: user.id as u64,
                style_mode: style_mode.clone(),
                rejudge_triggered,
                requested_at: job.requested_at,
            })
            .await
        {
            warn!(
                session_id,
                user_id = user.id,
                "publish kafka ai judge job created failed: {}",
                err
            );
        }

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

    pub async fn get_latest_judge_report(
        &self,
        session_id: u64,
        user: &User,
        query: GetJudgeReportQuery,
    ) -> Result<GetJudgeReportOutput, AppError> {
        let session_ws_id: Option<(i64,)> = sqlx::query_as(
            r#"
            SELECT ws_id
            FROM debate_sessions
            WHERE id = $1
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&self.pool)
        .await?;
        let Some((session_ws_id,)) = session_ws_id else {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        };
        if session_ws_id != user.ws_id {
            return Err(AppError::NotFound(format!(
                "debate session id {session_id}"
            )));
        }

        let latest_job: Option<JudgeJobRow> = sqlx::query_as(
            r#"
            SELECT id, status, style_mode, rejudge_triggered, requested_at
            FROM judge_jobs
            WHERE session_id = $1
            ORDER BY requested_at DESC
            LIMIT 1
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&self.pool)
        .await?;

        let report: Option<JudgeReportRow> = sqlx::query_as(
            r#"
            SELECT
                id, job_id, winner, pro_score, con_score,
                logic_pro, logic_con, evidence_pro, evidence_con, rebuttal_pro, rebuttal_con,
                clarity_pro, clarity_con, pro_summary, con_summary, rationale, style_mode,
                needs_draw_vote, rejudge_triggered, payload, created_at
            FROM judge_reports
            WHERE session_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&self.pool)
        .await?;

        let report = if let Some(report) = report {
            let stage_limit = normalize_stage_summary_limit(query.max_stage_count);
            let stage_offset = normalize_stage_summary_offset(query.stage_offset);
            let total_stage_count: i64 = sqlx::query_scalar(
                r#"
                SELECT COUNT(*)::bigint
                FROM judge_stage_summaries
                WHERE job_id = $1
                "#,
            )
            .bind(report.job_id)
            .fetch_one(&self.pool)
            .await?;
            let stage_summaries: Vec<JudgeStageSummaryRow> = if let Some(limit) = stage_limit {
                sqlx::query_as(
                    r#"
                    SELECT
                        stage_no, from_message_id, to_message_id,
                        pro_score, con_score, summary, created_at
                    FROM judge_stage_summaries
                    WHERE job_id = $1
                    ORDER BY stage_no ASC, created_at ASC
                    LIMIT $2 OFFSET $3
                    "#,
                )
                .bind(report.job_id)
                .bind(limit)
                .bind(stage_offset)
                .fetch_all(&self.pool)
                .await?
            } else {
                sqlx::query_as(
                    r#"
                    SELECT
                        stage_no, from_message_id, to_message_id,
                        pro_score, con_score, summary, created_at
                    FROM judge_stage_summaries
                    WHERE job_id = $1
                    ORDER BY stage_no ASC, created_at ASC
                    OFFSET $2
                    "#,
                )
                .bind(report.job_id)
                .bind(stage_offset)
                .fetch_all(&self.pool)
                .await?
            };
            let returned_count = u32::try_from(stage_summaries.len()).unwrap_or(u32::MAX);
            let total_count = if total_stage_count <= 0 {
                0
            } else {
                u32::try_from(total_stage_count).unwrap_or(u32::MAX)
            };
            let stage_offset_u32 = u32::try_from(stage_offset).unwrap_or(u32::MAX);
            let effective_offset = stage_offset_u32.min(total_count);
            let consumed = effective_offset.saturating_add(returned_count);
            let has_more = consumed < total_count;
            let stage_summaries_meta = Some(JudgeStageSummariesMeta {
                total_count,
                returned_count,
                stage_offset: effective_offset,
                truncated: has_more,
                has_more,
                next_offset: if has_more { Some(consumed) } else { None },
                max_stage_count: stage_limit.map(|value| value as u32),
            });
            Some(map_report_detail(
                report,
                stage_summaries.into_iter().map(map_stage_summary).collect(),
                stage_summaries_meta,
            ))
        } else {
            None
        };

        let status = if report.is_some() {
            "ready".to_string()
        } else if let Some(job) = latest_job.as_ref() {
            if job.status == "failed" {
                "failed".to_string()
            } else {
                "pending".to_string()
            }
        } else {
            "absent".to_string()
        };

        Ok(GetJudgeReportOutput {
            session_id,
            status,
            latest_job: latest_job.map(|job| JudgeJobSnapshot {
                job_id: job.id as u64,
                status: job.status,
                style_mode: job.style_mode,
                rejudge_triggered: job.rejudge_triggered,
                requested_at: job.requested_at,
            }),
            report,
        })
    }
}
