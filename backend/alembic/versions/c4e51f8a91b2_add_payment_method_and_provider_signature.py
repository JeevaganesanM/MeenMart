"""add payment_method and provider_signature to payments

Revision ID: c4e51f8a91b2
Revises: b0a23d106c86
Create Date: 2026-10-29 11:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e51f8a91b2'
down_revision: Union[str, Sequence[str], None] = 'b0a23d106c86'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('payments', sa.Column('payment_method', sa.String(length=50), nullable=True))
    op.add_column('payments', sa.Column('provider_signature', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('payments', 'provider_signature')
    op.drop_column('payments', 'payment_method')

