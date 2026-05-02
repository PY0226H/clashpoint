# AI Judge Local Reference Regression Refresh

1. 生成日期：2026-05-02
2. 统一状态：`pass`
3. 执行模式：`local_reference`
4. real-env pass ready：`false`
5. real-env window status：`env_blocked`
6. run_id：`20260502T063011Z-ai-judge-local-reference-regression-refresh`

## 1. 回归范围

1. AI service：官方 Judge 主链、public verify、challenge/public contract、runtime readiness public contract 与全量 pytest。
2. chat_server：官方 judge job 与 judge report/query/proxy 合同回归。
3. frontend：`debate-domain`、`ops-domain`、`app-shell` 的 test/typecheck/lint。
4. harness：real-env window closure、real-env evidence closure、runtime ops pack、stage closure evidence 与 plan consistency gate。

## 2. 命令结果

| 命令 | 结果 |
| --- | --- |
| `bash skills/python-venv-guard/scripts/assert_venv.sh --project /Users/panyihang/Documents/EchoIsle/ai_judge_service --venv /Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv` | `pass` |
| `cd ai_judge_service && /Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv/bin/python -m pytest -q tests/test_judge_mainline.py tests/test_judge_command_routes.py tests/test_runtime_readiness_public_contract.py tests/test_public_verify_projection.py tests/test_trust_challenge_public_contract.py` | `pass` |
| `cd ai_judge_service && /Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv/bin/ruff check app tests scripts` | `pass` |
| `cd ai_judge_service && /Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv/bin/python -m pytest -q` | `pass` |
| `cd chat && cargo test -p chat-server request_judge_job` | `pass` |
| `cd chat && cargo test -p chat-server request_judge_report_query` | `pass` |
| `pnpm --dir frontend --filter @echoisle/debate-domain test` | `pass` |
| `pnpm --dir frontend --filter @echoisle/debate-domain typecheck` | `pass` |
| `pnpm --dir frontend --filter @echoisle/debate-domain lint` | `pass` |
| `pnpm --dir frontend --filter @echoisle/ops-domain test` | `pass` |
| `pnpm --dir frontend --filter @echoisle/ops-domain typecheck` | `pass` |
| `pnpm --dir frontend --filter @echoisle/ops-domain lint` | `pass` |
| `pnpm --dir frontend --filter @echoisle/app-shell test` | `pass` |
| `pnpm --dir frontend --filter @echoisle/app-shell typecheck` | `pass` |
| `pnpm --dir frontend --filter @echoisle/app-shell lint` | `pass` |
| `bash scripts/harness/tests/test_ai_judge_real_env_window_closure.sh` | `pass` |
| `bash scripts/harness/tests/test_ai_judge_real_env_evidence_closure.sh` | `pass` |
| `bash scripts/harness/tests/test_ai_judge_plan_consistency_gate.sh` | `pass` |
| `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference` | `local_reference_ready` |
| `bash scripts/harness/ai_judge_real_env_evidence_closure.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference` | `local_reference_ready` |
| `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle --preflight-only` | `env_blocked` |
| `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle --plan-doc docs/dev_plan/当前开发计划.md` | `pass` |
| `bash scripts/harness/ai_judge_stage_closure_evidence.sh --root /Users/panyihang/Documents/EchoIsle` | `pass` |
| `bash scripts/quality/harness_docs_lint.sh --root /Users/panyihang/Documents/EchoIsle` | `pass` |

## 3. 证据工件

1. runtime ops pack：`docs/loadtest/evidence/ai_judge_runtime_ops_pack.md`
2. real-env evidence closure：`docs/loadtest/evidence/ai_judge_p5_real_env_closure_checklist.md`
3. real-env window closure：`docs/loadtest/evidence/ai_judge_real_env_window_closure.md`
4. stage closure evidence：`docs/loadtest/evidence/ai_judge_stage_closure_evidence.md`
5. plan consistency gate：`artifacts/harness/20260502T063257Z-ai-judge-plan-consistency-gate.summary.md`
6. local reference summary env：`docs/loadtest/evidence/ai_judge_local_reference_regression_refresh.env`
7. PRD guard metadata：`artifacts/harness/ai-judge-local-reference-regression-refresh-pack-prd-guard.env`

## 4. 结论

1. 本地参考回归通过，可作为后续 stage closure 或等待真实环境窗口前的可信本地基线。
2. runtime ops pack 当前为 `local_reference_ready`，stage closure evidence 当前为 `pass`。
3. real-env window preflight 当前为 `env_blocked`；阻塞原因包括真实样本 manifest、真实 provider/callback、生产对象存储 roundtrip 与真实阈值目标尚未齐备。
4. 本摘要不代表 real-env pass；真实环境结论仍以后续 C46 补证为准。
5. `NPC Coach` / `Room QA` 仍保持暂停；本轮只验证历史保护面不会污染 official verdict，不推进 assistant executor、ready-state 或 Ops evidence。
