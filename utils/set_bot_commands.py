import logging

from aiogram import types

from data.config import ADMINS


async def set_default_commands(dp):
    # Barcha foydalanuvchilar uchun
    await dp.bot.set_my_commands(
        [
            types.BotCommand("start", "Botni ishga tushirish"),
        ]
    )
    # Faqat adminlar uchun (/admin qo'shimcha)
    admin_commands = [
        types.BotCommand("start", "Botni ishga tushirish"),
        types.BotCommand("admin", "Admin panel"),
    ]
    for admin_id in ADMINS:
        try:
            await dp.bot.set_my_commands(
                admin_commands,
                scope=types.BotCommandScopeChat(chat_id=admin_id),
            )
        except Exception as err:
            logging.warning("Admin buyruqlarini o'rnatishda xato (%s): %s", admin_id, err)
