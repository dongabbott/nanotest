# filepath: d:\project\nanotest\apps\backend\app\services\test_run_service.py
"""Test run service for business logic."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.models import TestRun, TestRunNode, TestStepResult
from app.repositories.test_run_repository import (
    TestRunRepository, 
    TestRunNodeRepository, 
    TestStepResultRepository
)
from app.services.test_flow_service import TestFlowService
from app.schemas.schemas import (
    TestRunCreate, 
    TestRunResponse, 
    TestRunListResponse,
    TestRunNodeResponse,
    TestStepResultResponse,
    TestRunDetailResponse,
)


class TestRunService:
    """Service for test run operations."""
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = TestRunRepository(db)
        self.node_repository = TestRunNodeRepository(db)
        self.step_repository = TestStepResultRepository(db)
        self.flow_service = TestFlowService(db)
    
    def create_test_run(
        self, 
        project_id: UUID, 
        run_data: TestRunCreate,
        triggered_by: UUID
    ) -> TestRun:
        """Create a new test run."""
        # Generate run number
        run_no = self.repository.generate_run_no(project_id)
        
        # Compile the flow to get execution order
        compiled = self.flow_service.compile_flow(run_data.flow_id)
        
        run_dict = {
            "project_id": project_id,
            "flow_id": run_data.flow_id,
            "run_no": run_no,
            "triggered_by": triggered_by,
            "trigger_type": run_data.trigger_type,
            "status": "pending",
            "config": run_data.config or {},
            "environment": run_data.environment or {},
            "started_at": datetime.utcnow(),
        }
        
        test_run = self.repository.create(obj_in=run_dict)
        
        # Create run nodes for each step in the flow
        for i, node in enumerate(compiled["execution_order"]):
            node_dict = {
                "test_run_id": test_run.id,
                "flow_node_id": node["id"],
                "test_case_id": node.get("data", {}).get("test_case_id"),
                "sequence": i,
                "status": "pending",
            }
            self.node_repository.create(obj_in=node_dict)
        
        return test_run
    
    def get_test_run(self, run_id: UUID) -> Optional[TestRun]:
        """Get a test run by ID."""
        return self.repository.get(run_id)
    
    def get_test_run_detail(self, run_id: UUID) -> Optional[TestRunDetailResponse]:
        """Get detailed test run information including nodes and steps."""
        run = self.repository.get(run_id)
        if not run:
            return None
        
        nodes = self.node_repository.get_by_run(run_id)
        
        node_responses = []
        for node in nodes:
            steps = self.step_repository.get_by_node(node.id)
            node_responses.append(TestRunNodeResponse(
                id=node.id,
                test_run_id=node.test_run_id,
                flow_node_id=node.flow_node_id,
                test_case_id=node.test_case_id,
                sequence=node.sequence,
                status=node.status,
                duration_ms=node.duration_ms,
                error_code=node.error_code,
                error_message=node.error_message,
                created_at=node.created_at,
                updated_at=node.updated_at,
                steps=[TestStepResultResponse.model_validate(s) for s in steps],
            ))
        
        return TestRunDetailResponse(
            id=run.id,
            project_id=run.project_id,
            flow_id=run.flow_id,
            run_no=run.run_no,
            status=run.status,
            triggered_by=run.triggered_by,
            trigger_type=run.trigger_type,
            config=run.config,
            environment=run.environment,
            started_at=run.started_at,
            finished_at=run.finished_at,
            summary=run.summary,
            created_at=run.created_at,
            updated_at=run.updated_at,
            nodes=node_responses,
        )
    
    def list_test_runs(
        self, 
        project_id: UUID, 
        status: Optional[str] = None,
        page: int = 1, 
        page_size: int = 20
    ) -> TestRunListResponse:
        """List all test runs for a project with pagination."""
        skip = (page - 1) * page_size
        runs = self.repository.get_by_project(
            project_id, 
            status=status,
            skip=skip, 
            limit=page_size
        )
        total = self.repository.count(filters={"project_id": project_id})
        
        return TestRunListResponse(
            items=[TestRunResponse.model_validate(r) for r in runs],
            total=total,
            page=page,
            page_size=page_size,
        )
    
    def update_run_status(
        self, 
        run_id: UUID, 
        status: str,
        summary: Optional[dict] = None
    ) -> Optional[TestRun]:
        """Update test run status."""
        finished_at = None
        if status in ("passed", "failed", "cancelled", "error"):
            finished_at = datetime.utcnow()
        
        return self.repository.update_status(
            run_id=run_id,
            status=status,
            summary=summary,
            finished_at=finished_at,
        )
    
    def update_node_status(
        self, 
        node_id: UUID, 
        status: str,
        duration_ms: Optional[int] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Optional[TestRunNode]:
        """Update test run node status."""
        return self.node_repository.update_node_status(
            node_id=node_id,
            status=status,
            duration_ms=duration_ms,
            error_code=error_code,
            error_message=error_message,
        )
    
    def add_step_result(
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
        """Add a step result to a run node."""
        return self.step_repository.create_step_result(
            run_node_id=run_node_id,
            step_index=step_index,
            action=action,
            input_payload=input_payload,
            status=status,
            assertion_result=assertion_result,
            screenshot_object_key=screenshot_object_key,
            raw_log_object_key=raw_log_object_key,
        )
    
    def cancel_run(self, run_id: UUID) -> Optional[TestRun]:
        """Cancel a running test."""
        run = self.repository.get(run_id)
        if not run:
            return None
        
        if run.status not in ("pending", "running"):
            raise ValueError(f"Cannot cancel run with status '{run.status}'")
        
        return self.update_run_status(run_id, "cancelled")
    
    def retry_run(self, run_id: UUID, triggered_by: UUID) -> TestRun:
        """Retry a failed test run."""
        original_run = self.repository.get(run_id)
        if not original_run:
            raise ValueError("Original run not found")
        
        if original_run.status not in ("failed", "error", "cancelled"):
            raise ValueError(f"Cannot retry run with status '{original_run.status}'")
        
        # Create a new run with the same configuration
        from app.schemas.schemas import TestRunCreate
        new_run_data = TestRunCreate(
            flow_id=original_run.flow_id,
            trigger_type="retry",
            config=original_run.config,
            environment=original_run.environment,
        )
        
        return self.create_test_run(
            project_id=original_run.project_id,
            run_data=new_run_data,
            triggered_by=triggered_by,
        )
    
    def get_run_statistics(self, project_id: UUID) -> dict:
        """Get statistics for test runs in a project."""
        from sqlalchemy import func, select
        
        # Count by status
        status_query = (
            select(TestRun.status, func.count(TestRun.id))
            .where(TestRun.project_id == project_id)
            .group_by(TestRun.status)
        )
        result = self.db.execute(status_query)
        status_counts = dict(result.all())
        
        # Total runs
        total = sum(status_counts.values())
        
        # Calculate pass rate
        passed = status_counts.get("passed", 0)
        completed = passed + status_counts.get("failed", 0)
        pass_rate = (passed / completed * 100) if completed > 0 else 0
        
        return {
            "total_runs": total,
            "status_breakdown": status_counts,
            "pass_rate": round(pass_rate, 2),
        }
