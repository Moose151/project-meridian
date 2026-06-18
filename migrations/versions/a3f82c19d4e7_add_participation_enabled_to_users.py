"""Add participation_enabled to users

Revision ID: a3f82c19d4e7
Revises: 1b649d4f76f6
Create Date: 2026-06-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3f82c19d4e7'
down_revision = '1b649d4f76f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'participation_enabled',
                sa.Boolean(),
                nullable=False,
                server_default=sa.false()
            )
        )


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('participation_enabled')
