# filepath: d:\project\nanotest\apps\backend\app\repositories\test_case_repository.py
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from app.domain.models import TestCase, TestCaseVersion
from app.repositories.base import BaseRepository


class TestCaseRepository(BaseRepository[TestCase]):
    """Repository for TestCase operations."""
    
    def __init__(self, db: Session):
        super().__init__(TestCase, db)
    
    def get_by_project(
        self, 
        project_id: UUID, 
        *, 
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[TestCase]:
        """Get all test cases for a project with optional filters."""
        query = select(TestCase).where(TestCase.project_id == project_id)
        
        if status:
            query = query.where(TestCase.status == status)
        
        if tags:
            # Use PostgreSQL JSONB contains operator
            for tag in tags:
                query = query.where(TestCase.tags.contains([tag]))
        
        query = query.offset(skip).limit(limit)
        result = self.db.execute(query)
        return list(result.scalars().all())
    
    def get_by_name(self, project_id: UUID, name: str) -> Optional[TestCase]:
        """Get a test case by name within a project."""
        query = select(TestCase).where(
            and_(TestCase.project_id == project_id, TestCase.name == name)
        )
        result = self.db.execute(query)
        return result.scalar_one_or_none()
    
    def create_version(
        self, 
        test_case_id: UUID, 
        dsl_content: dict,
        change_log: str,
        created_by: UUID
    ) -> TestCaseVersion:
        """Create a new version for a test case."""
        # Get current max version
        query = select(TestCaseVersion).where(
            TestCaseVersion.test_case_id == test_case_id
        ).order_by(TestCaseVersion.version_no.desc()).limit(1)
        result = self.db.execute(query)
        latest = result.scalar_one_or_none()
        
        new_version_no = (latest.version_no + 1) if latest else 1
        
        version = TestCaseVersion(
            test_case_id=test_case_id,
            version_no=new_version_no,
            dsl_content=dsl_content,
            change_log=change_log,
            created_by=created_by
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version
    
    def get_versions(self, test_case_id: UUID) -> List[TestCaseVersion]:
        """Get all versions of a test case."""
        query = (
            select(TestCaseVersion)
            .where(TestCaseVersion.test_case_id == test_case_id)
            .order_by(TestCaseVersion.version_no.desc())
        )
        result = self.db.execute(query)
        return list(result.scalars().all())
