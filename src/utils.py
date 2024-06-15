import logging
import requests_cache
from requests import RequestException
from typing import Optional
from bs4 import BeautifulSoup

from exceptions import ParserFindTagException
from constants import UTF_8


# Перехват ошибки RequestException.
def get_response(
        session: requests_cache.CachedSession, url: str
) -> Optional[requests_cache.CachedResponse]:
    try:
        response = session.get(url)
        response.encoding = UTF_8
        return response
    except RequestException:
        logging.exception(
            f'Возникла ошибка при загрузке страницы {url}',
            stack_info=True
        )


# Перехват ошибки поиска тегов.
def find_tag(
        soup: BeautifulSoup, tag: str, attrs: Optional[dict] = None
) -> BeautifulSoup:
    searched_tag = soup.find(tag, attrs=(attrs or {}))
    if searched_tag is None:
        error_msg = f'Не найден тег {tag} {attrs}'
        logging.error(error_msg, stack_info=True)
        raise ParserFindTagException(error_msg)
    return searched_tag
