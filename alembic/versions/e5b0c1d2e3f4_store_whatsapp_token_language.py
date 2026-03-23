"""store whatsapp access token and template language

Revision ID: e5b0c1d2e3f4
Revises: c3a9b1d2e4f5
Create Date: 2026-03-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5b0c1d2e3f4"
down_revision: Union[str, Sequence[str], None] = "c3a9b1d2e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("store_settings", sa.Column("whatsapp_access_token", sa.Text(), nullable=True))
    op.add_column(
        "store_settings",
        sa.Column("whatsapp_template_language", sa.String(length=10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("store_settings", "whatsapp_template_language")
    op.drop_column("store_settings", "whatsapp_access_token")
