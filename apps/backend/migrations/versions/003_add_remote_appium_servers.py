"""add remote_appium_servers table

Revision ID: 003_add_remote_appium_servers
Revises: 002_add_app_packages_local_path
Create Date: 2026-02-25

"""
from alembic import op
import sqlalchemy as sa


revision = "003_add_remote_appium_servers"
down_revision = "002_add_app_packages_local_path"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "remote_appium_servers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default="4723"),
        sa.Column("path", sa.String(255), nullable=False, server_default=""),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("password", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="unknown"),
        sa.Column("last_connected", sa.DateTime(), nullable=True),
        sa.Column("device_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )

    op.create_index("ix_remote_appium_servers_tenant", "remote_appium_servers", ["tenant_id"])
    op.create_index("ix_remote_appium_servers_host_port", "remote_appium_servers", ["host", "port"])


def downgrade() -> None:
    op.drop_index("ix_remote_appium_servers_host_port", table_name="remote_appium_servers")
    op.drop_index("ix_remote_appium_servers_tenant", table_name="remote_appium_servers")
    op.drop_table("remote_appium_servers")

