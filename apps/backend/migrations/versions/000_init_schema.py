"""init schema

Revision ID: 000_init_schema
Revises: 
Create Date: 2026-03-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '000_init_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tenants',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, server_default='qa'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'projects',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('platform', sa.String(50), nullable=False),
        sa.Column('repo_url', sa.String(500), nullable=True),
        sa.Column('default_branch', sa.String(100), nullable=False, server_default='main'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'test_cases',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('dsl_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('dsl_content', postgresql.JSON(), nullable=False),
        sa.Column('tags', postgresql.JSON(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'test_case_versions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('test_case_id', sa.String(36), sa.ForeignKey('test_cases.id'), nullable=False),
        sa.Column('version_no', sa.Integer(), nullable=False),
        sa.Column('dsl_content', postgresql.JSON(), nullable=False),
        sa.Column('change_log', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'test_flows',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('graph_json', postgresql.JSON(), nullable=False),
        sa.Column('entry_node', sa.String(100), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'flow_node_bindings',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('flow_id', sa.String(36), sa.ForeignKey('test_flows.id'), nullable=False),
        sa.Column('node_key', sa.String(100), nullable=False),
        sa.Column('test_case_id', sa.String(36), sa.ForeignKey('test_cases.id'), nullable=False),
        sa.Column('retry_policy', postgresql.JSON(), nullable=False),
        sa.Column('timeout_sec', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'devices',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('udid', sa.String(255), nullable=False),
        sa.Column('platform', sa.String(50), nullable=False),
        sa.Column('platform_version', sa.String(50), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('manufacturer', sa.String(100), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='available'),
        sa.Column('capabilities', postgresql.JSON(), nullable=False),
        sa.Column('tags', postgresql.JSON(), nullable=False),
        sa.Column('last_heartbeat', sa.DateTime(), nullable=True),
        sa.Column('current_run_id', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'test_plans',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('trigger_type', sa.String(50), nullable=False, server_default='manual'),
        sa.Column('cron_expr', sa.String(100), nullable=True),
        sa.Column('flow_id', sa.String(36), sa.ForeignKey('test_flows.id'), nullable=False),
        sa.Column('env_config', postgresql.JSON(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'test_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('plan_id', sa.String(36), sa.ForeignKey('test_plans.id'), nullable=True),
        sa.Column('flow_id', sa.String(36), sa.ForeignKey('test_flows.id'), nullable=False),
        sa.Column('run_no', sa.String(100), nullable=False, unique=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='queued'),
        sa.Column('triggered_by', sa.String(36), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('summary', postgresql.JSON(), nullable=False),
        sa.Column('env_config', postgresql.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'test_run_nodes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('test_run_id', sa.String(36), sa.ForeignKey('test_runs.id'), nullable=False),
        sa.Column('node_key', sa.String(100), nullable=False),
        sa.Column('test_case_id', sa.String(36), nullable=False),
        sa.Column('device_id', sa.String(36), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('attempt', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('error_code', sa.String(100), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'test_step_results',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('run_node_id', sa.String(36), sa.ForeignKey('test_run_nodes.id'), nullable=False),
        sa.Column('step_index', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('input_payload', postgresql.JSON(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('assertion_result', postgresql.JSON(), nullable=False),
        sa.Column('screenshot_object_key', sa.String(500), nullable=True),
        sa.Column('page_source_object_key', sa.String(500), nullable=True),
        sa.Column('raw_log_object_key', sa.String(500), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'screen_analyses',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('test_step_result_id', sa.String(36), sa.ForeignKey('test_step_results.id'), nullable=False),
        sa.Column('model_name', sa.String(100), nullable=False),
        sa.Column('prompt_version', sa.String(50), nullable=False),
        sa.Column('analysis_type', sa.String(50), nullable=False),
        sa.Column('result_json', postgresql.JSON(), nullable=False),
        sa.Column('confidence', sa.Numeric(5, 4), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'run_comparisons',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('baseline_run_id', sa.String(36), nullable=False),
        sa.Column('target_run_id', sa.String(36), nullable=False),
        sa.Column('diff_summary', postgresql.JSON(), nullable=False),
        sa.Column('risk_score', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('report_object_key', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'risk_signals',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('test_run_id', sa.String(36), sa.ForeignKey('test_runs.id'), nullable=False),
        sa.Column('signal_type', sa.String(50), nullable=False),
        sa.Column('weight', sa.Numeric(5, 2), nullable=False),
        sa.Column('value', sa.Numeric(10, 4), nullable=False),
        sa.Column('evidence_json', postgresql.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=False),
        sa.Column('resource_id', sa.String(36), nullable=True),
        sa.Column('payload', postgresql.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'event_outbox',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('aggregate_id', sa.String(36), nullable=False),
        sa.Column('payload', postgresql.JSON(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('event_outbox')
    op.drop_table('audit_logs')
    op.drop_table('risk_signals')
    op.drop_table('run_comparisons')
    op.drop_table('screen_analyses')
    op.drop_table('test_step_results')
    op.drop_table('test_run_nodes')
    op.drop_table('test_runs')
    op.drop_table('test_plans')
    op.drop_table('devices')
    op.drop_table('flow_node_bindings')
    op.drop_table('test_flows')
    op.drop_table('test_case_versions')
    op.drop_table('test_cases')
    op.drop_table('projects')
    op.drop_table('users')
    op.drop_table('tenants')
