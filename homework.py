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
                       WrongResponseCode, CurrentDateDoesNotExists)

load_dotenv()

PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TIME_FORMAT = "%d-%m-%Y %H:%M"

RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}


HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания."
}

logging.FileHandler(
    filename="program.log",
    mode="w",
)
logger = logging.getLogger(__name__)


def check_tokens():
    """Проверяем, что есть все токены.
    Если нет хотя бы одного, то останавливаем бота.
    """
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot: telegram.bot.Bot, message: str) -> None:
    """Отправляет сообщение в telegram."""
    try:
        logging.debug("Начало отправки статуса в telegram")
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.error.TelegramError as error:
        logging.error(f"Ошибка отправки статуса в telegram: {error}")
        logging.error(f"Ошибка отправки статуса в telegram: {error}")
    else:
        logging.info("Успешная отправка сообщения!")


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

    logger.info("Проверка ответа API на корректность")
    if not isinstance(response, dict):
        raise TypeError(
            f"при получении ответа от api {response} пришёл не словарь "
        )

    if not response.get("current_date"):
        raise CurrentDateDoesNotExists("В ответе нет текущей даты")

    homework_template = response.get("homeworks")
    if not isinstance(homework_template, list):
        raise TypeError(
            f"при получении ответа от api {response}"
            f"в словаре нет домашней работы или она не является листом "
        )

    if not homework_template:
        raise KeyError(f"в {response}  пустой JSON")

    if "homeworks" not in response or "current_date" not in response:
        raise EmptyDictionaryOrListError("Нет ключа homeworks в ответе API")
    print(homework_template)
    return homework_template


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


def main():
    """Главная функция запуска бота."""
    if not check_tokens():
        no_tokens_msg = (
            "Программа принудительно остановлена. "
            "Отсутствует какой-то из токенов."
        )
        logging.critical(f"{no_tokens_msg}")
        sys.exit("Отсутствует обязательная переменная окружения")

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    now = datetime.datetime.now()
    send_message(
        bot,
        f"Я начал свою работу: {now.strftime(TIME_FORMAT)}")
    current_timestamp = 1668370964
    tmp_status = None
    previous_error = None
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)[0]
            if homework:
                message = parse_status(homework)
                curent_status = homework["status"]
                if tmp_status != curent_status:
                    send_message(bot, message)
                    tmp_status = curent_status
                current_timestamp = response.get("current_date")
        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            unknown_error = f"Неизвестная ощибка: {error}"
            if error != previous_error:
                send_message(bot, message)
                error = previous_error
                logger.error(message, exc_info=True)
            else:
                send_message(bot, unknown_error)
                error = previous_error
                logger.error(unknown_error, exc_info=True)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
