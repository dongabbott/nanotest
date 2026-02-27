"""add page_source_object_key to test_step_results

Revision ID: 004_add_page_source_object_key
Revises: 003_add_remote_appium_servers
Create Date: 2026-02-27

"""
from alembic import op
import sqlalchemy as sa


revision = "004_add_page_source_object_key"
down_revision = "003_add_remote_appium_servers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "test_step_results",
        sa.Column("page_source_object_key", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("test_step_results", "page_source_object_key")
