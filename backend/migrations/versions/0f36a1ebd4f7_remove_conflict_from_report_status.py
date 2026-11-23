"""remove conflict from report_status

Revision ID: 0f36a1ebd4f7
Revises: 07e128524cc9
Create Date: 2026-11-18 04:28:36.573012

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f36a1ebd4f7'
down_revision: Union[str, Sequence[str], None] = '07e128524cc9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CHECK_NAME = "ck_reports_raw_quarantine_reason"
CHECK_SQL = "(status = 'quarantined') = (quarantine_reason IS NOT NULL)"


def _recreate_report_status(values: list[str]) -> None:
    """Postgres does not remove values from an ENUM: it creates the type again with `values`.

    The CHECK that compares status with 'quarantined' depends on the old type, so
    it is removed first and created again at the end.
    """
    op.drop_constraint(CHECK_NAME, "reports_raw", type_="check")
    op.execute("ALTER TABLE reports_raw ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TYPE report_status RENAME TO report_status_old")
    sa.Enum(*values, name="report_status").create(op.get_bind())
    # Fails if there are rows with a value that no longer exists
    op.execute(
        "ALTER TABLE reports_raw ALTER COLUMN status "
        "TYPE report_status USING status::text::report_status"
    )
    op.execute("ALTER TABLE reports_raw ALTER COLUMN status SET DEFAULT 'pending'")
    op.execute("DROP TYPE report_status_old")
    op.create_check_constraint(CHECK_NAME, "reports_raw", CHECK_SQL)


def upgrade() -> None:
    """conflict becomes only a quarantine reason, not a status."""
    _recreate_report_status(["pending", "applied", "duplicate", "quarantined"])


def downgrade() -> None:
    """Downgrade schema."""
    _recreate_report_status(["pending", "applied", "duplicate", "quarantined", "conflict"])
