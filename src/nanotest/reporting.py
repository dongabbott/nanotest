from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .ai import calculate_risk_score, generate_test_points
from .models import CollectedPageData, DesignIssue, RegressionDiff, Report, StepExecution, TestCase


def build_report(
    testcase: TestCase,
    execution: list[StepExecution],
    artifacts: list[CollectedPageData],
    issues: list[DesignIssue],
    regressions: list[RegressionDiff],
) -> Report:
    suggestions = [
        *generate_test_points(artifacts),
        "对中高风险页面补充多分辨率截图回归集",
        "对关键流程增加夜间构建自动回归任务",
    ]
    return Report(
        id=uuid4().hex[:12],
        testcase_id=testcase.id,
        created_at=datetime.utcnow(),
        execution=execution,
        issues=issues,
        regressions=regressions,
        risk_score=calculate_risk_score(issues, len(regressions)),
        suggestions=suggestions,
        artifacts=artifacts,
    )


def save_report(report: Report, output_dir: str | Path) -> Path:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"report_{report.id}.json"
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path
