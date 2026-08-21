#!/bin/bash
set -e

echo "============================================================"
echo "  AmneziaWG Telegram Bot Installer"
echo "============================================================"
echo ""

# Проверка root
if [ "$EUID" -ne 0 ]; then
    echo "✗ Скрипт должен быть запущен от root (используйте sudo)"
    exit 1
fi

# Создание временной директории
TMPDIR=$(mktemp -d)
cd "$TMPDIR"

echo "⏳ Скачивание файлов..."

# Скачивание setup.py
curl -fsSL "https://raw.githubusercontent.com/A1-EVO/WG_STAT_BOT/main/setup.py" -o setup.py

if [ ! -f setup.py ]; then
    echo "✗ Не удалось скачать setup.py"
    rm -rf "$TMPDIR"
    exit 1
fi

echo "✓ Файлы скачаны"
echo ""

# Запуск инсталлятора в интерактивном режиме
python3 setup.py
EXIT_CODE=$?

# Очистка
cd /
rm -rf "$TMPDIR"

exit $EXIT_CODE
