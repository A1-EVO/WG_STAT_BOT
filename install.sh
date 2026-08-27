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

# Устанавливаем curl если его нет
if ! command -v curl &> /dev/null && ! command -v wget &> /dev/null; then
    echo "⏳ Установка curl..."
    apt-get update -qq && apt-get install -y -qq curl >/dev/null 2>&1 || true
fi

TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT
cd "$TMPDIR"

echo "⏳ Скачивание setup.py..."

if command -v curl &> /dev/null; then
    curl -fsSL "https://raw.githubusercontent.com/A1-EVO/WG_STAT_BOT/main/setup.py" -o setup.py
elif command -v wget &> /dev/null; then
    wget -q "https://raw.githubusercontent.com/A1-EVO/WG_STAT_BOT/main/setup.py" -O setup.py
else
    echo "✗ Ни curl ни wget не найдены"
    exit 1
fi

if [ ! -s setup.py ]; then
    echo "✗ Не удалось скачать setup.py (файл пустой)"
    exit 1
fi

echo "✓ Файлы скачаны"
echo ""

python3 setup.py
