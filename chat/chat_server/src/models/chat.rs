use crate::{AppError, AppState};
use chat_core::{Chat, ChatType};
use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

#[derive(Debug, Clone, Default, ToSchema, Serialize, Deserialize)]
pub struct CreateChat {
    pub name: Option<String>,
    pub members: Vec<i64>,
    pub public: bool,
}

#[derive(Debug, Clone, Default, ToSchema, Serialize, Deserialize)]
pub struct UpdateChat {
    pub name: String,
}

#[derive(Debug, Clone, Default, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateChatMembers {
    pub member_ids: Vec<i64>,
}

#[allow(dead_code)]
impl AppState {
    pub async fn create_chat(
        &self,
        input: CreateChat,
        user_id: u64,
        ws_id: u64,
    ) -> Result<Chat, AppError> {
        let members = normalize_member_ids(input.members)?;
        let len = members.len();
        if len < 2 {
            return Err(AppError::CreateChatError(
                "Chat must have at least 2 members".to_string(),
            ));
        }

        // if user id is not in members, reject
        if !members.contains(&(user_id as i64)) {
            return Err(AppError::CreateChatError(
                "You must be a member of the chat".to_string(),
            ));
        }

        if let Some(name) = &input.name {
            if name.len() < 3 {
                return Err(AppError::CreateChatError(
                    "Chat name must have at least 3 characters".to_string(),
                ));
            }
        }

        if len > 8 && input.name.is_none() {
            return Err(AppError::CreateChatError(
                "Group chat with more than 8 members must have a name".to_string(),
            ));
        }

        // verify if all members exist
        self.ensure_workspace_users_exist(ws_id, &members).await?;

        let chat_type = match (&input.name, len) {
            (None, 2) => ChatType::Single,
            (None, _) => ChatType::Group,
            (Some(_), _) => {
                if input.public {
                    ChatType::PublicChannel
                } else {
                    ChatType::PrivateChannel
                }
            }
        };

        let chat = sqlx::query_as(
            r#"
            INSERT INTO chats (ws_id, name, type, members)
            VALUES ($1, $2, $3, $4)
            RETURNING id, ws_id, name, type, members, agents, created_at
            "#,
        )
        .bind(ws_id as i64)
        .bind(input.name)
        .bind(chat_type)
        .bind(members)
        .fetch_one(&self.pool)
        .await?;

        Ok(chat)
    }

    pub async fn fetch_chats(&self, user_id: u64, ws_id: u64) -> Result<Vec<Chat>, AppError> {
        let chats = sqlx::query_as(
            r#"
            SELECT id, ws_id, name, type, members, agents, created_at
            FROM chats
            WHERE ws_id = $1 AND $2 = ANY(members)
            "#,
        )
        .bind(ws_id as i64)
        .bind(user_id as i64)
        .fetch_all(&self.pool)
        .await?;

        Ok(chats)
    }

    pub async fn get_chat_by_id(&self, id: u64) -> Result<Option<Chat>, AppError> {
        let chat = sqlx::query_as(
            r#"
            SELECT id, ws_id, name, type, members, agents, created_at
            FROM chats
            WHERE id = $1
            "#,
        )
        .bind(id as i64)
        .fetch_optional(&self.pool)
        .await?;

        Ok(chat)
    }

    pub async fn join_chat(&self, id: u64, ws_id: u64, user_id: u64) -> Result<Chat, AppError> {
        self.ensure_workspace_users_exist(ws_id, &[user_id as i64])
            .await?;

        let chat = sqlx::query_as(
            r#"
            UPDATE chats
            SET members = CASE
                WHEN $3 = ANY(members) THEN members
                ELSE array_append(members, $3)
            END
            WHERE id = $1 AND ws_id = $2 AND type = 'public_channel'::chat_type
            RETURNING id, ws_id, name, type, members, agents, created_at
            "#,
        )
        .bind(id as i64)
        .bind(ws_id as i64)
        .bind(user_id as i64)
        .fetch_optional(&self.pool)
        .await?;
        if let Some(chat) = chat {
            return Ok(chat);
        }

        let Some(chat) = self.get_chat_by_id_and_ws(id, ws_id).await? else {
            return Err(AppError::NotFound(format!("chat id {id}")));
        };
        if chat.r#type != ChatType::PublicChannel {
            return Err(AppError::CreateChatError(
                "Only public channels can be joined directly".to_string(),
            ));
        }

        Err(AppError::CreateChatError(format!(
            "failed to join public channel {id}"
        )))
    }

    pub async fn leave_chat(&self, id: u64, ws_id: u64, user_id: u64) -> Result<Chat, AppError> {
        let Some(chat) = self.get_chat_by_id_and_ws(id, ws_id).await? else {
            return Err(AppError::NotFound(format!("chat id {id}")));
        };
        if chat.r#type == ChatType::Single {
            return Err(AppError::CreateChatError(
                "Single chat does not support leave".to_string(),
            ));
        }
        if !chat.members.contains(&(user_id as i64)) {
            return Err(AppError::NotChatMemberError {
                user_id,
                chat_id: id,
            });
        }
        if chat.members.len() <= 1 {
            return Err(AppError::CreateChatError(
                "Chat must retain at least one member".to_string(),
            ));
        }

        let updated = sqlx::query_as(
            r#"
            UPDATE chats
            SET members = array_remove(members, $1)
            WHERE id = $2 AND ws_id = $3
            RETURNING id, ws_id, name, type, members, agents, created_at
            "#,
        )
        .bind(user_id as i64)
        .bind(id as i64)
        .bind(ws_id as i64)
        .fetch_optional(&self.pool)
        .await?;

        match updated {
            Some(chat) => Ok(chat),
            None => Err(AppError::NotFound(format!("chat id {id}"))),
        }
    }

    pub async fn add_chat_members(
        &self,
        id: u64,
        ws_id: u64,
        actor_id: u64,
        input: UpdateChatMembers,
    ) -> Result<Chat, AppError> {
        let member_ids = normalize_member_ids(input.member_ids)?;
        if member_ids.is_empty() {
            return Err(AppError::CreateChatError(
                "memberIds must not be empty".to_string(),
            ));
        }

        let Some(chat) = self.get_chat_by_id_and_ws(id, ws_id).await? else {
            return Err(AppError::NotFound(format!("chat id {id}")));
        };
        if chat.r#type == ChatType::Single {
            return Err(AppError::CreateChatError(
                "Single chat does not support member updates".to_string(),
            ));
        }
        if !chat.members.contains(&(actor_id as i64)) {
            return Err(AppError::NotChatMemberError {
                user_id: actor_id,
                chat_id: id,
            });
        }
        self.ensure_workspace_users_exist(ws_id, &member_ids)
            .await?;

        let updated = sqlx::query_as(
            r#"
            UPDATE chats
            SET members = ARRAY(
                SELECT DISTINCT member_id
                FROM unnest(chats.members || $1::bigint[]) AS member_id
                ORDER BY member_id
            )
            WHERE id = $2 AND ws_id = $3
            RETURNING id, ws_id, name, type, members, agents, created_at
            "#,
        )
        .bind(&member_ids)
        .bind(id as i64)
        .bind(ws_id as i64)
        .fetch_optional(&self.pool)
        .await?;

        match updated {
            Some(chat) => Ok(chat),
            None => Err(AppError::NotFound(format!("chat id {id}"))),
        }
    }

    pub async fn remove_chat_members(
        &self,
        id: u64,
        ws_id: u64,
        actor_id: u64,
        input: UpdateChatMembers,
    ) -> Result<Chat, AppError> {
        let member_ids = normalize_member_ids(input.member_ids)?;
        if member_ids.is_empty() {
            return Err(AppError::CreateChatError(
                "memberIds must not be empty".to_string(),
            ));
        }

        let Some(chat) = self.get_chat_by_id_and_ws(id, ws_id).await? else {
            return Err(AppError::NotFound(format!("chat id {id}")));
        };
        if chat.r#type == ChatType::Single {
            return Err(AppError::CreateChatError(
                "Single chat does not support member updates".to_string(),
            ));
        }
        if !chat.members.contains(&(actor_id as i64)) {
            return Err(AppError::NotChatMemberError {
                user_id: actor_id,
                chat_id: id,
            });
        }

        let mut will_remove = std::collections::HashSet::new();
        for member_id in &member_ids {
            will_remove.insert(*member_id);
        }
        let remaining = chat
            .members
            .iter()
            .filter(|member_id| !will_remove.contains(member_id))
            .count();
        if remaining == 0 {
            return Err(AppError::CreateChatError(
                "Chat must retain at least one member".to_string(),
            ));
        }

        let updated = sqlx::query_as(
            r#"
            UPDATE chats
            SET members = COALESCE((
                SELECT ARRAY(
                    SELECT member_id
                    FROM unnest(chats.members) AS member_id
                    WHERE NOT (member_id = ANY($1::bigint[]))
                    ORDER BY member_id
                )
            ), '{}'::bigint[])
            WHERE id = $2 AND ws_id = $3
            RETURNING id, ws_id, name, type, members, agents, created_at
            "#,
        )
        .bind(&member_ids)
        .bind(id as i64)
        .bind(ws_id as i64)
        .fetch_optional(&self.pool)
        .await?;

        match updated {
            Some(chat) => Ok(chat),
            None => Err(AppError::NotFound(format!("chat id {id}"))),
        }
    }

    pub async fn update_chat(
        &self,
        id: u64,
        ws_id: u64,
        input: UpdateChat,
    ) -> Result<Chat, AppError> {
        let name = input.name.trim();
        if name.len() < 3 {
            return Err(AppError::CreateChatError(
                "Chat name must have at least 3 characters".to_string(),
            ));
        }
        if name.len() > 64 {
            return Err(AppError::CreateChatError(
                "Chat name must have at most 64 characters".to_string(),
            ));
        }

        let chat = sqlx::query_as(
            r#"
            UPDATE chats
            SET name = $1
            WHERE id = $2 AND ws_id = $3
            RETURNING id, ws_id, name, type, members, agents, created_at
            "#,
        )
        .bind(name)
        .bind(id as i64)
        .bind(ws_id as i64)
        .fetch_optional(&self.pool)
        .await?;

        match chat {
            Some(chat) => Ok(chat),
            None => Err(AppError::NotFound(format!("chat id {id}"))),
        }
    }

    pub async fn delete_chat(&self, id: u64, ws_id: u64) -> Result<(), AppError> {
        let mut tx = self.pool.begin().await?;
        let existed = sqlx::query_scalar::<_, i64>(
            r#"
            SELECT id
            FROM chats
            WHERE id = $1 AND ws_id = $2
            "#,
        )
        .bind(id as i64)
        .bind(ws_id as i64)
        .fetch_optional(&mut *tx)
        .await?;
        if existed.is_none() {
            return Err(AppError::NotFound(format!("chat id {id}")));
        }

        sqlx::query("DELETE FROM chat_agents WHERE chat_id = $1")
            .bind(id as i64)
            .execute(&mut *tx)
            .await?;
        sqlx::query("DELETE FROM messages WHERE chat_id = $1")
            .bind(id as i64)
            .execute(&mut *tx)
            .await?;
        sqlx::query("DELETE FROM chats WHERE id = $1 AND ws_id = $2")
            .bind(id as i64)
            .bind(ws_id as i64)
            .execute(&mut *tx)
            .await?;
        tx.commit().await?;

        Ok(())
    }

    pub async fn is_chat_member(
        &self,
        chat_id: u64,
        user_id: u64,
        ws_id: u64,
    ) -> Result<bool, AppError> {
        let is_member = sqlx::query(
            r#"
            SELECT 1
            FROM chats
            WHERE id = $1 AND ws_id = $2 AND $3 = ANY(members)
            "#,
        )
        .bind(chat_id as i64)
        .bind(ws_id as i64)
        .bind(user_id as i64)
        .fetch_optional(&self.pool)
        .await?;

        Ok(is_member.is_some())
    }

    async fn get_chat_by_id_and_ws(&self, id: u64, ws_id: u64) -> Result<Option<Chat>, AppError> {
        let chat = sqlx::query_as(
            r#"
            SELECT id, ws_id, name, type, members, agents, created_at
            FROM chats
            WHERE id = $1 AND ws_id = $2
            "#,
        )
        .bind(id as i64)
        .bind(ws_id as i64)
        .fetch_optional(&self.pool)
        .await?;
        Ok(chat)
    }

    async fn ensure_workspace_users_exist(
        &self,
        ws_id: u64,
        member_ids: &[i64],
    ) -> Result<(), AppError> {
        if member_ids.is_empty() {
            return Ok(());
        }
        let count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(*)
            FROM users
            WHERE ws_id = $1 AND id = ANY($2)
            "#,
        )
        .bind(ws_id as i64)
        .bind(member_ids)
        .fetch_one(&self.pool)
        .await?;
        if count != member_ids.len() as i64 {
            return Err(AppError::CreateChatError(
                "Some members do not exist in workspace".to_string(),
            ));
        }
        Ok(())
    }
}

fn normalize_member_ids(member_ids: Vec<i64>) -> Result<Vec<i64>, AppError> {
    if member_ids.iter().any(|member_id| *member_id <= 0) {
        return Err(AppError::CreateChatError(
            "memberIds must be positive integers".to_string(),
        ));
    }
    let mut unique = member_ids;
    unique.sort_unstable();
    unique.dedup();
    Ok(unique)
}

#[cfg(test)]
impl CreateChat {
    pub fn new(name: &str, members: &[i64], public: bool) -> Self {
        let name = if name.is_empty() {
            None
        } else {
            Some(name.to_string())
        };
        Self {
            name,
            members: members.to_vec(),
            public,
        }
    }
}

#[cfg(test)]
impl UpdateChat {
    pub fn new(name: &str) -> Self {
        Self {
            name: name.to_string(),
        }
    }
}

#[cfg(test)]
impl UpdateChatMembers {
    pub fn new(member_ids: &[i64]) -> Self {
        Self {
            member_ids: member_ids.to_vec(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{CreateAgent, CreateMessage, ListMessages};
    use anyhow::Result;
    use chat_core::{AdapterType, AgentType};
    use std::collections::HashMap;

    #[tokio::test]
    async fn create_single_chat_should_work() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let input = CreateChat::new("", &[1, 2], false);
        let chat = state
            .create_chat(input, 1, 1)
            .await
            .expect("create chat failed");
        assert_eq!(chat.ws_id, 1);
        assert_eq!(chat.members.len(), 2);
        assert_eq!(chat.r#type, ChatType::Single);
        Ok(())
    }

    #[tokio::test]
    async fn create_public_named_chat_should_work() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let input = CreateChat::new("general1", &[1, 2, 3], true);
        let chat = state
            .create_chat(input, 1, 1)
            .await
            .expect("create chat failed");
        assert_eq!(chat.ws_id, 1);
        assert_eq!(chat.members.len(), 3);
        assert_eq!(chat.r#type, ChatType::PublicChannel);
        Ok(())
    }

    #[tokio::test]
    async fn chat_get_by_id_should_work() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let chat = state
            .get_chat_by_id(1)
            .await
            .expect("get chat by id failed")
            .unwrap();

        assert_eq!(chat.id, 1);
        assert_eq!(chat.name.unwrap(), "general");
        assert_eq!(chat.ws_id, 1);
        assert_eq!(chat.members.len(), 5);

        Ok(())
    }

    #[tokio::test]
    async fn chat_fetch_all_should_work() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let chats = state
            .fetch_chats(1, 1)
            .await
            .expect("fetch all chats failed");

        assert_eq!(chats.len(), 4);

        Ok(())
    }

    #[tokio::test]
    async fn chat_is_member_should_work() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let is_member = state
            .is_chat_member(1, 1, 1)
            .await
            .expect("is member failed");
        assert!(is_member);

        // user 6 doesn't exist
        let is_member = state
            .is_chat_member(1, 6, 1)
            .await
            .expect("is member failed");
        assert!(!is_member);

        // chat 10 doesn't exist
        let is_member = state
            .is_chat_member(10, 1, 1)
            .await
            .expect("is member failed");
        assert!(!is_member);

        // user 4 is not a member of chat 2
        let is_member = state
            .is_chat_member(2, 4, 1)
            .await
            .expect("is member failed");
        assert!(!is_member);

        Ok(())
    }

    #[tokio::test]
    async fn chat_join_public_channel_should_work_and_be_idempotent() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let new_user = state
            .create_user(&crate::CreateUser::new(
                "acme",
                "Join User",
                "join-user@acme.org",
                "hunter42",
            ))
            .await?;

        let chat = state.join_chat(1, 1, new_user.id as u64).await?;
        assert!(chat.members.contains(&new_user.id));

        let chat_again = state.join_chat(1, 1, new_user.id as u64).await?;
        let count = chat_again
            .members
            .iter()
            .filter(|member_id| **member_id == new_user.id)
            .count();
        assert_eq!(count, 1);
        Ok(())
    }

    #[tokio::test]
    async fn chat_join_private_channel_should_fail() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let ret = state.join_chat(2, 1, 4).await;
        assert!(matches!(ret, Err(AppError::CreateChatError(_))));
        Ok(())
    }

    #[tokio::test]
    async fn chat_leave_single_should_fail() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let ret = state.leave_chat(3, 1, 1).await;
        assert!(matches!(ret, Err(AppError::CreateChatError(_))));
        Ok(())
    }

    #[tokio::test]
    async fn chat_add_and_remove_members_should_work() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let new_user = state
            .create_user(&crate::CreateUser::new(
                "acme",
                "Member User",
                "member-user@acme.org",
                "hunter42",
            ))
            .await?;

        let added = state
            .add_chat_members(2, 1, 1, UpdateChatMembers::new(&[new_user.id]))
            .await?;
        assert!(added.members.contains(&new_user.id));

        let removed = state
            .remove_chat_members(2, 1, 1, UpdateChatMembers::new(&[new_user.id]))
            .await?;
        assert!(!removed.members.contains(&new_user.id));
        Ok(())
    }

    #[tokio::test]
    async fn chat_add_members_should_require_actor_membership() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let ret = state
            .add_chat_members(2, 1, 4, UpdateChatMembers::new(&[5]))
            .await;
        assert!(matches!(ret, Err(AppError::NotChatMemberError { .. })));
        Ok(())
    }

    #[tokio::test]
    async fn chat_remove_members_should_not_allow_empty_chat() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let ret = state
            .remove_chat_members(4, 1, 1, UpdateChatMembers::new(&[1, 3, 4]))
            .await;
        assert!(matches!(ret, Err(AppError::CreateChatError(_))));
        Ok(())
    }

    #[tokio::test]
    async fn chat_update_should_work() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let input = CreateChat::new("origin-name", &[1, 2], false);
        let chat = state.create_chat(input, 1, 1).await?;
        let updated = state
            .update_chat(chat.id as u64, 1, UpdateChat::new("renamed-chat"))
            .await?;
        assert_eq!(updated.name.as_deref(), Some("renamed-chat"));
        Ok(())
    }

    #[tokio::test]
    async fn chat_delete_should_remove_chat_messages_and_agents() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let input = CreateChat::new("to-delete", &[1, 2], false);
        let chat = state.create_chat(input, 1, 1).await?;

        let agent = CreateAgent::new(
            "cleanup-agent",
            AgentType::Proxy,
            AdapterType::Test,
            "gpt-4o-mini",
            "cleanup",
            HashMap::<String, String>::new(),
        );
        state.create_agent(agent, chat.id as u64).await?;

        let message = CreateMessage {
            content: "hello".to_string(),
            files: vec![],
        };
        state.create_message(message, chat.id as u64, 1).await?;

        state.delete_chat(chat.id as u64, 1).await?;

        assert!(state.get_chat_by_id(chat.id as u64).await?.is_none());
        let messages = state
            .list_messages(
                ListMessages {
                    last_id: None,
                    limit: 20,
                },
                chat.id as u64,
            )
            .await?;
        assert!(messages.is_empty());
        let agents = state.list_agents(chat.id as u64).await?;
        assert!(agents.is_empty());

        Ok(())
    }
}
