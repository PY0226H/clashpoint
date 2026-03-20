use super::{
    AppError, DrawVoteDetail, DrawVoteRow, DrawVoteStatsRow, JudgeFinalReportDetail,
    JudgeFinalReportRow,
};
use serde_json::Value;

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

pub(super) fn map_final_report_detail(v: JudgeFinalReportRow) -> JudgeFinalReportDetail {
    JudgeFinalReportDetail {
        final_report_id: v.id as u64,
        final_job_id: v.final_job_id as u64,
        winner: v.winner,
        pro_score: v.pro_score,
        con_score: v.con_score,
        dimension_scores: v.dimension_scores,
        final_rationale: v.final_rationale,
        verdict_evidence_refs: value_array_or_empty(v.verdict_evidence_refs),
        phase_rollup_summary: value_array_or_empty(v.phase_rollup_summary),
        retrieval_snapshot_rollup: value_array_or_empty(v.retrieval_snapshot_rollup),
        winner_first: v.winner_first,
        winner_second: v.winner_second,
        rejudge_triggered: v.rejudge_triggered,
        needs_draw_vote: v.needs_draw_vote,
        judge_trace: v.judge_trace,
        audit_alerts: value_array_or_empty(v.audit_alerts),
        error_codes: value_string_array_or_empty(v.error_codes),
        degradation_level: v.degradation_level,
        created_at: v.created_at,
    }
}

fn value_array_or_empty(v: Value) -> Vec<Value> {
    match v {
        Value::Array(rows) => rows,
        _ => Vec::new(),
    }
}

fn value_string_array_or_empty(v: Value) -> Vec<String> {
    match v {
        Value::Array(rows) => rows
            .into_iter()
            .filter_map(|item| item.as_str().map(str::trim).map(ToString::to_string))
            .filter(|item| !item.is_empty())
            .collect(),
        _ => Vec::new(),
    }
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

pub(super) fn map_draw_vote_detail(
    vote: DrawVoteRow,
    stats: DrawVoteStatsRow,
    my_vote: Option<bool>,
) -> DrawVoteDetail {
    let decision_source = draw_vote_decision_source(&vote, &stats);
    DrawVoteDetail {
        vote_id: vote.id as u64,
        final_report_id: vote.final_report_id as u64,
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
