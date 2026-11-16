#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""cli_errors.py — единый формат ошибок для CLI калькуляторов.

Контракт (его проверяет check_cli_errors.py):
  код 0 — результат; при --json в stdout только JSON результата;
  код 2 — неверный или неполный ввод (дата, время, пояс, город, флаги);
  код 1 — внутренняя ошибка либо красный --test.
Сообщение об ошибке идёт в stderr строкой «ОШИБКА: …» (или подсказкой по использованию), без трассировки;
в режиме --json в stdout дополнительно печатается {"error": {"kind": "input"|"internal", "message": "..."}} —
потребителю не нужно разбирать stderr. Трассировка печатается только при BAZI_DEBUG=1.

Что считается неверным вводом: InputError откуда угодно, а также ValueError / KeyError / IndexError / OverflowError,
возникшие ПРЯМО в функции-точке входа (разбор аргументов) или в функции с пометкой @parser. То же исключение из
глубины расчёта — внутренняя ошибка (код 1): дефект движка не должен выглядеть как опечатка пользователя.
Поэтому точка входа обязана проверить ввод сама, до вызова движка.
Вне контракта: сбой импорта зависимостей (нет .venv, swisseph или ephem) происходит до входа в обработчик —
сообщение в stderr и ненулевой код есть, JSON-конверта нет.

Использование в калькуляторе:
    import cli_errors
    ...
    raise cli_errors.InputError("месяц должен быть 1–12")      # из любого места разбора ввода
    ...
    if __name__ == "__main__":
        cli_errors.run(main)
"""
import json
import os
import sys
import traceback


class InputError(Exception):
    """Неверные или неполные входные данные: код возврата 2."""


_reported = False
_PARSERS = set()


def parser(fn):
    """Пометить функцию разбора ввода: ValueError/KeyError/IndexError из неё — неверный ввод, а не дефект."""
    _PARSERS.add(fn.__code__)
    return fn


def _emit_json(kind, message):
    global _reported
    _reported = True
    sys.stdout.flush()
    print(json.dumps({"error": {"kind": kind, "message": message}}, ensure_ascii=False))
    sys.stdout.flush()


def fail(message, kind="input"):
    """Сообщить об ошибке по контракту и завершить процесс: input → 2, internal → 1."""
    if "--json" in sys.argv:
        _emit_json(kind, message)
    print(f"ОШИБКА: {message}", file=sys.stderr)
    sys.exit(2 if kind == "input" else 1)


class _Tee:
    """Пропускает stderr насквозь и помнит последнюю непустую строку — для JSON-конверта при sys.exit(код)."""

    def __init__(self, stream):
        self.stream, self.last = stream, ""

    def write(self, text):
        for line in str(text).split("\n"):
            if line.strip():
                self.last = line.strip()
        return self.stream.write(text)

    def __getattr__(self, name):
        return getattr(self.stream, name)


def _raised_in_entry(exc, entry):
    """Исключение возникло прямо в точке входа (или во вложенной в неё функции) либо в @parser-функции?"""
    tb = exc.__traceback__
    while tb is not None and tb.tb_next is not None:
        tb = tb.tb_next
    if tb is None:
        return False
    code, top = tb.tb_frame.f_code, entry.__code__
    if code in _PARSERS:
        return True
    if code.co_filename != top.co_filename:
        return False
    last = max((ln for _a, _b, ln in top.co_lines() if ln), default=top.co_firstlineno)
    return top.co_firstlineno <= code.co_firstlineno <= last      # сама функция или вложенные в неё


def _describe(exc):
    if isinstance(exc, IndexError):
        return "не хватает аргументов или значения после флага"
    if isinstance(exc, KeyError):
        return f"неизвестное значение во входных данных: {exc.args[0] if exc.args else exc}"
    return f"неверное значение во входных данных: {exc}"


def _exit_nonzero(code, last_stderr_line):
    """Калькулятор сам напечатал сообщение и выбрал код: в режиме --json добавить конверт и выйти с тем же кодом."""
    if "--json" in sys.argv and not _reported:
        message = last_stderr_line or f"завершение с кодом {code}"
        for prefix in ("ОШИБКА: ", "ОШИБКА "):
            if message.startswith(prefix):
                message = message[len(prefix):]
        _emit_json("input" if code == 2 else "internal", message)
    sys.exit(code)


def run(main, entry=None):
    """Выполнить main() калькулятора под общим обработчиком ошибок и завершить процесс с кодом по контракту.
    entry — функция-точка входа, если main обёрнут (например, lambda): по ней отличается разбор ввода от расчёта."""
    entry = entry or main
    real, tee = sys.stderr, _Tee(sys.stderr)
    sys.stderr = tee
    debug = os.environ.get("BAZI_DEBUG") == "1"
    try:
        try:
            rc = main()
            sys.stdout.flush()                  # закрытый получатель (| head) должен всплыть здесь, а не при выходе
        finally:
            sys.stderr = real
    except SystemExit as exc:
        code = exc.code
        if code in (None, 0):
            raise
        if not isinstance(code, int):           # sys.exit("текст"): текст — в stderr, код 1
            print(code, file=sys.stderr)
            tee.last, code = str(code), 1
        _exit_nonzero(code, tee.last)
    except KeyboardInterrupt:
        sys.exit(130)
    except BrokenPipeError:
        # читатель закрыл канал (… | head): писать больше некуда — молча выйти, как процесс, получивший SIGPIPE
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except (OSError, ValueError):
            pass
        sys.exit(141)
    except InputError as exc:
        fail(str(exc))
    except (ValueError, KeyError, IndexError, OverflowError) as exc:
        if debug:
            traceback.print_exc()
        if _raised_in_entry(exc, entry):
            fail(_describe(exc))
        fail(f"внутренняя ошибка {type(exc).__name__}: {exc}", kind="internal")
    except Exception as exc:  # ошибка в самом калькуляторе
        if debug:
            traceback.print_exc()
        fail(f"внутренняя ошибка {type(exc).__name__}: {exc}", kind="internal")
    if isinstance(rc, int) and not isinstance(rc, bool) and rc != 0:    # main() вернул код сам, сообщение уже в stderr
        _exit_nonzero(rc, tee.last)
    sys.exit(0)
