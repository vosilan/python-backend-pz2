# HTTP API для сжатия файлов по алгоритму LZMA2 (XZ)

Практическое задание №2, вариант 19. Тема курсовой работы: веб-приложение
с HTTP API для асинхронного сжатия файлов по алгоритму LZMA2 (XZ).

## Общее описание

Проект выполнен в три этапа:

1. Утилита командной строки `xzpack.py`: читает данные из стандартного
   ввода, сжимает алгоритмом LZMA2 в формат XZ и сохраняет в файл.
2. Веб-приложение на Flask с HTTP API в формате XML. Задача сжатия,
   полученная через API, выполняется утилитой из этапа 1 в отдельном
   процессе (модуль `subprocess`). Клиент к API, тестирование на основе
   модели (`hypothesis`) и отчёт о покрытии по ветвям (`coverage`).
3. Хранение данных в SQLite через ORM SQLAlchemy.

Схема данных:

| Таблица     | Поля |
|-------------|------|
| Profile     | key, timestamp, platform, user_agent |
| Instruction | key, timestamp, parameter, profile (ссылка на Profile), stage |
| Reply       | key, timestamp, response, stage, failure, instruction (ссылка на Instruction), cache_hit |

Instruction это задача сжатия, в `parameter` данные для сжатия. Reply
это её результат: путь к файлу `.xz` в `response`, `done` или `failed`
в `stage`, текст ошибки в `failure`. Кэша в приложении нет, `cache_hit`
всегда 0.

Структура репозитория:

```
src/xzpack.py      утилита сжатия
src/app.py         веб-приложение на Flask
src/xmlio.py       перевод записей в XML и обратно
src/db.py          слой доступа к данным на SQLite
src/client.py      клиент к HTTP API
src/demo.py        вызов всех обработчиков через клиента
tests/test_api.py  тестирование на основе модели
examples/          входные данные для утилиты
```

## Функции и настройки

### Утилита (`src/xzpack.py`)

```
python src/xzpack.py ФАЙЛ_РЕЗУЛЬТАТА < входной_файл
```

Сжимает стандартный ввод в файл формата XZ и печатает размеры до и после
сжатия в байтах.

### HTTP API (`src/app.py`)

| № | Метод | Маршрут | Параметры запроса |
|---|-------|---------|-------------------|
| 1.1 | POST | `/core/api/v2/save/profile` | тело: platform, user_agent |
| 1.2 | POST | `/core/api/v2/fetch/profile` | тело: поля для поиска |
| 1.3 | GET | `/core/api/v2/inspect/profile` | `?key=N` |
| 2.1 | POST | `/core/api/v2/save/instruction` | тело: parameter, profile |
| 2.2 | POST | `/core/api/v2/fetch/instruction/:profile` | путь, тело |
| 2.3 | GET | `/core/api/v2/inspect/instruction` | `?key=N` |
| 3.1 | POST | `/core/api/v2/fetch/reply/:instruction` | путь, тело |
| 3.2 | GET | `/core/api/v2/inspect/reply` | `?key=N` |
| 4.1 | POST | `/core/api/v2/fetch/report` | нет |

`save` создаёт запись и возвращает её. Маршрут 2.1 при этом сжимает
`parameter` утилитой и записывает результат в Reply. `fetch` возвращает
список найденных записей, для 2.2 и 3.1 только записи Profile или
Instruction из пути. `inspect` возвращает одну запись по ключу.

При создании записи можно передать `timestamp`, иначе берётся текущее
время. Поиск возвращает записи, у которых поля из тела совпадают
с заданными значениями, пустое тело возвращает все записи.

Отчёт 4.1: параметр задачи и `cache_hit` для всех Reply за последние
8 минут, формула (19):

```
π[I.parameter, R.cache_hit] ( I ⟖[I.key = R.instruction] ( σ[R.timestamp > now − 8 min] R ) )
```

Формат XML: запись `<profile><key>1</key><platform>linux</platform>…</profile>`,
список `<profiles>…</profiles>`, отчёт `<report><row>…</row></report>`,
ошибка `<error><message>…</message></error>`.

Коды ответов:

| Код | Когда |
|-----|-------|
| 415 | у POST, PUT, PATCH нет заголовка `Content-Type: text/xml` |
| 406 | нет заголовка `Accept: text/xml` |
| 200 | во всех остальных случаях |

Если нет обоих заголовков, возвращается 415. Ошибки обработки (записи
с таким ключом нет, некорректный XML, нет обязательного поля) приходят
с кодом 200 и телом `<error><message>…</message></error>`.

Сервер слушает `127.0.0.1:5019`, данные хранит в `data.sqlite`, сжатые
файлы кладёт в `results/`. Тестовый режим без запуска утилиты:
переменная окружения `XZ_FAKE=1`.

### Слой данных (`src/db.py`)

Таблицы описаны классами SQLAlchemy `Profile`, `Instruction`, `Reply`.

| Функция | Назначение |
|---------|------------|
| `connect(url)` | подключиться к базе и создать таблицы |
| `create_profile`, `create_instruction`, `create_reply` | создать запись |
| `get_profile`, `get_instruction`, `get_reply` | запись по ключу, иначе `ModelError` |
| `find_profiles`, `find_instructions`, `find_replies` | поиск по значениям полей |
| `select_recent_replies` | отчёт по формуле (19) |
| `reset` | удалить все записи |

### Клиент (`src/client.py`)

Класс `ApiClient(url)`. Имена методов повторяют маршруты, «/» заменён
на «_»: `core_api_v2_save_profile`, `core_api_v2_fetch_profile`,
`core_api_v2_inspect_profile`, `core_api_v2_save_instruction`,
`core_api_v2_fetch_instruction`, `core_api_v2_inspect_instruction`,
`core_api_v2_fetch_reply`, `core_api_v2_inspect_reply`,
`core_api_v2_fetch_report`. Если код ответа не 200 или в теле
`<error>`, выбрасывается `ApiError`.

## Сборка и запуск

```
make install    # виртуальное окружение и зависимости
make examples   # утилита на пяти примерах
make server     # запуск веб-приложения
make demo       # все обработчики через клиента (в другом терминале)
make test       # тесты на основе модели и отчёт о покрытии
make lint       # проверка стиля flake8
```

## Примеры использования

`make examples`, размеры до и после сжатия:

| Вход | До | После |
|------|----|-------|
| `examples/text.txt` | 617 | 408 |
| `examples/profiles.json` | 5 878 | 468 |
| `examples/access.csv` | 25 200 | 728 |
| 4 КБ случайных байт | 4 096 | 4 156 |
| пустой ввод | 0 | 32 |

Распаковка стандартной утилитой: `xz -dc results/text.xz`.

Запросы через curl:

```
curl -X POST http://127.0.0.1:5019/core/api/v2/save/profile \
     -H "Content-Type: text/xml" -H "Accept: text/xml" \
     -d "<profile><platform>linux</platform><user_agent>curl</user_agent></profile>"

curl -X POST http://127.0.0.1:5019/core/api/v2/save/instruction \
     -H "Content-Type: text/xml" -H "Accept: text/xml" \
     -d "<instruction><parameter>привет</parameter><profile>1</profile></instruction>"

curl "http://127.0.0.1:5019/core/api/v2/inspect/reply?key=1" -H "Accept: text/xml"
```

Через клиента:

```python
from client import ApiClient

api = ApiClient("http://127.0.0.1:5019")
profile = api.core_api_v2_save_profile("linux", "Firefox")
task = api.core_api_v2_save_instruction("привет", profile["key"])
print(api.core_api_v2_fetch_reply(task["key"]))
print(api.core_api_v2_fetch_report())
```

`make test` выводит отчёт о покрытии: 100 % строк и ветвей во всех
модулях API.
