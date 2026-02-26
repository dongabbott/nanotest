"""Celery tasks package."""
from app.tasks.celery_app import celery_app
from app.tasks.analysis import (
    analyze_test_run,
    compare_test_runs,
    calculate_risk_signals,
)
from app.tasks.execution import (
    execute_test_run,
    execute_single_node as execute_test_node,
)
from app.tasks.reports import (
    generate_run_report,
    generate_project_summary,
    aggregate_comparison_report,
    cleanup_old_reports,
)

__all__ = [
    "celery_app",
    # Analysis tasks
    "analyze_test_run",
    "compare_test_runs",
    "calculate_risk_signals",
    # Execution tasks
    "execute_test_run",
    "execute_test_node",
    # Report tasks
    "generate_run_report",
    "generate_project_summary",
    "aggregate_comparison_report",
    "cleanup_old_reports",
]
