# 当前开发计划

关联 slot：`default`  
更新时间：2026-04-19  
当前主线：`AI_judge_service P21（裁判主链结构收敛 + 契约冻结扩展 + 本地稳态回归）`  
当前状态：执行中（已完成 `ai-judge-next-iteration-planning`、`ai-judge-p21-app-factory-structure-split-v4`、`ai-judge-p21-read-model-contract-freeze-v3`、`ai-judge-p21-ops-export-contract-alignment-v1`、`ai-judge-p21-local-regression-bundle-v3`、`ai-judge-p21-enterprise-consistency-refresh-v4`，下一步 `ai-judge-p21-stage-closure-execute`）

---

## 1. 计划定位

1. 本计划承接 P20 阶段收口归档：`/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260419T085628Z-ai-judge-stage-closure-execute.md`。
2. 当前明确前提：你仍没有真实开发环境，本轮继续按 `local_reference` 路径推进，不宣称 `real-env pass`。
3. P21 核心目标：
   - 继续降低 `app_factory` 热点复杂度，推进高复杂视图构建下沉；
   - 将 read-model 契约冻结从 pack v5 扩展到更多关键聚合段；
   - 固化本地回归证据链并保持收口节奏稳定。
4. 继续执行预发布硬切原则：不保留长期兼容层、灰度双轨、旧新并行字段或双写路径。

---

## 2. 当前代码状态快照（P21 起点）

截至 2026-04-19，`ai_judge_service` 当前状态：

1. P20 主体已完成并收口：
   - `app_factory structure split v3`；
   - `ops/read-model contract freeze v2`；
   - `local regression bundle v2`；
   - `enterprise consistency refresh v3`；
   - `stage closure execute`。
2. 裁决主链保持稳定：`phase/final dispatch + trace + replay + review + failed callback + trust challenge`。
3. 关键新增资产已进入主链：
   - `app/applications/ops_read_model_pack.py`（pack v5 组装、统计、契约校验）；
   - `tests/test_ops_read_model_pack.py`（契约冻结与失败分支回归）。
4. 当前可见缺口：
   - `app_factory.py` 仍有大体量 read-model 逻辑未下沉；
   - 部分 read-model 聚合尚未具备显式“冻结级契约校验”；
   - real-env pass 仍为唯一环境阻塞项。

---

## 3. P21 总目标

1. 在无真实环境条件下继续推进“可维护 + 可验证 + 可收口”的工程稳态。
2. 把“局部契约冻结”扩大到关键运营读面，降低隐式字段漂移风险。
3. 为真实环境窗口保留一次性冲刺路径，不在本地阶段误宣称 `pass`。

---

## 4. P21 模块执行矩阵

### 已完成/未完成矩阵

| 模块 | 优先级 | 状态 | 本轮目标 | DoD（完成定义） | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| `ai-judge-next-iteration-planning` | P0 | 已完成（2026-04-19） | 阶段收口后生成 P21 完整计划 | 当前计划切换为 P21，明确“无真实环境”边界、模块矩阵与阻塞项 | `bash scripts/quality/harness_docs_lint.sh` + `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p21-app-factory-structure-split-v4` | P1 | 已完成（2026-04-19） | 继续拆分 `app_factory` 热点 | 再抽离一批高复杂 read-model 视图构建逻辑到 `applications`，路由层保留编排职责且行为不变 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "registry_alert_ops_view or policy_registry_audits"` |
| `ai-judge-p21-read-model-contract-freeze-v3` | P1 | 已完成（2026-04-19） | 扩展 read-model 契约冻结 | 对关键读面新增稳定契约断言（关键字段 + 聚合段 + 计数语义），补齐失败分支回归 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py tests/test_ops_read_model_pack.py -k "ops_read_model_pack or fairness_dashboard"` |
| `ai-judge-p21-ops-export-contract-alignment-v1` | P1 | 已完成（2026-04-19） | 对齐导出链路契约 | `ops_read_model_export` 与 pack v5/读面契约字段语义对齐，导出失败语义清晰可追踪 | `bash scripts/harness/tests/test_ai_judge_ops_read_model_export.sh` |
| `ai-judge-p21-local-regression-bundle-v3` | P2 | 已完成（2026-04-19） | 固化 P21 本地回归包 | 完成 `ruff + pytest + runtime_ops_pack(local_reference)`，产出最新证据工件并保持口径一致 | `cd ai_judge_service && ../scripts/py -m ruff check app tests` + `cd ai_judge_service && ../scripts/py -m pytest -q` + `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference` |
| `ai-judge-p21-enterprise-consistency-refresh-v4` | P2 | 已完成（2026-04-19） | 同步企业方案一致性 | 更新章节完成度映射与当前计划状态，确保“文档口径 = 代码口径” | `bash scripts/quality/harness_docs_lint.sh` + `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p21-real-env-pass-window-execute-on-env` | P0（环境阻塞） | 阻塞（待真实环境窗口） | 真实环境窗口 pass 冲刺 | `AI_JUDGE_REAL_ENV_WINDOW_CLOSURE_STATUS=pass` 且 `REAL_PASS_READY=true`，形成 on-env 证据归档 | `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p21-stage-closure-execute` | P2 | 待执行 | 执行阶段收口 | 归档当前活动计划，`completed/todo` 同步，计划文档重置到下一轮入口 | `bash scripts/harness/ai_judge_stage_closure_execute.sh --root /Users/panyihang/Documents/EchoIsle` |

### 下一开发模块建议

1. `ai-judge-p21-stage-closure-execute`

---

## 5. 延后事项（不阻塞 P21）

1. `real-env pass` 相关能力（严格 on-env）。
2. `NPC Coach / Room QA` 正式业务策略与主链接入（等待你冻结 PRD）。
3. 协议化扩展（链上锚定 / ZK / ZKML）继续保持后置。

---

## 6. 执行顺序与依赖

1. 先做 `app-factory-structure-split-v4`，继续降低维护热区。
2. 再做 `read-model-contract-freeze-v3` 与 `ops-export-contract-alignment-v1`，收敛读面与导出口径。
3. 完成本地回归包与企业一致性刷新。
4. 执行阶段收口；real-env 窗口就绪后单独推进 on-env pass。

---

## 7. 本阶段明确不做

1. 不推进 `NPC Coach / Room QA` 正式功能开发。
2. 不为未上线能力保留长期兼容层（alias/双写/灰度并行）。
3. 不把 `local_reference_ready` 或 `local_reference_frozen` 描述成 `pass`。

---

## 8. 测试与验收基线

1. `bash skills/python-venv-guard/scripts/assert_venv.sh --project /Users/panyihang/Documents/EchoIsle/ai_judge_service --venv /Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv`
2. `cd ai_judge_service && ../scripts/py -m ruff check app tests`
3. `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_ops_read_model_pack.py tests/test_app_factory.py`
4. `cd ai_judge_service && ../scripts/py -m pytest -q`
5. `bash scripts/harness/tests/test_ai_judge_artifact_prune.sh`
6. `bash scripts/harness/tests/test_ai_judge_ops_read_model_export.sh`
7. `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`
8. `bash scripts/quality/harness_docs_lint.sh`
9. `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle`

---

## 9. 风险与对策

1. 风险：`app_factory` 继续膨胀导致维护成本上升。  
   对策：P21-M1 持续拆分高复杂聚合逻辑并保留行为回归断言。
2. 风险：read-model 输出字段发生隐式漂移。  
   对策：P21-M2 扩展冻结契约并增加失败分支测试。
3. 风险：导出脚本与 read-model 语义脱节。  
   对策：P21-M3 对齐导出契约并纳入脚本回归门禁。
4. 风险：无真实环境导致状态被误读。  
   对策：保持 `local_reference_*` 与 `pass` 双层口径并在文档显式标注。

---

## 10. 模块完成同步历史

### 模块完成同步历史

1. 2026-04-19：完成 `ai-judge-stage-closure-execute`，当前开发计划已归档到 `20260419T085628Z-ai-judge-stage-closure-execute.md` 并重置。
2. 2026-04-19：完成 `ai-judge-next-iteration-planning`，当前计划切换到 P21 并锁定“无真实环境”执行边界。
3. 2026-04-19：完成 `ai-judge-p21-app-factory-structure-split-v4`，`registry_audit/alert ops view` 构建逻辑下沉到 `app/applications/registry_ops_views.py`，并通过定向回归。
4. 2026-04-19：完成 `ai-judge-p21-read-model-contract-freeze-v3`，新增 `fairness dashboard` 契约冻结校验与 500 失败分支回归，扩展 read-model 稳定性保障。
5. 2026-04-19：完成 `ai-judge-p21-ops-export-contract-alignment-v1`，增强 `ops_read_model_export` 对 fairness dashboard 冻结字段的导出校验与观测指标。
6. 2026-04-19：完成 `ai-judge-p21-local-regression-bundle-v3`，`ruff + 全量pytest + runtime_ops_pack(local_reference)` 全部通过并产出新证据工件。
7. 2026-04-19：完成 `ai-judge-p21-enterprise-consistency-refresh-v4`，章节完成度映射已更新到 P21，文档门禁与计划一致性门禁均通过。

---

## 11. 本轮启动检查清单

1. 开发前运行 `pre-module-prd-goal-guard`（本轮已执行，`full`）。
2. 涉及 API/DTO/错误码变更时，同轮同步调用方、测试与文档。
3. 与真实环境有关结论必须标注 on-env，不在本地阶段宣称 `pass`。
4. 每完成一个模块都回写当前计划矩阵与同步历史。

---

## 12. 架构方案第13章一致性校验（计划生成前置）

1. **角色一致性**：继续沿用法庭式 8 Agent 边界，不新增绕过 Sentinel/Arbiter 的捷径路径。
2. **数据一致性**：六对象主链仍是唯一裁决事实源，不引入平行 winner 写链。
3. **门禁一致性**：fairness/review/registry/trust gate 不弱化；新增能力显式标注主链或 advisory-only。
4. **边界一致性**：`NPC/Room QA` 继续 `advisory_only`，不写官方裁决链。
5. **跨层一致性**：契约变更同轮同步调用方、测试与文档，不保留长期双轨 alias。
6. **收口一致性**：真实环境结论与本地参考结论分层表达，未获窗口前不宣称 `pass`。
