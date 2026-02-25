# NanoTest 项目 Agent 配置

本文件用于记录项目的基本配置信息，供 AI Agent 使用。

## 后端 (Backend)

- **路径**: `apps/backend`
- **语言**: Python 3.13
- **虚拟环境路径**: `d:\project\nanotest\apps\backend\.venv`
- **Python 解释器**: `d:\project\nanotest\apps\backend\.venv\Scripts\python.exe`
- **激活虚拟环境**: `d:\project\nanotest\apps\backend\.venv\Scripts\activate`
- **依赖文件**: `apps/backend/requirements.txt`
- **数据库**: SQLite (`nanotest.db`) / PostgreSQL (生产环境)

### 常用命令

```bash
# 激活虚拟环境
d:\project\nanotest\apps\backend\.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行测试
pytest tests/ -v

# 运行登录接口测试
pytest tests/test_auth.py -v

# 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 前端 (Web)

- **路径**: `apps/web`
- **框架**: React + TypeScript + Vite
- **包管理器**: npm / pnpm

### 常用命令

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

## Worker

- **路径**: `apps/worker`
- **用途**: Celery 异步任务执行器

## Packages

- `packages/ai-adapter-sdk` - AI 适配器 SDK
- `packages/dsl-engine` - DSL 引擎
- `packages/flow-compiler` - 流程编译器
- `packages/shared-types` - 共享类型定义
