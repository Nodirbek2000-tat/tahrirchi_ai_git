#!/bin/sh
set -e

echo "Migratsiyalar qo'llanmoqda (alembic upgrade head)..."
# Baza tayyor bo'lmasa qayta uriniladi (ma'lumotlar hech qachon o'chmaydi)
until alembic upgrade head; do
  echo "Baza hali tayyor emas, 3s dan keyin qayta urinaman..."
  sleep 3
done

echo "Bot ishga tushmoqda..."
exec python app.py
