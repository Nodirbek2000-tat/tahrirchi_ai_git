"""premium: tokenlar o'rniga oylik premium va bepul fayllar

Revision ID: a1f3c9d2b7e4
Revises: 769ec7410e11
Create Date: 2026-10-22 12:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1f3c9d2b7e4'
down_revision = '769ec7410e11'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("free_files", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("premium_until", sa.DateTime(timezone=True), nullable=True))
    # Eski token ustuni endi ishlatilmaydi (ma'lumot o'chirilmaydi)
    op.alter_column("users", "tokens", server_default="0")

    # Barcha eski userlarga 2 ta bepul fayl
    op.execute("UPDATE users SET free_files = 2")
    # Token SOTIB OLGAN va tokeni hali qolgan userlar puli kuymasin — 30 kunlik premium
    op.execute(
        "UPDATE users SET premium_until = now() + interval '30 days' "
        "WHERE tokens > 0 AND id IN "
        "(SELECT user_id FROM payments WHERE status = 'APPROVED')"
    )

    op.add_column("payments", sa.Column("days", sa.Integer(), nullable=False, server_default="0"))
    op.alter_column("payments", "tokens", server_default="0")


def downgrade() -> None:
    op.alter_column("payments", "tokens", server_default=None)
    op.drop_column("payments", "days")
    op.alter_column("users", "tokens", server_default=None)
    op.drop_column("users", "premium_until")
    op.drop_column("users", "free_files")
