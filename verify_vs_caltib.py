#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""verify_vs_caltib.py — внешний оракул для таблицы Лосара (losar_provenance/losar_dates.json): caltib (MIT,
точные традиционные движки Пхугпа/Цурпху по Янсону, целочисленная арифметика). Issue #17.

Сверяется дата Лосара (1-й день года) по Пхугпа для всех строк таблицы (1900–2100). Результат 2026-11-09:
201/201 совпали — третья независимая линия к Janson (печатно) и Henning (tibcalendar).

Запуск:  .venv/bin/python verify_vs_caltib.py [--require]
Зависимость (вне .venv): pip install --target /tmp/xval_site caltib && PYTHONPATH=/tmp/xval_site …
"""
import json
import os
import sys
import warnings

DIR = os.path.dirname(os.path.abspath(__file__))
try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import caltib
except ImportError:
    if "--require" in sys.argv:
        print("verify_vs_caltib: caltib не установлен (pip install caltib) — оракул обязателен, exit 2")
        sys.exit(2)
    print("verify_vs_caltib: caltib не установлен — оракул пропущен (pip install caltib, чтобы включить)")
    sys.exit(0)


def main():
    rows = json.load(open(os.path.join(DIR, "losar_provenance", "losar_dates.json"), encoding="utf-8"))["rows"]
    bad = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for r in rows:
            theirs = str(caltib.api.new_year_day(r["year"], engine="phugpa"))
            if theirs != r["losar"]:
                bad.append((r["year"], r["losar"], theirs))
    print(f"verify_vs_caltib: Лосар Пхугпа {rows[0]['year']}–{rows[-1]['year']} против caltib — "
          f"совпало {len(rows) - len(bad)}/{len(rows)}, расхождений {len(bad)}")
    for y, ours, theirs in bad[:20]:
        print(f"  ✗ {y}: таблица {ours}, caltib {theirs}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
