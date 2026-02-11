from __future__ import annotations

import json
from pathlib import Path

from .models import Step, TestCase


def _parse_simple_yaml(text: str) -> dict:
    data: dict = {}
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("steps:"):
            i += 1
            steps: list[dict] = []
            curr: dict | None = None
            while i < len(lines) and lines[i].startswith("  -"):
                if curr:
                    steps.append(curr)
                curr = {}
                part = lines[i][3:]
                if part.strip():
                    k, v = [p.strip() for p in part.split(":", 1)]
                    curr[k] = v
                i += 1
                while i < len(lines) and lines[i].startswith("    "):
                    k, v = [p.strip() for p in lines[i].strip().split(":", 1)]
                    curr[k] = v
                    i += 1
            if curr:
                steps.append(curr)
            data["steps"] = steps
            continue
        if ":" in ln:
            k, v = [p.strip() for p in ln.split(":", 1)]
            data[k] = v
        i += 1
    return data


def load_test_case(path: str | Path) -> TestCase:
    file = Path(path)
    content = file.read_text(encoding="utf-8")
    if file.suffix in {".yaml", ".yml"}:
        payload = _parse_simple_yaml(content)
    elif file.suffix == ".json":
        payload = json.loads(content)
    else:
        raise ValueError(f"Unsupported DSL file: {file.suffix}")

    steps = [Step(**s) for s in payload.get("steps", [])]
    return TestCase(
        id=payload["id"],
        name=payload["name"],
        platform=payload["platform"],
        app=payload["app"],
        route=payload.get("route", "/"),
        steps=steps,
        baseline_report=payload.get("baseline_report"),
    )
