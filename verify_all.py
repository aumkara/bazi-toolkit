#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""
verify_all.py — одна кнопка «проверить всё»: ЧИСТЫЙ ТЕСТ ДВИЖКОВ на зашитом
тест-рождении. Гоняет golden-/инвариант-тесты всех калькуляторов и кросс-системные
тождества (один ephem_core → потребители обязаны сойтись). Выход: PASS/FAIL по
каждому + итог; код возврата 1 при любом FAIL.

Гейт «движки исправны» перед каждым прогоном на пользовательских данных; вывод
к карте пользователя НЕ относится и в чтение НЕ идёт. Все оговорки чтения
(хрупкость, Лосар, конвенция узлов, уверенность) живут в honesty-полях JSON
конкретного прогона: fragile_activations / losar_warning / convention_warnings /
confidence / not_computed / *_note.

Это слои верификации из плана: 1 (golden), 2 (инварианты), 3 (два движка),
4 (кросс-система) — в одном отчёте; слой 5 (близость к границе) живёт в JSON
каждой карты (fragile_activations и т.п.), не здесь.
"""
import io
import contextlib
import sys
from datetime import datetime, timezone, date

import ephem_core as ec
import geo
import hd
import gene_keys as gk
import jyotish as jy
import matrix as mx
import tibetan as tb
import timezones as tz
import bazi

# тест-рождение
DT = datetime(1990, 3, 3, 12, 0, tzinfo=timezone.utc)   # нейтральная фикстура (issue #4): 1990-03-03 15:00 Москва = 12:00 UTC; node-чувствительна
LAT, LON = 55.75, 37.62


def _quiet(fn):
    """Запустить _test() молча, вернуть (ok, exception|None)."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            ok = fn()
        return bool(ok), None
    except Exception as e:  # noqa
        return False, e


def main():
    print("═" * 64)
    print("  VERIFY ALL — проверка всех калькуляторов и кросс-связей")
    print("═" * 64)

    # ── 1. golden + инварианты каждого модуля ──
    print("\n[1] GOLDEN / ИНВАРИАНТЫ (каждый калькулятор):")
    units = [("ephem_core", ec._test), ("geo", geo._test), ("hd", hd._test),
             ("gene_keys", gk._test), ("jyotish", jy._test), ("matrix", mx._test),
             ("tibetan", tb._test),
             # timezones — внутри гейта, а не только в check_all.sh: правка CITIES/CITY_IANA —
             # единственная разрешённая скиллу правка кода, гейт не должен быть к ней слеп
             ("timezones", tz._test)]
    results = []
    for name, fn in units:
        ok, err = _quiet(fn)
        results.append(ok)
        tag = "PASS" if ok else "FAIL"
        print(f"    [{tag}] {name}" + (f"  — {err}" if err else ""))
    # bazi — собственный тест
    bazi_ok = False
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            bazi_ok = bazi.run_tests() if hasattr(bazi, "run_tests") else None
        if bazi_ok is None:
            import subprocess
            r = subprocess.run([sys.executable, "bazi.py", "--test"], capture_output=True)
            bazi_ok = (r.returncode == 0)
    except Exception as e:  # noqa
        bazi_ok = False
    results.append(bazi_ok)
    print(f"    [{'PASS' if bazi_ok else 'FAIL'}] bazi")

    # ── 2. кросс-система (слой 4) ──
    print("\n[2] КРОСС-СИСТЕМНЫЕ ТОЖДЕСТВА:")
    cross = []

    # 2a. hd Солнце Личности == gene_keys Life's Work
    hd_ch = hd.build_chart(DT)
    hd_sun = next(a for a in hd_ch["activations"]["personality"] if a["body"] == "sun")
    gk_prof = gk.build_profile(DT)
    lw = next(s for s in gk_prof["spheres"] if s["sphere"] == "Life's Work")
    c1 = (hd_sun["gate"], hd_sun["line"]) == (lw["gate"], lw["line"])
    cross.append(c1)
    print(f"    [{'PASS' if c1 else 'FAIL'}] HD Солнце {hd_sun['gate']}.{hd_sun['line']} "
          f"== Gene Keys Life's Work {lw['gate']}.{lw['line']}")

    # 2b. bazi год-животное == tibetan год-животное (оба sexagenary)
    bz = bazi.build_chart_data(1990, 3, 3, 15, 0, None, 3)
    bz_animal = bz["pillars"]["year"]["branch"]["animal"]
    tb_animal = tb.build_profile(date(1990, 3, 3))["year_sign"]["animal"]
    c2 = bz_animal == tb_animal
    cross.append(c2)
    print(f"    [{'PASS' if c2 else 'FAIL'}] Ба Цзы год-животное '{bz_animal}' == Джунгци '{tb_animal}'")

    # 2b2. Джунгци Меуа: якоря из 2 независимых источников (hannilim + buddhaweekly)
    mewa_ok = all(tb.birth_mewa(yr) == exp for yr, exp in
                  {1927: 1, 1981: 1, 1990: 1, 1989: 2, 1984: 7, 1992: 8}.items())
    cross.append(mewa_ok)
    print(f"    [{'PASS' if mewa_ok else 'FAIL'}] Джунгци Меуа 1989 = {tb.birth_mewa(1989)} (якоря 6/6)")

    # 2c. два движка (слой 3) на тест-рождении
    mxd, _ = ec.dual_engine_max_diff(DT)
    c3 = mxd < 3.0
    cross.append(c3)
    print(f"    [{'PASS' if c3 else 'FAIL'}] два движка swisseph↔ephem: макс {mxd:.2f}′ (< 3′)")

    # 2d. Лагна резолвится через geo
    la, lo = geo.resolve("Москва")
    jy_ch = jy.build_chart(DT, la, lo)
    c4 = jy_ch["lagna"]["rashi"] in [r[0] for r in jy.RASHI]
    cross.append(c4)
    print(f"    [{'PASS' if c4 else 'FAIL'}] geo→Джйотиш Лагна = {jy_ch['lagna']['rashi']} "
          f"(ЭТАЛОН Москва 1990-03-03, НЕ карта пользователя)")

    # ── ИТОГ ──
    # «Флагов для чтения» здесь больше НЕТ (снято 2026-07-11): это чистый тест,
    # его вывод в чтение не идёт; оговорки чтения — из honesty-полей JSON карты.
    all_ok = all(results) and all(cross)
    npass = sum(results) + sum(cross)
    ntot = len(results) + len(cross)
    print("\n" + "═" * 64)
    print(f"  ИТОГ: {npass}/{ntot} проверок PASS (чистый тест движков; вывод в чтение не идёт)")
    print(f"  {'✓ ВСЁ ЗЕЛЁНО — числам можно доверять' if all_ok else '✗ ЕСТЬ КРАСНОЕ — чинить до интерпретации'}")
    print("═" * 64)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
