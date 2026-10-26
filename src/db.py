"""Слой доступа к данным на SQLite через ORM SQLAlchemy

Заменяет model.py: те же функции с тем же результатом (словари полей).
Таблицы описаны классами, SQLAlchemy сам переводит обращения к ним
в запросы SQL. Перед работой нужно вызвать connect
"""

import time

from sqlalchemy import ForeignKey, create_engine, delete, select
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, sessionmaker,
)

RECENT_SECONDS = 8 * 60


class ModelError(Exception):
    """Запись не найдена"""


class Base(DeclarativeBase):
    """Общий предок классов-таблиц"""


class Profile(Base):
    """Таблица profile"""

    __tablename__ = "profile"

    key: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[int]
    platform: Mapped[str]
    user_agent: Mapped[str]


class Instruction(Base):
    """Таблица instruction, ссылается на profile"""

    __tablename__ = "instruction"

    key: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[int]
    parameter: Mapped[str]
    profile: Mapped[int] = mapped_column(ForeignKey("profile.key"))
    stage: Mapped[str]


class Reply(Base):
    """Таблица reply, ссылается на instruction"""

    __tablename__ = "reply"

    key: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[int]
    response: Mapped[str]
    stage: Mapped[str]
    failure: Mapped[str]
    instruction: Mapped[int] = mapped_column(ForeignKey("instruction.key"))
    cache_hit: Mapped[int]


session_factory = sessionmaker()


def connect(url):
    """Подключиться к базе по адресу вида sqlite:///data.sqlite.

    Если таблиц ещё нет, они создаются
    """
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    session_factory.configure(bind=engine)


def reset():
    """Удалить все записи, сначала зависимые"""
    with session_factory.begin() as session:
        session.execute(delete(Reply))
        session.execute(delete(Instruction))
        session.execute(delete(Profile))


def now():
    """Текущее время в секундах от начала эпохи Unix"""
    return int(time.time())


def _record_to_dict(row):
    """Запись ORM в словарь полей в порядке столбцов"""
    return {
        column.name: getattr(row, column.name)
        for column in row.__table__.columns
    }


def _insert(row):
    """Сохранить новую запись и вернуть её поля с выданным ключом"""
    with session_factory.begin() as session:
        session.add(row)
        session.flush()
        return _record_to_dict(row)


def _get(table, key):
    """Поля записи по ключу или ModelError"""
    with session_factory() as session:
        row = session.get(table, key)
        if row is None:
            raise ModelError(f"{table.__name__} с key={key} не найден")
        return _record_to_dict(row)


def _find(table, filters):
    """Записи, у которых поля равны значениям из filters, по ключу"""
    query = select(table).filter_by(**filters).order_by(table.key)
    with session_factory() as session:
        return [_record_to_dict(row) for row in session.scalars(query)]


def _stamp(timestamp):
    """Взять переданную метку времени или текущее время"""
    return now() if timestamp is None else timestamp


def create_profile(platform, user_agent, timestamp=None):
    """Создать запись Profile"""
    return _insert(Profile(
        timestamp=_stamp(timestamp), platform=platform,
        user_agent=user_agent,
    ))


def get_profile(key):
    """Запись Profile по ключу"""
    return _get(Profile, key)


def find_profiles(filters):
    """Поиск Profile по значениям полей"""
    return _find(Profile, filters)


def create_instruction(parameter, profile, stage, timestamp=None):
    """Создать запись Instruction для существующего Profile"""
    get_profile(profile)
    return _insert(Instruction(
        timestamp=_stamp(timestamp), parameter=parameter, profile=profile,
        stage=stage,
    ))


def get_instruction(key):
    """Запись Instruction по ключу"""
    return _get(Instruction, key)


def find_instructions(profile, filters):
    """Поиск Instruction одного Profile по значениям полей"""
    return _find(Instruction, {**filters, "profile": profile})


def create_reply(
    response, stage, failure, instruction, cache_hit, timestamp=None
):
    """Создать запись Reply для существующей Instruction"""
    get_instruction(instruction)
    return _insert(Reply(
        timestamp=_stamp(timestamp), response=response, stage=stage,
        failure=failure, instruction=instruction, cache_hit=cache_hit,
    ))


def get_reply(key):
    """Запись Reply по ключу"""
    return _get(Reply, key)


def find_replies(instruction, filters):
    """Поиск Reply одной Instruction по значениям полей"""
    return _find(Reply, {**filters, "instruction": instruction})


def select_recent_replies():
    """Отчёт по формуле (19) одним запросом SQL.

    В SQLAlchemy нет RIGHT JOIN, поэтому таблицы переставлены:
    Instruction RIGHT JOIN Reply то же самое, что Reply LEFT JOIN
    Instruction
    """
    timegran = now() - RECENT_SECONDS
    query = (select(Instruction.parameter, Reply.cache_hit)
             .select_from(Reply)
             .outerjoin(Instruction, Instruction.key == Reply.instruction)
             .where(Reply.timestamp > timegran)
             .order_by(Reply.key))
    with session_factory() as session:
        return [row._asdict() for row in session.execute(query)]
