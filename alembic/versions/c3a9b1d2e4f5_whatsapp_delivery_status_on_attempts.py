"""whatsapp delivery status on notification_attempts

Revision ID: c3a9b1d2e4f5
Revises: 877df32a3031
Create Date: 2026-03-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3a9b1d2e4f5"
down_revision: Union[str, Sequence[str], None] = "877df32a3031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notification_attempts",
        sa.Column("provider_delivery_status", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "notification_attempts",
        sa.Column("provider_delivery_status_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notification_attempts", "provider_delivery_status_at")
    op.drop_column("notification_attempts", "provider_delivery_status")
