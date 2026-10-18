"""Add explicit schema metadata without changing domain tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_schema_metadata"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schema_metadata",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
    )
    op.execute(
        "INSERT INTO schema_metadata (key, value) VALUES "
        "('schema_contract', 'surge-0004-baseline')"
    )


def downgrade() -> None:
    op.drop_table("schema_metadata")
