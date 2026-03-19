# chat/migrations 规范

本目录使用 `sqlx` 时间戳迁移，目标是“可回放、可审计、可追责”。

## 1. 命名规范

- 文件名固定：`YYYYMMDDHHMMSS_<domain>_<change>.sql`
- 一条 migration 只表达一个业务意图（单一职责）。
- domain 建议复用现有业务词：`auth`、`debate`、`judge`、`iap`、`ops`、`workspace_removal`。

## 2. DDL 编写规则

- 核心 schema 变更默认 **fail-fast**：
  - 不使用 `CREATE TABLE IF NOT EXISTS`
  - 不使用 `CREATE INDEX IF NOT EXISTS`
  - 不使用 `ADD COLUMN IF NOT EXISTS`
- 允许保留 `IF NOT EXISTS` 的场景（需在 SQL 顶部注释说明原因）：
  - `CREATE EXTENSION IF NOT EXISTS ...`
  - 明确“兼容桥接窗口”迁移（例如历史租户兼容 shim）

## 3. 基线与历史策略

- 当前仓库采用“本地可重置”策略，允许在重构窗口回写历史 migration。
- 一旦进入线上/共享环境，迁移历史应改为不可变（append-only）。
- 当字段已成为基础模型稳定字段（例如 `users.token_version`），应优先并入基线建表迁移，再把后续“补字段迁移”收敛为 no-op 或只保留独立职责。

## 4. 回滚与修复

- 优先使用“前向修复”新增 migration，不在运行中环境回滚历史 SQL。
- `chat/scripts/repair_runtime_schema.sh` 为应急脚本，不作为默认初始化路径。

## 5. 提交前检查清单

- 命名是否符合时间戳规范。
- 是否做到单 migration 单意图。
- 是否误用了 `IF NOT EXISTS` / `IF EXISTS`。
- fresh DB 回放是否成功。
- 关键约束（`NOT NULL`、`UNIQUE`、`CHECK`、`FK`）是否可在 SQL 中直接读懂。
