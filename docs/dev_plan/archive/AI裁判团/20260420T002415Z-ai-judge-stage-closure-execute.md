# 当前开发计划

关联 slot：`default`  
更新时间：2026-04-20  
当前主线：`AI_judge_service P24（Trust 读面契约冻结 + app_factory 结构拆分延续 + on-env 收口准备）`  
当前状态：执行中（已完成 `ai-judge-next-iteration-planning`、`ai-judge-p24-trust-public-verify-contract-freeze-v1`、`ai-judge-p24-trust-challenge-ops-queue-contract-freeze-v1`、`ai-judge-p24-app-factory-structure-split-v7`、`ai-judge-p24-ops-export-trust-alignment-v1`、`ai-judge-p24-local-regression-bundle-v1`、`ai-judge-p24-enterprise-consistency-refresh-v1`；`ai-judge-p24-real-env-pass-window-execute-on-env` 当前 `env_blocked`，下一步 `ai-judge-p24-stage-closure-execute`）

---

## 1. 计划定位

1. 本计划承接阶段收口归档：`/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260420T000027Z-ai-judge-stage-closure-execute.md`。
2. 当前前提不变：仅本地开发环境可用，真实环境窗口仍不可用；所有 `pass` 级结论继续严格标注为 `on-env`。
3. P24 聚焦“企业方案 + 架构方案”的本地可推进主链：
   - 冻结 Trust 关键读面契约（`public-verify`、`trust challenge ops queue`）。
   - 继续拆分 `app_factory.py` 的 Trust 聚合热点，降低维护复杂度。
   - 让导出链路与 Trust 读面冻结口径一致，保持 Ops 视图稳定。
4. 继续执行预发布硬切原则：不保留长期兼容层、双写、灰度并行或旧字段 alias。

---

## 2. 当前代码状态快照（P24 起点）

截至 2026-04-20，`ai_judge_service` 当前状态：

1. P23 已完成本地闭环：`case fairness/panel runtime profile` 契约冻结、`app_factory split v6`、`ops_export v2`、`local regression bundle v5`。
2. Trust 主链接口已具备：`/trust/public-verify`、`/trust/challenges/ops-queue`、`/trust/kernel-version`、`/trust/audit-anchor`。
3. 当前可见缺口：
   - Trust 读面仍缺“独立 contract module + 明确 500 合同失败语义”。
   - `app_factory.py` 在 Trust 查询与聚合链路仍然偏重。
   - 真实环境 `pass window` 仍是唯一环境阻塞项（最新探测 `env_blocked`）。

---

## 3. P24 总目标

1. 对齐企业方案第 6/7/11/12/13/15 章与架构方案第 5/6/10/13 章。
2. 将 Trust 核心读面从“可用”升级为“契约冻结可审计”。
3. 持续降低 `app_factory` 热点复杂度，增强后续迭代稳定性。
4. 在无真实环境条件下完成本地证据闭环，不误报 `pass`。

---

## 4. P24 模块执行矩阵

### 已完成/未完成矩阵

| 模块 | 优先级 | 状态 | 本轮目标 | DoD（完成定义） | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| `ai-judge-next-iteration-planning` | P0 | 已完成（2026-04-20） | 阶段收口后生成 P24 完整计划 | 当前计划切换到 P24，明确模块边界、阻塞项与执行顺序 | `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p24-trust-public-verify-contract-freeze-v1` | P0 | 已完成（2026-04-20） | 冻结 `trust/public-verify` 读面契约 | 新增 `trust_public_verify_contract` 校验模块并接入 `/internal/judge/cases/{case_id}/trust/public-verify` 返回链路；缺失关键字段返回 500 合同失败语义；补独立 contract 单测 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "trust_public_verify"` + `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_trust_public_verify_contract.py` |
| `ai-judge-p24-trust-challenge-ops-queue-contract-freeze-v1` | P1 | 已完成（2026-04-20） | 冻结 `trust/challenges/ops-queue` 读面契约 | 新增 `trust_challenge_queue_contract` 校验模块并接入 `/internal/judge/trust/challenges/ops-queue` 返回链路；缺失关键字段返回 500 合同失败语义；补独立 contract 单测 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "trust_challenges_ops_queue"` + `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_trust_challenge_queue_contract.py` |
| `ai-judge-p24-app-factory-structure-split-v7` | P1 | 已完成（2026-04-20） | 继续下沉 Trust 热点聚合逻辑 | 将 Trust 公共校验/聚合逻辑下沉到 `app/applications` 子模块，`app_factory` 保留编排与路由层 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "trust_public_verify or trust_challenges_ops_queue or trust_kernel_version or trust_audit_anchor"` |
| `ai-judge-p24-ops-export-trust-alignment-v1` | P1 | 已完成（2026-04-20） | 导出链路对齐 Trust 冻结口径 | `ops_read_model_export` 增补 Trust 关键指标输出（来自 read-model pack 的 trust_overview / queue 摘要），并补脚本测试 | `bash scripts/harness/tests/test_ai_judge_ops_read_model_export.sh` |
| `ai-judge-p24-local-regression-bundle-v1` | P2 | 已完成（2026-04-20） | 固化 P24 本地回归包 | 完成 `ruff + pytest + runtime_ops_pack(local_reference)` 并产出最新工件 | `cd ai_judge_service && ../scripts/py -m ruff check app tests` + `cd ai_judge_service && ../scripts/py -m pytest -q` + `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference` |
| `ai-judge-p24-enterprise-consistency-refresh-v1` | P2 | 已完成（2026-04-20） | 文档一致性刷新 | 更新章节完成度映射与当前计划，确保“企业方案/架构方案/代码口径”一致 | `bash scripts/quality/harness_docs_lint.sh` + `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p24-real-env-pass-window-execute-on-env` | P0（环境阻塞） | 阻塞（待真实环境窗口） | 真实环境 pass 冲刺 | `AI_JUDGE_REAL_ENV_WINDOW_CLOSURE_STATUS=pass` 且 `REAL_PASS_READY=true` | `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p24-stage-closure-execute` | P2 | 待执行 | 阶段收口执行 | 归档活动计划，`completed/todo` 同步，计划重置到下一轮入口 | `bash scripts/harness/ai_judge_stage_closure_execute.sh --root /Users/panyihang/Documents/EchoIsle` |

### 下一开发模块建议

1. `ai-judge-p24-stage-closure-execute`
2. 真实环境窗口可用后再执行 `ai-judge-p24-real-env-pass-window-execute-on-env`

---

## 5. 延后事项（不阻塞 P24）

1. `real-env pass` 相关能力（严格 `on-env`）。
2. `NPC Coach / Room QA` 正式业务策略与主链接入（等待你冻结 PRD 后再推进）。
3. 协议化扩展（链上锚定 / ZK / ZKML）继续保持后置，不进入当前主链。

---

## 6. 执行顺序与依赖

1. 先做 `trust-public-verify-contract-freeze-v1`，稳住 Trust 对外验证读面。
2. 再做 `trust-challenge-ops-queue-contract-freeze-v1`，补齐运维队列口径冻结。
3. 推进 `app-factory-structure-split-v7`，下沉 Trust 查询聚合热点。
4. 同步 `ops-export-trust-alignment-v1`，避免导出链路口径漂移。
5. 执行 `local-regression-bundle-v1` 与 `enterprise-consistency-refresh-v1`。
6. 真实环境窗口就绪后单独推进 `on-env pass`，否则执行阶段收口。

---

## 7. 本阶段明确不做

1. 不推进 `NPC Coach / Room QA` 正式功能开发。
2. 不为未上线能力保留长期兼容层（alias/双写/灰度并行）。
3. 不将 `local_reference_*` 或 `env_blocked` 表述为 `pass`。

---

## 8. 测试与验收基线

1. `bash skills/python-venv-guard/scripts/assert_venv.sh --project /Users/panyihang/Documents/EchoIsle/ai_judge_service --venv /Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv`
2. `cd ai_judge_service && ../scripts/py -m ruff check app tests`
3. `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py tests/test_ops_read_model_pack.py`
4. `cd ai_judge_service && ../scripts/py -m pytest -q`
5. `bash scripts/harness/tests/test_ai_judge_ops_read_model_export.sh`
6. `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`
7. `bash scripts/quality/harness_docs_lint.sh`
8. `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle`

---

## 9. 风险与对策

1. 风险：Trust 关键读面继续隐式漂移，导致验证与运维口径不一致。  
   对策：P24-M1/M2 显式补 contract module + 500 失败语义 + 独立单测。
2. 风险：`app_factory` 热点继续增大，后续改动回归成本上升。  
   对策：P24-M3 按 Trust 子域继续下沉聚合逻辑到 `app/applications`。
3. 风险：导出链路与 read-model 冻结字段失配。  
   对策：P24-M4 在脚本层补 Trust 指标键检测，并纳入脚本门禁。
4. 风险：无真实环境导致状态误读。  
   对策：严格区分 `env_blocked/local_reference` 与 `pass`，保留 `on-env` 单独收口。

---

## 10. 模块完成同步历史

### 模块完成同步历史

1. 2026-04-20：完成 `ai-judge-stage-closure-execute`，归档上一阶段到 `/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260420T000027Z-ai-judge-stage-closure-execute.md`。
2. 2026-04-20：完成 `ai-judge-next-iteration-planning`，当前计划切换到 `P24`。
3. 2026-04-20：执行 `real-env window` 现状探测，当前结论仍为 `env_blocked`（工件：`/Users/panyihang/Documents/EchoIsle/artifacts/harness/20260419T235944Z-ai-judge-real-env-window-closure.summary.json`）。
4. 2026-04-20：完成 `ai-judge-p24-trust-public-verify-contract-freeze-v1`，新增 `trust_public_verify_contract` 模块并接入 `/internal/judge/cases/{case_id}/trust/public-verify` 500 契约失败语义与专项测试。
5. 2026-04-20：完成 `ai-judge-p24-trust-challenge-ops-queue-contract-freeze-v1`，新增 `trust_challenge_queue_contract` 模块并接入 `/internal/judge/trust/challenges/ops-queue` 500 契约失败语义与专项测试。
6. 2026-04-20：完成 `ai-judge-p24-app-factory-structure-split-v7`，新增 `trust_ops_views` 模块并下沉 `public_verify` 与 `trust ops queue` 视图组装逻辑，`app_factory` 保留编排与 contract 门禁。
7. 2026-04-20：完成 `ai-judge-p24-ops-export-trust-alignment-v1`，`ops_read_model_export` 新增 `trust/challenges/ops-queue` 导出链路、关键字段校验与指标输出，并通过脚本回归。
8. 2026-04-20：完成 `ai-judge-p24-local-regression-bundle-v1`，`ruff check app tests`、`pytest -q` 与 `runtime_ops_pack(--allow-local-reference)` 全部通过。
9. 2026-04-20：完成 `ai-judge-p24-enterprise-consistency-refresh-v1`，刷新企业方案章节完成度映射并通过 `harness_docs_lint + plan_consistency_gate` 收口一致性。
10. 2026-04-20：执行 `ai-judge-p24-real-env-pass-window-execute-on-env` 探测，结论仍为 `env_blocked`（工件：`/Users/panyihang/Documents/EchoIsle/artifacts/harness/20260420T002339Z-ai-judge-real-env-window-closure.summary.json`）。

---

## 11. 本轮启动检查清单

1. 开发前运行 `pre-module-prd-goal-guard`（按模块执行）。
2. 涉及 API/DTO/错误码变更时，同轮同步调用方、测试与文档。
3. 与真实环境有关结论必须标注 `on-env`，本地阶段不得宣称 `pass`。
4. 每完成一个模块都回写当前计划矩阵与同步历史。

---

## 12. 架构方案第13章一致性校验（计划生成前置）

1. **角色一致性**：继续沿用法庭式 8 Agent 边界，不新增绕过 Sentinel/Arbiter 的捷径路径。
2. **数据一致性**：六对象主链仍是唯一裁决事实源，不引入平行 winner 写链。
3. **门禁一致性**：fairness/review/registry/trust gate 不弱化；新增能力需显式标注主链或 advisory-only。
4. **边界一致性**：`NPC/Room QA` 保持 `advisory_only`，不写官方裁决链。
5. **跨层一致性**：契约变更同轮同步调用方、测试与文档，不保留长期双轨 alias。
6. **收口一致性**：真实环境结论与本地参考结论分层表达，未获窗口前不宣称 `pass`。
