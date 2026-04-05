use super::*;
use crate::test_fixtures::seed_judge_topic_and_session as fixture_seed_judge_topic_and_session;
use anyhow::Result;

async fn seed_topic_and_session(state: &AppState, status: &str) -> Result<i64> {
    fixture_seed_judge_topic_and_session(state, status, "topic-ai").await
}

mod phase_final_report_submit;
mod request_judge_job;
