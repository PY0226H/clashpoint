use crate::{AiJudgeJobCreatedEvent, AppError, AppState, JudgeDispatchTrigger};
use chat_core::User;
use chrono::{DateTime, Utc};

mod draw_vote;
mod helpers;
mod phase_final_report_submit;
mod report_submit;
mod request_report;
mod request_report_query;
mod rows;
mod types;

use rows::*;
pub use types::*;

#[cfg(test)]
use helpers::extract_rag_meta;
use helpers::{
    calc_required_voters, can_request_judge, extract_verdict_evidence_refs, majority_resolution,
    map_draw_vote_detail, map_report_detail, map_stage_summary, normalize_stage_summary_limit,
    normalize_stage_summary_offset, normalize_style_mode, normalize_winner, resolve_rubric_version,
    validate_non_empty_text, validate_score,
};
use sqlx::{Postgres, Transaction};
use tracing::warn;

const STYLE_RATIONAL: &str = "rational";
const STYLE_ENTERTAINING: &str = "entertaining";
const STYLE_MIXED: &str = "mixed";
const STYLE_SOURCE_SYSTEM_CONFIG: &str = "system_config";
const STYLE_SOURCE_SYSTEM_CONFIG_FALLBACK_DEFAULT: &str = "system_config_fallback_default";
const STYLE_SOURCE_EXISTING_RUNNING_JOB: &str = "existing_running_job";
const DRAW_VOTE_THRESHOLD_PERCENT: i32 = 70;
const DRAW_VOTE_WINDOW_SECS: i64 = 300;
const REMATCH_DELAY_SECS: i64 = 600;
const REMATCH_MIN_DURATION_SECS: i64 = 900;
const REMATCH_MAX_DURATION_SECS: i64 = 14_400;
const MAX_STAGE_SUMMARY_COUNT: u32 = 200;
const MAX_STAGE_SUMMARY_OFFSET: u32 = 10_000;
const DEFAULT_OPS_JUDGE_REVIEW_LIMIT: u32 = 50;
const MAX_OPS_JUDGE_REVIEW_LIMIT: u32 = 200;

#[cfg(test)]
mod tests;
