from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from data import config
from services.ai import AICorrector

bot = Bot(token=config.BOT_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# AI xizmati — faqat imloda, qoidalar hal qila olmagan murakkab gaplar uchun.
# Harflarni o'girish va asosiy imlo qoidalari AI'siz (translit_engine, services/spelling).
ai = AICorrector()
