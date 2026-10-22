FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# PDF tahriri uchun shriftlar (ş/ç/ğ/ö). Carlito/Caladea — Calibri/Cambria bilan
# bir xil o'lchamli, Liberation — Times New Roman/Arial bilan bir xil o'lchamli
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        fonts-dejavu-core \
        fonts-liberation \
        fonts-liberation2 \
        fonts-crosextra-carlito \
        fonts-crosextra-caladea \
    && rm -rf /var/lib/apt/lists/*

# Asl Times New Roman / Arial (PDF tahririda shrift aynan bir xil bo'lishi uchun).
# Internetdan yuklanadi — o'rnatilmasa ham build to'xtamaydi (Liberation ishlatiladi)
RUN (sed -i 's/^Components: main$/Components: main contrib/' /etc/apt/sources.list.d/debian.sources \
        2>/dev/null || true) \
    && echo "ttf-mscorefonts-installer msttcorefonts/accept-mscorefonts-eula select true" \
        | debconf-set-selections \
    && apt-get update \
    && (apt-get install -y --no-install-recommends ttf-mscorefonts-installer || true) \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]
