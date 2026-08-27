#!/bin/bash
set -e

echo "============================================================"
echo "  AmneziaWG Telegram Bot Installer"
echo "============================================================"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo "✗ Скрипт должен быть запущен от root (используйте sudo)"
    exit 1
fi

if ! command -v curl &> /dev/null && ! command -v wget &> /dev/null; then
    echo "⏳ Установка curl..."
    apt-get update -qq && apt-get install -y -qq curl >/dev/null 2>&1 || true
fi

SETUP_FILE="/tmp/amnezia_bot_setup.py"

echo "⏳ Скачивание setup.py..."

if command -v curl &> /dev/null; then
    curl -fsSL "https://raw.githubusercontent.com/A1-EVO/WG_STAT_BOT/main/setup.py" -o "$SETUP_FILE"
elif command -v wget &> /dev/null; then
    wget -q "https://raw.githubusercontent.com/A1-EVO/WG_STAT_BOT/main/setup.py" -O "$SETUP_FILE"
else
    echo "✗ Ни curl ни wget не найдены"
    exit 1
fi

if [ ! -s "$SETUP_FILE" ]; then
    echo "✗ Не удалось скачать setup.py (файл пустой)"
    exit 1
fi

echo "✓ Файлы скачаны"
echo ""

python3 "$SETUP_FILE"
EXIT_CODE=$?

rm -f "$SETUP_FILE"
exit $EXIT_CODE
