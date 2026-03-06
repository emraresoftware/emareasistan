# Emare WhatsApp Bridge - Docker
# Chromium gömülü, optimize edilmiş Node.js container
FROM node:18-slim

# Chromium ve gerekli kütüphaneler
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fonts-liberation \
    fonts-noto-color-emoji \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    procps \
    dumb-init \
    && rm -rf /var/lib/apt/lists/*

# Chromium'u Puppeteer'ın kullanması için env
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
ENV CHROME_PATH=/usr/bin/chromium

# Çalışma dizini
WORKDIR /app

# Bağımlılıkları önce kopyala (cache layer)
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev --ignore-scripts 2>/dev/null || npm install --omit=dev

# Uygulama kodunu kopyala
COPY index-multi.js index.js ./
COPY .env.example .env.example

# Auth verileri ve loglar için volume mount noktaları
VOLUME ["/app/auth_data"]

# Port
EXPOSE 3100

# Sağlık kontrolü - her 30 saniyede /api/connections endpoint'ini kontrol et
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=60s \
    CMD node -e "const http=require('http');const r=http.get('http://127.0.0.1:3100/api/connections',{timeout:5000},s=>{process.exit(s.statusCode===200?0:1)});r.on('error',()=>process.exit(1));"

# dumb-init ile PID 1 yönetimi (zombie process önleme)
ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "--max-old-space-size=512", "index-multi.js"]
