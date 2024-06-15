import logging
import csv
import datetime as dt
from typing import List
from argparse import Namespace

from prettytable import PrettyTable
from constants import BASE_DIR, DATETIME_FORMAT, OutputType, UTF_8


def control_output(results: list, cli_args: Namespace) -> None:
    if cli_args.output is None:
        default_output(results)
    else:
        output_type = OutputType(cli_args.output)
        if output_type == OutputType.PRETTY:
            pretty_output(results)
        elif output_type == OutputType.FILE:
            file_output(results, cli_args)
        else:
            default_output(results)


def default_output(results: List) -> None:
    for row in results:
        print(*row)


def pretty_output(results: List) -> None:
    table = PrettyTable()
    table.field_names = results[0]
    table.align = 'l'
    table.add_rows(results[1:])
    print(table)


def file_output(results: List, cli_args: Namespace) -> None:
    results_dir = BASE_DIR / 'results'
    results_dir.mkdir(exist_ok=True)
    parser_mode = cli_args.mode
    now = dt.datetime.now()
    now_formatted = now.strftime(DATETIME_FORMAT)
    file_name = f'{parser_mode}_{now_formatted}.csv'
    file_path = results_dir / file_name
    with open(file_path, 'w', encoding=UTF_8) as f:
        writer = csv.writer(f, dialect='unix')
        writer.writerows(results)
    logging.info(f'Файл с результатами был сохранён: {file_path}')
