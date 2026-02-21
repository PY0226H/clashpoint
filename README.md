# aicomm

A modern, real-time chat application built with Vue.js and Tauri.

## Features

- Real-time messaging
- User-friendly interface
- work across web and desktop
- Lightweight and fast performance

## Prerequisites

Before you begin, ensure you have met the following requirements:

- Node.js (v18 or later)
- Rust (latest stable version)
- Tauri CLI

## Setup

1. Clone the repository:
   ```
   git clone https://github.com/tyr-rust-bootcamp/aicomm.git
   cd aicomm
   ```

2. Install dependencies:
   ```
   cd chatapp
   yarn
   ```


## Quick Start

### 使用自动化脚本（推荐）

**启动所有服务：**
```bash
./start.sh
```

**关闭所有服务：**
```bash
./stop.sh
```

**访问应用：**
打开浏览器访问 http://localhost:1420/

### 手动启动

**详细的启动和配置说明，请参考：[START_GUIDE.md](START_GUIDE.md)**

First, run the server:
```bash
cd chat/chat_server
cargo run

cd chat/notify_server
cargo run
```

To run the desktop app, you could use:
```bash
cd chatapp
cargo tauri dev
```

To run the web app, you could use:
```bash
cd chatapp
yarn dev
```

## Documentation

- **[START_GUIDE.md](START_GUIDE.md)** - 完整的启动、配置和故障排除指南
- **[start.sh](start.sh)** - 自动启动脚本
- **[stop.sh](stop.sh)** - 自动关闭脚本

## Service Ports

| Service | Port | Description |
|---------|------|-------------|
| chat_server | 6688 | 聊天服务器 |
| notify_server | 6687 | 通知服务器 |
| Frontend (Web) | 1420 | Web 前端应用 |
