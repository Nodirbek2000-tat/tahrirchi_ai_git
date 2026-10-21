from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from data import config
from services.ai import AICorrector

bot = Bot(token=config.BOT_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# AI xizmati — faqat tarjima uchun. Harflarni o'girish AI'siz (translit_engine).
ai = AICorrector()
