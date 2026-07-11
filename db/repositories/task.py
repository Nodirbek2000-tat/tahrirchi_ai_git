from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Task, TaskStatus


class TaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, user_id: int, file_name: str, file_type: str, tokens_spent: int
    ) -> Task:
        task = Task(
            user_id=user_id,
            file_name=file_name,
            file_type=file_type,
            tokens_spent=tokens_spent,
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def set_status(self, task_id: int, status: TaskStatus) -> None:
        await self.session.execute(
            update(Task).where(Task.id == task_id).values(status=status)
        )
        await self.session.commit()
