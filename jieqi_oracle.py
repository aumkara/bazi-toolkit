#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""Тест-оракул точности 节气: bazi.py (Meeus/VSOP87-упрощённый) против ephem (JPL-эфемериды).
ephem — независимый авторитет, не код проекта. Меряем расхождение в минутах для всех
12 节 (границы месяцев) за 1900–2100, отдельно для 立春 (граница года)."""
import os, sys, math
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ephem
from bazi import find_term, jd_to_dt, SOLAR_TERMS_DATA

def ephem_sun_lon(dt_naive_utc):
    d = ephem.Date(dt_naive_utc)
    s = ephem.Sun()
    s.compute(d)
    # s.ra/s.dec — видимые экв. координаты равноденствия ДАТЫ; задаём epoch=date,
    # чтобы эклиптическая долгота тоже была в равноденствии даты (а не J2000 → прецессия)
    ecl = ephem.Ecliptic(ephem.Equatorial(s.ra, s.dec, epoch=d), epoch=d)
    return math.degrees(ecl.lon)

def ephem_term_time(approx_dt, target_lon):
    """Момент пересечения видимой долготой Солнца target_lon (бисекция, ~секунды)."""
    def f(dt):
        return (ephem_sun_lon(dt) - target_lon + 180) % 360 - 180
    lo, hi = approx_dt - timedelta(days=2), approx_dt + timedelta(days=2)
    flo = f(lo)
    for _ in range(50):
        mid = lo + (hi - lo) / 2
        fm = f(mid)
        if flo * fm <= 0:
            hi = mid
        else:
            lo, flo = mid, fm
    return lo + (hi - lo) / 2

worst = (0, None, None)          # (|Δ|мин, год, термин)
sum_abs = 0.0
n = 0
lichun_worst = (0, None)
lichun_sum = 0.0
lichun_n = 0
LICHUN_DT = None

for year in range(1900, 2101):
    for lon, mnum, branch in SOLAR_TERMS_DATA:
        bazi_dt = jd_to_dt(find_term(year, lon)).replace(tzinfo=None)  # UTC naive
        eph_dt = ephem_term_time(bazi_dt, lon)
        dmin = (bazi_dt - eph_dt).total_seconds() / 60.0
        ad = abs(dmin)
        sum_abs += ad; n += 1
        if ad > worst[0]:
            worst = (ad, year, f"{branch}/{lon}°")
        if lon == 315:  # 立春
            lichun_sum += ad; lichun_n += 1
            if ad > lichun_worst[0]:
                lichun_worst = (ad, year)
            if year == 2024:
                LICHUN_DT = (bazi_dt, eph_dt, dmin)

print(f"Сравнение: bazi.py (Meeus) vs ephem (JPL), 1900–2100, все 12 节")
print(f"  Точек сравнения: {n}")
print(f"  Среднее |Δ|: {sum_abs/n:.2f} мин")
print(f"  Макс |Δ|:    {worst[0]:.2f} мин  (год {worst[1]}, {worst[2]})")
print()
print(f"立春 (граница ГОДА Ба Цзы), 1900–2100:")
print(f"  Среднее |Δ|: {lichun_sum/lichun_n:.2f} мин")
print(f"  Макс |Δ|:    {lichun_worst[0]:.2f} мин  (год {lichun_worst[1]})")
if LICHUN_DT:
    b, e, dd = LICHUN_DT
    print(f"  Пример 立春-2024: bazi.py={b:%Y-%m-%d %H:%M:%S} UTC,  ephem={e:%Y-%m-%d %H:%M:%S} UTC,  Δ={dd:+.1f} мин")
