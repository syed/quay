"""test npm table

Revision ID: 16c8b6f647c1
Revises: 
Create Date: 2024-03-11 10:14:39.986398

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '16c8b6f647c1'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "npmpackage",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("version", sa.String, nullable=False),
    )


def downgrade():
    op.drop_table("npmpackage")
