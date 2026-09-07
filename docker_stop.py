import os
import sys
import subprocess
import logging
import socket
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import requests

# Визначаємо шлях до лог-файлу в тому же каталозі, де лежить цей скрипт
SCRIPT_DIR = Path(__file__).parent.resolve()

# Завантажуємо змінні з .env
dotenv_path = SCRIPT_DIR / '.env'
load_dotenv(dotenv_path)

# Конфігурація Telegram
TG_BOT_ON = os.getenv("TG_BOT_ON", "False").strip().lower()
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

LOG_FILE = SCRIPT_DIR / "docker_shutdown.log"

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

# --- Читання критичної інфраструктури з .env ---
# Отримуємо рядок, ділимо по комі та очищаємо від пробілів
raw_critical = os.getenv("CRITICAL_PROJECTS", "traefik,portainer,bind9")
CRITICAL_PROJECTS = [p.strip() for p in raw_critical.split(",") if p.strip()]
# Створюємо set для швидкої перевірки при скануванні папок
delayed_folders = set(CRITICAL_PROJECTS)
# -----------------------------------------------

def get_telegram_ip():
    """Хардкод IP-адреси Telegram на випадок, якщо DNS (bind9) вже ліг під час зупинки мережі."""
    try:
        return socket.gethostbyname("api.telegram.org")
    except socket.gaierror:
        logging.warning("DNS-резолв не вдався. Використовуємо резервний IP для Telegram API.")
        return "149.154.167.220"

def send_tg_message(text):
    """Надсилання повідомлення в Telegram з обходом впалого DNS та системних проксі"""
    if TG_BOT_ON == 'true':
        if not TG_BOT_TOKEN or not TG_CHAT_ID:
            logging.error("Telegram увімкнено, але TG_BOT_TOKEN або TG_CHAT_ID не заповнені в .env")
            return None

        tg_ip = get_telegram_ip()
        url = f"https://{tg_ip}/bot{TG_BOT_TOKEN}/sendMessage"
        
        payload = {
            "chat_id": TG_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }
        
        headers = {"Host": "api.telegram.org"}
        
        try:
            response = requests.post(url, json=payload, headers=headers, proxies={"http": None, "https": None}, verify=False, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Не вдалося надіслати сповіщення в Telegram: {e}")
    else:
        logging.info(f"[{os.getenv('TG_BOT_ON')}] Надсилання повідомлення в Telegram вимкнено в налаштуваннях")

def stop_compose_projects(base_path="."):
    target_path = Path(base_path).resolve()
    hostname = os.uname().nodename
    
    logging.info(f"=== РОЗПОЧАТО ПРОЦЕС ЗУПИНКИ НА СЕРВЕРІ [{hostname}] ===")
    logging.info(f"Пошук Docker Compose проєктів у: {target_path}")
    
    send_tg_message(f"🚀 <b>[{hostname}]</b> Розпочато процес зупинки Docker контейнерів...")

    standard_projects = []
    
    # Динамічно створюємо карту черги для критичних проєктів із збереженням порядку з .env
    priority_map = {folder: [] for folder in CRITICAL_PROJECTS}
    
    errors = []

    # Рекурсивний пошук файлів
    for path in target_path.rglob("*"):
        if path.is_file() and path.name in ("docker-compose.yml", "docker-compose.yaml"):
            project_dir = path.parent
            if project_dir.name in delayed_folders:
                priority_map[project_dir.name].append(project_dir)
            else:
                standard_projects.append(project_dir)

    # ЕТАП 1: Зупинка звичайних проєктів
    if standard_projects:
        logging.info("--- Зупинка стандартних проєктів ---")
        for project in standard_projects:
            err = run_docker_down(project)
            if err:
                errors.append(err)

    # ЕТАП 2: Послідовна зупинка критичної інфраструктури (Строго по черзі з .env)
    logging.info("--- Зупинка критичної інфраструктури ---")
    for folder_name in CRITICAL_PROJECTS:
        for project in priority_map.get(folder_name, []):
            err = run_docker_down(project)
            if err:
                errors.append(err)

    # Фінальний звіт
    if errors:
        error_details = "\n".join([f"❌ {e}" for e in errors])
        finish_msg = f"⚠️ <b>[{hostname}]</b> Контейнери зупинено, але виникли помилки:\n\n{error_details}"
        logging.error(f"Процес завершено з помилками: {', '.join(errors)}")
    else:
        finish_msg = f"✅ <b>[{hostname}]</b> Усі Docker Compose проєкти успішно зупинено!"
        logging.info("=== ВСІ ПРОЄКТИ УСПІШНО ЗУПИНЕНО ===")

    send_tg_message(finish_msg)

def run_docker_down(project_dir):
    """Зупиняє проєкт і записує детальний вивід команди в лог."""
    logging.info(f"Зупинка проєкту в папці: {project_dir}")
    try:
        result = subprocess.run(
            ["docker", "compose", "down", "--remove-orphans"],
            cwd=str(project_dir),
            check=True,
            capture_output=True,
            text=True
        )
        if result.stderr:
            logging.info(f"[Docker Output {project_dir.name}]:\n{result.stderr.strip()}")
        return None
    except subprocess.CalledProcessError as e:
        error_context = e.stderr.strip() if e.stderr else str(e)
        logging.error(f"Не вдалося зупинити {project_dir.name}. Деталі:\n{error_context}")
        return f"Помилка в {project_dir.name}"
    except FileNotFoundError:
        logging.critical("Команда 'docker' не знайдена в системи. Вихід.")
        sys.exit(1)

if __name__ == "__main__":
    search_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    stop_compose_projects(search_dir)
