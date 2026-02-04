"""add password reset token fields

Revision ID: aa96c1c2e95b
Revises: 159f114fdece
Create Date: 2026-02-04 09:25:36.431883

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa96c1c2e95b'
down_revision: Union[str, None] = '159f114fdece'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add password_reset_token and password_reset_expires columns to user table."""
    # Add columns if they don't exist (idempotent)
    with op.batch_alter_table('user') as batch_op:
        batch_op.add_column(
            sa.Column('password_reset_token', sa.String(), nullable=True)
        )
        batch_op.add_column(
            sa.Column('password_reset_expires', sa.DateTime(), nullable=True)
        )
        batch_op.create_index(
            'ix_user_password_reset_token',
            ['password_reset_token'],
            unique=False
        )


def downgrade() -> None:
    """Remove password_reset_token and password_reset_expires columns from user table."""
    with op.batch_alter_table('user') as batch_op:
        batch_op.drop_index('ix_user_password_reset_token')
        batch_op.drop_column('password_reset_expires')
        batch_op.drop_column('password_reset_token')
