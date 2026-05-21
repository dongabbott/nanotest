#!/usr/bin/env python3
"""Add 'from __future__ import annotations' to all Python files in the project."""

import os
import re
import sys

TARGET_DIRS = ["apps/backend", "apps/worker", "packages"]
EXCLUDE_DIRS = {"__pycache__", ".venv", "node_modules", "dist", "build", ".git"}


def should_process(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    return not any(p in EXCLUDE_DIRS for p in parts)


def find_insertion_point(lines: list[str]) -> int:
    """
    Return the line index where 'from __future__ import annotations' should be inserted.
    Rules:
      1. After shebang (#!/...)
      2. After module docstring (multiline string at top)
      3. At the very beginning otherwise
    """
    idx = 0
    n = len(lines)

    # Skip shebang
    if n > 0 and lines[0].startswith("#!"):
        idx = 1
        # Also skip blank lines after shebang
        while idx < n and lines[idx].strip() == "":
            idx += 1

    # Skip module docstring
    if idx < n:
        stripped = lines[idx].strip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            # Single-line docstring
            if stripped.endswith('"""') and len(stripped) > 3 or stripped.endswith("'''") and len(stripped) > 3:
                # Could be single line, e.g. """doc"""
                if stripped.count('"""') == 2 or stripped.count("'''") == 2:
                    idx += 1
                    while idx < n and lines[idx].strip() == "":
                        idx += 1
                    return idx
            # Multi-line docstring
            delimiter = '"""' if stripped.startswith('"""') else "'''"
            idx += 1
            while idx < n:
                if delimiter in lines[idx]:
                    idx += 1
                    break
                idx += 1
            while idx < n and lines[idx].strip() == "":
                idx += 1

    return idx


def process_file(filepath: str) -> bool:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Already present?
    if "from __future__ import annotations" in content:
        return False

    lines = content.splitlines(keepends=True)
    insert_idx = find_insertion_point(lines)

    # Ensure blank line before/after for cleanliness
    new_line = "from __future__ import annotations\n"

    # If inserting at very top, just prepend
    if insert_idx == 0:
        if lines and not lines[0].endswith("\n"):
            lines[0] += "\n"
        lines.insert(0, new_line)
    else:
        # Insert at calculated position
        lines.insert(insert_idx, new_line)

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)

    return True


def main() -> int:
    project_root = os.path.dirname(os.path.abspath(__file__))
    modified = 0
    skipped = 0
    errors = 0

    for target in TARGET_DIRS:
        target_path = os.path.join(project_root, target)
        if not os.path.isdir(target_path):
            continue
        for root, _dirs, files in os.walk(target_path):
            for name in files:
                if not name.endswith(".py"):
                    continue
                filepath = os.path.join(root, name)
                rel = os.path.relpath(filepath, project_root)
                if not should_process(rel):
                    continue
                try:
                    if process_file(filepath):
                        print(f"  + {rel}")
                        modified += 1
                    else:
                        skipped += 1
                except Exception as exc:
                    print(f"  ! ERROR {rel}: {exc}", file=sys.stderr)
                    errors += 1

    print(f"\nDone. Modified: {modified}, Already had: {skipped}, Errors: {errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
