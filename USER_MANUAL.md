# NanoTest 使用手册

## 目录

1. [系统概述](#1-系统概述)
2. [环境要求](#2-环境要求)
3. [系统安装](#3-系统安装)
4. [系统启动](#4-系统启动)
5. [功能模块](#5-功能模块)
6. [常规使用流程](#6-常规使用流程)
7. [API 接口说明](#7-api-接口说明)
8. [配置说明](#8-配置说明)
9. [故障排除](#9-故障排除)

---

## 1. 系统概述

NanoTest 是一个企业级 AI 驱动的移动端自动化测试管理平台，提供以下核心功能：

- **测试用例 DSL 定义**：使用声明式 DSL 语法定义测试用例
- **可视化流程编排**：通过拖拽式 DAG 编辑器设计测试流程
- **AI 智能分析**：自动截图分析和异常检测
- **多平台支持**：支持 iOS 和 Android 测试（通过 Appium）
- **风险评分**：AI 计算测试运行风险分数
- **运行对比**：测试运行之间的可视化差异对比
- **多租户支持**：完整的租户隔离和 RBAC 权限控制

### 1.1 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     前端 (React + Vite)                      │
│                TailwindCSS + ReactFlow                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   后端 API (FastAPI)                         │
│              REST API + WebSocket + JWT 认证                │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  PostgreSQL   │    │     Redis     │    │  Aliyun OSS   │
│   (数据库)     │    │ (缓存/队列)    │    │   (存储)      │
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
│ Appium Server │    │   OpenAI API  │    │   设备农场     │
│   (移动端)     │    │    (AI/LLM)   │    │   (设备)      │
└───────────────┘    └───────────────┘    └───────────────┘
```

---

## 2. 环境要求

### 2.1 软件要求

| 软件 | 版本要求 | 说明 |
|------|---------|------|
| Python | 3.11+ | 后端运行环境 |
| Node.js | 18+ | 前端构建环境 |
| Docker | 最新版 | 容器化部署 |
| Docker Compose | 最新版 | 多容器编排 |
| PostgreSQL | 15+ | 主数据库 |
| Redis | 7+ | 缓存和消息队列 |
| Aliyun OSS | - | 对象存储 |

### 2.2 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 2核 | 4核+ |
| 内存 | 4GB | 8GB+ |
| 存储 | 20GB | 50GB+ |

### 2.3 可选依赖

- **Appium Server**：用于真实设备测试
- **OpenAI API Key**：用于 AI 分析功能

---

## 3. 系统安装

### 3.1 克隆项目

```bash
git clone https://github.com/your-org/nanotest.git
cd nanotest
```

### 3.2 方式一：Docker Compose 部署（推荐）

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps
```

服务启动后可访问：
- **前端界面**：http://localhost:3000
- **后端 API**：http://localhost:8000
- **API 文档**：http://localhost:8000/api/v1/docs

### 3.3 方式二：本地开发部署

#### 3.3.1 启动基础设施

```bash
# 启动 PostgreSQL、Redis
docker-compose up -d postgres redis
```

#### 3.3.2 后端配置

```bash
cd apps/backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 复制环境配置文件
copy .env.example .env  # Windows
# cp .env.example .env  # Linux/macOS

# 编辑 .env 文件，配置必要参数
```

#### 3.3.3 数据库迁移

```bash
# 运行数据库迁移
alembic upgrade head
```

#### 3.3.4 启动后端服务

```bash
# 启动 FastAPI 服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 3.3.5 启动 Celery Worker

```bash
# 执行队列 Worker（新终端）
celery -A app.tasks.celery_app worker -Q execution -l info

# 分析队列 Worker（新终端）
celery -A app.tasks.celery_app worker -Q analysis -l info
```

#### 3.3.6 前端配置

```bash
cd apps/web

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

---

## 4. 系统启动

### 4.1 Docker 方式启动

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止所有服务
docker-compose down

# 重启特定服务
docker-compose restart backend
```

### 4.2 本地开发启动顺序

1. **启动基础设施**：`docker-compose up -d postgres redis minio`
2. **启动后端 API**：`uvicorn app.main:app --reload`
3. **启动 Celery Worker**：`celery -A app.tasks.celery_app worker -Q execution -l info`
4. **启动前端**：`npm run dev`

### 4.3 验证服务状态

```bash
# 检查后端健康状态
curl http://localhost:8000/health

# 预期响应
{
  "status": "healthy",
  "version": "1.0.0",
  "database": "connected",
  "redis": "connected"
}
```

### 4.4 默认账户

开发环境默认创建以下账户：

| 邮箱 | 密码 | 角色 |
|------|------|------|
| admin@example.com | admin123 | admin |

---

## 5. 功能模块

### 5.1 用户认证

#### 登录

```bash
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

username=admin@example.com&password=admin123
```

响应：
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

#### 获取当前用户信息

```bash
GET /api/v1/me
Authorization: Bearer <access_token>
```

### 5.2 项目管理

项目是测试资源的顶层容器。

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

#### 项目字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 项目名称 |
| description | string | 否 | 项目描述 |
| platform | string | 是 | 平台类型：ios/android/hybrid |
| repo_url | string | 否 | 代码仓库地址 |
| default_branch | string | 否 | 默认分支，默认 main |

### 5.3 测试用例管理

#### DSL 语法说明

测试用例使用声明式 DSL 语法定义：

```yaml
name: 登录流程测试
steps:
  - action: launch_app
    params:
      app_id: com.example.app
  
  - action: input
    target: accessibility_id:username_field
    value: testuser@example.com
  
  - action: input
    target: accessibility_id:password_field
    value: password123
  
  - action: tap
    target: accessibility_id:login_button
  
  - action: assert
    target: accessibility_id:welcome_message
    params:
      condition: exists
      timeout: 10
```

#### 支持的操作类型

| Action | 说明 | 必需参数 |
|--------|------|---------|
| launch_app | 启动应用 | app_id 或 bundle_id |
| close_app | 关闭应用 | - |
| tap / click | 点击元素 | target |
| input | 输入文本 | target, value |
| swipe | 滑动 | target, direction |
| scroll | 滚动 | direction |
| wait | 等待 | timeout |
| assert | 断言 | target, condition |
| screenshot | 截图 | - |
| back | 返回 | - |
| home | 主页 | - |
| clear | 清除输入 | target |
| long_press | 长按 | target |
| double_tap | 双击 | target |
| drag | 拖拽 | source, target |

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
      {"action": "launch_app", "params": {}},
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
    "steps": [...]
  }
}
```

### 5.4 测试流程编排

测试流程（Flow）用于将多个测试用例组织成有向无环图（DAG）。

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
      {"id": "node_1", "type": "test_case", "position": {"x": 0, "y": 0}},
      {"id": "node_2", "type": "test_case", "position": {"x": 200, "y": 0}},
      {"id": "node_3", "type": "test_case", "position": {"x": 400, "y": 0}}
    ],
    "edges": [
      {"source": "node_1", "target": "node_2"},
      {"source": "node_2", "target": "node_3"}
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
  "test_case_id": "<test_case_id>",
  "retry_policy": {
    "enabled": true,
    "max_retries": 3
  },
  "timeout_sec": 300
}
```

#### 编译验证流程

```bash
POST /api/v1/flows/{flow_id}/compile
Authorization: Bearer <token>
```

### 5.5 设备管理

#### 注册设备

```bash
POST /api/v1/devices
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "iPhone 14 Pro",
  "udid": "00008030-001234567890ABCD",
  "platform": "ios",
  "platform_version": "17.0",
  "model": "iPhone14,3",
  "manufacturer": "Apple",
  "capabilities": {
    "bundle_id": "com.example.app",
    "automation_name": "XCUITest"
  },
  "tags": ["ios", "iphone"]
}
```

#### 设备状态

| 状态 | 说明 |
|------|------|
| available | 设备可用 |
| busy | 设备忙碌中 |
| offline | 设备离线 |
| maintenance | 设备维护中 |

### 5.6 测试执行

#### 创建测试计划

```bash
POST /api/v1/projects/{project_id}/plans
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "每日冒烟测试",
  "trigger_type": "cron",
  "cron_expr": "0 9 * * *",
  "flow_id": "<flow_id>",
  "env_config": {
    "device_id": "<device_id>",
    "variables": {
      "ENV": "staging"
    }
  },
  "is_enabled": true
}
```

#### 触发类型

| 类型 | 说明 |
|------|------|
| manual | 手动触发 |
| cron | 定时触发（需配置 cron_expr） |
| webhook | Webhook 触发 |

#### 手动执行测试

```bash
POST /api/v1/flows/{flow_id}/runs
Authorization: Bearer <token>
Content-Type: application/json

{
  "plan_id": "<plan_id>",
  "env_config": {
    "device_id": "<device_id>",
    "screenshot_on_failure": true,
    "screenshot_on_step": false
  }
}
```

#### 查看运行状态

```bash
GET /api/v1/runs/{run_id}
Authorization: Bearer <token>
```

#### 取消运行

```bash
POST /api/v1/runs/{run_id}/cancel
Authorization: Bearer <token>
```

### 5.7 AI 分析

#### 触发 AI 分析

```bash
POST /api/v1/runs/{run_id}/ai-analyze
Authorization: Bearer <token>
Content-Type: application/json

{
  "analysis_types": ["anomaly", "ui_state"]
}
```

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

### 5.8 运行对比

#### 创建对比

```bash
POST /api/v1/runs/compare
Authorization: Bearer <token>
Content-Type: application/json

{
  "baseline_run_id": "<baseline_run_id>",
  "target_run_id": "<target_run_id>"
}
```

#### 获取对比结果

```bash
GET /api/v1/comparisons/{comparison_id}
Authorization: Bearer <token>
```

---

## 6. 常规使用流程

### 6.1 完整测试流程示例

```
1. 登录系统
   └── 使用账户密码登录，获取访问令牌

2. 创建项目
   └── 创建测试项目，指定平台类型

3. 编写测试用例
   └── 使用 DSL 语法定义测试步骤
   └── 验证 DSL 语法正确性

4. 创建测试流程
   └── 设计 DAG 流程图
   └── 将测试用例绑定到流程节点

5. 配置设备
   └── 注册测试设备
   └── 配置设备能力参数

6. 执行测试
   └── 手动触发或创建定时计划
   └── 实时监控执行状态

7. 查看结果
   └── 查看测试报告
   └── 分析失败原因

8. AI 分析（可选）
   └── 触发 AI 分析
   └── 查看风险评分

9. 版本对比（可选）
   └── 选择基线版本
   └── 对比差异
```

### 6.2 前端页面导航

| 路由 | 页面 | 说明 |
|------|------|------|
| /login | 登录页 | 用户登录 |
| /projects | 项目列表 | 管理所有项目 |
| /projects/:id/dashboard | 项目仪表盘 | 项目概览统计 |
| /projects/:id/cases | 测试用例 | 用例管理 |
| /projects/:id/flows | 测试流程 | 流程编排 |
| /projects/:id/runs | 测试运行 | 运行历史 |
| /projects/:id/runs/:runId | 运行详情 | 单次运行详情 |
| /projects/:id/devices | 设备管理 | 设备列表 |
| /settings/devices | 设备设置 | 全局设备配置 |

---

## 7. API 接口说明

### 7.1 认证接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/auth/login | 用户登录 |
| GET | /api/v1/me | 获取当前用户 |

### 7.2 项目接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/projects | 创建项目 |
| GET | /api/v1/projects | 项目列表 |
| GET | /api/v1/projects/{id} | 项目详情 |
| PUT | /api/v1/projects/{id} | 更新项目 |
| DELETE | /api/v1/projects/{id} | 删除项目 |

### 7.3 测试用例接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/projects/{id}/cases | 创建用例 |
| GET | /api/v1/projects/{id}/cases | 用例列表 |
| GET | /api/v1/cases/{id} | 用例详情 |
| PUT | /api/v1/cases/{id} | 更新用例 |
| DELETE | /api/v1/cases/{id} | 删除用例 |
| POST | /api/v1/cases/{id}/versions | 创建版本 |
| GET | /api/v1/cases/{id}/versions | 版本列表 |
| POST | /api/v1/cases/validate-dsl | 验证 DSL |

### 7.4 测试流程接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/projects/{id}/flows | 创建流程 |
| GET | /api/v1/projects/{id}/flows | 流程列表 |
| GET | /api/v1/flows/{id} | 流程详情 |
| PUT | /api/v1/flows/{id} | 更新流程 |
| DELETE | /api/v1/flows/{id} | 删除流程 |
| POST | /api/v1/flows/{id}/bindings | 创建绑定 |
| GET | /api/v1/flows/{id}/bindings | 绑定列表 |
| POST | /api/v1/flows/{id}/compile | 编译流程 |
| POST | /api/v1/flows/{id}/runs | 执行流程 |

### 7.5 测试运行接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/plans/{id}/runs | 从计划触发运行 |
| GET | /api/v1/projects/{id}/runs | 运行列表 |
| GET | /api/v1/runs/{id} | 运行详情 |
| POST | /api/v1/runs/{id}/cancel | 取消运行 |
| GET | /api/v1/runs/{id}/nodes | 运行节点列表 |
| GET | /api/v1/runs/{id}/steps | 运行步骤列表 |

### 7.6 AI 分析接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/runs/{id}/ai-analyze | 触发 AI 分析 |
| GET | /api/v1/runs/{id}/ai-summary | AI 分析摘要 |
| GET | /api/v1/runs/{id}/risk-score | 风险评分 |

### 7.7 对比接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/runs/compare | 创建对比 |
| GET | /api/v1/comparisons/{id} | 对比详情 |

### 7.8 设备接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/devices | 注册设备 |
| GET | /api/v1/devices | 设备列表 |
| GET | /api/v1/devices/{id} | 设备详情 |
| PATCH | /api/v1/devices/{id}/status | 更新状态 |

---

## 8. 配置说明

### 8.1 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| APP_NAME | 应用名称 | AI Mobile Test Platform |
| APP_VERSION | 应用版本 | 1.0.0 |
| DEBUG | 调试模式 | true |
| ENVIRONMENT | 环境标识 | development |
| API_V1_PREFIX | API 前缀 | /api/v1 |
| SECRET_KEY | JWT 签名密钥 | **生产环境必须修改** |
| ACCESS_TOKEN_EXPIRE_MINUTES | Token 过期时间（分钟） | 1440 |
| DATABASE_URL | 数据库连接串 | postgresql+asyncpg://... |
| REDIS_URL | Redis 连接串 | redis://localhost:6379/0 |
| CELERY_BROKER_URL | Celery Broker | redis://localhost:6379/1 |
| CELERY_RESULT_BACKEND | Celery 结果后端 | redis://localhost:6379/2 |
| OSS_STS_TOKEN_URL | 阿里云 OSS STS Token 获取地址 | - |
| APPIUM_SERVER_URL | Appium 服务器地址 | http://localhost:4723 |
| OPENAI_API_KEY | OpenAI API 密钥 | - |
| OPENAI_MODEL | AI 模型 | gpt-4-vision-preview |
| LOG_LEVEL | 日志级别 | INFO |
| LOG_FORMAT | 日志格式 | json |

### 8.2 Celery 队列配置

| 队列名 | 说明 | 并发建议 |
|--------|------|---------|
| execution | 测试执行队列 | 2-4 workers |
| analysis | AI 分析队列 | 2 workers |

### 8.3 OSS 对象路径约定

| 前缀 | 用途 |
|------|------|
| screenshots/ | 测试截图存储 |
| reports/ | 测试报告存储 |
| logs/ | 日志文件存储 |

---

## 9. 故障排除

### 9.1 常见问题

#### 后端无法连接数据库

```bash
# 检查 PostgreSQL 是否运行
docker-compose ps postgres

# 检查连接
docker-compose exec postgres pg_isready -U postgres
```

#### Redis 连接失败

```bash
# 检查 Redis 是否运行
docker-compose ps redis

# 测试连接
docker-compose exec redis redis-cli ping
```

#### Celery Worker 不执行任务

```bash
# 检查 Worker 状态
celery -A app.tasks.celery_app inspect active

# 查看 Worker 日志
celery -A app.tasks.celery_app worker -l debug
```

#### 前端无法访问后端 API

1. 检查后端服务是否运行
2. 检查 CORS 配置
3. 检查网络端口是否开放

### 9.2 日志查看

```bash
# Docker 日志
docker-compose logs -f backend
docker-compose logs -f celery-execution
docker-compose logs -f celery-analysis

# 本地运行日志
# 日志输出到控制台，根据 LOG_FORMAT 配置格式
```

### 9.3 数据库重置

```bash
# 警告：此操作会删除所有数据

# 重新运行迁移
alembic downgrade base
alembic upgrade head

# 或使用 Docker
docker-compose down -v
docker-compose up -d postgres
alembic upgrade head
```

### 9.4 性能优化建议

1. **数据库优化**
   - 添加适当的索引
   - 定期清理历史数据
   - 配置连接池

2. **Redis 优化**
   - 配置内存限制
   - 设置过期策略

3. **Celery 优化**
   - 根据负载调整 Worker 数量
   - 配置任务超时时间
   - 启用任务结果过期

4. **OSS 优化**
   - 配置生命周期规则
   - 定期清理旧文件

---

## 附录

### A. 项目目录结构

```
nanotest/
├── apps/
│   ├── backend/              # FastAPI 后端
│   │   ├── app/
│   │   │   ├── api/v1/       # API 端点
│   │   │   ├── core/         # 核心配置
│   │   │   ├── domain/       # 数据模型
│   │   │   ├── integrations/ # 外部集成
│   │   │   ├── schemas/      # Pydantic 模型
│   │   │   ├── services/     # 业务服务
│   │   │   └── tasks/        # Celery 任务
│   │   └── migrations/       # 数据库迁移
│   ├── web/                  # React 前端
│   └── worker/               # Worker 工具
├── packages/                 # 共享包
│   ├── dsl-engine/           # DSL 解析引擎
│   ├── flow-compiler/        # 流程编译器
│   └── ai-adapter-sdk/       # AI 集成 SDK
├── docker-compose.yml        # Docker 编排
└── README.md                 # 项目说明
```

### B. 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18, Vite, TailwindCSS, ReactFlow, Monaco Editor |
| 后端 | FastAPI, SQLAlchemy, Pydantic, Celery |
| 数据库 | PostgreSQL 15 |
| 缓存 | Redis 7 |
| 存储 | Aliyun OSS |
| 移动端测试 | Appium |
| AI | OpenAI API |

### C. 联系支持

如有问题，请通过以下方式获取支持：
- 提交 GitHub Issue
- 查阅项目 Wiki
- 联系技术支持团队
