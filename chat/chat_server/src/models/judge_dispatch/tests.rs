use super::*;
use crate::test_fixtures::{
    seed_judge_topic_and_session as fixture_seed_judge_topic_and_session,
    seed_running_judge_job as fixture_seed_running_judge_job,
};
use anyhow::Result;
use axum::{routing::post, Json, Router};
use reqwest::StatusCode;
use serde_json::Value;
use std::sync::{
    atomic::{AtomicUsize, Ordering},
    Arc, Mutex,
};
use tokio::net::TcpListener;

async fn seed_topic_and_session(state: &AppState, status: &str) -> Result<i64> {
    fixture_seed_judge_topic_and_session(state, status, "topic-dispatch").await
}

async fn seed_running_job(
    state: &AppState,
    session_id: i64,
    attempts: i32,
    lock_secs_offset: Option<i64>,
) -> Result<i64> {
    fixture_seed_running_judge_job(state, session_id, 1, attempts, lock_secs_offset).await
}

async fn spawn_mock_dispatch_server() -> Result<(String, Arc<AtomicUsize>)> {
    let hit_count = Arc::new(AtomicUsize::new(0));
    let app = {
        let hit_count = hit_count.clone();
        Router::new().route(
            "/internal/judge/dispatch",
            post(move |Json(_payload): Json<Value>| {
                let hit_count = hit_count.clone();
                async move {
                    hit_count.fetch_add(1, Ordering::SeqCst);
                    (
                        axum::http::StatusCode::OK,
                        Json(serde_json::json!({"ok": true})),
                    )
                }
            }),
        )
    };
    let listener = TcpListener::bind("127.0.0.1:0").await?;
    let addr = listener.local_addr()?;
    tokio::spawn(async move {
        let _ = axum::serve(listener, app).await;
    });
    Ok((format!("http://{}", addr), hit_count))
}

async fn spawn_mock_dispatch_server_with_json(response: Value) -> Result<String> {
    let app = Router::new().route(
        "/internal/judge/dispatch",
        post(move |Json(_payload): Json<Value>| {
            let response = response.clone();
            async move { (axum::http::StatusCode::OK, Json(response)) }
        }),
    );
    let listener = TcpListener::bind("127.0.0.1:0").await?;
    let addr = listener.local_addr()?;
    tokio::spawn(async move {
        let _ = axum::serve(listener, app).await;
    });
    Ok(format!("http://{}", addr))
}

async fn spawn_mock_dispatch_server_with_status(status: StatusCode) -> Result<String> {
    let app = Router::new().route(
        "/internal/judge/dispatch",
        post(move |Json(_payload): Json<Value>| async move {
            (
                axum::http::StatusCode::from_u16(status.as_u16()).expect("valid status"),
                Json(serde_json::json!({"error":"mock"})),
            )
        }),
    );
    let listener = TcpListener::bind("127.0.0.1:0").await?;
    let addr = listener.local_addr()?;
    tokio::spawn(async move {
        let _ = axum::serve(listener, app).await;
    });
    Ok(format!("http://{}", addr))
}

async fn spawn_mock_dispatch_server_capture_payload() -> Result<(String, Arc<Mutex<Vec<Value>>>)> {
    let payloads = Arc::new(Mutex::new(Vec::new()));
    let app = {
        let payloads = payloads.clone();
        Router::new().route(
            "/internal/judge/dispatch",
            post(move |Json(payload): Json<Value>| {
                let payloads = payloads.clone();
                async move {
                    payloads
                        .lock()
                        .expect("capture lock poisoned")
                        .push(payload);
                    (
                        axum::http::StatusCode::OK,
                        Json(serde_json::json!({"accepted": true})),
                    )
                }
            }),
        )
    };
    let listener = TcpListener::bind("127.0.0.1:0").await?;
    let addr = listener.local_addr()?;
    tokio::spawn(async move {
        let _ = axum::serve(listener, app).await;
    });
    Ok((format!("http://{}", addr), payloads))
}

async fn spawn_mock_phase_dispatch_server_capture_payload(
) -> Result<(String, Arc<Mutex<Vec<Value>>>)> {
    let payloads = Arc::new(Mutex::new(Vec::new()));
    let app = {
        let payloads = payloads.clone();
        Router::new().route(
            "/internal/judge/v3/phase/dispatch",
            post(move |Json(payload): Json<Value>| {
                let payloads = payloads.clone();
                async move {
                    payloads
                        .lock()
                        .expect("capture lock poisoned")
                        .push(payload.clone());
                    let job_id = payload
                        .get("job_id")
                        .and_then(Value::as_u64)
                        .unwrap_or_default();
                    (
                        axum::http::StatusCode::OK,
                        Json(serde_json::json!({"accepted": true, "jobId": job_id})),
                    )
                }
            }),
        )
    };
    let listener = TcpListener::bind("127.0.0.1:0").await?;
    let addr = listener.local_addr()?;
    tokio::spawn(async move {
        let _ = axum::serve(listener, app).await;
    });
    Ok((format!("http://{}", addr), payloads))
}

async fn spawn_mock_phase_dispatch_server_with_status(status: StatusCode) -> Result<String> {
    let app = Router::new().route(
        "/internal/judge/v3/phase/dispatch",
        post(move |Json(_payload): Json<Value>| async move {
            (
                axum::http::StatusCode::from_u16(status.as_u16()).expect("valid status"),
                Json(serde_json::json!({"error":"mock"})),
            )
        }),
    );
    let listener = TcpListener::bind("127.0.0.1:0").await?;
    let addr = listener.local_addr()?;
    tokio::spawn(async move {
        let _ = axum::serve(listener, app).await;
    });
    Ok(format!("http://{}", addr))
}

async fn spawn_mock_final_dispatch_server_capture_payload(
) -> Result<(String, Arc<Mutex<Vec<Value>>>)> {
    let payloads = Arc::new(Mutex::new(Vec::new()));
    let app = {
        let payloads = payloads.clone();
        Router::new().route(
            "/internal/judge/v3/final/dispatch",
            post(move |Json(payload): Json<Value>| {
                let payloads = payloads.clone();
                async move {
                    payloads
                        .lock()
                        .expect("capture lock poisoned")
                        .push(payload.clone());
                    let job_id = payload
                        .get("job_id")
                        .and_then(Value::as_u64)
                        .unwrap_or_default();
                    (
                        axum::http::StatusCode::OK,
                        Json(serde_json::json!({"accepted": true, "jobId": job_id})),
                    )
                }
            }),
        )
    };
    let listener = TcpListener::bind("127.0.0.1:0").await?;
    let addr = listener.local_addr()?;
    tokio::spawn(async move {
        let _ = axum::serve(listener, app).await;
    });
    Ok((format!("http://{}", addr), payloads))
}

async fn spawn_mock_final_dispatch_server_with_status(status: StatusCode) -> Result<String> {
    let app = Router::new().route(
        "/internal/judge/v3/final/dispatch",
        post(move |Json(_payload): Json<Value>| async move {
            (
                axum::http::StatusCode::from_u16(status.as_u16()).expect("valid status"),
                Json(serde_json::json!({"error":"mock"})),
            )
        }),
    );
    let listener = TcpListener::bind("127.0.0.1:0").await?;
    let addr = listener.local_addr()?;
    tokio::spawn(async move {
        let _ = axum::serve(listener, app).await;
    });
    Ok(format!("http://{}", addr))
}

async fn seed_messages(state: &AppState, session_id: i64, count: i64) -> Result<()> {
    for idx in 0..count {
        sqlx::query(
            r#"
            INSERT INTO session_messages(session_id, user_id, side, content)
            VALUES ($1, 1, 'pro', $2)
            "#,
        )
        .bind(session_id)
        .bind(format!("msg-{idx}"))
        .execute(&state.pool)
        .await?;
    }
    Ok(())
}

async fn seed_queued_phase_job(
    state: &AppState,
    session_id: i64,
    phase_no: i32,
    message_start_id: i64,
    message_end_id: i64,
    message_count: i32,
) -> Result<i64> {
    let phase_job_id: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO judge_phase_jobs(
            session_id, phase_no, message_start_id, message_end_id, message_count,
            status, trace_id, idempotency_key, rubric_version, judge_policy_version,
            topic_domain, retrieval_profile, dispatch_attempts
        )
        VALUES (
            $1, $2, $3, $4, $5,
            'queued', $6, $7, 'v3', 'v3-default',
            'default', 'hybrid_v1', 0
        )
        RETURNING id
        "#,
    )
    .bind(session_id)
    .bind(phase_no)
    .bind(message_start_id)
    .bind(message_end_id)
    .bind(message_count)
    .bind(format!("judge-phase-{}-{}", session_id, phase_no))
    .bind(format!(
        "judge_phase:{}:{}:v3:v3-default",
        session_id, phase_no
    ))
    .fetch_one(&state.pool)
    .await?;
    Ok(phase_job_id.0)
}

async fn seed_queued_final_job(
    state: &AppState,
    session_id: i64,
    phase_start_no: i32,
    phase_end_no: i32,
) -> Result<i64> {
    let final_job_id: (i64,) = sqlx::query_as(
        r#"
        INSERT INTO judge_final_jobs(
            session_id, phase_start_no, phase_end_no,
            status, trace_id, idempotency_key, rubric_version, judge_policy_version,
            topic_domain, dispatch_attempts
        )
        VALUES (
            $1, $2, $3,
            'queued', $4, $5, 'v3', 'v3-default',
            'default', 0
        )
        RETURNING id
        "#,
    )
    .bind(session_id)
    .bind(phase_start_no)
    .bind(phase_end_no)
    .bind(format!("judge-final-{}-{}", session_id, phase_end_no))
    .bind(format!(
        "judge_final:{}:{}:{}:v3:v3-default",
        session_id, phase_start_no, phase_end_no
    ))
    .fetch_one(&state.pool)
    .await?;
    Ok(final_job_id.0)
}

#[tokio::test]
async fn load_dispatch_payload_should_include_recent_messages_ordered_asc() -> Result<()> {
    let (_tdb, state) = AppState::new_for_test().await?;
    let session_id = seed_topic_and_session(&state, "judging").await?;
    let job_id = seed_running_job(&state, session_id, 0, None).await?;
    seed_messages(&state, session_id, 3).await?;

    let job = PendingDispatchJob {
        id: job_id,
        session_id,
        requested_by: 1,
        style_mode: "rational".to_string(),
        rejudge_triggered: false,
        requested_at: Utc::now(),
        dispatch_attempts: 1,
    };
    let payload = state.load_dispatch_payload(&job).await?;
    assert_eq!(payload.job.job_id, job_id as u64);
    assert_eq!(payload.topic.title, "topic-dispatch");
    assert_eq!(payload.messages.len(), 3);
    assert_eq!(payload.messages[0].content, "msg-0");
    assert_eq!(payload.messages[2].content, "msg-2");
    assert_eq!(payload.messages[0].speaker_tag, "speaker-1");
    assert_eq!(payload.messages[2].speaker_tag, "speaker-1");
    Ok(())
}

#[tokio::test]
async fn dispatch_payload_should_blind_user_id_and_use_speaker_tag() -> Result<()> {
    let (_tdb, mut state) = AppState::new_for_test().await?;
    let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
    let (service_base_url, payloads) = spawn_mock_dispatch_server_capture_payload().await?;
    inner.config.ai_judge.dispatch_max_attempts = 3;
    inner.config.ai_judge.dispatch_timeout_ms = 1_000;
    inner.config.ai_judge.dispatch_lock_secs = 1;
    inner.config.ai_judge.dispatch_batch_size = 20;
    inner.config.ai_judge.dispatch_callback_wait_secs = 120;
    inner.config.ai_judge.service_base_url = service_base_url;
    inner.config.ai_judge.dispatch_path = "/internal/judge/dispatch".to_string();

    let session_id = seed_topic_and_session(&state, "judging").await?;
    seed_messages(&state, session_id, 2).await?;
    let _job_id = seed_running_job(&state, session_id, 0, None).await?;

    let tick = state.dispatch_pending_judge_jobs_once().await?;
    assert_eq!(tick.claimed, 1);
    assert_eq!(tick.dispatched, 1);

    let captured = payloads.lock().expect("capture lock poisoned");
    assert_eq!(captured.len(), 1);
    let messages = captured[0]
        .get("messages")
        .and_then(Value::as_array)
        .expect("messages should be array");
    assert_eq!(messages.len(), 2);
    assert!(messages[0].get("userId").is_none());
    assert_eq!(
        messages[0]
            .get("speaker_tag")
            .and_then(Value::as_str)
            .unwrap_or_default(),
        "speaker-1"
    );
    assert_eq!(
        captured[0]
            .get("trace_id")
            .and_then(Value::as_str)
            .unwrap_or_default(),
        "judge-dispatch-1"
    );
    assert_eq!(
        captured[0]
            .get("idempotency_key")
            .and_then(Value::as_str)
            .unwrap_or_default(),
        "judge-dispatch-1"
    );
    assert_eq!(
        captured[0]
            .get("judge_policy_version")
            .and_then(Value::as_str)
            .unwrap_or_default(),
        "v2-default"
    );
    assert_eq!(
        captured[0]
            .get("topic_domain")
            .and_then(Value::as_str)
            .unwrap_or_default(),
        "default"
    );
    assert_eq!(
        captured[0]
            .get("retrieval_profile")
            .and_then(Value::as_str)
            .unwrap_or_default(),
        "hybrid_v1"
    );
    Ok(())
}

#[tokio::test]
async fn dispatch_pending_judge_phase_jobs_once_should_dispatch_and_mark_dispatched() -> Result<()>
{
    let (_tdb, mut state) = AppState::new_for_test().await?;
    let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
    let (service_base_url, payloads) = spawn_mock_phase_dispatch_server_capture_payload().await?;
    inner.config.ai_judge.dispatch_max_attempts = 3;
    inner.config.ai_judge.dispatch_timeout_ms = 1_000;
    inner.config.ai_judge.dispatch_lock_secs = 1;
    inner.config.ai_judge.dispatch_batch_size = 20;
    inner.config.ai_judge.service_base_url = service_base_url;

    let session_id = seed_topic_and_session(&state, "judging").await?;
    seed_messages(&state, session_id, 2).await?;
    let bounds: (i64, i64) = sqlx::query_as(
        r#"
        SELECT MIN(id), MAX(id)
        FROM session_messages
        WHERE session_id = $1
        "#,
    )
    .bind(session_id)
    .fetch_one(&state.pool)
    .await?;
    let phase_job_id = seed_queued_phase_job(&state, session_id, 1, bounds.0, bounds.1, 2).await?;

    let tick = state.dispatch_pending_judge_phase_jobs_once().await?;
    assert_eq!(tick.claimed, 1);
    assert_eq!(tick.dispatched, 1);
    assert_eq!(tick.failed, 0);

    let row: (String, i32) = sqlx::query_as(
        r#"
        SELECT status, dispatch_attempts
        FROM judge_phase_jobs
        WHERE id = $1
        "#,
    )
    .bind(phase_job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(row.0, "dispatched");
    assert_eq!(row.1, 1);

    let captured = payloads.lock().expect("capture lock poisoned");
    assert_eq!(captured.len(), 1);
    let payload = &captured[0];
    assert_eq!(
        payload
            .get("session_id")
            .and_then(Value::as_u64)
            .unwrap_or_default(),
        session_id as u64
    );
    assert_eq!(
        payload
            .get("phase_no")
            .and_then(Value::as_i64)
            .unwrap_or_default(),
        1
    );
    assert_eq!(
        payload
            .get("message_count")
            .and_then(Value::as_i64)
            .unwrap_or_default(),
        2
    );
    Ok(())
}

#[tokio::test]
async fn dispatch_pending_judge_phase_jobs_once_should_mark_failed_on_http_400() -> Result<()> {
    let (_tdb, mut state) = AppState::new_for_test().await?;
    let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
    inner.config.ai_judge.dispatch_max_attempts = 1;
    inner.config.ai_judge.dispatch_timeout_ms = 1_000;
    inner.config.ai_judge.dispatch_lock_secs = 1;
    inner.config.ai_judge.dispatch_batch_size = 20;
    inner.config.ai_judge.service_base_url =
        spawn_mock_phase_dispatch_server_with_status(StatusCode::BAD_REQUEST).await?;

    let session_id = seed_topic_and_session(&state, "judging").await?;
    seed_messages(&state, session_id, 2).await?;
    let bounds: (i64, i64) = sqlx::query_as(
        r#"
        SELECT MIN(id), MAX(id)
        FROM session_messages
        WHERE session_id = $1
        "#,
    )
    .bind(session_id)
    .fetch_one(&state.pool)
    .await?;
    let phase_job_id = seed_queued_phase_job(&state, session_id, 1, bounds.0, bounds.1, 2).await?;

    let tick = state.dispatch_pending_judge_phase_jobs_once().await?;
    assert_eq!(tick.claimed, 1);
    assert_eq!(tick.dispatched, 0);
    assert_eq!(tick.failed, 1);
    assert_eq!(tick.marked_failed, 1);
    assert_eq!(tick.terminal_failed, 1);
    assert_eq!(tick.failed_http_4xx, 1);

    let row: (String, Option<String>) = sqlx::query_as(
        r#"
        SELECT status, error_message
        FROM judge_phase_jobs
        WHERE id = $1
        "#,
    )
    .bind(phase_job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(row.0, "failed");
    assert!(row.1.unwrap_or_default().contains("status=400"));
    Ok(())
}

#[tokio::test]
async fn enqueue_due_judge_final_jobs_once_should_enqueue_for_closed_session() -> Result<()> {
    let (_tdb, mut state) = AppState::new_for_test().await?;
    let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
    inner.config.ai_judge.dispatch_batch_size = 20;

    let session_id = seed_topic_and_session(&state, "closed").await?;
    seed_messages(&state, session_id, 4).await?;
    let ids: Vec<(i64,)> = sqlx::query_as(
        r#"
        SELECT id
        FROM session_messages
        WHERE session_id = $1
        ORDER BY id ASC
        "#,
    )
    .bind(session_id)
    .fetch_all(&state.pool)
    .await?;
    let first_phase = seed_queued_phase_job(&state, session_id, 1, ids[0].0, ids[1].0, 2).await?;
    let second_phase = seed_queued_phase_job(&state, session_id, 2, ids[2].0, ids[3].0, 2).await?;
    for phase_job_id in [first_phase, second_phase] {
        sqlx::query(
            r#"
            UPDATE judge_phase_jobs
            SET status = 'succeeded',
                dispatch_attempts = 1,
                dispatch_locked_until = NULL,
                updated_at = NOW()
            WHERE id = $1
            "#,
        )
        .bind(phase_job_id)
        .execute(&state.pool)
        .await?;
    }

    let first = state.enqueue_due_judge_final_jobs_once().await?;
    assert_eq!(first, 1);
    let second = state.enqueue_due_judge_final_jobs_once().await?;
    assert_eq!(second, 0);

    let row: (i64, i32, i32, String, String, String) = sqlx::query_as(
        r#"
        SELECT
            session_id, phase_start_no, phase_end_no,
            status, rubric_version, judge_policy_version
        FROM judge_final_jobs
        WHERE session_id = $1
        "#,
    )
    .bind(session_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(row.0, session_id);
    assert_eq!(row.1, 1);
    assert_eq!(row.2, 2);
    assert_eq!(row.3, "queued");
    assert_eq!(row.4, "v3");
    assert_eq!(row.5, "v3-default");
    Ok(())
}

#[tokio::test]
async fn dispatch_pending_judge_final_jobs_once_should_dispatch_and_mark_dispatched() -> Result<()>
{
    let (_tdb, mut state) = AppState::new_for_test().await?;
    let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
    let (service_base_url, payloads) = spawn_mock_final_dispatch_server_capture_payload().await?;
    inner.config.ai_judge.dispatch_max_attempts = 3;
    inner.config.ai_judge.dispatch_timeout_ms = 1_000;
    inner.config.ai_judge.dispatch_lock_secs = 1;
    inner.config.ai_judge.dispatch_batch_size = 20;
    inner.config.ai_judge.service_base_url = service_base_url;

    let session_id = seed_topic_and_session(&state, "closed").await?;
    let final_job_id = seed_queued_final_job(&state, session_id, 1, 3).await?;

    let tick = state.dispatch_pending_judge_final_jobs_once().await?;
    assert_eq!(tick.claimed, 1);
    assert_eq!(tick.dispatched, 1);
    assert_eq!(tick.failed, 0);

    let row: (String, i32) = sqlx::query_as(
        r#"
        SELECT status, dispatch_attempts
        FROM judge_final_jobs
        WHERE id = $1
        "#,
    )
    .bind(final_job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(row.0, "dispatched");
    assert_eq!(row.1, 1);

    let captured = payloads.lock().expect("capture lock poisoned");
    assert_eq!(captured.len(), 1);
    let payload = &captured[0];
    assert_eq!(
        payload
            .get("session_id")
            .and_then(Value::as_u64)
            .unwrap_or_default(),
        session_id as u64
    );
    assert_eq!(
        payload
            .get("phase_start_no")
            .and_then(Value::as_i64)
            .unwrap_or_default(),
        1
    );
    assert_eq!(
        payload
            .get("phase_end_no")
            .and_then(Value::as_i64)
            .unwrap_or_default(),
        3
    );
    Ok(())
}

#[tokio::test]
async fn dispatch_pending_judge_final_jobs_once_should_mark_failed_on_http_400() -> Result<()> {
    let (_tdb, mut state) = AppState::new_for_test().await?;
    let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
    inner.config.ai_judge.dispatch_max_attempts = 1;
    inner.config.ai_judge.dispatch_timeout_ms = 1_000;
    inner.config.ai_judge.dispatch_lock_secs = 1;
    inner.config.ai_judge.dispatch_batch_size = 20;
    inner.config.ai_judge.service_base_url =
        spawn_mock_final_dispatch_server_with_status(StatusCode::BAD_REQUEST).await?;

    let session_id = seed_topic_and_session(&state, "closed").await?;
    let final_job_id = seed_queued_final_job(&state, session_id, 1, 2).await?;

    let tick = state.dispatch_pending_judge_final_jobs_once().await?;
    assert_eq!(tick.claimed, 1);
    assert_eq!(tick.dispatched, 0);
    assert_eq!(tick.failed, 1);
    assert_eq!(tick.marked_failed, 1);
    assert_eq!(tick.terminal_failed, 1);
    assert_eq!(tick.failed_http_4xx, 1);

    let row: (String, Option<String>) = sqlx::query_as(
        r#"
        SELECT status, error_message
        FROM judge_final_jobs
        WHERE id = $1
        "#,
    )
    .bind(final_job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(row.0, "failed");
    assert!(row.1.unwrap_or_default().contains("status=400"));
    Ok(())
}

#[tokio::test]
async fn dispatch_pending_judge_jobs_once_should_mark_failed_after_max_attempts() -> Result<()> {
    let (_tdb, mut state) = AppState::new_for_test().await?;
    let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
    inner.config.ai_judge.dispatch_max_attempts = 1;
    inner.config.ai_judge.dispatch_timeout_ms = 200;
    inner.config.ai_judge.dispatch_lock_secs = 1;
    inner.config.ai_judge.dispatch_batch_size = 20;
    inner.config.ai_judge.service_base_url = "http://127.0.0.1:9".to_string();
    inner.config.ai_judge.dispatch_path = "/internal/judge/dispatch".to_string();

    let session_id = seed_topic_and_session(&state, "judging").await?;
    let job_id = seed_running_job(&state, session_id, 0, None).await?;

    let tick = state.dispatch_pending_judge_jobs_once().await?;
    assert_eq!(tick.claimed, 1);
    assert_eq!(tick.failed, 1);
    assert_eq!(tick.marked_failed, 1);

    let row: (String,) = sqlx::query_as(
        r#"
        SELECT status
        FROM judge_jobs
        WHERE id = $1
        "#,
    )
    .bind(job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(row.0, "failed");
    assert_eq!(tick.timed_out_failed, 0);
    Ok(())
}

#[tokio::test]
async fn dispatch_pending_judge_jobs_once_should_not_redispatch_within_callback_wait_window(
) -> Result<()> {
    let (_tdb, mut state) = AppState::new_for_test().await?;
    let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
    let (service_base_url, hit_count) = spawn_mock_dispatch_server().await?;
    inner.config.ai_judge.dispatch_max_attempts = 3;
    inner.config.ai_judge.dispatch_timeout_ms = 1_000;
    inner.config.ai_judge.dispatch_lock_secs = 1;
    inner.config.ai_judge.dispatch_batch_size = 20;
    inner.config.ai_judge.dispatch_callback_wait_secs = 120;
    inner.config.ai_judge.service_base_url = service_base_url;
    inner.config.ai_judge.dispatch_path = "/internal/judge/dispatch".to_string();

    let session_id = seed_topic_and_session(&state, "judging").await?;
    seed_messages(&state, session_id, 2).await?;
    let job_id = seed_running_job(&state, session_id, 0, None).await?;

    let first = state.dispatch_pending_judge_jobs_once().await?;
    assert_eq!(first.claimed, 1);
    assert_eq!(first.dispatched, 1);
    assert_eq!(hit_count.load(Ordering::SeqCst), 1);

    let second = state.dispatch_pending_judge_jobs_once().await?;
    assert_eq!(second.claimed, 0);
    assert_eq!(second.dispatched, 0);
    assert_eq!(hit_count.load(Ordering::SeqCst), 1);

    let lock_row: (Option<DateTime<Utc>>,) = sqlx::query_as(
        r#"
        SELECT dispatch_locked_until
        FROM judge_jobs
        WHERE id = $1
        "#,
    )
    .bind(job_id)
    .fetch_one(&state.pool)
    .await?;
    assert!(lock_row.0.is_some());
    Ok(())
}

#[tokio::test]
async fn dispatch_pending_judge_jobs_once_should_mark_timeout_failed_when_attempts_exhausted(
) -> Result<()> {
    let (_tdb, mut state) = AppState::new_for_test().await?;
    let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
    inner.config.ai_judge.dispatch_max_attempts = 2;
    inner.config.ai_judge.dispatch_timeout_ms = 200;
    inner.config.ai_judge.dispatch_lock_secs = 1;
    inner.config.ai_judge.dispatch_batch_size = 20;
    inner.config.ai_judge.dispatch_callback_wait_secs = 60;

    let session_id = seed_topic_and_session(&state, "judging").await?;
    let job_id = seed_running_job(&state, session_id, 2, Some(-10)).await?;

    let tick = state.dispatch_pending_judge_jobs_once().await?;
    assert_eq!(tick.claimed, 0);
    assert_eq!(tick.timed_out_failed, 1);

    let row: (String, Option<String>) = sqlx::query_as(
        r#"
        SELECT status, error_message
        FROM judge_jobs
        WHERE id = $1
        "#,
    )
    .bind(job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(row.0, "failed");
    assert!(row
        .1
        .unwrap_or_default()
        .contains("dispatch callback timeout after 2 attempts"));
    Ok(())
}

#[tokio::test]
async fn dispatch_pending_judge_jobs_once_should_mark_failed_when_response_rejected() -> Result<()>
{
    let (_tdb, mut state) = AppState::new_for_test().await?;
    let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
    inner.config.ai_judge.dispatch_max_attempts = 1;
    inner.config.ai_judge.dispatch_timeout_ms = 1_000;
    inner.config.ai_judge.dispatch_lock_secs = 1;
    inner.config.ai_judge.dispatch_batch_size = 20;
    inner.config.ai_judge.service_base_url =
        spawn_mock_dispatch_server_with_json(serde_json::json!({
            "accepted": false,
            "status": "marked_failed"
        }))
        .await?;
    inner.config.ai_judge.dispatch_path = "/internal/judge/dispatch".to_string();

    let session_id = seed_topic_and_session(&state, "judging").await?;
    let job_id = seed_running_job(&state, session_id, 0, None).await?;

    let tick = state.dispatch_pending_judge_jobs_once().await?;
    assert_eq!(tick.claimed, 1);
    assert_eq!(tick.dispatched, 0);
    assert_eq!(tick.failed, 1);
    assert_eq!(tick.marked_failed, 1);
    assert_eq!(tick.terminal_failed, 1);
    assert_eq!(tick.retryable_failed, 0);
    assert_eq!(tick.failed_contract, 1);

    let row: (String, Option<String>) = sqlx::query_as(
        r#"
        SELECT status, error_message
        FROM judge_jobs
        WHERE id = $1
        "#,
    )
    .bind(job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(row.0, "failed");
    assert!(row.1.unwrap_or_default().contains("accepted=false"));
    Ok(())
}

#[tokio::test]
async fn dispatch_pending_judge_jobs_once_should_mark_terminal_failed_immediately_when_response_rejected_with_retries_left(
) -> Result<()> {
    let (_tdb, mut state) = AppState::new_for_test().await?;
    let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
    inner.config.ai_judge.dispatch_max_attempts = 3;
    inner.config.ai_judge.dispatch_timeout_ms = 1_000;
    inner.config.ai_judge.dispatch_lock_secs = 1;
    inner.config.ai_judge.dispatch_batch_size = 20;
    inner.config.ai_judge.service_base_url =
        spawn_mock_dispatch_server_with_json(serde_json::json!({
            "accepted": false,
            "status": "marked_failed"
        }))
        .await?;
    inner.config.ai_judge.dispatch_path = "/internal/judge/dispatch".to_string();

    let session_id = seed_topic_and_session(&state, "judging").await?;
    let job_id = seed_running_job(&state, session_id, 0, None).await?;

    let tick = state.dispatch_pending_judge_jobs_once().await?;
    assert_eq!(tick.claimed, 1);
    assert_eq!(tick.dispatched, 0);
    assert_eq!(tick.failed, 1);
    assert_eq!(tick.marked_failed, 1);
    assert_eq!(tick.terminal_failed, 1);
    assert_eq!(tick.retryable_failed, 0);
    assert_eq!(tick.failed_contract, 1);

    let row: (String, i32) = sqlx::query_as(
        r#"
        SELECT status, dispatch_attempts
        FROM judge_jobs
        WHERE id = $1
        "#,
    )
    .bind(job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(row.0, "failed");
    assert_eq!(row.1, 1);
    Ok(())
}

#[tokio::test]
async fn dispatch_pending_judge_jobs_once_should_mark_failed_when_response_job_id_mismatch(
) -> Result<()> {
    let (_tdb, mut state) = AppState::new_for_test().await?;
    let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
    inner.config.ai_judge.dispatch_max_attempts = 1;
    inner.config.ai_judge.dispatch_timeout_ms = 1_000;
    inner.config.ai_judge.dispatch_lock_secs = 1;
    inner.config.ai_judge.dispatch_batch_size = 20;
    inner.config.ai_judge.service_base_url =
        spawn_mock_dispatch_server_with_json(serde_json::json!({
            "accepted": true,
            "jobId": 999999_u64
        }))
        .await?;
    inner.config.ai_judge.dispatch_path = "/internal/judge/dispatch".to_string();

    let session_id = seed_topic_and_session(&state, "judging").await?;
    let job_id = seed_running_job(&state, session_id, 0, None).await?;

    let tick = state.dispatch_pending_judge_jobs_once().await?;
    assert_eq!(tick.claimed, 1);
    assert_eq!(tick.dispatched, 0);
    assert_eq!(tick.failed, 1);
    assert_eq!(tick.marked_failed, 1);
    assert_eq!(tick.terminal_failed, 1);
    assert_eq!(tick.failed_contract, 1);

    let row: (String, Option<String>) = sqlx::query_as(
        r#"
        SELECT status, error_message
        FROM judge_jobs
        WHERE id = $1
        "#,
    )
    .bind(job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(row.0, "failed");
    assert!(row.1.unwrap_or_default().contains("job_id mismatch"));
    Ok(())
}

#[tokio::test]
async fn dispatch_pending_judge_jobs_once_should_mark_terminal_failed_on_http_400_even_with_retries_left(
) -> Result<()> {
    let (_tdb, mut state) = AppState::new_for_test().await?;
    let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
    inner.config.ai_judge.dispatch_max_attempts = 3;
    inner.config.ai_judge.dispatch_timeout_ms = 1_000;
    inner.config.ai_judge.dispatch_lock_secs = 1;
    inner.config.ai_judge.dispatch_batch_size = 20;
    inner.config.ai_judge.service_base_url =
        spawn_mock_dispatch_server_with_status(StatusCode::BAD_REQUEST).await?;
    inner.config.ai_judge.dispatch_path = "/internal/judge/dispatch".to_string();

    let session_id = seed_topic_and_session(&state, "judging").await?;
    let job_id = seed_running_job(&state, session_id, 0, None).await?;

    let tick = state.dispatch_pending_judge_jobs_once().await?;
    assert_eq!(tick.claimed, 1);
    assert_eq!(tick.dispatched, 0);
    assert_eq!(tick.failed, 1);
    assert_eq!(tick.marked_failed, 1);
    assert_eq!(tick.terminal_failed, 1);
    assert_eq!(tick.failed_http_4xx, 1);

    let row: (String, Option<String>) = sqlx::query_as(
        r#"
        SELECT status, error_message
        FROM judge_jobs
        WHERE id = $1
        "#,
    )
    .bind(job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(row.0, "failed");
    assert!(row.1.unwrap_or_default().contains("status=400"));
    Ok(())
}

#[tokio::test]
async fn dispatch_pending_judge_jobs_once_should_keep_running_on_http_500_when_retries_left(
) -> Result<()> {
    let (_tdb, mut state) = AppState::new_for_test().await?;
    let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
    inner.config.ai_judge.dispatch_max_attempts = 3;
    inner.config.ai_judge.dispatch_timeout_ms = 1_000;
    inner.config.ai_judge.dispatch_lock_secs = 1;
    inner.config.ai_judge.dispatch_batch_size = 20;
    inner.config.ai_judge.service_base_url =
        spawn_mock_dispatch_server_with_status(StatusCode::INTERNAL_SERVER_ERROR).await?;
    inner.config.ai_judge.dispatch_path = "/internal/judge/dispatch".to_string();

    let session_id = seed_topic_and_session(&state, "judging").await?;
    let job_id = seed_running_job(&state, session_id, 0, None).await?;

    let tick = state.dispatch_pending_judge_jobs_once().await?;
    assert_eq!(tick.claimed, 1);
    assert_eq!(tick.dispatched, 0);
    assert_eq!(tick.failed, 1);
    assert_eq!(tick.marked_failed, 0);
    assert_eq!(tick.retryable_failed, 1);
    assert_eq!(tick.failed_http_5xx, 1);

    let row: (String, i32, Option<String>) = sqlx::query_as(
        r#"
        SELECT status, dispatch_attempts, error_message
        FROM judge_jobs
        WHERE id = $1
        "#,
    )
    .bind(job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(row.0, "running");
    assert_eq!(row.1, 1);
    assert!(row.2.unwrap_or_default().contains("status=500"));
    Ok(())
}

#[tokio::test]
async fn dispatch_pending_judge_jobs_once_should_keep_running_on_http_429_when_retries_left(
) -> Result<()> {
    let (_tdb, mut state) = AppState::new_for_test().await?;
    let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
    inner.config.ai_judge.dispatch_max_attempts = 3;
    inner.config.ai_judge.dispatch_timeout_ms = 1_000;
    inner.config.ai_judge.dispatch_lock_secs = 1;
    inner.config.ai_judge.dispatch_batch_size = 20;
    inner.config.ai_judge.service_base_url =
        spawn_mock_dispatch_server_with_status(StatusCode::TOO_MANY_REQUESTS).await?;
    inner.config.ai_judge.dispatch_path = "/internal/judge/dispatch".to_string();

    let session_id = seed_topic_and_session(&state, "judging").await?;
    let job_id = seed_running_job(&state, session_id, 0, None).await?;

    let tick = state.dispatch_pending_judge_jobs_once().await?;
    assert_eq!(tick.claimed, 1);
    assert_eq!(tick.dispatched, 0);
    assert_eq!(tick.failed, 1);
    assert_eq!(tick.marked_failed, 0);
    assert_eq!(tick.retryable_failed, 1);
    assert_eq!(tick.failed_http_429, 1);

    let row: (String, i32, Option<String>) = sqlx::query_as(
        r#"
        SELECT status, dispatch_attempts, error_message
        FROM judge_jobs
        WHERE id = $1
        "#,
    )
    .bind(job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(row.0, "running");
    assert_eq!(row.1, 1);
    assert!(row.2.unwrap_or_default().contains("status=429"));
    Ok(())
}

#[tokio::test]
async fn dispatch_pending_judge_jobs_once_should_count_failed_network_when_dispatch_io_fails(
) -> Result<()> {
    let (_tdb, mut state) = AppState::new_for_test().await?;
    let inner = Arc::get_mut(&mut state.inner).expect("state should be unique");
    inner.config.ai_judge.dispatch_max_attempts = 1;
    inner.config.ai_judge.dispatch_timeout_ms = 1_000;
    inner.config.ai_judge.dispatch_lock_secs = 1;
    inner.config.ai_judge.dispatch_batch_size = 20;
    inner.config.ai_judge.service_base_url = "http://127.0.0.1:9".to_string();
    inner.config.ai_judge.dispatch_path = "/internal/judge/dispatch".to_string();

    let session_id = seed_topic_and_session(&state, "judging").await?;
    let job_id = seed_running_job(&state, session_id, 0, None).await?;

    let tick = state.dispatch_pending_judge_jobs_once().await?;
    assert_eq!(tick.claimed, 1);
    assert_eq!(tick.dispatched, 0);
    assert_eq!(tick.failed, 1);
    assert_eq!(tick.marked_failed, 1);
    assert_eq!(tick.retryable_failed, 1);
    assert_eq!(tick.failed_network, 1);

    let row: (String, Option<String>) = sqlx::query_as(
        r#"
        SELECT status, error_message
        FROM judge_jobs
        WHERE id = $1
        "#,
    )
    .bind(job_id)
    .fetch_one(&state.pool)
    .await?;
    assert_eq!(row.0, "failed");
    assert!(row.1.unwrap_or_default().contains("[network_send_failed]"));
    Ok(())
}

#[test]
fn build_dispatch_url_should_join_base_and_path() {
    assert_eq!(
        build_dispatch_url("http://127.0.0.1:8787/", "/internal/judge/dispatch"),
        "http://127.0.0.1:8787/internal/judge/dispatch"
    );
    assert_eq!(
        build_dispatch_url("http://127.0.0.1:8787", "internal/judge/dispatch"),
        "http://127.0.0.1:8787/internal/judge/dispatch"
    );
}

#[test]
fn dispatch_trace_and_idempotency_key_should_be_stable() {
    assert_eq!(build_dispatch_trace_id(42), "judge-dispatch-42");
    assert_eq!(build_dispatch_idempotency_key(42), "judge-dispatch-42");
}

#[test]
fn validate_dispatch_response_should_allow_legacy_or_empty_body() {
    assert!(validate_dispatch_response("", 1).is_ok());
    assert!(validate_dispatch_response("{\"ok\":true}", 1).is_ok());
    assert!(validate_dispatch_response("not-json", 1).is_ok());
}

#[test]
fn validate_dispatch_response_should_reject_accepted_false() {
    let err = validate_dispatch_response(r#"{"accepted":false,"status":"marked_failed"}"#, 42)
        .expect_err("should reject");
    assert!(err.to_string().contains("accepted=false"));
}

#[test]
fn validate_dispatch_response_should_reject_job_id_mismatch() {
    let err = validate_dispatch_response(r#"{"accepted":true,"jobId":99}"#, 42)
        .expect_err("should reject mismatch");
    assert!(err.to_string().contains("job_id mismatch"));
}

#[test]
fn calc_retry_lock_secs_should_apply_exponential_backoff_with_cap() {
    assert_eq!(calc_retry_lock_secs(1, 1, 2, 8, 0), 2);
    assert_eq!(calc_retry_lock_secs(1, 2, 2, 8, 0), 4);
    assert_eq!(calc_retry_lock_secs(1, 3, 2, 8, 0), 8);
    assert_eq!(calc_retry_lock_secs(1, 4, 2, 8, 0), 16);
    assert_eq!(calc_retry_lock_secs(1, 9, 2, 8, 0), 16);
}

#[test]
fn calc_retry_lock_secs_should_apply_deterministic_jitter_within_bounds() {
    let base = calc_retry_lock_secs(42, 4, 10, 8, 0);
    let jittered = calc_retry_lock_secs(42, 4, 10, 8, 20);
    let jittered_repeat = calc_retry_lock_secs(42, 4, 10, 8, 20);
    let window = base * 20 / 100;
    assert!(jittered >= base - window);
    assert!(jittered <= base + window);
    assert_eq!(jittered, jittered_repeat);
}
