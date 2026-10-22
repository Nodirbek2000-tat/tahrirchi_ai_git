"""free_texts: matnni o'girish uchun bepul urinishlar

Revision ID: b4e8d1a6c3f2
Revises: a1f3c9d2b7e4
Create Date: 2026-10-22 18:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4e8d1a6c3f2'
down_revision = 'a1f3c9d2b7e4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("free_texts", sa.Integer(), nullable=False, server_default="0"))
    op.execute("UPDATE users SET free_texts = 20")   # barcha eski userlarga 20 ta urinish


def downgrade() -> None:
    op.drop_column("users", "free_texts")
