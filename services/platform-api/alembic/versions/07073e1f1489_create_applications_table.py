"""create applications table

Revision ID: 07073e1f1489
Revises:
Create Date: 2026-10-19 13:46:06.707310
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "07073e1f1489"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


application_status_enum = postgresql.ENUM(
    "registered",
    "deployed",
    "failed",
    name="application_status",
    create_type=False,
)


def upgrade() -> None:
    """Create the applications table and its PostgreSQL ENUM type."""

    bind = op.get_bind()

    application_status_enum.create(bind, checkfirst=False)

    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("repository_url", sa.String(length=2048), nullable=False),
        sa.Column("status", application_status_enum, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Remove the applications table and its PostgreSQL ENUM type."""

    bind = op.get_bind()

    op.drop_table("applications")

    application_status_enum.drop(bind, checkfirst=False)
