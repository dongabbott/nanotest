# filepath: d:\project\nanotest\apps\backend\app\repositories\test_run_repository.py
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc
from app.domain.models import TestRun, TestRunNode, TestStepResult
from app.repositories.base import BaseRepository


class TestRunRepository(BaseRepository[TestRun]):
    """Repository for TestRun operations."""
    
    def __init__(self, db: Session):
        super().__init__(TestRun, db)
    
    def get_by_project(
        self, 
        project_id: UUID, 
        *, 
        status: Optional[str] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[TestRun]:
        """Get all test runs for a project."""
        query = select(TestRun).where(TestRun.project_id == project_id)
        
        if status:
            query = query.where(TestRun.status == status)
        
        query = query.order_by(desc(TestRun.started_at)).offset(skip).limit(limit)
        result = self.db.execute(query)
        return list(result.scalars().all())
    
    def get_by_flow(self, flow_id: UUID, limit: int = 10) -> List[TestRun]:
        """Get recent runs for a specific flow."""
        query = (
            select(TestRun)
            .where(TestRun.flow_id == flow_id)
            .order_by(desc(TestRun.started_at))
            .limit(limit)
        )
        result = self.db.execute(query)
        return list(result.scalars().all())
    
    def update_status(
        self, 
        run_id: UUID, 
        status: str, 
        summary: Optional[dict] = None,
        finished_at: Optional[datetime] = None
    ) -> Optional[TestRun]:
        """Update run status and summary."""
        run = self.get(run_id)
        if run:
            run.status = status
            if summary:
                run.summary = summary
            if finished_at:
                run.finished_at = finished_at
            self.db.commit()
            self.db.refresh(run)
        return run
    
    def generate_run_no(self, project_id: UUID) -> str:
        """Generate a unique run number for a project."""
        from sqlalchemy import func
        query = select(func.count()).select_from(TestRun).where(
            TestRun.project_id == project_id
        )
        result = self.db.execute(query)
        count = result.scalar() or 0
        return f"RUN-{count + 1:05d}"


class TestRunNodeRepository(BaseRepository[TestRunNode]):
    """Repository for TestRunNode operations."""
    
    def __init__(self, db: Session):
        super().__init__(TestRunNode, db)
    
    def get_by_run(self, run_id: UUID) -> List[TestRunNode]:
        """Get all nodes for a test run."""
        query = select(TestRunNode).where(TestRunNode.test_run_id == run_id)
        result = self.db.execute(query)
        return list(result.scalars().all())
    
    def update_node_status(
        self, 
        node_id: UUID, 
        status: str,
        duration_ms: Optional[int] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Optional[TestRunNode]:
        """Update node execution status."""
        node = self.get(node_id)
        if node:
            node.status = status
            if duration_ms is not None:
                node.duration_ms = duration_ms
            if error_code:
                node.error_code = error_code
            if error_message:
                node.error_message = error_message
            self.db.commit()
            self.db.refresh(node)
        return node


class TestStepResultRepository(BaseRepository[TestStepResult]):
    """Repository for TestStepResult operations."""
    
    def __init__(self, db: Session):
        super().__init__(TestStepResult, db)
    
    def get_by_node(self, run_node_id: UUID) -> List[TestStepResult]:
        """Get all step results for a run node."""
        query = (
            select(TestStepResult)
            .where(TestStepResult.run_node_id == run_node_id)
            .order_by(TestStepResult.step_index)
        )
        result = self.db.execute(query)
        return list(result.scalars().all())
    
    def create_step_result(
        self,
        run_node_id: UUID,
        step_index: int,
        action: str,
        input_payload: dict,
        status: str,
        assertion_result: Optional[dict] = None,
        screenshot_object_key: Optional[str] = None,
        raw_log_object_key: Optional[str] = None
    ) -> TestStepResult:
        """Create a new step result."""
        step = TestStepResult(
            run_node_id=run_node_id,
            step_index=step_index,
            action=action,
            input_payload=input_payload,
            status=status,
            assertion_result=assertion_result,
            screenshot_object_key=screenshot_object_key,
            raw_log_object_key=raw_log_object_key
        )
        self.db.add(step)
        self.db.commit()
        self.db.refresh(step)
        return step
