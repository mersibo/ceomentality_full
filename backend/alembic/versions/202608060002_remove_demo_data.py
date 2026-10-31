"""remove legacy demo workspace data

Revision ID: 202608060002
Revises: 202608060001
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608060002"
down_revision: str | None = "202608060001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEMO_CANDIDATE_IDS = (
    "alexei-petrov",
    "maria-ivanova",
    "dmitry-sorokin",
    "nikita-volkov",
    "anastasia-belova",
    "sergey-karpov",
    "olga-smirnova",
    "pavel-e",
    "ivan-kuznetsov",
)
DEMO_DROP_IDS = ("wave-01", "wave-02", "partner", "waitlist")


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM access_codes WHERE candidate_id = ANY(:ids)"), {"ids": list(DEMO_CANDIDATE_IDS)})
    bind.execute(sa.text("DELETE FROM candidate_notes WHERE candidate_id = ANY(:ids)"), {"ids": list(DEMO_CANDIDATE_IDS)})
    bind.execute(sa.text("DELETE FROM candidates WHERE id = ANY(:ids)"), {"ids": list(DEMO_CANDIDATE_IDS)})
    bind.execute(sa.text("DELETE FROM access_codes WHERE batch_id IN (SELECT id FROM code_batches WHERE drop_id = ANY(:ids))"), {"ids": list(DEMO_DROP_IDS)})
    bind.execute(sa.text("DELETE FROM code_batches WHERE drop_id = ANY(:ids)"), {"ids": list(DEMO_DROP_IDS)})
    bind.execute(sa.text("DELETE FROM drops WHERE id = ANY(:ids)"), {"ids": list(DEMO_DROP_IDS)})
    bind.execute(sa.text("DELETE FROM activity_events WHERE type = 'System initialized' AND detail IN ('Postgres workspace is ready', 'MVP demo workspace is ready')"))


def downgrade() -> None:
    pass
