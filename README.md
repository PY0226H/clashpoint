# EchoIsle

在线辩论 + AI 裁判平台（MVP 阶段）。

当前仓库包含：
1. Rust 后端（聊天/辩论/支付/通知/分析）
2. Vue + Tauri 前端
3. Python AI 裁判服务（FastAPI，多 Agent + RAG）

## 目录结构

```text
echoisle/
├── chat/                    # Rust 多服务后端
├── chatapp/                 # Vue + Tauri 前端
├── ai_judge_service/        # Python AI 裁判服务
├── docs/                    # 产品计划、讲解、压测结果
├── start.sh                 # 一键启动（本地开发）
└── stop.sh                  # 一键停止（本地开发）
```

## 本地快速启动

## 1) 前置依赖

1. Node.js >= 18
2. Rust stable
3. PostgreSQL >= 14
4. Yarn
5. macOS 下建议安装 Homebrew（`start.sh` 使用 `brew services`）

## 2) 数据库配置

根目录 `.env` 示例见：
- `echoisle/.env.example`

默认本地库名是 `chat`，连接示例：
```env
DATABASE_URL=postgres://<username>:<password>@localhost:5432/chat
```

## 3) 一键启动（推荐）

```bash
./start.sh
```

脚本会自动：
1. 检查并启动 PostgreSQL（macOS）
2. 检查 `chat` 数据库
3. 执行标准迁移回放（`cargo sqlx migrate run`）
4. 启动 `chat_server`、`notify_server`、`chatapp`

启动后访问：
- `http://localhost:1420`

停止服务：
```bash
./stop.sh
```

## 可选：启动 AI 裁判服务

```bash
./scripts/pip install -r ai_judge_service/requirements.txt
cd ai_judge_service
../scripts/py -m uvicorn app.main:app --host 0.0.0.0 --port 8787
```

注意：项目内 Python 任务统一使用虚拟环境解释器，避免全局 Python 污染。

## 测试与质量门禁

Rust 全量门禁（fmt/check/clippy/nextest）：
```bash
bash skills/post-module-test-guard/scripts/run_test_gate.sh --mode full
```

AI 服务单测：
```bash
cd ai_judge_service
../scripts/py -m unittest discover -s tests -p "test_*.py" -v
```


## 服务端口

| Service | Port | 说明 |
|---|---:|---|
| chat_server | 6688 | 主业务 API |
| notify_server | 6687 | SSE / WebSocket 推送 |
| chatapp (vite) | 1420 | Web 前端 |
| ai_judge_service | 8787 | AI 裁判内部服务（可选） |
