#!/bin/bash

: "${STEAM_USERNAME:?STEAM_USERNAME не задан}"
: "${STEAM_PASSWORD:?STEAM_PASSWORD не задан}"
: "${STEAM_TOTP:?STEAM_TOTP не задан}"
: "${STEAM_CONFIG_PATH:?STEAM_CONFIG_PATH не задан}"

CONFIG_PATH="$STEAM_CONFIG_PATH"

if [ ! -f "$CONFIG_PATH" ]; then
  echo "Ошибка: Конфигурационный файл $CONFIG_PATH не найден!"
  exit 1
fi

if [ -f "README.md" ]; then
  DESCRIPTION=$(python3 -c "from md2steam import markdown_to_steam_bbcode; print(markdown_to_steam_bbcode(open('README.md').read()))")
else
  echo "Ошибка: README.md не найден!"
  exit 1
fi

PUBLISHED_ID=$(yq eval '.publishedfileid' "$CONFIG_PATH")
VISIBILITY=$(yq eval '.visibility' "$CONFIG_PATH")
TITLE=$(yq eval '.title' "$CONFIG_PATH")
CHANGE_NOTE=""
if [ -f "CHANGELOG.md" ]; then
  CHANGELOG_BLOCK=$(awk '/^## [0-9]/{ if (found) exit; found=1 } found' CHANGELOG.md)
  if [ -n "$CHANGELOG_BLOCK" ]; then
    CHANGELOG_VERSION=$(echo "$CHANGELOG_BLOCK" | head -n1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -n1)
    if [ -n "$CHANGELOG_VERSION" ]; then
      echo "Версия из CHANGELOG.md: $CHANGELOG_VERSION"
      CHANGE_NOTE="$CHANGELOG_BLOCK"
    else
      echo "Предупреждение: не удалось извлечь номер версии из первого заголовка CHANGELOG.md, описание обновления будет пустым"
    fi
  else
    echo "Предупреждение: в CHANGELOG.md не найдено ни одной версии, описание обновления будет пустым"
  fi
else
  echo "Предупреждение: CHANGELOG.md не найден, описание обновления будет пустым"
fi
APPID=$(yq eval '.appid' "$CONFIG_PATH")
PREVIEW_FILENAME_PATH=$(yq eval '.previewfile' "$CONFIG_PATH")
PREVIEW_FILE="$(pwd)/${PREVIEW_FILENAME_PATH}"
PROJECT_NAME=$(yq eval '.project_name' "$CONFIG_PATH")
EXCLUSIONS=$(yq eval '.exclusions[]' "$CONFIG_PATH")

if [ -z "$APPID" ] || [ "$APPID" = "null" ]; then
  echo "Ошибка: Steam appid не указан в $CONFIG_PATH"
  exit 1
fi

SOURCE_FOLDER="$(pwd)"
echo "Исходная директория: $SOURCE_FOLDER"
echo "Содержимое исходной директории:"
ls -la "$SOURCE_FOLDER"

RSYNC_EXCLUDES=""
for pattern in $EXCLUSIONS; do
  RSYNC_EXCLUDES+=" --exclude=${pattern}"
done
RSYNC_EXCLUDES+=" --exclude=${PROJECT_NAME}"
RSYNC_EXCLUDES+=" --exclude=build"
echo "Исключения для rsync: ${RSYNC_EXCLUDES}"

BUILD_PARENT="${SOURCE_FOLDER}/build"
BUILD_FOLDER="${BUILD_PARENT}/${PROJECT_NAME}"

echo "Подготавливаем папку сборки: ${BUILD_FOLDER}"
rm -rf "$BUILD_FOLDER"
mkdir -p "$BUILD_FOLDER"

rsync -av $RSYNC_EXCLUDES "${SOURCE_FOLDER}/" "$BUILD_FOLDER/"

echo "Содержимое папки сборки ($BUILD_FOLDER):"
ls -la "$BUILD_FOLDER"

CONTENT_FOLDER="$BUILD_FOLDER"

if [ "$PUBLISHED_ID" = "null" ] || [ -z "$PUBLISHED_ID" ]; then
  echo "Публикуем новый элемент Workshop для appid $APPID"
  PUBLISHED_ID=0
else
  echo "Обновляем существующий элемент Workshop с ID $PUBLISHED_ID"
fi

cat > workshop.vdf <<VDF
"workshopitem"
{
  "appid" "$APPID"
  "publishedfileid" "$PUBLISHED_ID"
  "contentfolder" "$BUILD_PARENT"
  "visibility" "$VISIBILITY"
  "title" "$TITLE"
  "description" "$DESCRIPTION"
  "changenote" "$CHANGE_NOTE"
  "previewfile" "$PREVIEW_FILE"
}
VDF

echo "Вывод workshop.vdf для дебага:"
cat workshop.vdf

steamcmd +login "$STEAM_USERNAME" "$STEAM_PASSWORD" "$STEAM_TOTP" \
         +workshop_build_item "$(pwd)/workshop.vdf" +quit