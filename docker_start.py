import os
import sys
import subprocess
import logging
import socket
import time
import json
from pathlib import Path
from dotenv import load_dotenv
import requests

# Визначаємо шлях до каталогу, де лежить цей скрипт
SCRIPT_DIR = Path(__file__).parent.resolve()

# Завантажуємо змінні з .env
dotenv_path = SCRIPT_DIR / '.env'
load_dotenv(dotenv_path)

# Конфігурація Telegram
TG_BOT_ON = os.getenv("TG_BOT_ON", "False").strip().lower()
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

LOG_FILE = SCRIPT_DIR / "docker_startup.log"

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

# --- Читання налаштувань з .env з дефолтними значеннями на випадок їх відсутності ---
BASE_DIR = Path(os.getenv("BASE_DIR", "/home/ifess"))

# Отримуємо рядок проектів, ділимо за комою та прибираємо зайві прогалини/порожні елементи
raw_projects = os.getenv("PROJECTS", "dns,traefik,portainer,glances")
PROJECTS = [p.strip() for p in raw_projects.split(",") if p.strip()]

try:
    CHECK_TIMEOUT = int(os.getenv("CHECK_TIMEOUT", "60"))
    CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "2"))
except ValueError:
    logging.warning("Помилка читання CHECK_TIMEOUT або CHECK_INTERVAL з .env. Використовуються дефолтні значення (60 та 2).")
    CHECK_TIMEOUT = 60
    CHECK_INTERVAL = 2
# -------------------------------------------------------------------------------


def get_telegram_ip():
    """Резервний IP Telegram на випадок проблем із DNS під час старту мережі."""
    try:
        return socket.gethostbyname("api.telegram.org")
    except socket.gaierror:
        logging.warning("DNS-резолв не вдався. Використовуємо резервну IP для Telegram API.")
        return "149.154.167.220"

def send_tg_message(text):
    """Надсилання повідомлень у Telegram з обходом системних проксі"""
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
            logging.error(f"Неможливо відправити повідомлення до Telegram: {e}")
    else:
        logging.info("Надсилання повідомлень у Telegram вимкнено у налаштуваннях.")

def wait_for_project_ready(project_dir, project_name):
    """Динамічний очікування готовності всіх контейнерів проекту."""
    logging.info(f"Очікування стабілізації контейнерів проекту [{project_name}]...")
    start_time = time.time()
    
    while time.time() - start_time < CHECK_TIMEOUT:
        try:
            # Отримуємо детальний статус контейнерів поточного проекту в JSON
            result = subprocess.run(
                ["docker", "compose", "ps", "--format", "json"],
                cwd=str(project_dir),
                check=True,
                capture_output=True,
                text=True
            )
            
            output = result.stdout.strip()
            if not output:
                # Контейнери ще не встигли створитися в Docker-демоні
                time.sleep(CHECK_INTERVAL)
                continue
                
            # Парсим JSON (docker compose ps віддає або масив об'єктів, або рядки NDJSON залежно від версії)
            try:
                containers = json.loads(output)
                if not isinstance(containers, list):
                    containers = [containers]
            except json.JSONDecodeError:
                containers = [json.loads(line) for line in output.splitlines() if line.strip()]

            if not containers:
                time.sleep(CHECK_INTERVAL)
                continue

            all_running = True
            for container in containers:
                state = container.get("State", "").lower()
                health = container.get("Health", "").lower()
                c_name = container.get("Name", "unknown")

                # Если контейнер упал или завершился с ошибкой
                if state in ("exited", "dead"):
                    logging.error(f"Контейнер {c_name} впав зі статусом '{state}'!")
                    return f"Контейнер {c_name} не зміг стартувати"

                # Если настроен Healthcheck, приоритетно проверяем его статус
                if health:
                    if health != "healthy":
                        all_running = False
                # Если Healthcheck нет, проверяем базовое состояние контейнера
                elif state != "running":
                    all_running = False

            if all_running:
                elapsed = round(time.time() - start_time, 1)
                logging.info(f"✅ Проєкт [{project_name}] успішно стабілізувався за {elapsed} сек.")
                return None

        except Exception as e:
            logging.warning(f"Помилка під час перевірки статусу контейнерів: {e}")
        
        time.sleep(CHECK_INTERVAL)

    return f"Таймаут очікування старту проекту ({CHECK_TIMEOUT} сек)"

def run_docker_up(project_dir, project_name):
    """Запускає проект та записує докладний висновок команди у лог."""
    logging.info(f"Запуск проекту у папці: {project_dir}")
    try:
        result = subprocess.run(
            ["docker", "compose", "up", "-d"],
            cwd=str(project_dir),
            check=True,
            capture_output=True,
            text=True
        )
        if result.stderr:
            logging.info(f"[Docker Output {project_name}]:\n{result.stderr.strip()}")
        return None
    except subprocess.CalledProcessError as e:
        error_context = e.stderr.strip() if e.stderr else str(e)
        logging.error(f"Не вдалося запустити {project_name}. Деталі:\n{error_context}")
        return f"Помилка складання/запуску {project_name}"
    except FileNotFoundError:
        logging.critical("Команда 'docker' не знайдена у системі. Вихід.")
        sys.exit(1)

def start_compose_projects():
    hostname = os.uname().nodename
    
    if not BASE_DIR.is_dir():
        error_msg = f"❌ <b>[{hostname}]</b> Помилка: Директорія {BASE_DIR} не знайдено!"
        logging.error(f"Директория {BASE_DIR} не найдена!")
        send_tg_message(error_msg)
        sys.exit(1)

    logging.info(f"=== ПОЧАТОК ПРОЦЕСУ ПОСЛІДОВНОГО ЗАПУСКУ НА СЕРВЕРІ [{hostname}] ===")
    send_tg_message(f"🚀 <b>[{hostname}]</b> Розпочато процес запуску Docker контейнерів...")

    errors = []
    started_count = 0

    for project in PROJECTS:
        dir_path = BASE_DIR / project
        logging.info("-" * 50)
        logging.info(f"Наступний у черзі: [{project}]")

        has_yml = (dir_path / "docker-compose.yml").is_file()
        has_yaml = (dir_path / "docker-compose.yaml").is_file()

        if not dir_path.is_dir() or not (has_yml or has_yaml):
            logging.warning(f"Проект або docker-compose.yml у папці '{project}' не знайдено! Пропускаємо...")
            continue

        # Шаг 1: Посылаем команду на запуск
        up_err = run_docker_up(dir_path, project)
        if up_err:
            errors.append(up_err)
            continue
        
        # Шаг 2: Динамически ждем, пока все поднимется
        wait_err = wait_for_project_ready(dir_path, project)
        if wait_err:
            errors.append(f"{project} ({wait_err})")
        else:
            started_count += 1

    logging.info("-" * 50)
    
    # Финальный отчет
    if errors:
        error_details = "\n".join([f"❌ {e}" for e in errors])
        finish_msg = f"⚠️ <b>[{hostname}]</b> Контейнери запущені, але виникли помилки:\n\n{error_details}"
        logging.error(f"Процес завершено з помилками: {', '.join(errors)}")
    elif started_count == 0:
        finish_msg = f"ℹ️ <b>[{hostname}]</b> Жоден проект зі списку не було запущено (папки не знайдено)."
        logging.info("Жоден проект не запущено.")
    else:
        finish_msg = f"✅ <b>[{hostname}]</b> Всі вказані проекти Docker Compose успішно запущені!"
        logging.info("=== ВСІ ПРОЕКТИ УСПІШНО ЗАПУЩЕНІ ===")

    send_tg_message(finish_msg)

if __name__ == "__main__":
    start_compose_projects()
