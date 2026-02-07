"""add token_version and refresh_tokens

Revision ID: b2e4f1a8c3d7
Revises: aa96c1c2e95b
Create Date: 2026-02-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2e4f1a8c3d7'
down_revision: Union[str, None] = 'aa96c1c2e95b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add token_version to user, create refresh_token table."""
    # Add token_version column to user table
    with op.batch_alter_table('user') as batch_op:
        batch_op.add_column(
            sa.Column('token_version', sa.Integer(), nullable=False, server_default='0')
        )

    # Create refresh_token table
    op.create_table(
        'refresh_token',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('token_hash', sa.String(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('family_id', sa.Uuid(), nullable=False),
        sa.Column('token_version', sa.Integer(), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_refresh_token_token_hash', 'refresh_token', ['token_hash'], unique=True)
    op.create_index('ix_refresh_token_user_id', 'refresh_token', ['user_id'])
    op.create_index('ix_refresh_token_family_id', 'refresh_token', ['family_id'])


def downgrade() -> None:
    """Remove refresh_token table and token_version column."""
    op.drop_index('ix_refresh_token_family_id', table_name='refresh_token')
    op.drop_index('ix_refresh_token_user_id', table_name='refresh_token')
    op.drop_index('ix_refresh_token_token_hash', table_name='refresh_token')
    op.drop_table('refresh_token')

    with op.batch_alter_table('user') as batch_op:
        batch_op.drop_column('token_version')
