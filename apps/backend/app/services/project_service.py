# filepath: d:\project\nanotest\apps\backend\app\services\project_service.py
"""Project service for business logic."""
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.models import Project
from app.repositories.project_repository import ProjectRepository
from app.schemas.schemas import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse


class ProjectService:
    """Service for project operations."""
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjectRepository(db)
    
    def create_project(self, tenant_id: UUID, project_data: ProjectCreate) -> Project:
        """Create a new project."""
        # Check if project with same name exists
        existing = self.repository.get_by_name(tenant_id, project_data.name)
        if existing:
            raise ValueError(f"Project with name '{project_data.name}' already exists")
        
        project_dict = project_data.model_dump()
        project_dict["tenant_id"] = tenant_id
        
        return self.repository.create(obj_in=project_dict)
    
    def get_project(self, project_id: UUID, tenant_id: UUID) -> Optional[Project]:
        """Get a project by ID, ensuring it belongs to the tenant."""
        project = self.repository.get(project_id)
        if project and project.tenant_id == tenant_id:
            return project
        return None
    
    def list_projects(
        self, 
        tenant_id: UUID, 
        page: int = 1, 
        page_size: int = 20
    ) -> ProjectListResponse:
        """List all projects for a tenant with pagination."""
        skip = (page - 1) * page_size
        projects = self.repository.get_by_tenant(tenant_id, skip=skip, limit=page_size)
        total = self.repository.count(filters={"tenant_id": tenant_id})
        
        return ProjectListResponse(
            items=[ProjectResponse.model_validate(p) for p in projects],
            total=total,
            page=page,
            page_size=page_size,
        )
    
    def update_project(
        self, 
        project_id: UUID, 
        tenant_id: UUID, 
        project_data: ProjectUpdate
    ) -> Optional[Project]:
        """Update a project."""
        project = self.get_project(project_id, tenant_id)
        if not project:
            return None
        
        update_data = project_data.model_dump(exclude_unset=True)
        return self.repository.update(id=project_id, obj_in=update_data)
    
    def delete_project(self, project_id: UUID, tenant_id: UUID) -> bool:
        """Delete a project."""
        project = self.get_project(project_id, tenant_id)
        if not project:
            return False
        
        return self.repository.delete(id=project_id)
