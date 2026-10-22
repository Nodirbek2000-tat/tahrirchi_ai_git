from environs import Env

env = Env()
env.read_env()

# --- Telegram ---
BOT_TOKEN = env.str("BOT_TOKEN")
ADMINS = env.list("ADMINS", subcast=int)
PAYMENT_CHANNEL_ID = env.str("PAYMENT_CHANNEL_ID", "@tahrirchiai")

# --- OpenAI ---
# Kalit ikkala nom bilan ham o'qiladi: OPENAI_API_KEY yoki OPEN_AI_TOKEN
OPENAI_API_KEY = env.str("OPENAI_API_KEY", None) or env.str("OPEN_AI_TOKEN", "")
OPENAI_MODEL = env.str("OPENAI_MODEL", "gpt-4o-mini")

# OpenAI narxlari — 1 000 000 token uchun USD (kirish, chiqish)
OPENAI_PRICES = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
}
# OpenAI hisobidagi boshlang'ich byudjet (USD). Statistikada "qoldi" shu asosda.
OPENAI_BUDGET_USD = env.float("OPENAI_BUDGET_USD", 0.0)
# Bir vaqtda OpenAI'ga ketadigan so'rovlar soni (OpenAI tarifingizga qarab oshiring)
AI_CONCURRENCY = env.int("AI_CONCURRENCY", 10)

# --- PostgreSQL ---
PG_HOST = env.str("PG_HOST", "localhost")
PG_PORT = env.int("PG_PORT", 5432)
PG_USER = env.str("PG_USER", "postgres")
PG_PASSWORD = env.str("PG_PASSWORD", "postgres")
PG_DB = env.str("PG_DB", "tahrirchi")

DATABASE_URL = (
    f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
)

# --- To'lov ---
CARD_NUMBER = env.str("CARD_NUMBER", "9860 1701 0951 8093")
CARD_HOLDER = env.str("CARD_HOLDER", "Nodirbek Shukurov")

# --- Biznes qoidalar ---
# Premium — barcha imkoniyatlar cheksiz. Premiumsiz user FREE_FILES ta faylni bepul
# tahrirlaydi. FREE_FILES va PREMIUM_PRICE — DASTLABKI (default) qiymatlar,
# admin panel ularni bazada (settings jadvalida) o'zgartiradi.
FREE_FILES = 2             # yangi userga beriladigan bepul fayllar soni (default)
PREMIUM_PRICE = 20_000     # premium narxi so'mda (default)
PREMIUM_DAYS = 30          # bitta to'lov necha kunlik premium beradi
PREMIUM_PACKAGE = "premium_30"

CHARS_PER_PAGE = 1800      # docx/txt: shuncha belgi = 1 sahifa
ROWS_PER_PAGE = 30         # xlsx: har shuncha qator = 1 sahifa
MAX_PAGES_PER_FILE = 300   # bitta fayl uchun maksimal hajm (sahifa)

# Bazadagi sozlama kalitlari (admin paneldan o'zgartiriladi)
SETTING_FREE_FILES = "free_files"
SETTING_PREMIUM_PRICE = "premium_price"

# --- Imlo tuzatish ---
# AI faqat qoidalar hal qila olmaydigan murakkab gaplarga ishlatiladi
SPELL_AI = env.bool("SPELL_AI", True)
SPELL_AI_MAX_SENTENCES = env.int("SPELL_AI_MAX_SENTENCES", 1500)  # bitta fayldan
