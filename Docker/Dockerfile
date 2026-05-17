FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Tehran

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        wget \
        gnupg \
        git \
        unzip \
        tini \
        fonts-liberation \
        libnss3 \
        libxss1 \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libcups2 \
        libdbus-1-3 \
        libdrm2 \
        libgbm1 \
        libgtk-3-0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libxkbcommon0 \
        libpango-1.0-0 \
        libcairo2 \
        xdg-utils \
        openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

RUN install -d -m 0755 /etc/apt/keyrings \
    && wget -qO- https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main" \
       > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --upgrade pip setuptools wheel \
    && pip install \
        "aiogram>=3.28,<3.29" \
        "gplaydl>=2.1,<3" \
        "pymongo>=4.15,<5" \
        "pydantic>=2.11,<3" \
        "pydantic-settings>=2.9,<3" \
        "python-dotenv>=1.1,<2" \
        "aiohttp" \
        "selenium>=4.20" \
        "google-play-scraper>=1.2,<2"

COPY . .

RUN mkdir -p storage/downloads storage/nixfile-debug tools

ENV DOWNLOAD_DIR=/app/storage/downloads \
    TOOLS_DIR=/app/tools \
    APKEDITOR_JAR=/app/tools/APKEditor.jar \
    APKSIGNER_JAR=/app/tools/uber-apk-signer.jar \
    ALLTECH_GPLAY_PATH=/app/tools/gplay-apk-downloader/gplay \
    ALLTECH_AUTH_FILE=/root/.gplay-auth.json \
    NIXFILE_SESSION_FILE=/app/storage/nixfile-session.json \
    NIXFILE_HEADLESS=true

ENTRYPOINT ["tini", "--"]
CMD ["python", "-u", "Main.py"]
