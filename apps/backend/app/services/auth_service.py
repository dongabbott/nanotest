# filepath: d:\project\nanotest\apps\backend\app\services\auth_service.py
"""Authentication service for user login and token management."""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import settings
from app.core.security import verify_password, create_access_token, get_password_hash
from app.domain.models import User, Tenant
from app.schemas.schemas import LoginRequest, LoginResponse, UserResponse, UserCreate


class AuthService:
    """Service for authentication operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def authenticate(self, email: str, password: str) -> Optional[User]:
        """Authenticate a user by email and password."""
        query = select(User).where(User.email == email, User.is_active == True)
        result = self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        if not verify_password(password, user.password_hash):
            return None
        
        return user
    
    def login(self, login_request: LoginRequest) -> Optional[LoginResponse]:
        """Login a user and return tokens."""
        user = self.authenticate(login_request.email, login_request.password)
        
        if not user:
            return None
        
        # Create access token
        access_token = create_access_token(
            subject=str(user.id),
            tenant_id=str(user.tenant_id),
            role=user.role,
        )
        
        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse(
                id=user.id,
                email=user.email,
                name=user.name,
                role=user.role,
                tenant_id=user.tenant_id,
                is_active=user.is_active,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
        )
    
    def create_user(self, user_data: UserCreate, tenant_id: UUID) -> User:
        """Create a new user."""
        user = User(
            email=user_data.email,
            name=user_data.name,
            password_hash=get_password_hash(user_data.password),
            role=user_data.role,
            tenant_id=tenant_id,
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get a user by ID."""
        return self.db.get(User, user_id)
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by email."""
        query = select(User).where(User.email == email)
        result = self.db.execute(query)
        return result.scalar_one_or_none()
    
    def create_tenant(self, name: str) -> Tenant:
        """Create a new tenant."""
        tenant = Tenant(name=name, status="active")
        self.db.add(tenant)
        self.db.commit()
        self.db.refresh(tenant)
        return tenant
