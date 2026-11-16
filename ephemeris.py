#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""
ephemeris.py — единственный источник астрономии Солнца для Ба Цзы (Swiss Ephemeris).

Политика (правило пользователя): долготу Солнца для границ 节气/立春 берём ТОЛЬКО
из pyswisseph. Без него расчёт ОСТАНАВЛИВАЕТСЯ — никакого тихого отката на
приближение Meeus (ошибка 3.5–13 мин), которое раньше дублировалось в
bazi.py и jieqi.py. Это и закрывает старый долг «две разошедшиеся копии астрономии»:
теперь источник один.

pyswisseph установлен в .venv проекта. Если этот модуль импортируется из-под
системного python3 (так зовёт команда /bazi), один раз перезапускаем текущий
скрипт под интерпретатором .venv.
"""
import os
import sys
from datetime import datetime, timezone

try:
    import swisseph as swe
except ImportError:
    _here = os.path.dirname(os.path.abspath(__file__))
    _venv_dir = os.path.join(_here, ".venv")
    _venv_py = os.path.join(_venv_dir, "bin", "python")
    # Один раз перезапускаем себя под .venv (где стоит swisseph). Сравниваем
    # sys.prefix, а НЕ путь к бинарю: venv и системный python — один и тот же
    # бинарь Homebrew, различаются только префиксом/site-packages.
    _already_in_venv = os.path.realpath(sys.prefix) == os.path.realpath(_venv_dir)
    _script = os.path.abspath(sys.argv[0])
    if (not os.environ.get("BAZI_SWE_BOOTSTRAP")
            and os.path.exists(_venv_py)
            and not _already_in_venv
            and os.path.isfile(_script)):  # перезапускаем только реальный скрипт (не python3 -c)
        os.environ["BAZI_SWE_BOOTSTRAP"] = "1"
        os.execv(_venv_py, [_venv_py, _script, *sys.argv[1:]])
    # Перезапуск не помог или невозможен — отказываемся считать, говорим прямо.
    sys.exit(
        "ОШИБКА: pyswisseph (Swiss Ephemeris) не установлен — расчёт остановлен.\n"
        "Астрономия 节气/立春 обязана идти через swisseph (без него не считаем,\n"
        "не падаем молча на приближение). Установи в .venv проекта:\n"
        f"  {_venv_py} -m pip install --no-binary :all: pyswisseph\n"
        "(нужны Command Line Tools / clang), затем повтори."
    )


def sun_lon(jd):
    """Видимая геоцентрическая эклиптическая долгота Солнца в градусах [0, 360).

    jd — юлианский день в UT (как возвращает julian_day в bazi.py / jieqi.py).
    Режим Moshier (FLG_MOSEPH): самодостаточно, без внешних файлов эфемерид;
    сверено с равноденствием 2026 — совпадает с published/ephem до секунд.
    Точность ~1″ по Солнцу на 1900–2100 → ошибка времени термина < ~3 сек
    (приближение Meeus, которое это заменило, давало 3.5–13 мин).
    """
    return swe.calc_ut(jd, swe.SUN, swe.FLG_MOSEPH)[0][0] % 360


# ── Календарная арифметика (единственная копия; issue #11) ───────────────────────────────────────
# До 2026-11-09 julian_day / jd_to_dt / find_term жили дублями в bazi.py и jieqi.py.

def julian_day(year, month, day, hour=0, minute=0, second=0):
    """Юлианский день из григорианской даты и времени UT (Флигель — Ван Фландерн)."""
    if month <= 2:
        year -= 1
        month += 12
    A = int(year / 100)
    B = 2 - A + int(A / 4)
    day_frac = day + (hour + minute / 60.0 + second / 3600.0) / 24.0
    return int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day_frac + B - 1524.5


def jd_to_datetime(jd):
    """Юлианский день → datetime (UTC), секунды усечены."""
    jd += 0.5
    Z = int(jd)
    F = jd - Z
    if Z < 2299161:
        A = Z
    else:
        alpha = int((Z - 1867216.25) / 36524.25)
        A = Z + 1 + alpha - int(alpha / 4)
    B = A + 1524
    C = int((B - 122.1) / 365.25)
    D = int(365.25 * C)
    E = int((B - D) / 30.6001)
    day = B - D - int(30.6001 * E) + F
    month = E - 1 if E < 14 else E - 13
    year = C - 4716 if month > 2 else C - 4715
    d = int(day)
    frac = (day - d) * 24
    h = int(frac)
    frac = (frac - h) * 60
    m = int(frac)
    s = int((frac - m) * 60)
    return datetime(int(year), int(month), d, h, m, s, tzinfo=timezone.utc)


def find_solar_term(year, target_longitude):
    """JD момента, когда видимая долгота Солнца равна target_longitude (°), в окрестности данного года.
    Стартовое приближение — от равноденствия (0° ≈ 20 марта); 285°…360° — январь-февраль того же года.
    Уточнение — итерации Ньютона по sun_lon (Swiss Ephemeris), порог 0.0001° (< 10 с)."""
    if target_longitude < 285:
        days_from_equinox = target_longitude * 365.25 / 360
    else:
        days_from_equinox = (target_longitude - 360) * 365.25 / 360
    jd = julian_day(year, 3, 20) + days_from_equinox
    for _ in range(50):
        diff = target_longitude - sun_lon(jd)
        while diff > 180:
            diff -= 360
        while diff < -180:
            diff += 360
        if abs(diff) < 0.0001:
            break
        jd += diff / 360 * 365.25
    return jd
