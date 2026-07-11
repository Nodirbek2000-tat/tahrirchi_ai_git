from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data import config
from db.models import Payment, PaymentStatus, Task, User

# O'zbekiston vaqti (UTC+5, DST yo'q)
TASHKENT = timezone(timedelta(hours=5))

AI_COST_KEY = "ai_cost_usd"


@dataclass
class Stats:
    users_today: int
    users_yesterday: int
    users_week: int
    users_total: int
    revenue_total: int      # so'm (tasdiqlangan to'lovlar)
    tokens_sold: int        # sotilgan tokenlar
    ai_cost_usd: float      # sarflangan OpenAI puli
    ai_left_usd: float      # qolgan (byudjet - sarf)


class StatsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _count_users(self, since: datetime, until: datetime | None = None) -> int:
        stmt = select(func.count(User.id)).where(User.created_at >= since)
        if until is not None:
            stmt = stmt.where(User.created_at < until)
        return int((await self.session.execute(stmt)).scalar_one())

    async def collect(self) -> Stats:
        now = datetime.now(TASHKENT)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)
        week_ago = now - timedelta(days=7)

        users_today = await self._count_users(today)
        users_yesterday = await self._count_users(yesterday, today)
        users_week = await self._count_users(week_ago)
        users_total = int(
            (await self.session.execute(select(func.count(User.id)))).scalar_one()
        )

        revenue = int(
            (
                await self.session.execute(
                    select(func.coalesce(func.sum(Payment.amount), 0)).where(
                        Payment.status == PaymentStatus.APPROVED
                    )
                )
            ).scalar_one()
        )
        tokens_sold = int(
            (
                await self.session.execute(
                    select(func.coalesce(func.sum(Payment.tokens), 0)).where(
                        Payment.status == PaymentStatus.APPROVED
                    )
                )
            ).scalar_one()
        )

        from db.models import Setting

        cost_row = await self.session.get(Setting, AI_COST_KEY)
        ai_cost = cost_row.value if cost_row else 0.0
        ai_left = config.OPENAI_BUDGET_USD - ai_cost

        return Stats(
            users_today=users_today,
            users_yesterday=users_yesterday,
            users_week=users_week,
            users_total=users_total,
            revenue_total=revenue,
            tokens_sold=tokens_sold,
            ai_cost_usd=round(ai_cost, 4),
            ai_left_usd=round(ai_left, 4),
        )
