# AI Judge Route Hotspot Inventory

更新时间：2026-05-02
模块：`P0-B. ai-judge-route-hotspot-inventory-pack`
状态：`completed_no_split`

---

## 1. 结论

1. 本轮只做 route/hotspot inventory，不拆代码。
2. 当前第一跳定位已经由 [docs/architecture/README.md](/Users/panyihang/Documents/EchoIsle/docs/architecture/README.md) 区分为官方 Judge 主线、Ops/readiness 主线与暂停 assistant 历史资产；本轮 inventory 未发现必须继续改 architecture map 的新入口。
3. 最大热点是 [debate_ops.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_ops.rs) 4826 行、[request_report_query.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/request_report_query.rs) 3572 行、[app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) 2346 行、[judge_command_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_command_routes.py) 2204 行。
4. 这些热点目前仍有清晰第一跳和 targeted tests；立即拆分收益不高，风险主要是误碰 official verdict、runtime readiness 或暂停 assistant 边界。
5. 下一步 P1-C 应优先建立官方合同测试索引；若测试索引发现某个热点需要反复修改，再按第 6 节的小拆分顺序执行。

## 2. 扫描口径

本次基于当前工作区代码事实扫描：

1. `wc -l`：统计 AI service、chat_server、frontend 热点文件行数。
2. `rg`：定位 AI service route registration、chat route/OpenAPI 入口、frontend domain/API 调用、现有 targeted tests。
3. 只记录当前开发决策需要的第一跳证据，不把本文件做成完整实现索引。
4. `NPC Coach` / `Room QA` 只作为暂停历史资产记录，不作为开发入口、不删除、不恢复。

## 3. 热点总览

| 文件 | 行数 | 平面 | 主职责 | 当前测试入口 | 建议动作 |
| --- | ---: | --- | --- | --- | --- |
| [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) | 2346 | official + ops + paused advisory wiring | 创建 runtime、装配依赖、注册 route groups | `test_app_factory*.py`, `test_app_factory_command_dispatch_routes.py`, route group tests | 暂不拆；后续只在 wiring 继续膨胀时抽 route registration coordinator |
| [judge_command_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_command_routes.py) | 2204 | official plane | case create、phase/final dispatch、callback、receipt、trust snapshot 写入 | `test_judge_command_routes.py`, `test_route_group_judge_command.py`, `test_app_factory_command_dispatch_routes.py` | 暂不拆；P1-C 若补合同测试命中这里，再优先拆 dispatch preflight/materialization/callback helper |
| [judge_workflow_roles.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_workflow_roles.py) | 1485 | official plane | Clerk/Recorder/Claim/Evidence/Panel/Fairness/Arbiter/Opinion 角色语义 | `test_judge_workflow_roles.py`, `test_judge_mainline.py` | 暂不拆；保护 8 Agent 顺序与 fact lock，不做结构重排 |
| [route_group_*.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications) | 3447 total | official + ops + paused advisory | route group 下沉层 | `test_route_group_*.py`, app factory route tests | 已经承担第一层拆分；继续沿用 |
| [bootstrap_*_helpers.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications) | 2885 total | wiring helpers | runtime helper / payload helper / dependency helper | `test_bootstrap_*_helpers.py` | 已经下沉大块 helper；短期不继续拆 |
| [debate_judge.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_judge.rs) | 1589 | official + paused advisory | 用户侧 judge job/report/public verify/challenge/draw vote；同时包含暂停 assistant proxy route | handler tests in same file, `request_judge_report_query.rs` tests | 暂不移动 assistant；P1-C 只检查 official route 合同 |
| [debate_ops.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_ops.rs) | 4826 | ops plane | Ops topics/session/RBAC/observability/kafka/judge ops route | `handlers/debate.rs` ops route tests, `request_judge_report_query.rs` ops tests | 文件最大；但 AI Judge ops route 只是其中一段，后续若继续改 judge ops，优先抽 `handlers/debate_ops/judge.rs` |
| [request_report_query.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/request_report_query.rs) | 3572 | official + ops + paused advisory proxy | report/read model/public verify/challenge/runtime readiness/replay/advisory proxy | `request_judge_report_query.rs` tests | 最大模型热点；P1-C/P1-D 若继续命中，优先抽 official report query 或 challenge proxy helper |
| [runtime_readiness_ops_projection.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/runtime_readiness_ops_projection.rs) | 344 | ops/readiness | AI runtime readiness public-safe proxy contract | `request_judge_report_query.rs`, frontend `runtimeReadiness.test.ts` | 已下沉，保持 |
| [assistant_advisory_proxy.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/assistant_advisory_proxy.rs) | 576 | paused advisory | NPC Coach / Room QA proxy 合同与 forbidden field guard | `request_judge_report_query.rs`, frontend assistant tests | 暂停历史资产；不继续开发 |
| [OpsConsolePage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/OpsConsolePage.tsx) | 1491 | ops plane | Ops Console 聚合 runtime readiness、challenge queue、observability | `runtimeReadiness.test.ts`, `OpsCalibrationDecisionActions.test.tsx` | 暂不拆；后续 UI 大改时优先抽 RuntimeReadiness panel |
| [runtimeReadiness.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/ops-domain/src/runtimeReadiness.ts) | 223 | ops/readiness | runtime readiness typed API 与 calibration decision API | `runtimeReadiness.test.ts` | 稳定，保持 |
| [debate-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/debate-domain/src/index.ts) | 1602 | official + paused advisory | debate/judge report/public verify/challenge/advisory typed API | `index.test.ts`, `DebateAssistantPanel.test.tsx` | 暂不拆；P1-C 只索引 official 合同，assistant 保持暂停 |

## 4. AI Service Route Registration

[app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) 当前仍是 wiring 中心，但 route 注册已经按 group 下沉：

| app_factory 行 | route group | 平面 | 说明 |
| ---: | --- | --- | --- |
| 1969 | `register_registry_routes` | ops/platform | policy/prompt/tool registry、release/gate/governance |
| 2013 | `register_judge_command_routes` | official | case create、phase/final dispatch、receipt |
| 2063 | `register_case_read_routes` | official/ops read | case overview、claim ledger、courtroom read model |
| 2116 | `register_assistant_routes` | paused advisory | NPC Coach / Room QA internal routes，仅保留暂停历史入口 |
| 2128 | `register_replay_routes` | ops/replay | trace/replay/report |
| 2150 | `register_trust_routes` | official trust | commitment、public verify、challenge、attestation |
| 2198 | `register_fairness_routes` | ops/fairness | benchmark、shadow、case fairness、calibration decisions |
| 2239 | `register_panel_runtime_routes` | ops/panel | panel profiles/readiness |
| 2254 | `register_review_routes` | ops/review | review cases/detail/decision |
| 2294 | `register_ops_read_model_pack_routes` | ops/readiness | ops read model pack、runtime readiness |
| 2312 | `register_alert_ops_routes` | ops/alert | alert ops view、outbox、RAG diagnostics |

判断：

1. `app_factory.py` 大，但第一跳已经是“runtime wiring + route group registration”，并非业务逻辑散落不可定位。
2. `route_group_judge_command.py` 仅 598 行，负责把 command routes 接到 `judge_command_routes.py` helper；这层已足够承接第一跳。
3. 继续拆 `app_factory.py` 之前，应先有明确重复修改压力；否则只会增加 wiring indirection。

## 5. Chat / Frontend Route Boundary

### 5.1 用户侧 official route 与暂停 advisory route

[chat/chat_server/src/lib.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/lib.rs) 当前注册：

| 路径 | handler | 平面 | 边界判断 |
| --- | --- | --- | --- |
| `/sessions/:id/judge/jobs` | `request_judge_job_handler` | official | 当前主线 |
| `/sessions/:id/judge-report` | `get_latest_judge_report_handler` | official | 当前主线 |
| `/sessions/:id/judge-report/final` | `get_latest_judge_final_report_handler` | official | 当前主线 |
| `/sessions/:id/judge-report/public-verify` | `get_judge_public_verify_handler` | official/trust | 当前主线 |
| `/sessions/:id/judge-report/challenge` | `get_judge_challenge_handler` | official/trust | 当前主线 |
| `/sessions/:id/judge-report/challenge/request` | `request_judge_challenge_handler` | official/trust | 当前主线 |
| `/sessions/:id/draw-vote` | `get_draw_vote_status_handler` | official | 当前主线 |
| `/sessions/:id/draw-vote/ballots` | `submit_draw_vote_handler` | official | 当前主线 |
| `/sessions/:id/assistant/npc-coach/advice` | `request_npc_coach_advice_handler` | paused advisory | 暂停历史资产 |
| `/sessions/:id/assistant/room-qa/answer` | `request_room_qa_answer_handler` | paused advisory | 暂停历史资产 |

判断：

1. `debate_judge.rs` 中 official route 与暂停 advisory route 同文件，但 route 列表可清晰区分。
2. 本轮不移动暂停 advisory route，避免在未冻结新 PRD 时制造不必要行为风险。
3. P1-C 只索引 official job/report/public verify/challenge/draw vote 合同；assistant 测试只作为“不污染官方裁决”的历史保护面。

### 5.2 Ops route

[chat/chat_server/src/lib.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/lib.rs) 当前注册的 AI Judge Ops 入口：

| 路径 | handler | 说明 |
| --- | --- | --- |
| `/ops/judge-reviews` | `list_judge_reviews_ops_handler` | judge review ops list |
| `/ops/judge-runtime-readiness` | `get_judge_runtime_readiness_ops_handler` | runtime readiness proxy |
| `/ops/judge-calibration-decisions` | `create_judge_calibration_decision_ops_handler` | Ops-only calibration decision，已下沉到 `debate_ops/calibration_decision.rs` |
| `/ops/judge-challenge-queue` | `list_judge_challenge_queue_ops_handler` | challenge ops queue |
| `/ops/judge-final-dispatch/failure-stats` | `list_judge_final_dispatch_failure_stats_ops_handler` | final dispatch failure stats |
| `/ops/judge-trace-replay` | `list_judge_trace_replay_ops_handler` | trace replay list |
| `/ops/judge-replay/preview` | `get_judge_replay_preview_ops_handler` | replay preview |
| `/ops/judge-replay/execute` | `execute_judge_replay_ops_handler` | replay execute |
| `/ops/judge-replay/actions` | `list_judge_replay_actions_ops_handler` | replay actions |
| `/ops/sessions/:id/judge/rejudge` | `request_judge_rejudge_ops_handler` | Ops rejudge |

判断：

1. `debate_ops.rs` 是全局 Ops 聚合热点，不只是 AI Judge 文件。
2. AI Judge calibration decision 已经下沉到 `handlers/debate_ops/calibration_decision.rs`，说明现有拆分方向有效。
3. 后续若 P1-C/P1-D 继续修改 judge ops handler，优先抽 `handlers/debate_ops/judge.rs`；本轮不提前做。

## 6. 建议的小拆分触发顺序

| 优先级 | 触发条件 | 建议动作 | 不触碰 |
| --- | --- | --- | --- |
| 1 | P1-C 合同索引发现 `judge_command_routes.py` 需要补多个 official dispatch 负向测试并修改 helper | 从 `judge_command_routes.py` 抽 dispatch preflight/materialization/callback helper，保留 route group API | 不改变 phase/final dispatch 合同 |
| 2 | P1-C/P1-D 继续改 `request_report_query.rs` 的 report/public verify/challenge/runtime readiness proxy | 抽 official report query 或 challenge proxy helper，复用现有 `runtime_readiness_ops_projection.rs` 方向 | 不移动 `assistant_advisory_proxy.rs` |
| 3 | 后续 AI Judge Ops route 继续集中修改 `debate_ops.rs` | 新建 `handlers/debate_ops/judge.rs` 承接 judge reviews/readiness/challenge/replay/rejudge | 不动非 judge Ops 路由 |
| 4 | Ops Console runtime readiness UI 再增长 | 从 `OpsConsolePage.tsx` 抽 RuntimeReadiness panel component | 不改变 `ops-domain` API |
| 5 | app wiring 继续膨胀且 route group 依赖重复 | 抽 `build_ai_judge_route_registry` 或类似 wiring coordinator | 不把业务逻辑搬回 app factory |

## 7. 现有测试保护面

### AI service

1. Official mainline：`test_judge_mainline.py`、`test_judge_command_routes.py`、`test_route_group_judge_command.py`、`test_app_factory_command_dispatch_routes.py`。
2. Trust / public verify / challenge：`test_public_verify_projection.py`、`test_trust_challenge_public_contract.py`、`test_route_group_trust.py`、`test_trust_challenge_runtime_routes.py`。
3. Runtime readiness：`test_runtime_readiness_public_contract.py`、`test_runtime_readiness_public_projection.py`、`test_route_group_ops_read_model_pack.py`。
4. Paused advisory historical guards：`test_route_group_assistant.py`、`test_assistant_agent_routes.py`、`test_assistant_advisory_prompt_output.py`。

### chat_server

1. Handler route permissions：inline tests in [debate_judge.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_judge.rs) cover auth、phone bind、participant boundary、public verify、challenge request、assistant forbidden/missing session。
2. Model contracts：`request_judge_job.rs` rejects unknown official verdict/challenge mutation fields and covers job idempotency/rejudge.
3. Report/query/proxy contracts：`request_judge_report_query.rs` covers report read, public verify, challenge, runtime readiness, calibration decision, replay and paused advisory proxy guards.
4. Final report / draw vote：`phase_final_report_submit.rs` covers final report persistence, idempotency, invalid winner fields and draw vote creation.
5. Ops routes：inline tests in [debate.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate.rs) cover judge reviews, calibration decision, replay, rejudge, RBAC and invalid input.

### frontend

1. [frontend/packages/debate-domain/src/index.test.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/debate-domain/src/index.test.ts) covers public verify, challenge read model, typed judge APIs and paused assistant fail-closed contract.
2. [frontend/packages/ops-domain/src/runtimeReadiness.test.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/ops-domain/src/runtimeReadiness.test.ts) covers runtime readiness endpoint defaults, filters and calibration decision idempotency.
3. [DebateAssistantPanel.test.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/components/DebateAssistantPanel.test.tsx) covers paused advisory UI remains advisory-only.
4. [OpsCalibrationDecisionActions.test.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/components/OpsCalibrationDecisionActions.test.tsx) covers Ops-only calibration decision action UI.

## 8. P0-B 验收状态

| 验收项 | 状态 | 说明 |
| --- | --- | --- |
| 产出可引用 inventory evidence | 通过 | 本文件即 P0-B inventory evidence |
| 区分 active official / ops / paused advisory | 通过 | 第 3、4、5 节已分层 |
| 不恢复或删除 NPC Coach / Room QA | 通过 | 仅记录暂停历史资产边界 |
| 决定是否立即拆分 | 通过 | 本轮 `completed_no_split`，后续按第 6 节触发 |
| 是否需要更新 architecture map | 不需要 | P0-A 已更新第一跳；P0-B 没有新增入口或模块边界变更 |
| 是否需要运行代码测试 | 不需要 | 本轮只新增/更新文档，不改变运行代码、API/DTO 或测试合同 |

