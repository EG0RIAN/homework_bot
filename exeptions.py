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


class JsonDoesNotExists(Exception):
    """Ответ не получен или получен пустым."""
