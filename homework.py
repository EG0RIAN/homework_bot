import datetime
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from exeptions import (EmptyDictionaryOrListError,
                       UndocumentedStatusError,
                       WrongResponseCode, TelegramError,
                       JsonDoesNotExists)
load_dotenv()

PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename="program.log",
    filemode="w",
    format="%(asctime)s - %(levelname)s - %(message)s - %(name)s"
)
logger = logging.getLogger(__name__)
logger.addHandler(
    logging.StreamHandler()
)


def check_tokens():
    """Проверяем, что есть все токены.
    Если нет хотя бы одного, то останавливаем бота.
    """
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True
    no_tokens_msg = (
        "Программа принудительно остановлена. "
        "Отсутствует какой-то из токенов.")
    logging.critical(f"{no_tokens_msg}")
    return False


def send_message(bot: telegram.bot.Bot, message: str) -> None:
    """Отправляет сообщение в telegram."""
    try:
        logging.debug("Начало отправки статуса в telegram")
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.error.TelegramError as error:
        logging.error(f"Ошибка отправки статуса в telegram: {error}")
        raise TelegramError(f"Ошибка отправки статуса в telegram: {error}")


def get_api_answer(current_timestamp: int) -> dict:
    """Отправляем запрос к API и получаем список домашних работ.
    Также проверяем, что эндпоинт отдает статус 200.
    """
    timestamp = current_timestamp or int(time.time())
    params_request = {
        "url": ENDPOINT,
        "headers": HEADERS,
        "params": {"from_date": timestamp},
    }
    message = ("Начало запроса к API. Запрос: {url}, {headers}, {params}."
               ).format(**params_request)
    logging.info(message)
    try:
        response = requests.get(**params_request)
        if response.status_code != HTTPStatus.OK:
            raise WrongResponseCode(
                f"Ответ API не возвращает 200. "
                f"Код ответа: {response.status_code}. "
                f"Причина: {response.reason}. "
                f"Текст: {response.text}."
            )
        return response.json()
    except Exception as error:
        message = ("API не возвращает 200. Запрос: {url}, {headers}, {params}."
                   ).format(**params_request)
        raise WrongResponseCode(message, error)


def check_response(response: dict):
    """Проверяет ответ API на корректность.
    В качестве параметра функция получает ответ API.
    """
    if not response:
        raise JsonDoesNotExists(
            f'Функция {check_response.__repr__()} не получила JSON'
        )

    logging.info("Проверка ответа API на корректность")
    if not isinstance(response, dict):
        raise TypeError(
            f"при получении ответа от api {response} пришёл не словарь "
        )

    if not isinstance(response.get("homeworks"), list):
        raise TypeError(
            f"при получении ответа от api {response}"
            f"в словаре нет домашней работы или она не является листом "
        )

    if not response.get('homeworks'):
        raise KeyError(f'в {response}  пустой JSON')

    if "homeworks" not in response or "current_date" not in response:
        raise EmptyDictionaryOrListError("Нет ключа homeworks в ответе API")
    return response.get("homeworks")


def parse_status(homework: dict):
    """Извлекает из информации о конкретной домашней работе статус этой работы.
    В случае успеха, функция возвращает подготовленную для отправки
    в Telegram строку.
    """
    logging.info("Проводим проверки и извлекаем статус работы")
    if "homework_name" not in homework:
        raise KeyError("Нет ключа homework_name в ответе API")
    homework_name = homework.get("homework_name")
    homework_status = homework.get("status")
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f"Неизвестный статус работы - {homework_status}")
    return ("Изменился статус проверки работы \"{homework_name}\". {verdict}"
            ).format(homework_name=homework_name,
                     verdict=HOMEWORK_VERDICTS[homework_status]
                     )


def extracted_from_parse_status(arg0, arg1):
    """Вывод ошибок парсера."""
    code_api_msg = f"{arg0}{arg1}"
    logger.error(code_api_msg)
    raise UndocumentedStatusError(code_api_msg)


def main():
    """Главная функция запуска бота."""
    if not check_tokens():
        sys.exit("Отсутствует обязательная переменная окружения")
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    now = datetime.datetime.now()
    send_message(
        bot,
        f"Я начал свою работу: {now.strftime('%d-%m-%Y %H:%M')}")
    current_timestamp = int(time.time())
    tmp_status = None
    errors = True
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)[0]
            if homework:
                message = parse_status(homework)
                if tmp_status != homework["status"]:
                    send_message(bot, message)
                    tmp_status = homework["status"]
                logger.info(
                    "Изменений нет, через 10 минут проверим API")
        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            if errors:
                errors = False
                send_message(bot, message)
            logger.error(message, exc_info=True)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
