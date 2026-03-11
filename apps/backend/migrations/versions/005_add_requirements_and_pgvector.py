"""add requirement management

Revision ID: 005_requirements
Revises: 004_add_page_source_object_key
Create Date: 2026-03-11

"""
from alembic import op
import sqlalchemy as sa


revision = "005_requirements"
down_revision = "004_add_page_source_object_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "requirements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("acceptance_criteria", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("business_rules", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("source_type", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("source_ref", sa.String(255), nullable=True),
        sa.Column("platform", sa.String(20), nullable=False, server_default="common"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_requirements_tenant_project_status", "requirements", ["tenant_id", "project_id", "status"])
    op.create_index("ix_requirements_project_priority", "requirements", ["project_id", "priority"])
    op.create_index("ix_requirements_project_updated", "requirements", ["project_id", "updated_at"])
    op.create_index("uq_requirements_project_key", "requirements", ["project_id", "key"], unique=True)

    op.create_table(
        "requirement_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("requirement_id", sa.String(36), sa.ForeignKey("requirements.id"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("change_log", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "uq_requirement_versions_requirement_version",
        "requirement_versions",
        ["requirement_id", "version_no"],
        unique=True,
    )

    op.create_table(
        "requirement_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("requirement_id", sa.String(36), sa.ForeignKey("requirements.id"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_type", sa.String(30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("embedding_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_requirement_chunks_project_requirement_version",
        "requirement_chunks",
        ["project_id", "requirement_id", "version_no"],
    )
    op.create_index("ix_requirement_chunks_project_status", "requirement_chunks", ["project_id", "embedding_status"])
    op.create_index("ix_requirement_chunks_project_type", "requirement_chunks", ["project_id", "chunk_type"])
    op.create_index(
        "uq_requirement_chunks_requirement_index",
        "requirement_chunks",
        ["requirement_id", "version_no", "chunk_index"],
        unique=True,
    )

    op.create_table(
        "requirement_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("requirement_id", sa.String(36), sa.ForeignKey("requirements.id"), nullable=False),
        sa.Column("target_type", sa.String(30), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("link_type", sa.String(30), nullable=False, server_default="covers"),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False, server_default="1.0"),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_requirement_links_requirement_target",
        "requirement_links",
        ["requirement_id", "target_type", "target_id"],
    )
    op.create_index(
        "ix_requirement_links_project_target",
        "requirement_links",
        ["project_id", "target_type", "target_id"],
    )
    op.create_index(
        "uq_requirement_links_unique",
        "requirement_links",
        ["requirement_id", "target_type", "target_id", "link_type"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_requirement_links_unique", table_name="requirement_links")
    op.drop_index("ix_requirement_links_project_target", table_name="requirement_links")
    op.drop_index("ix_requirement_links_requirement_target", table_name="requirement_links")
    op.drop_table("requirement_links")

    op.drop_index("uq_requirement_chunks_requirement_index", table_name="requirement_chunks")
    op.drop_index("ix_requirement_chunks_project_type", table_name="requirement_chunks")
    op.drop_index("ix_requirement_chunks_project_status", table_name="requirement_chunks")
    op.drop_index("ix_requirement_chunks_project_requirement_version", table_name="requirement_chunks")
    op.drop_table("requirement_chunks")

    op.drop_index("uq_requirement_versions_requirement_version", table_name="requirement_versions")
    op.drop_table("requirement_versions")

    op.drop_index("uq_requirements_project_key", table_name="requirements")
    op.drop_index("ix_requirements_project_updated", table_name="requirements")
    op.drop_index("ix_requirements_project_priority", table_name="requirements")
    op.drop_index("ix_requirements_tenant_project_status", table_name="requirements")
    op.drop_table("requirements")