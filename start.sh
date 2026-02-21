#!/bin/bash

# AiComm 应用启动脚本
# 使用方法: ./start.sh

set -e

echo "=========================================="
echo "  AiComm 应用启动脚本"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查 PostgreSQL
echo "1. 检查 PostgreSQL 数据库..."
if brew services list | grep -q "postgresql.*started"; then
    echo -e "${GREEN}✓${NC} PostgreSQL 正在运行"
else
    echo -e "${YELLOW}!${NC} PostgreSQL 未运行，正在启动..."
    brew services start postgresql@14
    sleep 2
fi

# 检查数据库是否存在
echo ""
echo "2. 检查数据库..."
if psql -lqt | cut -d \| -f 1 | grep -qw chat; then
    echo -e "${GREEN}✓${NC} 数据库 'chat' 已存在"
else
    echo -e "${YELLOW}!${NC} 数据库 'chat' 不存在，正在创建..."
    createdb chat
    echo -e "${GREEN}✓${NC} 数据库创建完成"
fi

# 检查端口占用
echo ""
echo "3. 检查端口占用..."
if lsof -Pi :6688 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}✗${NC} 端口 6688 已被占用"
    echo "   使用 './stop.sh' 关闭现有服务，或手动关闭占用端口的进程"
    exit 1
fi
if lsof -Pi :6687 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}✗${NC} 端口 6687 已被占用"
    echo "   使用 './stop.sh' 关闭现有服务，或手动关闭占用端口的进程"
    exit 1
fi
if lsof -Pi :1420 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}✗${NC} 端口 1420 已被占用"
    echo "   使用 './stop.sh' 关闭现有服务，或手动关闭占用端口的进程"
    exit 1
fi
echo -e "${GREEN}✓${NC} 所有端口可用 (6688, 6687, 1420)"

# 检查前端依赖
echo ""
echo "4. 检查前端依赖..."
if [ ! -d "chatapp/node_modules" ]; then
    echo -e "${YELLOW}!${NC} node_modules 不存在，正在安装..."
    cd chatapp
    yarn install
    cd ..
    echo -e "${GREEN}✓${NC} 依赖安装完成"
else
    echo -e "${GREEN}✓${NC} 前端依赖已安装"
fi

# 创建日志目录
mkdir -p /tmp/aicomm_logs

echo ""
echo "5. 启动服务..."

# 启动 chat_server
echo "   启动 chat_server (端口 6688)..."
cd chat/chat_server
nohup cargo run > /tmp/aicomm_logs/chat_server.log 2>&1 &
CHAT_PID=$!
echo $CHAT_PID > /tmp/aicomm_logs/chat_server.pid
cd ../..

# 启动 notify_server
echo "   启动 notify_server (端口 6687)..."
cd chat/notify_server
nohup cargo run > /tmp/aicomm_logs/notify_server.log 2>&1 &
NOTIFY_PID=$!
echo $NOTIFY_PID > /tmp/aicomm_logs/notify_server.pid
cd ../..

# 启动前端
echo "   启动前端应用 (端口 1420)..."
cd chatapp
nohup yarn dev > /tmp/aicomm_logs/chatapp.log 2>&1 &
APP_PID=$!
echo $APP_PID > /tmp/aicomm_logs/chatapp.pid
cd ..

echo ""
echo "6. 等待服务启动..."
sleep 5

# 检查服务是否启动成功
echo ""
echo "7. 检查服务状态..."

# 检查 chat_server
if lsof -Pi :6688 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} chat_server 运行中 (PID: $CHAT_PID, 端口: 6688)"
else
    echo -e "${RED}✗${NC} chat_server 启动失败，查看日志: tail -f /tmp/aicomm_logs/chat_server.log"
fi

# 检查 notify_server
if lsof -Pi :6687 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} notify_server 运行中 (PID: $NOTIFY_PID, 端口: 6687)"
else
    echo -e "${RED}✗${NC} notify_server 启动失败，查看日志: tail -f /tmp/aicomm_logs/notify_server.log"
fi

# 检查前端
sleep 3
if lsof -Pi :1420 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} 前端应用运行中 (PID: $APP_PID, 端口: 1420)"
else
    echo -e "${RED}✗${NC} 前端应用启动失败，查看日志: tail -f /tmp/aicomm_logs/chatapp.log"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}应用启动完成！${NC}"
echo "=========================================="
echo ""
echo "访问地址: http://localhost:1420/"
echo ""
echo "日志文件位置:"
echo "  - Chat Server:   /tmp/aicomm_logs/chat_server.log"
echo "  - Notify Server: /tmp/aicomm_logs/notify_server.log"
echo "  - Frontend:      /tmp/aicomm_logs/chatapp.log"
echo ""
echo "查看日志: tail -f /tmp/aicomm_logs/chat_server.log"
echo "关闭服务: ./stop.sh"
echo ""
