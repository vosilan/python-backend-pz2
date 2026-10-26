"""HTTP API на Flask: обработчики из табл. 19 варианта

Тело запросов и ответов в XML. Данные хранятся в SQLite (db.py).
Задача сжатия выполняется утилитой xzpack.py в отдельном процессе,
в тестовом режиме (XZ_FAKE=1) процесс не запускается
"""

import os
import subprocess
import sys
import uuid
from pathlib import Path
from xml.etree.ElementTree import ParseError

from flask import Flask, Response, request

import db as store
import xmlio

PREFIX = "/core/api/v2"
XML = "text/xml"
BODY_METHODS = ("POST", "PUT", "PATCH")
XZPACK = Path(__file__).with_name("xzpack.py")
RESULTS = "results"
PORT = 5019

app = Flask(__name__)


def xml_response(body, status=200):
    """Ответ с телом XML"""
    return Response(body, status=status, mimetype=XML)


def xml_error(status, message):
    """Ответ с ошибкой: <error>текст</error>"""
    return xml_response(xmlio.dump("error", {"message": message}), status)


@app.before_request
def check_headers():
    """Проверить обязательные заголовки до вызова обработчика.

    Если заголовка нет, вернуть код, указанный напротив первого
    отсутствующего: сначала Content-Type (415), потом Accept (406).
    None значит, что всё в порядке и запрос идёт дальше
    """
    if request.method in BODY_METHODS and request.mimetype != XML:
        return xml_error(415, "Не хватает Content-Type")
    if XML not in request.accept_mimetypes.values():
        return xml_error(406, "Не хватает Accept")
    return None


@app.errorhandler(store.ModelError)
@app.errorhandler(KeyError)
@app.errorhandler(ValueError)
@app.errorhandler(ParseError)
def request_error(error):
    """Нет записи, нет поля, не число или кривой XML.

    По заданию код всегда 200, ошибка передаётся в теле <error>
    """
    return xml_error(200, f"{type(error).__name__}: {error}")


def compress(parameter):
    """Сжать строку утилитой xzpack.py, вернуть (stage, response, failure)"""
    filename = f'{RESULTS}/{uuid.uuid4().hex}.xz'
    result = subprocess.run([sys.executable, XZPACK, filename],
                            input=parameter.encode('utf-8'),
                            capture_output=True)
    if result.returncode:
        return "failed", "", result.stderr.decode('utf-8')
    return "done", filename, ""


def fake_compress(parameter):
    """Тестовый режим: результат без запуска утилиты"""
    return "done", "fake.xz", ""


app.config["COMPRESS"] = (
    fake_compress if os.environ.get("XZ_FAKE") else compress
)


def one(tag, record):
    """Ответ с одной записью"""
    return xml_response(xmlio.dump(tag, record))


def many(tag, records):
    """Ответ со списком записей"""
    return xml_response(xmlio.dump_list(tag, records, tag + "s"))


def key_from_query():
    """Ключ из строки запроса ?key=N"""
    return int(request.args["key"])


@app.post(PREFIX + "/save/profile")
def save_profile():
    """1.1 Создать Profile"""
    data = xmlio.load(request.get_data())
    return one("profile", store.create_profile(
        data["platform"], data["user_agent"], data.get("timestamp")
    ))


@app.post(PREFIX + "/fetch/profile")
def fetch_profile():
    """1.2 Поиск Profile по полям из тела"""
    filters = xmlio.load(request.get_data())
    return many("profile", store.find_profiles(filters))


@app.get(PREFIX + "/inspect/profile")
def inspect_profile():
    """1.3 Profile по ключу"""
    return one("profile", store.get_profile(key_from_query()))


@app.post(PREFIX + "/save/instruction")
def save_instruction():
    """2.1 Создать Instruction, выполнить сжатие и записать Reply"""
    data = xmlio.load(request.get_data())
    store.get_profile(data["profile"])
    stage, response, failure = app.config["COMPRESS"](data["parameter"])
    instruction = store.create_instruction(
        data["parameter"], data["profile"], stage, data.get("timestamp")
    )
    store.create_reply(
        response, stage, failure, instruction["key"], 0,
        instruction["timestamp"],
    )
    return one("instruction", instruction)


@app.post(PREFIX + "/fetch/instruction/<int:profile>")
def fetch_instruction(profile):
    """2.2 Поиск Instruction одного Profile"""
    filters = xmlio.load(request.get_data())
    return many("instruction", store.find_instructions(profile, filters))


@app.get(PREFIX + "/inspect/instruction")
def inspect_instruction():
    """2.3 Instruction по ключу"""
    return one("instruction", store.get_instruction(key_from_query()))


@app.post(PREFIX + "/fetch/reply/<int:instruction>")
def fetch_reply(instruction):
    """3.1 Поиск Reply одной Instruction"""
    filters = xmlio.load(request.get_data())
    return many("reply", store.find_replies(instruction, filters))


@app.get(PREFIX + "/inspect/reply")
def inspect_reply():
    """3.2 Reply по ключу"""
    return one("reply", store.get_reply(key_from_query()))


@app.post(PREFIX + "/fetch/report")
def fetch_report():
    """4.1 Отчёт по формуле (19)"""
    rows = store.select_recent_replies()
    return xml_response(xmlio.dump_list("row", rows, "report"))


def main():
    """Подключить базу и запустить сервер"""
    store.connect("sqlite:///data.sqlite")
    app.run(port=PORT)


if __name__ == "__main__":
    main()
