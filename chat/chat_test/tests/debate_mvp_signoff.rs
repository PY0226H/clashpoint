use anyhow::Result;
use axum::Router;
use chat_server::{
    AppState, CreateDebateMessageInput, DebateMessage, DebateSessionSummary, DebateTopic,
    GetDrawVoteOutput, GetJudgeReportOutput, JoinDebateSessionOutput, OpsCreateDebateSessionInput,
    OpsCreateDebateTopicInput, OpsUpdateDebateSessionInput, PinDebateMessageInput,
    PinDebateMessageOutput, RequestJudgeJobInput, RequestJudgeJobOutput, SubmitDrawVoteInput,
    SubmitDrawVoteOutput, SubmitJudgeReportInput, VerifyIapOrderInput, VerifyIapOrderOutput,
};
use reqwest::{Client, StatusCode};
use serde::de::DeserializeOwned;
use serde::Deserialize;
use std::net::SocketAddr;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::net::TcpListener;

const WILD_ADDR: &str = "0.0.0.0:0";

#[derive(Debug, Deserialize)]
struct AuthToken {
    token: String,
}

struct TestServer {
    addr: SocketAddr,
    http: Client,
}

#[derive(Clone)]
struct ApiSession {
    addr: SocketAddr,
    http: Client,
    token: String,
}

#[tokio::test]
async fn debate_mvp_signoff_should_cover_core_flow() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let server = TestServer::new(state.clone()).await?;

    let now_ms = SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis();
    let workspace = format!("mvp-signoff-{now_ms}");
    let owner_email = format!("owner-{now_ms}@acme.org");
    let challenger_email = format!("challenger-{now_ms}@acme.org");

    let owner = server
        .signup(&workspace, "Owner One", &owner_email, "123456")
        .await?;
    let challenger = server
        .signup(&workspace, "Challenger Two", &challenger_email, "123456")
        .await?;

    let topic: DebateTopic = owner
        .post(
            "/api/debate/ops/topics",
            &OpsCreateDebateTopicInput {
                title: "云顶之弈版本平衡争议".to_string(),
                description: "当前版本是否过度依赖特定阵容。".to_string(),
                category: "game".to_string(),
                stance_pro: "是，环境失衡".to_string(),
                stance_con: "否，策略仍多样".to_string(),
                context_seed: Some("MVP signoff seed".to_string()),
                is_active: true,
            },
            StatusCode::CREATED,
        )
        .await?;
    assert!(topic.id > 0);

    let session: DebateSessionSummary = owner
        .post(
            "/api/debate/ops/sessions",
            &OpsCreateDebateSessionInput {
                topic_id: topic.id as u64,
                status: Some("open".to_string()),
                scheduled_start_at: "2025-01-01T00:00:00Z".parse()?,
                end_at: "2099-01-01T01:00:00Z".parse()?,
                max_participants_per_side: Some(200),
            },
            StatusCode::CREATED,
        )
        .await?;
    assert_eq!(session.topic_id, topic.id);
    assert_eq!(session.status, "open");

    let join_owner: JoinDebateSessionOutput = owner
        .post(
            format!("/api/debate/sessions/{}/join", session.id).as_str(),
            &serde_json::json!({ "side": "pro" }),
            StatusCode::OK,
        )
        .await?;
    assert_eq!(join_owner.side, "pro");

    let join_challenger: JoinDebateSessionOutput = challenger
        .post(
            format!("/api/debate/sessions/{}/join", session.id).as_str(),
            &serde_json::json!({ "side": "con" }),
            StatusCode::OK,
        )
        .await?;
    assert_eq!(join_challenger.side, "con");

    let message: DebateMessage = owner
        .post(
            format!("/api/debate/sessions/{}/messages", session.id).as_str(),
            &CreateDebateMessageInput {
                content: "我认为当前版本头部阵容过于集中，需要平衡。".to_string(),
            },
            StatusCode::CREATED,
        )
        .await?;
    assert_eq!(message.session_id, session.id);

    let tx_id = format!("tx-{now_ms}");
    let verify: VerifyIapOrderOutput = owner
        .post(
            "/api/pay/iap/verify",
            &VerifyIapOrderInput {
                product_id: "com.aicomm.coins.60".to_string(),
                transaction_id: tx_id.clone(),
                original_transaction_id: None,
                receipt_data: format!("mock_ok_{now_ms}"),
            },
            StatusCode::OK,
        )
        .await?;
    assert_eq!(verify.status, "verified");
    assert!(verify.credited);
    assert!(verify.wallet_balance >= i64::from(verify.coins));

    let pin: PinDebateMessageOutput = owner
        .post(
            format!("/api/debate/messages/{}/pin", message.id).as_str(),
            &PinDebateMessageInput {
                pin_seconds: 60,
                idempotency_key: format!("pin-{now_ms}"),
            },
            StatusCode::OK,
        )
        .await?;
    assert_eq!(pin.session_id, session.id as u64);
    assert!(pin.debited_coins > 0);

    let closed_session: DebateSessionSummary = owner
        .put(
            format!("/api/debate/ops/sessions/{}", session.id).as_str(),
            &OpsUpdateDebateSessionInput {
                status: Some("closed".to_string()),
                scheduled_start_at: None,
                end_at: None,
                max_participants_per_side: None,
            },
            StatusCode::OK,
        )
        .await?;
    assert_eq!(closed_session.status, "closed");

    let job: RequestJudgeJobOutput = owner
        .post(
            format!("/api/debate/sessions/{}/judge/jobs", session.id).as_str(),
            &RequestJudgeJobInput {
                style_mode: None,
                allow_rejudge: false,
            },
            StatusCode::ACCEPTED,
        )
        .await?;
    assert_eq!(job.session_id, session.id as u64);
    assert_eq!(job.status, "running");

    let submit_ret = state
        .submit_judge_report(
            job.job_id,
            SubmitJudgeReportInput {
                winner: "pro".to_string(),
                pro_score: 86,
                con_score: 78,
                logic_pro: 85,
                logic_con: 76,
                evidence_pro: 88,
                evidence_con: 79,
                rebuttal_pro: 84,
                rebuttal_con: 77,
                clarity_pro: 87,
                clarity_con: 80,
                pro_summary: "正方在证据完整性上更优。".to_string(),
                con_summary: "反方反驳有效，但证据链不足。".to_string(),
                rationale: "综合四维评分，正方胜出。".to_string(),
                style_mode: Some("rational".to_string()),
                needs_draw_vote: false,
                rejudge_triggered: false,
                payload: serde_json::json!({"source":"mvp-signoff-test"}),
                winner_first: Some("pro".to_string()),
                winner_second: Some("pro".to_string()),
                stage_summaries: vec![],
            },
        )
        .await?;
    assert_eq!(submit_ret.status, "succeeded");

    let report: GetJudgeReportOutput = owner
        .get(
            format!("/api/debate/sessions/{}/judge-report", session.id).as_str(),
            StatusCode::OK,
        )
        .await?;
    assert_eq!(report.session_id, session.id as u64);
    assert_eq!(report.status, "ready");
    let detail = report.report.expect("judge report should exist");
    assert_eq!(detail.winner, "pro");

    Ok(())
}

#[tokio::test]
async fn debate_mvp_signoff_should_cover_draw_vote_and_rematch_flow() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let server = TestServer::new(state.clone()).await?;

    let now_ms = SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis();
    let workspace = format!("mvp-draw-signoff-{now_ms}");

    let owner = server
        .signup(
            &workspace,
            "Owner Draw",
            &format!("owner-draw-{now_ms}@acme.org"),
            "123456",
        )
        .await?;
    let user2 = server
        .signup(
            &workspace,
            "User Draw 2",
            &format!("u2-draw-{now_ms}@acme.org"),
            "123456",
        )
        .await?;
    let user3 = server
        .signup(
            &workspace,
            "User Draw 3",
            &format!("u3-draw-{now_ms}@acme.org"),
            "123456",
        )
        .await?;

    let topic: DebateTopic = owner
        .post(
            "/api/debate/ops/topics",
            &OpsCreateDebateTopicInput {
                title: "平局投票是否应该开启二番战".to_string(),
                description: "测试 draw vote 到 rematch 的完整闭环。".to_string(),
                category: "game".to_string(),
                stance_pro: "应该开启".to_string(),
                stance_con: "不应开启".to_string(),
                context_seed: Some("MVP draw vote signoff seed".to_string()),
                is_active: true,
            },
            StatusCode::CREATED,
        )
        .await?;

    let session: DebateSessionSummary = owner
        .post(
            "/api/debate/ops/sessions",
            &OpsCreateDebateSessionInput {
                topic_id: topic.id as u64,
                status: Some("open".to_string()),
                scheduled_start_at: "2025-02-01T00:00:00Z".parse()?,
                end_at: "2099-02-01T01:00:00Z".parse()?,
                max_participants_per_side: Some(500),
            },
            StatusCode::CREATED,
        )
        .await?;

    let _: JoinDebateSessionOutput = owner
        .post(
            format!("/api/debate/sessions/{}/join", session.id).as_str(),
            &serde_json::json!({ "side": "pro" }),
            StatusCode::OK,
        )
        .await?;
    let _: JoinDebateSessionOutput = user2
        .post(
            format!("/api/debate/sessions/{}/join", session.id).as_str(),
            &serde_json::json!({ "side": "con" }),
            StatusCode::OK,
        )
        .await?;
    let _: JoinDebateSessionOutput = user3
        .post(
            format!("/api/debate/sessions/{}/join", session.id).as_str(),
            &serde_json::json!({ "side": "con" }),
            StatusCode::OK,
        )
        .await?;

    let _: DebateMessage = owner
        .post(
            format!("/api/debate/sessions/{}/messages", session.id).as_str(),
            &CreateDebateMessageInput {
                content: "这条消息用于触发判决流程。".to_string(),
            },
            StatusCode::CREATED,
        )
        .await?;

    let _: DebateSessionSummary = owner
        .put(
            format!("/api/debate/ops/sessions/{}", session.id).as_str(),
            &OpsUpdateDebateSessionInput {
                status: Some("closed".to_string()),
                scheduled_start_at: None,
                end_at: None,
                max_participants_per_side: None,
            },
            StatusCode::OK,
        )
        .await?;

    let job: RequestJudgeJobOutput = owner
        .post(
            format!("/api/debate/sessions/{}/judge/jobs", session.id).as_str(),
            &RequestJudgeJobInput {
                style_mode: None,
                allow_rejudge: false,
            },
            StatusCode::ACCEPTED,
        )
        .await?;
    assert_eq!(job.status, "running");

    let _ = state
        .submit_judge_report(
            job.job_id,
            SubmitJudgeReportInput {
                winner: "pro".to_string(),
                pro_score: 82,
                con_score: 82,
                logic_pro: 82,
                logic_con: 82,
                evidence_pro: 82,
                evidence_con: 82,
                rebuttal_pro: 82,
                rebuttal_con: 82,
                clarity_pro: 82,
                clarity_con: 82,
                pro_summary: "双方表现接近。".to_string(),
                con_summary: "双方表现接近。".to_string(),
                rationale: "触发平局投票流程验证。".to_string(),
                style_mode: Some("rational".to_string()),
                needs_draw_vote: true,
                rejudge_triggered: false,
                payload: serde_json::json!({"source":"mvp-draw-signoff-test"}),
                winner_first: Some("pro".to_string()),
                winner_second: Some("pro".to_string()),
                stage_summaries: vec![],
            },
        )
        .await?;

    let vote_before: GetDrawVoteOutput = owner
        .get(
            format!("/api/debate/sessions/{}/draw-vote", session.id).as_str(),
            StatusCode::OK,
        )
        .await?;
    assert_eq!(vote_before.status, "open");
    let vote_detail_before = vote_before.vote.expect("draw vote should exist");
    assert_eq!(vote_detail_before.eligible_voters, 3);
    assert_eq!(vote_detail_before.required_voters, 3);
    assert_eq!(vote_detail_before.decision_source, "pending");

    let _: SubmitDrawVoteOutput = owner
        .post(
            format!("/api/debate/sessions/{}/draw-vote/ballots", session.id).as_str(),
            &SubmitDrawVoteInput { agree_draw: false },
            StatusCode::OK,
        )
        .await?;
    let _: SubmitDrawVoteOutput = user2
        .post(
            format!("/api/debate/sessions/{}/draw-vote/ballots", session.id).as_str(),
            &SubmitDrawVoteInput { agree_draw: false },
            StatusCode::OK,
        )
        .await?;
    let final_vote_submit: SubmitDrawVoteOutput = user3
        .post(
            format!("/api/debate/sessions/{}/draw-vote/ballots", session.id).as_str(),
            &SubmitDrawVoteInput { agree_draw: true },
            StatusCode::OK,
        )
        .await?;
    assert_eq!(final_vote_submit.status, "decided");
    assert_eq!(final_vote_submit.vote.resolution, "open_rematch");
    assert_eq!(final_vote_submit.vote.decision_source, "threshold_reached");
    assert_eq!(final_vote_submit.vote.agree_votes, 1);
    assert_eq!(final_vote_submit.vote.disagree_votes, 2);
    let rematch_session_id = final_vote_submit
        .vote
        .rematch_session_id
        .expect("open_rematch should create rematch session");

    let vote_after: GetDrawVoteOutput = owner
        .get(
            format!("/api/debate/sessions/{}/draw-vote", session.id).as_str(),
            StatusCode::OK,
        )
        .await?;
    assert_eq!(vote_after.status, "decided");
    let vote_detail_after = vote_after.vote.expect("draw vote should still exist");
    assert_eq!(vote_detail_after.resolution, "open_rematch");
    assert_eq!(vote_detail_after.decision_source, "threshold_reached");
    assert_eq!(
        vote_detail_after.rematch_session_id,
        Some(rematch_session_id)
    );

    let sessions_after: Vec<DebateSessionSummary> = owner
        .get(
            format!("/api/debate/sessions?topicId={}&limit=200", topic.id).as_str(),
            StatusCode::OK,
        )
        .await?;
    let rematch = sessions_after
        .iter()
        .find(|item| item.id as u64 == rematch_session_id)
        .expect("rematch session should be queryable via sessions API");
    assert_eq!(rematch.status, "scheduled");

    Ok(())
}

#[tokio::test]
async fn debate_mvp_signoff_should_cover_accept_draw_without_rematch() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let server = TestServer::new(state.clone()).await?;

    let now_ms = SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis();
    let workspace = format!("mvp-accept-{now_ms}");

    let owner = server
        .signup(
            &workspace,
            "Owner Accept Draw",
            &format!("owner-accept-{now_ms}@acme.org"),
            "123456",
        )
        .await?;
    let user2 = server
        .signup(
            &workspace,
            "User Accept 2",
            &format!("u2-accept-{now_ms}@acme.org"),
            "123456",
        )
        .await?;
    let user3 = server
        .signup(
            &workspace,
            "User Accept 3",
            &format!("u3-accept-{now_ms}@acme.org"),
            "123456",
        )
        .await?;

    let topic: DebateTopic = owner
        .post(
            "/api/debate/ops/topics",
            &OpsCreateDebateTopicInput {
                title: "平局后是否直接结束".to_string(),
                description: "测试 accept_draw 分支不生成二番战。".to_string(),
                category: "game".to_string(),
                stance_pro: "应直接结束".to_string(),
                stance_con: "应继续二番战".to_string(),
                context_seed: Some("MVP accept draw signoff seed".to_string()),
                is_active: true,
            },
            StatusCode::CREATED,
        )
        .await?;

    let session: DebateSessionSummary = owner
        .post(
            "/api/debate/ops/sessions",
            &OpsCreateDebateSessionInput {
                topic_id: topic.id as u64,
                status: Some("open".to_string()),
                scheduled_start_at: "2025-03-01T00:00:00Z".parse()?,
                end_at: "2099-03-01T01:00:00Z".parse()?,
                max_participants_per_side: Some(500),
            },
            StatusCode::CREATED,
        )
        .await?;

    let _: JoinDebateSessionOutput = owner
        .post(
            format!("/api/debate/sessions/{}/join", session.id).as_str(),
            &serde_json::json!({ "side": "pro" }),
            StatusCode::OK,
        )
        .await?;
    let _: JoinDebateSessionOutput = user2
        .post(
            format!("/api/debate/sessions/{}/join", session.id).as_str(),
            &serde_json::json!({ "side": "con" }),
            StatusCode::OK,
        )
        .await?;
    let _: JoinDebateSessionOutput = user3
        .post(
            format!("/api/debate/sessions/{}/join", session.id).as_str(),
            &serde_json::json!({ "side": "pro" }),
            StatusCode::OK,
        )
        .await?;

    let _: DebateMessage = owner
        .post(
            format!("/api/debate/sessions/{}/messages", session.id).as_str(),
            &CreateDebateMessageInput {
                content: "这条消息用于触发平局投票接受路径。".to_string(),
            },
            StatusCode::CREATED,
        )
        .await?;

    let _: DebateSessionSummary = owner
        .put(
            format!("/api/debate/ops/sessions/{}", session.id).as_str(),
            &OpsUpdateDebateSessionInput {
                status: Some("closed".to_string()),
                scheduled_start_at: None,
                end_at: None,
                max_participants_per_side: None,
            },
            StatusCode::OK,
        )
        .await?;

    let job: RequestJudgeJobOutput = owner
        .post(
            format!("/api/debate/sessions/{}/judge/jobs", session.id).as_str(),
            &RequestJudgeJobInput {
                style_mode: None,
                allow_rejudge: false,
            },
            StatusCode::ACCEPTED,
        )
        .await?;

    let _ = state
        .submit_judge_report(
            job.job_id,
            SubmitJudgeReportInput {
                winner: "con".to_string(),
                pro_score: 80,
                con_score: 80,
                logic_pro: 80,
                logic_con: 80,
                evidence_pro: 80,
                evidence_con: 80,
                rebuttal_pro: 80,
                rebuttal_con: 80,
                clarity_pro: 80,
                clarity_con: 80,
                pro_summary: "双方表现接近。".to_string(),
                con_summary: "双方表现接近。".to_string(),
                rationale: "触发平局投票 accept_draw 分支。".to_string(),
                style_mode: Some("rational".to_string()),
                needs_draw_vote: true,
                rejudge_triggered: false,
                payload: serde_json::json!({"source":"mvp-accept-draw-signoff-test"}),
                winner_first: Some("con".to_string()),
                winner_second: Some("con".to_string()),
                stage_summaries: vec![],
            },
        )
        .await?;

    let vote_before: GetDrawVoteOutput = owner
        .get(
            format!("/api/debate/sessions/{}/draw-vote", session.id).as_str(),
            StatusCode::OK,
        )
        .await?;
    assert_eq!(vote_before.status, "open");
    let vote_detail_before = vote_before.vote.expect("draw vote should exist");
    assert_eq!(vote_detail_before.required_voters, 3);
    assert_eq!(vote_detail_before.decision_source, "pending");

    let _: SubmitDrawVoteOutput = owner
        .post(
            format!("/api/debate/sessions/{}/draw-vote/ballots", session.id).as_str(),
            &SubmitDrawVoteInput { agree_draw: true },
            StatusCode::OK,
        )
        .await?;
    let _: SubmitDrawVoteOutput = user2
        .post(
            format!("/api/debate/sessions/{}/draw-vote/ballots", session.id).as_str(),
            &SubmitDrawVoteInput { agree_draw: true },
            StatusCode::OK,
        )
        .await?;
    let final_vote_submit: SubmitDrawVoteOutput = user3
        .post(
            format!("/api/debate/sessions/{}/draw-vote/ballots", session.id).as_str(),
            &SubmitDrawVoteInput { agree_draw: false },
            StatusCode::OK,
        )
        .await?;
    assert_eq!(final_vote_submit.status, "decided");
    assert_eq!(final_vote_submit.vote.resolution, "accept_draw");
    assert_eq!(final_vote_submit.vote.decision_source, "threshold_reached");
    assert_eq!(final_vote_submit.vote.agree_votes, 2);
    assert_eq!(final_vote_submit.vote.disagree_votes, 1);
    assert_eq!(final_vote_submit.vote.rematch_session_id, None);

    let vote_after: GetDrawVoteOutput = owner
        .get(
            format!("/api/debate/sessions/{}/draw-vote", session.id).as_str(),
            StatusCode::OK,
        )
        .await?;
    assert_eq!(vote_after.status, "decided");
    let vote_detail_after = vote_after.vote.expect("draw vote should still exist");
    assert_eq!(vote_detail_after.resolution, "accept_draw");
    assert_eq!(vote_detail_after.decision_source, "threshold_reached");
    assert_eq!(vote_detail_after.rematch_session_id, None);

    let sessions_after: Vec<DebateSessionSummary> = owner
        .get(
            format!("/api/debate/sessions?topicId={}&limit=200", topic.id).as_str(),
            StatusCode::OK,
        )
        .await?;
    assert_eq!(sessions_after.len(), 1);
    assert_eq!(sessions_after[0].id, session.id);

    Ok(())
}

#[tokio::test]
async fn debate_ops_should_reject_non_owner_management_actions() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let server = TestServer::new(state.clone()).await?;

    let now_ms = SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis();
    let workspace = format!("mvp-ops-perm-{now_ms}");
    let owner_email = format!("owner-ops-{now_ms}@acme.org");
    let member_email = format!("member-ops-{now_ms}@acme.org");

    let owner = server
        .signup(&workspace, "Owner Ops", &owner_email, "123456")
        .await?;
    let member = server
        .signup(&workspace, "Member Ops", &member_email, "123456")
        .await?;

    let topic: DebateTopic = owner
        .post(
            "/api/debate/ops/topics",
            &OpsCreateDebateTopicInput {
                title: "权限校验辩题".to_string(),
                description: "用于验证非 owner 权限限制".to_string(),
                category: "game".to_string(),
                stance_pro: "应限制".to_string(),
                stance_con: "可放开".to_string(),
                context_seed: Some("ops permission seed".to_string()),
                is_active: true,
            },
            StatusCode::CREATED,
        )
        .await?;

    let session: DebateSessionSummary = owner
        .post(
            "/api/debate/ops/sessions",
            &OpsCreateDebateSessionInput {
                topic_id: topic.id as u64,
                status: Some("scheduled".to_string()),
                scheduled_start_at: "2099-01-02T00:00:00Z".parse()?,
                end_at: "2099-01-02T01:00:00Z".parse()?,
                max_participants_per_side: Some(200),
            },
            StatusCode::CREATED,
        )
        .await?;

    let create_topic_error: serde_json::Value = member
        .post(
            "/api/debate/ops/topics",
            &OpsCreateDebateTopicInput {
                title: "member create topic".to_string(),
                description: "should fail".to_string(),
                category: "game".to_string(),
                stance_pro: "pro".to_string(),
                stance_con: "con".to_string(),
                context_seed: None,
                is_active: true,
            },
            StatusCode::CONFLICT,
        )
        .await?;
    assert!(create_topic_error
        .to_string()
        .contains("only workspace owner can manage debate operations"));

    let update_topic_error: serde_json::Value = member
        .put(
            format!("/api/debate/ops/topics/{}", topic.id).as_str(),
            &serde_json::json!({
                "title": "member update topic",
                "description": "should fail",
                "category": "game",
                "stancePro": "pro",
                "stanceCon": "con",
                "contextSeed": null,
                "isActive": true
            }),
            StatusCode::CONFLICT,
        )
        .await?;
    assert!(update_topic_error
        .to_string()
        .contains("only workspace owner can manage debate operations"));

    let create_session_error: serde_json::Value = member
        .post(
            "/api/debate/ops/sessions",
            &OpsCreateDebateSessionInput {
                topic_id: topic.id as u64,
                status: Some("open".to_string()),
                scheduled_start_at: "2099-01-02T00:00:00Z".parse()?,
                end_at: "2099-01-02T01:00:00Z".parse()?,
                max_participants_per_side: Some(200),
            },
            StatusCode::CONFLICT,
        )
        .await?;
    assert!(create_session_error
        .to_string()
        .contains("only workspace owner can manage debate operations"));

    let update_session_error: serde_json::Value = member
        .put(
            format!("/api/debate/ops/sessions/{}", session.id).as_str(),
            &OpsUpdateDebateSessionInput {
                status: Some("open".to_string()),
                scheduled_start_at: None,
                end_at: None,
                max_participants_per_side: None,
            },
            StatusCode::CONFLICT,
        )
        .await?;
    assert!(update_session_error
        .to_string()
        .contains("only workspace owner can manage debate operations"));

    Ok(())
}

impl TestServer {
    async fn new(state: AppState) -> Result<Self> {
        let app: Router = chat_server::get_router(state).await?;
        let listener = TcpListener::bind(WILD_ADDR).await?;
        let addr = listener.local_addr()?;
        tokio::spawn(async move {
            axum::serve(listener, app.into_make_service())
                .await
                .expect("chat server should run");
        });
        Ok(Self {
            addr,
            http: Client::new(),
        })
    }

    async fn signup(
        &self,
        workspace: &str,
        fullname: &str,
        email: &str,
        password: &str,
    ) -> Result<ApiSession> {
        let res = self
            .http
            .post(format!("http://{}{}", self.addr, "/api/signup"))
            .json(&serde_json::json!({
                "workspace": workspace,
                "fullname": fullname,
                "email": email,
                "password": password,
            }))
            .send()
            .await?;
        assert_eq!(res.status(), StatusCode::CREATED);
        let auth: AuthToken = res.json().await?;
        Ok(ApiSession {
            addr: self.addr,
            http: self.http.clone(),
            token: auth.token,
        })
    }
}

impl ApiSession {
    async fn post<T, R>(&self, path: &str, payload: &T, expected: StatusCode) -> Result<R>
    where
        T: serde::Serialize + ?Sized,
        R: DeserializeOwned,
    {
        let res = self
            .http
            .post(format!("http://{}{}", self.addr, path))
            .header("Authorization", format!("Bearer {}", self.token))
            .json(payload)
            .send()
            .await?;
        assert_eq!(res.status(), expected, "path={path}");
        Ok(res.json::<R>().await?)
    }

    async fn put<T, R>(&self, path: &str, payload: &T, expected: StatusCode) -> Result<R>
    where
        T: serde::Serialize + ?Sized,
        R: DeserializeOwned,
    {
        let res = self
            .http
            .put(format!("http://{}{}", self.addr, path))
            .header("Authorization", format!("Bearer {}", self.token))
            .json(payload)
            .send()
            .await?;
        assert_eq!(res.status(), expected, "path={path}");
        Ok(res.json::<R>().await?)
    }

    async fn get<R>(&self, path: &str, expected: StatusCode) -> Result<R>
    where
        R: DeserializeOwned,
    {
        let res = self
            .http
            .get(format!("http://{}{}", self.addr, path))
            .header("Authorization", format!("Bearer {}", self.token))
            .send()
            .await?;
        assert_eq!(res.status(), expected, "path={path}");
        Ok(res.json::<R>().await?)
    }
}
