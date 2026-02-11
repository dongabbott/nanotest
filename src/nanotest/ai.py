from __future__ import annotations

from pathlib import Path

from .models import CollectedPageData, DesignIssue


def analyze_design(artifacts: list[CollectedPageData]) -> list[DesignIssue]:
    issues: list[DesignIssue] = []
    for item in artifacts:
        xml = Path(item.xml_path).read_text(encoding="utf-8")
        if "height='18'" in xml:
            issues.append(
                DesignIssue(
                    severity="medium",
                    kind="readability",
                    description="Route label text height is below recommended size.",
                    step_id=item.step_id,
                )
            )
        if "button_login" in xml and "width='160'" in xml:
            issues.append(
                DesignIssue(
                    severity="low",
                    kind="tap_target",
                    description="Login button width can be expanded for easier tapping.",
                    step_id=item.step_id,
                )
            )
    return issues


def generate_test_points(artifacts: list[CollectedPageData]) -> list[str]:
    points = ["验证页面元素可见性和布局稳定性", "验证路由跳转与返回栈行为"]
    if artifacts:
        points.append("验证关键按钮的点击区域和可读性")
    return points


def calculate_risk_score(issues: list[DesignIssue], regression_count: int) -> int:
    score = 5
    score += sum(30 if i.severity == "high" else 15 if i.severity == "medium" else 8 for i in issues)
    score += regression_count * 12
    return min(score, 100)
