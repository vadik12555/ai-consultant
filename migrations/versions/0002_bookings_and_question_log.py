"""bookings + journal of all questions

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Журнал всех вопросов вместо таблицы «только без ответа»: старые строки — неотвеченные
    op.rename_table("unanswered_questions", "questions")
    op.add_column(
        "questions",
        sa.Column("answered", sa.Boolean, nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("service", sa.String(100), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "uq_bookings_active_slot",
        "bookings",
        ["starts_at"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_bookings_active_slot", table_name="bookings")
    op.drop_table("bookings")
    op.drop_column("questions", "answered")
    op.rename_table("questions", "unanswered_questions")
