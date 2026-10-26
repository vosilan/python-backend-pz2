"""Модель слоя доступа к данным в памяти: Profile, Instruction, Reply

Перенесена из ПЗ1 и дополнена поиском. Записи хранятся в списках
словарей. Ключ новой записи равен длине таблицы плюс один: удаления нет,
поэтому ключи не повторяются
"""

import time

RECENT_SECONDS = 8 * 60


class ModelError(Exception):
    """Запись не найдена"""


profiles = []
instructions = []
replies = []


def reset():
    """Очистить все таблицы"""
    profiles.clear()
    instructions.clear()
    replies.clear()


def now():
    """Текущее время в секундах от начала эпохи Unix"""
    return int(time.time())


def _stamp(timestamp):
    """Взять переданную метку времени или текущее время"""
    return now() if timestamp is None else timestamp


def _get(table, key, name):
    """Найти запись по ключу или выбросить ModelError"""
    for record in table:
        if record["key"] == key:
            return dict(record)
    raise ModelError(f"{name} с key={key} не найден")


def _find(table, filters):
    """Записи, у которых все поля из filters равны заданным значениям"""
    return [
        dict(record) for record in table
        if all(record[name] == value for name, value in filters.items())
    ]


def _insert(table, record):
    """Выдать записи ключ, добавить её в таблицу и вернуть копию"""
    record = {"key": len(table) + 1, **record}
    table.append(record)
    return dict(record)


def create_profile(platform, user_agent, timestamp=None):
    """Создать запись Profile"""
    return _insert(profiles, {
        "timestamp": _stamp(timestamp), "platform": platform,
        "user_agent": user_agent,
    })


def get_profile(key):
    """Запись Profile по ключу"""
    return _get(profiles, key, "Profile")


def find_profiles(filters):
    """Поиск Profile по значениям полей"""
    return _find(profiles, filters)


def create_instruction(parameter, profile, stage, timestamp=None):
    """Создать запись Instruction для существующего Profile"""
    get_profile(profile)
    return _insert(instructions, {
        "timestamp": _stamp(timestamp), "parameter": parameter,
        "profile": profile, "stage": stage,
    })


def get_instruction(key):
    """Запись Instruction по ключу"""
    return _get(instructions, key, "Instruction")


def find_instructions(profile, filters):
    """Поиск Instruction одного Profile по значениям полей"""
    return _find(instructions, {**filters, "profile": profile})


def create_reply(
    response, stage, failure, instruction, cache_hit, timestamp=None
):
    """Создать запись Reply для существующей Instruction"""
    get_instruction(instruction)
    return _insert(replies, {
        "timestamp": _stamp(timestamp), "response": response,
        "stage": stage, "failure": failure, "instruction": instruction,
        "cache_hit": cache_hit,
    })


def get_reply(key):
    """Запись Reply по ключу"""
    return _get(replies, key, "Reply")


def find_replies(instruction, filters):
    """Поиск Reply одной Instruction по значениям полей"""
    return _find(replies, {**filters, "instruction": instruction})


def select_recent_replies():
    """Отчёт по формуле (19).

    pi[I.parameter, R.cache_hit] (
        Instruction RIGHT JOIN[I.key = R.instruction]
        sigma[R.timestamp > now - 8 min] (Reply)
    )

    Правое внешнее соединение сохраняет каждый подходящий Reply, даже
    если Instruction для него не нашлась: тогда parameter равен None
    """
    border = now() - RECENT_SECONDS
    numpar = {i["key"]: i["parameter"] for i in instructions}
    recrep = []
    for r in replies:
        if r["timestamp"] > border:
            recrep.append({
                "parameter": numpar.get(r["instruction"]),
                "cache_hit": r["cache_hit"],
            })
    return recrep
