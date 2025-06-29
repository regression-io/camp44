import sqlalchemy as sa
from alembic import op

"""enable RLS and tenant isolation policies

Revision ID: f5ff3b3c6d4e
Revises: d69d27a04493
Create Date: 2025-06-23 17:40:00-04:00
"""

# revision identifiers, used by Alembic.
revision = 'f5ff3b3c6d4e'
down_revision = 'd69d27a04493'
branch_labels = None
depends_on = None

tables_with_tenant_column = [
    "user",
    "app",
    "entity",
    "meter_event",
]


def upgrade():
    # Enable RLS and create tenant-isolation policy for each table
    conn = op.get_bind()

    for tbl in tables_with_tenant_column:
        conn.execute(sa.text(f"ALTER TABLE public.{tbl} ENABLE ROW LEVEL SECURITY"))
        # Drop if exists to ensure idempotency when re-running in dev
        conn.execute(sa.text(
            f"DROP POLICY IF EXISTS tenant_isolation ON public.{tbl}"
        ))
        conn.execute(sa.text(
            f"CREATE POLICY tenant_isolation ON public.{tbl} "
            f"USING (tenant_id = current_setting('app.tenant_id')::uuid) "
            f"WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)"
        ))


def downgrade():
    conn = op.get_bind()
    for tbl in tables_with_tenant_column:
        conn.execute(sa.text(f"ALTER TABLE public.{tbl} DISABLE ROW LEVEL SECURITY"))
        conn.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON public.{tbl}"))
