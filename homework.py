import datetime
import json
import logging
import os
import time

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': '✅ Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': '🔎 Работа взята на проверку ревьюером.',
    'rejected': '⚠️ Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    filemode='w',
    format='%(asctime)s - %(levelname)s - %(message)s - %(name)s'
)
logger = logging.getLogger(__name__)
logger.addHandler(
    logging.StreamHandler()
)


class TheAnswerIsNot200Error(Exception):
    """Ответ сервера не равен 200."""


class EmptyDictionaryOrListError(Exception):
    """Пустой словарь или список."""


class UndocumentedStatusError(Exception):
    """Недокументированный статус."""


class RequestExceptionError(Exception):
    """Ошибка запроса."""


def check_tokens():
    """Проверяем, что есть все токены.
    Если нет хотя бы одного, то останавливаем бота.
    """
    no_tokens_msg = (
        'Программа принудительно остановлена. '
        'Отсутствует какой-то из токенов.')
    logging.info(f'{no_tokens_msg}')
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправка сообщения в Телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(
            f'Сообщение в Telegram отправлено: {message}')
    except telegram.TelegramError as telegram_error:
        logger.error(
            f'Сообщение в Telegram не отправлено: {telegram_error}')


def get_api_answer(url, current_timestamp):
    """Получение данных с API YP."""
    current_timestamp = current_timestamp or int(time.time())
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    payload = {'from_date': current_timestamp}
    try:
        response = requests.get(url, headers=headers, params=payload)
        if response.status_code != 200:
            code_api_msg = (
                f'Эндпоинт {url} недоступен.'
                f' Код ответа API: {response.status_code}')
            logger.error(code_api_msg)
            raise TheAnswerIsNot200Error(code_api_msg)
        return response.json()
    except requests.exceptions.RequestException as request_error:
        code_api_msg = f'Код ответа API (RequestException): {request_error}'
        logger.error(code_api_msg)
        raise RequestExceptionError(code_api_msg) from request_error
    except json.JSONDecodeError as value_error:
        code_api_msg = f'Код ответа API (ValueError): {value_error}'
        logger.error(code_api_msg)
        raise json.JSONDecodeError(code_api_msg) from value_error


def check_response(response):
    """Проверяем данные в response."""
    if response.get('homeworks') is None:
        code_api_msg = (
            'Ошибка ключа homeworks или response'
            'имеет неправильное значение.')
        logger.error(code_api_msg)
        raise EmptyDictionaryOrListError(code_api_msg)
    if response['homeworks'] == []:
        return {}
    status = response['homeworks'][0].get('status')
    if status not in HOMEWORK_VERDICTS:
        code_api_msg = f'Ошибка не задокументированный статус: {status}'
        logger.error(code_api_msg)
        raise UndocumentedStatusError(code_api_msg)
    return response['homeworks'][0]


def parse_status(homework):
    """Анализ статуса если изменился."""
    status = homework.get('status')
    homework_name = homework.get('homework_name')
    if status is None:
        extracted_from_parse_status(
            'Ошибка пустое значение status: ', status)
    if homework_name is None:
        extracted_from_parse_status(
            'Ошибка пустое значение homework_name: ', homework_name)
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def extracted_from_parse_status(arg0, arg1):
    """Вывод ошибок парсера."""
    code_api_msg = f'{arg0}{arg1}'
    logger.error(code_api_msg)
    raise UndocumentedStatusError(code_api_msg)


def main():
    """Главная функция запуска бота."""
    if not check_tokens():
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    now = datetime.datetime.now()
    send_message(
        bot,
        f'Я начал свою работу: {now.strftime("%d-%m-%Y %H:%M")}')
    current_timestamp = int(time.time())
    tmp_status = 'reviewing'
    errors = True
    while True:
        try:
            response = get_api_answer(ENDPOINT, current_timestamp)
            homework = check_response(response)
            if homework and tmp_status != homework['status']:
                message = parse_status(homework)
                send_message(bot, message)
                tmp_status = homework['status']
            logger.info(
                'Изменений нет, через 10 минут проверим API')
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if errors:
                errors = False
                send_message(bot, message)
            logger.critical(message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
