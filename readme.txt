docker_start_stop -- 
Невеличкий скрипт для автоматичного запуску основних докер контейнерів, або зупинка усіх контейнерів.
Додатково відправляє звіт в телеграм.

Всі налаштування винесені в файл .env

Швидкий запуск
~/dstop
~/dstart


# Встановлення застосунку (скрипта)
======================================
1. Копіюємо до робочої директорії:
sudo mc /mnt/win_share /home/ifess

2. Надаємо права та встановлюємо оточення:
sudo chown -R ifess:ifess /home/ifess/docker_start_stop
cd docker_start_stop/
python3 -m venv venv
ls -ahl
source venv/bin/activate
pip install python-dotenv requests
deactivate
cd ..

3. Додати користувача в групу docker (Рекомендовано)
Це стандартний і найправильніший спосіб у Linux. 
Він дозволить вашому користувачу ifess виконувати будь-які команди Docker (і запускати цей скрипт) без sudo.
Додайте користувача до групи:
sudo usermod -aG docker ifess

Обов'язково перезапустіть сесію користувача, щоб зміни набули чинності.
Найпростіше — перепідключитися по SSH або виконати команду:
newgrp docker

4. Можно скопіювати баш скрипти одразу в корінь робочої директорії.
Швидкий запуск
~/dstop
~/dstart

======================================
Вимкнення контйнерів
======================================
source /home/ifess/docker_stop/venv/bin/activate
python3 /home/ifess/docker_stop/stop_all_compose.py /home/ifess
deactivate
docker ps
sudo systemctl stop docker
sudo shutdown -h now.

або

/home/ifess/docker_start_stop/venv/bin/python3 /home/ifess/docker_start_stop/docker_stop.py /home/ifess

або

~/dstop

======================================
Увімкнення контйнерів
======================================
source /home/ifess/docker_stop/venv/bin/activate
python3 /home/ifess/docker_stop/stop_all_compose.py /home/ifess
deactivate
docker ps

або

/home/ifess/docker_start_stop/venv/bin/python3 /home/ifess/docker_start_stop/docker_start.py

або

~/dstart

=============================================================
Короткий скрипт запуску вимкнення/увімкнення
=============================================================
як вкласти команду запуску python скрипта в bash файл щоб скоротити команду запуску: /home/ifess/docker_start_stop/venv/bin/python3 /home/ifess/docker_start_stop/docker_stop.py /home/ifess
Щоб скоротити цю довгу команду, найкраще створити bash-скрипт (або додати аліас).
Ось найшвидший і найправильніший спосіб через bash-файл.
Крок 1: Створення bash-файлу
Створіть новий файл (наприклад, з назвою dstop) у вашій домашній директорії:
bash
nano ~/dstop
mcedit ~/dstop
Крок 2: Наповнення файлу
Вставте у файл наступний код (знак $@ дозволить вам за потреби передавати додаткові аргументи):
bash
#!/bin/bash
/home/ifess/docker_start_stop/venv/bin/python3 /home/ifess/docker_start_stop/docker_stop.py /home/ifess "$@"
Збережіть файл (Ctrl+O, Enter) та вийдіть з редактора (Ctrl+X).
Крок 3: Робимо файл виконуваним
Надайте файлу права на запуск:
bash
chmod +x ~/dstop
Тепер ви можете запускати ваш Python скрипт короткою командою: 
~/dstop

Крок 1: Створення bash-файлу
Створіть новий файл (наприклад, з назвою dstart) у вашій домашній директорії:
bash
mcedit ~/dstart
Крок 2: Наповнення файлу
Вставте у файл наступний код (знак $@ дозволить вам за потреби передавати додаткові аргументи):
bash
#!/bin/bash
/home/ifess/docker_start_stop/venv/bin/python3 /home/ifess/docker_start_stop/docker_start.py /home/ifess "$@"
Збережіть файл (Ctrl+O, Enter) та вийдіть з редактора (Ctrl+X).
Крок 3: Робимо файл виконуваним
Надайте файлу права на запуск:
bash
chmod +x ~/dstart
Тепер ви можете запускати ваш Python скрипт короткою командою: 
~/dstart


======================================================
Коректне вимкнення сервера із запущеним Docker!!!
======================================================
Коректне вимкнення сервера із запущеним Docker запобігає пошкодженню баз даних та втраті даних. 
Найкращий спосіб — спочатку плавно зупинити всі контейнери, потім службу Docker, і тільки після цього вимкнути сам сервер.
Виконайте ці кроки в терміналі через ssh або безпосередньо:
1. Зупиніть усі контейнери
Зупинка дозволяє програмам зберегти стан і коректно завершити транзакції.
Якщо ви використовуєте окремі контейнери:
bash
docker stop $(docker ps -q)
Якщо ви використовуєте Docker Compose (перейдіть у папку з файлом docker-compose.yml та введіть):
bash
docker-compose down
або
nano stop_all_compose.sh
chmod +x stop_all_compose.sh
./stop_all_compose.sh
або
nano stop_all_compose.py
chmod +x stop_all_compose.py
python3 stop_all_compose.py

2. Зупиніть службу Docker
Це гарантує, що Docker демон (daemon) завершить усі фонові процеси та відмонтує файлові системи без помилок.
bash
sudo systemctl stop docker
3. Вимкніть сервер
Тепер сервер можна безпечно вимикати стандартною командою shutdown.
bash
sudo shutdown -h now

./stop_all_compose.sh
sudo systemctl stop docker
sudo shutdown -h now

# Переходимо в папку зі скриптом
cd docker_stop/

# Створюємо та активуємо віртуальне середовище
python3 -m venv venv
source venv/bin/activate

# Встановлюємо бібліотеки всередині venv
pip install python-dotenv requests

Запуск:
Для поточної папки:
bash
python3 stop_all_compose.py

Для конкретної директорії:
bash
python3 stop_all_compose.py /home/ifess