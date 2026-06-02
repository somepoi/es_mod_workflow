FROM rclone/rclone:latest

# Метаданные образа
LABEL org.opencontainers.image.title="Google Drive Uploader"
LABEL org.opencontainers.image.description="Загрузчик файлов на Google Drive"
LABEL org.opencontainers.image.source="https://github.com/somepoi/es_mod_workflow"

RUN apk add --no-cache zip

WORKDIR /data
