"""create_base_tables

Revision ID: 940cb4a06c84
Revises: 0eca423a3830
Create Date: 2025-01-05 10:38:48.360293

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '940cb4a06c84'
down_revision: Union[str, None] = '0eca423a3830'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('user_id', sa.Integer(), primary_key=True),
        sa.Column('token_limit', sa.Integer()),
        sa.Column('tokens_used', sa.Integer(), server_default='0'),
        sa.Column('daily_tokens_used', sa.Integer(), server_default='0'),
        sa.Column('last_reset', sa.Date())
    )

    # Create sessions table
    op.create_table(
        'sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.user_id', ondelete='CASCADE')),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True)
    )

    # Create index for sessions.user_id
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'])

    # Create messages table
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.user_id', ondelete='CASCADE')),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('sessions.id', ondelete='CASCADE')),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', sa.Text(), nullable=True)
    )

    # Create indexes for messages
    op.create_index('ix_messages_user_id', 'messages', ['user_id'])
    op.create_index('ix_messages_session_id', 'messages', ['session_id'])

def downgrade() -> None:
    # Drop indexes first
    op.drop_index('ix_messages_session_id')
    op.drop_index('ix_messages_user_id')
    op.drop_index('ix_sessions_user_id')

    # Drop tables in correct order
    op.drop_table('messages')
    op.drop_table('sessions')
    op.drop_table('users')