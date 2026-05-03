# 当前开发计划

关联 slot：`default`  
更新时间：2026-04-20  
当前主线：`AI_judge_service P26（Trust 读面契约全冻结 + 读路由结构下沉 + on-env 收口准备）`  
当前状态：执行中（已完成 `ai-judge-next-iteration-planning`、`ai-judge-p26-trust-commitment-contract-freeze-v1`、`ai-judge-p26-trust-verdict-attestation-contract-freeze-v1`、`ai-judge-p26-trust-challenge-review-contract-freeze-v1`、`ai-judge-p26-trust-read-route-structure-split-v1`、`ai-judge-p26-ops-export-trust-phasea-snapshot-alignment-v1`、`ai-judge-p26-local-regression-bundle-v1`、`ai-judge-p26-enterprise-consistency-refresh-v1`，下一步 `ai-judge-p26-real-env-pass-window-execute-on-env`）

---

## 1. 计划定位

1. 本计划承接阶段收口归档：`/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260420T011519Z-ai-judge-stage-closure-execute.md`。
2. 当前前提不变：仅本地开发环境可用，真实环境窗口仍不可用；所有 `pass` 级结论继续严格标注为 `on-env`。
3. P26 聚焦企业方案第 15 章（可验证信任层）和架构方案第 5/6/13 章在 Trust 读面上的剩余硬口径缺口：
   - 冻结 `trust/commitment`、`trust/verdict-attestation`、`trust/challenges` 三条读面契约。
   - 继续下沉 Trust 读路由聚合逻辑，降低 `app_factory.py` 热点复杂度。
   - 将 ops 导出中已有 `public-verify` 快照能力与 Trust PhaseA 关键指标进一步对齐。
4. 继续执行预发布硬切原则：不保留长期兼容层、双写、灰度并行或旧字段 alias。

---

## 2. 当前代码状态快照（P26 起点）

截至 2026-04-20，`ai_judge_service` 当前状态：

1. P25 本地主链已完成：
   - `trust/kernel-version`、`trust/audit-anchor` 契约冻结并接入 500 合同失败语义。
   - `Trust PhaseA` 组装已下沉到 `app/applications/trust_phasea_bundle.py`。
   - `ops_read_model_export` 已支持显式 `case_id` 触发 `trust/public-verify` 快照导出与关键字段校验。
   - 本地回归 `ruff + pytest + runtime_ops_pack(local_reference_ready)` 已通过。
2. Trust 主链接口当前具备：`/trust/commitment`、`/trust/verdict-attestation`、`/trust/challenges`、`/trust/challenges/ops-queue`、`/trust/kernel-version`、`/trust/audit-anchor`、`/trust/public-verify`。
3. 当前可见缺口：
   - `trust/commitment`、`trust/verdict-attestation`、`trust/challenges` 三条读面契约已冻结，下一步是读路由结构下沉与导出指标对齐。
   - Trust 读路由中 receipt/context 解析逻辑仍有聚合热点留在 `app_factory.py`。
   - 导出链路尚未显式输出 Trust PhaseA 子对象指标（目前聚合在 `public-verify` 快照下）。
   - `real-env pass window` 仍是唯一环境阻塞项（最新探测 `env_blocked`）。

---

## 3. P26 总目标

1. 对齐企业方案第 6/7/11/12/13/15 章与架构方案第 5/6/10/13 章。
2. 将 Trust 核心读面从“部分冻结”推进到“PhaseA 三读面 + kernel/audit/public verify 全冻结”。
3. 持续降低 `app_factory` 聚合复杂度，确保后续扩展（含 NPC/Room QA）不反向污染裁判主链。
4. 在无真实环境条件下完成可复现本地收口，不误报 `pass`。

---

## 4. P26 模块执行矩阵

### 已完成/未完成矩阵

| 模块 | 优先级 | 状态 | 本轮目标 | DoD（完成定义） | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| `ai-judge-next-iteration-planning` | P0 | 已完成（2026-04-20） | 阶段收口后生成 P26 完整计划 | 当前计划切换到 P26，明确模块边界、阻塞项与执行顺序 | `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p26-trust-commitment-contract-freeze-v1` | P0 | 已完成（2026-04-20） | 冻结 `trust/commitment` 读面契约 | 新增 `trust_commitment_contract` 校验模块并接入 `/internal/judge/cases/{case_id}/trust/commitment` 返回链路；缺失关键字段返回 500 合同失败语义；补独立 contract 单测 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "trust_commitment"` + `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_trust_commitment_contract.py` |
| `ai-judge-p26-trust-verdict-attestation-contract-freeze-v1` | P0 | 已完成（2026-04-20） | 冻结 `trust/verdict-attestation` 读面契约 | 新增 `trust_verdict_attestation_contract` 校验模块并接入 `/internal/judge/cases/{case_id}/trust/verdict-attestation` 返回链路；缺失关键字段返回 500 合同失败语义；补独立 contract 单测 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "trust_verdict_attestation"` + `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_trust_verdict_attestation_contract.py` |
| `ai-judge-p26-trust-challenge-review-contract-freeze-v1` | P1 | 已完成（2026-04-20） | 冻结 `trust/challenges` 读面契约 | 新增 `trust_challenge_review_contract` 校验模块并接入 `/internal/judge/cases/{case_id}/trust/challenges` 返回链路；缺失关键字段返回 500 合同失败语义；补独立 contract 单测 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "trust_challenge_review"` + `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_trust_challenge_review_contract.py` |
| `ai-judge-p26-trust-read-route-structure-split-v1` | P1 | 已完成（2026-04-20） | 下沉 Trust 读路由热点逻辑 | 将 Trust 读面共用的 receipt/context 解析与 payload 组装逻辑下沉到 `app/applications` 子模块；`app_factory` 保留编排与路由层 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "trust_commitment or trust_verdict_attestation or trust_challenge_review or trust_public_verify"` |
| `ai-judge-p26-ops-export-trust-phasea-snapshot-alignment-v1` | P1 | 已完成（2026-04-20） | 导出链路补齐 Trust PhaseA 子指标 | 在 `ops_read_model_export` 的 `public-verify` 快照路径上补齐 commitment/verdict/challenge 关键指标导出与缺失检测，脚本测试覆盖通过 | `bash scripts/harness/tests/test_ai_judge_ops_read_model_export.sh` |
| `ai-judge-p26-local-regression-bundle-v1` | P2 | 已完成（2026-04-20） | 固化 P26 本地回归包 | 完成 `ruff + pytest + runtime_ops_pack(local_reference)` 并产出最新工件 | `cd ai_judge_service && ../scripts/py -m ruff check app tests` + `cd ai_judge_service && ../scripts/py -m pytest -q` + `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference` |
| `ai-judge-p26-enterprise-consistency-refresh-v1` | P2 | 已完成（2026-04-20） | 文档一致性刷新 | 更新章节完成度映射与当前计划，确保“企业方案/架构方案/代码口径”一致 | `bash scripts/quality/harness_docs_lint.sh` + `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p26-real-env-pass-window-execute-on-env` | P0（环境阻塞） | 阻塞（待真实环境窗口） | 真实环境 pass 冲刺 | `AI_JUDGE_REAL_ENV_WINDOW_CLOSURE_STATUS=pass` 且 `REAL_PASS_READY=true` | `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p26-stage-closure-execute` | P2 | 待执行 | 阶段收口执行 | 归档活动计划，`completed/todo` 同步，计划重置到下一轮入口 | `bash scripts/harness/ai_judge_stage_closure_execute.sh --root /Users/panyihang/Documents/EchoIsle` |

### 下一开发模块建议

1. `ai-judge-p26-real-env-pass-window-execute-on-env`
2. `ai-judge-p26-stage-closure-execute`
3. `ai-judge-next-iteration-planning`（下一轮）

---

## 5. 延后事项（不阻塞 P26）

1. `real-env pass` 相关能力（严格 `on-env`）。
2. `NPC Coach / Room QA` 正式业务策略与主链接入（等待你冻结 PRD 后再推进）。
3. 协议化扩展（链上锚定 / ZK / ZKML）继续保持后置，不进入当前主链。

---

## 6. 执行顺序与依赖

1. 先做 `trust-commitment-contract-freeze-v1`，稳住 Trust commitment 读面。
2. 再做 `trust-verdict-attestation-contract-freeze-v1`，补齐 verdict attestation 读面冻结。
3. 然后做 `trust-challenge-review-contract-freeze-v1`，完成 challenge review 读面冻结。
4. 推进 `trust-read-route-structure-split-v1`，继续下沉 `app_factory` Trust 热点。
5. 同步 `ops-export-trust-phasea-snapshot-alignment-v1`，补齐导出链路 Trust PhaseA 关键指标。
6. 执行 `local-regression-bundle-v1` 与 `enterprise-consistency-refresh-v1`。
7. 真实环境窗口就绪后单独推进 `on-env pass`，否则执行阶段收口。

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

1. 风险：Trust 深水区剩余读面持续隐式漂移，导致验证与运维口径不一致。  
   对策：P26-M1/M2/M3 显式补 contract module + 500 失败语义 + 独立单测。
2. 风险：`app_factory` 热点继续增大，后续改动回归成本上升。  
   对策：P26-M4 按 Trust 读路由子域继续下沉组装逻辑到 `app/applications`。
3. 风险：导出链路与 Trust 读面冻结字段失配。  
   对策：P26-M5 在脚本层补 Trust PhaseA 快照子指标导出与关键字段检测。
4. 风险：无真实环境导致状态误读。  
   对策：严格区分 `env_blocked/local_reference` 与 `pass`，保留 `on-env` 单独收口。

---

## 10. 模块完成同步历史

### 模块完成同步历史

1. 2026-04-20：完成 `ai-judge-stage-closure-execute`，归档上一阶段到 `/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260420T011519Z-ai-judge-stage-closure-execute.md`。
2. 2026-04-20：完成 `ai-judge-next-iteration-planning`，当前计划切换到 `P26`。
3. 2026-04-20：完成 `ai-judge-p26-trust-commitment-contract-freeze-v1`，新增 `trust_commitment_contract` 模块并接入 `/internal/judge/cases/{case_id}/trust/commitment` 500 契约失败语义与专项测试。
4. 2026-04-20：完成 `ai-judge-p26-trust-verdict-attestation-contract-freeze-v1`，新增 `trust_verdict_attestation_contract` 模块并接入 `/internal/judge/cases/{case_id}/trust/verdict-attestation` 500 契约失败语义与专项测试。
5. 2026-04-20：完成 `ai-judge-p26-trust-challenge-review-contract-freeze-v1`，新增 `trust_challenge_review_contract` 模块并接入 `/internal/judge/cases/{case_id}/trust/challenges` 500 契约失败语义与专项测试。
6. 2026-04-20：完成 `ai-judge-p26-trust-read-route-structure-split-v1`，新增 `trust_read_routes` 模块并下沉 Trust 读路由共用的 dispatch 选择、report context 解析与 payload 组装逻辑。
7. 2026-04-20：完成 `ai-judge-p26-ops-export-trust-phasea-snapshot-alignment-v1`，补齐 `ops_read_model_export` 中 Trust public-verify 的 commitment/verdict/challenge 子指标导出与缺失检测，并补脚本回归场景。
8. 2026-04-20：完成 `ai-judge-p26-local-regression-bundle-v1`，通过 `ruff + pytest -q + runtime_ops_pack(local_reference_ready)` 全量本地回归。
9. 2026-04-20：完成 `ai-judge-p26-enterprise-consistency-refresh-v1`，更新章节完成度映射并通过 `harness_docs_lint + ai_judge_plan_consistency_gate`。
10. 2026-04-20：执行 `ai-judge-p26-real-env-pass-window-execute-on-env` 探测，当前输出 `env_blocked`，阻塞码：`real_env_marker_not_ready,p5_status_not_pass,runtime_ops_status_not_pass,fairness_status_not_pass,runtime_sla_status_not_pass,real_env_closure_status_not_pass`。

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
