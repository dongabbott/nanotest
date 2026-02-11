from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Literal


@dataclass
class Step:
    id: str
    action: Literal["launch", "tap", "input", "assert_visible", "swipe"]
    target: str | None = None
    value: str | None = None


@dataclass
class TestCase:
    id: str
    name: str
    platform: Literal["android", "ios"]
    app: str
    route: str = "/"
    steps: list[Step] = field(default_factory=list)
    baseline_report: str | None = None


@dataclass
class StepExecution:
    step_id: str
    status: Literal["passed", "failed"]
    message: str
    route: str


@dataclass
class CollectedPageData:
    step_id: str
    screenshot_path: str
    xml_path: str
    route: str


@dataclass
class DesignIssue:
    severity: Literal["low", "medium", "high"]
    kind: str
    description: str
    step_id: str


@dataclass
class RegressionDiff:
    step_id: str
    baseline: str
    current: str
    diff_score: float


@dataclass
class Report:
    id: str
    testcase_id: str
    created_at: datetime
    execution: list[StepExecution]
    issues: list[DesignIssue]
    regressions: list[RegressionDiff]
    risk_score: int
    suggestions: list[str]
    artifacts: list[CollectedPageData]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data
