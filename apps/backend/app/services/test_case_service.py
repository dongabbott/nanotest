# filepath: d:\project\nanotest\apps\backend\app\services\test_case_service.py
"""Test case service for business logic."""
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.models import TestCase, TestCaseVersion
from app.repositories.test_case_repository import TestCaseRepository
from app.schemas.schemas import (
    TestCaseCreate, 
    TestCaseUpdate, 
    TestCaseResponse, 
    TestCaseListResponse,
    TestCaseVersionResponse,
    ValidateDSLRequest,
    ValidateDSLResponse,
)


class TestCaseService:
    """Service for test case operations."""
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = TestCaseRepository(db)
    
    def create_test_case(self, project_id: UUID, test_case_data: TestCaseCreate) -> TestCase:
        """Create a new test case."""
        # Check if test case with same name exists
        existing = self.repository.get_by_name(project_id, test_case_data.name)
        if existing:
            raise ValueError(f"Test case with name '{test_case_data.name}' already exists")
        
        # Validate DSL content
        validation = self.validate_dsl(ValidateDSLRequest(dsl_content=test_case_data.dsl_content))
        if not validation.valid:
            raise ValueError(f"Invalid DSL content: {', '.join(validation.errors)}")
        
        test_case_dict = test_case_data.model_dump()
        test_case_dict["project_id"] = project_id
        test_case_dict["dsl_version"] = 1
        
        return self.repository.create(obj_in=test_case_dict)
    
    def get_test_case(self, test_case_id: UUID) -> Optional[TestCase]:
        """Get a test case by ID."""
        return self.repository.get(test_case_id)
    
    def list_test_cases(
        self, 
        project_id: UUID, 
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
        page: int = 1, 
        page_size: int = 20
    ) -> TestCaseListResponse:
        """List all test cases for a project with pagination."""
        skip = (page - 1) * page_size
        test_cases = self.repository.get_by_project(
            project_id, 
            status=status, 
            tags=tags,
            skip=skip, 
            limit=page_size
        )
        total = self.repository.count(filters={"project_id": project_id})
        
        return TestCaseListResponse(
            items=[TestCaseResponse.model_validate(tc) for tc in test_cases],
            total=total,
            page=page,
            page_size=page_size,
        )
    
    def update_test_case(
        self, 
        test_case_id: UUID, 
        test_case_data: TestCaseUpdate,
        user_id: Optional[UUID] = None
    ) -> Optional[TestCase]:
        """Update a test case."""
        test_case = self.repository.get(test_case_id)
        if not test_case:
            return None
        
        update_data = test_case_data.model_dump(exclude_unset=True)
        
        # If DSL content is being updated, validate and create a new version
        if "dsl_content" in update_data and update_data["dsl_content"]:
            validation = self.validate_dsl(ValidateDSLRequest(dsl_content=test_case_data.dsl_content))
            if not validation.valid:
                raise ValueError(f"Invalid DSL content: {', '.join(validation.errors)}")
            
            # Create a version snapshot
            self.repository.create_version(
                test_case_id=test_case_id,
                dsl_content=test_case.dsl_content,  # Save current content as version
                change_log="Auto-saved before update",
                created_by=user_id
            )
            
            # Increment version number
            update_data["dsl_version"] = test_case.dsl_version + 1
        
        return self.repository.update(id=test_case_id, obj_in=update_data)
    
    def delete_test_case(self, test_case_id: UUID) -> bool:
        """Delete a test case."""
        return self.repository.delete(id=test_case_id)
    
    def get_versions(self, test_case_id: UUID) -> List[TestCaseVersionResponse]:
        """Get all versions of a test case."""
        versions = self.repository.get_versions(test_case_id)
        return [TestCaseVersionResponse.model_validate(v) for v in versions]
    
    def create_version(
        self, 
        test_case_id: UUID, 
        change_log: Optional[str],
        user_id: UUID
    ) -> TestCaseVersion:
        """Create a new version snapshot of a test case."""
        test_case = self.repository.get(test_case_id)
        if not test_case:
            raise ValueError("Test case not found")
        
        return self.repository.create_version(
            test_case_id=test_case_id,
            dsl_content=test_case.dsl_content,
            change_log=change_log or "Manual version snapshot",
            created_by=user_id
        )
    
    def validate_dsl(self, request: ValidateDSLRequest) -> ValidateDSLResponse:
        """Validate DSL content."""
        errors = []
        warnings = []
        
        dsl = request.dsl_content
        
        # Basic validation
        if not dsl.name:
            errors.append("Test case name is required")
        
        if not dsl.steps or len(dsl.steps) == 0:
            errors.append("At least one test step is required")
        
        # Validate each step
        valid_actions = {
            "tap", "click", "input", "swipe", "scroll", "wait", 
            "assert_visible", "assert_text", "assert_exists",
            "screenshot", "back", "home", "launch_app", "close_app"
        }
        
        for i, step in enumerate(dsl.steps):
            if step.action not in valid_actions:
                warnings.append(f"Step {i+1}: Unknown action '{step.action}'")
            
            # Check if target is required for certain actions
            target_required_actions = {"tap", "click", "input", "assert_visible", "assert_text", "assert_exists"}
            if step.action in target_required_actions and not step.target:
                errors.append(f"Step {i+1}: Action '{step.action}' requires a target")
            
            # Check if value is required for input action
            if step.action == "input" and not step.value:
                errors.append(f"Step {i+1}: Action 'input' requires a value")
        
        return ValidateDSLResponse(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
