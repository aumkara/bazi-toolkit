#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""verify_vs_lunar.py — внешний оракул для bazi.py: сверка четырёх столпов с lunar-python (6tail).

Идея взята из fortune-assistant / bazaar-of-fates (2026-11-09, docs/related_projects.md): календарная
арифметика проверяется не только своими golden-тестами, но и независимой реализацией.
Сравниваем ТОЛЬКО календарь: пояс UTC+8, без города и солнечной поправки.

История: первый прогон (2026-11-09) дал 10 расхождений — все по стволу часа 23:00–23:59 (夜子时):
bazi.py брал его от текущего дня, lunar-python — от следующего (классическое правило). Issue #16 закрыт
принятием мейнстрима, с тех пор любое расхождение — настоящее.

Запуск:  .venv/bin/python verify_vs_lunar.py [N=300] [--seed 20261109] [--require] [--verbose]
Зависимость (не в .venv проекта): pip install --target /tmp/xval_site lunar-python && PYTHONPATH=/tmp/xval_site …
Без lunar_python — честный пропуск с exit 0 (оракул необязателен), с флагом --require — exit 2.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from lunar_python import Solar
except ImportError:
    if "--require" in sys.argv:
        print("verify_vs_lunar: lunar_python не установлен (pip install lunar-python) — оракул обязателен, exit 2")
        sys.exit(2)
    print("verify_vs_lunar: lunar_python не установлен — оракул пропущен (pip install lunar-python, чтобы включить)")
    sys.exit(0)

import bazi

BOUNDARY_CASES = [  # Личунь 1990 (10:14 CST) и 2024 (16:27 CST), полночь, 夜子时, опорные даты
    (1990, 2, 4, 9, 0), (1990, 2, 4, 11, 0), (2024, 2, 4, 16, 20), (2024, 2, 4, 16, 40),
    (1990, 5, 15, 0, 30), (1990, 5, 15, 23, 30), (2000, 1, 1, 0, 0), (1949, 10, 1, 12, 0),
    (2019, 1, 27, 12, 0), (2020, 5, 4, 23, 45), (1965, 12, 2, 23, 15),
]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = int(args[0]) if args else 300
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 20261109
    rnd = random.Random(seed)
    cases = [(rnd.randint(1900, 2050), rnd.randint(1, 12), rnd.randint(1, 28),
              rnd.randint(0, 23), rnd.choice([0, 15, 30, 45, 59])) for _ in range(n)] + BOUNDARY_CASES
    mism = []
    for (y, m, d, hh, mm) in cases:
        data = bazi.build_chart_data(y, m, d, hh, mm, "мужской", 8)
        ours = [data["pillars"][k]["name"] for k in ("year", "month", "day", "hour")]
        ec = Solar.fromYmdHms(y, m, d, hh, mm, 0).getLunar().getEightChar()
        ec.setSect(2)  # 夜子时: день остаётся текущим — как в bazi.py (conventions.late_zi_day = same_day)
        theirs = [ec.getYear(), ec.getMonth(), ec.getDay(), ec.getTime()]
        if ours != theirs:
            mism.append((f"{y:04d}-{m:02d}-{d:02d} {hh:02d}:{mm:02d}", "".join(ours), "".join(theirs)))
    total = len(cases)
    print(f"verify_vs_lunar: {total} моментов (UTC+8) против lunar-python — совпало {total - len(mism)}, "
          f"расхождений: {len(mism)}")
    for when, o, t in mism[:20]:
        print(f"  ✗ {when}  bazi.py={o}  lunar={t}")
    return 1 if mism else 0


if __name__ == "__main__":
    sys.exit(main())
