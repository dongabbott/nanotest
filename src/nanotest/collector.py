from __future__ import annotations

import struct
import zlib
from pathlib import Path

from .models import CollectedPageData, StepExecution, TestCase


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack("!I", len(data)) + tag + data + struct.pack("!I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def _write_png(path: Path, width: int, height: int, color: tuple[int, int, int]) -> None:
    row = bytes(color) * width
    raw = b"".join(b"\x00" + row for _ in range(height))
    comp = zlib.compress(raw, level=9)
    png = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack("!2I5B", width, height, 8, 2, 0, 0, 0)
    png += _png_chunk(b"IHDR", ihdr)
    png += _png_chunk(b"IDAT", comp)
    png += _png_chunk(b"IEND", b"")
    path.write_bytes(png)


def collect_pages(
    testcase: TestCase, executions: list[StepExecution], output_dir: str | Path
) -> list[CollectedPageData]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    artifacts: list[CollectedPageData] = []
    for item in executions:
        screen_path = root / f"{testcase.id}_{item.step_id}.png"
        xml_path = root / f"{testcase.id}_{item.step_id}.xml"
        color = (120, 185, 255) if item.status == "passed" else (255, 120, 120)
        _write_png(screen_path, 360, 720, color)
        xml_path.write_text(
            (
                "<hierarchy>"
                f"<node id='title' text='{testcase.name}' width='320' height='56'/>"
                "<node id='button_login' text='Login' width='160' height='48'/>"
                f"<node id='route' text='{item.route}' width='320' height='18'/>"
                "</hierarchy>"
            ),
            encoding="utf-8",
        )
        artifacts.append(
            CollectedPageData(
                step_id=item.step_id,
                screenshot_path=str(screen_path),
                xml_path=str(xml_path),
                route=item.route,
            )
        )
    return artifacts
