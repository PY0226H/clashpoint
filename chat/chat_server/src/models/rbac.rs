use crate::{AppError, AppState};
use chat_core::User;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::{FromRow, Postgres, Transaction};
use utoipa::{IntoParams, ToSchema};

const ROLE_OPS_ADMIN: &str = "ops_admin";
const ROLE_OPS_REVIEWER: &str = "ops_reviewer";
const ROLE_OPS_VIEWER: &str = "ops_viewer";
const ROLE_PLATFORM_ROLE_ADMIN: &str = "platform_role_admin";
pub(crate) const OPS_RBAC_PERMISSION_DENIED_ROLE_MANAGE_CODE: &str =
    "ops_permission_denied:role_manage";
pub(crate) const OPS_RBAC_OWNER_NOT_CONFIGURED_CODE: &str = "platform_owner_not_configured";
pub(crate) const OPS_RBAC_INVALID_ROLE_CODE: &str = "ops_role_invalid";
pub(crate) const OPS_RBAC_TARGET_USER_NOT_FOUND_CODE: &str = "ops_role_target_user_not_found";
pub(crate) const OPS_RBAC_TARGET_USER_ID_OUT_OF_RANGE_CODE: &str =
    "ops_role_target_user_id_out_of_range";
pub(crate) const OPS_RBAC_IF_MATCH_REQUIRED_CODE: &str = "ops_rbac_if_match_required";
pub(crate) const OPS_RBAC_REVISION_CONFLICT_CODE: &str = "ops_rbac_revision_conflict";
const OPS_RBAC_ROLE_ASSIGNMENT_USER_ID_INVALID_CODE: &str = "ops_role_assignment_user_id_invalid";
const OPS_RBAC_ROLE_ASSIGNMENT_GRANTED_BY_INVALID_CODE: &str =
    "ops_role_assignment_granted_by_invalid";
const OPS_RBAC_EMPTY_REVISION: &str = "empty";
const OPS_RBAC_WRITE_REVISION_LOCK_KEY: &str = "ops_rbac_roles_write_revision_lock";
const OPS_RBAC_AUDIT_EVENT_ROLE_UPSERT: &str = "role_upsert";
const OPS_RBAC_AUDIT_EVENT_ROLE_REVOKE: &str = "role_revoke";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum OpsRoleManageAccess {
    Owner,
    DelegatedRoleAdmin,
}

#[derive(Debug, Clone, Copy)]
struct OpsRoleManageContext {
    owner_user_id: i64,
    access: OpsRoleManageAccess,
}

#[derive(Debug, Clone, Copy)]
pub(crate) enum OpsPermission {
    DebateManage,
    JudgeReview,
    JudgeRejudge,
    ObservabilityRead,
    ObservabilityManage,
}

fn permission_key(permission: OpsPermission) -> &'static str {
    match permission {
        OpsPermission::DebateManage => "debate_manage",
        OpsPermission::JudgeReview => "judge_review",
        OpsPermission::JudgeRejudge => "judge_rejudge",
        OpsPermission::ObservabilityRead => "observability_read",
        OpsPermission::ObservabilityManage => "observability_manage",
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

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OpsRbacPiiLevel {
    #[default]
    Minimal,
    Full,
}

#[derive(Debug, Clone, Default, IntoParams, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListOpsRoleAssignmentsQuery {
    #[serde(default)]
    pub pii_level: OpsRbacPiiLevel,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListOpsRoleAssignmentsOutput {
    pub items: Vec<OpsRoleAssignment>,
    pub rbac_revision: String,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RevokeOpsRoleOutput {
    pub user_id: u64,
    pub removed: bool,
}

#[derive(Debug, Clone, Copy, Default)]
pub struct OpsRbacUpsertMeta<'a> {
    pub expected_rbac_revision: Option<&'a str>,
    pub idempotency_key: Option<&'a str>,
    pub idempotency_ttl_secs: u64,
    pub success_request_id: Option<&'a str>,
    pub require_if_match: bool,
}

#[derive(Debug, Clone, Copy, Default)]
pub struct OpsRbacRevokeMeta<'a> {
    pub expected_rbac_revision: Option<&'a str>,
    pub success_request_id: Option<&'a str>,
    pub require_if_match: bool,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OpsPermissionFlags {
    pub debate_manage: bool,
    pub judge_review: bool,
    pub judge_rejudge: bool,
    pub observability_read: bool,
    pub observability_manage: bool,
    pub role_manage: bool,
}

#[derive(Debug, Clone, ToSchema, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetOpsRbacMeOutput {
    pub user_id: u64,
    pub is_owner: bool,
    pub role: Option<String>,
    pub permissions: OpsPermissionFlags,
    pub rbac_revision: String,
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
        ROLE_OPS_ADMIN | ROLE_OPS_REVIEWER | ROLE_OPS_VIEWER | ROLE_PLATFORM_ROLE_ADMIN
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
        OpsPermission::ObservabilityRead => {
            matches!(role, ROLE_OPS_ADMIN | ROLE_OPS_REVIEWER | ROLE_OPS_VIEWER)
        }
        OpsPermission::ObservabilityManage => {
            matches!(role, ROLE_OPS_ADMIN | ROLE_OPS_REVIEWER)
        }
    }
}

fn role_grants_role_manage(role: &str) -> bool {
    role == ROLE_PLATFORM_ROLE_ADMIN
}

fn role_manage_permission_denied(reason: &str) -> AppError {
    AppError::DebateConflict(format!(
        "{OPS_RBAC_PERMISSION_DENIED_ROLE_MANAGE_CODE}:{reason}"
    ))
}

fn checked_i64_to_u64(value: i64, code: &'static str) -> Result<u64, AppError> {
    u64::try_from(value).map_err(|_| AppError::ServerError(code.to_string()))
}

fn checked_u64_to_i64(value: u64, code: &'static str) -> Result<i64, AppError> {
    i64::try_from(value).map_err(|_| AppError::DebateError(code.to_string()))
}

fn map_assignment_row(row: OpsRoleAssignmentRow) -> Result<OpsRoleAssignment, AppError> {
    map_assignment_row_with_pii_level(row, OpsRbacPiiLevel::Full)
}

fn mask_user_email(email: &str) -> String {
    let normalized = email.trim();
    let Some((local_part, domain_part)) = normalized.split_once('@') else {
        return "***".to_string();
    };
    if local_part.is_empty() || domain_part.is_empty() {
        return "***".to_string();
    }
    let mut local_chars = local_part.chars();
    let local_first = local_chars.next().unwrap_or('*');
    let local_second = local_chars.next();
    let local_prefix = match local_second {
        Some(second) => format!("{local_first}{second}"),
        None => local_first.to_string(),
    };
    let domain_first = domain_part.chars().next().unwrap_or('*');
    format!("{local_prefix}***@{domain_first}***")
}

fn mask_user_fullname(fullname: &str) -> String {
    let normalized = fullname.trim();
    if normalized.is_empty() {
        return "***".to_string();
    }
    let first = normalized.chars().next().unwrap_or('*');
    format!("{first}***")
}

fn map_assignment_row_with_pii_level(
    row: OpsRoleAssignmentRow,
    pii_level: OpsRbacPiiLevel,
) -> Result<OpsRoleAssignment, AppError> {
    let (user_email, user_fullname) = match pii_level {
        OpsRbacPiiLevel::Full => (row.user_email, row.user_fullname),
        OpsRbacPiiLevel::Minimal => (
            mask_user_email(&row.user_email),
            mask_user_fullname(&row.user_fullname),
        ),
    };
    Ok(OpsRoleAssignment {
        user_id: checked_i64_to_u64(row.user_id, OPS_RBAC_ROLE_ASSIGNMENT_USER_ID_INVALID_CODE)?,
        user_email,
        user_fullname,
        role: row.role,
        granted_by: checked_i64_to_u64(
            row.granted_by,
            OPS_RBAC_ROLE_ASSIGNMENT_GRANTED_BY_INVALID_CODE,
        )?,
        created_at: row.created_at,
        updated_at: row.updated_at,
    })
}

fn format_rbac_revision(value: DateTime<Utc>) -> String {
    value.to_rfc3339_opts(chrono::SecondsFormat::Micros, true)
}

async fn get_ops_rbac_revision_tx(tx: &mut Transaction<'_, Postgres>) -> Result<String, AppError> {
    let revision: Option<DateTime<Utc>> = sqlx::query_scalar(
        r#"
        SELECT MAX(updated_at)
        FROM (
            SELECT updated_at
            FROM platform_user_roles
            UNION ALL
            SELECT updated_at
            FROM platform_admin_owners
        ) updates
        "#,
    )
    .fetch_one(&mut **tx)
    .await?;
    Ok(revision
        .map(format_rbac_revision)
        .unwrap_or_else(|| OPS_RBAC_EMPTY_REVISION.to_string()))
}

fn ensure_expected_ops_rbac_revision(
    expected_rbac_revision: Option<&str>,
    current_revision: &str,
    require_if_match: bool,
) -> Result<(), AppError> {
    if let Some(expected) = expected_rbac_revision {
        if expected != current_revision {
            return Err(AppError::DebateConflict(
                OPS_RBAC_REVISION_CONFLICT_CODE.to_string(),
            ));
        }
    } else if require_if_match {
        return Err(AppError::DebateError(
            OPS_RBAC_IF_MATCH_REQUIRED_CODE.to_string(),
        ));
    }
    Ok(())
}

#[derive(Debug, Clone, Copy)]
struct OpsRbacAuditOutboxInput<'a> {
    event_type: &'a str,
    operator_user_id: i64,
    target_user_id: Option<i64>,
    decision: &'a str,
    request_id: Option<&'a str>,
    result_count: Option<i64>,
    role: Option<&'a str>,
    removed: Option<bool>,
    error_code: Option<&'a str>,
    failure_reason: Option<&'a str>,
}

async fn acquire_ops_rbac_revision_lock(
    tx: &mut Transaction<'_, Postgres>,
) -> Result<(), AppError> {
    // 控制面写频率低，这里用事务级 advisory lock 让 If-Match 校验与落库具备串行语义。
    sqlx::query("SELECT pg_advisory_xact_lock(hashtext($1))")
        .bind(OPS_RBAC_WRITE_REVISION_LOCK_KEY)
        .execute(&mut **tx)
        .await?;
    Ok(())
}

async fn enqueue_ops_rbac_audit_outbox_job_tx(
    tx: &mut Transaction<'_, Postgres>,
    input: OpsRbacAuditOutboxInput<'_>,
) -> Result<(), AppError> {
    sqlx::query(
        r#"
        INSERT INTO ops_rbac_audit_outbox_jobs(
            event_type,
            operator_user_id,
            target_user_id,
            decision,
            request_id,
            result_count,
            role,
            removed,
            error_code,
            failure_reason,
            attempts,
            next_retry_at,
            locked_until,
            delivered_at,
            last_error,
            created_at,
            updated_at
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            0, NOW(), NULL, NULL, NULL, NOW(), NOW()
        )
        "#,
    )
    .bind(input.event_type)
    .bind(input.operator_user_id)
    .bind(input.target_user_id)
    .bind(input.decision)
    .bind(input.request_id)
    .bind(input.result_count)
    .bind(input.role)
    .bind(input.removed)
    .bind(input.error_code)
    .bind(input.failure_reason)
    .execute(&mut **tx)
    .await?;
    Ok(())
}

impl AppState {
    pub(crate) async fn get_ops_rbac_revision(&self) -> Result<String, AppError> {
        let revision: Option<DateTime<Utc>> = sqlx::query_scalar(
            r#"
            SELECT MAX(updated_at)
            FROM (
                SELECT updated_at
                FROM platform_user_roles
                UNION ALL
                SELECT updated_at
                FROM platform_admin_owners
            ) updates
            "#,
        )
        .fetch_one(&self.pool)
        .await?;
        Ok(revision
            .map(format_rbac_revision)
            .unwrap_or_else(|| OPS_RBAC_EMPTY_REVISION.to_string()))
    }

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
        let rbac_revision = self.get_ops_rbac_revision().await?;
        if owner_id == user.id {
            return Ok(GetOpsRbacMeOutput {
                user_id: user.id as u64,
                is_owner: true,
                role: None,
                permissions: OpsPermissionFlags {
                    debate_manage: true,
                    judge_review: true,
                    judge_rejudge: true,
                    observability_read: true,
                    observability_manage: true,
                    role_manage: true,
                },
                rbac_revision,
            });
        }

        let role = self.find_ops_role_for_user(user.id).await?;
        let permissions = if let Some(role_value) = role.as_deref() {
            OpsPermissionFlags {
                debate_manage: role_grants_permission(role_value, OpsPermission::DebateManage),
                judge_review: role_grants_permission(role_value, OpsPermission::JudgeReview),
                judge_rejudge: role_grants_permission(role_value, OpsPermission::JudgeRejudge),
                observability_read: role_grants_permission(
                    role_value,
                    OpsPermission::ObservabilityRead,
                ),
                observability_manage: role_grants_permission(
                    role_value,
                    OpsPermission::ObservabilityManage,
                ),
                role_manage: role_grants_role_manage(role_value),
            }
        } else {
            OpsPermissionFlags {
                debate_manage: false,
                judge_review: false,
                judge_rejudge: false,
                observability_read: false,
                observability_manage: false,
                role_manage: false,
            }
        };

        Ok(GetOpsRbacMeOutput {
            user_id: user.id as u64,
            is_owner: false,
            role,
            permissions,
            rbac_revision,
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

    async fn resolve_ops_role_manage_context(
        &self,
        user: &User,
    ) -> Result<OpsRoleManageContext, AppError> {
        let owner_id = self.get_platform_admin_user_id().await?;
        if owner_id == user.id {
            return Ok(OpsRoleManageContext {
                owner_user_id: owner_id,
                access: OpsRoleManageAccess::Owner,
            });
        }
        let role = self.find_ops_role_for_user(user.id).await?;
        if matches!(role.as_deref(), Some(ROLE_PLATFORM_ROLE_ADMIN)) {
            return Ok(OpsRoleManageContext {
                owner_user_id: owner_id,
                access: OpsRoleManageAccess::DelegatedRoleAdmin,
            });
        }
        Err(AppError::DebateConflict(
            OPS_RBAC_PERMISSION_DENIED_ROLE_MANAGE_CODE.to_string(),
        ))
    }

    fn enforce_delegated_role_manage_constraints(
        context: OpsRoleManageContext,
        target_user_id: i64,
        target_role: Option<&str>,
    ) -> Result<(), AppError> {
        if context.access != OpsRoleManageAccess::DelegatedRoleAdmin {
            return Ok(());
        }
        // 委派管理员是受限治理角色：不能改 owner，也不能管理同级委派资格。
        if target_user_id == context.owner_user_id {
            return Err(role_manage_permission_denied(
                "delegated_role_admin_cannot_manage_owner",
            ));
        }
        if matches!(target_role, Some(ROLE_PLATFORM_ROLE_ADMIN)) {
            return Err(role_manage_permission_denied(
                "delegated_role_admin_cannot_manage_role_admin",
            ));
        }
        Ok(())
    }

    pub async fn list_ops_role_assignments_by_owner(
        &self,
        user: &User,
        pii_level: OpsRbacPiiLevel,
    ) -> Result<ListOpsRoleAssignmentsOutput, AppError> {
        self.resolve_ops_role_manage_context(user).await?;
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
                .map(|row| map_assignment_row_with_pii_level(row, pii_level))
                .collect::<Result<Vec<_>, _>>()?,
            rbac_revision: self.get_ops_rbac_revision().await?,
        })
    }

    pub async fn upsert_ops_role_assignment_by_owner(
        &self,
        user: &User,
        target_user_id: u64,
        input: UpsertOpsRoleInput,
    ) -> Result<OpsRoleAssignment, AppError> {
        let (assignment, _) = self
            .upsert_ops_role_assignment_by_owner_with_meta(
                user,
                target_user_id,
                input,
                OpsRbacUpsertMeta::default(),
            )
            .await?;
        Ok(assignment)
    }

    pub async fn upsert_ops_role_assignment_by_owner_with_meta(
        &self,
        user: &User,
        target_user_id: u64,
        input: UpsertOpsRoleInput,
        meta: OpsRbacUpsertMeta<'_>,
    ) -> Result<(OpsRoleAssignment, bool), AppError> {
        let role_manage_context = self.resolve_ops_role_manage_context(user).await?;
        let role = normalize_ops_role(&input.role)?;
        let target_user_id =
            checked_u64_to_i64(target_user_id, OPS_RBAC_TARGET_USER_ID_OUT_OF_RANGE_CODE)?;
        Self::enforce_delegated_role_manage_constraints(
            role_manage_context,
            target_user_id,
            Some(role.as_str()),
        )?;

        if let Some(idempotency_key) = meta.idempotency_key {
            let mut tx = self.pool.begin().await?;
            acquire_ops_rbac_revision_lock(&mut tx).await?;
            let current_revision = get_ops_rbac_revision_tx(&mut tx).await?;
            ensure_expected_ops_rbac_revision(
                meta.expected_rbac_revision,
                &current_revision,
                meta.require_if_match,
            )?;
            let advisory_lock_key = format!(
                "ops_rbac_role_upsert:{}:{}:{}",
                user.id, target_user_id, idempotency_key
            );
            sqlx::query("SELECT pg_advisory_xact_lock(hashtext($1))")
                .bind(&advisory_lock_key)
                .execute(&mut *tx)
                .await?;

            let idempotency_created_at: Option<DateTime<Utc>> = sqlx::query_scalar(
                r#"
                SELECT created_at
                FROM ops_rbac_role_upsert_idempotency_keys
                WHERE operator_user_id = $1
                  AND target_user_id = $2
                  AND idempotency_key = $3
                "#,
            )
            .bind(user.id)
            .bind(target_user_id)
            .bind(idempotency_key)
            .fetch_optional(&mut *tx)
            .await?;
            if let Some(created_at) = idempotency_created_at {
                let now = Utc::now();
                let age_secs = now.signed_duration_since(created_at).num_seconds();
                let is_fresh =
                    meta.idempotency_ttl_secs == 0 || age_secs < meta.idempotency_ttl_secs as i64;
                if is_fresh {
                    let existing_row: Option<OpsRoleAssignmentRow> = sqlx::query_as(
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
                        WHERE r.user_id = $1
                        "#,
                    )
                    .bind(target_user_id)
                    .fetch_optional(&mut *tx)
                    .await?;
                    if let Some(existing_row) = existing_row {
                        tx.commit().await?;
                        return Ok((map_assignment_row(existing_row)?, true));
                    }
                }
                sqlx::query(
                    r#"
                    DELETE FROM ops_rbac_role_upsert_idempotency_keys
                    WHERE operator_user_id = $1
                      AND target_user_id = $2
                      AND idempotency_key = $3
                    "#,
                )
                .bind(user.id)
                .bind(target_user_id)
                .bind(idempotency_key)
                .execute(&mut *tx)
                .await?;
            }

            let row: Option<OpsRoleAssignmentRow> = sqlx::query_as(
                r#"
                WITH upserted AS (
                    INSERT INTO platform_user_roles(
                        user_id, role, granted_by, created_at, updated_at
                    )
                    SELECT u.id, $2, $3, NOW(), NOW()
                    FROM users u
                    WHERE u.id = $1
                    ON CONFLICT (user_id)
                    DO UPDATE
                    SET role = EXCLUDED.role,
                        granted_by = EXCLUDED.granted_by,
                        updated_at = NOW()
                    RETURNING
                        user_id,
                        role,
                        granted_by,
                        created_at,
                        updated_at
                )
                SELECT
                    up.user_id,
                    COALESCE(u.email, '') AS user_email,
                    u.fullname AS user_fullname,
                    up.role,
                    up.granted_by,
                    up.created_at,
                    up.updated_at
                FROM upserted up
                JOIN users u ON u.id = up.user_id
                "#,
            )
            .bind(target_user_id)
            .bind(role.as_str())
            .bind(user.id)
            .fetch_optional(&mut *tx)
            .await?;
            let row = row.ok_or_else(|| {
                AppError::NotFound(OPS_RBAC_TARGET_USER_NOT_FOUND_CODE.to_string())
            })?;

            sqlx::query(
                r#"
                INSERT INTO ops_rbac_role_upsert_idempotency_keys(
                    operator_user_id,
                    target_user_id,
                    idempotency_key,
                    role,
                    created_at
                )
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (operator_user_id, target_user_id, idempotency_key)
                DO UPDATE
                SET role = EXCLUDED.role,
                    created_at = NOW()
                "#,
            )
            .bind(user.id)
            .bind(target_user_id)
            .bind(idempotency_key)
            .bind(role.as_str())
            .execute(&mut *tx)
            .await?;
            enqueue_ops_rbac_audit_outbox_job_tx(
                &mut tx,
                OpsRbacAuditOutboxInput {
                    event_type: OPS_RBAC_AUDIT_EVENT_ROLE_UPSERT,
                    operator_user_id: user.id,
                    target_user_id: Some(target_user_id),
                    decision: "success",
                    request_id: meta.success_request_id,
                    result_count: None,
                    role: Some(role.as_str()),
                    removed: None,
                    error_code: None,
                    failure_reason: None,
                },
            )
            .await?;
            tx.commit().await?;
            return Ok((map_assignment_row(row)?, false));
        }

        let mut tx = self.pool.begin().await?;
        acquire_ops_rbac_revision_lock(&mut tx).await?;
        let current_revision = get_ops_rbac_revision_tx(&mut tx).await?;
        ensure_expected_ops_rbac_revision(
            meta.expected_rbac_revision,
            &current_revision,
            meta.require_if_match,
        )?;

        let row: Option<OpsRoleAssignmentRow> = sqlx::query_as(
            r#"
            WITH upserted AS (
                INSERT INTO platform_user_roles(
                    user_id, role, granted_by, created_at, updated_at
                )
                SELECT u.id, $2, $3, NOW(), NOW()
                FROM users u
                WHERE u.id = $1
                ON CONFLICT (user_id)
                DO UPDATE
                SET role = EXCLUDED.role,
                    granted_by = EXCLUDED.granted_by,
                    updated_at = NOW()
                RETURNING
                    user_id,
                    role,
                    granted_by,
                    created_at,
                    updated_at
            )
            SELECT
                up.user_id,
                COALESCE(u.email, '') AS user_email,
                u.fullname AS user_fullname,
                up.role,
                up.granted_by,
                up.created_at,
                up.updated_at
            FROM upserted up
            JOIN users u ON u.id = up.user_id
            "#,
        )
        .bind(target_user_id)
        .bind(role.as_str())
        .bind(user.id)
        .fetch_optional(&mut *tx)
        .await?;
        let row =
            row.ok_or_else(|| AppError::NotFound(OPS_RBAC_TARGET_USER_NOT_FOUND_CODE.to_string()))?;
        enqueue_ops_rbac_audit_outbox_job_tx(
            &mut tx,
            OpsRbacAuditOutboxInput {
                event_type: OPS_RBAC_AUDIT_EVENT_ROLE_UPSERT,
                operator_user_id: user.id,
                target_user_id: Some(target_user_id),
                decision: "success",
                request_id: meta.success_request_id,
                result_count: None,
                role: Some(role.as_str()),
                removed: None,
                error_code: None,
                failure_reason: None,
            },
        )
        .await?;
        tx.commit().await?;
        Ok((map_assignment_row(row)?, false))
    }

    pub async fn revoke_ops_role_assignment_by_owner(
        &self,
        user: &User,
        target_user_id: u64,
    ) -> Result<RevokeOpsRoleOutput, AppError> {
        self.revoke_ops_role_assignment_by_owner_with_meta(
            user,
            target_user_id,
            OpsRbacRevokeMeta::default(),
        )
        .await
    }

    pub async fn revoke_ops_role_assignment_by_owner_with_meta(
        &self,
        user: &User,
        target_user_id: u64,
        meta: OpsRbacRevokeMeta<'_>,
    ) -> Result<RevokeOpsRoleOutput, AppError> {
        let role_manage_context = self.resolve_ops_role_manage_context(user).await?;
        let target_user_id =
            checked_u64_to_i64(target_user_id, OPS_RBAC_TARGET_USER_ID_OUT_OF_RANGE_CODE)?;
        let target_role = self.find_ops_role_for_user(target_user_id).await?;
        Self::enforce_delegated_role_manage_constraints(
            role_manage_context,
            target_user_id,
            target_role.as_deref(),
        )?;
        let target_user_id_u64 = checked_i64_to_u64(
            target_user_id,
            OPS_RBAC_ROLE_ASSIGNMENT_USER_ID_INVALID_CODE,
        )?;
        let mut tx = self.pool.begin().await?;
        acquire_ops_rbac_revision_lock(&mut tx).await?;
        let current_revision = get_ops_rbac_revision_tx(&mut tx).await?;
        ensure_expected_ops_rbac_revision(
            meta.expected_rbac_revision,
            &current_revision,
            meta.require_if_match,
        )?;

        let removed = sqlx::query_scalar::<_, i64>(
            r#"
            DELETE FROM platform_user_roles
            WHERE user_id = $1
            RETURNING user_id
            "#,
        )
        .bind(target_user_id)
        .fetch_optional(&mut *tx)
        .await?
        .is_some();
        enqueue_ops_rbac_audit_outbox_job_tx(
            &mut tx,
            OpsRbacAuditOutboxInput {
                event_type: OPS_RBAC_AUDIT_EVENT_ROLE_REVOKE,
                operator_user_id: user.id,
                target_user_id: Some(target_user_id),
                decision: "success",
                request_id: meta.success_request_id,
                result_count: None,
                role: None,
                removed: Some(removed),
                error_code: None,
                failure_reason: None,
            },
        )
        .await?;
        tx.commit().await?;

        Ok(RevokeOpsRoleOutput {
            user_id: target_user_id_u64,
            removed,
        })
    }

    pub async fn grant_platform_admin(&self, user_id: u64) -> Result<(), AppError> {
        let user_id = checked_u64_to_i64(user_id, OPS_RBAC_TARGET_USER_ID_OUT_OF_RANGE_CODE)?;
        let user_exists: Option<(i64,)> = sqlx::query_as("SELECT id FROM users WHERE id = $1")
            .bind(user_id)
            .fetch_optional(&self.pool)
            .await?;
        if user_exists.is_none() {
            return Err(AppError::NotFound(
                OPS_RBAC_TARGET_USER_NOT_FOUND_CODE.to_string(),
            ));
        }
        let mut tx = self.pool.begin().await?;
        let previous_owner_id: Option<i64> = sqlx::query_scalar(
            r#"
            SELECT owner_user_id
            FROM platform_admin_owners
            WHERE singleton_key = TRUE
            LIMIT 1
            FOR UPDATE
            "#,
        )
        .fetch_optional(&mut *tx)
        .await?;
        // 先复用旧 owner 作为授权来源，缺省再回退到 user=1，最后才自授权。
        let granted_by = if let Some(owner_id) = previous_owner_id {
            owner_id
        } else {
            sqlx::query_scalar::<_, i64>("SELECT id FROM users WHERE id = 1")
                .fetch_optional(&mut *tx)
                .await?
                .unwrap_or(user_id)
        };
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
        .bind(user_id)
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
        .bind(user_id)
        .bind(granted_by)
        .execute(&mut *tx)
        .await?;
        if let Some(old_owner_id) = previous_owner_id.filter(|value| *value != user_id) {
            sqlx::query("DELETE FROM platform_user_roles WHERE user_id = $1")
                .bind(old_owner_id)
                .execute(&mut *tx)
                .await?;
        }
        tx.commit().await?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::CreateUser;
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
        state
            .ensure_ops_permission(&user, OpsPermission::ObservabilityManage)
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
        state
            .ensure_ops_permission(&user, OpsPermission::ObservabilityRead)
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
        let observability_manage_err = state
            .ensure_ops_permission(&user, OpsPermission::ObservabilityManage)
            .await
            .expect_err("viewer should not manage observability");
        match observability_manage_err {
            AppError::DebateConflict(msg) => {
                assert!(msg.contains("ops_permission_denied:observability_manage:"))
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
        assert!(owner_snapshot.permissions.observability_read);
        assert!(owner_snapshot.permissions.observability_manage);
        assert!(owner_snapshot.permissions.role_manage);
        assert_ne!(owner_snapshot.rbac_revision, OPS_RBAC_EMPTY_REVISION);

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
        assert!(viewer_snapshot.permissions.observability_read);
        assert!(!viewer_snapshot.permissions.observability_manage);
        assert!(!viewer_snapshot.permissions.role_manage);
        assert_ne!(viewer_snapshot.rbac_revision, OPS_RBAC_EMPTY_REVISION);
        Ok(())
    }

    #[tokio::test]
    async fn get_ops_rbac_me_should_grant_role_manage_for_delegated_role_admin() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let delegated = state
            .create_user(&CreateUser {
                fullname: "Delegated Role Admin".to_string(),
                email: "delegated-role-admin@acme.org".to_string(),
                password: "123456".to_string(),
            })
            .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                delegated.id as u64,
                UpsertOpsRoleInput {
                    role: ROLE_PLATFORM_ROLE_ADMIN.to_string(),
                },
            )
            .await?;

        let delegated_snapshot = state.get_ops_rbac_me(&delegated).await?;
        assert!(!delegated_snapshot.is_owner);
        assert_eq!(
            delegated_snapshot.role.as_deref(),
            Some(ROLE_PLATFORM_ROLE_ADMIN)
        );
        assert!(!delegated_snapshot.permissions.debate_manage);
        assert!(!delegated_snapshot.permissions.judge_review);
        assert!(!delegated_snapshot.permissions.judge_rejudge);
        assert!(!delegated_snapshot.permissions.observability_read);
        assert!(!delegated_snapshot.permissions.observability_manage);
        assert!(delegated_snapshot.permissions.role_manage);
        assert_ne!(delegated_snapshot.rbac_revision, OPS_RBAC_EMPTY_REVISION);

        let err = state
            .ensure_ops_permission(&delegated, OpsPermission::DebateManage)
            .await
            .expect_err("delegated role admin should not manage debate directly");
        match err {
            AppError::DebateConflict(msg) => {
                assert!(msg.contains("ops_permission_denied:debate_manage:"))
            }
            other => panic!("unexpected error: {other}"),
        }
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
        assert_ne!(next_snapshot.rbac_revision, OPS_RBAC_EMPTY_REVISION);

        let old_owner_snapshot = state.get_ops_rbac_me(&owner).await?;
        assert!(!old_owner_snapshot.is_owner);
        assert!(!old_owner_snapshot.permissions.observability_read);
        assert!(!old_owner_snapshot.permissions.observability_manage);
        assert!(!old_owner_snapshot.permissions.role_manage);
        assert_ne!(old_owner_snapshot.rbac_revision, OPS_RBAC_EMPTY_REVISION);
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

        let list = state
            .list_ops_role_assignments_by_owner(&owner, OpsRbacPiiLevel::Full)
            .await?;
        assert!(!list.items.is_empty());
        assert_ne!(list.rbac_revision, OPS_RBAC_EMPTY_REVISION);
        assert!(list
            .items
            .iter()
            .any(|item| item.user_id == 2 && item.role == "ops_reviewer"));

        let revoked = state.revoke_ops_role_assignment_by_owner(&owner, 2).await?;
        assert!(revoked.removed);

        let list_after = state
            .list_ops_role_assignments_by_owner(&owner, OpsRbacPiiLevel::Full)
            .await?;
        assert!(list_after.items.iter().all(|item| item.user_id != 2));
        assert_ne!(list_after.rbac_revision, OPS_RBAC_EMPTY_REVISION);
        Ok(())
    }

    #[tokio::test]
    async fn upsert_with_meta_should_enqueue_success_audit_outbox() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let request_id = "req-upsert-tx";

        let (_assignment, replayed) = state
            .upsert_ops_role_assignment_by_owner_with_meta(
                &owner,
                2,
                UpsertOpsRoleInput {
                    role: "ops_reviewer".to_string(),
                },
                OpsRbacUpsertMeta {
                    success_request_id: Some(request_id),
                    ..OpsRbacUpsertMeta::default()
                },
            )
            .await?;
        assert!(!replayed);

        let outbox_count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(*)::bigint
            FROM ops_rbac_audit_outbox_jobs
            WHERE event_type = 'role_upsert'
              AND operator_user_id = $1
              AND target_user_id = $2
              AND decision = 'success'
              AND request_id = $3
              AND role = $4
            "#,
        )
        .bind(owner.id)
        .bind(2_i64)
        .bind(request_id)
        .bind("ops_reviewer")
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(outbox_count, 1);
        Ok(())
    }

    #[tokio::test]
    async fn upsert_with_meta_replay_should_not_duplicate_success_audit_outbox() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");

        let (_first, replayed_first) = state
            .upsert_ops_role_assignment_by_owner_with_meta(
                &owner,
                2,
                UpsertOpsRoleInput {
                    role: "ops_viewer".to_string(),
                },
                OpsRbacUpsertMeta {
                    idempotency_key: Some("idem-key-1"),
                    idempotency_ttl_secs: 30,
                    success_request_id: Some("req-upsert-first"),
                    ..OpsRbacUpsertMeta::default()
                },
            )
            .await?;
        assert!(!replayed_first);

        let (_second, replayed_second) = state
            .upsert_ops_role_assignment_by_owner_with_meta(
                &owner,
                2,
                UpsertOpsRoleInput {
                    role: "ops_viewer".to_string(),
                },
                OpsRbacUpsertMeta {
                    idempotency_key: Some("idem-key-1"),
                    idempotency_ttl_secs: 30,
                    success_request_id: Some("req-upsert-second"),
                    ..OpsRbacUpsertMeta::default()
                },
            )
            .await?;
        assert!(replayed_second);

        let outbox_count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(*)::bigint
            FROM ops_rbac_audit_outbox_jobs
            WHERE event_type = 'role_upsert'
              AND operator_user_id = $1
              AND target_user_id = $2
              AND decision = 'success'
            "#,
        )
        .bind(owner.id)
        .bind(2_i64)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(outbox_count, 1);
        Ok(())
    }

    #[tokio::test]
    async fn revoke_with_meta_should_enqueue_success_audit_outbox() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let request_id = "req-revoke-tx";
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                2,
                UpsertOpsRoleInput {
                    role: "ops_reviewer".to_string(),
                },
            )
            .await?;

        let output = state
            .revoke_ops_role_assignment_by_owner_with_meta(
                &owner,
                2,
                OpsRbacRevokeMeta {
                    success_request_id: Some(request_id),
                    ..OpsRbacRevokeMeta::default()
                },
            )
            .await?;
        assert!(output.removed);

        let outbox_count: i64 = sqlx::query_scalar(
            r#"
            SELECT COUNT(*)::bigint
            FROM ops_rbac_audit_outbox_jobs
            WHERE event_type = 'role_revoke'
              AND operator_user_id = $1
              AND target_user_id = $2
              AND decision = 'success'
              AND request_id = $3
              AND removed = $4
            "#,
        )
        .bind(owner.id)
        .bind(2_i64)
        .bind(request_id)
        .bind(true)
        .fetch_one(&state.pool)
        .await?;
        assert_eq!(outbox_count, 1);
        Ok(())
    }

    #[tokio::test]
    async fn delegated_role_admin_should_manage_ops_roles_with_guardrails() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let delegated = state
            .create_user(&CreateUser {
                fullname: "Delegated Manager".to_string(),
                email: "delegated-manager@acme.org".to_string(),
                password: "123456".to_string(),
            })
            .await?;
        let target_regular = state
            .create_user(&CreateUser {
                fullname: "Regular Target".to_string(),
                email: "delegated-regular-target@acme.org".to_string(),
                password: "123456".to_string(),
            })
            .await?;
        let target_role_admin = state
            .create_user(&CreateUser {
                fullname: "Role Admin Target".to_string(),
                email: "delegated-role-admin-target@acme.org".to_string(),
                password: "123456".to_string(),
            })
            .await?;

        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                delegated.id as u64,
                UpsertOpsRoleInput {
                    role: ROLE_PLATFORM_ROLE_ADMIN.to_string(),
                },
            )
            .await?;
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                target_role_admin.id as u64,
                UpsertOpsRoleInput {
                    role: ROLE_PLATFORM_ROLE_ADMIN.to_string(),
                },
            )
            .await?;

        let assigned = state
            .upsert_ops_role_assignment_by_owner(
                &delegated,
                target_regular.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_reviewer".to_string(),
                },
            )
            .await?;
        assert_eq!(assigned.user_id, target_regular.id as u64);
        assert_eq!(assigned.role, "ops_reviewer");

        let revoke_regular = state
            .revoke_ops_role_assignment_by_owner(&delegated, target_regular.id as u64)
            .await?;
        assert!(revoke_regular.removed);

        let assign_owner_err = state
            .upsert_ops_role_assignment_by_owner(
                &delegated,
                owner.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_viewer".to_string(),
                },
            )
            .await
            .expect_err("delegated role admin should not manage owner");
        match assign_owner_err {
            AppError::DebateConflict(code) => assert_eq!(
                code,
                format!(
                    "{OPS_RBAC_PERMISSION_DENIED_ROLE_MANAGE_CODE}:delegated_role_admin_cannot_manage_owner"
                )
            ),
            other => panic!("unexpected error: {other}"),
        }

        let assign_role_admin_err = state
            .upsert_ops_role_assignment_by_owner(
                &delegated,
                target_regular.id as u64,
                UpsertOpsRoleInput {
                    role: ROLE_PLATFORM_ROLE_ADMIN.to_string(),
                },
            )
            .await
            .expect_err("delegated role admin should not assign role admin");
        match assign_role_admin_err {
            AppError::DebateConflict(code) => assert_eq!(
                code,
                format!(
                    "{OPS_RBAC_PERMISSION_DENIED_ROLE_MANAGE_CODE}:delegated_role_admin_cannot_manage_role_admin"
                )
            ),
            other => panic!("unexpected error: {other}"),
        }

        let revoke_role_admin_err = state
            .revoke_ops_role_assignment_by_owner(&delegated, target_role_admin.id as u64)
            .await
            .expect_err("delegated role admin should not revoke role admin");
        match revoke_role_admin_err {
            AppError::DebateConflict(code) => assert_eq!(
                code,
                format!(
                    "{OPS_RBAC_PERMISSION_DENIED_ROLE_MANAGE_CODE}:delegated_role_admin_cannot_manage_role_admin"
                )
            ),
            other => panic!("unexpected error: {other}"),
        }
        Ok(())
    }

    #[tokio::test]
    async fn list_ops_role_assignments_by_owner_should_mask_pii_in_minimal_mode() -> Result<()> {
        let (_tdb, state) = AppState::new_for_test().await?;
        state.grant_platform_admin(1).await?;
        let owner = state.find_user_by_id(1).await?.expect("owner should exist");
        let user = state.find_user_by_id(2).await?.expect("user should exist");
        state
            .upsert_ops_role_assignment_by_owner(
                &owner,
                user.id as u64,
                UpsertOpsRoleInput {
                    role: "ops_reviewer".to_string(),
                },
            )
            .await?;

        let masked = state
            .list_ops_role_assignments_by_owner(&owner, OpsRbacPiiLevel::Minimal)
            .await?;
        let full = state
            .list_ops_role_assignments_by_owner(&owner, OpsRbacPiiLevel::Full)
            .await?;

        let masked_item = masked
            .items
            .iter()
            .find(|item| item.user_id == user.id as u64)
            .expect("masked role assignment should exist");
        let full_item = full
            .items
            .iter()
            .find(|item| item.user_id == user.id as u64)
            .expect("full role assignment should exist");

        assert_eq!(full_item.user_email, user.email);
        assert_eq!(full_item.user_fullname, user.fullname);
        assert_ne!(masked_item.user_email, user.email);
        assert_ne!(masked_item.user_fullname, user.fullname);
        assert!(masked_item.user_email.contains("***"));
        assert!(masked_item.user_fullname.contains("***"));
        Ok(())
    }
}
