# EchoIsle

在线辩论 + AI 裁判平台（MVP 阶段）。

EchoIsle 面向“辩论结束后给出可信、可读、可复盘结论”的产品场景，当前仓库包含完整的后端、前端与 AI 裁判链路。

## 当前状态

- 项目处于持续开发阶段，尚未正式发布到生产环境。
- 主线功能覆盖：账号登录、辩论大厅/房间、判决报告、平局投票、钱包与运营观测。
- 默认开发形态为本地联调，支持按模块单独启动。

## 核心能力

- 多端入口：Web + Desktop（Tauri）共用一套 React + TypeScript 业务层。
- 后端业务：Rust 服务提供鉴权、辩论流程、钱包、运营接口与内部 AI 回写接口。
- 实时通道：`notify_server` 提供 SSE / WebSocket 实时通知与回放窗口。
- AI 裁判：FastAPI 服务承接 phase/final dispatch，支持 RAG、重放、审计告警与回调。
- 质量门禁：包含仓库级测试门禁脚本与 CI workflow（格式、编译、lint、测试等）。

## 技术栈

- Backend: Rust, Axum, SQLx, PostgreSQL, Redis/Kafka（可选）
- Frontend: React 18, TypeScript, Vite, pnpm workspace, Playwright
- AI Service: Python, FastAPI, Uvicorn, BM25 / Milvus（可选）

## 仓库结构

```text
EchoIsle/
├── chat/                 # Rust 后端工作区（chat/notify/analytics/...）
├── frontend/             # 前端 monorepo（web/desktop/packages）
├── ai_judge_service/     # Python AI 裁判服务
├── docs/                 # 架构、计划、验证与说明文档
├── scripts/              # 仓库级脚本（含 Python 包装器、harness）
├── start.sh              # 一键启动（偏本地开发）
└── stop.sh               # 一键停止（偏本地开发）
```

## 快速开始（开发环境）

### 1) 前置依赖

- Node.js 18+
- pnpm
- Rust stable toolchain
- PostgreSQL 14+
- Python 3.11+（仅在启用 AI 裁判服务时必需）

### 2) 基础配置

1. 复制环境变量模板并填写数据库连接：

```bash
cp .env.example .env
```

2. 确认后端配置中的数据库连接可用：

- `chat/chat_server/chat.yml`
- `chat/notify_server/notify.yml`

### 3) 安装依赖

```bash
cd frontend
pnpm install --no-frozen-lockfile
cd ..
```

### 4) 执行数据库迁移

```bash
cd chat
cargo sqlx migrate run
cd ..
```

### 5) 启动服务

方式 A（一键启动，适合本地开发）：

```bash
./start.sh
```

方式 B（手动启动）：

```bash
# Terminal 1
cd chat/chat_server
cargo run

# Terminal 2
cd chat/notify_server
cargo run

# Terminal 3
cd frontend
pnpm dev:web
```

Desktop 壳调试（可选）：

```bash
cd frontend
pnpm dev:desktop:tauri
```

访问地址：

- `http://localhost:1420`（使用 `start.sh`）
- `http://localhost:5173`（手动 `pnpm dev:web` 默认端口）

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

常用环境变量：

- `AI_JUDGE_INTERNAL_KEY`（需与 `chat_server` 配置保持一致）
- `CHAT_SERVER_BASE_URL`
- `AI_JUDGE_PROVIDER`（`mock` 或 `openai`）
- `OPENAI_API_KEY`（当 provider 为 `openai` 时需要）

## 常用测试命令

仓库级 Rust 门禁（fmt/check/clippy/nextest）：

```bash
bash skills/post-module-test-guard/scripts/run_test_gate.sh --mode full
```

前端检查与测试：

```bash
cd frontend
pnpm typecheck
pnpm lint
pnpm test
pnpm e2e:smoke:web
```

AI 裁判服务测试：

```bash
cd ai_judge_service
../scripts/py -m unittest discover -s tests -p "test_*.py" -v
```

## 服务端口（默认）

| Service | Port | 说明 |
|---|---:|---|
| `chat_server` | 6688 | 主业务 API |
| `notify_server` | 6687 | SSE / WebSocket 通知 |
| `frontend web` | 5173 / 1420 | Vite 默认 / 一键脚本 |
| `ai_judge_service` | 8787 | AI 裁判服务（可选） |

## API 文档入口（chat_server）

- `http://localhost:6688/swagger-ui`
- `http://localhost:6688/redoc`
- `http://localhost:6688/rapidoc`

## 文档导航

- [架构代码地图](docs/architecture/README.md)
- [Harness 规则总览](docs/harness/00-overview.md)
- [开发计划入口](docs/dev_plan/active/README.md)
