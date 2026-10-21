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
# FREE_TOKENS va TOKEN_PRICE — DASTLABKI (default) qiymatlar.
# Admin panel ularni bazada (settings jadvalida) o'zgartiradi.
FREE_TOKENS = 30           # yangi userga beriladigan tekin token (default)
TOKEN_PRICE = 500          # 1 token narxi so'mda (default)
CHARS_PER_PAGE = 1800      # docx/txt/pdf: shuncha belgi = 1 sahifa (1 token)
ROWS_PER_TOKEN = 30        # xlsx: har shuncha qatorga 1 token
MAX_TOKENS_PER_FILE = 300      # harflarga o'girish: maksimal sahifa/token
MAX_TRANSLATE_TOKENS = 200     # tarjima: maksimal sahifa/token

# Token paketlaridagi token sonlari. Narx = token soni × TOKEN_PRICE (bazadan olinadi).
PACKAGE_TOKENS = {
    "pkg_20": 20,
    "pkg_40": 40,
    "pkg_60": 60,
}

# Bazadagi sozlama kalitlari (admin paneldan o'zgartiriladi)
SETTING_FREE_TOKENS = "free_tokens"
SETTING_TOKEN_PRICE = "token_price"
