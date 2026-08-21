#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
from pathlib import Path

BOT_DIR = '/opt/amnezia-bot'
SERVICE_FILE = '/etc/systemd/system/amnezia-bot.service'
BACKUP_DIR = f'{BOT_DIR}/backups'

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_status(status, message):
    """Вывод статуса с цветом"""
    colors = {
        'ok': Colors.GREEN,
        'error': Colors.RED,
        'warning': Colors.YELLOW,
        'info': Colors.BLUE
    }
    color = colors.get(status, Colors.RESET)
    print(f"{color}{message}{Colors.RESET}")

def check_service_installed():
    """Проверка установлен ли сервис"""
    return os.path.exists(SERVICE_FILE) and os.path.exists(BOT_DIR)

def get_service_status():
    """Получить статус сервиса"""
    if not check_service_installed():
        return 'not_installed'
    
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', 'amnezia-bot'],
            capture_output=True, text=True
        )
        return 'running' if result.returncode == 0 else 'stopped'
    except:
        return 'error'

def check_requirements():
    """Проверка зависимостей"""
    print_status('info', '\n🔍 Проверка зависимостей...')
    
    # Проверка Docker
    try:
        subprocess.run(['docker', '--version'], capture_output=True, check=True)
        print_status('ok', '✓ Docker установлен')
    except:
        print_status('error', '✗ Docker не установлен')
        return False
    
    # Проверка контейнера
    try:
        result = subprocess.run(
            ['docker', 'ps', '-a', '--filter', 'name=amnezia-awg2', '--format', '{{.Names}}'],
            capture_output=True, text=True
        )
        if 'amnezia-awg2' in result.stdout:
            print_status('ok', '✓ Контейнер amnezia-awg2 найден')
        else:
            print_status('warning', '⚠ Контейнер amnezia-awg2 не найден (бот будет работать, но без статистики)')
    except:
        print_status('warning', '⚠ Не удалось проверить контейнер')
    
    # Проверка Python
    try:
        subprocess.run(['python3', '--version'], capture_output=True, check=True)
        print_status('ok', '✓ Python3 установлен')
    except:
        print_status('error', '✗ Python3 не установлен')
        return False
    
    return True

def install_dependencies():
    """Установка зависимостей"""
    print_status('info', '\n📦 Установка зависимостей...')
    
    # Создание директорий
    os.makedirs(BOT_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    # Создание venv
    venv_path = Path(BOT_DIR) / 'venv'
    if not venv_path.exists():
        subprocess.run([sys.executable, '-m', 'venv', str(venv_path)], check=True)
        print_status('ok', '✓ Virtual environment создан')
    
    # Установка пакетов
    pip_path = venv_path / 'bin' / 'pip'
    subprocess.run([str(pip_path), 'install', '--upgrade', 'pip'], capture_output=True)
    subprocess.run([str(pip_path), 'install', 'python-telegram-bot==22.8'], check=True)
    print_status('ok', '✓ Зависимости установлены')

def create_bot_file(token):
    """Создание файла бота"""
    print_status('info', '\n📝 Создание файла бота...')
    
    bot_code = f'''#!/usr/bin/env python3
import subprocess
import json
import logging
import os
import tempfile
import tarfile
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

TOKEN = '{token}'
BACKUP_DIR = '{BACKUP_DIR}'
os.makedirs(BACKUP_DIR, exist_ok=True)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BACKUP_FILES = [
    '/opt/amnezia/awg/awg0.conf',
    '/opt/amnezia/awg/clientsTable',
    '/opt/amnezia/awg/wireguard_server_private_key.key',
    '/opt/amnezia/awg/wireguard_server_public_key.key',
    '/opt/amnezia/awg/wireguard_psk.key'
]


def get_clients_table():
    try:
        result = subprocess.run(
            ['docker', 'exec', 'amnezia-awg2', 'cat', '/opt/amnezia/awg/clientsTable'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except:
        pass
    return []


def get_stats():
    try:
        result = subprocess.run(
            ['docker', 'exec', 'amnezia-awg2', 'awg', 'show', 'awg0', 'dump'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return None, f"Ошибка: {{result.stderr}}"
        return result.stdout, None
    except Exception as e:
        return None, str(e)


def parse_stats(raw_data, clients_table):
    name_map = {{}}
    for client in clients_table:
        client_id = client.get('clientId')
        user_data = client.get('userData', {{}})
        if client_id:
            name_map[client_id] = user_data.get('clientName', 'Unknown')
    
    peers = []
    lines = raw_data.strip().split('\\n')
    
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 7:
            pubkey = parts[0]
            peer = {{
                'pubkey': pubkey,
                'name': name_map.get(pubkey, f"Unknown ({{pubkey[:12]}}...)"),
                'endpoint': parts[2] if len(parts) > 2 else 'N/A',
                'allowed_ips': parts[3] if len(parts) > 3 else 'N/A',
                'last_handshake': int(parts[4]) if len(parts) > 4 else 0,
                'rx_bytes': int(parts[5]) if len(parts) > 5 else 0,
                'tx_bytes': int(parts[6]) if len(parts) > 6 else 0
            }}
            
            now = int(datetime.now(timezone.utc).timestamp())
            diff = now - peer['last_handshake']
            
            if peer['last_handshake'] == 0:
                peer['status'] = '⚪ never'
                peer['status_short'] = 'never'
            elif diff < 180:
                peer['status'] = '🟢 online'
                peer['status_short'] = 'online'
            elif diff < 3600:
                peer['status'] = f'🟡 idle ({{diff//60}}m)'
                peer['status_short'] = 'idle'
            else:
                peer['status'] = f'🔴 offline ({{diff//3600}}h)'
                peer['status_short'] = 'offline'
            
            peer['rx_mb'] = peer['rx_bytes'] / (1024 * 1024)
            peer['tx_mb'] = peer['tx_bytes'] / (1024 * 1024)
            peer['total_mb'] = peer['rx_mb'] + peer['tx_mb']
            
            peers.append(peer)
    
    return peers


def create_backup():
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f'amnezia_backup_{{timestamp}}.tar.gz'
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        
        with tarfile.open(backup_path, 'w:gz') as tar:
            for file_path in BACKUP_FILES:
                result = subprocess.run(
                    ['docker', 'exec', 'amnezia-awg2', 'cat', file_path],
                    capture_output=True, timeout=10
                )
                
                if result.returncode == 0:
                    with tempfile.NamedTemporaryFile(delete=False) as tmp:
                        tmp.write(result.stdout)
                        tmp_path = tmp.name
                    
                    arcname = file_path.replace('/opt/amnezia/awg/', '')
                    tar.add(tmp_path, arcname=arcname)
                    os.unlink(tmp_path)
        
        return backup_path, None
    except Exception as e:
        return None, str(e)


def restore_backup(backup_path):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            with tarfile.open(backup_path, 'r:gz') as tar:
                tar.extractall(tmpdir)
            
            for filename in os.listdir(tmpdir):
                local_path = os.path.join(tmpdir, filename)
                container_path = f'/opt/amnezia/awg/{{filename}}'
                
                with open(local_path, 'rb') as f:
                    result = subprocess.run(
                        ['docker', 'exec', '-i', 'amnezia-awg2', 'tee', container_path],
                        input=f.read(), capture_output=True, timeout=10
                    )
                    
                    if result.returncode != 0:
                        return False, f"Ошибка копирования {{filename}}: {{result.stderr.decode()}}"
            
            subprocess.run(['docker', 'restart', 'amnezia-awg2'], timeout=30)
            
        return True, None
    except Exception as e:
        return False, str(e)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data='stats')],
        [InlineKeyboardButton("🟢 Онлайн", callback_data='online')],
        [InlineKeyboardButton("💾 Создать бекап", callback_data='backup_create')],
        [InlineKeyboardButton("📥 Скачать бекап", callback_data='backup_download')],
        [InlineKeyboardButton("📤 Загрузить бекап", callback_data='backup_upload')],
        [InlineKeyboardButton("❓ Помощь", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        '👋 *AmneziaWG Monitor Bot*\\n\\nВыберите действие:',
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    logger.info(f"Callback received: {{data}}")
    
    if data == 'stats':
        await show_stats(query)
    elif data == 'online':
        await show_online(query)
    elif data == 'backup_create':
        await create_backup_handler(query)
    elif data == 'backup_download':
        await download_backup_list(query)
    elif data == 'backup_upload':
        await upload_backup(query, context)
    elif data == 'help':
        await show_help(query)
    elif data == 'back_to_menu':
        await back_to_menu(query)
    elif data.startswith('download_'):
        await download_specific_backup(query, context)


async def show_stats(query):
    clients_table = get_clients_table()
    raw, error = get_stats()
    
    if error:
        await query.edit_message_text(f'❌ Ошибка: {{error}}')
        return
    
    peers = parse_stats(raw, clients_table)
    
    if not peers:
        await query.edit_message_text('📭 Нет подключённых пользователей')
        return
    
    online_count = sum(1 for p in peers if p['status_short'] == 'online')
    peers_sorted = sorted(peers, key=lambda x: (0 if x['status_short'] == 'online' else 1, x['name']))
    
    msg = f'📊 *Статистика ({{len(peers)}} пользователей, {{online_count}} онлайн)*\\n\\n'
    
    for i, peer in enumerate(peers_sorted, 1):
        msg += f"*{{i}}. {{peer['name']}}*\\n"
        msg += f"   {{peer['status']}}\\n"
        msg += f"   IP: `{{peer['allowed_ips']}}`\\n"
        msg += f"   ↓{{peer['rx_mb']:.2f}} MB ↑{{peer['tx_mb']:.2f}} MB\\n"
        msg += f"   Всего: *{{peer['total_mb']:.2f}} MB*\\n\\n"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data='stats')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode='Markdown')


async def show_online(query):
    clients_table = get_clients_table()
    raw, error = get_stats()
    
    if error:
        await query.edit_message_text(f'❌ Ошибка: {{error}}')
        return
    
    peers = parse_stats(raw, clients_table)
    online_peers = [p for p in peers if p['status_short'] == 'online']
    
    if not online_peers:
        await query.edit_message_text('😴 Нет активных пользователей')
        return
    
    msg = f'🟢 *Онлайн ({{len(online_peers)}})*\\n\\n'
    
    for peer in online_peers:
        msg += f"• *{{peer['name']}}*\\n"
        msg += f"  `{{peer['allowed_ips']}}` — {{peer['total_mb']:.2f}} MB\\n\\n"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data='online')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode='Markdown')


async def create_backup_handler(query):
    await query.edit_message_text('⏳ Создаю бекап...')
    
    backup_path, error = create_backup()
    
    if error:
        await query.edit_message_text(f'❌ Ошибка: {{error}}')
        return
    
    backup_name = os.path.basename(backup_path)
    
    keyboard = [
        [InlineKeyboardButton("📥 Скачать этот бекап", callback_data=f'download_{{backup_name}}')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f'✅ *Бекап создан!*\\n\\n'
        f'📦 {{backup_name}}\\n\\n'
        f'Нажмите кнопку ниже чтобы скачать:',
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def download_backup_list(query):
    backups = [f for f in os.listdir(BACKUP_DIR) if f.endswith('.tar.gz')]
    
    if not backups:
        await query.edit_message_text('📭 Нет доступных бекапов')
        return
    
    keyboard = [[InlineKeyboardButton(f"📦 {{b}}", callback_data=f'download_{{b}}')] for b in sorted(backups, reverse=True)]
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        '📥 *Доступные бекапы:*\\n\\nВыберите файл для скачивания:',
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def download_specific_backup(query, context):
    backup_name = query.data.replace('download_', '')
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    
    logger.info(f"Downloading backup: {{backup_path}}")
    
    if not os.path.exists(backup_path):
        await query.edit_message_text('❌ Файл не найден')
        return
    
    try:
        with open(backup_path, 'rb') as f:
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=f,
                filename=backup_name,
                caption=f'📦 Бекап: {{backup_name}}'
            )
        logger.info("Backup sent successfully")
    except Exception as e:
        logger.error(f"Error sending backup: {{e}}")
        await query.edit_message_text(f'❌ Ошибка отправки: {{e}}')


async def upload_backup(query, context):
    await query.edit_message_text(
        '📤 *Загрузка бекапа*\\n\\n'
        'Отправьте файл бекапа (.tar.gz) в чат.\\n\\n'
        '⚠️ *Внимание:* это перезапишет текущую конфигурацию!',
        parse_mode='Markdown'
    )
    context.user_data['awaiting_backup'] = True


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_backup'):
        return
    
    document = update.message.document
    
    if not document.file_name.endswith('.tar.gz'):
        await update.message.reply_text('❌ Файл должен быть .tar.gz архивом')
        return
    
    await update.message.reply_text('⏳ Загружаю и восстанавливаю...')
    
    file = await context.bot.get_file(document.file_id)
    with tempfile.NamedTemporaryFile(delete=False, suffix='.tar.gz') as tmp:
        await file.download_to_drive(tmp.name)
        tmp_path = tmp.name
    
    success, error = restore_backup(tmp_path)
    os.unlink(tmp_path)
    
    context.user_data['awaiting_backup'] = False
    
    if success:
        await update.message.reply_text(
            '✅ *Бекап восстановлен!*\\n\\n'
            'Контейнер перезапущен. Конфигурация обновлена.',
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(f'❌ Ошибка восстановления: {{error}}')


async def show_help(query):
    help_text = (
        '📊 *AmneziaWG Monitor*\\n\\n'
        '*Статистика:*\\n'
        '🟢 online - активен (<3 мин)\\n'
        '🟡 idle - неактивен (3 мин - 1 час)\\n'
        '🔴 offline - давно не подключался\\n'
        '⚪ never - никогда не подключался\\n\\n'
        '*Бекапы:*\\n'
        '💾 Создать - делает архив конфигурации\\n'
        '📥 Скачать - получить файл бекапа\\n'
        '📤 Загрузить - восстановить из файла\\n\\n'
        '*Команды:*\\n'
        '/start - главное меню\\n'
        '/stats - статистика\\n'
        '/online - только онлайн'
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')


async def back_to_menu(query):
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data='stats')],
        [InlineKeyboardButton("🟢 Онлайн", callback_data='online')],
        [InlineKeyboardButton("💾 Создать бекап", callback_data='backup_create')],
        [InlineKeyboardButton("📥 Скачать бекап", callback_data='backup_download')],
        [InlineKeyboardButton("📤 Загрузить бекап", callback_data='backup_upload')],
        [InlineKeyboardButton("❓ Помощь", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        '👋 *AmneziaWG Monitor Bot*\\n\\nВыберите действие:',
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def post_init(application: Application):
    commands = [
        BotCommand("start", "Главное меню"),
        BotCommand("stats", "Статистика пользователей"),
        BotCommand("online", "Только онлайн пользователи")
    ]
    await application.bot.set_my_commands(commands)


def main():
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('stats', lambda u, c: show_stats(u.message)))
    app.add_handler(CommandHandler('online', lambda u, c: show_online(u.message)))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info('Бот запущен')
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
'''
    
    bot_path = Path(BOT_DIR) / 'bot.py'
    with open(bot_path, 'w') as f:
        f.write(bot_code)
    
    os.chmod(bot_path, 0o755)
    print_status('ok', '✓ Файл бота создан')

def create_service_file():
    """Создание systemd service"""
    print_status('info', '\n⚙️  Создание systemd сервиса...')
    
    service_content = f'''[Unit]
Description=AmneziaWG Telegram Bot
After=network.target docker.service

[Service]
Type=simple
User=root
WorkingDirectory={BOT_DIR}
ExecStart={BOT_DIR}/venv/bin/python {BOT_DIR}/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
'''
    
    with open(SERVICE_FILE, 'w') as f:
        f.write(service_content)
    
    print_status('ok', '✓ Systemd service создан')

def install_service():
    """Установка и запуск сервиса"""
    print_status('info', '\n🚀 Установка сервиса...')
    
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'enable', 'amnezia-bot'], check=True)
    subprocess.run(['systemctl', 'start', 'amnezia-bot'], check=True)
    
    print_status('ok', '✓ Сервис установлен и запущен')
    print_status('info', '\nПроверка статуса:')
    subprocess.run(['systemctl', 'status', 'amnezia-bot', '--no-pager', '-l'])

def uninstall_service():
    """Удаление сервиса"""
    print_status('info', '\n🗑️  Удаление сервиса...')
    
    subprocess.run(['systemctl', 'stop', 'amnezia-bot'], capture_output=True)
    subprocess.run(['systemctl', 'disable', 'amnezia-bot'], capture_output=True)
    
    if os.path.exists(SERVICE_FILE):
        os.remove(SERVICE_FILE)
    
    subprocess.run(['systemctl', 'daemon-reload'], capture_output=True)
    
    print_status('ok', '✓ Сервис удален')

def uninstall_all():
    """Полное удаление"""
    uninstall_service()
    
    if os.path.exists(BOT_DIR):
        shutil.rmtree(BOT_DIR)
        print_status('ok', '✓ Директория бота удалена')

def show_menu():
    """Показать главное меню"""
    status = get_service_status()
    
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}  AmneziaWG Telegram Bot Installer{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
    
    # Статус
    status_colors = {
        'not_installed': Colors.RED,
        'running': Colors.GREEN,
        'stopped': Colors.YELLOW,
        'error': Colors.RED
    }
    status_text = {
        'not_installed': '⚫ Не установлен',
        'running': '🟢 Работает',
        'stopped': '🟡 Остановлен',
        'error': '🔴 Ошибка'
    }
    
    color = status_colors.get(status, Colors.RESET)
    text = status_text.get(status, '❓ Неизвестно')
    print(f"\n{Colors.BOLD}Статус:{Colors.RESET} {color}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")
    
    # Меню
    if status == 'not_installed':
        print("1. 📦 Установить бота")
        print("2. ❌ Выход")
        return ['install', 'exit']
    else:
        print("1. ▶️  Запустить бота" if status == 'stopped' else "1. ⏸️  Остановить бота")
        print("2. 🔄 Переустановить бота")
        print("3. 🗑️  Удалить бота")
        print("4. 📊 Проверить статус")
        print("5. 📋 Посмотреть логи")
        print("6. ❌ Выход")
        return ['toggle', 'reinstall', 'uninstall', 'status', 'logs', 'exit']

def main():
    """Главная функция"""
    if os.geteuid() != 0:
        print_status('error', '✗ Скрипт должен быть запущен от root')
        sys.exit(1)
    
    while True:
        options = show_menu()
        choice = input("\nВыберите действие: ").strip()
        
        if choice == 'exit' or (choice.isdigit() and int(choice) == len(options)):
            print_status('info', '\nДо свидания!')
            break
        
        if choice == 'install' or (choice.isdigit() and options[int(choice)-1] == 'install'):
            if not check_requirements():
                print_status('error', '\n✗ Проверка зависимостей не пройдена')
                continue
            
            token = input("\nВведите токен Telegram бота: ").strip()
            if not token:
                print_status('error', '✗ Токен не может быть пустым')
                continue
            
            install_dependencies()
            create_bot_file(token)
            create_service_file()
            install_service()
            
            print_status('ok', '\n✅ Установка завершена!')
            print_status('info', 'Откройте бота в Telegram и отправьте /start')
        
        elif choice == 'toggle' or (choice.isdigit() and options[int(choice)-1] == 'toggle'):
            status = get_service_status()
            if status == 'stopped':
                subprocess.run(['systemctl', 'start', 'amnezia-bot'])
                print_status('ok', '✓ Бот запущен')
            else:
                subprocess.run(['systemctl', 'stop', 'amnezia-bot'])
                print_status('ok', '✓ Бот остановлен')
        
        elif choice == 'reinstall' or (choice.isdigit() and options[int(choice)-1] == 'reinstall'):
            print_status('warning', '\n⚠️  Это удалит текущую установку и создаст новую')
            confirm = input("Продолжить? (y/N): ").strip().lower()
            if confirm == 'y':
                uninstall_service()
                if os.path.exists(BOT_DIR):
                    shutil.rmtree(BOT_DIR)
                
                if not check_requirements():
                    print_status('error', '\n✗ Проверка зависимостей не пройдена')
                    continue
                
                token = input("\nВведите токен Telegram бота: ").strip()
                if not token:
                    print_status('error', '✗ Токен не может быть пустым')
                    continue
                
                install_dependencies()
                create_bot_file(token)
                create_service_file()
                install_service()
                
                print_status('ok', '\n✅ Переустановка завершена!')
        
        elif choice == 'uninstall' or (choice.isdigit() and options[int(choice)-1] == 'uninstall'):
            print_status('warning', '\n⚠️  Это полностью удалит бота и все бекапы')
            confirm = input("Продолжить? (y/N): ").strip().lower()
            if confirm == 'y':
                uninstall_all()
                print_status('ok', '\n✅ Удаление завершено!')
        
        elif choice == 'status' or (choice.isdigit() and options[int(choice)-1] == 'status'):
            subprocess.run(['systemctl', 'status', 'amnezia-bot', '--no-pager', '-l'])
            input("\nНажмите Enter для продолжения...")
        
        elif choice == 'logs' or (choice.isdigit() and options[int(choice)-1] == 'logs'):
            try:
                subprocess.run(['journalctl', '-u', 'amnezia-bot', '-f', '--no-pager'])
            except KeyboardInterrupt:
                pass
        
        else:
            print_status('error', '✗ Неверный выбор')

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print_status('info', '\n\nПрервано пользователем')
        sys.exit(0)
    except Exception as e:
        print_status('error', f'\n✗ Ошибка: {e}')
        sys.exit(1)
