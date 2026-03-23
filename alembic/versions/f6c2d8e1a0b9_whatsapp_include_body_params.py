"""whatsapp_include_body_params on store_settings

Revision ID: f6c2d8e1a0b9
Revises: e5b0c1d2e3f4
Create Date: 2026-03-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6c2d8e1a0b9"
down_revision: Union[str, Sequence[str], None] = "e5b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "store_settings",
        sa.Column(
            "whatsapp_include_body_params",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("store_settings", "whatsapp_include_body_params")
