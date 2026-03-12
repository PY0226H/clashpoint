use axum::{
    body::Body,
    extract::{Multipart, Path, Query, State},
    http::{header::CONTENT_TYPE, HeaderMap, StatusCode},
    response::IntoResponse,
    Extension, Json,
};
use std::path::{Component, Path as StdPath, PathBuf};
use tokio::fs;
use tokio_util::io::ReaderStream;
use tracing::{info, warn};

use crate::{AppError, AppState, ChatFile, CreateMessage, ListMessages};
use chat_core::User;

/// Send a new message in the chat.
#[utoipa::path(
    post,
    path = "/api/chats/{id}",
    params(
        ("id" = u64, Path, description = "Chat id")
    ),
    responses(
        (status = 200, description = "List of messages", body = Message),
        (status = 400, description = "Invalid input", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn send_message_handler(
    Extension(user): Extension<User>,
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Json(input): Json<CreateMessage>,
) -> Result<impl IntoResponse, AppError> {
    let msg = state.create_message(input, id, user.id as _).await?;

    Ok((StatusCode::CREATED, Json(msg)))
}

/// List all messages in the chat.
#[utoipa::path(
    get,
    path = "/api/chats/{id}/messages",
    params(
        ("id" = u64, Path, description = "Chat id"),
        ListMessages

    ),
    responses(
        (status = 200, description = "List of messages", body = Vec<Message>),
        (status = 400, description = "Invalid input", body = ErrorOutput),
    ),
    security(
        ("token" = [])
    )
)]
pub(crate) async fn list_message_handler(
    State(state): State<AppState>,
    Path(id): Path<u64>,
    Query(input): Query<ListMessages>,
) -> Result<impl IntoResponse, AppError> {
    let messages = state.list_messages(input, id).await?;
    Ok(Json(messages))
}

pub(crate) async fn file_handler(
    Extension(_user): Extension<User>,
    State(state): State<AppState>,
    Path(path): Path<String>,
) -> Result<impl IntoResponse, AppError> {
    let path = resolve_file_path(&state.config.server.base_dir, &path).await?;

    let mime = mime_guess::from_path(&path).first_or_octet_stream();
    let file = fs::File::open(path).await?;
    let body = Body::from_stream(ReaderStream::new(file));
    let mut headers = HeaderMap::new();
    headers.insert(CONTENT_TYPE, mime.to_string().parse()?);
    Ok((headers, body))
}

pub(crate) async fn upload_handler(
    Extension(_user): Extension<User>,
    State(state): State<AppState>,
    mut multipart: Multipart,
) -> Result<impl IntoResponse, AppError> {
    let base_dir = &state.config.server.base_dir;
    let mut files = vec![];
    while let Some(field) = multipart.next_field().await.unwrap() {
        let filename = field.file_name().map(|name| name.to_string());
        let (Some(filename), Ok(data)) = (filename, field.bytes().await) else {
            warn!("Failed to read multipart field");
            continue;
        };

        let file = ChatFile::new(&filename, &data);
        let path = file.path(base_dir);
        if path.exists() {
            info!("File {} already exists: {:?}", filename, path);
        } else {
            fs::create_dir_all(path.parent().expect("file path parent should exists")).await?;
            fs::write(path, data).await?;
        }
        files.push(file.url());
    }

    Ok(Json(files))
}

fn sanitize_relative_path(path: &str) -> Result<PathBuf, AppError> {
    let mut normalized = PathBuf::new();
    for component in StdPath::new(path).components() {
        match component {
            Component::Normal(seg) => normalized.push(seg),
            Component::CurDir => continue,
            Component::ParentDir | Component::RootDir | Component::Prefix(_) => {
                return Err(AppError::NotFound(
                    "File doesn't exist or you don't have permission".to_string(),
                ))
            }
        }
    }

    if normalized.as_os_str().is_empty() {
        return Err(AppError::NotFound(
            "File doesn't exist or you don't have permission".to_string(),
        ));
    }

    Ok(normalized)
}

async fn resolve_file_path(base_dir: &StdPath, raw_path: &str) -> Result<PathBuf, AppError> {
    let normalized = sanitize_relative_path(raw_path)?;
    let requested = base_dir.join(normalized);

    let canonical_base_dir = fs::canonicalize(base_dir)
        .await
        .unwrap_or(base_dir.to_path_buf());
    let canonical_requested = fs::canonicalize(&requested)
        .await
        .map_err(|_| AppError::NotFound("File doesn't exist".to_string()))?;

    if !canonical_requested.starts_with(&canonical_base_dir) {
        return Err(AppError::NotFound(
            "File doesn't exist or you don't have permission".to_string(),
        ));
    }

    Ok(canonical_requested)
}

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_base_dir(label: &str) -> PathBuf {
        let ts = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("time should be monotonic")
            .as_nanos();
        std::env::temp_dir().join(format!("chat-file-handler-{label}-{ts}"))
    }

    #[tokio::test]
    async fn resolve_file_path_should_allow_normalized_valid_path() -> Result<()> {
        let base_dir = temp_base_dir("ok");
        let file_path = base_dir.join("a/b/file.txt");
        fs::create_dir_all(file_path.parent().expect("parent should exist")).await?;
        fs::write(&file_path, b"hello").await?;

        let resolved = resolve_file_path(&base_dir, "a/./b/file.txt").await?;
        assert_eq!(resolved, fs::canonicalize(&file_path).await?);

        fs::remove_dir_all(base_dir).await?;
        Ok(())
    }

    #[tokio::test]
    async fn resolve_file_path_should_reject_parent_dir_traversal() -> Result<()> {
        let base_dir = temp_base_dir("traversal");
        fs::create_dir_all(&base_dir).await?;

        let result = resolve_file_path(&base_dir, "../outside.txt").await;
        assert!(matches!(result, Err(AppError::NotFound(_))));

        fs::remove_dir_all(base_dir).await?;
        Ok(())
    }

    #[tokio::test]
    async fn resolve_file_path_should_reject_missing_file() -> Result<()> {
        let base_dir = temp_base_dir("missing");
        fs::create_dir_all(&base_dir).await?;

        let result = resolve_file_path(&base_dir, "a/b/missing.txt").await;
        assert!(matches!(result, Err(AppError::NotFound(_))));

        fs::remove_dir_all(base_dir).await?;
        Ok(())
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn resolve_file_path_should_reject_symlink_escape() -> Result<()> {
        use std::os::unix::fs::symlink;

        let temp_root_dir = temp_base_dir("symlink");
        let base_dir = temp_root_dir.join("base");
        let outside_dir = temp_root_dir.join("outside");
        fs::create_dir_all(&base_dir).await?;
        fs::create_dir_all(&outside_dir).await?;
        let outside_file = outside_dir.join("secret.txt");
        fs::write(&outside_file, b"secret").await?;

        symlink(&outside_dir, base_dir.join("link"))?;
        let result = resolve_file_path(&base_dir, "link/secret.txt").await;
        assert!(matches!(result, Err(AppError::NotFound(_))));

        fs::remove_dir_all(temp_root_dir).await?;
        Ok(())
    }
}
