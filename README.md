# AmneziaWG Telegram Bot

Telegram бот для мониторинга статистики AmneziaWG VPN сервера с возможностью резервного копирования и восстановления конфигурации.

![Status](https://img.shields.io/badge/status-active-success)
![Python](https://img.shields.io/badge/python-3.8+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## 🚀 Возможности

- 📊 **Мониторинг статистики** - отслеживание трафика по каждому пользователю
- 🟢 **Онлайн статус** - определение активных подключений в реальном времени
- 💾 **Резервное копирование** - создание бекапов конфигурации через Telegram
- 📥 **Загрузка бекапов** - скачивание бекапов прямо из чата
- 📤 **Восстановление** - загрузка бекапов и восстановление конфигурации
- 🔄 **Автозапуск** - автоматический старт после перезагрузки сервера
- 📱 **Удобный интерфейс** - кнопочное меню в Telegram

## 📋 Требования

- Ubuntu/Debian Linux
- Docker
- Python 3.8+
- AmneziaWG контейнер (amnezia-awg2)

## ⚡ Быстрая установка

Одна команда для установки:

```bash
curl -fsSL https://raw.githubusercontent.com/A1-EVO/WG_STAT_BOT/main/setup.py | sudo python3
