from __future__ import annotations

from pathlib import Path

from .models import CollectedPageData, RegressionDiff


def compare_with_baseline(
    artifacts: list[CollectedPageData], baseline_dir: str | Path
) -> list[RegressionDiff]:
    baseline_root = Path(baseline_dir)
    diffs: list[RegressionDiff] = []
    for item in artifacts:
        current = Path(item.screenshot_path)
        baseline = baseline_root / current.name
        if not baseline.exists():
            continue
        current_bytes = current.read_bytes()
        baseline_bytes = baseline.read_bytes()
        if current_bytes == baseline_bytes:
            continue
        length = max(len(current_bytes), len(baseline_bytes))
        mismatch = sum(
            1 for i in range(min(len(current_bytes), len(baseline_bytes))) if current_bytes[i] != baseline_bytes[i]
        ) + abs(len(current_bytes) - len(baseline_bytes))
        score = round(mismatch / max(length, 1), 4)
        diffs.append(
            RegressionDiff(
                step_id=item.step_id,
                baseline=str(baseline),
                current=str(current),
                diff_score=score,
            )
        )
    return diffs
