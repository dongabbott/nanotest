# filepath: d:\project\nanotest\apps\backend\app\repositories\project_repository.py
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.domain.models import Project
from app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """Repository for Project operations."""
    
    def __init__(self, db: Session):
        super().__init__(Project, db)
    
    def get_by_tenant(
        self, 
        tenant_id: UUID, 
        *, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Project]:
        """Get all projects for a tenant."""
        query = (
            select(Project)
            .where(Project.tenant_id == tenant_id)
            .offset(skip)
            .limit(limit)
        )
        result = self.db.execute(query)
        return list(result.scalars().all())
    
    def get_by_name(self, tenant_id: UUID, name: str) -> Optional[Project]:
        """Get a project by name within a tenant."""
        query = select(Project).where(
            Project.tenant_id == tenant_id,
            Project.name == name
        )
        result = self.db.execute(query)
        return result.scalar_one_or_none()
