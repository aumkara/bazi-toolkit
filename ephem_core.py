#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""
ephem_core.py — общий астрономический фундамент для систем, которым нужны точные
положения планет: Дизайн Человека, Генные Ключи, Джйотиш.

Источник №1 — Swiss Ephemeris (pyswisseph, режим Moshier, без внешних файлов).
Источник №2 — PyEphem — используется ТОЛЬКО для независимой перекрёстной сверки
(`dual_engine_max_diff`): если два движка расходятся > порога, это ловится в --test.

Даёт:
  • longitudes(jd, sidereal)      — эклиптич. долготы 13 тел (+ скорости °/сут)
  • design_jd(natal_jd)           — момент Дизайна (Солнце = натальное − 88° дуги)
  • ayanamsa(jd)                  — аянамша Лахири (для сидерики Джйотиш)
  • ascendant(jd, lat, lon, sid)  — асцендент (Лагна)
  • dual_engine_max_diff(dt_utc)  — макс. расхождение swisseph↔ephem, угл. минуты

Конвенции (named явно, потому что школы расходятся — см. AGENTS.md):
  • сидерика: аянамша Лахири (SIDM_LAHIRI)
  • узлы: по умолчанию СРЕДНИЙ узел (mean node) — стандарт большинства Джйотиш;
    истинный узел доступен как 'node_true'. Для Дизайна Человека выбор узла
    проверяется отдельно при сверке с Jovian/Genetic Matrix.
"""
from ephemeris import swe          # переиспользует swisseph + бутстрап-перезапуск под .venv
import ephem                        # второй движок — только для сверки
import math
import sys
from datetime import datetime, timezone

swe.set_sid_mode(swe.SIDM_LAHIRI)   # сидерический режим: Лахири

# ── тела ────────────────────────────────────────────────────────────────────
# Дизайн Человека/Ключи используют 13 «ворот-активаторов»: Солнце, Земля,
# Сев./Юж. узлы, Луна и планеты. Земля = Солнце+180°, Юж.узел = Сев.узел+180°.
_SWE_BODIES = {
    "sun": swe.SUN, "moon": swe.MOON, "mercury": swe.MERCURY, "venus": swe.VENUS,
    "mars": swe.MARS, "jupiter": swe.JUPITER, "saturn": swe.SATURN,
    "uranus": swe.URANUS, "neptune": swe.NEPTUNE, "pluto": swe.PLUTO,
}
_EPHEM_BODIES = {  # для двойной сверки (узлы PyEphem напрямую не даёт)
    "sun": ephem.Sun, "moon": ephem.Moon, "mercury": ephem.Mercury,
    "venus": ephem.Venus, "mars": ephem.Mars, "jupiter": ephem.Jupiter,
    "saturn": ephem.Saturn, "uranus": ephem.Uranus, "neptune": ephem.Neptune,
    "pluto": ephem.Pluto,
}

_FLAG = swe.FLG_MOSEPH | swe.FLG_SPEED


def jd_ut(dt_utc):
    """datetime (UTC, naive или aware) → JD(UT)."""
    if dt_utc.tzinfo is not None:
        dt_utc = dt_utc.astimezone(timezone.utc).replace(tzinfo=None)
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day,
                      dt_utc.hour + dt_utc.minute / 60 + dt_utc.second / 3600)


def dt_from_jd(jd):
    y, m, d, h = swe.revjul(jd)
    hh = int(h); mi = int((h - hh) * 60); ss = int(round((((h - hh) * 60) - mi) * 60))
    if ss == 60: ss = 59
    return datetime(y, m, d, hh, mi, ss, tzinfo=timezone.utc)


def longitudes(jd, sidereal=False):
    """Эклиптич. долготы тел на момент jd (UT).

    Возвращает {имя: {"lon": °[0,360), "speed": °/сут}} для 10 планет +
    производные 'earth', 'node_mean', 'node_true', 'south_node_mean',
    'south_node_true'. sidereal=True → долготы Лахири.
    """
    flag = _FLAG | (swe.FLG_SIDEREAL if sidereal else 0)
    out = {}
    for name, b in _SWE_BODIES.items():
        xx = swe.calc_ut(jd, b, flag)[0]
        out[name] = {"lon": xx[0] % 360, "speed": xx[3]}
    for key, const in (("node_mean", swe.MEAN_NODE), ("node_true", swe.TRUE_NODE)):
        xx = swe.calc_ut(jd, const, flag)[0]
        out[key] = {"lon": xx[0] % 360, "speed": xx[3]}
    # производные
    out["earth"] = {"lon": (out["sun"]["lon"] + 180) % 360, "speed": out["sun"]["speed"]}
    out["south_node_mean"] = {"lon": (out["node_mean"]["lon"] + 180) % 360, "speed": out["node_mean"]["speed"]}
    out["south_node_true"] = {"lon": (out["node_true"]["lon"] + 180) % 360, "speed": out["node_true"]["speed"]}
    return out


def design_jd(natal_jd, tol_deg=1e-7, max_iter=60):
    """JD момента Дизайна Человека: когда Солнце было ровно на 88° дуги РАНЬШЕ
    натального (Sun_design = Sun_natal − 88°, mod 360). Ньютон по реальной
    скорости Солнца. ~88 дней до рождения."""
    natal_sun = swe.calc_ut(natal_jd, swe.SUN, _FLAG)[0][0]
    target = (natal_sun - 88.0) % 360
    jd = natal_jd - 88.0 / 0.9856  # сид Солнца ~0.9856°/сут
    for _ in range(max_iter):
        xx = swe.calc_ut(jd, swe.SUN, _FLAG)[0]
        lon, spd = xx[0], xx[3]
        diff = (target - lon + 180) % 360 - 180
        if abs(diff) < tol_deg:
            break
        jd += diff / spd
    return jd


def ayanamsa(jd):
    """Аянамша Лахири на момент jd (°)."""
    return swe.get_ayanamsa_ut(jd)


def ascendant(jd, lat, lon, sidereal=False, hsys=b"W"):
    """Асцендент (Лагна) в °[0,360). sidereal=True → Лахири; hsys=b'W' (whole-sign,
    стандарт Джйотиш) или b'P' (Placidus, для тропической проверки).
    Возвращает (asc_deg, [12 куспидов])."""
    if sidereal:
        cusps, ascmc = swe.houses_ex(jd, lat, lon, hsys, swe.FLG_SIDEREAL)
    else:
        cusps, ascmc = swe.houses(jd, lat, lon, hsys)
    return ascmc[0] % 360, list(cusps)


# ── двойная сверка движков (слой 3 верификации) ─────────────────────────────

def _ephem_lon(body_cls, dt_utc):
    b = body_cls()
    b.compute(ephem.Date((dt_utc.year, dt_utc.month, dt_utc.day,
                          dt_utc.hour, dt_utc.minute, dt_utc.second)))
    ec = ephem.Ecliptic(b, epoch=ephem.Date((dt_utc.year, dt_utc.month, dt_utc.day,
                                             dt_utc.hour, dt_utc.minute, dt_utc.second)))
    return math.degrees(ec.lon) % 360


def dual_engine_diffs(dt_utc):
    """Расхождения swisseph↔PyEphem по 10 телам, в угловых минутах. dict имя→′."""
    jd = jd_ut(dt_utc)
    trop = longitudes(jd, sidereal=False)
    out = {}
    for name, cls in _EPHEM_BODIES.items():
        a = trop[name]["lon"]
        b = _ephem_lon(cls, dt_utc)
        out[name] = abs((a - b + 180) % 360 - 180) * 60
    return out


def dual_engine_max_diff(dt_utc):
    d = dual_engine_diffs(dt_utc)
    return max(d.values()), d


# ── self-test (слой 1+2+3 для самого фундамента) ────────────────────────────

def _test():
    # тест-рождение: нейтральная фикстура 1990-03-03 15:00 MSK (UTC+3) = 12:00 UTC, Москва 55.75N 37.62E
    dt = datetime(1990, 3, 3, 12, 0, tzinfo=timezone.utc)
    jd = jd_ut(dt)
    LAT, LON = 55.75, 37.62
    ok = True

    print("ephem_core --test  (фикстура 1990-03-03 12:00 UTC, Москва)")
    print("─" * 64)

    # 1) двойной движок
    mx, diffs = dual_engine_max_diff(dt)
    worst = max(diffs, key=diffs.get)
    p1 = mx < 3.0
    ok &= p1
    print(f"[{'PASS' if p1 else 'FAIL'}] двойной движок: макс Δ = {mx:.2f}′ "
          f"(худшее: {worst} {diffs[worst]:.2f}′), порог 3.0′")

    # 2) тождество точки Дизайна: Sun_design == Sun_natal − 88°
    djd = design_jd(jd)
    sun_n = longitudes(jd)["sun"]["lon"]
    sun_d = longitudes(djd)["sun"]["lon"]
    arc = (sun_n - sun_d) % 360
    p2 = abs(arc - 88.0) < 1e-4
    ok &= p2
    days_back = jd - djd
    print(f"[{'PASS' if p2 else 'FAIL'}] точка Дизайна: дуга Солнца = {arc:.6f}° "
          f"(ждём 88.0), за {days_back:.2f} сут до рождения")

    # 3) тождество сидерики: sid == trop − ayanamsa (для всех 10 тел)
    ay = ayanamsa(jd)
    trop = longitudes(jd, False); sidr = longitudes(jd, True)
    worst_sid = 0.0
    for nm in _SWE_BODIES:
        expect = (trop[nm]["lon"] - ay) % 360
        d = abs((sidr[nm]["lon"] - expect + 180) % 360 - 180) * 60
        worst_sid = max(worst_sid, d)
    p3 = worst_sid < 2.0
    ok &= p3
    print(f"[{'PASS' if p3 else 'FAIL'}] сидерика = тропик − аянамша({ay:.4f}°): "
          f"макс Δ = {worst_sid:.3f}′, порог 2.0′")

    # 4) асцендент: тропический и сидерический в диапазоне, раши определён
    asc_t, _ = ascendant(jd, LAT, LON, sidereal=False, hsys=b"P")
    asc_s, _ = ascendant(jd, LAT, LON, sidereal=True, hsys=b"W")
    RASHI = ["Овен","Телец","Близнецы","Рак","Лев","Дева","Весы","Скорпион",
             "Стрелец","Козерог","Водолей","Рыбы"]
    p4 = 0 <= asc_t < 360 and 0 <= asc_s < 360
    ok &= p4
    print(f"[{'PASS' if p4 else 'FAIL'}] асцендент: тропич={asc_t:.2f}° | "
          f"сидерич={asc_s:.2f}° → Лагна {RASHI[int(asc_s//30)]}")

    print("─" * 64)
    print(f"ИТОГ: {'ВСЕ ВОРОТА ЗЕЛЁНЫЕ ✓' if ok else 'ЕСТЬ КРАСНОЕ ✗ — фундамент не доверенный'}")
    return ok


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(0 if _test() else 1)
    else:
        # быстрый дамп долгот для произвольной UTC-даты: ephem_core.py YYYY-MM-DD HH:MM
        if len(sys.argv) >= 3:
            d = datetime.fromisoformat(f"{sys.argv[1]} {sys.argv[2]}").replace(tzinfo=timezone.utc)
            jd = jd_ut(d)
            for nm, v in longitudes(jd).items():
                print(f"  {nm:16s} {v['lon']:8.3f}°  ({v['speed']:+.3f}°/сут)")
        else:
            print(__doc__)
