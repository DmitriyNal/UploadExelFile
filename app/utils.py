import logging
import os
import time
from io import StringIO
from tqdm import tqdm
import pandas as pd
from g4f.client import Client
import concurrent.futures

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

processing_flags = {}


def get_gpt_feedback(comment, prompt, block=3):
    attempts = 10
    for attempt in range(attempts):
        try:
            client = Client()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": comment + f'\n\n{prompt}'}],
            )
            if block == -1:
                logger.info("Получен успешный ответ.")
                print(str(response.choices[0].message.content), end='*')
                return str(response.choices[0].message.content)

            elif block >= len(response.choices[0].message.content) > 1:
                logger.info("Ответ получен и обработан.")
                print(str(response.choices[0].message.content).lower(), end='*')
                return str(response.choices[0].message.content).lower()

        except Exception as e:
            logger.error(f"Попытка {attempt + 1} не удалась: {e}")
            time.sleep(2)


def try_table(df, prompt):
    attempts = 10
    for attempt in range(attempts):
        try:
            logger.info("Попытка создать таблицу из DataFrame.")
            res = get_gpt_feedback(str(df), prompt, -1)
            df_table = pd.read_html(StringIO(res))[0]
            if isinstance(df_table, pd.DataFrame):
                logging.info("Таблица успешно создана.")
                return df_table
        except Exception as e:
            logger.error(f"Попытка {attempt + 1} создать таблицу не удалась: {e}")
            time.sleep(2)


def process_row(row, prompt):
    logger.info(f"Обработка строки: {row}")
    return get_gpt_feedback(str(row), prompt)


def process_file(file_path, prompt, master_prompt, processed_file_path):
    logger.info(f"Начало обработки файла: {file_path}")
    df = pd.read_excel(file_path, index_col=0)
    df_full = df.copy()

    # Логирование начала обработки
    logger.info('Обработка файла начата.')

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(process_row, row, prompt) for _, row in df_full.iterrows()]
        results = []
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
            results.append(future.result())

    df_full['ai'] = results

    # Логирование завершения обработки
    logger.info('Обработка файла завершена.')

    df_table = try_table(df, master_prompt)

    # Проверка наличия данных
    if df_table.empty:
        logging.warning('DataFrame пуст. Файл Excel не будет создан.')
    else:
        # Сохранение таблицы в Excel
        filename = f"{os.path.splitext(file_path)[0]}_results.xlsx"
        df_table.to_excel(filename, index=False)
        logger.info(f'Файл Excel сохранен: {filename}')

    # Обновление статуса после завершения обработки
    processing_flags[file_path] = "Файл готов -Можно скачать "
    logger.info(f"Статус обработки обновлен для файла: {file_path}")