"""Утилита сжатия: стандартный ввод -> файл .xz (алгоритм LZMA2)

Запуск: python src/xzpack.py results/text.xz < examples/text.txt
В стандартный вывод печатаются размеры до и после сжатия в байтах
"""

import argparse
import lzma
from pathlib import Path
import sys


def main():
    """Прочитать stdin, сжать в формат XZ и записать в файл"""
    parser = argparse.ArgumentParser(description="Сжатие stdin в .xz")
    parser.add_argument("output", help="путь к файлу результата")
    path = Path(parser.parse_args().output)
    data = sys.stdin.buffer.read()
    result = lzma.compress(data, format=lzma.FORMAT_XZ)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(result)
    print(len(data), len(result))


if __name__ == "__main__":
    main()
