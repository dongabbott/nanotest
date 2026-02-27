"""DSL helper endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/dsl", tags=["DSL"])


@router.get("/generators")
def list_generators():
    """List supported ${...} generator functions for DSL inputs."""
    import sys
    import os

    # Resolve: apps/backend/app/api/v1/dsl.py -> apps/worker
    backend_app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    apps_dir = os.path.abspath(os.path.join(backend_app_dir, ".."))
    worker_root = os.path.join(apps_dir, "worker")

    if worker_root not in sys.path:
        sys.path.insert(0, worker_root)

    from runners.text_generators import GENERATORS  # type: ignore

    return {"items": GENERATORS}
