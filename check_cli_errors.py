#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""check_cli_errors.py — контракт ошибок CLI калькуляторов (cli_errors.py) на заведомо плохом вводе.

Для каждого случая проверяется: код возврата 2; в stderr есть сообщение и нет трассировки; при --json в stdout
лежит {"error": {"kind": "input", "message": ...}}. Плюс по одному хорошему вызову на калькулятор: код 0 и JSON
без ключа error. Запуск: .venv/bin/python check_cli_errors.py   (выход 0 — контракт соблюдён).
"""
import json
import os
import subprocess
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(DIR, ".venv", "bin", "python")
PY = PY if os.path.exists(PY) else sys.executable

BAD = [  # (ярлык, скрипт, аргументы) — везде ждём код 2
    ("bazi: нет данных", "bazi.py", []),
    ("bazi: дата-мусор", "bazi.py", ["abc", "14:30", "М", "--city", "Москва"]),
    ("bazi: 13-й месяц", "bazi.py", ["2026-13-45", "14:30", "М", "--city", "Москва"]),
    ("bazi: города нет в базе", "bazi.py", ["1990-05-15", "14:30", "М", "--city", "Нетакого"]),
    ("bazi: нет пояса", "bazi.py", ["1990-05-15", "14:30", "М"]),
    ("bazi: время 25:99", "bazi.py", ["1990-05-15", "25:99", "М", "--city", "Москва"]),
    ("jyotish: нет данных", "jyotish.py", []),
    ("jyotish: 13-й месяц", "jyotish.py", ["2026-13-45", "14:30", "55.75", "37.62", "+4"]),
    ("jyotish: широта-мусор", "jyotish.py", ["1990-05-15", "14:30", "abc", "37.62", "+4"]),
    ("hd: нет оффсета", "hd.py", ["1990-05-15", "14:30"]),
    ("hd: 13-й месяц", "hd.py", ["2026-13-45", "14:30", "+4"]),
    ("gene_keys: 13-й месяц", "gene_keys.py", ["2026-13-45", "14:30", "+4"]),
    ("matrix: нет данных", "matrix.py", []),
    ("matrix: 13-й месяц", "matrix.py", ["2026-13-45"]),
    ("tibetan: нет данных", "tibetan.py", []),
    ("tibetan: 13-й месяц", "tibetan.py", ["2026-13-45"]),
    ("qimen: 13-й месяц", "qimen.py", ["2026-13-45", "14:30", "UTC+3"]),
    ("qimen: пояс UTC+99", "qimen.py", ["2026-04-08", "14:30", "UTC+99"]),
    ("qimen: --method bad", "qimen.py", ["2026-04-08", "14:30", "UTC+3", "--method", "bad"]),
    ("ziwei: нет данных", "ziwei.py", []),
    ("ziwei: лунный месяц 13", "ziwei.py", ["--lunar", "1990", "13", "15", "14", "М"]),
    ("ziwei: пол-мусор", "ziwei.py", ["--lunar", "1990", "4", "15", "14", "X"]),
    ("ziwei: год-мусор", "ziwei.py", ["--lunar", "abc", "4", "15", "14", "М"]),
    ("meihua: нет данных", "meihua.py", []),
    ("meihua: числа-мусор", "meihua.py", ["--numbers", "a", "b"]),
    ("bazi_reverse: столпы-мусор", "bazi_reverse.py", ["xx", "yy", "zz", "UTC+4"]),
    ("compat: нет файлов карт", "compat.py", []),
]
GOOD = [  # (ярлык, скрипт, аргументы, ключ, который обязан быть в JSON)
    ("bazi", "bazi.py", ["1990-05-15", "14:30", "М", "--city", "Москва"], "pillars"),
    ("jyotish", "jyotish.py", ["1990-05-15", "14:30", "55.75", "37.62", "+4"], "lagna"),
    ("hd", "hd.py", ["1990-05-15", "14:30", "+4"], "type"),
    ("gene_keys", "gene_keys.py", ["1990-05-15", "14:30", "+4"], "spheres"),
    ("matrix", "matrix.py", ["1990-05-15"], "core_points"),
    ("tibetan", "tibetan.py", ["1990-05-15"], "year_sign"),
    ("qimen, дробный пояс UTC+5.5", "qimen.py", ["2026-04-08", "14:30", "UTC+5.5"], "palaces"),
    ("ziwei", "ziwei.py", ["--lunar", "1990", "4", "15", "14", "М"], "zi_wei"),
    ("meihua", "meihua.py", ["--numbers", "17", "29"], "ben_gua"),
    ("bazi_reverse", "bazi_reverse.py", ["庚午", "辛巳", "庚辰", "癸未", "UTC+4", "--from", "1980", "--to", "2000"], "matches"),
]


def call(script, args, env=None):
    return subprocess.run([PY, os.path.join(DIR, script), *args], capture_output=True, text=True, cwd=DIR, timeout=120,
                          env={**os.environ, **(env or {})})


def main():
    ok = True

    def chk(cond, label, detail=""):
        nonlocal ok
        ok &= bool(cond)
        print(("  ✓ " if cond else "  ✗ ") + label + (f" — {detail}" if detail and not cond else ""))

    for label, script, args in BAD:
        p = call(script, args + ["--json"])
        try:
            env = json.loads(p.stdout)
            good_json = isinstance(env.get("error"), dict) and env["error"].get("kind") == "input" and env["error"].get("message")
        except (ValueError, AttributeError):
            good_json = False
        chk(p.returncode == 2 and p.stderr.strip() and "Traceback" not in p.stderr and good_json,
            f"отказ: {label}", f"код {p.returncode}, stdout {p.stdout[:60]!r}, stderr {p.stderr.strip()[-80:]!r}")
        if (script != "bazi.py" or args) and script != "compat.py":   # без --json: stdout пуст, сообщение только в stderr
            q = call(script, args)
            chk(q.returncode == 2 and q.stderr.strip() and "Traceback" not in q.stderr and not q.stdout.strip(),
                f"отказ без --json: {label}", f"код {q.returncode}, stdout {q.stdout[:60]!r}")
    for label, script, args, key in GOOD:
        p = call(script, args + ["--json"])
        try:
            data = json.loads(p.stdout)
        except ValueError:
            data = {}
        chk(p.returncode == 0 and key in data and "error" not in data, f"результат: {label}",
            f"код {p.returncode}, stderr {p.stderr.strip()[-80:]!r}")
    p = call("hd.py", ["2026-13-45", "14:30", "+4", "--json"], env={"BAZI_DEBUG": "1"})
    chk(p.returncode == 2 and "Traceback" in p.stderr, "BAZI_DEBUG=1 показывает трассировку")
    p = call("hd.py", ["2026-13-45", "14:30", "+4", "--json"], env={"BAZI_DEBUG": "0"})
    chk(p.returncode == 2 and "Traceback" not in p.stderr, "BAZI_DEBUG=0 трассировку не включает")

    def probe(body, *argv):
        code = "import sys, cli_errors\n" + body
        return subprocess.run([PY, "-c", code, *argv], capture_output=True, text=True, cwd=DIR, timeout=60)

    p = probe("def engine(): return {}['дефект']\ndef main(): engine()\ncli_errors.run(main)", "--json")
    env = json.loads(p.stdout) if p.stdout.strip().startswith("{") else {}
    chk(p.returncode == 1 and env.get("error", {}).get("kind") == "internal" and "Traceback" not in p.stderr,
        "исключение из глубины расчёта — внутренняя ошибка (код 1), а не «неверный ввод»", f"код {p.returncode}, {p.stdout[:70]!r}")
    p = probe("def main(): return int(sys.argv[1])\ncli_errors.run(main)", "abc", "--json")
    chk(p.returncode == 2, "то же исключение прямо в точке входа — неверный ввод (код 2)", f"код {p.returncode}")
    p = probe("def test(): assert 1 == 2, 'красный'\ndef main(): test()\ncli_errors.run(main)", "--test")
    chk(p.returncode == 1 and "AssertionError" in p.stderr, "красный --test (assert) даёт код 1", f"код {p.returncode}")
    p = probe("def main(): return 1\ncli_errors.run(main)", "--test")
    chk(p.returncode == 1, "--test, вернувший 1, даёт код 1", f"код {p.returncode}")
    sh = subprocess.run(f'"{PY}" bazi.py 1990-05-15 14:30 М --city Москва --json | head -c 0', shell=True, capture_output=True,
                        text=True, cwd=DIR, timeout=120)
    chk("Traceback" not in sh.stderr and "BrokenPipe" not in sh.stderr, "закрытый получатель (| head) не даёт трассировки",
        sh.stderr.strip()[-120:])
    print("check_cli_errors:", "ЗЕЛЕНО ✓" if ok else "КРАСНОЕ ✗")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
