#!/bin/bash -e

error_exit() {
    echo "ERROR: $1" >&2
    if [ -f "/app/ESTool/estool.log" ]; then
        echo "" >&2
        echo "=== ESTool Log ===" >&2
        cat /app/ESTool/estool.log >&2
    fi
    exit "${2:-1}"
}

echo "========================================="
echo "ESTool Mobile Port Conversion"
echo "========================================="

# Обязательный параметр - имя мода (определяет имена папок/архива и virtual_root)
: "${PROJECT_NAME:?PROJECT_NAME env var is required (e.g. 'pioneriada')}"

# Опциональный параметр - папка результата ESTool, по умолчанию ${PROJECT_NAME}_android
PROJECT_ANDROID="${PROJECT_ANDROID:-${PROJECT_NAME}_android}"

echo "Project:         ${PROJECT_NAME}"
echo "Android output:  ${PROJECT_ANDROID}"
echo "========================================="

cd /app || error_exit "Failed to change directory to /app" 1

# Активируем общий ESTool-файл для мобильного порта (если есть .disabled-версия)
if [ -f "/app/ESTool/sprites_lol.rpy.disabled" ]; then
    cp /app/ESTool/sprites_lol.rpy.disabled /app/ESTool/sprites_lol.rpy
fi

# Удаляем старую копию если есть
if [ -d "/app/${PROJECT_NAME}" ]; then
    rm -rf "/app/${PROJECT_NAME}" || error_exit "Failed to remove old ${PROJECT_NAME}" 1
fi

# Копируем проект из read-only volume
if [ -d "/app/source" ]; then
    cp -r /app/source "/app/${PROJECT_NAME}" || error_exit "Failed to copy project" 1

    # Удаляем чувствительные и ненужные файлы
    rm -f  "/app/${PROJECT_NAME}/.env"*
    rm -rf "/app/${PROJECT_NAME}/.git"
    rm -rf "/app/${PROJECT_NAME}/.github"
    rm -rf "/app/${PROJECT_NAME}/output"
    rm -rf "/app/${PROJECT_NAME}/ESTool"
    rm -f  "/app/${PROJECT_NAME}/docker-compose"*.yml
    rm -f  "/app/${PROJECT_NAME}/Dockerfile"
    rm -f  "/app/${PROJECT_NAME}/"*.Dockerfile
    rm -f  "/app/${PROJECT_NAME}/.dockerignore"
else
    error_exit "/app/source not found!" 1
fi

# Проверяем наличие необходимых папок
[ -d "ESTool" ] || error_exit "ESTool folder not found!" 1
[ -d "${PROJECT_NAME}" ] || error_exit "${PROJECT_NAME} folder not found!" 1

# Генерируем config.py из шаблона (подставляем PROJECT_NAME / PROJECT_ANDROID)
if [ -f "/app/ESTool/config.template.py" ]; then
    export PROJECT_NAME PROJECT_ANDROID
    envsubst '${PROJECT_NAME} ${PROJECT_ANDROID}' \
        < /app/ESTool/config.template.py \
        > /app/ESTool/config.py \
        || error_exit "Failed to render config.py from template" 1
elif [ ! -f "/app/ESTool/config.py" ]; then
    error_exit "Neither ESTool/config.template.py nor ESTool/config.py is present" 1
fi

# Запускаем ESTool
python3 /app/ESTool/estool-1.001.py \
    --keep-cwd \
    -c /app/ESTool/config.py \
    --log /app/ESTool/estool.log \
    || error_exit "ESTool conversion failed!" 1

# Удаляем оригинальную папку и переименовываем результат
rm -rf "${PROJECT_NAME}" || error_exit "Failed to remove ${PROJECT_NAME}" 1
mv "${PROJECT_ANDROID}" "${PROJECT_NAME}" \
    || error_exit "Failed to rename ${PROJECT_ANDROID}" 1

[ -d "${PROJECT_NAME}" ] || error_exit "${PROJECT_NAME} folder not found after rename!" 1

# Показываем краткую статистику из лога
if [ -f "/app/ESTool/estool.log" ]; then
    echo ""
    echo "=== ESTool Log Summary ==="
    tail -n 20 /app/ESTool/estool.log
fi

echo ""
echo "========================================="
echo "Mobile port ready: /app/${PROJECT_NAME}"
echo "========================================="

# Копируем результат в /output если примонтирован
if [ -d "/output" ]; then
    cp -r "/app/${PROJECT_NAME}" /output/ \
        || error_exit "Failed to copy ${PROJECT_NAME} to /output" 1

    # Копируем лог для отладки
    mkdir -p /output/ESTool
    cp /app/ESTool/estool.log /output/ESTool/ 2>/dev/null || true

    echo "Results copied to /output"
fi

echo ""
echo "Conversion completed successfully!"

exit 0
