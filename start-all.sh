#!/bin/bash
# NanoTest - macOS / Linux 启动脚本
# 同时启动 Backend (uvicorn) + Worker (celery) + Web (vite)
# 使用方法:
#   ./start-all.sh           # 本地开发：用 Terminal.app 打开新窗口
#   ./start-all.sh --headless # 后台运行（适合 SSH / CI）

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

HEADLESS=false
for arg in "$@"; do
    if [ "$arg" = "--headless" ]; then
        HEADLESS=true
    fi
done

# 检测是否在交互式终端
IS_INTERACTIVE=false
[ -t 0 ] && IS_INTERACTIVE=true

# 检测当前登录 shell（用于 headless 模式加载 nvm/pyenv）
LOGIN_SHELL="${SHELL:-/bin/zsh}"

# 检测 shell 类型，用于在新 Terminal 窗口中加载环境（nvm/pyenv 等）
SHELL_RC=""
if [ -n "$ZSH_VERSION" ] || [ "$(basename "$SHELL")" = "zsh" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ] || [ "$(basename "$SHELL")" = "bash" ]; then
    SHELL_RC="$HOME/.bash_profile"
    [ -f "$HOME/.bashrc" ] && SHELL_RC="$HOME/.bashrc"
fi

# 构建环境初始化命令
INIT_SHELL=""
if [ -n "$SHELL_RC" ] && [ -f "$SHELL_RC" ]; then
    INIT_SHELL="source \"$SHELL_RC\" && "
fi

# 颜色输出
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GRAY='\033[0;90m'
NC='\033[0m'

echo -e "${CYAN}NanoTest - Dev Launcher (macOS/Linux)${NC}"
if [ "$HEADLESS" = "true" ]; then
    echo -e "${GRAY}Mode: headless (background)${NC}"
fi
echo ""

# 检查 Redis（兼容没有 redis-cli 的环境）
REDIS_OK=false
if command -v redis-cli >/dev/null 2>&1; then
    redis-cli ping >/dev/null 2>&1 && REDIS_OK=true
elif command -v nc >/dev/null 2>&1; then
    nc -z localhost 6379 >/dev/null 2>&1 && REDIS_OK=true
fi

if [ "$REDIS_OK" != "true" ]; then
    echo -e "${YELLOW}⚠️  Redis 未运行。请先启动 Redis:${NC}"
    echo "    brew services start redis"
    echo "    或: redis-server"
    echo ""
    if [ "$IS_INTERACTIVE" = "true" ]; then
        read -p "按回车继续，或 Ctrl+C 退出..."
    else
        echo -e "${RED}非交互式环境，自动退出。请先启动 Redis。${NC}"
        exit 1
    fi
    echo ""
fi

# 检查端口占用
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  端口 8000 已被占用。请先运行 ./stop-all.sh 停止残留进程。${NC}"
    exit 1
fi

# 检查后端虚拟环境
if [ ! -f "$PROJECT_ROOT/apps/backend/.venv/bin/activate" ]; then
    echo -e "${YELLOW}⚠️  未找到后端虚拟环境: apps/backend/.venv/bin/activate${NC}"
    echo "    请先创建虚拟环境并安装依赖:"
    echo "    cd apps/backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# 检查前端依赖
if [ ! -d "$PROJECT_ROOT/apps/web/node_modules" ]; then
    echo -e "${YELLOW}⚠️  前端依赖未安装。${NC}"
    echo "    请先执行: cd apps/web && npm install"
    exit 1
fi

# 准备日志目录
mkdir -p "$PROJECT_ROOT/logs"

# 生成带时间戳的日志文件名
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
LOG_BACKEND="$PROJECT_ROOT/logs/backend-${TIMESTAMP}.log"
LOG_WORKER="$PROJECT_ROOT/logs/worker-${TIMESTAMP}.log"
LOG_WEB="$PROJECT_ROOT/logs/web-${TIMESTAMP}.log"

# 更新 latest 软链接
ln -sf "backend-${TIMESTAMP}.log" "$PROJECT_ROOT/logs/backend.log"
ln -sf "worker-${TIMESTAMP}.log" "$PROJECT_ROOT/logs/worker.log"
ln -sf "web-${TIMESTAMP}.log" "$PROJECT_ROOT/logs/web.log"

# ============================================================
# 启动函数
# ============================================================
start_backend() {
    local cmd="cd \"$PROJECT_ROOT/apps/backend\" && source .venv/bin/activate && echo '=== Running migrations ===' && alembic upgrade head && echo '=== Starting uvicorn ===' && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app"
    if [ "$HEADLESS" = "true" ]; then
        nohup "$LOGIN_SHELL" -lic "$cmd" > "$LOG_BACKEND" 2>&1 &
        echo $! > "$PROJECT_ROOT/logs/backend.pid"
        echo -e "${GREEN}  Backend PID: $!${NC}"
        echo -e "${GRAY}  Log: $LOG_BACKEND${NC}"
    else
        osascript <<EOF
tell application "Terminal"
    activate
    do script "${INIT_SHELL}$cmd 2>&1 | tee -a \"$LOG_BACKEND\""
    set name of front window to "NanoTest Backend"
end tell
EOF
        echo -e "${GRAY}  Log: $LOG_BACKEND${NC}"
    fi
}

start_worker() {
    local cmd="cd \"$PROJECT_ROOT/apps/backend\" && source .venv/bin/activate && celery -A app.tasks.celery_app worker --loglevel=info"
    if [ "$HEADLESS" = "true" ]; then
        nohup "$LOGIN_SHELL" -lic "$cmd" > "$LOG_WORKER" 2>&1 &
        echo $! > "$PROJECT_ROOT/logs/worker.pid"
        echo -e "${GREEN}  Worker PID: $!${NC}"
        echo -e "${GRAY}  Log: $LOG_WORKER${NC}"
    else
        osascript <<EOF
tell application "Terminal"
    activate
    do script "${INIT_SHELL}$cmd 2>&1 | tee -a \"$LOG_WORKER\""
    set name of front window to "NanoTest Worker"
end tell
EOF
        echo -e "${GRAY}  Log: $LOG_WORKER${NC}"
    fi
}

start_web() {
    local cmd="cd \"$PROJECT_ROOT/apps/web\" && npm run dev"
    if [ "$HEADLESS" = "true" ]; then
        nohup "$LOGIN_SHELL" -lic "$cmd" > "$LOG_WEB" 2>&1 &
        echo $! > "$PROJECT_ROOT/logs/web.pid"
        echo -e "${GREEN}  Web PID: $!${NC}"
        echo -e "${GRAY}  Log: $LOG_WEB${NC}"
    else
        osascript <<EOF
tell application "Terminal"
    activate
    do script "${INIT_SHELL}$cmd 2>&1 | tee -a \"$LOG_WEB\""
    set name of front window to "NanoTest Web"
end tell
EOF
        echo -e "${GRAY}  Log: $LOG_WEB${NC}"
    fi
}

# ============================================================
# 启动所有服务
# ============================================================
echo -e "${CYAN}🚀 启动 Backend...${NC}"
start_backend

echo -e "${CYAN}🚀 启动 Worker...${NC}"
start_worker

echo -e "${CYAN}🚀 启动 Web Frontend...${NC}"
start_web

# ============================================================
echo ""
echo -e "${GREEN}✅ 已启动所有服务。${NC}"
echo ""
echo -e "${GRAY}  Backend API:  http://localhost:8000${NC}"
echo -e "${GRAY}  Web Frontend: http://localhost:5173${NC}"
echo -e "${GRAY}  API Docs:     http://localhost:8000/docs${NC}"
echo -e "${GRAY}  Logs:         $PROJECT_ROOT/logs/${NC}"
echo -e "${GRAY}  Latest:       backend.log / worker.log / web.log${NC}"
if [ "$HEADLESS" = "true" ]; then
    echo -e "${GRAY}  PIDs:         $PROJECT_ROOT/logs/*.pid${NC}"
fi
echo ""
echo -e "${YELLOW}提示: 关闭对应的 Terminal 窗口即可停止服务。${NC}"
echo -e "      或使用 ./stop-all.sh 一键停止所有服务。"
echo ""
