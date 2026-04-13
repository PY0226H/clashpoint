# AI Judge Service

用于接收 `chat_server` 的 v3 phase/final 派发请求，执行评审逻辑，并回调内部接口写入 phase/final 报告。RAG 支持 `file(bm25s lexical)` 与 `milvus` 两种后端；hybrid 路径为 `Milvus vector + BM25 lexical + RRF + BGE/heuristic rerank`。

## 目录结构

- `app/main.py`: FastAPI 入口
- `app/app_factory.py`: v3 路由装配与运行时编排
- `app/models.py`: v3 dispatch/final 合约模型
- `app/phase_pipeline.py`: phase 报告生成主流程
- `app/runtime_rag.py` + `app/rag_retriever.py`: 检索编排与后端适配
- `app/runtime_policy.py`: provider 与环境开关解析
- `tests/test_app_factory.py`: v3 路由与回调契约测试

## 快速启动

```bash
cd /Users/panyihang/Documents/EchoIsle/ai_judge_service
uv sync --frozen --group dev --no-install-project
../scripts/py -m uvicorn app.main:app --host 0.0.0.0 --port 8787
```

仓库内所有 Python 解释器调用都应通过 `scripts/py` / `scripts/pip` 完成，不直接使用全局 `python`、`python3`、`pip`、`pip3`。
依赖解析来源为 `pyproject.toml + uv.lock`；`requirements.txt` 是由 `scripts/export_requirements.sh` 导出的供应链兼容产物，禁止手工编辑。

手工知识导入 Milvus（MVP 推荐）：

```bash
cd /Users/panyihang/Documents/EchoIsle/ai_judge_service
../scripts/py scripts/import_knowledge_to_milvus.py \
  --input-file ./knowledge.json \
  --milvus-uri http://127.0.0.1:19530 \
  --milvus-collection debate_knowledge \
  --openai-api-key "$OPENAI_API_KEY"
```

如果需要脚本自动尝试创建 collection（仅适用于你的 Milvus 配置允许该简化创建方式）：

```bash
../scripts/py scripts/import_knowledge_to_milvus.py \
  --input-file ./knowledge.json \
  --milvus-uri http://127.0.0.1:19530 \
  --milvus-collection debate_knowledge \
  --openai-api-key "$OPENAI_API_KEY" \
  --ensure-collection
```

## 环境变量

- `AI_JUDGE_INTERNAL_KEY`: 与 `chat_server.ai_judge.internal_key` 保持一致
- `CHAT_SERVER_BASE_URL`: 例如 `http://127.0.0.1:6688`
- `CHAT_SERVER_PHASE_REPORT_PATH_TEMPLATE`: phase 成功回调路径模板，默认 `/api/internal/ai/judge/v3/phase/jobs/{job_id}/report`
- `CHAT_SERVER_FINAL_REPORT_PATH_TEMPLATE`: final 成功回调路径模板，默认 `/api/internal/ai/judge/v3/final/jobs/{job_id}/report`
- `CHAT_SERVER_PHASE_FAILED_PATH_TEMPLATE`: phase 失败回调路径模板，默认 `/api/internal/ai/judge/v3/phase/jobs/{job_id}/failed`
- `CHAT_SERVER_FINAL_FAILED_PATH_TEMPLATE`: final 失败回调路径模板，默认 `/api/internal/ai/judge/v3/final/jobs/{job_id}/failed`
- `CALLBACK_TIMEOUT_SECONDS`: 回调超时，默认 `8`
- `JUDGE_PROCESS_DELAY_MS`: 模拟处理耗时，默认 `0`
- `JUDGE_STYLE_MODE`: 系统级文风开关，`rational|entertaining|mixed`，默认 `rational`
- `AI_JUDGE_PROVIDER`: `mock|openai`，默认 `openai`（`dev_mock` 也会归一化为 `mock`）
- `OPENAI_API_KEY`: 当 `AI_JUDGE_PROVIDER=openai` 时建议配置；生产环境必填
- `AI_JUDGE_OPENAI_MODEL`: 默认 `gpt-4.1-mini`
- `AI_JUDGE_OPENAI_BASE_URL`: 默认 `https://api.openai.com/v1`
- `AI_JUDGE_OPENAI_TIMEOUT_SECONDS`: OpenAI 请求超时，默认 `25`
- `AI_JUDGE_OPENAI_TEMPERATURE`: 默认 `0.1`
- `AI_JUDGE_OPENAI_MAX_RETRIES`: 每次评估重试次数，默认 `2`
- `AI_JUDGE_OPENAI_FALLBACK_TO_MOCK`: OpenAI 失败时是否回退到 mock，默认 `false`（生产环境禁止为 `true`）
- `AI_JUDGE_RAG_ENABLED`: 是否启用检索上下文，默认 `true`
- `AI_JUDGE_RAG_KNOWLEDGE_FILE`: 本地知识库 JSON 文件路径（为空则仅使用 `context_seed`）
- `AI_JUDGE_RAG_MAX_SNIPPETS`: 检索片段上限，默认 `4`
- `AI_JUDGE_RAG_MAX_CHARS_PER_SNIPPET`: 单片段最大字符数，默认 `280`
- `AI_JUDGE_RAG_QUERY_MESSAGE_LIMIT`: 检索查询使用最近消息条数，默认 `80`
- `AI_JUDGE_TOKENIZER_FALLBACK_ENCODING`: tokenizer 编码回退名，默认 `o200k_base`
- `AI_JUDGE_PHASE_PROMPT_MAX_TOKENS`: A2/A3 单次 prompt 总预算，默认 `3200`
- `AI_JUDGE_AGENT2_PROMPT_MAX_TOKENS`: A6/A7 单次 prompt 总预算，默认 `3600`
- `AI_JUDGE_RAG_QUERY_MAX_TOKENS`: RAG query 文本 token 上限，默认 `1600`
- `AI_JUDGE_RAG_SNIPPET_MAX_TOKENS`: RAG snippet token 上限，默认 `180`
- `AI_JUDGE_EMBED_INPUT_MAX_TOKENS`: embedding 输入 token 上限，默认 `2000`
- `AI_JUDGE_RAG_SOURCE_WHITELIST`: 允许知识来源的 URL 前缀列表（逗号/分号/换行分隔），默认 `https://teamfighttactics.leagueoflegends.com/en-us/news/`
- `AI_JUDGE_RAG_BACKEND`: `file|milvus`，默认 `file`
- `AI_JUDGE_RAG_LEXICAL_ENGINE`: 词法检索引擎，当前固定为 `bm25`
- `AI_JUDGE_RAG_BM25_CACHE_DIR`: BM25 sidecar 索引缓存目录，默认 `ai_judge_service/.cache/bm25`
- `AI_JUDGE_RAG_BM25_USE_DISK_CACHE`: 是否启用 BM25 磁盘缓存，默认 `true`
- `AI_JUDGE_RAG_BM25_FALLBACK_TO_SIMPLE`: BM25 不可用时是否回退简单 overlap lexical，默认 `true`
- `AI_JUDGE_RAG_OPENAI_EMBEDDING_MODEL`: Milvus 检索生成查询向量的 embedding 模型，默认 `text-embedding-3-small`
- `AI_JUDGE_RAG_MILVUS_URI`: Milvus 连接地址（例如 `http://127.0.0.1:19530`）
- `AI_JUDGE_RAG_MILVUS_TOKEN`: Milvus token（可空）
- `AI_JUDGE_RAG_MILVUS_DB_NAME`: Milvus DB 名称（可空）
- `AI_JUDGE_RAG_MILVUS_COLLECTION`: Milvus collection 名称
- `AI_JUDGE_RAG_MILVUS_VECTOR_FIELD`: 向量字段名，默认 `embedding`
- `AI_JUDGE_RAG_MILVUS_CONTENT_FIELD`: 文本内容字段名，默认 `content`
- `AI_JUDGE_RAG_MILVUS_TITLE_FIELD`: 标题字段名，默认 `title`
- `AI_JUDGE_RAG_MILVUS_SOURCE_URL_FIELD`: 来源 URL 字段名，默认 `source_url`
- `AI_JUDGE_RAG_MILVUS_CHUNK_ID_FIELD`: chunk id 字段名，默认 `chunk_id`
- `AI_JUDGE_RAG_MILVUS_TAGS_FIELD`: tags 字段名，默认 `tags`
- `AI_JUDGE_RAG_MILVUS_METRIC_TYPE`: 向量距离类型，默认 `COSINE`
- `AI_JUDGE_RAG_MILVUS_SEARCH_LIMIT`: Milvus 向量召回候选数，默认 `20`
- `AI_JUDGE_STAGE_AGENT_MAX_CHUNKS`: 阶段 Agent 最大处理窗口数（超出取最近窗口），默认 `12`
- `AI_JUDGE_REFLECTION_ENABLED`: 终局反思回路开关，默认 `true`
- `AI_JUDGE_REFLECTION_POLICY`: 反思策略，`winner_mismatch_only|winner_mismatch_or_low_margin`，默认 `winner_mismatch_only`
- `AI_JUDGE_REFLECTION_LOW_MARGIN_THRESHOLD`: 低分差保护阈值（平均分差），默认 `3`
- `AI_JUDGE_FAULT_INJECTION_NODES`: 故障注入节点（逗号分隔），可选
  - pipeline 节点：`stage_judge,aggregate,final_pass_1,final_pass_2,display`
  - 运行时故障：`provider_timeout,provider_overload,rag_retrieve_timeout,rag_retrieve_unavailable,topic_memory_unavailable`
  - 生产环境禁止
- `AI_JUDGE_TOPIC_MEMORY_ENABLED`: 辩题级长期记忆开关，默认 `true`
- `AI_JUDGE_RAG_HYBRID_ENABLED`: 混合检索策略开关，默认 `true`
- `AI_JUDGE_RAG_RERANK_ENABLED`: 检索重排开关，默认 `true`
- `AI_JUDGE_RAG_RERANK_ENGINE`: 重排引擎，`bge|heuristic`，默认 `bge`
- `AI_JUDGE_RAG_RERANK_MODEL`: 重排模型，默认 `BAAI/bge-reranker-v2-m3`
- `AI_JUDGE_RAG_RERANK_BATCH_SIZE`: 重排批大小，默认 `16`
- `AI_JUDGE_RAG_RERANK_CANDIDATE_CAP`: 每次重排候选上限，默认 `50`
- `AI_JUDGE_RAG_RERANK_TIMEOUT_MS`: 重排超时毫秒，默认 `12000`
- `AI_JUDGE_RAG_RERANK_DEVICE`: 重排设备，`cpu|cuda`，默认 `cpu`
- `AI_JUDGE_DEGRADE_MAX_LEVEL`: 最大降级等级 `0..3`，默认 `3`
- `AI_JUDGE_RUNTIME_RETRY_MAX_ATTEMPTS`: runtime 可重试错误最大尝试次数（含首次），默认 `2`
- `AI_JUDGE_RUNTIME_RETRY_BACKOFF_MS`: runtime 重试退避基线毫秒，默认 `200`
- `AI_JUDGE_COMPLIANCE_BLOCK_ENABLED`: 检测到合规违规时是否阻断提交并走 failed callback，默认 `true`
- `AI_JUDGE_TRACE_TTL_SECS`: trace 与回放记录 TTL，默认 `86400`
- `AI_JUDGE_IDEMPOTENCY_TTL_SECS`: 幂等键 TTL，默认 `86400`
- `AI_JUDGE_REDIS_ENABLED`: 启用 Redis 短期记忆（trace/idempotency/stage runtime），默认 `false`
- `AI_JUDGE_REDIS_REQUIRED`: Redis 不可用时是否启动失败（`true`=fail-closed，`false`=fail-open 回退内存），默认 `false`
- `AI_JUDGE_REDIS_URL`: Redis 连接串，默认 `redis://127.0.0.1:6379/0`
- `AI_JUDGE_REDIS_POOL_SIZE`: Redis 连接池大小，默认 `20`
- `AI_JUDGE_REDIS_KEY_PREFIX`: Redis 键前缀，默认 `ai_judge:v2`
- `AI_JUDGE_TOPIC_MEMORY_LIMIT`: 辩题级长期记忆复用条数上限，默认 `5`
- `AI_JUDGE_TOPIC_MEMORY_MIN_EVIDENCE_REFS`: topic memory 入库最小证据条数，默认 `1`
- `AI_JUDGE_TOPIC_MEMORY_MIN_RATIONALE_CHARS`: topic memory 入库最小理由长度，默认 `20`
- `AI_JUDGE_TOPIC_MEMORY_MIN_QUALITY_SCORE`: topic memory 入库最小质量分（`0..1`），默认 `0.55`

生产环境识别规则：按 `ECHOISLE_ENV -> APP_ENV -> PYTHON_ENV -> RUST_ENV -> ENV` 顺序读取，值为 `prod|production` 时视为生产。
生产环境门禁：
- 禁止 `AI_JUDGE_PROVIDER=mock`
- 禁止 `AI_JUDGE_OPENAI_FALLBACK_TO_MOCK=true`
- `AI_JUDGE_PROVIDER=openai` 时，`OPENAI_API_KEY` 不能为空
- 禁止配置 `AI_JUDGE_FAULT_INJECTION_NODES`

## 内部运维接口（v2）

均要求 header：`x-ai-internal-key`

- `GET /internal/judge/jobs/{job_id}/trace`：查看单任务 trace、请求快照、回调状态、回放历史
- `POST /internal/judge/jobs/{job_id}/replay`：按历史请求快照执行一次无副作用重放（不触发 callback），支持 `dispatch_type=auto|final|phase`（默认 `auto`：优先 final，缺失回退 phase）
- `GET /internal/judge/jobs/{job_id}/replay/report`：导出 job 级回放报告（输入快照、阶段输出、终局结果、callback 状态、审计字段）
- `GET /internal/judge/jobs/replay/reports`：按筛选条件查询回放报告列表（`status/winner/callback_status/trace_id/created_after/created_before/has_audit_alert/limit`，可选 `include_report=true` 返回完整报告）
- `GET /internal/judge/jobs/{job_id}/alerts`：查看任务审计告警（支持 `status=raised|acked|resolved`）
- `POST /internal/judge/jobs/{job_id}/alerts/{alert_id}/ack`：告警确认（`raised -> acked`）
- `POST /internal/judge/jobs/{job_id}/alerts/{alert_id}/resolve`：告警恢复（`raised|acked -> resolved`）
- `GET /internal/judge/alerts/outbox`：查看待投递通知事件 outbox（支持 `delivery_status=pending|sent|failed`）
- `POST /internal/judge/alerts/outbox/{event_id}/delivery`：回写 outbox 投递结果（`delivery_status=sent|failed`）
- `GET /internal/judge/rag/diagnostics?job_id=...`：查看该任务检索诊断摘要
- `GET /internal/judge/v3/phase/jobs/{job_id}/receipt`：查看 phase dispatch 请求落库快照（入参、状态、回执）
- `GET /internal/judge/v3/final/jobs/{job_id}/receipt`：查看 final dispatch 请求落库快照（入参、状态、回执）

## v3 回调契约

- final report 主展示字段已硬切为：
  - `debateSummary`
  - `sideAnalysis`（必须包含 `pro` 与 `con`）
  - `verdictReason`
- final 关键字段缺失会阻断成功回调，并触发 failed callback。
- phase/final failed callback payload 统一包含：
  - `jobId`
  - `dispatchType`
  - `traceId`
  - `errorCode`
  - `errorMessage`
  - `auditAlertIds`（可空）
  - `degradationLevel`（可空）

`dispatch` 的 `retrieval_profile`（默认 `hybrid_v1`）当前支持：
- `hybrid_v1`
- `hybrid_recall_v1`
- `hybrid_precision_v1`
- `lexical_fast_v1`

运行时错误码（M5 phase1）：
- `judge_timeout`
- `rag_unavailable`
- `model_overload`
- `consistency_conflict`

`report.payload` 中会回写：
- `errorCodes`: 当前任务触发的错误码列表（可为空）。
- `judgeTrace.errorCodes`: 与上面一致，用于链路追踪对齐。
- `auditAlerts`: 审计告警列表（如 `compliance_violation`）。
- `judgeAudit`: 审计快照（`promptHash/model/rubricVersion/retrievalSnapshot/degradationLevel`）。

当命中公平性/合规违规并触发阻断时：
- `dispatch` 返回 `status=marked_failed` 与 `errorCode=consistency_conflict`
- 响应中包含 `auditAlert`
- 响应中包含 `auditAlertIds`（可用于后续 ack/resolve）
- `GET /internal/judge/jobs/{job_id}/replay/report` 的 `auditAlerts` 可用于 Ops 复盘

M6 phase4 告警状态机：
- 告警状态：`raised -> acked -> resolved`
- 每次状态变化都会写入 `alerts/outbox`，用于对接通知中心投递链路

## 知识文件格式（最小）

`AI_JUDGE_RAG_KNOWLEDGE_FILE` 指向一个 JSON 数组，每个元素示例：

```json
[
  {
    "chunkId": "tft-frontline-001",
    "title": "前排改动说明",
    "sourceUrl": "https://teamfighttactics.leagueoflegends.com/en-us/news/...",
    "content": "该版本前排羁绊获得额外护甲和魔抗加成。",
    "tags": ["tft", "frontline"]
  }
]
```

## 检索链路说明

- `file` backend: `BM25 lexical -> topK -> BGE/heuristic rerank`
- `milvus` backend 且 `AI_JUDGE_RAG_HYBRID_ENABLED=true`: `Milvus vector + BM25 lexical -> RRF -> BGE/heuristic rerank`
- 当前不接 Elasticsearch；若后续知识规模、过滤条件和运维复杂度明显上升，再升级为外部 lexical backend。

## 运行测试

依赖安装完成后执行：

```bash
cd /Users/panyihang/Documents/EchoIsle/ai_judge_service
.venv/bin/pytest -q
```

运行静态检查与质量门禁：

```bash
cd /Users/panyihang/Documents/EchoIsle/ai_judge_service
./scripts/run_quality_gate.sh
```

类型检查当前采用分阶段收敛：

1. `mypy` phase1 strict 覆盖：
   - `app/settings.py`
   - `app/runtime_policy.py`
   - `app/runtime_errors.py`
   - `app/token_budget.py`
   - `app/models.py`
   - `app/rag_profiles.py`
   - `app/openai_judge_client.py`
2. `pyright` phase1 strict 覆盖：`settings/runtime_policy/runtime_errors/token_budget/rag_profiles`。
3. `trace_store/phase_pipeline/rag_retriever/runtime_rag/milvus_indexer/lexical_retriever` 以及剩余测试文件纳入后续收敛。
4. 收敛目标：`2026-05-31` 前完成 `app/` 与 `tests/` 全量 strict，每个 PR 只增不减覆盖范围。

M7 预验收（phase1）端到端场景回归：

```bash
cd /Users/panyihang/Documents/EchoIsle/ai_judge_service
.venv/bin/pytest -q tests/test_m7_acceptance_gate.py
```

M7 预验收门禁（phase2，回归 + 负载阈值 + 报告）：

```bash
cd /Users/panyihang/Documents/EchoIsle/ai_judge_service
../scripts/py scripts/m7_acceptance_gate.py \
  --report-out ../docs/loadtest/evidence/AI裁判M7验收报告-$(date +%F).md
```

M7 预发阶段验收门禁（phase3，回归证据 + Soak/Spike + 故障注入矩阵）：

```bash
cd /Users/panyihang/Documents/EchoIsle
bash scripts/release/ai_judge_m7_stage_acceptance_gate.sh \
  --regression-evidence docs/loadtest/evidence/ai_judge_m7_regression.env \
  --preprod-summary docs/loadtest/evidence/ai_judge_m7_preprod_summary.env \
  --fault-matrix docs/loadtest/evidence/ai_judge_m7_fault_matrix.env \
  --report-out docs/loadtest/evidence/AI裁判M7阶段验收报告-$(date +%F).md
```

## RAG 评测基线（M4 phase2）

执行离线 profile 对照评测：

```bash
cd ai_judge_service
../scripts/py scripts/rag_eval_baseline.py \
  --dataset-file ./tests/fixtures/rag_eval_cases.json \
  --knowledge-file ./knowledge.json \
  --output-file /tmp/rag_eval_result.json
```

`dataset-file` 为 JSON 数组，每项包含：
- `request`: `topic/messages/retrieval_profile` 结构（可兼容旧样例字段）
- `expectedChunkIds`: 该样本期望命中的 chunk id 列表
