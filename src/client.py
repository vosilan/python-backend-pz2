"""Клиент к HTTP API

Имена методов повторяют маршруты из табл. 19, где «/» заменён на «_»:
/core/api/v2/save/profile превратился в core_api_v2_save_profile
"""

import urllib.error
import urllib.request
from http import HTTPStatus

import xmlio

PREFIX = "/core/api/v2"
XML_HEADERS = {"Content-Type": "text/xml", "Accept": "text/xml"}


class ApiError(Exception):
    """Сервер ответил ошибкой: код не 200 или тело <error>"""


class ApiClient:
    """Клиент к серверу по адресу вида http://127.0.0.1:5019"""

    def __init__(self, url):
        """Запомнить адрес сервера"""
        self.url = url

    def send(self, method, path, body=None, headers=None):
        """Отправить запрос и вернуть (код ответа, тело ответа)"""
        request = urllib.request.Request(
            self.url + path, data=body, method=method,
            headers=XML_HEADERS if headers is None else headers,
        )
        try:
            with urllib.request.urlopen(request) as answer:
                return answer.status, answer.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def _call(self, method, path, body=b""):
        """Запрос к API, при ошибке выбрасывается ApiError"""
        status, answer = self.send(method, PREFIX + path, body)
        if status != HTTPStatus.OK or answer.startswith(b"<error>"):
            raise ApiError(f"{status}: {answer.decode('utf-8')}")
        return answer

    def core_api_v2_save_profile(self, platform, user_agent, timestamp=None):
        """1.1 Создать Profile"""
        body = xmlio.dump("profile", {
            "platform": platform, "user_agent": user_agent,
            "timestamp": timestamp,
        })
        return xmlio.load(self._call("POST", "/save/profile", body))

    def core_api_v2_fetch_profile(self, **filters):
        """1.2 Поиск Profile по значениям полей"""
        body = xmlio.dump("profile", filters)
        return xmlio.load_list(self._call("POST", "/fetch/profile", body))

    def core_api_v2_inspect_profile(self, key):
        """1.3 Profile по ключу"""
        answer = self._call("GET", f"/inspect/profile?key={key}", None)
        return xmlio.load(answer)

    def core_api_v2_save_instruction(self, parameter, profile, timestamp=None):
        """2.1 Создать Instruction, сервер сразу выполняет сжатие"""
        body = xmlio.dump("instruction", {
            "parameter": parameter, "profile": profile,
            "timestamp": timestamp,
        })
        return xmlio.load(self._call("POST", "/save/instruction", body))

    def core_api_v2_fetch_instruction(self, profile, **filters):
        """2.2 Поиск Instruction одного Profile"""
        body = xmlio.dump("instruction", filters)
        answer = self._call("POST", f"/fetch/instruction/{profile}", body)
        return xmlio.load_list(answer)

    def core_api_v2_inspect_instruction(self, key):
        """2.3 Instruction по ключу"""
        answer = self._call("GET", f"/inspect/instruction?key={key}", None)
        return xmlio.load(answer)

    def core_api_v2_fetch_reply(self, instruction, **filters):
        """3.1 Поиск Reply одной Instruction"""
        body = xmlio.dump("reply", filters)
        answer = self._call("POST", f"/fetch/reply/{instruction}", body)
        return xmlio.load_list(answer)

    def core_api_v2_inspect_reply(self, key):
        """3.2 Reply по ключу"""
        answer = self._call("GET", f"/inspect/reply?key={key}", None)
        return xmlio.load(answer)

    def core_api_v2_fetch_report(self):
        """4.1 Отчёт по формуле (19)"""
        return xmlio.load_list(self._call("POST", "/fetch/report"))
