"""Тестирование HTTP API на основе модели

Сервер работает в фоновом потоке в тестовом режиме (без запуска
утилиты сжатия). ApiMachine выполняет одни и те же действия над
сервером через клиента и над упрощённой моделью на списках словарей,
затем сравнивает результаты
"""

import threading

import pytest
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    Bundle, RuleBasedStateMachine, invariant, rule,
)
from werkzeug.serving import make_server

import app as web
from client import PREFIX, ApiClient, ApiError

web.app.config["COMPRESS"] = web.fake_compress
SERVER = make_server("127.0.0.1", 0, web.app)
threading.Thread(target=SERVER.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{SERVER.server_port}"

RECENT_AGE = 60
OLD_AGE = 60 * 60
MISSING_KEY = 10 ** 6
OK = 200
NOT_ACCEPTABLE = 406
UNSUPPORTED = 415

texts = st.text(
    st.characters(codec="utf-8", categories=("L", "N", "P", "Zs")),
    max_size=8,
)
ages = st.sampled_from([None, RECENT_AGE, OLD_AGE])
post_paths = st.sampled_from([
    "/save/profile", "/fetch/profile", "/save/instruction",
    "/fetch/instruction/1", "/fetch/reply/1", "/fetch/report",
])
get_paths = st.sampled_from([
    "/inspect/profile", "/inspect/instruction", "/inspect/reply",
])


def stamp(age):
    """Метка времени age секунд назад, None значит время сервера"""
    return None if age is None else web.store.now() - age


def matching(rows, filters):
    """Строки модели, у которых поля совпадают с filters"""
    return [
        row for row in rows
        if all(row[name] == value for name, value in filters.items())
    ]


class ApiMachine(RuleBasedStateMachine):
    """HTTP API против упрощённой модели на списках словарей"""

    profiles = Bundle("profiles")
    instructions = Bundle("instructions")

    def __init__(self):
        """Очистить данные сервера и завести пустую модель"""
        super().__init__()
        web.store.reset()
        self.client = ApiClient(URL)
        self.expected = {"profile": [], "instruction": [], "reply": []}

    def remember(self, table, result, fields):
        """Сверить созданную сервером запись и добавить её в модель"""
        rows = self.expected[table]
        row = {"key": len(rows) + 1, **fields}
        if row["timestamp"] is None:
            row["timestamp"] = result["timestamp"]
        assert result == row
        rows.append(row)
        return row

    @rule(target=profiles, platform=texts, user_agent=texts, age=ages)
    def save_profile(self, platform, user_agent, age):
        """1.1 Создать Profile"""
        fields = {
            "timestamp": stamp(age), "platform": platform,
            "user_agent": user_agent,
        }
        result = self.client.core_api_v2_save_profile(**fields)
        return self.remember("profile", result, fields)["key"]

    @rule(target=instructions, profile=profiles, parameter=texts, age=ages)
    def save_instruction(self, profile, parameter, age):
        """2.1 Создать Instruction, в модель попадает и её Reply"""
        fields = {
            "timestamp": stamp(age), "parameter": parameter,
            "profile": profile, "stage": "done",
        }
        result = self.client.core_api_v2_save_instruction(
            parameter, profile, fields["timestamp"]
        )
        row = self.remember("instruction", result, fields)
        self.expected["reply"].append({
            "key": len(self.expected["reply"]) + 1,
            "timestamp": row["timestamp"], "response": "fake.xz",
            "stage": "done", "failure": "", "instruction": row["key"],
            "cache_hit": 0,
        })
        return row["key"]

    @rule(parameter=texts)
    def save_instruction_without_profile(self, parameter):
        """Ссылка на несуществующий Profile даёт ошибку"""
        with pytest.raises(ApiError):
            self.client.core_api_v2_save_instruction(parameter, MISSING_KEY)

    @rule(
        profile=profiles,
        names=st.sets(st.sampled_from(["platform", "user_agent"])),
    )
    def fetch_profile(self, profile, names):
        """1.2 Поиск Profile по полям существующей записи"""
        row = self.expected["profile"][profile - 1]
        filters = {name: row[name] for name in names}
        expected = matching(self.expected["profile"], filters)
        assert self.client.core_api_v2_fetch_profile(**filters) == expected

    @rule(
        profile=profiles, instruction=instructions,
        names=st.sets(st.sampled_from(["parameter", "stage"])),
    )
    def fetch_instruction(self, profile, instruction, names):
        """2.2 Поиск Instruction одного Profile по полям другой записи"""
        row = self.expected["instruction"][instruction - 1]
        filters = {name: row[name] for name in names}
        expected = matching(
            self.expected["instruction"], {**filters, "profile": profile}
        )
        result = self.client.core_api_v2_fetch_instruction(profile, **filters)
        assert result == expected

    @rule(instruction=instructions)
    def fetch_reply(self, instruction):
        """3.1 Поиск Reply одной Instruction"""
        expected = matching(
            self.expected["reply"], {"instruction": instruction}
        )
        result = self.client.core_api_v2_fetch_reply(instruction)
        assert result == expected

    @rule(profile=profiles)
    def inspect_profile(self, profile):
        """1.3 Profile по ключу совпадает с моделью"""
        expected = self.expected["profile"][profile - 1]
        assert self.client.core_api_v2_inspect_profile(profile) == expected

    @rule(instruction=instructions)
    def inspect_instruction_and_reply(self, instruction):
        """2.3 и 3.2 Instruction и Reply по ключу совпадают с моделью"""
        expected = self.expected["instruction"][instruction - 1]
        result = self.client.core_api_v2_inspect_instruction(instruction)
        assert result == expected
        expected = self.expected["reply"][instruction - 1]
        assert self.client.core_api_v2_inspect_reply(instruction) == expected

    @rule(path=get_paths, query=st.sampled_from(["?key=0", "?key=x", ""]))
    def inspect_missing(self, path, query):
        """Нет записи, ключ не число или нет ключа: 200 и <error>"""
        status, body = self.client.send("GET", PREFIX + path + query)
        assert status == OK and body.startswith(b"<error>")

    @rule(path=post_paths)
    def bad_xml(self, path):
        """Некорректный XML: 200 и <error>, отчёт тело не читает"""
        status, body = self.client.send("POST", PREFIX + path, b"<profile")
        assert status == OK
        assert body.startswith(b"<error>") or path == "/fetch/report"

    @rule(path=post_paths, accept=st.booleans())
    def without_content_type(self, path, accept):
        """Нет Content-Type: 415, даже если нет и Accept"""
        headers = {"Accept": "text/xml"} if accept else {}
        status, _ = self.client.send("POST", PREFIX + path, b"", headers)
        assert status == UNSUPPORTED

    @rule(post=post_paths, get=get_paths)
    def without_accept(self, post, get):
        """Content-Type есть, Accept нет: 406"""
        headers = {"Content-Type": "text/xml"}
        status, _ = self.client.send("POST", PREFIX + post, b"", headers)
        assert status == NOT_ACCEPTABLE
        status, _ = self.client.send("GET", PREFIX + get + "?key=1", None, {})
        assert status == NOT_ACCEPTABLE

    @rule()
    def fetch_report(self):
        """4.1 Отчёт совпадает с выборкой по модели"""
        border = web.store.now() - web.store.RECENT_SECONDS
        parameters = {
            row["key"]: row["parameter"]
            for row in self.expected["instruction"]
        }
        expected = [
            {
                "parameter": parameters[row["instruction"]],
                "cache_hit": row["cache_hit"],
            }
            for row in self.expected["reply"]
            if row["timestamp"] > border
        ]
        assert self.client.core_api_v2_fetch_report() == expected

    @invariant()
    def profiles_match(self):
        """После каждого шага все Profile сервера совпадают с моделью"""
        result = self.client.core_api_v2_fetch_profile()
        assert result == self.expected["profile"]


TestApi = ApiMachine.TestCase
TestApi.settings = settings(
    max_examples=30, stateful_step_count=40, deadline=None,
    derandomize=True,
)
