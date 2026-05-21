#!/bin/bash
# NanoTest - macOS / Linux 停止脚本
# 停止 Backend (uvicorn) + Worker (celery) + Web (vite dev server)
# 使用方法: ./stop-all.sh

set -e

# 颜色输出
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}NanoTest - Stop All Services${NC}"
echo ""

stop_service() {
    local name="$1"
    local pattern="$2"
    local pids

    pids=$(pgrep -f "$pattern" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo -e "${YELLOW}Stopping $name ...${NC}"
        echo "$pids" | xargs kill -TERM 2>/dev/null || true
        sleep 1
        # 强制清理残留
        local residual
        residual=$(pgrep -f "$pattern" 2>/dev/null || true)
        if [ -n "$residual" ]; then
            echo -e "${YELLOW}  Force killing residual $name processes...${NC}"
            echo "$residual" | xargs kill -KILL 2>/dev/null || true
        fi
        echo -e "${GREEN}  $name stopped.${NC}"
    else
        echo -e "${GRAY}  $name not running.${NC}"
    fi
}

# 停止 Web (vite)
stop_service "Web Frontend (vite)" "vite"

# 停止 Backend (uvicorn)
stop_service "Backend (uvicorn)" "uvicorn app.main:app"

# 停止 Celery Worker
stop_service "Celery Worker" "celery.*worker"

echo ""
echo -e "${GREEN}✅ 所有服务已停止。${NC}"
echo ""
