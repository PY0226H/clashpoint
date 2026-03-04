use super::{
    AppError, DrawVoteDetail, DrawVoteRow, DrawVoteStatsRow, JudgeRagMeta, JudgeRagSourceItem,
    JudgeReportDetail, JudgeReportRow, JudgeStageSummariesMeta, JudgeStageSummaryDetail,
    JudgeStageSummaryRow, JudgeVerdictEvidenceItem, MAX_STAGE_SUMMARY_COUNT,
    MAX_STAGE_SUMMARY_OFFSET, STYLE_ENTERTAINING, STYLE_MIXED, STYLE_RATIONAL,
};
use serde_json::Value;
use std::collections::HashSet;

const DEFAULT_RUBRIC_VERSION: &str = "v1-logic-evidence-rebuttal-clarity";
const MAX_VERDICT_EVIDENCE_REFS: usize = 12;

#[derive(Debug, Clone)]
pub(super) struct VerdictEvidenceRef {
    pub message_id: u64,
    pub side: String,
    pub role: Option<String>,
    pub reason: Option<String>,
}

pub(super) fn normalize_style_mode(style_mode: Option<String>) -> Result<String, AppError> {
    let raw = style_mode.unwrap_or_else(|| STYLE_RATIONAL.to_string());
    let mode = raw.trim().to_ascii_lowercase();
    if mode.is_empty() {
        return Err(AppError::DebateError(
            "style_mode cannot be empty".to_string(),
        ));
    }
    if matches!(
        mode.as_str(),
        STYLE_RATIONAL | STYLE_ENTERTAINING | STYLE_MIXED
    ) {
        Ok(mode)
    } else {
        Err(AppError::DebateError(format!(
            "invalid style_mode: {raw}, expect `rational` | `entertaining` | `mixed`"
        )))
    }
}

pub(super) fn can_request_judge(status: &str) -> bool {
    matches!(status, "judging" | "closed")
}

pub(super) fn normalize_winner(winner: &str, field: &str) -> Result<String, AppError> {
    let winner = winner.trim().to_ascii_lowercase();
    if matches!(winner.as_str(), "pro" | "con" | "draw") {
        Ok(winner)
    } else {
        Err(AppError::DebateError(format!(
            "invalid {field}: {winner}, expect `pro` | `con` | `draw`"
        )))
    }
}

pub(super) fn validate_score(score: i32, field: &str) -> Result<(), AppError> {
    if !(0..=100).contains(&score) {
        return Err(AppError::DebateError(format!(
            "invalid {field}: {score}, expect 0..=100"
        )));
    }
    Ok(())
}

pub(super) fn validate_non_empty_text(
    input: &str,
    field: &str,
    max_len: usize,
) -> Result<String, AppError> {
    let ret = input.trim();
    if ret.is_empty() {
        return Err(AppError::DebateError(format!("{field} cannot be empty")));
    }
    if ret.len() > max_len {
        return Err(AppError::DebateError(format!(
            "{field} too long, max {max_len} chars"
        )));
    }
    Ok(ret.to_string())
}

pub(super) fn map_report_detail(
    v: JudgeReportRow,
    verdict_evidence: Vec<JudgeVerdictEvidenceItem>,
    stage_summaries: Vec<JudgeStageSummaryDetail>,
    stage_summaries_meta: Option<JudgeStageSummariesMeta>,
) -> JudgeReportDetail {
    let rag = extract_rag_meta(&v.payload);
    JudgeReportDetail {
        report_id: v.id as u64,
        job_id: v.job_id as u64,
        winner: v.winner,
        pro_score: v.pro_score,
        con_score: v.con_score,
        logic_pro: v.logic_pro,
        logic_con: v.logic_con,
        evidence_pro: v.evidence_pro,
        evidence_con: v.evidence_con,
        rebuttal_pro: v.rebuttal_pro,
        rebuttal_con: v.rebuttal_con,
        clarity_pro: v.clarity_pro,
        clarity_con: v.clarity_con,
        pro_summary: v.pro_summary,
        con_summary: v.con_summary,
        rationale: v.rationale,
        style_mode: v.style_mode,
        rubric_version: v.rubric_version,
        needs_draw_vote: v.needs_draw_vote,
        rejudge_triggered: v.rejudge_triggered,
        payload: v.payload,
        rag,
        verdict_evidence,
        stage_summaries,
        stage_summaries_meta,
        created_at: v.created_at,
    }
}

pub(super) fn resolve_rubric_version(payload: &Value) -> String {
    payload
        .get("rubricVersion")
        .or_else(|| payload.get("rubric_version"))
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(|value| value.chars().take(128).collect())
        .unwrap_or_else(|| DEFAULT_RUBRIC_VERSION.to_string())
}

pub(super) fn extract_verdict_evidence_refs(payload: &Value) -> Vec<VerdictEvidenceRef> {
    let mut seen_ids: HashSet<u64> = HashSet::new();
    payload
        .get("verdictEvidenceRefs")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(|item| {
                    let message_id = item
                        .get("messageId")
                        .or_else(|| item.get("message_id"))
                        .and_then(Value::as_u64)?;
                    if message_id == 0 || !seen_ids.insert(message_id) {
                        return None;
                    }
                    let side = item
                        .get("side")
                        .and_then(Value::as_str)
                        .unwrap_or_default()
                        .trim()
                        .to_ascii_lowercase();
                    if side != "pro" && side != "con" {
                        return None;
                    }
                    Some(VerdictEvidenceRef {
                        message_id,
                        side,
                        role: optional_trimmed_text(item.get("role")),
                        reason: optional_trimmed_text(item.get("reason")),
                    })
                })
                .take(MAX_VERDICT_EVIDENCE_REFS)
                .collect()
        })
        .unwrap_or_default()
}

fn optional_trimmed_text(value: Option<&Value>) -> Option<String> {
    value
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|text| !text.is_empty())
        .map(ToString::to_string)
}

pub(super) fn map_stage_summary(v: JudgeStageSummaryRow) -> JudgeStageSummaryDetail {
    JudgeStageSummaryDetail {
        stage_no: v.stage_no,
        from_message_id: v.from_message_id.map(|value| value as u64),
        to_message_id: v.to_message_id.map(|value| value as u64),
        pro_score: v.pro_score,
        con_score: v.con_score,
        summary: v.summary,
        created_at: v.created_at,
    }
}

pub(super) fn extract_rag_meta(payload: &Value) -> Option<JudgeRagMeta> {
    let enabled = payload.get("ragEnabled").and_then(Value::as_bool);
    let used_by_model = payload.get("ragUsedByModel").and_then(Value::as_bool);
    let snippet_count = payload
        .get("ragSnippetCount")
        .and_then(Value::as_u64)
        .and_then(|v| u32::try_from(v).ok());
    let source_whitelist: Vec<String> = payload
        .get("ragSourceWhitelist")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(Value::as_str)
                .map(str::trim)
                .filter(|v| !v.is_empty())
                .map(ToString::to_string)
                .collect()
        })
        .unwrap_or_default();
    let sources: Vec<JudgeRagSourceItem> = payload
        .get("ragSources")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(|item| {
                    let chunk_id = item
                        .get("chunkId")
                        .and_then(Value::as_str)
                        .or_else(|| item.get("chunk_id").and_then(Value::as_str))
                        .unwrap_or_default()
                        .trim()
                        .to_string();
                    let title = item
                        .get("title")
                        .and_then(Value::as_str)
                        .unwrap_or_default()
                        .trim()
                        .to_string();
                    let source_url = item
                        .get("sourceUrl")
                        .and_then(Value::as_str)
                        .or_else(|| item.get("source_url").and_then(Value::as_str))
                        .unwrap_or_default()
                        .trim()
                        .to_string();
                    if chunk_id.is_empty() && title.is_empty() && source_url.is_empty() {
                        return None;
                    }
                    Some(JudgeRagSourceItem {
                        chunk_id,
                        title,
                        source_url,
                        score: item.get("score").and_then(Value::as_f64),
                    })
                })
                .collect()
        })
        .unwrap_or_default();
    if enabled.is_none()
        && used_by_model.is_none()
        && snippet_count.is_none()
        && source_whitelist.is_empty()
        && sources.is_empty()
    {
        return None;
    }
    Some(JudgeRagMeta {
        enabled,
        used_by_model,
        snippet_count,
        source_whitelist,
        sources,
    })
}

pub(super) fn calc_required_voters(eligible_voters: i32, threshold_percent: i32) -> i32 {
    if eligible_voters <= 0 {
        return 1;
    }
    let threshold = threshold_percent.clamp(1, 100) as i64;
    let eligible = eligible_voters as i64;
    ((eligible * threshold + 99) / 100) as i32
}

pub(super) fn majority_resolution(agree_votes: i32, disagree_votes: i32) -> &'static str {
    if agree_votes > disagree_votes {
        "accept_draw"
    } else {
        "open_rematch"
    }
}

pub(super) fn normalize_stage_summary_limit(limit: Option<u32>) -> Option<i64> {
    limit.map(|value| value.clamp(1, MAX_STAGE_SUMMARY_COUNT) as i64)
}

pub(super) fn normalize_stage_summary_offset(offset: Option<u32>) -> i64 {
    offset.unwrap_or(0).clamp(0, MAX_STAGE_SUMMARY_OFFSET) as i64
}

pub(super) fn map_draw_vote_detail(
    vote: DrawVoteRow,
    stats: DrawVoteStatsRow,
    my_vote: Option<bool>,
) -> DrawVoteDetail {
    let decision_source = draw_vote_decision_source(&vote, &stats);
    DrawVoteDetail {
        vote_id: vote.id as u64,
        report_id: vote.report_id as u64,
        status: vote.status,
        resolution: vote.resolution,
        decision_source: decision_source.to_string(),
        threshold_percent: vote.threshold_percent,
        eligible_voters: vote.eligible_voters,
        required_voters: vote.required_voters,
        participated_voters: stats.participated_voters,
        agree_votes: stats.agree_votes,
        disagree_votes: stats.disagree_votes,
        voting_ends_at: vote.voting_ends_at,
        decided_at: vote.decided_at,
        my_vote,
        rematch_session_id: vote.rematch_session_id.map(|v| v as u64),
    }
}

fn draw_vote_decision_source(vote: &DrawVoteRow, stats: &DrawVoteStatsRow) -> &'static str {
    match vote.status.as_str() {
        "decided" => "threshold_reached",
        "expired" => "vote_timeout",
        "open" => "pending",
        _ if stats.participated_voters >= vote.required_voters => "threshold_reached",
        _ if vote.decided_at.is_some() => "vote_timeout",
        _ => "pending",
    }
}
