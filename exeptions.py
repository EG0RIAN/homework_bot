class EmptyDictionaryOrListError(Exception):
    """Пустой словарь или список."""


class UndocumentedStatusError(Exception):
    """Недокументированный статус."""


class WrongResponseCode(Exception):
    """Неверный ответ API."""


class EmptyResponseFromAPI(Exception):
    """Пустой ответ API."""


class TelegramError(Exception):
    """Ошибка отправки сообщения в telegram."""


class CurrentDateDoesNotExists(Exception):
    """В ответе нет текущей даты"""
