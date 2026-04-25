# AI Judge P36 Local Reference Regression

1. 生成日期：2026-04-25
2. 更新时间：2026-04-25T07:25:14Z
3. 统一状态：`local_reference_ready`
4. 环境模式：`local_reference`
5. 真实环境 pass：`false`

## 覆盖范围

| 维度 | 本地参考状态 | 证据 |
| --- | --- | --- |
| trust registry durable/read-through | `local_reference_ready` | `pytest -q` 全量通过，覆盖 trust registry repository、trust read routes、app factory trust routes |
| artifact manifest/local artifact store | `local_reference_ready` | `test_ai_judge_audit_anchor_export_local.sh` 通过，pytest 运行产生本地 artifact refs，`ai_judge_service/artifacts/` 已作为本地输出忽略 |
| public verify redaction | `local_reference_ready` | `pytest -q` 全量通过，覆盖 public verify contract 与 app factory trust attestation routes |
| challenge review state machine | `local_reference_ready` | `pytest -q` 全量通过，覆盖 challenge runtime/routes、workflow orchestrator 与 ops queue contract |
| ops read model trust/artifact coverage | `local_reference_ready` | `pytest -q` 全量通过，覆盖 ops read model pack、case read、trace replay 与 route group |
| runtime ops pack | `local_reference_ready` | `docs/loadtest/evidence/ai_judge_runtime_ops_pack.md` |

## 已执行命令

1. `bash skills/pre-module-prd-goal-guard/scripts/run_prd_goal_guard.sh --root /Users/panyihang/Documents/EchoIsle --task-kind dev --module ai-judge-p36-local-reference-regression-pack --summary "Run P36 AI Judge local reference regression and runtime ops pack without claiming real environment pass" --mode auto --metadata-out artifacts/harness/ai-judge-p36-local-reference-regression-pack-pre-prd-goal-guard.metadata`
2. `bash skills/python-venv-guard/scripts/assert_venv.sh --project /Users/panyihang/Documents/EchoIsle/ai_judge_service --venv /Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv`
3. `/Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv/bin/ruff check app tests`
4. `/Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv/bin/python -m pytest -q`
5. `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --evidence-dir docs/loadtest/evidence --allow-local-reference`
6. `bash scripts/harness/tests/test_ai_judge_audit_anchor_export_local.sh`
7. `bash scripts/harness/tests/test_ai_judge_runtime_ops_pack.sh`

## 结果摘要

| 检查 | 状态 | 备注 |
| --- | --- | --- |
| ruff | `pass` | `app tests` |
| pytest | `pass` | 571 tests collected and passed |
| runtime ops pack | `local_reference_ready` | `allow_local_reference=true` |
| audit anchor local export script tests | `pass` | ready/pending/fake-pending fail-closed 场景通过 |
| runtime ops pack script tests | `pass` | blocked/local/pass/violation/ingest 场景通过 |

## 真实环境后置条件

1. 后续真实环境模块：`ai-judge-p36-real-env-pass-window-execute-on-env`
2. 需要真实样本、真实 AI provider / callback 环境、真实服务窗口与 on-env evidence。
3. 当前文档只证明 P36 本地参考链路可用，不替代 real-env `pass`。
