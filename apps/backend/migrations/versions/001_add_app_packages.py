"""add app_packages table

Revision ID: 001_add_app_packages
Revises: 
Create Date: 2026-02-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_add_app_packages'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'app_packages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
        
        # Basic info
        sa.Column('filename', sa.String(500), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('file_hash', sa.String(64), nullable=False),
        sa.Column('object_key', sa.String(500), nullable=False),
        
        # Platform
        sa.Column('platform', sa.String(20), nullable=False),
        
        # Parsed metadata
        sa.Column('package_name', sa.String(500), nullable=False),
        sa.Column('app_name', sa.String(255), nullable=True),
        sa.Column('version_name', sa.String(100), nullable=False),
        sa.Column('version_code', sa.Integer(), nullable=True),
        sa.Column('build_number', sa.String(100), nullable=True),
        
        # Android specific
        sa.Column('min_sdk_version', sa.Integer(), nullable=True),
        sa.Column('target_sdk_version', sa.Integer(), nullable=True),
        sa.Column('app_activity', sa.String(500), nullable=True),
        sa.Column('app_package', sa.String(500), nullable=True),
        
        # iOS specific
        sa.Column('bundle_id', sa.String(500), nullable=True),
        sa.Column('minimum_os_version', sa.String(50), nullable=True),
        sa.Column('supported_platforms', sa.JSON(), nullable=True),
        
        # Additional metadata
        sa.Column('permissions', sa.JSON(), nullable=True),
        sa.Column('icon_object_key', sa.String(500), nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=False, default=dict),
        
        # Status
        sa.Column('status', sa.String(50), nullable=False, default='active'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=False, default=list),
        
        # Uploader
        sa.Column('uploaded_by', sa.String(36), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
    )
    
    # Create indexes
    op.create_index('ix_app_packages_project_platform', 'app_packages', ['project_id', 'platform'])
    op.create_index('ix_app_packages_package_name', 'app_packages', ['package_name'])
    op.create_index('ix_app_packages_tenant', 'app_packages', ['tenant_id'])


def downgrade() -> None:
    op.drop_index('ix_app_packages_tenant', 'app_packages')
    op.drop_index('ix_app_packages_package_name', 'app_packages')
    op.drop_index('ix_app_packages_project_platform', 'app_packages')
    op.drop_table('app_packages')
