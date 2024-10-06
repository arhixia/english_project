"""Make unique_id NOT NULL

Revision ID: 4531f1edd2d1
Revises: 97f55dd36940
Create Date: 2024-09-30 22:34:02.328876

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4531f1edd2d1'
down_revision: Union[str, None] = '97f55dd36940'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('electives', 'unique_id', nullable=False)


def downgrade() -> None:
    pass
