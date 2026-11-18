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
    """O Postgres não remove valores de um ENUM: cria o tipo de novo com `values`.

    A CHECK que compara status com 'quarantined' depende do tipo antigo, por isso
    é removida antes e criada outra vez no fim.
    """
    op.drop_constraint(CHECK_NAME, "reports_raw", type_="check")
    op.execute("ALTER TABLE reports_raw ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TYPE report_status RENAME TO report_status_old")
    sa.Enum(*values, name="report_status").create(op.get_bind())
    # Falha se houver linhas com um valor que deixou de existir
    op.execute(
        "ALTER TABLE reports_raw ALTER COLUMN status "
        "TYPE report_status USING status::text::report_status"
    )
    op.execute("ALTER TABLE reports_raw ALTER COLUMN status SET DEFAULT 'pending'")
    op.execute("DROP TYPE report_status_old")
    op.create_check_constraint(CHECK_NAME, "reports_raw", CHECK_SQL)


def upgrade() -> None:
    """conflict passa a ser só motivo de quarentena, não um status."""
    _recreate_report_status(["pending", "applied", "duplicate", "quarantined"])


def downgrade() -> None:
    """Downgrade schema."""
    _recreate_report_status(["pending", "applied", "duplicate", "quarantined", "conflict"])
