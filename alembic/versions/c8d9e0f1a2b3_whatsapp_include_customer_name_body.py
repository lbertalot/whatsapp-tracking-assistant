"""store_settings: whatsapp_include_customer_name_in_body

Revision ID: c8d9e0f1a2b3
Revises: b1c2d3e4f5a6
Create Date: 2026-04-06

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "store_settings",
        sa.Column(
            "whatsapp_include_customer_name_in_body",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column(
        "store_settings",
        "whatsapp_include_customer_name_in_body",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("store_settings", "whatsapp_include_customer_name_in_body")
