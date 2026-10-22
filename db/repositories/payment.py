from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Payment, PaymentStatus


class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, user_id: int, package: str, days: int, amount: int
    ) -> Payment:
        payment = Payment(
            user_id=user_id, package=package, days=days, amount=amount
        )
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def get(self, payment_id: int) -> Payment | None:
        return await self.session.get(Payment, payment_id)

    async def attach_receipt(
        self, payment_id: int, receipt_file_id: str, channel_message_id: int | None
    ) -> None:
        await self.session.execute(
            update(Payment)
            .where(Payment.id == payment_id)
            .values(
                receipt_file_id=receipt_file_id,
                channel_message_id=channel_message_id,
            )
        )
        await self.session.commit()

    async def resolve(
        self, payment_id: int, status: PaymentStatus, admin_id: int
    ) -> Payment | None:
        """Faqat PENDING to'lovni tasdiqlaydi/rad etadi. Ikki marta ishlamaydi."""
        result = await self.session.execute(
            update(Payment)
            .where(Payment.id == payment_id, Payment.status == PaymentStatus.PENDING)
            .values(
                status=status,
                processed_by=admin_id,
                processed_at=datetime.now(timezone.utc),
            )
            .returning(Payment.id)
        )
        await self.session.commit()
        if result.scalar_one_or_none() is None:
            return None
        return await self.session.get(Payment, payment_id)
