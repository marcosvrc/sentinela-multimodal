"""add_dicom_service_enabled_flag

Revision ID: 52edc2c9d79c
"""

from alembic import op
import sqlalchemy as sa

revision = "52edc2c9d79c"
down_revision = "cd764b6027e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "feature_flags",
        sa.Column("dicom_service_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("feature_flags", "dicom_service_enabled")
