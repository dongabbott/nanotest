import json
from pathlib import Path

from nanotest.pipeline import Pipeline


def test_pipeline_generates_report(tmp_path: Path):
    dsl = tmp_path / "case.yaml"
    dsl.write_text(
        """
id: t1
name: test
platform: ios
app: demo
route: /root
steps:
  - id: s1
    action: launch
  - id: s2
    action: tap
    target: next
""".strip(),
        encoding="utf-8",
    )

    report, report_path = Pipeline(workspace=tmp_path / "out").run(dsl)
    assert report.risk_score >= 0
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["testcase_id"] == "t1"
    assert len(payload["artifacts"]) == 2
