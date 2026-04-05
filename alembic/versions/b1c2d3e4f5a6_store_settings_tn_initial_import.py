"""store_settings: tn_initial_import_completed_at for MS-ONB03

Revision ID: b1c2d3e4f5a6
Revises: a7b3c9d1e2f0
Create Date: 2026-04-05

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "a7b3c9d1e2f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "store_settings",
        sa.Column("tn_initial_import_completed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("store_settings", "tn_initial_import_completed_at")
