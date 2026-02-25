use anyhow::Result;
use axum::Router;
use chat_server::{
    AppState, CreateDebateMessageInput, DebateMessage, DebateSessionSummary, DebateTopic,
    GetJudgeReportOutput, JoinDebateSessionOutput, OpsCreateDebateSessionInput,
    OpsCreateDebateTopicInput, OpsUpdateDebateSessionInput, PinDebateMessageInput,
    PinDebateMessageOutput, RequestJudgeJobInput, RequestJudgeJobOutput, SubmitJudgeReportInput,
    VerifyIapOrderInput, VerifyIapOrderOutput,
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
                scheduled_start_at: "2099-01-01T00:00:00Z".parse()?,
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
