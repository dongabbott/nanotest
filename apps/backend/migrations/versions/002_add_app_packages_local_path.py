"""add app_packages local_path

Revision ID: 002_add_app_packages_local_path
Revises: 001_add_app_packages
Create Date: 2026-02-25

"""
from alembic import op
import sqlalchemy as sa


revision = "002_add_app_packages_local_path"
down_revision = "001_add_app_packages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_packages", sa.Column("local_path", sa.String(1000), nullable=True))


def downgrade() -> None:
    op.drop_column("app_packages", "local_path")

