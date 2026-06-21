"""Initial schema with users, submissions, and admin action logs.

Revision ID: 001_initial_schema
Revises: 
Create Date: 2025-12-16 18:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema."""
    
    # Create enums explicitly. create_type=False prevents the subsequent
    # create_table() calls from emitting a second CREATE TYPE (which would fail
    # with "type already exists").
    submission_status_enum = postgresql.ENUM(
        'pending', 'approved', 'rejected', 'published',
        'accepted_not_published', 'publication_failed', 'scheduled',
        name='submissionstatus',
        create_type=False
    )
    submission_status_enum.create(op.get_bind(), checkfirst=True)

    # Create admin_action_type enum
    admin_action_type_enum = postgresql.ENUM(
        'approve_publish', 'approve_only', 'reject', 'block_user',
        'unblock_user', 'add_note', 'edit_note', 'cancel_publication',
        name='actiontype',
        create_type=False
    )
    admin_action_type_enum.create(op.get_bind(), checkfirst=True)
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('first_name', sa.String(length=255), nullable=True),
        sa.Column('last_name', sa.String(length=255), nullable=True),
        sa.Column('is_blocked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('admin_note', sa.Text(), nullable=True),
        sa.Column('total_submissions_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('registration_timestamp', sa.DateTime(), nullable=False),
        sa.Column('last_interaction_timestamp', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('user_id'),
        sa.CheckConstraint('total_submissions_count >= 0', name='check_submissions_non_negative')
    )
    
    # Create index on username
    op.create_index('ix_users_username', 'users', ['username'])
    op.create_index('ix_users_is_blocked', 'users', ['is_blocked'])
    op.create_index('ix_users_registration_timestamp', 'users', ['registration_timestamp'])
    
    # Create submissions table
    op.create_table(
        'submissions',
        sa.Column('submission_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('submission_timestamp', sa.DateTime(), nullable=False),
        sa.Column('status', submission_status_enum, nullable=False),
        sa.Column('moderator_id', sa.BigInteger(), nullable=True),
        sa.Column('decision_timestamp', sa.DateTime(), nullable=True),
        sa.Column('show_authorship', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('message_id_in_admin_chat', sa.BigInteger(), nullable=True),
        sa.Column('message_id_in_channel', sa.BigInteger(), nullable=True),
        sa.Column('user_message_id', sa.BigInteger(), nullable=True),
        sa.Column('user_chat_id', sa.BigInteger(), nullable=True),
        sa.Column('has_media', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('media_type', sa.String(length=50), nullable=True),
        sa.Column('media_file_id', sa.String(length=255), nullable=True),
        sa.Column('text_content', sa.Text(), nullable=True),
        sa.Column('scheduled_publication_time', sa.DateTime(), nullable=True),
        sa.Column('publication_error_message', sa.Text(), nullable=True),
        sa.Column('publication_retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('submission_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE')
    )
    
    # Create indexes on submissions
    op.create_index('ix_submissions_user_id', 'submissions', ['user_id'])
    op.create_index('ix_submissions_status', 'submissions', ['status'])
    op.create_index('ix_submissions_submission_timestamp', 'submissions', ['submission_timestamp'])
    op.create_index('ix_submissions_moderator_id', 'submissions', ['moderator_id'])
    op.create_index('ix_submissions_scheduled_publication_time', 'submissions', ['scheduled_publication_time'])
    
    # Create admin_action_logs table
    op.create_table(
        'admin_action_logs',
        sa.Column('log_id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('action_type', admin_action_type_enum, nullable=False),
        sa.Column('admin_user_id', sa.BigInteger(), nullable=False),
        sa.Column('target_user_id', sa.BigInteger(), nullable=True),
        sa.Column('submission_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action_timestamp', sa.DateTime(), nullable=False),
        sa.Column('additional_context', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('log_id'),
        sa.ForeignKeyConstraint(['submission_id'], ['submissions.submission_id'], ondelete='CASCADE')
    )
    
    # Create indexes on admin_action_logs
    op.create_index('ix_admin_action_logs_submission_id', 'admin_action_logs', ['submission_id'])
    op.create_index('ix_admin_action_logs_admin_user_id', 'admin_action_logs', ['admin_user_id'])
    op.create_index('ix_admin_action_logs_action_timestamp', 'admin_action_logs', ['action_timestamp'])


def downgrade() -> None:
    """Drop all tables and enums."""
    
    # Drop tables
    op.drop_index('ix_users_registration_timestamp', table_name='users')
    op.drop_table('admin_action_logs')
    op.drop_table('submissions')
    op.drop_table('users')
    
    # Drop enums
    sa.Enum(name='actiontype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='submissionstatus').drop(op.get_bind(), checkfirst=True)
