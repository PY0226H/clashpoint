# 当前开发计划

关联 slot：`default`  
更新时间：2026-04-20  
当前主线：`AI_judge_service P29（Judge Command 主链下沉 + 读面契约硬化 + on-env 收口准备）`  
当前状态：执行中（已完成 `ai-judge-next-iteration-planning`、`ai-judge-p29-judge-command-runtime-split-v1`、`ai-judge-p29-trace-replay-route-split-v1`、`ai-judge-p29-fairness-read-model-hardcut-v1`、`ai-judge-p29-judge-workflow-contract-assert-v1`、`ai-judge-p29-local-regression-bundle-v1`、`ai-judge-p29-enterprise-consistency-refresh-v1`；下一步按环境窗口选择 `ai-judge-p29-real-env-pass-window-execute-on-env` 或 `ai-judge-p29-stage-closure-execute`）

---

## 1. 计划定位

1. 本计划承接阶段归档：`/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260420T052218Z-ai-judge-stage-closure-execute.md`。
2. P28 已完成本地闭环（Judge App 显式化、fairness 合同固定化、全量回归与文档一致性）。
3. P29 目标从“能力补齐”转为“主链结构化降复杂度 + 读面硬契约收敛”。
4. 当前前提不变：仅本地环境可用，真实环境窗口不可用；`pass` 结论继续严格区分 `on-env`。
5. 继续执行预发布硬切原则：不保留长期兼容层、灰度并行、双写或 alias。

---

## 2. 当前代码状态快照（P29 起点）

截至 2026-04-20，`ai_judge_service` 当前状态：

1. 已完成 P28 本地闭环：
   - `judge_app_domain` / `judge_workflow_roles` / `judge_trace_summary` 已落地。
   - `fairnessSummary.gateDecision/reviewReasons` 与 `verdictLedger.arbitration.gateDecision` 合同已固定。
   - 全量回归已通过：`ruff + pytest -q + runtime_ops_pack(local_reference_ready)`。
2. 主链能力已具备：dispatch / trace / replay / fairness / review / trust / courtroom / ops read model。
3. 当前核心缺口：
   - phase/final callback 主链、trace/replay 路由、fairness read-model 与 Judge workflow 结构化合同断言已完成。
   - 剩余工作集中在 P29 收口：本地全量回归包、企业方案一致性文档刷新与阶段归档。
   - `real-env pass window` 仍是唯一环境阻塞项（`env_blocked`）。

---

## 3. P29 总目标

1. 继续将 Judge 主链从“可用”推进到“可维护、可扩展、可审计”的企业化结构。
2. 把 phase/final 命令编排从 `app_factory` 下沉到 `app/applications`，`app_factory` 只保留 route 装配与 HTTP 错误映射。
3. 统一 trace/replay/read-model 的 fairness gate 消费语义，避免跨路由字段漂移。
4. 在本地完成完整回归与文档一致性收口，不误报真实环境 `pass`。

---

## 4. P29 模块执行矩阵

### 已完成/未完成矩阵

| 模块 | 优先级 | 状态 | 本轮目标 | DoD（完成定义） | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| `ai-judge-next-iteration-planning` | P0 | 已完成（2026-04-20） | 阶段收口后生成 P29 完整计划 | 当前计划切换到 P29，明确模块边界、阻塞项与执行顺序 | `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p29-judge-command-runtime-split-v1` | P0 | 已完成（2026-04-20） | 下沉 phase/final 命令主链 | 新增 `judge_dispatch_runtime.py` 承载 dispatch accepted payload / workflow payload / callback failover 编排，phase/final route 切换到应用层 runtime helper | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "phase or final or callback"` + `cd ai_judge_service && ../scripts/py -m ruff check app` |
| `ai-judge-p29-trace-replay-route-split-v1` | P1 | 已完成（2026-04-20） | 下沉 trace/replay 读路由组装 | 新增 `judge_trace_replay_routes.py` 承载 dispatch type 归一化、receipt 选择、trace/replay route payload 组装；`app_factory` trace/replay 端点切换至应用层 helper，返回契约保持不变 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_judge_trace_replay_routes.py tests/test_app_factory.py -k "replay"` + `cd ai_judge_service && ../scripts/py -m ruff check app/app_factory.py app/applications` |
| `ai-judge-p29-fairness-read-model-hardcut-v1` | P1 | 已完成（2026-04-20） | 统一 fairness gate 跨读面口径 | fairness/courtroom/read-model 与相关合同硬切到 `pass_through/blocked_to_draw`，旧值仅通过内部 alias 吸收不再作为对外主语义；dashboard/case contract 与测试同步更新 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_fairness_case_contract.py tests/test_fairness_dashboard_contract.py tests/test_app_factory.py -k "fairness or courtroom"` + `cd ai_judge_service && ../scripts/py -m ruff check app/app_factory.py app/applications` |
| `ai-judge-p29-judge-workflow-contract-assert-v1` | P1 | 已完成（2026-04-20） | 强化 Judge workflow 合同断言 | `judge_trace_summary` 新增合同校验，phase/final trace summary 缺失 `judgeWorkflow/roleNodes` 时直接失败；`replay_audit_ops` 保留并校验 `reportSummary.judgeWorkflow/roleNodes`；新增路由级回归用例覆盖 trace+replay/report 契约 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_judge_trace_summary.py tests/test_replay_audit_ops.py tests/test_app_factory.py -k \"trace_and_replay_report_should_keep_judge_workflow_summary_contract or replay\"` + `cd ai_judge_service && ../scripts/py -m ruff check app/applications` |
| `ai-judge-p29-local-regression-bundle-v1` | P2 | 已完成（2026-04-20） | 固化 P29 本地回归包 | 完成 `ruff + pytest -q + runtime_ops_pack(local_reference_ready)` 并生成新工件 `20260420T062335Z-ai-judge-runtime-ops-pack.summary.*` | `cd ai_judge_service && ../scripts/py -m ruff check app tests` + `cd ai_judge_service && ../scripts/py -m pytest -q` + `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference` |
| `ai-judge-p29-enterprise-consistency-refresh-v1` | P2 | 已完成（2026-04-20） | 文档一致性刷新 | 已更新章节完成度映射与当前计划，并通过 docs lint / plan consistency gate | `bash scripts/quality/harness_docs_lint.sh` + `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p29-real-env-pass-window-execute-on-env` | P0（环境阻塞） | 阻塞（待真实环境窗口） | 真实环境 pass 冲刺 | `AI_JUDGE_REAL_ENV_WINDOW_CLOSURE_STATUS=pass` 且 `REAL_PASS_READY=true` | `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p29-stage-closure-execute` | P2 | 待执行 | 阶段收口执行 | 归档活动计划，`completed/todo` 同步，计划重置到下一轮入口 | `bash scripts/harness/ai_judge_stage_closure_execute.sh --root /Users/panyihang/Documents/EchoIsle` |

### 下一开发模块建议

1. `ai-judge-p29-stage-closure-execute`
2. `ai-judge-p29-real-env-pass-window-execute-on-env`（on-env）
3. `ai-judge-next-iteration-planning`（阶段归档后）

---

## 5. 延后事项（不阻塞 P29）

1. `real-env pass` 相关能力（严格 `on-env`）。
2. `NPC Coach / Room QA` 正式业务策略与主链接入（等待你冻结 PRD 后再推进）。
3. 协议化扩展（链上锚定 / ZK / ZKML）保持后置，不进入当前官方裁决主链。

---

## 6. 执行顺序与依赖

1. 先做 `judge-command-runtime-split-v1`，先解决 `app_factory` 命令热点。
2. 再做 `trace-replay-route-split-v1`，统一读面组装边界。
3. 然后做 `fairness-read-model-hardcut-v1`，锁死跨路由公平门禁语义。
4. 再做 `judge-workflow-contract-assert-v1`，补齐结构化合同断言。
5. 执行 `local-regression-bundle-v1` 与 `enterprise-consistency-refresh-v1`。
6. 真实环境窗口就绪后推进 `on-env pass`，否则执行阶段收口。

---

## 7. 本阶段明确不做

1. 不推进 `NPC Coach / Room QA` 正式功能开发。
2. 不为未上线能力保留长期兼容层（alias/双写/灰度并行）。
3. 不把 `local_reference_*` 或 `env_blocked` 结论表述为 `pass`。

---

## 8. 测试与验收基线

1. `bash skills/python-venv-guard/scripts/assert_venv.sh --project /Users/panyihang/Documents/EchoIsle/ai_judge_service --venv /Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv`
2. `cd ai_judge_service && ../scripts/py -m ruff check app tests`
3. `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_phase_pipeline.py tests/test_app_factory.py`
4. `cd ai_judge_service && ../scripts/py -m pytest -q`
5. `bash scripts/harness/tests/test_ai_judge_ops_read_model_export.sh`
6. `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`
7. `bash scripts/quality/harness_docs_lint.sh`
8. `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle`

---

## 9. 风险与对策

1. 风险：下沉 command/runtime 时破坏现有对外合同。  
   对策：保持外部 DTO 与错误码语义不变，先迁移内部编排函数，再回归测试。
2. 风险：trace/replay 重构导致读面字段漂移。  
   对策：对 `reportSummary/judgeWorkflow/roleNodes` 加合同断言并保持回放用例稳定。
3. 风险：fairness gate 字段硬切引发历史测试数据回归。  
   对策：测试夹具统一主语义值，禁止新用例引入遗留 gateDecision。
4. 风险：无真实环境导致“完成”与“可上线”混淆。  
   对策：继续分层表达 `local_reference_ready` 与 `pass`，`on-env` 单独收口。

---

## 10. 模块完成同步历史

### 模块完成同步历史

1. 2026-04-20：完成 `ai-judge-stage-closure-execute`（P28 阶段归档），归档文件：`/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260420T052218Z-ai-judge-stage-closure-execute.md`。
2. 2026-04-20：完成 `ai-judge-next-iteration-planning`，当前计划切换到 `P29`。
3. 2026-04-20：完成 `ai-judge-p29-judge-command-runtime-split-v1`，新增 `judge_dispatch_runtime.py` 并将 phase/final dispatch 的 callback failover 与 workflow payload 组装下沉到 `app/applications`，补充 `test_judge_dispatch_runtime.py` 覆盖。
4. 2026-04-20：完成 `ai-judge-p29-trace-replay-route-split-v1`，新增 `judge_trace_replay_routes.py`，将 trace/replay 路由中的 dispatch type 校验、receipt 选择与读面 payload 组装下沉到 `app/applications`，并补充 `test_judge_trace_replay_routes.py`。
5. 2026-04-20：完成 `ai-judge-p29-fairness-read-model-hardcut-v1`，fairness/courtroom/read-model 的 `gateDecision/gateConclusion` 对外语义统一为 `pass_through/blocked_to_draw`，同步更新 fairness contract、dashboard contract 与相关测试断言。
6. 2026-04-20：完成 `ai-judge-p29-judge-workflow-contract-assert-v1`，新增 trace summary 合同校验并将 replay report summary 同步为 `judgeWorkflow/roleNodes` 主语义，补充 `test_replay_audit_ops.py` 与 `test_app_factory.py` 覆盖。
7. 2026-04-20：完成 `ai-judge-p29-local-regression-bundle-v1`，执行 `ruff + pytest -q + runtime_ops_pack(local_reference_ready)`，新增工件 [20260420T062335Z-ai-judge-runtime-ops-pack.summary.json](/Users/panyihang/Documents/EchoIsle/artifacts/harness/20260420T062335Z-ai-judge-runtime-ops-pack.summary.json)。
8. 2026-04-20：完成 `ai-judge-p29-enterprise-consistency-refresh-v1`，更新 [AI_Judge_Service-企业级Agent方案-章节完成度映射-2026-04-13.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/AI_Judge_Service-企业级Agent方案-章节完成度映射-2026-04-13.md) 并通过 docs/plan 一致性门禁。

---

## 11. 本轮启动检查清单

1. 开发前运行 `pre-module-prd-goal-guard`（按模块执行）。
2. 涉及 API/DTO/错误码变更时，同轮同步调用方、测试与文档。
3. 与真实环境有关结论必须标注 `on-env`，本地阶段不得宣称 `pass`。
4. 每完成一个模块都回写当前计划矩阵与同步历史。

---

## 12. 架构方案第13章一致性校验（计划生成前置）

1. **角色一致性**：8 Agent 职责必须完整映射，不能被错误合并或绕过。
2. **数据一致性**：`case_dossier/claim_graph/evidence_bundle/verdict_ledger/fairness_report/opinion_pack` 保持唯一主链语义。
3. **门禁一致性**：`Fairness Sentinel` 仍在终判前，override/阻断必须可审计。
4. **边界一致性**：`NPC/Room QA` 继续保持 `advisory_only`，不写官方裁决链。
5. **跨层一致性**：契约变更同轮同步调用方、测试与文档，不保留长期双轨 alias。
6. **收口一致性**：real-env 项继续区分 `local_reference_ready` 与 `pass`，不混淆口径。
