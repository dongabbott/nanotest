"""Task status API endpoints (Celery AsyncResult polling)."""

from typing import Annotated, Any, Optional

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.auth import get_current_active_user
from app.domain.models import User
from app.schemas.schemas import TaskStatusResponse
from app.tasks.celery_app import celery_app

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get Celery task status by task_id."""
    try:
        res = AsyncResult(task_id, app=celery_app)

        payload: dict[str, Any] = {
            "task_id": task_id,
            "state": res.state,
            "status": getattr(res, "status", None),
        }

        if res.successful():
            r = res.result
            payload["result"] = r if isinstance(r, dict) else {"value": r}
        elif res.failed():
            payload["error"] = str(res.result)

        return TaskStatusResponse(**payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {e}")
