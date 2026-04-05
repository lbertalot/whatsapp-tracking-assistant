"""ecommerce source of truth: remove Weraha flags, add platform audit fields

Revision ID: a7b3c9d1e2f0
Revises: f6c2d8e1a0b9
Create Date: 2026-04-05

Legacy `ready_for_polling` is remapped to `pending_tracking` (not `in_transit`) so we do
not imply a confirmed in-transit state from the platform without a later TN sync.

WARNING: downgrade drops `ecommerce_sync_enabled` / audit columns — avoid downgrade in
production without a DB backup and a clear rollback plan.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7b3c9d1e2f0"
down_revision: Union[str, Sequence[str], None] = "f6c2d8e1a0b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("platform_status_raw", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("last_status_source", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "store_settings",
        sa.Column(
            "ecommerce_sync_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "store_settings",
        sa.Column("default_phone_region", sa.String(length=5), nullable=True),
    )

    op.execute(
        """
        UPDATE orders
        SET current_status = 'pending_tracking'
        WHERE current_status = 'ready_for_polling'
        """
    )

    op.drop_column("store_settings", "weraha_account_reference")
    op.drop_column("store_settings", "weraha_enabled")


def downgrade() -> None:
    op.add_column(
        "store_settings",
        sa.Column("weraha_enabled", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "store_settings",
        sa.Column("weraha_account_reference", sa.String(length=100), nullable=True),
    )
    op.execute("UPDATE store_settings SET weraha_enabled = false WHERE weraha_enabled IS NULL")

    op.drop_column("store_settings", "default_phone_region")
    op.drop_column("store_settings", "ecommerce_sync_enabled")
    op.drop_column("orders", "last_status_source")
    op.drop_column("orders", "platform_status_raw")
