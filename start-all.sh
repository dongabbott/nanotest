#!/bin/bash
# NanoTest - macOS / Linux 启动脚本
# 同时启动 Backend (uvicorn) + Worker (celery) + Web (vite)
# 使用方法: ./start-all.sh

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

# 检测 shell 类型，用于在新 Terminal 窗口中加载环境（nvm/pyenv 等）
SHELL_RC=""
if [ -n "$ZSH_VERSION" ] || [ "$(basename "$SHELL")" = "zsh" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ] || [ "$(basename "$SHELL")" = "bash" ]; then
    SHELL_RC="$HOME/.bash_profile"
    [ -f "$HOME/.bashrc" ] && SHELL_RC="$HOME/.bashrc"
fi

# 构建在新 Terminal 窗口中预执行的 shell 初始化命令
INIT_SHELL=""
if [ -n "$SHELL_RC" ] && [ -f "$SHELL_RC" ]; then
    INIT_SHELL="source \"$SHELL_RC\" && "
fi

# 颜色输出
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
GRAY='\033[0;90m'
NC='\033[0m'

echo -e "${CYAN}NanoTest - Dev Launcher (macOS/Linux)${NC}"
echo ""

# 检查 Redis
if ! redis-cli ping > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Redis 未运行。请先启动 Redis:${NC}"
    echo "    brew services start redis"
    echo "    或: redis-server"
    echo ""
    read -p "按回车继续，或 Ctrl+C 退出..."
    echo ""
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

# ============================================================
# 启动 Backend
# ============================================================
echo -e "${CYAN}🚀 启动 Backend...${NC}"
osascript <<EOF
tell application "Terminal"
    do script "${INIT_SHELL}cd \"$PROJECT_ROOT/apps/backend\" && source .venv/bin/activate && echo '=== Running migrations ===' && alembic upgrade head && echo '=== Starting uvicorn ===' && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app"
    set custom title of front window to "NanoTest Backend"
end tell
EOF

# ============================================================
# 启动 Worker
# ============================================================
echo -e "${CYAN}🚀 启动 Worker...${NC}"
osascript <<EOF
tell application "Terminal"
    do script "${INIT_SHELL}cd \"$PROJECT_ROOT/apps/backend\" && source .venv/bin/activate && celery -A app.tasks.celery_app worker --loglevel=info"
    set custom title of front window to "NanoTest Worker"
end tell
EOF

# ============================================================
# 启动 Web Frontend
# ============================================================
echo -e "${CYAN}🚀 启动 Web Frontend...${NC}"
osascript <<EOF
tell application "Terminal"
    do script "${INIT_SHELL}cd \"$PROJECT_ROOT/apps/web\" && npm run dev"
    set custom title of front window to "NanoTest Web"
end tell
EOF

# ============================================================
echo ""
echo -e "${GREEN}✅ 已启动所有服务。${NC}"
echo ""
echo -e "${GRAY}  Backend API:  http://localhost:8000${NC}"
echo -e "${GRAY}  Web Frontend: http://localhost:5173${NC}"
echo -e "${GRAY}  API Docs:     http://localhost:8000/docs${NC}"
echo ""
echo -e "${YELLOW}提示: 关闭对应的 Terminal 窗口即可停止服务。${NC}"
echo -e "      或使用 ./stop-all.sh 一键停止所有服务。"
echo ""
