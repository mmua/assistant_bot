# src/bot/migrations/versions/202412_01_add_analysis_models.py

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime


# revision identifiers
revision = '202501_01'
down_revision = None  # Replace with your previous migration revision ID
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create TaskStatus enum type
    op.execute("""
        CREATE TYPE taskstatus AS ENUM (
            'pending',
            'in_progress',
            'completed',
            'cancelled'
        )
    """)

    # Create TaskPriority enum type
    op.execute("""
        CREATE TYPE taskpriority AS ENUM (
            'low',
            'medium',
            'high',
            'urgent'
        )
    """)

    # Create daily_analyses table
    op.create_table(
        'daily_analyses',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.user_id')),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('total_messages', sa.Integer(), default=0),
        sa.Column('total_sessions', sa.Integer(), default=0),
        sa.Column('average_sentiment', sa.Float()),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.Column('morning_brief_sent', sa.Boolean(), default=False),
        sa.Column('morning_brief_content', sa.Text())
    )

    # Create tasks table
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.user_id')),
        sa.Column('analysis_id', sa.Integer(), sa.ForeignKey('daily_analyses.id', ondelete='CASCADE')),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('status', sa.Enum('taskstatus'), server_default='pending'),
        sa.Column('priority', sa.Enum('taskpriority'), server_default='medium'),
        sa.Column('due_date', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('is_strategic', sa.Boolean(), default=False)
    )

    # Create analysis_insights table
    op.create_table(
        'analysis_insights',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('analysis_id', sa.Integer(), sa.ForeignKey('daily_analyses.id', ondelete='CASCADE')),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('insight', sa.Text(), nullable=False),
        sa.Column('importance_score', sa.Float()),
        sa.Column('requires_action', sa.Boolean(), default=False)
    )

    # Create strategic_points table
    op.create_table(
        'strategic_points',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('analysis_id', sa.Integer(), sa.ForeignKey('daily_analyses.id', ondelete='CASCADE')),
        sa.Column('timeframe', sa.String()),
        sa.Column('point', sa.Text(), nullable=False),
        sa.Column('priority', sa.Integer()),
        sa.Column('status', sa.String(), server_default='pending'),
        sa.Column('metrics', JSON)
    )

    # Create analysis_topics table
    op.create_table(
        'analysis_topics',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('analysis_id', sa.Integer(), sa.ForeignKey('daily_analyses.id', ondelete='CASCADE')),
        sa.Column('topic', sa.String(), nullable=False),
        sa.Column('frequency', sa.Integer()),
        sa.Column('importance_score', sa.Float()),
        sa.Column('is_trending', sa.Boolean(), default=False)
    )

    # Create session_topics table
    op.create_table(
        'session_topics',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('sessions.id')),
        sa.Column('topic', sa.String(), nullable=False),
        sa.Column('confidence_score', sa.Float()),
        sa.Column('mention_count', sa.Integer(), default=1)
    )

    # Create message_sentiments table
    op.create_table(
        'message_sentiments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('message_id', sa.Integer(), sa.ForeignKey('messages.id')),
        sa.Column('sentiment_score', sa.Float()),
        sa.Column('emotion_labels', JSON),
        sa.Column('confidence', sa.Float())
    )

    # Create indexes for frequent queries
    op.create_index('ix_daily_analyses_user_id_date', 'daily_analyses', ['user_id', 'date'])
    op.create_index('ix_tasks_user_id', 'tasks', ['user_id'])
    op.create_index('ix_tasks_due_date', 'tasks', ['due_date'])
    op.create_index('ix_analysis_insights_analysis_id', 'analysis_insights', ['analysis_id'])
    op.create_index('ix_message_sentiments_message_id', 'message_sentiments', ['message_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_message_sentiments_message_id')
    op.drop_index('ix_analysis_insights_analysis_id')
    op.drop_index('ix_tasks_due_date')
    op.drop_index('ix_tasks_user_id')
    op.drop_index('ix_daily_analyses_user_id_date')

    # Drop tables in reverse order
    op.drop_table('message_sentiments')
    op.drop_table('session_topics')
    op.drop_table('analysis_topics')
    op.drop_table('strategic_points')
    op.drop_table('analysis_insights')
    op.drop_table('tasks')
    op.drop_table('daily_analyses')

    # Drop enum types
    op.execute('DROP TYPE taskpriority')
    op.execute('DROP TYPE taskstatus')