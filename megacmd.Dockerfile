FROM ubuntu:22.04

# Метаданные образа
LABEL org.opencontainers.image.title="MEGAcmd Uploader"
LABEL org.opencontainers.image.description="Загрузчик файлов на MEGA (универсальный)"
LABEL org.opencontainers.image.source="https://github.com/somepoi/es_mod_workflow"

RUN apt-get update && \
    apt-get install -y wget zip && \
    wget https://mega.nz/linux/repo/xUbuntu_22.04/amd64/megacmd-xUbuntu_22.04_amd64.deb && \
    apt-get install -y ./megacmd-xUbuntu_22.04_amd64.deb && \
    rm megacmd-xUbuntu_22.04_amd64.deb && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /data
