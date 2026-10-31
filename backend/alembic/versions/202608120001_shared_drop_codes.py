"""store shared drop codes without candidate suffix

Revision ID: 202608120001
Revises: 202608080001
"""

from alembic import op


revision = "202608120001"
down_revision = "202608080001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_access_codes_value", "access_codes", type_="unique")
    op.execute(
        """
        UPDATE access_codes
        SET value = left(value, length(value) - length(candidate_id) - 1)
        WHERE candidate_id IS NOT NULL
          AND right(value, length(candidate_id) + 1) = ':' || candidate_id
        """
    )
    op.create_unique_constraint(
        "uq_access_codes_candidate_value", "access_codes", ["candidate_id", "value"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_access_codes_candidate_value", "access_codes", type_="unique")
    op.execute(
        """
        UPDATE access_codes
        SET value = value || ':' || candidate_id
        WHERE candidate_id IS NOT NULL
        """
    )
    op.create_unique_constraint("uq_access_codes_value", "access_codes", ["value"])
