# EchoIsle Codex 生产级交付 v1 改造清单

更新时间：2026-04-12  
状态：可执行 v1（按 P0/P1 优先级落地）

---

2026-04-13 更新：

1. 本清单中依赖旧 orchestration / module-turn 入口的条目已作废。
2. `module-turn-harness` 已退役并删除，不再作为生产级交付改造目标。
3. 后续若继续推进生产级交付治理，应基于 `docs/harness/task-flows/` 与具体 leaf skill/guard 重新拆分计划。

---

## 1. 目标与边界

目标：
1. 让每次 Codex 回合都具备“可阻断、可审计、可复盘”的工程化闭环。
2. 在不改变既有业务行为和对外 API 的前提下，提高“产出生产级代码”的一致性。

边界：
1. v1 只做工程流程与门禁改造，不做业务重构。
2. v1 允许短期豁免，但必须结构化且可过期阻断。

---

## 2. v1 完成标准（必须同时满足）

1. 高风险回合默认强制 runtime verify，缺证据即失败。
2. API/DTO/错误码/WS payload 变更必须通过 contract sync guard。
3. 每次模块开发回合必须产出 self-review 结构化报告，缺项即失败。
4. Python strict 白名单、Rust advisory 豁免清单只能减不能增（增量需审批字段）。
5. CI 必须有可追溯证据产物（harness summary + runtime verify + self-review）。

---

## 3. 改造清单（P0，先做）

| ID | 必改文件/脚本 | 新增字段/参数 | 阻断失败条件（Fail-Closed） | 验收命令 |
| --- | --- | --- | --- | --- |
| P0-1 | 已作废：原目标为 `scripts/harness/module_turn_harness.sh` | `module-turn-harness` 已退役并删除 | 不再执行 | 后续基于 task flow 与具体 leaf skill 重新规划 |
| P0-2 | 已作废：原目标为 `scripts/harness/module_turn_harness.sh` summary 输出逻辑 | `module-turn-harness` 已退役并删除 | 不再执行 | 后续基于 task flow 与具体 leaf skill 重新规划 |
| P0-3 | `scripts/harness/journey_verify.sh` | 新增参数：`--enforce`、`--require-evidence`；在 checks 中增加 `executed`、`evidence_required`、`evidence_found` | `--enforce` 时出现 `fail/env_blocked/evidence_missing` 任一状态即退出非 0；`--require-evidence` 且证据文件不存在 | `bash scripts/harness/journey_verify.sh --profile auth --enforce --require-evidence --emit-json /tmp/journey.json --emit-md /tmp/journey.md` |
| P0-4 | 新增：`skills/post-module-contract-sync-guard/scripts/check_contract_sync.sh` | 输入参数：`--root`、`--base-ref`、`--head-ref`、`--report-out`；输出 JSON 字段：`api_changed`、`openapi_synced`、`sdk_synced`、`tests_synced` | 变更命中 API/DTO/错误码/WS payload，但未同时命中 OpenAPI 或 SDK/domain 或测试更新；报告缺关键字段 | `bash skills/post-module-contract-sync-guard/scripts/check_contract_sync.sh --root . --base-ref origin/master --head-ref HEAD --report-out /tmp/contract-sync.json` |
| P0-5 | 新增：`skills/post-module-self-review/scripts/generate_self_review.sh` + `check_self_review.sh` | 报告固定章节字段：`risk_assumptions`、`uncovered_scope`、`rollback_plan`、`runtime_observability`、`followups` | 缺章节、空章节、`risk-level=high` 但 `rollback_plan` 为空；未生成报告文件 | `bash skills/post-module-self-review/scripts/check_self_review.sh --risk-level high --report /tmp/self-review.md` |
| P0-6 | `.github/workflows/build.yml` | 新增 job：`harness-governance`；执行 `harness_docs_lint`、`contract-sync-guard`、`self-review-check`、summary schema 校验 | 任一治理检查失败即阻断 PR；缺少必须 artifacts（summary/runtime/self-review）即失败 | 在 PR 触发 CI，确认 `harness-governance` 为 required |

---

## 4. 改造清单（P1，紧随其后）

| ID | 必改文件/脚本 | 新增字段/参数 | 阻断失败条件（Fail-Closed） | 验收命令 |
| --- | --- | --- | --- | --- |
| P1-1 | 新增：`scripts/quality/python_strict_debt_guard.sh` | 基线文件：`ai_judge_service/docs/typing/strict_whitelist.baseline.txt` | strict 白名单模块数增加；新增模块未附 `owner/reason/expires_on` | `bash scripts/quality/python_strict_debt_guard.sh --root .` |
| P1-2 | 新增：`scripts/release/supply_chain_allowlist_budget_guard.sh` | 对 `cargo_deny_advisories_allowlist.csv` 增加字段校验：`owner/reason/expires_on`（可扩展 `ticket`） | 新增豁免无 owner/reason/expires_on；到期日超 14 天；活跃豁免总量较基线上升 | `bash scripts/release/supply_chain_allowlist_budget_guard.sh --root . --max-expire-days 14` |
| P1-3 | `skills/post-module-test-guard/scripts/run_test_gate.sh` | 统一 nextest 参数（去除与 CI 分叉）；新增 `--ci-parity` 模式 | 本地门禁与 CI 命令不一致；`--ci-parity` 模式检查失败 | `bash skills/post-module-test-guard/scripts/run_test_gate.sh --mode full --ci-parity` |
| P1-4 | 已作废：原目标为旧 orchestration / module-turn 入口与 `AGENTS.md` | `module-turn-harness` 已退役并删除 | 不再执行 | 后续基于 task flow 与具体 leaf skill 重新规划 |

---

## 5. 必补测试（v1 最小集）

| 测试域 | 必新增位置 | 最小覆盖要求 | 阻断条件 |
| --- | --- | --- | --- |
| API 契约测试 | `chat/.../tests/contract/`，`ai_judge_service/tests/contract/` | 每个外部 API 至少 1 个契约快照测试（成功+失败） | API/DTO 改动但无契约测试更新 |
| 幂等/并发测试 | `chat/.../tests/idempotency/` | 至少覆盖重复请求、并发写入、补偿链路 | 改事务/幂等逻辑但无并发回归测试 |
| AI Judge 金标回归 | `ai_judge_service/tests/golden/` | 固定样本集 + 期望输出阈值 | 改 prompt/裁判策略但无金标回归结果 |
| 关键旅程 E2E | `frontend/tests/e2e/` | `auth/lobby/room/judge-ops` 各至少 1 条阻断级场景 | 改主流程但无对应旅程 smoke 证据 |
| 迁移测试 | `chat/migrations` 对应测试脚本 | 至少覆盖 migrate up + 回滚可行性验证 | 改 schema/migration 但无迁移验证 |

---

## 6. 建议执行顺序（10 个工作日）

1. Day 1-2：完成 P0-1、P0-2（harness 参数与 summary 字段）。
2. Day 3：完成 P0-3（journey verify enforce）。
3. Day 4-5：完成 P0-4、P0-5（contract sync + self-review 两个 guard）。
4. Day 6：完成 P0-6（CI `harness-governance`）。
5. Day 7-8：完成 P1-1、P1-2（strict/allowlist 债务预算门禁）。
6. Day 9：完成 P1-3（本地与 CI 测试参数对齐）。
7. Day 10：完成 P1-4 + 最小测试补齐一轮验收。

---

## 7. v1 统一失败语义（建议写入脚本约定）

1. `exit 1`：命令执行失败或输入参数非法。
2. `exit 2`：命中治理阻断（缺证据、缺同步、缺自审、过期豁免）。
3. `exit 3`：环境阻塞（网络/权限/基础设施不可达），必须显式标记 `env_blocked`，不得宣称通过。

---

## 8. 产物约定（审计最小集）

每次模块级开发回合至少保留以下文件：
1. `artifacts/harness/<run-id>.summary.json`
2. `artifacts/harness/<run-id>.summary.md`
3. `artifacts/harness/<run-id>.journey.json`（当 `runtime-verify != skip`）
4. `artifacts/harness/<run-id>.journey.md`（当 `runtime-verify != skip`）
5. `artifacts/harness/<run-id>.self-review.md`（当 `self-review != skip`）
6. `artifacts/harness/<run-id>.contract-sync.json`（当命中契约变更）

缺任一 required artifact：CI 直接失败。
