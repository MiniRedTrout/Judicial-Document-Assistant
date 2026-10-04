# Запуск Windows и Linux/Docker

Это инструкция по текущей реализации. API-ключ LLM, окончательный классификатор команды и подтверждение доставки письма ещё необходимо проверить. Docker-сборка в среде подготовки не запускалась: Docker здесь недоступен.

## Что установлено и что переносить

pdf2image — Python-обёртка для преобразования страниц PDF в изображения. Poppler — отдельные программы pdfinfo/pdftoppm. EasyOCR — распознавание текста, использующее PyTorch и веса моделей.

В .venv установлены Python-пакеты. На Windows Poppler распакован отдельно; POPPLER_PATH указывает на папку с exe. На Linux тот же код использует системный Poppler из PATH. Windows exe и локальную .venv на Linux копировать нельзя.

## Windows

1. Для нового окружения установите Python 3.12. Можно продолжать использовать уже рабочую .venv с Python 3.14.
2. В корне проекта:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-ocr.txt
```

Не пересоздавайте существующую рабочую .venv. Перед установкой пакетов остановите сервер/скрипты, использующие cv2.pyd. WinError 5 может означать блокировку файла.

3. Если .env ещё нет, скопируйте .env.example в .env. Не заменяйте существующий .env шаблоном.
4. Распакуйте ZIP Poppler для Windows (Release, не Source code). Укажите в .env путь к папке с pdftoppm.exe и pdfinfo.exe:

```dotenv
POPPLER_PATH=C:\Users\Gigabyte\Desktop\poopler\poppler-26.09.0\Library\bin
```

Это пример вашего текущего пути; на другом компьютере он будет другим. В обновлённом src/utils/imaging.py путь явно передаётся convert_from_path. Прямой импорт модуля вне backend не загружает .env автоматически.

5. Проверка зависимостей и запуск:

```powershell
python -c "import cv2, pdf2image, easyocr; print('Python-зависимости доступны')"
& "C:\Users\Gigabyte\Desktop\poopler\poppler-26.09.0\Library\bin\pdfinfo.exe" -v
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Фронт http://127.0.0.1:8000/ . После любого изменения .env полностью перезапустите сервер. Переменные текущего окружения имеют приоритет над .env.

## Linux-сервер: Docker Compose

Нужны Docker Engine и Compose plugin на целевой Linux-машине. Загрузите исходники из GitLab; .env создайте на сервере отдельно.

```bash
cp .env.example .env
# отредактируйте .env своим редактором
docker compose up --build -d
docker compose ps
docker compose logs -f web
```

Dockerfile использует Python 3.12, устанавливает poppler-utils, CPU PyTorch и Python-зависимости OCR. Интернет нужен для сборки. Compose перекрывает POPPLER_PATH пустой строкой, поэтому локальный Windows-путь не помешает Linux.

Проверка внутри контейнера:

```bash
docker compose exec web pdfinfo -v
docker compose exec web pdftoppm -h
docker compose exec web python -c "import cv2, pdf2image, easyocr; print('OCR dependencies OK')"
```

Один worker обязателен для текущего прототипа с фоновыми задачами и восстановлением статусов. Первый OCR скачивает веса; это требует доступа к источнику моделей. Прогрейте OCR перед демонстрацией:

```bash
docker compose exec web python -c "from src.pdf_extractor.ocr import get_ocr_engine; print(get_ocr_engine().name)"
```

Веса сохраняются через EASYOCR_MODULE_PATH в data/cache/easyocr на хосте. Данные/SQLite — в storage на хосте. Не удаляйте эти папки при обновлении.

Сервис доступен только на 127.0.0.1 сервера. Для открытия с Windows создайте SSH-туннель в отдельном PowerShell:

```powershell
ssh -L 8000:127.0.0.1:8000 USER@SERVER
```

Замените USER/SERVER своими значениями, откройте http://127.0.0.1:8000/ на своём компьютере. Локальный сервис на том же порту должен быть остановлен. Для публичного размещения нужны отдельно настроенные доступ и HTTPS: встроенной авторизации у прототипа нет.

Обновление и остановка:

```bash
docker compose up --build -d
docker compose down
```

Табличный извлекатель Camelot отключён в Compose: OCR и заполнение полей продолжают работать. Для него есть requirements-tables.txt, но Docker по умолчанию этот дополнительный модуль не устанавливает.

## Linux без Docker

Для Debian/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils python3-venv libgomp1 libglib2.0-0
python3 -m venv .venv
. .venv/bin/activate
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-ocr.txt
```

Python должен удовлетворять pyproject.toml. POPPLER_PATH в серверном .env оставьте пустым. Проверьте pdfinfo -v, затем запустите uvicorn аналогично Windows. Для постоянной работы потребуется настроить systemd самостоятельно; Compose уже содержит restart policy.

## LLM и почта

LLM_API_BASE/LLM_MODEL/LLM_API_KEY выбирают совместимый API. Без ключа PDF сохранит текст/кандидатов по фразам, но поля не заполнятся. XML не использует LLM. После добавления ключа загрузите PDF повторно.

Для почты заполните MAIL_USER, MAIL_PASS, MAIL_FROM, MAIL_LAWYER; установите MAIL_ENABLED=true и оставьте MAIL_AUTO_SEND=false для первой проверки. SMTP Mail.ru: smtp.mail.ru/465/ssl. Gmail требует отдельного пароля приложения при доступности этой функции в аккаунте. SENT — сервер принял письмо, проверьте входящие/спам получателя.

## Старые результаты

При остановленном сервере сделайте копию storage и выполните:

```bash
python -m scripts.recheck_results
```

В Docker вместо локальной команды используйте одноразовый контейнер после остановки web:

```bash
docker compose stop web
docker compose run --rm --no-deps web python -m scripts.recheck_results
docker compose start web
```

Пересчёт не запускает OCR/LLM и не отправляет письма. Старые неудачные сканы загрузите заново.

## Использованные инструкции

- pdf2image/Poppler: https://pdf2image.readthedocs.io/en/latest/installation.html
- Windows Poppler: https://github.com/oschwartz10612/poppler-windows/releases
- CPU PyTorch: https://pytorch.org/get-started/locally/
- EasyOCR/веса: https://jaided.ai/easyocr/documentation/
- Docker Python: https://docs.docker.com/guides/python/
