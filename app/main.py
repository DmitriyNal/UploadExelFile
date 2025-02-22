import logging
import os
import warnings
from urllib.parse import quote, unquote

from fastapi import FastAPI, UploadFile, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from app.utils import processing_flags, process_file

# warnings.filterwarnings('ignore', category=RuntimeWarning)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
app = FastAPI(swagger_ui_parameters={"tryItOutEnabled": True}, debug=True)
templates = Jinja2Templates(directory="templates")

logging.info("Пуск")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    logger.info("Главная страница")
    return templates.TemplateResponse("upload.html", {"request": request})


@app.get("/check-status/{file_name}", response_class=HTMLResponse)
async def check_status(file_name: str, request: Request):
    file_path = os.path.join("uploads", file_name)
    status = processing_flags.get(file_path, "not_started")
    logger.info(f"Проверка статуса файла {file_name}: {status}")

    # Формируем URL для обновления статуса
    check_url = f"/check-status/{file_name}"

    return templates.TemplateResponse("status.html", {
        "request": request,
        "status": status,
        "check_url": check_url
    })


@app.post("/upload-file/")
async def upload_file(request: Request, file: UploadFile, background_tasks: BackgroundTasks):
    logger.info('Загрузка файла')
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    # file_path = os.path.join(upload_dir, file.filename)
    # Стандартизируем имя файла
    base_filename = os.path.splitext(file.filename)[0]
    file_path = os.path.join(upload_dir, file.filename)
    processed_file_path = os.path.join(upload_dir, f"{base_filename}_results.xlsx")

    # Save the uploaded file
    with open(file_path, "wb") as f:
        f.write(await file.read())
    logger.info(f"Файл {file.filename} загружен")

    prompt = ("Ты система оценки обратной связи, измерь оценки и отзыв человека, "
              "если всё нормально или хорошо ответь ok, если нет bad. *Только эти два слова*")

    master_prompt = '''Ты система оценки обратной связи.
    Твоя задача — анализировать отзывы и кластеризовать проблемы/отзывы.
    Выдели часто встречающиеся положительные и отрицательные.
    Для каждого кластера укажи процент встречаемости и количество случаев.
    Ответ в виде *html* таблицы на русском языке. Будь объективен и точно считай случаи.
    Структура таблицы: Проблема/Отзыв, Тип (Отрицательный, Положительный), Количество случаев, Процент встречаемости
    '''

    # Add the background task for processing the file
    background_tasks.add_task(process_file, file_path, prompt, master_prompt, processed_file_path)

    # Кодируем имя файла для URL
    encoded_filename = quote(f"{base_filename}_results.xlsx")

    return templates.TemplateResponse("result.html", {
        "request": request,
        "message": "Файл обрабатывается в фоновом режиме. Пожалуйста, проверьте статус позже.",
        "check_url": f"/check-status/{quote(file.filename)}",
        "download_url": f"/download/{encoded_filename}"
    })


@app.get("/download/{filename}")
async def download_result(filename: str):
    # Декодируем имя файла из URL
    decoded_filename = unquote(filename)
    file_path = os.path.join("uploads", decoded_filename)
    if os.path.exists(file_path):
        logger.info(f"Скачан результат обработки файла {filename}")
        return FileResponse(path=file_path,
                            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            filename=decoded_filename)
    else:
        logger.error(f"Файл {filename} не найден")
        raise HTTPException(status_code=404, detail="File not found")
