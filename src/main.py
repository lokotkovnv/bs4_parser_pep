import logging
import re
from urllib.parse import urljoin
from collections import defaultdict
from typing import List

import requests_cache
from bs4 import BeautifulSoup
from tqdm import tqdm

from constants import BASE_DIR, MAIN_DOC_URL, PEPS_URL, EXPECTED_STATUS, LXML
from configs import configure_argument_parser, configure_logging
from outputs import control_output
from utils import get_response, find_tag


def whats_new(session: requests_cache.CachedSession) -> List:
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')
    response = get_response(session, whats_new_url)
    if response is None:
        # Если основная страница не загрузится, программа закончит работу.
        return
    soup = BeautifulSoup(response.text, features=LXML)
    main_div = find_tag(soup, 'section', attrs={'id': 'what-s-new-in-python'})
    div_with_ul = find_tag(main_div, 'div', attrs={'class': 'toctree-wrapper'})
    sections_by_python = div_with_ul.find_all(
        'li', attrs={'class': 'toctree-l1'}
    )
    results = [('Ссылка на статью', 'Заголовок', 'Редактор, Автор')]
    for section in tqdm(sections_by_python):
        version_a_tag = find_tag(section, 'a')
        version_link = urljoin(whats_new_url, version_a_tag['href'])
        response = get_response(session, version_link)
        if response is None:
            # Если страница не загрузится,
            # программа перейдёт к следующей ссылке.
            continue
        soup = BeautifulSoup(response.text, features=LXML)
        h1 = find_tag(soup, 'h1')
        dl = find_tag(soup, 'dl')
        dl_text = dl.text.replace('\n', ' ')
        results.append(
            (version_link, h1.text, dl_text)
        )

    return results


def latest_versions(session: requests_cache.CachedSession) -> List:
    response = get_response(session, MAIN_DOC_URL)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features=LXML)
    sidebar = find_tag(soup, 'div', {'class': 'sphinxsidebarwrapper'})
    ul_tags = sidebar.find_all('ul')
    for ul in ul_tags:
        if 'All versions' in ul.text:
            a_tags = ul.find_all('a')
            break
    else:
        raise Exception('Ничего не нашлось')
    results = [('Ссылка на документацию', 'Версия', 'Статус')]
    # Шаблон для поиска версии и статуса:
    pattern = r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)'
    for a_tag in a_tags:
        link = a_tag['href']
        text_match = re.search(pattern, a_tag.text)
        if text_match is not None:
            # Если строка соответствует паттерну,
            # переменным присываивается содержимое групп, начиная с первой.
            version, status = text_match.groups()
        else:
            # Если строка не соответствует паттерну,
            # первой переменной присваивается весь текст,
            # второй — пустая строка.
            version, status = a_tag.text, ''
        results.append(
            (link, version, status)
        )

    return results


def download(session: requests_cache.CachedSession) -> None:
    downloads_url = urljoin(MAIN_DOC_URL, 'download.html')
    response = get_response(session, downloads_url)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features=LXML)
    main_tag = find_tag(soup, 'div', {'role': 'main'})
    table_tag = find_tag(main_tag, 'table', {'class': 'docutils'})
    pdf_a4_tag = find_tag(
        table_tag, 'a', {'href': re.compile(r'.+pdf-a4\.zip$')}
    )
    pdf_a4_link = pdf_a4_tag['href']
    archive_url = urljoin(downloads_url, pdf_a4_link)
    print(archive_url)
    filename = archive_url.split('/')[-1]
    downloads_dir = BASE_DIR / 'downloads'
    downloads_dir.mkdir(exist_ok=True)
    archive_path = downloads_dir / filename
    response = session.get(archive_url)

    with open(archive_path, 'wb') as file:
        file.write(response.content)
    logging.info(f'Архив был загружен и сохранён: {archive_path}')


def pep(session: requests_cache.CachedSession) -> List:
    status_count = defaultdict(int)
    mismatched_statuses = []

    response = session.get(PEPS_URL)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, features=LXML)

    section = soup.find('section', {'id': 'numerical-index'})
    table = section.find('table')

    pep_links = []

    for row in table.find_all('tr')[1:]:
        cells = row.find_all('td')
        status_index = cells[0].text.strip()[1:]
        expected_statuses = EXPECTED_STATUS.get(status_index, [])

        if not expected_statuses:
            logging.warning(f"Неизвестный статус в таблице: {status_index}")

        pep_link = cells[1].find('a')['href']
        full_pep_link = urljoin(PEPS_URL, pep_link)
        pep_links.append((full_pep_link, expected_statuses))

    for pep_link, expected_statuses in tqdm(pep_links):
        response = session.get(pep_link)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, features=LXML)

        article = soup.find('article')
        field_list = article.find('dl')

        for dt, dd in zip(
            field_list.find_all('dt'), field_list.find_all('dd')
        ):
            if dt.text.strip() == 'Status:':
                pep_status = dd.text.strip()
                break
        status_count[pep_status] += 1

        if pep_status not in expected_statuses:
            mismatched_statuses.append(
                (pep_link, pep_status, expected_statuses)
            )

    if mismatched_statuses:
        logging.warning("Несовпадающие статусы:")
        for link, card_status, expected in mismatched_statuses:
            logging.warning(
                f"\n{link}\nСтатус в карточке: {card_status}\n"
                f"Ожидаемые статусы: {expected}"
            )

    results = [('Статус', 'Количество')]
    for status, count in status_count.items():
        results.append((status, count))
    results.append(('Total', sum(status_count.values())))

    return results


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep,
}


def main() -> None:
    configure_logging()
    logging.info('Парсер запущен!')

    arg_parser = configure_argument_parser(MODE_TO_FUNCTION.keys())
    args = arg_parser.parse_args()
    logging.info(f'Аргументы командной строки: {args}')

    session = requests_cache.CachedSession()
    # Если был передан ключ '--clear-cache', то args.clear_cache == True.
    if args.clear_cache:
        # Очистка кеша.
        session.cache.clear()

    parser_mode = args.mode
    results = MODE_TO_FUNCTION[parser_mode](session)

    if results is not None:
        control_output(results, args)
    logging.info('Парсер завершил работу.')


if __name__ == '__main__':
    main()
