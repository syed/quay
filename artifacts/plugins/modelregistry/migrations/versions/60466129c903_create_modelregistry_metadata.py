"""Create JSON annotations DB

Revision ID: 60466129c903
Revises: 
Create Date: 2024-07-22 18:14:54.648670

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = "60466129c903"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "modelregistrymetadata",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "manifest_id",
            sa.Integer,
            sa.ForeignKey(
                "manifest.id",
                ondelete="CASCADE",
            ),
            nullable=False,
            index=True,
        ),
        sa.Column("metadata", JSONB, nullable=True, index=True),
    )


def downgrade():
    op.drop_table("modelregistryannotations")
