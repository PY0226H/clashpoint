# EchoIsle 应用启动和关闭指南

## 目录
- [系统要求](#系统要求)
- [环境准备](#环境准备)
- [启动流程](#启动流程)
- [关闭流程](#关闭流程)
- [常见问题](#常见问题)
- [服务端口说明](#服务端口说明)

---

## 系统要求

在启动应用之前，请确保你的系统满足以下要求：

- **Node.js**: v18 或更高版本
- **Rust**: 最新稳定版本
- **PostgreSQL**: 14 或更高版本
- **pnpm**: 包管理器
- **Cargo**: Rust 构建工具（随 Rust 一起安装）
- **sqlx-cli**: 数据库迁移工具（推荐安装，`start.sh` 默认会执行迁移回放）

### 安装系统依赖

```bash
# macOS (使用 Homebrew)
brew install postgresql@14
brew install node
brew install pnpm
brew install rust

# 启动 PostgreSQL
brew services start postgresql@14

# 安装 sqlx-cli (推荐)
cargo install sqlx-cli --no-default-features --features postgres
```

---

## 环境准备

### 1. 配置数据库

#### 1.1 创建数据库

```bash
# 连接到 PostgreSQL
psql postgres

# 在 psql 中创建数据库
CREATE DATABASE chat;
\q
```

#### 1.2 配置数据库连接

需要更新以下文件中的数据库连接信息：

**文件 1: `.env`**
```bash
DATABASE_URL=postgres://你的用户名@localhost/chat
```

**文件 2: `chat/.env`**
```bash
DATABASE_URL=postgres://你的用户名@localhost/chat
```

**文件 3: `chat/chat_server/chat.yml`**
```yaml
server:
  port: 6688
  db_url: postgres://你的用户名@localhost:5432/chat
  base_dir: /tmp/chat_server
```

**文件 4: `chat/notify_server/notify.yml`**
```yaml
server:
  port: 6687
  db_url: postgres://你的用户名@localhost:5432/chat
```

> **注意**: 将 `你的用户名` 替换为你的系统用户名（使用 `whoami` 命令查看）

### 2. 安装依赖

#### 2.1 安装前端依赖

```bash
cd frontend
pnpm install --no-frozen-lockfile
cd ..
```

#### 2.2 编译 Rust 项目（可选，首次运行时会自动编译）

```bash
cd chat
cargo build
cd ..
```

### 3. 运行数据库迁移（如果需要）

如果是首次运行或数据库表结构需要更新：

```bash
cd chat
cargo sqlx migrate run
cd ..
```

> **注意**: `start.sh` 会默认执行这一步；若你手动启动服务，请先确保迁移已回放

---

## 启动流程

### 方式一：手动启动各个服务（推荐用于开发）

#### 步骤 1: 启动 PostgreSQL 数据库

```bash
# 检查 PostgreSQL 是否运行
brew services list | grep postgresql

# 如果未运行，启动它
brew services start postgresql@14
```

#### 步骤 2: 启动 Chat Server（聊天服务）

打开第一个终端窗口：

```bash
cd chat/chat_server
cargo run
```

等待编译完成，你应该看到：
```
INFO chat_server: Listening on: 0.0.0.0:6688
```

#### 步骤 3: 启动 Notify Server（通知服务）

打开第二个终端窗口：

```bash
cd chat/notify_server
cargo run
```

等待编译完成，你应该看到：
```
INFO notify_server: Listening on: 0.0.0.0:6687
```

#### 步骤 4: 启动前端应用

打开第三个终端窗口：

```bash
cd frontend
pnpm --filter @echoisle/web dev -- --host 127.0.0.1 --port 1420
```

你应该看到：
```
VITE v5.4.1  ready in 522 ms
➜  Local:   http://localhost:1420/
```

#### 步骤 5: 访问应用

打开浏览器，访问：
```
http://localhost:1420/
```

### 方式二：使用后台进程启动

如果你想在后台运行服务：

```bash
# 启动 chat_server
cd chat/chat_server
nohup cargo run > /tmp/chat_server.log 2>&1 &
echo $! > /tmp/chat_server.pid

# 启动 notify_server
cd ../notify_server
nohup cargo run > /tmp/notify_server.log 2>&1 &
echo $! > /tmp/notify_server.pid

# 启动前端
cd ../../frontend
nohup pnpm --filter @echoisle/web dev -- --host 127.0.0.1 --port 1420 > /tmp/frontend-web.log 2>&1 &
echo $! > /tmp/frontend-web.pid
```

查看日志：
```bash
tail -f /tmp/chat_server.log
tail -f /tmp/notify_server.log
tail -f /tmp/frontend-web.log
```

### 方式三：使用 Docker（如果配置了）

```bash
# 构建 Docker 镜像
make build-docker

# 运行 Docker 容器
make run-docker
```

---

## 关闭流程

### 方式一：关闭手动启动的服务

如果服务运行在前台（终端窗口）：

1. 在每个运行服务的终端窗口中按 `Ctrl + C`
2. 按顺序关闭：
   - 前端应用（frontend web）
   - Notify Server
   - Chat Server

### 方式二：关闭后台进程

#### 使用 PID 文件关闭

```bash
# 关闭 chat_server
if [ -f /tmp/chat_server.pid ]; then
    kill $(cat /tmp/chat_server.pid)
    rm /tmp/chat_server.pid
fi

# 关闭 notify_server
if [ -f /tmp/notify_server.pid ]; then
    kill $(cat /tmp/notify_server.pid)
    rm /tmp/notify_server.pid
fi

# 关闭前端
if [ -f /tmp/frontend-web.pid ]; then
    kill $(cat /tmp/frontend-web.pid)
    rm /tmp/frontend-web.pid
fi
```

#### 使用端口查找并关闭

```bash
# 查找并关闭占用 6688 端口的进程（chat_server）
lsof -ti:6688 | xargs kill -9

# 查找并关闭占用 6687 端口的进程（notify_server）
lsof -ti:6687 | xargs kill -9

# 查找并关闭占用 1420 端口的进程（前端）
lsof -ti:1420 | xargs kill -9
```

#### 使用进程名关闭

```bash
# 关闭所有相关进程
pkill -f chat-server
pkill -f notify-server
pkill -f "pnpm --filter @echoisle/web dev"
```

### 方式三：关闭 Docker 容器

```bash
# 停止所有容器
make kill-dockers

# 或者手动停止
docker stop chat notify bot analytics
docker rm chat notify bot analytics
```

### 完整关闭脚本

创建一个关闭脚本 `stop.sh`：

```bash
#!/bin/bash

echo "正在关闭 EchoIsle 应用..."

# 方法1: 使用端口关闭
echo "关闭 chat_server (端口 6688)..."
lsof -ti:6688 | xargs kill -9 2>/dev/null && echo "  ✓ chat_server 已关闭" || echo "  ✗ chat_server 未运行"

echo "关闭 notify_server (端口 6687)..."
lsof -ti:6687 | xargs kill -9 2>/dev/null && echo "  ✓ notify_server 已关闭" || echo "  ✗ notify_server 未运行"

echo "关闭前端应用 (端口 1420)..."
lsof -ti:1420 | xargs kill -9 2>/dev/null && echo "  ✓ 前端应用已关闭" || echo "  ✗ 前端应用未运行"

# 方法2: 使用进程名关闭（备用）
pkill -f chat-server 2>/dev/null
pkill -f notify-server 2>/dev/null
pkill -f "pnpm --filter @echoisle/web dev" 2>/dev/null

echo "所有服务已关闭！"
```

使用方法：
```bash
chmod +x stop.sh
./stop.sh
```

---

## 常见问题

### 1. 数据库连接失败

**错误信息**: `role "postgres" does not exist`

**解决方案**: 更新配置文件中的数据库用户名为你的系统用户名

### 2. 端口已被占用

**错误信息**: `Address already in use`

**解决方案**:
```bash
# 查看占用端口的进程
lsof -i :6688
lsof -i :6687
lsof -i :1420

# 关闭占用端口的进程
kill -9 <PID>
```

### 3. 编译错误

**错误信息**: `could not compile...`

**解决方案**:
```bash
# 清理并重新构建
cd chat
cargo clean
cargo build
```

### 4. 前端依赖安装失败

**解决方案**:
```bash
cd frontend
rm -rf node_modules
rm pnpm-lock.yaml
pnpm install --no-frozen-lockfile
```

### 5. 数据库迁移冲突

**错误信息**: `migration was previously applied but is missing`

**解决方案**: 数据库表已存在，无需运行迁移。如果需要重置：
```bash
# 备份数据（如果需要）
pg_dump chat > backup.sql

# 删除并重建数据库
psql postgres -c "DROP DATABASE chat;"
psql postgres -c "CREATE DATABASE chat;"

# 重新运行迁移
cd chat
cargo sqlx migrate run
```

### 6. 检查服务状态

```bash
# 检查所有服务是否运行
lsof -i :6688 -i :6687 -i :1420 | grep LISTEN

# 检查 PostgreSQL 状态
brew services list | grep postgresql

# 测试 API 端点
curl http://localhost:6688/health
curl http://localhost:6687/health
```

---

## 服务端口说明

| 服务 | 端口 | 说明 |
|------|------|------|
| **chat_server** | 6688 | 聊天服务器，处理消息发送、接收等核心功能 |
| **notify_server** | 6687 | 通知服务器，处理实时通知和 WebSocket 连接 |
| **frontend web (Vite)** | 1420 | Web 前端应用，用户界面 |
| **PostgreSQL** | 5432 | 数据库服务（默认端口） |

---

## 快速启动检查清单

启动应用前，请确认：

- [ ] PostgreSQL 正在运行
- [ ] 数据库 `chat` 已创建
- [ ] 所有配置文件中的数据库连接信息已更新
- [ ] frontend 的依赖已安装（node_modules 存在）
- [ ] 端口 6688、6687、1420 未被占用

---

## 开发提示

### 热重载

- **前端**: Vite 提供自动热重载，修改代码后自动刷新
- **后端**: 需要手动重启服务，或使用 `cargo-watch`:
  ```bash
  cargo install cargo-watch
  cargo watch -x run
  ```

### 日志级别

修改日志级别，在启动命令前添加环境变量：
```bash
RUST_LOG=debug cargo run
```

### 数据库管理工具

推荐使用以下工具管理数据库：
- **psql**: 命令行工具
- **pgAdmin**: GUI 工具
- **DBeaver**: 跨平台数据库管理工具

---

## 联系和支持

- **GitHub**: https://github.com/PY0226H/EchoIsle
- **问题反馈**: 在 GitHub Issues 中提交问题

---

**最后更新**: 2026-02-11
