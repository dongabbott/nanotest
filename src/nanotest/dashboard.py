from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote


def _render_html(report: dict, case_id: str, report_file: str) -> str:
    issues = "".join(
        f"<li>[{i['severity']}] {i['kind']} - {i['description']} (step: {i['step_id']})</li>" for i in report["issues"]
    ) or "<li>无</li>"
    regressions = "".join(
        f"<li>{r['step_id']} - diff_score={r['diff_score']}</li>" for r in report["regressions"]
    ) or "<li>暂无明显差异</li>"
    suggestions = "".join(f"<li>{s}</li>" for s in report["suggestions"])
    return f"""<!DOCTYPE html><html lang='zh-CN'><head><meta charset='UTF-8'><title>NanoTest 报告</title>
<style>body{{font-family:Arial;background:#f5f7fb;padding:24px}}.card{{background:#fff;padding:16px;border-radius:10px;margin-bottom:12px}}</style></head>
<body><div class='card'><h1>NanoTest 报告</h1><p>Case: <code>{case_id}</code> / <code>{report_file}</code></p><h2>风险评分：{report['risk_score']}</h2></div>
<div class='card'><h3>建议</h3><ul>{suggestions}</ul></div>
<div class='card'><h3>UI问题</h3><ul>{issues}</ul></div>
<div class='card'><h3>回归差异</h3><ul>{regressions}</ul></div></body></html>"""


def serve_dashboard(report_root: str | Path = "outputs", host: str = "0.0.0.0", port: int = 8000) -> None:
    root = Path(report_root)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            path = unquote(self.path)
            if path.startswith("/api/reports/"):
                _, _, _, case_id, report_file = path.split("/", 4)
                report_path = root / case_id / report_file
                if not report_path.exists():
                    self.send_response(404)
                    self.end_headers()
                    return
                payload = report_path.read_text(encoding="utf-8").encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(payload)
                return

            if path.startswith("/reports/"):
                _, _, case_id, report_file = path.split("/", 3)
                report_path = root / case_id / report_file
                if not report_path.exists():
                    self.send_response(404)
                    self.end_headers()
                    return
                report = json.loads(report_path.read_text(encoding="utf-8"))
                html = _render_html(report, case_id, report_file).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html)
                return

            self.send_response(404)
            self.end_headers()

    ThreadingHTTPServer((host, port), Handler).serve_forever()
