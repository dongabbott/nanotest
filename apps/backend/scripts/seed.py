"""Seed script to create initial data."""
import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from app.core.config import settings
from app.core.security import get_password_hash
from app.domain.models import Base, Tenant, User


async def seed_database():
    """Create initial tenant and admin user."""
    engine = create_async_engine(settings.database_url, echo=True)
    
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        # Check if tenant exists, create if not
        result = await session.execute(select(Tenant).limit(1))
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            tenant = Tenant(
                id=uuid.uuid4(),
                name="Default Tenant",
                status="active"
            )
            session.add(tenant)
            await session.flush()
            print("Created default tenant")
        
        # Check if users exist
        result = await session.execute(select(User).limit(1))
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            print("Users already exist, skipping...")
            return
        
        # Create admin user
        admin_user = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email="admin@nanotest.com",
            name="Admin User",
            hashed_password=get_password_hash("admin123"),
            role="admin",
            is_active=True
        )
        session.add(admin_user)
        
        # Create test user
        test_user = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email="test@example.com",
            name="Test User",
            hashed_password=get_password_hash("password123"),
            role="qa",
            is_active=True
        )
        session.add(test_user)
        
        await session.commit()
        
        print("=" * 50)
        print("Database seeded successfully!")
        print("=" * 50)
        print("\nDefault accounts created:")
        print("-" * 50)
        print(f"Admin:  admin@nanotest.com / admin123")
        print(f"Test:   test@example.com / password123")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(seed_database())
