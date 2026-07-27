"""add_assisted_risk_columns_to_risk_consolidations

Revision ID: cd764b6027e2
Create Date: 2026-07-26
"""

from alembic import op
import sqlalchemy as sa

revision = "cd764b6027e2"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("risk_consolidations", sa.Column("assisted_risk_level", sa.Integer(), nullable=True))
    op.add_column("risk_consolidations", sa.Column("assisted_risk_label", sa.String(200), nullable=True))
    op.add_column("risk_consolidations", sa.Column("assisted_risk_justification", sa.Text(), nullable=True))
    op.add_column("risk_consolidations", sa.Column("assisted_risk_uncertainty", sa.Text(), nullable=True))
    op.add_column("risk_consolidations", sa.Column("assisted_risk_provider", sa.String(50), nullable=True))
    op.add_column("risk_consolidations", sa.Column("assisted_risk_model", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("risk_consolidations", "assisted_risk_model")
    op.drop_column("risk_consolidations", "assisted_risk_provider")
    op.drop_column("risk_consolidations", "assisted_risk_uncertainty")
    op.drop_column("risk_consolidations", "assisted_risk_justification")
    op.drop_column("risk_consolidations", "assisted_risk_label")
    op.drop_column("risk_consolidations", "assisted_risk_level")
