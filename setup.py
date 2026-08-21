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

def input_tty(prompt=''):
    """Читает ввод напрямую из терминала, обходя занятый stdin"""
    print(prompt, end='', flush=True)
    try:
        with open('/dev/tty', 'r') as tty:
            return tty.readline().rstrip('\n')
    except:
        # Fallback на обычный input если /dev/tty недоступен
        return input(prompt)

def print_status(status, message):
    colors = {
        'ok': Colors.GREEN,
        'error': Colors.RED,
        'warning': Colors.YELLOW,
        'info': Colors.BLUE
    }
    color = colors.get(status, Colors.RESET)
    print(f"{color}{message}{Colors.RESET}")

def check_service_installed():
    return os.path.exists(SERVICE_FILE) and os.path.exists(BOT_DIR)

def get_service_status():
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
    print_status('info', '\n🔍 Проверка зависимостей...')
    
    try:
        subprocess.run(['docker', '--version'], capture_output=True, check=True)
        print_status('ok', '✓ Docker установлен')
    except:
        print_status('error', '✗ Docker не установлен')
        return False
    
    try:
        result = subprocess.run(
            ['docker', 'ps', '-a', '--filter', 'name=amnezia-awg2', '--format', '{{.Names}}'],
            capture_output=True, text=True
        )
        if 'amnezia-awg2' in result.stdout:
            print_status('ok', '✓ Контейнер amnezia-awg2 найден')
        else:
            print_status('warning', '⚠ Контейнер amnezia-awg2 не найден')
    except:
        print_status('warning', '⚠ Не удалось проверить контейнер')
    
    try:
        subprocess.run(['python3', '--version'], capture_output=True, check=True)
        print_status('ok', '✓ Python3 установлен')
    except:
        print_status('error', '✗ Python3 не установлен')
        return False
    
    return True

def install_dependencies():
    print_status('info', '\n📦 Установка зависимостей...')
    
    os.makedirs(BOT_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    venv_path = Path(BOT_DIR) / 'venv'
    if not venv_path.exists():
        subprocess.run([sys.executable, '-m', 'venv', str(venv_path)], check=True)
        print_status('ok', '✓ Virtual environment создан')
    
    pip_path = venv_path / 'bin' / 'pip'
    subprocess.run([str(pip_path), 'install', '--upgrade', 'pip'], capture_output=True)
    subprocess.run([str(pip_path), 'install', 'python-telegram-bot==22.8'], check=True)
    print_status('ok', '✓ Зависимости установлены')

def create_bot_file(token):
    print_status('info', '\n📝 Создание файла бота...')
    
    # Скачиваем bot.py из репозитория
    bot_path = Path(BOT_DIR) / 'bot.py'
    try:
        result = subprocess.run(
            ['curl', '-fsSL', 'https://raw.githubusercontent.com/A1-EVO/WG_STAT_BOT/main/bot.py.template'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            bot_code = result.stdout.replace('__TOKEN_PLACEHOLDER__', token)
            with open(bot_path, 'w') as f:
                f.write(bot_code)
            os.chmod(bot_path, 0o755)
            print_status('ok', '✓ Файл бота создан')
            return
    except:
        pass
    
    # Fallback: встроенный код
    print_status('warning', '⚠ Не удалось скачать bot.py из репозитория, используем встроенный')
    # ... здесь весь код бота как раньше ...
    print_status('error', '✗ Встроенный код бота не реализован в этой версии')
    sys.exit(1)

def create_service_file():
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
    print_status('info', '\n🚀 Установка сервиса...')
    
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'enable', 'amnezia-bot'], check=True)
    subprocess.run(['systemctl', 'start', 'amnezia-bot'], check=True)
    
    print_status('ok', '✓ Сервис установлен и запущен')

def uninstall_service():
    print_status('info', '\n🗑️  Удаление сервиса...')
    
    subprocess.run(['systemctl', 'stop', 'amnezia-bot'], capture_output=True)
    subprocess.run(['systemctl', 'disable', 'amnezia-bot'], capture_output=True)
    
    if os.path.exists(SERVICE_FILE):
        os.remove(SERVICE_FILE)
    
    subprocess.run(['systemctl', 'daemon-reload'], capture_output=True)
    
    print_status('ok', '✓ Сервис удален')

def uninstall_all():
    uninstall_service()
    if os.path.exists(BOT_DIR):
        shutil.rmtree(BOT_DIR)
        print_status('ok', '✓ Директория бота удалена')

def show_menu():
    status = get_service_status()
    
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}  AmneziaWG Telegram Bot Installer{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
    
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
    if os.geteuid() != 0:
        print_status('error', '✗ Скрипт должен быть запущен от root')
        sys.exit(1)
    
    while True:
        options = show_menu()
        choice = input_tty("\nВыберите действие: ").strip()
        
        if not choice:
            continue
        
        if choice in ['exit', str(len(options))]:
            print_status('info', '\nДо свидания!')
            break
        
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(options):
                print_status('error', '✗ Неверный выбор')
                continue
            action = options[idx]
        except ValueError:
            action = choice
        
        if action == 'install':
            if not check_requirements():
                continue
            
            token = input_tty("\nВведите токен Telegram бота: ").strip()
            if not token:
                print_status('error', '✗ Токен не может быть пустым')
                continue
            
            install_dependencies()
            create_bot_file(token)
            create_service_file()
            install_service()
            
            print_status('ok', '\n✅ Установка завершена!')
        
        elif action == 'toggle':
            status = get_service_status()
            if status == 'stopped':
                subprocess.run(['systemctl', 'start', 'amnezia-bot'])
                print_status('ok', '✓ Бот запущен')
            else:
                subprocess.run(['systemctl', 'stop', 'amnezia-bot'])
                print_status('ok', '✓ Бот остановлен')
        
        elif action == 'reinstall':
            print_status('warning', '\n⚠️  Это удалит текущую установку')
            confirm = input_tty("Продолжить? (y/N): ").strip().lower()
            if confirm == 'y':
                uninstall_service()
                if os.path.exists(BOT_DIR):
                    shutil.rmtree(BOT_DIR)
                
                if not check_requirements():
                    continue
                
                token = input_tty("\nВведите токен Telegram бота: ").strip()
                if not token:
                    continue
                
                install_dependencies()
                create_bot_file(token)
                create_service_file()
                install_service()
                
                print_status('ok', '\n✅ Переустановка завершена!')
        
        elif action == 'uninstall':
            print_status('warning', '\n⚠️  Это полностью удалит бота и все бекапы')
            confirm = input_tty("Продолжить? (y/N): ").strip().lower()
            if confirm == 'y':
                uninstall_all()
                print_status('ok', '\n✅ Удаление завершено!')
        
        elif action == 'status':
            subprocess.run(['systemctl', 'status', 'amnezia-bot', '--no-pager', '-l'])
            input_tty("\nНажмите Enter для продолжения...")
        
        elif action == 'logs':
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
        import traceback
        traceback.print_exc()
        sys.exit(1)
