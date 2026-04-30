use crate::{AppError, AppState, JudgeDispatchTrigger};
use chat_core::User;
use chrono::{DateTime, Utc};

mod assistant_advisory_proxy;
mod calibration_decision_ops_proxy;
mod challenge_ops_projection;
mod draw_vote;
mod helpers;
mod phase_final_report_submit;
mod request_report;
mod request_report_query;
mod rows;
mod runtime_readiness_ops_projection;
mod types;

use rows::*;
pub use types::*;

use helpers::{
    calc_required_voters, can_request_judge, majority_resolution, map_draw_vote_detail,
    map_final_report_detail, normalize_winner, validate_non_empty_text,
};
use sqlx::{Postgres, Transaction};
use tracing::warn;

const DRAW_VOTE_THRESHOLD_PERCENT: i32 = 70;
const DRAW_VOTE_WINDOW_SECS: i64 = 300;
const REMATCH_DELAY_SECS: i64 = 600;
const REMATCH_MIN_DURATION_SECS: i64 = 900;
const REMATCH_MAX_DURATION_SECS: i64 = 14_400;
const DEFAULT_OPS_JUDGE_REVIEW_LIMIT: u32 = 50;
const MAX_OPS_JUDGE_REVIEW_LIMIT: u32 = 200;

#[cfg(test)]
mod tests;
