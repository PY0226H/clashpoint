use super::*;
use std::collections::HashSet;

impl AppState {
    pub async fn submit_judge_report(
        &self,
        job_id: u64,
        input: SubmitJudgeReportInput,
    ) -> Result<SubmitJudgeReportOutput, AppError> {
        let winner = normalize_winner(&input.winner, "winner")?;
        let winner_first = match input.winner_first.as_deref() {
            Some(v) => Some(normalize_winner(v, "winner_first")?),
            None => None,
        };
        let winner_second = match input.winner_second.as_deref() {
            Some(v) => Some(normalize_winner(v, "winner_second")?),
            None => None,
        };
        let style_mode = normalize_style_mode(input.style_mode)?;
        let rubric_version = resolve_rubric_version(&input.payload);
        let pro_summary = validate_non_empty_text(&input.pro_summary, "pro_summary", 4000)?;
        let con_summary = validate_non_empty_text(&input.con_summary, "con_summary", 4000)?;
        let rationale = validate_non_empty_text(&input.rationale, "rationale", 4000)?;

        for (score, field) in [
            (input.pro_score, "pro_score"),
            (input.con_score, "con_score"),
            (input.logic_pro, "logic_pro"),
            (input.logic_con, "logic_con"),
            (input.evidence_pro, "evidence_pro"),
            (input.evidence_con, "evidence_con"),
            (input.rebuttal_pro, "rebuttal_pro"),
            (input.rebuttal_con, "rebuttal_con"),
            (input.clarity_pro, "clarity_pro"),
            (input.clarity_con, "clarity_con"),
        ] {
            validate_score(score, field)?;
        }

        let mut stage_no_set = HashSet::new();
        for stage in input.stage_summaries.iter() {
            if stage.stage_no <= 0 {
                return Err(AppError::DebateError(format!(
                    "invalid stage_no: {}, expect > 0",
                    stage.stage_no
                )));
            }
            if !stage_no_set.insert(stage.stage_no) {
                return Err(AppError::DebateError(format!(
                    "duplicated stage_no: {}",
                    stage.stage_no
                )));
            }
            validate_score(stage.pro_score, "stage.pro_score")?;
            validate_score(stage.con_score, "stage.con_score")?;
        }

        let mut tx = self.pool.begin().await?;
        let Some(job): Option<JudgeJobForUpdate> = sqlx::query_as(
            r#"
            SELECT id, ws_id, session_id, status, rejudge_triggered, error_message
            FROM judge_jobs
            WHERE id = $1
            FOR UPDATE
            "#,
        )
        .bind(job_id as i64)
        .fetch_optional(&mut *tx)
        .await?
        else {
            return Err(AppError::NotFound(format!("judge job id {job_id}")));
        };

        let existing_report: Option<JudgeReportRow> = sqlx::query_as(
            r#"
            SELECT
                id, job_id, winner, pro_score, con_score,
                logic_pro, logic_con, evidence_pro, evidence_con, rebuttal_pro, rebuttal_con,
                clarity_pro, clarity_con, pro_summary, con_summary, rationale, style_mode, rubric_version,
                needs_draw_vote, rejudge_triggered, payload, created_at
            FROM judge_reports
            WHERE job_id = $1
            LIMIT 1
            "#,
        )
        .bind(job_id as i64)
        .fetch_optional(&mut *tx)
        .await?;
        if let Some(report) = existing_report {
            tx.commit().await?;
            return Ok(SubmitJudgeReportOutput {
                job_id,
                session_id: job.session_id as u64,
                report_id: report.id as u64,
                status: "succeeded".to_string(),
                newly_created: false,
            });
        }

        if job.status != "running" {
            return Err(AppError::DebateConflict(format!(
                "judge job {} is not running, current status {}",
                job_id, job.status
            )));
        }

        let rejudge_triggered = input.rejudge_triggered || job.rejudge_triggered;
        let report_id: (i64,) = sqlx::query_as(
            r#"
            INSERT INTO judge_reports(
                ws_id, session_id, job_id, winner, pro_score, con_score,
                logic_pro, logic_con, evidence_pro, evidence_con, rebuttal_pro, rebuttal_con,
                clarity_pro, clarity_con, pro_summary, con_summary, rationale, style_mode, rubric_version,
                needs_draw_vote, rejudge_triggered, payload, created_at, updated_at
            )
            SELECT
                ws_id, session_id, id, $2, $3, $4,
                $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16, $17,
                $18, $19, $20, NOW(), NOW()
            FROM judge_jobs
            WHERE id = $1
            RETURNING id
            "#,
        )
        .bind(job_id as i64)
        .bind(&winner)
        .bind(input.pro_score)
        .bind(input.con_score)
        .bind(input.logic_pro)
        .bind(input.logic_con)
        .bind(input.evidence_pro)
        .bind(input.evidence_con)
        .bind(input.rebuttal_pro)
        .bind(input.rebuttal_con)
        .bind(input.clarity_pro)
        .bind(input.clarity_con)
        .bind(pro_summary)
        .bind(con_summary)
        .bind(rationale)
        .bind(style_mode.clone())
        .bind(rubric_version)
        .bind(input.needs_draw_vote)
        .bind(rejudge_triggered)
        .bind(input.payload)
        .fetch_one(&mut *tx)
        .await?;

        if input.needs_draw_vote {
            Self::create_draw_vote_for_report(&mut tx, job.ws_id, job.session_id, report_id.0)
                .await?;
        }

        for stage in input.stage_summaries.iter() {
            sqlx::query(
                r#"
                INSERT INTO judge_stage_summaries(
                    ws_id, session_id, job_id, stage_no, from_message_id, to_message_id,
                    pro_score, con_score, summary, created_at
                )
                SELECT
                    ws_id, session_id, id, $2, $3, $4, $5, $6, $7, NOW()
                FROM judge_jobs
                WHERE id = $1
                "#,
            )
            .bind(job_id as i64)
            .bind(stage.stage_no)
            .bind(stage.from_message_id.map(|v| v as i64))
            .bind(stage.to_message_id.map(|v| v as i64))
            .bind(stage.pro_score)
            .bind(stage.con_score)
            .bind(stage.summary.clone())
            .execute(&mut *tx)
            .await?;
        }

        sqlx::query(
            r#"
            UPDATE judge_jobs
            SET status = 'succeeded',
                style_mode = $2,
                winner_first = $3,
                winner_second = $4,
                error_message = NULL,
                finished_at = NOW(),
                updated_at = NOW()
            WHERE id = $1
            "#,
        )
        .bind(job_id as i64)
        .bind(style_mode)
        .bind(winner_first)
        .bind(winner_second)
        .execute(&mut *tx)
        .await?;

        tx.commit().await?;
        Ok(SubmitJudgeReportOutput {
            job_id,
            session_id: job.session_id as u64,
            report_id: report_id.0 as u64,
            status: "succeeded".to_string(),
            newly_created: true,
        })
    }

    pub async fn mark_judge_job_failed(
        &self,
        job_id: u64,
        input: MarkJudgeJobFailedInput,
    ) -> Result<MarkJudgeJobFailedOutput, AppError> {
        let error_message = validate_non_empty_text(&input.error_message, "error_message", 4000)?;
        let mut tx = self.pool.begin().await?;
        let Some(job): Option<JudgeJobForUpdate> = sqlx::query_as(
            r#"
            SELECT id, ws_id, session_id, status, rejudge_triggered, error_message
            FROM judge_jobs
            WHERE id = $1
            FOR UPDATE
            "#,
        )
        .bind(job_id as i64)
        .fetch_optional(&mut *tx)
        .await?
        else {
            return Err(AppError::NotFound(format!("judge job id {job_id}")));
        };
        let report_exists = sqlx::query_scalar::<_, i64>(
            r#"
            SELECT id
            FROM judge_reports
            WHERE job_id = $1
            LIMIT 1
            "#,
        )
        .bind(job.id)
        .fetch_optional(&mut *tx)
        .await?
        .is_some();
        if report_exists {
            return Err(AppError::DebateConflict(format!(
                "judge job {} already has report, cannot mark failed",
                job_id
            )));
        }

        if job.status == "failed" {
            tx.commit().await?;
            return Ok(MarkJudgeJobFailedOutput {
                job_id,
                session_id: job.session_id as u64,
                status: "failed".to_string(),
                error_message: job.error_message.unwrap_or(error_message),
                newly_marked: false,
            });
        }
        if job.status != "running" {
            return Err(AppError::DebateConflict(format!(
                "judge job {} is not running, current status {}",
                job_id, job.status
            )));
        }

        sqlx::query(
            r#"
            UPDATE judge_jobs
            SET status = 'failed',
                error_message = $2,
                finished_at = NOW(),
                updated_at = NOW()
            WHERE id = $1
            "#,
        )
        .bind(job.id)
        .bind(&error_message)
        .execute(&mut *tx)
        .await?;

        tx.commit().await?;
        Ok(MarkJudgeJobFailedOutput {
            job_id,
            session_id: job.session_id as u64,
            status: "failed".to_string(),
            error_message,
            newly_marked: true,
        })
    }
}
