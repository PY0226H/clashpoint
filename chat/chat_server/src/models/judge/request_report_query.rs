use super::*;
use crate::models::OpsPermission;
use std::collections::HashMap;

fn normalize_ops_review_limit(limit: Option<u32>) -> i64 {
    let requested = limit.unwrap_or(DEFAULT_OPS_JUDGE_REVIEW_LIMIT);
    requested.clamp(1, MAX_OPS_JUDGE_REVIEW_LIMIT) as i64
}

fn normalize_optional_winner_filter(winner: Option<String>) -> Result<Option<String>, AppError> {
    match winner {
        Some(value) => {
            let trimmed = value.trim();
            if trimmed.is_empty() {
                Ok(None)
            } else {
                Ok(Some(normalize_winner(trimmed, "winner")?))
            }
        }
        None => Ok(None),
    }
}

fn detect_ops_review_abnormal_flags(item: &JudgeReviewOpsItem) -> Vec<String> {
    let mut flags = Vec::new();
    if item.verdict_evidence_count == 0 {
        flags.push("missing_verdict_evidence_refs".to_string());
    }
    if item.winner != "draw" && item.score_gap <= 3 {
        flags.push("narrow_score_gap".to_string());
    }
    if item.winner == "draw" && !item.needs_draw_vote {
        flags.push("draw_without_vote_flow".to_string());
    }
    if let (Some(first), Some(second)) =
        (item.winner_first.as_deref(), item.winner_second.as_deref())
    {
        if first != second {
            flags.push("winner_inconsistent_between_two_passes".to_string());
        }
    }
    flags
}

impl AppState {
    pub async fn list_judge_reviews_by_owner(
        &self,
        user: &User,
        query: ListJudgeReviewOpsQuery,
    ) -> Result<ListJudgeReviewOpsOutput, AppError> {
        self.ensure_ops_permission(user, OpsPermission::JudgeReview)
            .await?;
        if let (Some(from), Some(to)) = (query.from, query.to) {
            if from > to {
                return Err(AppError::DebateError("from must be <= to".to_string()));
            }
        }

        let winner_filter = normalize_optional_winner_filter(query.winner)?;
        let row_limit = normalize_ops_review_limit(query.limit);
        let scan_limit = if query.anomaly_only {
            (row_limit * 4).min((MAX_OPS_JUDGE_REVIEW_LIMIT as i64) * 4)
        } else {
            row_limit
        };

        let rows: Vec<JudgeReviewOpsRow> = sqlx::query_as(
            r#"
            SELECT
                r.id AS report_id,
                r.session_id,
                r.job_id,
                r.winner,
                j.winner_first,
                j.winner_second,
                r.pro_score,
                r.con_score,
                r.style_mode,
                r.rubric_version,
                r.needs_draw_vote,
                r.rejudge_triggered,
                CASE
                    WHEN jsonb_typeof(r.payload->'verdictEvidenceRefs') = 'array'
                    THEN jsonb_array_length(r.payload->'verdictEvidenceRefs')
                    ELSE 0
                END AS verdict_evidence_count,
                r.created_at
            FROM judge_reports r
            JOIN judge_jobs j ON j.id = r.job_id
            WHERE ($1::timestamptz IS NULL OR r.created_at >= $1)
              AND ($2::timestamptz IS NULL OR r.created_at <= $2)
              AND ($3::varchar IS NULL OR r.winner = $3)
              AND ($4::boolean IS NULL OR r.rejudge_triggered = $4)
              AND (
                $5::boolean IS NULL
                OR (
                    CASE
                        WHEN jsonb_typeof(r.payload->'verdictEvidenceRefs') = 'array'
                        THEN jsonb_array_length(r.payload->'verdictEvidenceRefs') > 0
                        ELSE FALSE
                    END
                ) = $5
              )
            ORDER BY r.created_at DESC
            LIMIT $6
            "#,
        )
        .bind(query.from)
        .bind(query.to)
        .bind(winner_filter)
        .bind(query.rejudge_triggered)
        .bind(query.has_verdict_evidence)
        .bind(scan_limit)
        .fetch_all(&self.pool)
        .await?;

        let scanned_count = u32::try_from(rows.len()).unwrap_or(u32::MAX);
        let mut items = Vec::new();
        for row in rows {
            let verdict_evidence_count = if row.verdict_evidence_count <= 0 {
                0
            } else {
                u32::try_from(row.verdict_evidence_count).unwrap_or(u32::MAX)
            };
            let score_gap = row.pro_score.abs_diff(row.con_score) as i32;
            let mut item = JudgeReviewOpsItem {
                report_id: row.report_id as u64,
                session_id: row.session_id as u64,
                job_id: row.job_id as u64,
                winner: row.winner,
                winner_first: row.winner_first,
                winner_second: row.winner_second,
                pro_score: row.pro_score,
                con_score: row.con_score,
                score_gap,
                style_mode: row.style_mode,
                rubric_version: row.rubric_version,
                needs_draw_vote: row.needs_draw_vote,
                rejudge_triggered: row.rejudge_triggered,
                has_verdict_evidence: verdict_evidence_count > 0,
                verdict_evidence_count,
                abnormal_flags: Vec::new(),
                created_at: row.created_at,
            };
            item.abnormal_flags = detect_ops_review_abnormal_flags(&item);
            if query.anomaly_only && item.abnormal_flags.is_empty() {
                continue;
            }
            items.push(item);
            if i64::try_from(items.len()).unwrap_or(i64::MAX) >= row_limit {
                break;
            }
        }

        Ok(ListJudgeReviewOpsOutput {
            scanned_count,
            returned_count: u32::try_from(items.len()).unwrap_or(u32::MAX),
            items,
        })
    }

    pub async fn get_latest_judge_report(
        &self,
        session_id: u64,
        _user: &User,
        query: GetJudgeReportQuery,
    ) -> Result<GetJudgeReportOutput, AppError> {
        let session_exists = sqlx::query_scalar::<_, i32>(
            r#"
            SELECT 1
            FROM debate_sessions
            WHERE id = $1
            LIMIT 1
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&self.pool)
        .await?;
        if session_exists.is_none() {
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
                clarity_pro, clarity_con, pro_summary, con_summary, rationale, style_mode, rubric_version,
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
        let final_report_v3: Option<JudgeFinalReportRow> = sqlx::query_as(
            r#"
            SELECT
                id,
                final_job_id,
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
                created_at
            FROM judge_final_reports
            WHERE session_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            "#,
        )
        .bind(session_id as i64)
        .fetch_optional(&self.pool)
        .await?;

        let report = if let Some(report) = report {
            let verdict_refs = extract_verdict_evidence_refs(&report.payload);
            let verdict_evidence = if verdict_refs.is_empty() {
                Vec::new()
            } else {
                let message_ids: Vec<i64> = verdict_refs
                    .iter()
                    .map(|item| item.message_id as i64)
                    .collect();
                let message_rows: Vec<SessionMessageEvidenceRow> = sqlx::query_as(
                    r#"
                    SELECT id, side, content, created_at
                    FROM session_messages
                    WHERE session_id = $1 AND id = ANY($2)
                    "#,
                )
                .bind(session_id as i64)
                .bind(&message_ids)
                .fetch_all(&self.pool)
                .await?;
                let by_id: HashMap<u64, SessionMessageEvidenceRow> = message_rows
                    .into_iter()
                    .map(|row| (row.id as u64, row))
                    .collect();
                verdict_refs
                    .into_iter()
                    .filter_map(|item| {
                        let row = by_id.get(&item.message_id)?;
                        let side = if row.side.trim().is_empty() {
                            item.side.clone()
                        } else {
                            row.side.clone()
                        };
                        Some(JudgeVerdictEvidenceItem {
                            message_id: row.id as u64,
                            side,
                            role: item.role,
                            reason: item.reason,
                            content: row.content.clone(),
                            created_at: row.created_at,
                        })
                    })
                    .collect()
            };
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
                verdict_evidence,
                stage_summaries.into_iter().map(map_stage_summary).collect(),
                stage_summaries_meta,
            ))
        } else {
            None
        };

        let final_report_v3 = final_report_v3.map(map_final_report_detail);

        let status = if report.is_some() || final_report_v3.is_some() {
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
            final_report_v3,
        })
    }
}
