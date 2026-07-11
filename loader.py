from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from data import config
from services.ai import AICorrector
from services.corrector import TextCorrector

bot = Bot(token=config.BOT_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Umumiy AI xizmati (imlo + tarjima bitta parallel chegarani bo'lishadi)
ai = AICorrector()
corrector = TextCorrector(ai)  # harflarga o'girish + imlo
