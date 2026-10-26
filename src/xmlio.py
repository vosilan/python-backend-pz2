"""Перевод записей в XML и обратно

Запись: <profile><key>1</key><platform>linux</platform>...</profile>
Список: <profiles><profile>...</profile>...</profiles>
Поле со значением None в XML не пишется
"""

from xml.etree import ElementTree

INT_FIELDS = {"key", "timestamp", "profile", "instruction", "cache_hit"}


def _element(tag, record):
    """Элемент XML для одной записи"""
    node = ElementTree.Element(tag)
    for name, value in record.items():
        if value is not None:
            ElementTree.SubElement(node, name).text = str(value)
    return node


def dump(tag, record):
    """Одна запись в байты XML"""
    return ElementTree.tostring(_element(tag, record), encoding="utf-8")


def dump_list(tag, records, root):
    """Список записей в байты XML с корнем root"""
    node = ElementTree.Element(root)
    for record in records:
        node.append(_element(tag, record))
    return ElementTree.tostring(node, encoding="utf-8")


def _fields(node):
    """Словарь полей элемента, числовые поля приводятся к int"""
    record = {}
    for child in node:
        text = child.text or ""
        record[child.tag] = int(text) if child.tag in INT_FIELDS else text
    return record


def load(body):
    """Байты XML одной записи в словарь"""
    return _fields(ElementTree.fromstring(body))


def load_list(body):
    """Байты XML списка записей в список словарей"""
    return [_fields(node) for node in ElementTree.fromstring(body)]
