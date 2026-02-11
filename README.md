# NanoTest

一个按你给出的分层架构实现的可运行 MVP：

1. **测试用例定义层**：支持 YAML/JSON DSL。
2. **自动化执行引擎层**：Android(UIA2)/iOS(XCUITest) 统一接口。
3. **页面采集层**：自动生成截图 + XML + 路由信息。
4. **AI 分析引擎**：页面设计分析、测试点生成、UI一致性检测、回归对比。
5. **报告系统**：轻量 Web Dashboard + JSON API。

## 快速开始

```bash
PYTHONPATH=src python -m nanotest.cli examples/login_flow.yaml --workspace outputs
PYTHONPATH=src python -m nanotest.cli examples/login_flow.yaml --workspace outputs --serve --port 8000
```

然后打开：`http://localhost:8000/reports/smoke_login/report_<id>.json`

## 目录

- `src/nanotest/dsl.py`：用例 DSL 解析
- `src/nanotest/engine.py`：执行引擎抽象
- `src/nanotest/collector.py`：截图/XML/路由采集
- `src/nanotest/ai.py`：分析与风险评分
- `src/nanotest/regression.py`：截图回归差异
- `src/nanotest/reporting.py`：报告聚合与落盘
- `src/nanotest/dashboard.py`：Web Dashboard
- `tests/test_pipeline.py`：端到端单测
