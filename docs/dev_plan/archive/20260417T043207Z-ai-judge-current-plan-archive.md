# 当前开发计划

关联 slot：`default`  
更新时间：2026-04-17  
当前主线：`AI_judge_service P12（real-env pass 冲刺 + 可验证信任层 PhaseB + 裁决展示深化）`  
当前状态：执行中（非阻塞模块已完成；仅剩 real-env 窗口阻塞）
归档来源：`docs/dev_plan/archive/20260417T034808Z-ai-judge-current-plan-archive.md`

---

## 1. 计划定位

1. 本计划承接 P11 完成态，目标是在不回退既有主链的前提下推进“企业方案目标态”的下一阶段。
2. 本轮继续执行硬切原则：不保留兼容层、灰度双轨、旧新并行主链。
3. 本计划按“窗口阻塞项 + 非阻塞增量项”并行组织，确保在无真实环境时仍可持续推进。
4. 本计划要求后续每次“下一阶段开发计划”先通过架构方案第13章一致性检查（角色/数据/门禁/边界/跨层/收口）。

---

## 2. 当前代码状态快照（P11 基线）

以下能力已在代码侧落地，可作为 P12 起点（保留，不回退）：

1. `trace/replay/audit/receipt` 主链可用，`failed callback` 追踪闭环可用。
2. 法庭式 8 Agent 主链在 Judge runtime 已显式建模，并在 `judgeTrace` 暴露关键链路节点。
3. 六对象主链已成型：`case_dossier / claim_graph / evidence_bundle / verdict_ledger / fairness_report / opinion_pack`。
4. `Fairness Sentinel -> Chief Arbiter` 不可绕过门禁已落地，`review_required => winner=draw` 合同已校验。
5. `debateSummary/sideAnalysis/verdictReason` 已改为 `verdict_ledger` 驱动生成，且具备合同一致性校验。
6. `registry` 三元（policy/prompt/tool）与 dependency/fairness gate 产品化路由已具备。
7. `trust phaseA/phaseB` 关键接口已具备（commitment/attestation/challenge/kernel/audit-anchor），但外部可验证读层仍可深化。
8. `NPC Coach / Room QA` 入口壳已存在且保持 `advisory_only`，未侵入官方裁决主链。
9. real-env 收口链脚本已具备，当前状态为 `local_reference_ready`，尚未达到 `pass`。

---

## 3. 未完成项（本阶段真实缺口）

1. **real-env 最终收口未完成**：`AI_JUDGE_REAL_ENV_WINDOW_CLOSURE_STATUS=local_reference_ready`，`REAL_PASS_READY=false`。
2. **真实环境证据仍缺**：当前仅有本机参考证据，缺少目标部署环境的稳定性与收口证据包。

---

## 4. P12 总目标（与企业方案/架构方案强一致）

1. 在真实环境窗口到来时，一次性把收口状态从 `local_reference_ready` 推进到 `pass`。
2. 在不暴露敏感内部细节前提下，补齐“可验证信任层 PhaseB”的统一核验出口。
3. 升级用户可见裁决展示结构，使“阶段争点与关键证据”可稳定消费、可复盘。
4. 保持架构边界不塌缩：8 Agent 角色、门禁链、advisory-only、跨层同步、收口口径不混淆。

---

## 5. P12 模块执行矩阵

### 已完成/未完成矩阵

| 模块 | 优先级 | 状态 | 本轮目标 | DoD（完成定义） | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| `ai-judge-p12-real-env-pass-window-execute` | P0（环境阻塞） | 阻塞（待窗口） | 在真实环境窗口执行一键冲刺链路并达成 `pass` | `ai_judge_real_env_window_closure.env` 中 `AI_JUDGE_REAL_ENV_WINDOW_CLOSURE_STATUS=pass` 且 `REAL_PASS_READY=true` | `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p12-public-verification-endpoint-v1` | P1 | 已完成（2026-04-16） | 在现有 trust phaseA/phaseB 基础上提供统一“公开核验载荷”读接口（去敏） | 可返回 `caseCommitment/verdictAttestation/challengeReview/kernelVersion/auditAnchor` 的可核验摘要，且不泄露 transcript 与内部审计细节 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k \"create_app_should_expose_v3_routes_only or trust_routes_should_return_phasea_registry_bundle\"` |
| `ai-judge-p12-opinion-pack-timeline-v2` | P1 | 已完成（2026-04-16） | 把 `phaseRollupSummary + claimGraphSummary + decisiveEvidenceRefs` 收敛为稳定展示结构（阶段争点时间线/证据解释卡片） | `opinionPack.userReport` 新增稳定可消费字段，且与 `winner/debateSummary/sideAnalysis/verdictReason` 合同一致 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_judge_mainline.py tests/test_phase_final_contract_models.py tests/test_app_factory.py -k \"final_dispatch_should_mark_workflow_review_required_when_gate_triggers or review_routes_should_list_detail_and_decide_review_job\"` |
| `ai-judge-p12-evidence-ledger-reliability-guard-v2` | P1 | 已完成（2026-04-16） | 提升 `evidence_ledger` 可靠性标签与冲突原因的可解释口径，并与 fairness gate 联动 | `evidenceLedger.stats` 与 `conflictSources/reliabilityLabel` 在 final 合同和 fairness 读链路可一致复盘 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_evidence_ledger.py tests/test_judge_mainline.py tests/test_phase_final_contract_models.py` |
| `ai-judge-p12-enterprise-mapping-refresh` | P2 | 已完成（2026-04-16） | 将章节完成度映射文档同步到 P11/P12 基线，移除 P10 旧口径 | 映射文档中的章节结论、证据链接、下一步优先级与当前代码状态一致 | 文档 diff + `bash scripts/quality/harness_docs_lint.sh` + `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p12-stage-closure-ready` | P2 | 已完成（2026-04-16） | 在本阶段尾部输出“可收口草案”：主体完成/环境阻塞/下轮入口清晰分离 | 可产出一版可执行的 stage closure 草案；不把环境阻塞误报为功能未完成 | `bash scripts/harness/ai_judge_stage_closure_draft.sh --root /Users/panyihang/Documents/EchoIsle` |

---

## 6. 执行顺序与依赖

### 下一开发模块建议

1. 当前仅剩 `real-env-pass-window-execute` 环境窗口阻塞项：窗口到位后执行一键冲刺并更新 `pass` 证据。
2. 在窗口前保持本机基线与收口脚本可运行，避免窗口到来时出现脚本/配置漂移。

---

## 7. 本阶段明确不做

1. 不开放 `NPC Coach / Room QA` 到用户侧正式流程（继续 `advisory_only`）。
2. 不引入长期兼容层、alias 并存、旧新 payload 双写。
3. 不在本阶段启动服务拆分（Judge/NPC/QA 微服务化暂不推进）。
4. 不把区块链/ZK/ZKML 上链能力作为当前主链依赖（仅保留可验证承诺接口扩展位）。
5. 不在无真实环境证据条件下宣称 `real-env pass`。

---

## 8. 测试与验收基线

1. 服务回归：`cd ai_judge_service && ../scripts/py -m pytest -q`
2. 质量检查：`cd ai_judge_service && ../scripts/py -m ruff check app tests`
3. 核心主链回归：
   - `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_judge_mainline.py tests/test_phase_final_contract_models.py tests/test_app_factory.py`
4. trust/read-model 回归：
   - `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_trust_phasea.py tests/test_trust_attestation.py tests/test_app_factory.py -k \"trust\"`
5. 收口脚本基线（本机）：
   - `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`
   - `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`
6. 文档与计划结构：
   - `bash scripts/quality/harness_docs_lint.sh`
   - `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle`

---

## 9. 风险与对策

1. 风险：公开核验接口误暴露内部细节。  
   对策：只输出承诺/哈希/状态，不输出 transcript 原文、内部 prompt、敏感审计细节。
2. 风险：展示字段扩展导致跨层消费不一致。  
   对策：同轮同步 `chat_server` 消费契约与测试，不保留长期双轨字段。
3. 风险：证据可靠性门禁过严导致误触发 `review_required`。  
   对策：先引入可观测阈值与审计归因，再按 benchmark 数据校准。
4. 风险：真实环境窗口迟迟不可用。  
   对策：保持 `local_reference_ready` 口径与 blocker 导出，窗口到来时按一键冲刺清单执行。
5. 风险：文档口径滞后于代码现实。  
   对策：本阶段把章节映射作为显式模块持续同步。

---

## 10. 模块完成同步历史

### 模块完成同步历史

1. 2026-04-17：上一轮 P11 计划已归档至 `docs/dev_plan/archive/20260417T034808Z-ai-judge-current-plan-archive.md`，作为本计划基线输入。
2. 2026-04-17：生成 P12 下一阶段计划，主线切换为“real-env pass 冲刺 + 可验证信任层 PhaseB + 裁决展示深化”。
3. 2026-04-16：完成 `ai-judge-p12-public-verification-endpoint-v1`，新增 `/internal/judge/cases/{case_id}/trust/public-verify` 去敏聚合核验接口，并补充路由与行为测试覆盖。
4. 2026-04-16：完成 `ai-judge-p12-opinion-pack-timeline-v2`，在 `opinionPack.userReport` 增加 `phaseDebateTimeline/evidenceInsightCards` 稳定展示结构，并补充合同校验与测试。
5. 2026-04-16：完成 `ai-judge-p12-evidence-ledger-reliability-guard-v2`，补充可靠性/冲突原因统计口径并新增 `evidence_reliability_too_low` fairness 门禁测试覆盖。
6. 2026-04-16：完成 `ai-judge-p12-enterprise-mapping-refresh`，将章节完成度映射文档从 P10 口径刷新为 P11/P12 口径并通过文档门禁。
7. 2026-04-16：完成 `ai-judge-p12-stage-closure-ready`，产出阶段收口草案摘要（completed_candidates=3，todo_candidates=0）。

---

## 11. 本轮启动检查清单

1. 对照架构方案第13章，先回答 6 项一致性问题（角色/数据/门禁/边界/跨层/收口）。
2. 明确本轮变更触达的 Agent 角色与对象边界，禁止“无名重构”。
3. 若改动 API/DTO/错误码，必须同轮检查 `chat_server` 与调用方同步状态。
4. 涉及 real-env 结论时，必须区分 `local_reference_ready` 与 `pass`，禁止口径混写。
5. 涉及用户展示字段扩展时，先保证原主合同字段稳定可回放。

---

## 12. 架构方案第13章一致性校验（计划生成前置）

1. **角色一致性**：P12 仅在既有 8 Agent 主链上做能力深化，不新增绕过角色，也不把 `Fairness Sentinel` 与 `Chief Arbiter` 合并。
2. **数据一致性**：继续围绕六对象（`case_dossier/claim_graph/evidence_bundle/verdict_ledger/fairness_report/opinion_pack`）扩展读写，不引入平行事实源。
3. **门禁一致性**：任何展示/核验增强都不得绕过公平门禁；`review_required` 仍优先于终判公开。
4. **边界一致性**：`NPC/Room QA` 继续 `advisory_only`，不参与官方裁决写链。
5. **跨层一致性**：若新增公开核验接口或展示字段，必须同轮同步 `chat_server` / 调用方契约与测试。
6. **收口一致性**：P12 明确把 real-env 视为窗口阻塞项；窗口前只承认 `local_reference_ready`，窗口后才可宣告 `pass`。
