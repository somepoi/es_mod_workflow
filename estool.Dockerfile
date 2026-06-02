# syntax=docker/dockerfile:1
# Базовый образ с ESTool для конвертации Ren'Py проектов в мобильный порт
FROM ubuntu:24.04

# Метаданные образа
LABEL org.opencontainers.image.title="ESTool Mobile Converter"
LABEL org.opencontainers.image.description="Конвертер модов в мобильный порт"
LABEL org.opencontainers.image.source="https://github.com/somepoi/es_mod_workflow"

# Устанавливаем переменные окружения для неинтерактивной установки
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Устанавливаем Python, gettext (для envsubst) и зависимости в одном слое
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    gettext-base \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir --break-system-packages Pillow==10.2.0

# Рабочая директория
WORKDIR /app

# Копируем ESTool в образ (скрипт + общие ассеты + шаблон конфига)
COPY ESTool/ /app/ESTool/
COPY --chmod=755 docker-entrypoint.sh /app/docker-entrypoint.sh

# Объявляем volumes
VOLUME ["/app/source", "/output"]

# Используем exec form для ENTRYPOINT (best practice)
ENTRYPOINT ["/app/docker-entrypoint.sh"]
