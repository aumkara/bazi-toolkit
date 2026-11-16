#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""verify_vs_dashaflow.py — внешний оракул для jyotish.py: dashaflow (MIT, pyswisseph, Лахири). Issue #17.

Сверяется на батарее случайных рождений: знак и градус Лагны (±0.1°), знак каждой грахи (Солнце…Сатурн,
Раху, Кету), накшатра и пада Луны, владыка текущей махадаши (на дату as-of). Пояса — `Etc/GMT∓N`
(у dashaflow вход — зона IANA; у jyotish.py — оффсет). Узлы: dashaflow — средний Раху (как и мы).

Запуск:  .venv/bin/python verify_vs_dashaflow.py [N=40] [--seed 20261109] [--require]
Зависимость (dashaflow тянет pytz; pyswisseph уже в .venv): pip install dashaflow
"""
import json
import os
import random
import subprocess
import sys
import warnings

DIR = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(DIR, ".venv", "bin", "python")
if not os.path.exists(PY):
    PY = sys.executable

try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import dashaflow
except ImportError:
    if "--require" in sys.argv:
        print("verify_vs_dashaflow: dashaflow не установлен (pip install dashaflow) — оракул обязателен, exit 2")
        sys.exit(2)
    print("verify_vs_dashaflow: dashaflow не установлен — оракул пропущен (pip install dashaflow, чтобы включить)")
    sys.exit(0)

SIGNS = {"Aries": "Овен", "Taurus": "Телец", "Gemini": "Близнецы", "Cancer": "Рак", "Leo": "Лев", "Virgo": "Дева",
         "Libra": "Весы", "Scorpio": "Скорпион", "Sagittarius": "Стрелец", "Capricorn": "Козерог",
         "Aquarius": "Водолей", "Pisces": "Рыбы"}
PLANETS = {"Sun": "Солнце", "Moon": "Луна", "Mars": "Марс", "Mercury": "Меркурий", "Jupiter": "Юпитер",
           "Venus": "Венера", "Saturn": "Сатурн", "Rahu": "Раху", "Ketu": "Кету"}
NAKSH_RU = {  # dashaflow (транслит) → jyotish.py (русский)
    "Ashwini": "Ашвини", "Bharani": "Бхарани", "Krittika": "Криттика", "Rohini": "Рохини", "Mrigashira": "Мригашира",
    "Ardra": "Ардра", "Punarvasu": "Пунарвасу", "Pushya": "Пушья", "Ashlesha": "Ашлеша", "Magha": "Магха",
    "Purva Phalguni": "Пурва Пхалгуни", "Uttara Phalguni": "Уттара Пхалгуни", "Hasta": "Хаста", "Chitra": "Читра",
    "Swati": "Свати", "Vishakha": "Вишакха", "Anuradha": "Анурадха", "Jyeshtha": "Джйештха", "Mula": "Мула",
    "Purva Ashadha": "Пурва Ашадха", "Uttara Ashadha": "Уттара Ашадха", "Shravana": "Шравана", "Dhanishta": "Дхаништха",
    "Shatabhisha": "Шатабхиша", "Purva Bhadrapada": "Пурва Бхадрапада", "Uttara Bhadrapada": "Уттара Бхадрапада",
    "Revati": "Ревати"}
CITIES = [(55.75, 37.62), (59.93, 30.32), (56.84, 60.6), (43.12, 131.9), (40.71, -74.0), (51.51, -0.13), (28.61, 77.21),
          (35.68, 139.69), (-33.87, 151.21), (48.86, 2.35)]


def ours(date, time, lat, lon, off, as_of):
    p = subprocess.run([PY, os.path.join(DIR, "jyotish.py"), date, time, str(lat), str(lon), f"{off:+d}", "--as-of", as_of, "--json"],
                       capture_output=True, text=True, cwd=DIR)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[:200])
    return json.loads(p.stdout)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = int(args[0]) if args else 40
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 20261109
    rnd = random.Random(seed)
    cats = {"Лагна": 0, "градус Лагны": 0, "грахи": 0, "накшатра Луны": 0, "махадаша": 0}
    ex = []
    as_of = "2026-07-01"
    for _ in range(n):
        y, m, d = rnd.randint(1940, 2015), rnd.randint(1, 12), rnd.randint(1, 28)
        hh, mm = rnd.randint(0, 23), rnd.choice([0, 15, 30, 45])
        lat, lon = rnd.choice(CITIES)
        off = int(round(lon / 15))
        o = ours(f"{y:04d}-{m:02d}-{d:02d}", f"{hh:02d}:{mm:02d}", lat, lon, off, as_of)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            r = dashaflow.cast_chart(f"{y:04d}-{m:02d}-{d:02d}", f"{hh:02d}:{mm:02d}", lat, lon,
                                     f"Etc/GMT{-off:+d}" if off else "Etc/GMT", query_date=as_of)
        bad = []
        if o["lagna"]["rashi"] != SIGNS[r["lagna"]["sign"]]:
            cats["Лагна"] += 1; bad.append(f"Лагна {o['lagna']['rashi']}≠{r['lagna']['sign']}")
        elif abs((o["lagna"]["degree"] % 30) - r["lagna"]["degree"]) > 0.1:
            cats["градус Лагны"] += 1; bad.append(f"градус Лагны {o['lagna']['degree'] % 30:.2f}≠{r['lagna']['degree']:.2f}")
        og = {g["graha"].split(" (")[0]: g for g in o["grahas"]}
        for en, ru in PLANETS.items():
            tp = r["planets"].get(en)
            if not tp or ru not in og:
                continue
            if og[ru]["rashi"] != SIGNS[tp["sign"]]:
                cats["грахи"] += 1; bad.append(f"{ru} {og[ru]['rashi']}≠{tp['sign']}"); break
        mn = r["planets"]["Moon"]
        if (o["moon_nakshatra"]["nakshatra"], o["moon_nakshatra"]["pada"]) != (NAKSH_RU.get(mn["nakshatra"], mn["nakshatra"]), mn["pada"]):
            cats["накшатра Луны"] += 1; bad.append(f"накшатра {o['moon_nakshatra']}≠{mn['nakshatra']} {mn['pada']}")
        maha_t = PLANETS.get(r["dashas"]["maha"]["planet"], r["dashas"]["maha"]["planet"])
        if o["maha_dasha"]["lord"] != maha_t:
            cats["махадаша"] += 1; bad.append(f"махадаша {o['maha_dasha']['lord']}≠{maha_t}")
        if bad and len(ex) < 8:
            ex.append((f"{y}-{m:02d}-{d:02d} {hh:02d}:{mm:02d} UTC{off:+d} ({lat},{lon})", bad))
    print(f"verify_vs_dashaflow: {n} карт против dashaflow — расхождения: " + ", ".join(f"{k}={v}" for k, v in cats.items()))
    for when, bad in ex if sum(cats.values()) else []:
        print(f"  ✗ {when}: {'; '.join(bad)[:300]}")
    return 1 if sum(cats.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
