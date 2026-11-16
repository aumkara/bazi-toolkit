#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""verify_meihua_table.py — внешний оракул для таблицы 64 гексаграмм meihua.py (issue #27).

Фикстура oracles/hexagrams_kingwen_wikipedia.json получена 2026-11-09 разбором страницы
https://en.wikipedia.org/wiki/List_of_hexagrams_of_the_I_Ching (порядок 文王; у каждой гексаграммы — нижняя и
верхняя триграммы и имя Unicode). Это независимый от скилла и от памяти модели источник: таблица meihua.py
была сгенерирована из §1.4 skills/meihua/SKILL.md, где заголовок строк/столбцов оказался перепутан (77ed936).
Сверяется: состав (верх, низ) → номер для всех 64; имена (традиционные на странице ↔ упрощённые у нас).
Не сверяется (нет независимой реализации): сами методы 起卦 (суммы, 动爻), 互/错/综 — только внутренние тесты.

Запуск: .venv/bin/python verify_meihua_table.py   (exit 0 — чисто; 1 — расхождения)
"""
import json
import os
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DIR)
import meihua  # noqa: E402

TRAD = {"訟": "讼", "師": "师", "謙": "谦", "隨": "随", "蠱": "蛊", "臨": "临", "觀": "观", "賁": "贲", "剝": "剥", "復": "复",
        "頤": "颐", "大過": "大过", "離": "离", "恆": "恒", "遯": "遁", "大壯": "大壮", "晉": "晋", "損": "损", "豐": "丰",
        "歸妹": "归妹", "節": "节", "渙": "涣", "既濟": "既济", "未濟": "未济", "兌": "兑", "漸": "渐", "小過": "小过"}


def main():
    fx = json.load(open(os.path.join(DIR, "oracles", "hexagrams_kingwen_wikipedia.json"), encoding="utf-8"))
    wiki = {int(k): v for k, v in fx["hexagrams"].items()}
    bad = []
    for n in range(1, 65):
        zh, up, lo, _, _ = meihua.HEXAGRAMS[n]
        w = wiki[n]
        if (up, lo) != (w["upper"], w["lower"]):
            bad.append(f"#{n} {zh}: у нас {up}/{lo}, Wikipedia {w['upper']}/{w['lower']}")
        if TRAD.get(w["zh"], w["zh"]) != zh:
            bad.append(f"#{n}: имя у нас {zh}, Wikipedia {w['zh']}")
    print(f"verify_meihua_table: 64 гексаграммы против Wikipedia (фикстура {fx['fetched']}) — расхождений {len(bad)}")
    for b in bad:
        print("  ✗", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
