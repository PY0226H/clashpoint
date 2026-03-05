# AI Judge Service

用于接收 `chat_server` 的评审派发请求，执行评审逻辑（`mock` 或 `openai` 多 Agent 流水线），并回调内部接口写入评审结果。RAG 支持 `file` 与 `milvus` 两种后端。

## 目录结构

- `app/main.py`: FastAPI 入口与回调编排
- `app/models.py`: 派发请求与回调模型
- `app/scoring_core.py`: 不依赖三方框架的评分核心
- `app/scoring.py`: `pydantic` 适配层
- `app/runtime_policy.py`: provider 与环境开关解析
- `app/openai_judge.py`: OpenAI 运行时（阶段 Agent -> 汇总 Agent -> 终局 Agent -> 展示 Agent）
- `tests/test_scoring_core.py`: 评分核心单测（`unittest`）

## 快速启动

```bash
cd ai_judge_service
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8787
```

如果启用 `AI_JUDGE_RAG_BACKEND=milvus`，需额外安装：

```bash
.venv/bin/python -m pip install pymilvus
```

手工知识导入 Milvus（MVP 推荐）：

```bash
cd ai_judge_service
.venv/bin/python scripts/import_knowledge_to_milvus.py \
  --input-file ./knowledge.json \
  --milvus-uri http://127.0.0.1:19530 \
  --milvus-collection debate_knowledge \
  --openai-api-key "$OPENAI_API_KEY"
```

如果需要脚本自动尝试创建 collection（仅适用于你的 Milvus 配置允许该简化创建方式）：

```bash
.venv/bin/python scripts/import_knowledge_to_milvus.py \
  --input-file ./knowledge.json \
  --milvus-uri http://127.0.0.1:19530 \
  --milvus-collection debate_knowledge \
  --openai-api-key "$OPENAI_API_KEY" \
  --ensure-collection
```

## 环境变量

- `AI_JUDGE_INTERNAL_KEY`: 与 `chat_server.ai_judge.internal_key` 保持一致
- `CHAT_SERVER_BASE_URL`: 例如 `http://127.0.0.1:6688`
- `CHAT_SERVER_REPORT_PATH_TEMPLATE`: 默认 `/api/internal/ai/judge/jobs/{job_id}/report`
- `CHAT_SERVER_FAILED_PATH_TEMPLATE`: 默认 `/api/internal/ai/judge/jobs/{job_id}/failed`
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
- `AI_JUDGE_RAG_SOURCE_WHITELIST`: 允许知识来源的 URL 前缀列表（逗号/分号/换行分隔），默认 `https://teamfighttactics.leagueoflegends.com/en-us/news/`
- `AI_JUDGE_RAG_BACKEND`: `file|milvus`，默认 `file`
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
- `AI_JUDGE_GRAPH_V2_ENABLED`: DAG+Reflection v2 开关，默认 `true`
- `AI_JUDGE_REFLECTION_ENABLED`: 终局反思回路开关，默认 `true`
- `AI_JUDGE_REFLECTION_POLICY`: 反思策略，`winner_mismatch_only|winner_mismatch_or_low_margin`，默认 `winner_mismatch_only`
- `AI_JUDGE_REFLECTION_LOW_MARGIN_THRESHOLD`: 低分差保护阈值（平均分差），默认 `3`
- `AI_JUDGE_FAULT_INJECTION_NODES`: 故障注入节点（逗号分隔），可选 `stage_judge,aggregate,final_pass_1,final_pass_2,display`；生产环境禁止
- `AI_JUDGE_TOPIC_MEMORY_ENABLED`: 辩题级长期记忆开关，默认 `true`
- `AI_JUDGE_RAG_HYBRID_ENABLED`: 混合检索策略开关，默认 `true`
- `AI_JUDGE_RAG_RERANK_ENABLED`: 检索重排开关，默认 `true`
- `AI_JUDGE_DEGRADE_MAX_LEVEL`: 最大降级等级 `0..3`，默认 `3`
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

生产环境识别规则：按 `AICOMM_ENV -> APP_ENV -> PYTHON_ENV -> RUST_ENV -> ENV` 顺序读取，值为 `prod|production` 时视为生产。
生产环境门禁：
- 禁止 `AI_JUDGE_PROVIDER=mock`
- 禁止 `AI_JUDGE_OPENAI_FALLBACK_TO_MOCK=true`
- `AI_JUDGE_PROVIDER=openai` 时，`OPENAI_API_KEY` 不能为空
- 禁止配置 `AI_JUDGE_FAULT_INJECTION_NODES`

## 内部运维接口（v2）

均要求 header：`x-ai-internal-key`

- `GET /internal/judge/jobs/{job_id}/trace`：查看单任务 trace、请求快照、回调状态、回放历史
- `POST /internal/judge/jobs/{job_id}/replay`：按历史请求快照执行一次无副作用重放（不触发 callback）
- `GET /internal/judge/rag/diagnostics?job_id=...`：查看该任务检索诊断摘要

`dispatch` 的 `retrieval_profile`（默认 `hybrid_v1`）当前支持：
- `hybrid_v1`
- `hybrid_recall_v1`
- `hybrid_precision_v1`
- `lexical_fast_v1`

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

## 运行测试

依赖安装完成后执行：

```bash
cd ai_judge_service
.venv/bin/python -m unittest discover -s tests -p "test_*.py" -v
```

## RAG 评测基线（M4 phase2）

执行离线 profile 对照评测：

```bash
cd ai_judge_service
.venv/bin/python scripts/rag_eval_baseline.py \
  --dataset-file ./tests/fixtures/rag_eval_cases.json \
  --knowledge-file ./knowledge.json \
  --output-file /tmp/rag_eval_result.json
```

`dataset-file` 为 JSON 数组，每项包含：
- `request`: `JudgeDispatchRequest` 结构
- `expectedChunkIds`: 该样本期望命中的 chunk id 列表
