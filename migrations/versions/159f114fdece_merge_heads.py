"""merge heads

Revision ID: 159f114fdece
Revises: 5a316bd07df3, f5ff3b3c6d4e
Create Date: 2026-02-04 09:25:21.083005

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '159f114fdece'
down_revision: Union[str, None] = ('5a316bd07df3', 'f5ff3b3c6d4e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
