import datetime
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exeptions import (CurrentDateDoesNotExists, EmptyDictionaryOrListError,
                       NotTelegramError, UndocumentedStatusError,
                       WrongResponseCode)

load_dotenv()

PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TIME_FORMAT = "%d-%m-%Y %H:%M"

RETRY_PERIOD = 60 * 10
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}


HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания."
}

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def check_tokens():
    """
    Проверяем, что есть все токены.
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
    else:
        logging.info("Успешная отправка сообщения!")


def get_api_answer(current_timestamp: int) -> dict:
    """
    Отправляем запрос к API и получаем список домашних работ.
    Также проверяем, что эндпоинт отдает статус 200.
    """
    timestamp = current_timestamp or int(time.time())
    params_request = {
        "url": ENDPOINT,
        "headers": HEADERS,
        "params": {"from_date": timestamp},
    }
    message = (
        "Начало запроса к API. Запрос: {url}, {headers}, {params}."
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
        message = (
            "API не возвращает 200. Запрос: {url}, {headers}, {params}."
        ).format(**params_request)
        raise WrongResponseCode(message, error)


def check_response(response: dict):
    """Проверяем корректность JSON."""
    logger.info("Проверка ответа API на корректность")
    if not isinstance(response, dict):
        raise TypeError(
            f"при получении ответа от api {response} пришёл не словарь "
        )

    if not response.get("current_date"):
        raise CurrentDateDoesNotExists("В ответе нет текущей даты")

    homework_response = response.get("homeworks")
    if not isinstance(homework_response, list):
        raise TypeError(
            f"при получении ответа от api {response}"
            f"в словаре нет домашней работы или она не является листом "
        )

    if not homework_response:
        raise KeyError(f"в {response}  пустой JSON")

    if "homeworks" not in response or "current_date" not in response:
        raise EmptyDictionaryOrListError("Нет ключа homeworks в ответе API")
    return homework_response


def parse_status(homework):
    """Информации о конкретном статусе домашней работы."""
    homework_name = homework.get('homework_name')
    if 'status' not in homework:
        raise KeyError('Статус отсутствует в homeworks')
    if homework.get('status') not in HOMEWORK_VERDICTS:
        raise KeyError('В домашней работе нет соответствующего статуса')
    if 'homework_name' not in homework:
        raise KeyError('Имя работы не найдено в домашней работе.')
    verdict = homework.get('status')
    homework_name = homework.get('homework_name')
    message = HOMEWORK_VERDICTS[verdict]
    if not verdict:
        raise UndocumentedStatusError('Неожиданный статус домашней работы')
    return (
        f'Изменился статус проверки работы "'
        f'{homework_name}"'
        f' {verdict}'
        f' {message}'
    )


def main():
    """Главная функция запуска бота."""
    if not check_tokens():
        no_tokens_msg = (
            "Программа принудительно остановлена. "
            "Отсутствует какой-то из токенов."
        )
        logging.critical(no_tokens_msg)
        sys.exit("Отсутствует обязательная переменная окружения")

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    now = datetime.datetime.now()
    send_message(
        bot,
        f"Я начал свою работу: {now.strftime(TIME_FORMAT)}")
    timestamp = int(time.time())
    preview_api_response = None
    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date')
            api_answer = get_api_answer(timestamp)
            homeworks = check_response(api_answer)

            if homeworks:
                homework = homeworks[0]
                message = parse_status(homework)
                current_api_answer = homework
                if current_api_answer != preview_api_response:
                    send_message(bot, message)
                    preview_api_response = current_api_answer
                logging.info(
                    'Новое домашнее задание не появилось или не изменилось'
                )
            else:
                logger.debug('Новых статусов нет')
        except NotTelegramError as error:
            logging.error(
                f'Что то сломалось при отправке,{error}',
                exc_info=True
            )
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logging.error(message, exc_info=error)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
