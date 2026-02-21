#!/bin/bash

# AiComm 应用关闭脚本
# 使用方法: ./stop.sh

echo "=========================================="
echo "  AiComm 应用关闭脚本"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 关闭函数
stop_service() {
    local service_name=$1
    local port=$2
    local pid_file=$3

    echo "关闭 $service_name (端口 $port)..."

    # 方法1: 使用 PID 文件
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if kill -0 $pid 2>/dev/null; then
            kill $pid 2>/dev/null
            sleep 1
            # 如果进程还在运行，强制关闭
            if kill -0 $pid 2>/dev/null; then
                kill -9 $pid 2>/dev/null
            fi
            echo -e "${GREEN}✓${NC} $service_name 已关闭 (PID: $pid)"
        else
            echo -e "${YELLOW}!${NC} $service_name 未运行"
        fi
        rm -f "$pid_file"
    else
        # 方法2: 使用端口查找
        if lsof -ti:$port >/dev/null 2>&1; then
            lsof -ti:$port | xargs kill -9 2>/dev/null
            echo -e "${GREEN}✓${NC} $service_name 已关闭"
        else
            echo -e "${YELLOW}!${NC} $service_name 未运行"
        fi
    fi
}

# 关闭各个服务
stop_service "chat_server" "6688" "/tmp/aicomm_logs/chat_server.pid"
stop_service "notify_server" "6687" "/tmp/aicomm_logs/notify_server.pid"
stop_service "前端应用" "1420" "/tmp/aicomm_logs/chatapp.pid"

# 额外清理：使用进程名关闭（备用）
echo ""
echo "执行额外清理..."
pkill -f chat-server 2>/dev/null && echo -e "${GREEN}✓${NC} 清理 chat-server 进程" || true
pkill -f notify-server 2>/dev/null && echo -e "${GREEN}✓${NC} 清理 notify-server 进程" || true
pkill -f "vite.*chatapp" 2>/dev/null && echo -e "${GREEN}✓${NC} 清理 vite 进程" || true

# 验证所有服务已关闭
echo ""
echo "验证服务状态..."
if lsof -i :6688 -i :6687 -i :1420 2>/dev/null | grep -q LISTEN; then
    echo -e "${RED}✗${NC} 仍有服务在运行，请手动检查"
    lsof -i :6688 -i :6687 -i :1420 | grep LISTEN
else
    echo -e "${GREEN}✓${NC} 所有服务已关闭"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}关闭完成！${NC}"
echo "=========================================="
echo ""
echo "提示: 日志文件保留在 /tmp/aicomm_logs/ 目录"
echo "      如需清理日志: rm -rf /tmp/aicomm_logs/"
echo ""
