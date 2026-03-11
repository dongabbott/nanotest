# NanoTest 使用手册

## 目录

1. [系统概述](#1-系统概述)
2. [环境要求](#2-环境要求)
3. [系统安装与启动](#3-系统安装与启动)
4. [功能模块](#4-功能模块)
5. [常规使用流程](#5-常规使用流程)
6. [API 接口说明](#6-api-接口说明)
7. [配置说明](#7-配置说明)
8. [故障排除](#8-故障排除)

---

## 1. 系统概述

NanoTest 是一个 AI 驱动的移动端自动化测试管理平台，提供以下核心功能：

- **测试用例 DSL 定义**：使用声明式 DSL 语法定义测试用例
- **可视化流程编排**：通过拖拽式 DAG 编辑器设计测试流程
- **AI 智能分析**：支持火山引擎豆包（Doubao）和阿里千问（Qwen），自动截图分析和异常检测
- **需求管理与语义检索**：支持项目级需求管理、验收标准维护、Embedding 检索与需求关联
- **多平台支持**：支持 iOS 和 Android 测试（通过 Appium）
- **应用包管理**：APK/IPA 上传、解析、安装到设备
- **设备与 Session 管理**：本地设备扫描、远程 Appium 服务器、基于包创建 Session
- **风险评分**：AI 计算测试运行风险分数
- **运行对比**：测试运行之间的差异对比
- **实时通知**：WebSocket 推送运行状态更新
- **多租户支持**：租户隔离和 RBAC 权限控制

### 1.1 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     前端 (React + Vite)                      │
│           TailwindCSS + ReactFlow + Monaco Editor           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   后端 API (FastAPI)                         │
│           REST API + WebSocket + JWT 认证                   │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ SQLite / PG   │    │     Redis     │    │  Aliyun OSS   │
│   (数据库)     │    │ (缓存/Session │    │   (存储)      │
│               │    │  /Celery队列)  │    │               │
└───────────────┘    └───────────────┘    └───────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Celery Workers                            │
│              执行队列 │ 分析队列                              │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ Appium Server │    │ Doubao/Qwen   │    │   移动设备     │
│   (移动端)     │    │    (AI/LLM)   │    │  (Android/iOS) │
└───────────────┘    └───────────────┘    └───────────────┘
```

> **开发模式说明**：当前项目可使用 SQLite 或 PostgreSQL。若使用 PostgreSQL，系统通过 Alembic 管理表结构；若使用 SQLite，适合轻量本地调试。生产环境建议使用 PostgreSQL。

---

## 2. 环境要求

### 2.1 必需软件

| 软件 | 版本要求 | 说明 |
|------|---------|------|
| Python | 3.11+ | 后端运行环境 |
| Node.js | 18+ | 前端构建环境 |
| Redis | 7+ | Appium Session 存储、Celery 队列、WebSocket 事件（可选，开发时部分功能可跳过） |

### 2.2 可选软件

| 软件 | 说明 |
|------|------|
| PostgreSQL 15+ | 生产环境数据库（开发环境默认 SQLite） |
| Appium Server | 真实设备测试执行 |
| ADB | Android 设备本地扫描与安装 |
| libimobiledevice | iOS 设备本地扫描 |

### 2.3 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 2 核 | 4 核+ |
| 内存 | 4 GB | 8 GB+ |
| 存储 | 10 GB | 30 GB+（包含应用包存储） |

---

## 3. 系统安装与启动

### 3.1 克隆项目

```bash
git clone https://github.com/your-org/nanotest.git
cd nanotest
```

### 3.2 后端设置

```bash
cd apps/backend

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3.3 配置环境变量

在 `apps/backend/` 目录下创建 `.env` 文件（可选，所有配置都有默认值）：

```env
# 数据库（推荐 PostgreSQL）
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/nanotest

# Redis（Session 存储和 Celery 需要）
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# AI/LLM 配置（二选一）
# 方式一：火山引擎豆包（默认）
LLM_PROVIDER=doubao
DOUBAO_API_KEY=your-doubao-api-key
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_CHAT_MODEL=doubao-seed-2-0-pro-260215
DOUBAO_EMBEDDING_MODEL=doubao-embedding-vision-251215

# 方式二：阿里千问
# LLM_PROVIDER=qwen
# QWEN_API_KEY=sk-xxx
# QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
# QWEN_CHAT_MODEL=qwen-plus
# QWEN_EMBEDDING_MODEL=text-embedding-v3

# JWT 密钥（生产环境必须修改）
SECRET_KEY=your-secret-key-change-in-production
```

### 3.4 启动后端

#### 方式一：使用启动脚本（Windows 推荐）

```powershell
cd apps/backend
.\start.ps1
```

`start.ps1` 会自动完成以下操作：
1. 激活 `.venv` 虚拟环境
2. 清理占用 8000 端口的进程
3. 运行数据库迁移（`alembic upgrade head`）
4. 启动 uvicorn 开发服务器（自动重载）

#### 方式二：手动启动

```bash
cd apps/backend

# 运行数据库迁移
python -m alembic upgrade head

# 启动后端服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app
```

> 首次启动前建议确认数据库已可访问；`start.ps1` 会自动执行 `alembic upgrade head`。

### 3.5 启动前端

```bash
cd apps/web

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端默认运行在 `http://localhost:3000`，并代理 API 请求到 `http://localhost:8000`。

### 3.6 启动 Celery Worker（可选）

测试执行和 AI 分析功能需要 Celery Worker，本地开发如不需要可跳过。

```bash
cd apps/backend

# 执行队列 Worker
celery -A app.tasks.celery_app worker -Q execution -l info

# 分析队列 Worker（新终端）
celery -A app.tasks.celery_app worker -Q analysis -l info
```

### 3.7 验证服务状态

```bash
# 检查后端健康状态
curl http://localhost:8000/health
```

预期响应：
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "database": "connected",
  "redis": "connected"
}
```

### 3.8 默认账户

当前默认开发账户：

| 邮箱 | 密码 | 角色 |
|------|------|------|
| admin@example.com | admin123 | admin |

### 3.9 访问地址

| 服务 | 地址 |
|------|------|
| 前端界面 | http://localhost:3000 |
| 后端 API | http://localhost:8000 |
| Swagger 文档 | http://localhost:8000/docs |
| ReDoc 文档 | http://localhost:8000/redoc |

---

## 4. 功能模块

### 4.1 用户认证

#### JSON 登录（前端使用）

```bash
POST /api/v1/auth/login/json
Content-Type: application/json

{
  "email": "admin@example.com",
  "password": "admin123"
}
```

响应：
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "id": "...",
    "email": "admin@example.com",
    "name": "Admin User",
    "role": "admin",
    "tenant_id": "..."
  }
}
```

#### 表单登录（OAuth2 标准，Swagger UI 使用）

```bash
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

username=admin@example.com&password=admin123
```

#### 获取当前用户信息

```bash
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

### 4.2 项目管理

项目是测试资源的顶层容器，所有测试用例、流程、运行都归属于某个项目。

### 4.2.1 需求管理

需求管理用于沉淀业务规则、验收标准，并为测试用例设计、测试执行分析提供上下文。

支持能力：

- 项目级需求列表与详情维护
- 需求编号、标题、描述、验收标准、业务规则管理
- 需求自动切块与 Embedding 生成
- 需求语义检索
- 需求与测试资产的可追踪关联

#### 创建需求

```bash
POST /api/v1/projects/{project_id}/requirements
Authorization: Bearer <token>
Content-Type: application/json

{
  "key": "REQ-LOGIN-001",
  "title": "用户应能通过验证码登录",
  "description": "已注册用户输入手机号和验证码后应成功进入首页。",
  "acceptance_criteria": [
    "验证码有效期为 5 分钟",
    "验证码校验成功后进入首页"
  ],
  "business_rules": [
    "未注册手机号不可登录",
    "验证码连续错误 5 次需要限流"
  ],
  "priority": "high",
  "status": "active",
  "platform": "common",
  "tags": ["登录", "验证码"]
}
```

#### 搜索需求

```bash
POST /api/v1/projects/{project_id}/requirements/search
Authorization: Bearer <token>
Content-Type: application/json

{
  "query": "登录验证码有效期和限流规则",
  "top_k": 5
}
```

#### 创建项目

```bash
POST /api/v1/projects
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "我的测试项目",
  "description": "项目描述",
  "platform": "android",
  "repo_url": "https://github.com/org/repo",
  "default_branch": "main"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 项目名称（1-255 字符） |
| description | string | 否 | 项目描述 |
| platform | string | 是 | `ios` / `android` / `hybrid` |
| repo_url | string | 否 | 代码仓库地址 |
| default_branch | string | 否 | 默认分支（默认 `main`） |

### 4.3 测试用例管理

#### DSL 语法说明

测试用例使用结构化 JSON DSL 定义，后端接收 `TestCaseDSL` 对象：

```json
{
  "name": "登录流程测试",
  "steps": [
    {
      "action": "launch_app",
      "params": {"app_id": "com.example.app"}
    },
    {
      "action": "input",
      "target": "id=username_field",
      "locator_type": "id",
      "value": "testuser@example.com"
    },
    {
      "action": "input",
      "target": "id=password_field",
      "locator_type": "id",
      "value": "password123"
    },
    {
      "action": "tap",
      "target": "id=login_button",
      "locator_type": "id"
    },
    {
      "action": "assert",
      "target": "id=welcome_message",
      "locator_type": "id",
      "timeout": 10
    }
  ],
  "variables": {
    "ENV": "staging"
  }
}
```

> **前端 DSL 编辑器**：前端提供 Monaco Editor 编辑器，支持 YAML-like 语法编写，保存时自动转换为上述 JSON 格式发送给后端。

#### 支持的操作类型

| Action | 说明 | 必需参数 |
|--------|------|---------|
| launch_app | 启动应用 | params.app_id |
| close_app | 关闭应用 | - |
| tap / click | 点击元素 | target |
| input | 输入文本 | target, value |
| swipe | 滑动 | target |
| scroll | 滚动 | - |
| wait | 等待 | timeout |
| assert | 断言 | target |
| screenshot | 截图 | - |
| back | 返回 | - |
| home | 主页 | - |
| clear | 清除输入 | target |
| long_press | 长按 | target |
| double_tap | 双击 | target |
| drag | 拖拽 | target |

#### 创建测试用例

```bash
POST /api/v1/projects/{project_id}/cases
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "登录测试",
  "description": "用户登录流程测试",
  "dsl_content": {
    "name": "LoginTest",
    "steps": [
      {"action": "launch_app", "params": {"app_id": "com.example.app"}},
      {"action": "input", "target": "id=username", "value": "test"},
      {"action": "input", "target": "id=password", "value": "pass"},
      {"action": "tap", "target": "id=btn_login"},
      {"action": "assert", "target": "id=home_banner"}
    ]
  },
  "tags": ["login", "smoke"],
  "status": "active"
}
```

#### 验证 DSL

```bash
POST /api/v1/cases/validate-dsl
Authorization: Bearer <token>
Content-Type: application/json

{
  "dsl_content": {
    "name": "Test",
    "steps": [{"action": "tap", "target": "id=btn"}]
  }
}
```

### 4.4 测试流程编排

测试流程（Flow）用于将多个测试用例组织成有向无环图（DAG），支持条件分支和并行执行。

#### 创建测试流程

```bash
POST /api/v1/projects/{project_id}/flows
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "完整测试流程",
  "description": "包含登录、操作、退出的完整流程",
  "graph_json": {
    "nodes": [
      {"id": "node_1", "type": "test_case", "label": "登录", "position": {"x": 0, "y": 0}},
      {"id": "node_2", "type": "test_case", "label": "操作", "position": {"x": 200, "y": 0}},
      {"id": "node_3", "type": "test_case", "label": "退出", "position": {"x": 400, "y": 0}}
    ],
    "edges": [
      {"id": "e1", "source": "node_1", "target": "node_2"},
      {"id": "e2", "source": "node_2", "target": "node_3"}
    ]
  },
  "entry_node": "node_1",
  "status": "active"
}
```

#### 绑定测试用例到流程节点

```bash
POST /api/v1/flows/{flow_id}/bindings
Authorization: Bearer <token>
Content-Type: application/json

{
  "node_key": "node_1",
  "test_case_id": "<test_case_uuid>",
  "retry_policy": {"enabled": true, "max_retries": 3},
  "timeout_sec": 300
}
```

#### 编译验证流程

```bash
POST /api/v1/flows/{flow_id}/compile
Authorization: Bearer <token>
```

返回编译结果，包含错误和警告（如未绑定用例的节点、不存在的边引用等）。

#### 直接执行流程

```bash
POST /api/v1/flows/{flow_id}/runs
Authorization: Bearer <token>
Content-Type: application/json

{}
```

> **自动绑定**：如果流程尚无绑定记录，但节点 `data` 中包含 `testCaseId`，后端会自动从 graph_json 中提取并创建绑定。

### 4.5 应用包管理

支持上传 APK/IPA 包，自动解析包名、版本、权限等元信息。

#### 上传应用包

```bash
POST /api/v1/packages/upload
Authorization: Bearer <token>
Content-Type: multipart/form-data

file=@app-release.apk
project_id=<project_uuid>
description=Release v1.2.0
tags=release,v1.2
```

上传后自动解析：
- **Android (APK)**：package_name, version_name, version_code, min_sdk, target_sdk, app_activity, permissions
- **iOS (IPA)**：bundle_id, version, build_number, minimum_os_version, supported_platforms

#### 列出应用包

```bash
GET /api/v1/packages?project_id=<id>&platform=android&page=1&page_size=20
Authorization: Bearer <token>
```

#### 安装包到本地设备

```bash
POST /api/v1/devices/install-package
Authorization: Bearer <token>
Content-Type: application/json

{
  "udid": "emulator-5554",
  "platform": "android",
  "package_id": "<package_uuid>"
}
```

### 4.6 设备管理

#### 注册设备

```bash
POST /api/v1/devices
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Pixel 7",
  "udid": "emulator-5554",
  "platform": "android",
  "platform_version": "14.0",
  "model": "Pixel 7",
  "manufacturer": "Google",
  "capabilities": {},
  "tags": ["android", "emulator"]
}
```

#### 扫描本地设备

自动通过 ADB（Android）和 libimobiledevice（iOS）扫描已连接的设备：

```bash
POST /api/v1/devices/scan-local
Authorization: Bearer <token>
```

#### 设备状态

| 状态 | 说明 |
|------|------|
| available | 设备可用 |
| busy | 设备忙碌（Session 占用中） |
| offline | 设备离线 |
| maintenance | 设备维护中 |

#### 远程 Appium 服务器

```bash
# 添加远程服务器
POST /api/v1/devices/remote-servers
{
  "name": "CI Server",
  "host": "192.168.1.100",
  "port": 4723
}

# 测试连接
POST /api/v1/devices/test-connection
{
  "host": "192.168.1.100",
  "port": 4723
}

# 刷新远程设备
POST /api/v1/devices/remote-servers/{server_id}/refresh
```

### 4.7 Appium Session 管理

基于应用包和设备创建 Appium Session，Session 信息存储在 Redis 中，支持跨进程访问。

#### 基于包创建 Session

```bash
POST /api/v1/devices/sessions/create-from-package
Authorization: Bearer <token>
Content-Type: application/json

{
  "device_udid": "emulator-5554",
  "package_id": "<package_uuid>",
  "server_url": "http://localhost:4723",
  "no_reset": true,
  "auto_launch": true
}
```

后端自动从包信息中提取 capabilities（appPackage/appActivity 或 bundleId），构建 W3C WebDriver 协议请求创建 Session。

#### Session 操作

```bash
# 列出活跃 Sessions
GET /api/v1/devices/sessions

# 执行操作（screenshot/source/launch_app/close_app/reset_app）
POST /api/v1/devices/sessions/{session_id}/action
{"action": "screenshot"}

# 终止 Session 并释放设备
DELETE /api/v1/devices/sessions/{session_id}/terminate
```

### 4.8 测试计划

#### 创建测试计划

```bash
POST /api/v1/projects/{project_id}/plans
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "每日冒烟测试",
  "trigger_type": "cron",
  "cron_expr": "0 9 * * *",
  "flow_id": "<flow_uuid>",
  "env_config": {"variables": {"ENV": "staging"}},
  "is_enabled": true
}
```

#### 触发类型

| 类型 | 说明 |
|------|------|
| manual | 手动触发 |
| cron | 定时触发（需配置 cron_expr） |
| webhook | Webhook 触发 |

#### 手动触发计划

```bash
POST /api/v1/plans/{plan_id}/trigger
Authorization: Bearer <token>
```

> 注意：此端点不需要请求体，后端会自动从计划配置中获取所需参数。

### 4.9 测试运行

#### 查看运行状态

```bash
GET /api/v1/runs/{run_id}
Authorization: Bearer <token>
```

#### 查看运行节点和步骤

```bash
# 运行节点列表
GET /api/v1/runs/{run_id}/nodes

# 运行所有步骤
GET /api/v1/runs/{run_id}/steps

# 特定节点的步骤
GET /api/v1/runs/{run_id}/nodes/{node_id}/steps
```

#### 取消运行

```bash
POST /api/v1/runs/{run_id}/cancel
Authorization: Bearer <token>
```

> 只能取消 `queued` 或 `running` 状态的运行。

### 4.10 AI 分析

#### 触发 AI 分析

```bash
POST /api/v1/runs/{run_id}/ai-analyze
Authorization: Bearer <token>
Content-Type: application/json

{
  "analysis_types": ["anomaly", "ui_state"]
}
```

> 需要运行处于完成状态（`passed`/`failed`/`completed`）。

#### 获取 AI 分析摘要

```bash
GET /api/v1/runs/{run_id}/ai-summary
Authorization: Bearer <token>
```

#### 获取风险评分

```bash
GET /api/v1/runs/{run_id}/risk-score
Authorization: Bearer <token>
```

### 4.11 运行对比

```bash
# 创建对比
POST /api/v1/runs/compare
{
  "baseline_run_id": "<uuid>",
  "target_run_id": "<uuid>"
}

# 获取对比结果
GET /api/v1/comparisons/{comparison_id}
```

---

## 5. 常规使用流程

### 5.1 完整测试流程

```
1. 登录系统
   └── 使用 admin@example.com / admin123 登录

2. 创建项目
   └── 指定名称和平台类型 (android/ios/hybrid)

3. 上传应用包
   └── 上传 APK/IPA 文件
   └── 系统自动解析包信息

4. 编写测试用例
   └── 使用前端 DSL 编辑器编写
   └── 支持语法高亮和自动补全
   └── 保存时自动转换为结构化 JSON

5. 创建测试流程
   └── 使用拖拽式 DAG 编辑器设计流程
   └── 将测试用例绑定到流程节点

6. 配置设备
   └── 扫描本地设备 或 添加远程 Appium 服务器
   └── 安装应用包到设备
   └── 创建 Appium Session

7. 执行测试
   └── 直接执行流程 或 通过测试计划触发
   └── 通过 WebSocket 实时接收状态更新

8. 查看结果
   └── 查看运行详情、节点状态、步骤结果

9. AI 分析（可选）
   └── 触发 AI 分析获取异常检测结果
   └── 查看风险评分和改进建议

10. 版本对比（可选）
    └── 选择两次运行进行差异对比
```

### 5.2 前端页面导航

| 路由 | 页面 | 说明 |
|------|------|------|
| `/login` | 登录页 | 用户登录 |
| `/projects` | 项目列表 | 管理所有项目 |
| `/projects/:id/dashboard` | 项目仪表盘 | 项目概览统计 |
| `/projects/:id/requirements` | 需求管理 | 需求维护与语义检索 |
| `/projects/:id/cases` | 测试用例 | 用例管理与 DSL 编辑 |
| `/projects/:id/flows` | 测试流程 | DAG 流程编排 |
| `/projects/:id/runs` | 测试运行 | 运行历史列表 |
| `/projects/:id/runs/:runId` | 运行详情 | 单次运行详情 |
| `/projects/:id/plans` | 测试计划 | 定时/手动计划管理 |
| `/projects/:id/comparison` | 运行对比 | 两次运行差异对比 |
| `/devices` | 设备管理 | 全局设备列表、Session 管理 |
| `/packages` | 应用包管理 | APK/IPA 上传与管理 |

---

## 6. API 接口说明

### 6.1 认证接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/login` | 表单登录（OAuth2 标准） |
| POST | `/api/v1/auth/login/json` | JSON 登录（前端使用） |
| GET | `/api/v1/auth/me` | 获取当前用户信息 |

### 6.2 项目接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/projects` | 创建项目 |
| GET | `/api/v1/projects` | 项目列表 |
| GET | `/api/v1/projects/{id}` | 项目详情 |
| PATCH | `/api/v1/projects/{id}` | 更新项目 |
| DELETE | `/api/v1/projects/{id}` | 删除项目 |

### 6.2.1 需求接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/projects/{id}/requirements` | 创建需求 |
| GET | `/api/v1/projects/{id}/requirements` | 需求列表 |
| POST | `/api/v1/projects/{id}/requirements/search` | 语义搜索需求 |
| GET | `/api/v1/requirements/{id}` | 需求详情 |
| PATCH | `/api/v1/requirements/{id}` | 更新需求 |
| DELETE | `/api/v1/requirements/{id}` | 删除需求（软删除） |
| POST | `/api/v1/requirements/{id}/reindex` | 重建需求索引 |
| POST | `/api/v1/requirements/{id}/links` | 创建需求关联 |
| GET | `/api/v1/requirements/{id}/links` | 查询需求关联 |
| DELETE | `/api/v1/requirements/{id}/links/{link_id}` | 删除需求关联 |

### 6.3 测试用例接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/projects/{id}/cases` | 创建用例 |
| GET | `/api/v1/projects/{id}/cases` | 用例列表（支持分页和筛选） |
| GET | `/api/v1/cases/{id}` | 用例详情 |
| PUT | `/api/v1/cases/{id}` | 更新用例 |
| DELETE | `/api/v1/cases/{id}` | 删除用例（软删除） |
| POST | `/api/v1/cases/{id}/versions` | 创建版本快照 |
| GET | `/api/v1/cases/{id}/versions` | 版本列表 |
| POST | `/api/v1/cases/validate-dsl` | 验证 DSL 语法 |

### 6.4 测试流程接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/projects/{id}/flows` | 创建流程 |
| GET | `/api/v1/projects/{id}/flows` | 流程列表 |
| GET | `/api/v1/flows/{id}` | 流程详情 |
| PUT | `/api/v1/flows/{id}` | 更新流程 |
| DELETE | `/api/v1/flows/{id}` | 删除流程（软删除） |
| POST | `/api/v1/flows/{id}/bindings` | 创建/更新节点绑定 |
| GET | `/api/v1/flows/{id}/bindings` | 绑定列表 |
| DELETE | `/api/v1/flows/{id}/bindings/{node_key}` | 删除绑定 |
| POST | `/api/v1/flows/{id}/compile` | 编译验证流程 |
| POST | `/api/v1/flows/{id}/runs` | 创建并执行流程运行 |

### 6.5 测试计划接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/projects/{id}/plans` | 创建计划 |
| GET | `/api/v1/projects/{id}/plans` | 计划列表 |
| GET | `/api/v1/plans/{id}` | 计划详情 |
| PATCH | `/api/v1/plans/{id}` | 更新计划 |
| DELETE | `/api/v1/plans/{id}` | 删除计划（软删除） |
| POST | `/api/v1/plans/{id}/trigger` | 触发计划执行（无请求体） |

### 6.6 测试运行接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/plans/{id}/runs` | 从计划创建运行（需 RunCreateRequest body） |
| GET | `/api/v1/projects/{id}/runs` | 运行列表（支持分页和状态筛选） |
| GET | `/api/v1/runs/{id}` | 运行详情 |
| POST | `/api/v1/runs/{id}/cancel` | 取消运行 |
| GET | `/api/v1/runs/{id}/nodes` | 运行节点列表 |
| GET | `/api/v1/runs/{id}/steps` | 运行所有步骤 |
| GET | `/api/v1/runs/{id}/nodes/{node_id}/steps` | 节点步骤列表 |

### 6.7 AI 分析接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/runs/{id}/ai-analyze` | 触发 AI 分析 |
| GET | `/api/v1/runs/{id}/ai-summary` | AI 分析摘要 |
| GET | `/api/v1/runs/{id}/risk-score` | 风险评分 |

### 6.8 对比接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/runs/compare` | 创建运行对比 |
| GET | `/api/v1/comparisons/{id}` | 对比详情 |

### 6.9 设备接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/devices` | 注册设备 |
| GET | `/api/v1/devices` | 设备列表（支持分页和平台筛选） |
| GET | `/api/v1/devices/{id}` | 设备详情 |
| PATCH | `/api/v1/devices/{id}` | 更新设备 |
| DELETE | `/api/v1/devices/{id}` | 删除设备（软删除） |
| POST | `/api/v1/devices/scan-local` | 扫描本地设备 |
| POST | `/api/v1/devices/install-package` | 安装包到设备 |
| POST | `/api/v1/devices/test-connection` | 测试远程连接 |
| POST | `/api/v1/devices/remote-servers` | 添加远程服务器 |
| GET | `/api/v1/devices/remote-servers` | 远程服务器列表 |
| DELETE | `/api/v1/devices/remote-servers/{id}` | 删除远程服务器 |
| POST | `/api/v1/devices/remote-servers/{id}/refresh` | 刷新远程设备 |

### 6.10 Session 管理接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/devices/sessions/create-from-package` | 基于包创建 Session |
| GET | `/api/v1/devices/sessions` | 列出活跃 Sessions |
| GET | `/api/v1/devices/sessions/{id}` | Session 详情 |
| POST | `/api/v1/devices/sessions/{id}/action` | 执行 Session 操作 |
| POST | `/api/v1/devices/sessions/{id}/refresh` | 刷新 Session 状态 |
| DELETE | `/api/v1/devices/sessions/{id}/terminate` | 终止 Session |

### 6.11 应用包接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/packages/upload` | 上传应用包（multipart/form-data） |
| GET | `/api/v1/packages` | 应用包列表（支持分页和筛选） |
| GET | `/api/v1/packages/{id}` | 应用包详情 |
| PATCH | `/api/v1/packages/{id}` | 更新应用包信息 |
| DELETE | `/api/v1/packages/{id}` | 删除应用包 |
| GET | `/api/v1/packages/{id}/download` | 获取下载地址 |
| GET | `/api/v1/packages/{id}/icon` | 获取图标地址 |
| GET | `/api/v1/packages/by-name/{package_name}` | 按包名查找 |

### 6.12 WebSocket 接口

| 路径 | 说明 |
|------|------|
| `/api/v1/ws/runs/{run_id}` | 订阅运行状态实时更新 |

---

## 7. 配置说明

### 7.1 环境变量

所有配置通过环境变量或 `.env` 文件设置，定义在 `app/core/config.py` 中。

#### 应用配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `APP_NAME` | 应用名称 | AI Mobile Test Platform |
| `APP_VERSION` | 应用版本 | 1.0.0 |
| `DEBUG` | 调试模式 | false |
| `ENVIRONMENT` | 环境标识 | development |
| `API_V1_PREFIX` | API 前缀 | /api/v1 |

#### 安全配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `SECRET_KEY` | JWT 签名密钥 | *开发默认值，**生产必须修改*** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token 过期时间（分钟） | 1440（24 小时） |
| `ALGORITHM` | JWT 算法 | HS256 |

#### 数据库配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DATABASE_URL` | 数据库连接串 | postgresql+asyncpg://postgres:postgres@localhost:5432/nanotest |
| `DATABASE_ECHO` | SQL 日志输出 | false |

> **开发模式提示**：若将 `DATABASE_URL` 设为 `sqlite+aiosqlite:///nanotest.db`，后端自动切换为 SQLite 模式。实际上默认 `.env` 未配置时，如果 PostgreSQL 不可达，后端会使用已存在的 `nanotest.db` 文件。

#### Redis 配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `REDIS_URL` | Redis 连接串 | redis://localhost:6379/0 |
| `CELERY_BROKER_URL` | Celery Broker | redis://localhost:6379/1 |
| `CELERY_RESULT_BACKEND` | Celery 结果后端 | redis://localhost:6379/2 |

#### AI/LLM 配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `LLM_PROVIDER` | LLM 提供商（`doubao` / `qwen`） | doubao |
| `DOUBAO_API_KEY` | 火山豆包 API Key | - |
| `DOUBAO_BASE_URL` | 豆包兼容 API 地址 | https://ark.cn-beijing.volces.com/api/v3 |
| `DOUBAO_CHAT_MODEL` | 豆包对话模型 | doubao-seed-2-0-pro-260215 |
| `DOUBAO_EMBEDDING_MODEL` | 豆包向量模型 | doubao-embedding-vision-251215 |
| `QWEN_API_KEY` | 千问 API Key | - |
| `QWEN_BASE_URL` | 千问兼容 API 地址 | https://dashscope.aliyuncs.com/compatible-mode/v1 |
| `QWEN_CHAT_MODEL` | 千问对话模型 | qwen-plus |
| `QWEN_EMBEDDING_MODEL` | 千问向量模型 | text-embedding-v3 |
| `AI_ANALYSIS_TIMEOUT` | AI 分析超时（秒） | 60 |

> **LLM 切换方式**：通过 `LLM_PROVIDER` 指定当前使用 `doubao` 或 `qwen`。系统会自动读取对应的一组 Key、Base URL、Chat Model、Embedding Model。

#### 存储配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `OSS_STS_TOKEN_URL` | 阿里云 OSS STS Token URL | - |
| `APP_PACKAGE_STORAGE_DIR` | 本地应用包存储路径 | storage/app_packages |

#### Appium 配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `APPIUM_SERVER_URL` | Appium 服务器地址 | http://localhost:4723 |
| `APPIUM_SESSION_TIMEOUT` | Session 超时（秒） | 300 |

#### 日志配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `LOG_LEVEL` | 日志级别 | INFO |
| `LOG_FORMAT` | 日志格式（json / console） | json |

### 7.2 Celery 队列配置

| 队列名 | 说明 | 并发建议 |
|--------|------|---------|
| execution | 测试执行队列 | 2-4 workers |
| analysis | AI 分析队列 | 1-2 workers |

---

## 8. 故障排除

### 8.1 常见问题

#### 后端启动报端口被占用

```powershell
# 使用 start.ps1 会自动清理端口，或手动：
# 查找占用 8000 端口的进程
netstat -ano | findstr :8000

# 结束进程
taskkill /PID <pid> /F
```

#### SQLite 模式下数据库锁错误

SQLite 不支持高并发写入。开发模式下这通常不是问题，但如果遇到 `database is locked` 错误：
1. 确保没有其他进程正在访问 `nanotest.db`
2. 考虑切换到 PostgreSQL

#### Redis 连接失败

```bash
# 检查 Redis 是否运行
redis-cli ping
# 预期返回 PONG

# Windows 上安装 Redis：
# 方式一：使用 WSL
# 方式二：使用 Memurai（Windows Redis 替代）
# 方式三：Docker
docker run -d -p 6379:6379 redis:7-alpine
```

> 注意：不安装 Redis 时，后端 API 基本功能仍可使用，但 Celery Worker、WebSocket 事件推送和 Appium Session 管理将不可用。

#### Celery Worker 不执行任务

```bash
# 检查 Worker 状态
celery -A app.tasks.celery_app inspect active

# 以 debug 级别启动查看详细日志
celery -A app.tasks.celery_app worker -l debug
```

#### 前端无法访问后端 API

1. 确认后端运行在 `http://localhost:8000`
2. 检查 `apps/web/.env`（如有）中 `VITE_API_URL` 是否正确
3. 前端默认通过 Vite 代理访问 `/api`，通常无需额外配置 `VITE_API_URL`
4. 后端已配置 CORS 允许开发环境访问

#### Alembic 迁移失败

```bash
# 查看当前迁移版本
python -m alembic current

# 强制标记到最新版本（谨慎使用）
python -m alembic stamp head

# 重新运行迁移
python -m alembic upgrade head
```

### 8.2 数据库重置

```bash
cd apps/backend

# SQLite 模式：直接删除数据库文件
del nanotest.db          # Windows
# rm nanotest.db         # Linux/macOS

# 重新启动后端会自动重建表和默认账户
python -m uvicorn app.main:app --reload
```

### 8.3 日志查看

后端使用 `structlog` 输出结构化日志：
- `LOG_FORMAT=json`：JSON 格式（适合生产环境日志收集）
- `LOG_FORMAT=console`：彩色控制台格式（适合开发调试）

---

## 附录

### A. 项目目录结构

```
nanotest/
├── apps/
│   ├── backend/              # FastAPI 后端
│   │   ├── app/
│   │   │   ├── api/v1/       # API 端点（auth, cases, devices, flows, packages, projects, reports, runs, websocket）
│   │   │   ├── core/         # 核心配置（config, database, events, security）
│   │   │   ├── domain/       # SQLAlchemy 数据模型
│   │   │   ├── integrations/ # 外部集成（aliyun OSS, appium, llm）
│   │   │   ├── schemas/      # Pydantic 请求/响应模型
│   │   │   ├── services/     # 业务服务层
│   │   │   └── tasks/        # Celery 异步任务（execution, analysis, reports）
│   │   ├── migrations/       # Alembic 数据库迁移
│   │   ├── scripts/          # 辅助脚本（seed.py）
│   │   ├── storage/          # 本地文件存储（应用包等）
│   │   ├── start.ps1         # Windows 开发启动脚本
│   │   ├── requirements.txt  # Python 依赖
│   │   └── alembic.ini       # Alembic 配置
│   ├── web/                  # React 前端
│   │   ├── src/
│   │   │   ├── components/   # UI 组件（Layout, ElementInspector 等）
│   │   │   ├── pages/        # 页面组件
│   │   │   ├── routes/       # 路由配置
│   │   │   ├── services/     # API 客户端（api.ts）
│   │   │   └── store/        # Zustand 状态管理
│   │   └── package.json
│   └── worker/               # Worker 运行器
│       └── runners/          # 执行引擎（base, flow_runner, appium_runner）
├── packages/                 # 共享 TypeScript 包
│   ├── dsl-engine/           # DSL 解析引擎
│   ├── flow-compiler/        # 流程编译器
│   ├── ai-adapter-sdk/       # AI 集成 SDK
│   └── shared-types/         # 共享类型定义
├── deploy/                   # 部署配置
│   ├── k8s/                  # Kubernetes 清单
│   └── observability/        # 监控配置
└── docs/                     # 文档
```

### B. 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18, Vite 5, TailwindCSS, ReactFlow, Monaco Editor, Zustand, @tanstack/react-query v5 |
| 后端 | FastAPI, SQLAlchemy 2 (async), Pydantic v2, Celery 5, structlog |
| 数据库 | SQLite（开发）/ PostgreSQL 15+（生产） |
| 缓存/队列 | Redis 7 |
| 存储 | 阿里云 OSS / 本地文件系统 |
| 移动端测试 | Appium 3.x (W3C WebDriver 协议) |
| AI/LLM | 火山引擎豆包（Doubao/Ark）/ OpenAI API |
| 包解析 | androguard (APK), plistlib (IPA) |
