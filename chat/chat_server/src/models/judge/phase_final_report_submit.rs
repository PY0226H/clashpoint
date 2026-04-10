use super::*;
use serde_json::{json, Value};
use std::collections::HashSet;

const MAX_PHASE_SUMMARY_TEXT_LEN: usize = 8000;
const MAX_PHASE_RATIONALE_TEXT_LEN: usize = 8000;
const MAX_FINAL_RATIONALE_TEXT_LEN: usize = 12000;
const MAX_ERROR_CODE_COUNT: usize = 64;

impl AppState {
    pub async fn submit_judge_phase_report(
        &self,
        job_id: u64,
        input: SubmitJudgePhaseReportInput,
    ) -> Result<SubmitJudgePhaseReportOutput, AppError> {
        let SubmitJudgePhaseReportInput {
            session_id,
            phase_no,
            message_start_id,
            message_end_id,
            message_count,
            pro_summary_grounded,
            con_summary_grounded,
            pro_retrieval_bundle,
            con_retrieval_bundle,
            agent1_score,
            agent2_score,
            agent3_weighted_score,
            prompt_hashes,
            token_usage,
            latency_ms,
            error_codes,
            degradation_level,
            judge_trace,
        } = input;

        if phase_no <= 0 {
            return Err(AppError::DebateError(format!(
                "invalid phase_no: {}, expect > 0",
                phase_no
            )));
        }
        if message_count <= 0 {
            return Err(AppError::DebateError(format!(
                "invalid message_count: {}, expect > 0",
                message_count
            )));
        }
        if message_start_id == 0 || message_end_id == 0 || message_start_id > message_end_id {
            return Err(AppError::DebateError(format!(
                "invalid message range: start={}, end={}",
                message_start_id, message_end_id
            )));
        }

        validate_non_empty_text(
            &pro_summary_grounded.text,
            "pro_summary_grounded.text",
            MAX_PHASE_SUMMARY_TEXT_LEN,
        )?;
        validate_non_empty_text(
            &con_summary_grounded.text,
            "con_summary_grounded.text",
            MAX_PHASE_SUMMARY_TEXT_LEN,
        )?;
        validate_message_ids(
            &pro_summary_grounded.message_ids,
            "pro_summary_grounded.message_ids",
        )?;
        validate_message_ids(
            &con_summary_grounded.message_ids,
            "con_summary_grounded.message_ids",
        )?;

        validate_percentage_score(agent1_score.pro, "agent1_score.pro")?;
        validate_percentage_score(agent1_score.con, "agent1_score.con")?;
        validate_non_empty_text(
            &agent1_score.rationale,
            "agent1_score.rationale",
            MAX_PHASE_RATIONALE_TEXT_LEN,
        )?;
        validate_percentage_score(agent2_score.pro, "agent2_score.pro")?;
        validate_percentage_score(agent2_score.con, "agent2_score.con")?;
        validate_non_empty_text(
            &agent2_score.rationale,
            "agent2_score.rationale",
            MAX_PHASE_RATIONALE_TEXT_LEN,
        )?;
        validate_percentage_score(agent3_weighted_score.pro, "agent3_weighted_score.pro")?;
        validate_percentage_score(agent3_weighted_score.con, "agent3_weighted_score.con")?;
        validate_ratio(agent3_weighted_score.w1, "agent3_weighted_score.w1")?;
        validate_ratio(agent3_weighted_score.w2, "agent3_weighted_score.w2")?;
        if agent3_weighted_score.w2 <= agent3_weighted_score.w1 {
            return Err(AppError::DebateError(format!(
                "invalid agent3 weights: w1={}, w2={}, expect w2 > w1",
                agent3_weighted_score.w1, agent3_weighted_score.w2
            )));
        }

        let error_codes = normalize_error_codes(error_codes);

        let mut tx = self.pool.begin().await?;
        let Some(job): Option<JudgePhaseJobForUpdate> = sqlx::query_as(
            r#"
            SELECT
                id,
                session_id,
                rejudge_run_no,
                phase_no,
                message_start_id,
                message_end_id,
                message_count,
                status
            FROM judge_phase_jobs
            WHERE id = $1
            FOR UPDATE
            "#,
        )
        .bind(job_id as i64)
        .fetch_optional(&mut *tx)
        .await?
        else {
            return Err(AppError::NotFound(format!("judge phase job id {job_id}")));
        };

        let existing_report_id: Option<i64> = sqlx::query_scalar(
            r#"
            SELECT id
            FROM judge_phase_reports
            WHERE phase_job_id = $1
            LIMIT 1
            "#,
        )
        .bind(job.id)
        .fetch_optional(&mut *tx)
        .await?;
        if existing_report_id.is_some() {
            tx.commit().await?;
            return Ok(SubmitJudgePhaseReportOutput {
                session_id,
                phase_no,
                status: "succeeded".to_string(),
            });
        }

        if job.status == "failed" {
            return Err(AppError::DebateConflict(format!(
                "judge phase job {} is failed, cannot submit report",
                job_id
            )));
        }
        if job.status != "dispatched" && job.status != "succeeded" {
            return Err(AppError::DebateConflict(format!(
                "judge phase job {} is not dispatched, current status {}",
                job_id, job.status
            )));
        }
        if session_id as i64 != job.session_id {
            return Err(AppError::DebateError(format!(
                "session_id mismatch: input={}, job={}",
                session_id, job.session_id
            )));
        }
        if phase_no != job.phase_no {
            return Err(AppError::DebateError(format!(
                "phase_no mismatch: input={}, job={}",
                phase_no, job.phase_no
            )));
        }
        if message_start_id as i64 != job.message_start_id
            || message_end_id as i64 != job.message_end_id
            || message_count != job.message_count
        {
            return Err(AppError::DebateError(format!(
                "message range mismatch: input=({},{},{}), job=({},{},{})",
                message_start_id,
                message_end_id,
                message_count,
                job.message_start_id,
                job.message_end_id,
                job.message_count
            )));
        }

        sqlx::query(
            r#"
            INSERT INTO judge_phase_reports(
                phase_job_id,
                session_id,
                rejudge_run_no,
                phase_no,
                message_start_id,
                message_end_id,
                message_count,
                pro_summary_grounded,
                con_summary_grounded,
                pro_retrieval_bundle,
                con_retrieval_bundle,
                agent1_score,
                agent2_score,
                agent3_weighted_score,
                prompt_hashes,
                token_usage,
                latency_ms,
                error_codes,
                degradation_level,
                judge_trace,
                created_at,
                updated_at
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7,
                $8, $9, $10, $11,
                $12, $13, $14,
                $15, $16, $17, $18,
                $19, $20, NOW(), NOW()
            )
            "#,
        )
        .bind(job.id)
        .bind(job.session_id)
        .bind(job.rejudge_run_no)
        .bind(job.phase_no)
        .bind(job.message_start_id)
        .bind(job.message_end_id)
        .bind(job.message_count)
        .bind(json!(pro_summary_grounded))
        .bind(json!(con_summary_grounded))
        .bind(json!(pro_retrieval_bundle))
        .bind(json!(con_retrieval_bundle))
        .bind(json!(agent1_score))
        .bind(json!(agent2_score))
        .bind(json!(agent3_weighted_score))
        .bind(non_null_json(prompt_hashes))
        .bind(non_null_json(token_usage))
        .bind(non_null_json(latency_ms))
        .bind(json!(error_codes))
        .bind(degradation_level)
        .bind(non_null_json(judge_trace))
        .execute(&mut *tx)
        .await?;

        sqlx::query(
            r#"
            UPDATE judge_phase_jobs
            SET status = 'succeeded',
                error_message = NULL,
                dispatch_locked_until = NULL,
                updated_at = NOW()
            WHERE id = $1
              AND status IN ('dispatched', 'succeeded')
            "#,
        )
        .bind(job.id)
        .execute(&mut *tx)
        .await?;

        tx.commit().await?;
        Ok(SubmitJudgePhaseReportOutput {
            session_id,
            phase_no,
            status: "succeeded".to_string(),
        })
    }

    pub async fn submit_judge_final_report(
        &self,
        job_id: u64,
        input: SubmitJudgeFinalReportInput,
    ) -> Result<SubmitJudgeFinalReportOutput, AppError> {
        let SubmitJudgeFinalReportInput {
            session_id,
            winner,
            pro_score,
            con_score,
            dimension_scores,
            final_rationale,
            verdict_evidence_refs,
            phase_rollup_summary,
            retrieval_snapshot_rollup,
            winner_first,
            winner_second,
            rejudge_triggered,
            needs_draw_vote,
            judge_trace,
            audit_alerts,
            error_codes,
            degradation_level,
        } = input;

        let winner = normalize_winner(&winner, "winner")?;
        let winner_first = match winner_first.as_deref() {
            Some(v) => Some(normalize_winner(v, "winner_first")?),
            None => None,
        };
        let winner_second = match winner_second.as_deref() {
            Some(v) => Some(normalize_winner(v, "winner_second")?),
            None => None,
        };
        validate_percentage_score(pro_score, "pro_score")?;
        validate_percentage_score(con_score, "con_score")?;
        validate_non_empty_text(
            &final_rationale,
            "final_rationale",
            MAX_FINAL_RATIONALE_TEXT_LEN,
        )?;
        let error_codes = normalize_error_codes(error_codes);

        let mut tx = self.pool.begin().await?;
        let Some(job): Option<JudgeFinalJobForUpdate> = sqlx::query_as(
            r#"
            SELECT
                id,
                session_id,
                rejudge_run_no,
                status
            FROM judge_final_jobs
            WHERE id = $1
            FOR UPDATE
            "#,
        )
        .bind(job_id as i64)
        .fetch_optional(&mut *tx)
        .await?
        else {
            return Err(AppError::NotFound(format!("judge final job id {job_id}")));
        };

        let existing_report_id: Option<i64> = sqlx::query_scalar(
            r#"
            SELECT id
            FROM judge_final_reports
            WHERE final_job_id = $1
            LIMIT 1
            "#,
        )
        .bind(job.id)
        .fetch_optional(&mut *tx)
        .await?;
        if existing_report_id.is_some() {
            tx.commit().await?;
            return Ok(SubmitJudgeFinalReportOutput {
                session_id,
                status: "succeeded".to_string(),
            });
        }

        if job.status == "failed" {
            return Err(AppError::DebateConflict(format!(
                "judge final job {} is failed, cannot submit report",
                job_id
            )));
        }
        if job.status != "dispatched" && job.status != "succeeded" {
            return Err(AppError::DebateConflict(format!(
                "judge final job {} is not dispatched, current status {}",
                job_id, job.status
            )));
        }
        if session_id as i64 != job.session_id {
            return Err(AppError::DebateError(format!(
                "session_id mismatch: input={}, job={}",
                session_id, job.session_id
            )));
        }

        let final_report_id: i64 = sqlx::query_scalar(
            r#"
            INSERT INTO judge_final_reports(
                final_job_id,
                session_id,
                rejudge_run_no,
                winner,
                pro_score,
                con_score,
                dimension_scores,
                final_rationale,
                verdict_evidence_refs,
                phase_rollup_summary,
                retrieval_snapshot_rollup,
                winner_first,
                winner_second,
                rejudge_triggered,
                needs_draw_vote,
                judge_trace,
                audit_alerts,
                error_codes,
                degradation_level,
                created_at,
                updated_at
            )
            VALUES (
                $1, $2, $3, $4, $5, $6,
                $7, $8, $9, $10, $11,
                $12, $13, $14, $15,
                $16, $17, $18, $19,
                NOW(), NOW()
            )
            RETURNING id
            "#,
        )
        .bind(job.id)
        .bind(job.session_id)
        .bind(job.rejudge_run_no)
        .bind(winner)
        .bind(pro_score)
        .bind(con_score)
        .bind(non_null_json(dimension_scores))
        .bind(final_rationale)
        .bind(json!(verdict_evidence_refs))
        .bind(json!(phase_rollup_summary))
        .bind(json!(retrieval_snapshot_rollup))
        .bind(winner_first)
        .bind(winner_second)
        .bind(rejudge_triggered)
        .bind(needs_draw_vote)
        .bind(non_null_json(judge_trace))
        .bind(json!(audit_alerts))
        .bind(json!(error_codes))
        .bind(degradation_level)
        .fetch_one(&mut *tx)
        .await?;

        if needs_draw_vote {
            AppState::create_draw_vote_for_report(&mut tx, job.session_id, final_report_id).await?;
        }

        sqlx::query(
            r#"
            UPDATE judge_final_jobs
            SET status = 'succeeded',
                error_message = NULL,
                error_code = NULL,
                contract_failure_type = NULL,
                dispatch_locked_until = NULL,
                updated_at = NOW()
            WHERE id = $1
              AND status IN ('dispatched', 'succeeded')
            "#,
        )
        .bind(job.id)
        .execute(&mut *tx)
        .await?;

        tx.commit().await?;
        Ok(SubmitJudgeFinalReportOutput {
            session_id,
            status: "succeeded".to_string(),
        })
    }
}

fn validate_percentage_score(score: f64, field: &str) -> Result<(), AppError> {
    if !score.is_finite() || !(0.0..=100.0).contains(&score) {
        return Err(AppError::DebateError(format!(
            "invalid {field}: {score}, expect finite number in 0..=100"
        )));
    }
    Ok(())
}

fn validate_ratio(score: f64, field: &str) -> Result<(), AppError> {
    if !score.is_finite() || !(0.0..=1.0).contains(&score) {
        return Err(AppError::DebateError(format!(
            "invalid {field}: {score}, expect finite number in 0..=1"
        )));
    }
    Ok(())
}

fn validate_message_ids(message_ids: &[u64], field: &str) -> Result<(), AppError> {
    if message_ids.is_empty() {
        return Err(AppError::DebateError(format!("{field} cannot be empty")));
    }
    if message_ids.contains(&0) {
        return Err(AppError::DebateError(format!(
            "{field} contains invalid message_id=0"
        )));
    }
    Ok(())
}

fn normalize_error_codes(raw: Vec<String>) -> Vec<String> {
    let mut seen = HashSet::new();
    raw.into_iter()
        .map(|code| code.trim().to_ascii_lowercase())
        .filter(|code| !code.is_empty())
        .filter(|code| seen.insert(code.clone()))
        .take(MAX_ERROR_CODE_COUNT)
        .collect()
}

fn non_null_json(v: Value) -> Value {
    if v.is_null() {
        json!({})
    } else {
        v
    }
}
