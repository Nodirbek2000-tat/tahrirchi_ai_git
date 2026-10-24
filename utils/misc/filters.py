from aiogram import types


def not_command(message: types.Message) -> bool:
    """Kiritish kutilayotgan holatda buyruqlar (/start, /admin ...) yutilmasin —
    ular o'z handleriga o'tadi (masalan, /start holatni tozalab, menyuni ochadi)."""
    return not (message.text or "").startswith("/")
