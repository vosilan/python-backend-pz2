"""Демонстрация: вызов всех обработчиков HTTP API через клиента

Сервер должен быть запущен отдельно: make server
"""

from client import PREFIX, ApiClient, ApiError
from db import now

URL = "http://127.0.0.1:5019"
OLD_SECONDS = 10 * 60


def show(title, call, *args):
    """Выполнить вызов клиента и напечатать результат или ошибку"""
    print(f"\n== {title}")
    try:
        result = call(*args)
    except ApiError as error:
        print("ошибка", error)
        return None
    for row in result if isinstance(result, list) else [result]:
        print(row)
    return result


def main():
    """Пройти по всем маршрутам табл. 19 и показать ошибки заголовков"""
    api = ApiClient(URL)
    profile = show(
        "1.1 save/profile", api.core_api_v2_save_profile, "linux", "Firefox"
    )
    show("1.2 fetch/profile", api.core_api_v2_fetch_profile)
    show("1.3 inspect/profile", api.core_api_v2_inspect_profile, 1)
    key = profile["key"]
    task = show(
        "2.1 save/instruction", api.core_api_v2_save_instruction,
        "привет, привет, привет", key,
    )
    show(
        "2.1 задача десять минут назад", api.core_api_v2_save_instruction,
        "старые данные", key, now() - OLD_SECONDS,
    )
    show("2.2 fetch/instruction", api.core_api_v2_fetch_instruction, key)
    show(
        "2.3 inspect/instruction", api.core_api_v2_inspect_instruction,
        task["key"],
    )
    show("3.1 fetch/reply", api.core_api_v2_fetch_reply, task["key"])
    show("3.2 inspect/reply", api.core_api_v2_inspect_reply, task["key"])
    show("4.1 fetch/report", api.core_api_v2_fetch_report)
    show("нет такой записи", api.core_api_v2_inspect_profile, 10 ** 6)
    for method, headers in [
        ("POST", {}), ("POST", {"Content-Type": "text/xml"}), ("GET", {}),
    ]:
        status, body = api.send(method, PREFIX + "/fetch/report", b"", headers)
        print(f"\n== {method} с заголовками {headers}")
        print(status, body.decode("utf-8"))


if __name__ == "__main__":
    main()
