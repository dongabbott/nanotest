from __future__ import annotations

import argparse

from .dashboard import serve_dashboard
from .pipeline import Pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="NanoTest pipeline")
    parser.add_argument("dsl", help="Path to YAML/JSON testcase")
    parser.add_argument("--workspace", default="outputs")
    parser.add_argument("--serve", action="store_true", help="Start dashboard server after run")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()

    pipeline = Pipeline(workspace=args.workspace)
    report, path = pipeline.run(args.dsl)
    print(f"report_id={report.id}")
    print(f"report_path={path}")

    if args.serve:
        serve_dashboard(args.workspace, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
