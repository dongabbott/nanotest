from __future__ import annotations

from pathlib import Path

from .ai import analyze_design
from .collector import collect_pages
from .dsl import load_test_case
from .engine import get_engine
from .regression import compare_with_baseline
from .reporting import build_report, save_report


class Pipeline:
    def __init__(self, workspace: str | Path = "outputs") -> None:
        self.workspace = Path(workspace)

    def run(self, dsl_path: str | Path):
        testcase = load_test_case(dsl_path)
        case_dir = self.workspace / testcase.id
        artifacts_dir = case_dir / "artifacts"

        engine = get_engine(testcase.platform)
        execution = engine.run(testcase)
        artifacts = collect_pages(testcase, execution, artifacts_dir)
        issues = analyze_design(artifacts)

        regressions = []
        if testcase.baseline_report:
            regressions = compare_with_baseline(artifacts, testcase.baseline_report)

        report = build_report(testcase, execution, artifacts, issues, regressions)
        report_path = save_report(report, case_dir)
        return report, report_path
