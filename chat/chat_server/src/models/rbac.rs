use crate::{AppError, AppState};
use chat_core::User;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::FromRow;
use utoipa::ToSchema;

const ROLE_OPS_ADMIN: &str = "ops_admin";
const ROLE_OPS_REVIEWER: &str = "ops_reviewer";
const ROLE_OPS_VIEWER: &str = "ops_viewer";
pub(crate) const OPS_RBAC_PERMISSION_DENIED_ROLE_MANAGE_CODE: &str =
    "ops_permission_denied:role_manage";
pub(crate) const OPS_RBAC_OWNER_NOT_CONFIGURED_CODE: &str = "platform_owner_not_configured";
pub(crate) const OPS_RBAC_INVALID_ROLE_CODE: &str = "ops_role_invalid";
pub(crate) const OPS_RBAC_TARGET_USER_NOT_FOUND_CODE: &str = "ops_role_target_user_not_found";
const OPS_RBAC_ROLE_ASSIGNMENT_USER_ID_INVALID_CODE: &str = "ops_role_assignment_user_id_invalid";
const OPS_RBAC_ROLE_ASSIGNMENT_GRANTED_BY_INVALID_CODE: &str =
    "ops_role_assignment_granted_by_invalid";

#[derive(Debug, Clone, Copy)]
pub(crate) enum OpsPermission {
    DebateManage,
    JudgeReview,
    JudgeRejudge,
}

fn permission_key(permission: OpsPermission) -> &'static str {
    match permission {
        OpsPermission::DebateManage => "debate_manage",
        OpsPermission::JudgeReview => "judge_review",
        OpsPermission::JudgeRejudge => "judge_rejudge",
    }
}

fn permission_denied(permission: OpsPermission, reason: &str) -> AppError {
    AppError::DebateConflict(format!(
        "ops_permission_denied:{}:{}",
        permission_key(permission),
        reason
    ))
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UpsertOpsRoleInput {
    pub role: String,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OpsRoleAssignment {
    pub user_id: u64,
    pub user_email: String,
    pub user_fullname: String,
    pub role: String,
    pub granted_by: u64,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListOpsRoleAssignmentsOutput {
    pub items: Vec<OpsRoleAssignment>,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RevokeOpsRoleOutput {
    pub user_id: u64,
    pub removed: bool,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OpsPermissionFlags {
    pub debate_manage: bool,
    pub judge_review: bool,
    pub judge_rejudge: bool,
    pub role_manage: bool,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetOpsRbacMeOutput {
    pub user_id: u64,
    pub is_owner: bool,
    pub role: Option<String>,
    pub permissions: OpsPermissionFlags,
}

#[derive(Debug, Clone, FromRow)]
struct OpsRoleAssignmentRow {
    user_id: i64,
    user_email: String,
    user_fullname: String,
    role: String,
    granted_by: i64,
    created_at: DateTime<Utc>,
    updated_at: DateTime<Utc>,
}

fn normalize_ops_role(role: &str) -> Result<String, AppError> {
    let normalized = role.trim().to_lowercase();
    let is_valid = matches!(
        normalized.as_str(),
        ROLE_OPS_ADMIN | ROLE_OPS_REVIEWER | ROLE_OPS_VIEWER
    );
    if !is_valid {
        return Err(AppError::DebateError(
            OPS_RBAC_INVALID_ROLE_CODE.to_string(),
        ));
    }
    Ok(normalized)
}

fn role_grants_permission(role: &str, permission: OpsPermission) -> bool {
    match permission {
        OpsPermission::DebateManage => role == ROLE_OPS_ADMIN,
        OpsPermission::JudgeReview => {
            matches!(role, ROLE_OPS_ADMIN | ROLE_OPS_REVIEWER | ROLE_OPS_VIEWER)
        }
        OpsPermission::JudgeRejudge => matches!(role, ROLE_OPS_ADMIN | ROLE_OPS_REVIEWER),
    }
}

fn checked_i64_to_u64(value: i64, code: &'static str) -> Result<u64, AppError> {
    u64::try_from(value).map_err(|_| AppError::ServerError(code.to_string()))
}

fn map_assignment_row(row: OpsRoleAssignmentRow) -> Result<OpsRoleAssignment, AppError> {
    Ok(OpsRoleAssignment {
        user_id: checked_i64_to_u64(row.user_id, OPS_RBAC_ROLE_ASSIGNMENT_USER_ID_INVALID_CODE)?,
        user_email: row.user_email,
        user_fullname: row.user_fullname,
        role: row.role,
        granted_by: checked_i64_to_u64(
            row.granted_by,
            OPS_RBAC_ROLE_ASSIGNMENT_GRANTED_BY_INVALID_CODE,
        )?,
        created_at: row.created_at,
        updated_at: row.updated_at,
    })
}

impl AppState {
    pub(crate) async fn get_platform_admin_user_id(&self) -> Result<i64, AppError> {
        let owner_id: Option<i64> = sqlx::query_scalar(
            r#"
            SELECT owner_user_id
            FROM platform_admin_owners
            WHERE singleton_key = TRUE
            LIMIT 1
            "#,
        )
        .fetch_optional(&self.pool)
        .await?;
        owner_id
            .ok_or_else(|| AppError::ServerError(OPS_RBAC_OWNER_NOT_CONFIGURED_CODE.to_string()))
    }

    async fn find_ops_role_for_user(&self, user_id: i64) -> Result<Option<String>, AppError> {
        let role_row: Option<(String,)> = sqlx::query_as(
            r#"
            SELECT role
            FROM platform_user_roles
            WHERE user_id = $1
            "#,
        )
        .bind(user_id)
        .fetch_optional(&self.pool)
        .await?;
        Ok(role_row.map(|v| v.0))
    }

    pub async fn get_ops_rbac_me(&self, user: &User) -> Result<GetOpsRbacMeOutput, AppError> {
        let owner_id = self.get_platform_admin_user_id().await?;
        if owner_id == user.id {
            return Ok(GetOpsRbacMeOutput {
                user_id: user.id as u64,
                is_owner: true,
                role: None,
                permissions: OpsPermissionFlags {
                    debate_manage: true,
                    judge_review: true,
                    judge_rejudge: true,
                    role_manage: true,
                },
            });
        }

        let role = self.find_ops_role_for_user(user.id).await?;
        let permissions = if let Some(role_value) = role.as_deref() {
            OpsPermissionFlags {
                debate_manage: role_grants_permission(role_value, OpsPermission::DebateManage),
                judge_review: role_grants_permission(role_value, OpsPermission::JudgeReview),
                judge_rejudge: role_grants_permission(role_value, OpsPermission::JudgeRejudge),
                role_manage: false,
            }
        } else {
            OpsPermissionFlags {
                debate_manage: false,
                judge_review: false,
                judge_rejudge: false,
                role_manage: false,
            }
        };

        Ok(GetOpsRbacMeOutput {
            user_id: user.id as u64,
            is_owner: false,
            role,
            permissions,
        })
    }

    pub(crate) async fn ensure_ops_permission(
        &self,
        user: &User,
        permission: OpsPermission,
    ) -> Result<(), AppError> {
        let owner_id = self.get_platform_admin_user_id().await?;
        if owner_id == user.id {
            return Ok(());
        }

        let role = self.find_ops_role_for_user(user.id).await?;
        let Some(role) = role else {
            return Err(permission_denied(permission, "missing ops role assignment"));
        };
        if !role_grants_permission(&role, permission) {
            return Err(permission_denied(
                permission,
                format!("ops role {} cannot access this operation", role).as_str(),
            ));
        }
        Ok(())
    }

    async fn ensure_platform_admin_for_ops_rbac(&self, user: &User) -> Result<(), AppError> {
        let owner_id = self.get_platform_admin_user_id().await?;
        if owner_id != user.id {
            return Err(AppError::DebateConflict(
                OPS_RBAC_PERMISSION_DENIED_ROLE_MANAGE_CODE.to_string(),
            ));
        }
        Ok(())
    }

    pub async fn list_ops_role_assignments_by_owner(
        &self,
        user: &User,
    ) -> Result<ListOpsRoleAssignmentsOutput, AppError> {
        self.ensure_platform_admin_for_ops_rbac(user).await?;
        let rows: Vec<OpsRoleAssignmentRow> = sqlx::query_as(
            r#"
            SELECT
                r.user_id,
                COALESCE(u.email, '') AS user_email,
                u.fullname AS user_fullname,
                r.role,
                r.granted_by,
                r.created_at,
                r.updated_at
            FROM platform_user_roles r
            JOIN users u ON u.id = r.user_id
            ORDER BY r.updated_at DESC, r.user_id DESC
            "#,
        )
        .fetch_all(&self.pool)
        .await?;
        Ok(ListOpsRoleAssignmentsOutput {
            items: rows
                .into_iter()
                .map(map_assignment_row)
                .collect::<Result<Vec<_>, _>>()?,
        })
    }

    pub async fn upsert_ops_role_assignment_by_owner(
        &self,
        user: &User,
        target_user_id: u64,
        input: UpsertOpsRoleInput,
    ) -> Result<OpsRoleAssignment, AppError> {
        self.ensure_platform_admin_for_ops_rbac(user).await?;
        let role = normalize_ops_role(&input.role)?;

        let target_exists: Option<(i64,)> = sqlx::query_as(
            r#"
            SELECT id
            FROM users
            WHERE id = $1
            "#,
        )
        .bind(target_user_id as i64)
        .fetch_optional(&self.pool)
        .await?;
        if target_exists.is_none() {
            return Err(AppError::NotFound(
                OPS_RBAC_TARGET_USER_NOT_FOUND_CODE.to_string(),
            ));
        }

        let row: OpsRoleAssignmentRow = sqlx::query_as(
            r#"
            INSERT INTO platform_user_roles(
                user_id, role, granted_by, created_at, updated_at
            )
            VALUES ($1, $2, $3, NOW(), NOW())
            ON CONFLICT (user_id)
            DO UPDATE
            SET role = EXCLUDED.role,
                granted_by = EXCLUDED.granted_by,
                updated_at = NOW()
            RETURNING
                user_id,
                (SELECT COALESCE(email, '') FROM users WHERE id = platform_user_roles.user_id) AS user_email,
                (SELECT fullname FROM users WHERE id = platform_user_roles.user_id) AS user_fullname,
                role,
                granted_by,
                created_at,
                updated_at
            "#,
        )
        .bind(target_user_id as i64)
        .bind(role)
        .bind(user.id)
        .fetch_one(&self.pool)
        .await?;
        map_assignment_row(row)
    }

    pub async fn revoke_ops_role_assignment_by_owner(
        &self,
        user: &User,
        target_user_id: u64,
    ) -> Result<RevokeOpsRoleOutput, AppError> {
        self.ensure_platform_admin_for_ops_rbac(user).await?;
        let removed = sqlx::query_scalar::<_, i64>(
            r#"
            DELETE FROM platform_user_roles
            WHERE user_id = $1
            RETURNING user_id
            "#,
        )
        .bind(target_user_id as i64)
        .fetch_optional(&self.pool)
        .await?
        .is_some();

        Ok(RevokeOpsRoleOutput {
            user_id: target_user_id,
            removed,
        })
    }

    pub async fn grant_platform_admin(&self, user_id: u64) -> Result<(), AppError> {
        let user_exists: Option<(i64,)> = sqlx::query_as("SELECT id FROM users WHERE id = $1")
            .bind(user_id as i64)
            .fetch_optional(&self.pool)
            .await?;
        if user_exists.is_none() {
            return Err(AppError::NotFound(
                OPS_RBAC_TARGET_USER_NOT_FOUND_CODE.to_string(),
            ));
        }

        // Prefer current platform owner as grant source.
        // If missing, fallback to conventional user id=1, and then self-grant in local edge cases.
        let granted_by = sqlx::query_scalar::<_, i64>(
            r#"
            SELECT owner_user_id
            FROM platform_admin_owners
            WHERE singleton_key = TRUE
            LIMIT 1
            "#,
        )
        .fetch_optional(&self.pool)
        .await?
        .or(
            sqlx::query_scalar::<_, i64>("SELECT id FROM users WHERE id = 1")
                .fetch_optional(&self.pool)
                .await?,
        )
        .unwrap_or(user_id as i64);

        let mut tx = self.pool.begin().await?;
        sqlx::query(
            r#"
            INSERT INTO platform_user_roles(user_id, role, granted_by, created_at, updated_at)
            VALUES ($1, $2, $3, NOW(), NOW())
            ON CONFLICT (user_id)
            DO UPDATE
            SET role = EXCLUDED.role,
                granted_by = EXCLUDED.granted_by,
                updated_at = NOW()
            "#,
        )
        .bind(user_id as i64)
        .bind(ROLE_OPS_ADMIN)
        .bind(granted_by)
        .execute(&mut *tx)
        .await?;
        sqlx::query(
            r#"
            INSERT INTO platform_admin_owners(
                singleton_key, owner_user_id, updated_by, created_at, updated_at
            )
            VALUES (TRUE, $1, $2, NOW(), NOW())
            ON CONFLICT (singleton_key)
            DO UPDATE
            SET owner_user_id = EXCLUDED.owner_user_id,
                updated_by = EXCLUDED.updated_by,
                updated_at = NOW()
            "#,
        )
        .bind(user_id as i64)
        .bind(granted_by)
        .execute(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::Result;

    #[tokio::test]
    async fn ensure_ops_permission_should_allow_owner_and_assigned_role() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let user = state.find_user_by_id(2).await?.expect("user should exist");

        state
            .ensure_ops_permission(&owner, OpsPermission::DebateManage)
            .await?;

        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                user.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_admin".to_string(),
                },
            )
            .await?;
        state
            .ensure_ops_permission(&user, OpsPermission::DebateManage)
            .await?;
        state
            .ensure_ops_permission(&user, OpsPermission::JudgeRejudge)
            .await?;
        Ok(())
    }

    #[tokio::test]
    async fn ensure_ops_permission_should_respect_role_matrix() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let user = state.find_user_by_id(2).await?.expect("user should exist");

        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                user.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_viewer".to_string(),
                },
            )
            .await?;
        state
            .ensure_ops_permission(&user, OpsPermission::JudgeReview)
            .await?;
        let manage_err = state
            .ensure_ops_permission(&user, OpsPermission::DebateManage)
            .await
            .expect_err("viewer should not manage debate");
        match manage_err {
            AppError::DebateConflict(msg) => {
                assert!(msg.contains("ops_permission_denied:debate_manage:"))
            }
            other => panic!("unexpected error: {}", other),
        }
        let rejudge_err = state
            .ensure_ops_permission(&user, OpsPermission::JudgeRejudge)
            .await
            .expect_err("viewer should not rejudge");
        match rejudge_err {
            AppError::DebateConflict(msg) => {
                assert!(msg.contains("ops_permission_denied:judge_rejudge:"))
            }
            other => panic!("unexpected error: {}", other),
        }
        Ok(())
    }

    #[tokio::test]
    async fn get_ops_rbac_me_should_return_permissions_snapshot() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let viewer = state
            .find_user_by_id(2)
            .await?
            .expect("viewer should exist");

        let owner_snapshot = state.get_ops_rbac_me(&owner).await?;
        assert!(owner_snapshot.is_owner);
        assert!(owner_snapshot.permissions.debate_manage);
        assert!(owner_snapshot.permissions.judge_review);
        assert!(owner_snapshot.permissions.judge_rejudge);
        assert!(owner_snapshot.permissions.role_manage);

        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                viewer.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_viewer".to_string(),
                },
            )
            .await?;
        let viewer_snapshot = state.get_ops_rbac_me(&viewer).await?;
        assert!(!viewer_snapshot.is_owner);
        assert_eq!(viewer_snapshot.role.as_deref(), Some("ops_viewer"));
        assert!(!viewer_snapshot.permissions.debate_manage);
        assert!(viewer_snapshot.permissions.judge_review);
        assert!(!viewer_snapshot.permissions.judge_rejudge);
        assert!(!viewer_snapshot.permissions.role_manage);
        Ok(())
    }

    #[tokio::test]
    async fn grant_platform_admin_should_update_owner_source() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let next_owner = state
            .find_user_by_id(2)
            .await?
            .expect("next owner should exist");
        state.grant_platform_admin(owner.id as u64).await?;

        state.grant_platform_admin(next_owner.id as u64).await?;
        let owner_id = state.get_platform_admin_user_id().await?;
        assert_eq!(owner_id, next_owner.id);

        let next_snapshot = state.get_ops_rbac_me(&next_owner).await?;
        assert!(next_snapshot.is_owner);
        assert!(next_snapshot.permissions.role_manage);

        let old_owner_snapshot = state.get_ops_rbac_me(&owner).await?;
        assert!(!old_owner_snapshot.is_owner);
        assert!(!old_owner_snapshot.permissions.role_manage);
        Ok(())
    }

    #[tokio::test]
    async fn ops_role_assignment_crud_should_work() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");

        let created = state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                2,
                UpsertOpsRoleInput {
                    role: "ops_reviewer".to_string(),
                },
            )
            .await?;
        assert_eq!(created.user_id, 2);
        assert_eq!(created.role, "ops_reviewer");

        let list = state.list_ops_role_assignments_by_owner(&owner).await?;
        assert!(!list.items.is_empty());
        assert!(list
            .items
            .iter()
            .any(|item| item.user_id == 2 && item.role == "ops_reviewer"));

        let revoked = state.revoke_ops_role_assignment_by_owner(&owner, 2).await?;
        assert!(revoked.removed);

        let list_after = state.list_ops_role_assignments_by_owner(&owner).await?;
        assert!(list_after.items.iter().all(|item| item.user_id != 2));
        Ok(())
    }
}
