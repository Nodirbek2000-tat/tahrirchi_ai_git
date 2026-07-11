# Tahrirchi AI Bot

Hujjatlarni (**.docx, .xlsx, .pptx, .pdf, .txt**) yangi o'zbek lotin alifbosiga
o'giradi va imloviy xatolarni to'g'irlaydi. Matn, uslub, rasm va tuzilma
o'zgarmaydi — faqat harflar va imlo.

```
sh → ş    ch → ç    gʻ → ğ    oʻ → ö
```

## Texnologiyalar
- aiogram 2.25.2 · PostgreSQL · SQLAlchemy 2 (async) · Alembic · OpenAI

## Token tizimi
- Yangi foydalanuvchi: **7 ta bepul token**
- 1 sahifa (~1800 belgi) = 1 token · PDF: sahifa · PPTX: slayd · Excel: har 30 qator = 1 token
- Paketlar: 10 = 10 000, 20 = 20 000, 30 = 30 000 so'm
- To'lov: karta o'tkazma + chek → `@tahrirchiai` kanaliga → admin tasdiqlaydi → token qo'shiladi

## O'rnatish

1. Kutubxonalar:
   ```powershell
   venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. `.env` faylini yarating (`.env.dist` dan nusxa oling) va to'ldiring:
   `BOT_TOKEN`, `ADMINS`, `PAYMENT_CHANNEL_ID`, `OPENAI_API_KEY`,
   `PG_*`, `CARD_NUMBER`, `CARD_HOLDER`.

3. PostgreSQL bazasini yarating (masalan `tahrirchi`).

4. Migratsiyalar:
   ```powershell
   venv\Scripts\python.exe -m alembic revision --autogenerate -m "init"
   venv\Scripts\python.exe -m alembic upgrade head
   ```

5. Botni ishga tushiring:
   ```powershell
   venv\Scripts\python.exe app.py
   ```

## Muhim
- Bot `@tahrirchiai` kanalida **admin** bo'lishi shart (cheklar o'sha yerga boradi).
- Chek tasdiqlash tugmalarini faqat `.env` dagi `ADMINS` bosa oladi.

## Docker bilan serverga o'rnatish

1. Serverga fayllarni ko'chiring va `.env` ni to'ldiring (`PG_PASSWORD` ni albatta o'zgartiring).
2. Ishga tushirish:
   ```bash
   docker compose up -d --build
   ```
   Bu Postgres + botni ko'taradi va migratsiyalarni avtomatik qo'llaydi.

3. **Yangilanish** (kod o'zgarsa) — ma'lumotlar bazasi **O'CHMAYDI**:
   ```bash
   git pull            # yoki yangi fayllarni yuklang
   docker compose up -d --build
   ```
   Postgres ma'lumotlari `pgdata` volume'da saqlanadi. Faqat `docker compose down -v`
   qilsangizgina o'chadi — **buni ishlatmang**.

4. Loglarni ko'rish: `docker compose logs -f bot`

> Bir vaqtdagi AI so'rovlar sonini `.env` dagi `AI_CONCURRENCY` orqali oshiring
> (OpenAI tarifingiz ruxsat bersa, masalan 20–40).

## Loyiha tuzilmasi
```
app.py              — kirish nuqtasi
loader.py           — bot, dp, corrector
data/config.py      — .env sozlamalari
db/                 — modellar (User, Payment, Task) + repozitoriylar
services/
  transliteration.py  — yangi alifbo (deterministik)
  ai/                 — OpenAI imlo tuzatuvchi
  corrector.py        — AI + alifbo birlashmasi
  files/              — docx / xlsx / pptx / pdf / txt processorlar
handlers/
  users/  — start, menyu, token/to'lov, fayl tahriri
  admin/  — to'lovni tasdiqlash
keyboards/ · states/ · middlewares/ · migrations/
```
