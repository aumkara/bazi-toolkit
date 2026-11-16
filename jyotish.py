#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""
jyotish.py — Джйотиш (ведическая астрология). Сидерический зодиак.

Считает: Лагну (асцендент), 9 грах по раши/накшатрам(+пады)/домам, период Вимшоттари
(маха+антар даша) на заданную дату, несколько базовых йог.

КОНВЕНЦИИ (названы явно — школы расходятся):
  • аянамша Лахири (SIDM_LAHIRI);  • дома — знаковые (whole-sign, дом 1 = раши Лагны);
  • даша — Вимшоттари;  • Раху/Кету — СРЕДНИЙ узел (ведическая норма), Кету = Раху+180°.
Другой выбор (Раман/KP-аянамша, Плацидус, истинный узел) даст другой результат.

ВЫВЕРКА:
  • Долготы — сидерические из ephem_core (тождество sid=тропик−аянамша проверено там).
  • Накшатра выводится из долготы Луны; --test проверяет инварианты:
    сумма лет Вимшоттари = 120, 27 накшатр, управители цикличны, Лагна в [0,360).
"""
import sys
from datetime import datetime, timezone, timedelta
import ephem_core as ec

NAK_DEG = 40.0 / 3.0   # 13°20′ = 13.3333°
PADA_DEG = NAK_DEG / 4  # 3°20′

RASHI = [("Овен", "Меша"), ("Телец", "Вришабха"), ("Близнецы", "Митхуна"), ("Рак", "Карка"),
         ("Лев", "Симха"), ("Дева", "Канья"), ("Весы", "Тула"), ("Скорпион", "Вришчика"),
         ("Стрелец", "Дхану"), ("Козерог", "Макара"), ("Водолей", "Кумбха"), ("Рыбы", "Мина")]

NAVAMSA_DEG = 10.0 / 3.0  # 3°20′ — навамша D9: 9 частей знака, 108 на круг

# управители знаков (0=Овен … 11=Рыбы)
SIGN_LORD = ["Марс", "Венера", "Меркурий", "Луна", "Солнце", "Меркурий",
             "Венера", "Марс", "Юпитер", "Сатурн", "Сатурн", "Юпитер"]
# экзальтация / падение / свои знаки граха (индексы раши). Узлы (Раху/Кету) не оцениваем.
EXALT = {"sun": 0, "moon": 1, "mars": 9, "mercury": 5, "jupiter": 3, "venus": 11, "saturn": 6}
DEBIL = {"sun": 6, "moon": 7, "mars": 3, "mercury": 11, "jupiter": 9, "venus": 5, "saturn": 0}
OWN = {"sun": {4}, "moon": {3}, "mars": {0, 7}, "mercury": {2, 5},
       "jupiter": {8, 11}, "venus": {1, 6}, "saturn": {9, 10}}

NAKSHATRAS = ["Ашвини", "Бхарани", "Криттика", "Рохини", "Мригашира", "Ардра", "Пунарвасу",
              "Пушья", "Ашлеша", "Магха", "Пурва Пхалгуни", "Уттара Пхалгуни", "Хаста",
              "Читра", "Свати", "Вишакха", "Анурадха", "Джйештха", "Мула", "Пурва Ашадха",
              "Уттара Ашадха", "Шравана", "Дхаништха", "Шатабхиша", "Пурва Бхадрапада",
              "Уттара Бхадрапада", "Ревати"]

# Вимшоттари: порядок управителей и их годы (сумма = 120)
DASHA_ORDER = ["Кету", "Венера", "Солнце", "Луна", "Марс", "Раху", "Юпитер", "Сатурн", "Меркурий"]
DASHA_YEARS = {"Кету": 7, "Венера": 20, "Солнце": 6, "Луна": 10, "Марс": 7,
               "Раху": 18, "Юпитер": 16, "Сатурн": 19, "Меркурий": 17}
# управитель накшатры = DASHA_ORDER[(idx) % 9]
NAK_LORD = [DASHA_ORDER[i % 9] for i in range(27)]

# грахи: ключ ephem_core + рус(санскр)
GRAHAS = [("sun", "Солнце (Сурья)"), ("moon", "Луна (Чандра)"), ("mars", "Марс (Мангала)"),
          ("mercury", "Меркурий (Будха)"), ("jupiter", "Юпитер (Гуру)"),
          ("venus", "Венера (Шукра)"), ("saturn", "Сатурн (Шани)")]
YEAR_DAYS = 365.2425


def _rashi(lon):
    return int(lon // 30)


def _nakshatra(lon):
    idx = int(lon // NAK_DEG) % 27
    pada = int((lon % NAK_DEG) // PADA_DEG) + 1
    return idx, pada


def _navamsa(lon):
    """Индекс знака навамши (D9), 0=Овен. floor(lon·3/10) устойчив на границах знаков
    (деление на 10/3 там промахивается из-за float) и эквивалентен классическому правилу
    старта: подвижный знак — от себя, фиксированный — 9-й, двойственный — 5-й."""
    return int(lon * 3.0 / 10.0) % 12


def _dignity(key, rashi_idx):
    """Достоинство грахи в знаке: экзальтация / падение / свой знак / нейтрально. Узлы → None."""
    if key not in EXALT:
        return None
    if EXALT[key] == rashi_idx:
        return "экзальтация"
    if DEBIL[key] == rashi_idx:
        return "падение"
    if rashi_idx in OWN[key]:
        return "свой знак"
    return "нейтрально"


def vimshottari(birth_dt, moon_lon, as_of):
    """Маха+антар даша на дату as_of. Возвращает (maha, antar, timeline)."""
    nak = int(moon_lon // NAK_DEG) % 27
    lord = NAK_LORD[nak]
    elapsed = (moon_lon % NAK_DEG) / NAK_DEG
    balance = (1 - elapsed) * DASHA_YEARS[lord]
    start_idx = DASHA_ORDER.index(lord)
    seq, start = [], birth_dt
    for k in range(10):                       # все 9 махадаш жизни (~120 лет); без раннего break — нужен полный таймлайн
        L = DASHA_ORDER[(start_idx + k) % 9]
        dur = balance if k == 0 else DASHA_YEARS[L]
        end = start + timedelta(days=dur * YEAR_DAYS)
        seq.append({"lord": L, "start": start, "end": end, "years": round(dur, 2)})
        start = end
    maha = next((s for s in seq if s["start"] <= as_of < s["end"]), seq[0])
    # антардаша внутри махи
    ao = DASHA_ORDER.index(maha["lord"])
    astart, antar = maha["start"], None
    for k in range(9):
        AL = DASHA_ORDER[(ao + k) % 9]
        adur = DASHA_YEARS[AL] / 120.0 * maha["years"]
        aend = astart + timedelta(days=adur * YEAR_DAYS)
        if astart <= as_of < aend:
            antar = {"lord": AL, "start": astart, "end": aend}
            break
        astart = aend
    return maha, antar, seq


def _yogas(graha_rashi, moon_rashi):
    """Несколько базовых, чётко определённых йог (НЕ исчерпывающе)."""
    found = []
    if graha_rashi.get("sun") == graha_rashi.get("mercury"):
        found.append(("Будха-Адитья", "Солнце и Меркурий в одном знаке — ум, речь, интеллект"))
    if graha_rashi.get("moon") == graha_rashi.get("mars"):
        found.append(("Чандра-Мангала", "Луна и Марс вместе — энергия, предприимчивость, но вспыльчивость"))
    # Гаджакесари: Юпитер в кендре (1/4/7/10) от Луны
    if "jupiter" in graha_rashi and moon_rashi is not None:
        h = (graha_rashi["jupiter"] - moon_rashi) % 12
        if h in (0, 3, 6, 9):
            found.append(("Гаджакесари", "Юпитер в кендре от Луны — мудрость, уважение, благополучие"))
    return found


def build_chart(birth_dt_utc, lat, lon_geo, as_of=None, meta=None):
    if as_of is None:
        # даша «на сейчас»; дата расчёта уходит в JSON полем dasha_as_of.
        # Для детерминизма (тесты, воспроизведение старого чтения) передай as_of явно.
        as_of = datetime.now(timezone.utc)
    jd = ec.jd_ut(birth_dt_utc)
    sid = ec.longitudes(jd, sidereal=True)
    asc, _ = ec.ascendant(jd, lat, lon_geo, sidereal=True, hsys=b"W")
    lagna_rashi = _rashi(asc)

    d9_lagna = _navamsa(asc)
    grahas, graha_rashi = [], {}
    bodies = list(GRAHAS) + [("node_mean", "Раху")]
    for key, ru in bodies:
        gl = sid[key]["lon"]
        ri = _rashi(gl); ni, pada = _nakshatra(gl); d9 = _navamsa(gl)
        house = (ri - lagna_rashi) % 12 + 1
        graha_rashi[key] = ri
        grahas.append({"graha": ru, "lon": round(gl, 3), "rashi": RASHI[ri][0],
                       "rashi_sanskrit": RASHI[ri][1], "nakshatra": NAKSHATRAS[ni],
                       "pada": pada, "nakshatra_lord": NAK_LORD[ni], "house": house,
                       "dignity": _dignity(key, ri),
                       "d9_rashi": RASHI[d9][0], "d9_rashi_sanskrit": RASHI[d9][1],
                       "d9_house": (d9 - d9_lagna) % 12 + 1, "d9_dignity": _dignity(key, d9),
                       "vargottama": d9 == ri,
                       "retrograde": sid[key]["speed"] < 0})
    # Кету = Раху + 180
    ketu_lon = (sid["node_mean"]["lon"] + 180) % 360
    kri = _rashi(ketu_lon); kni, kpada = _nakshatra(ketu_lon); kd9 = _navamsa(ketu_lon)
    graha_rashi["ketu"] = kri
    grahas.append({"graha": "Кету", "lon": round(ketu_lon, 3), "rashi": RASHI[kri][0],
                   "rashi_sanskrit": RASHI[kri][1], "nakshatra": NAKSHATRAS[kni],
                   "pada": kpada, "nakshatra_lord": NAK_LORD[kni],
                   "house": (kri - lagna_rashi) % 12 + 1, "dignity": None,
                   "d9_rashi": RASHI[kd9][0], "d9_rashi_sanskrit": RASHI[kd9][1],
                   "d9_house": (kd9 - d9_lagna) % 12 + 1, "d9_dignity": None,
                   "vargottama": kd9 == kri, "retrograde": True})

    moon_lon = sid["moon"]["lon"]
    mni, mpada = _nakshatra(moon_lon)
    maha, antar, dasha_tl = vimshottari(birth_dt_utc, moon_lon, as_of)
    ayan = round(ec.ayanamsa(jd), 4)

    # «Западный взгляд»: тропические Солнце/Луна/асцендент — мостик к привычному
    # «я Близнецы». Те же тела и тот же момент, другой отсчёт круга (от равноденствия,
    # а не от звёзд) — НЕ отдельная система и НЕ новая информация.
    trop = ec.longitudes(jd, sidereal=False)
    asc_trop, _ = ec.ascendant(jd, lat, lon_geo, sidereal=False, hsys=b"W")

    def _trop_point(tl):
        dis = tl % 30
        return {"lon": round(tl, 3), "sign": RASHI[_rashi(tl)][0],
                "degree_in_sign": round(dis, 2),
                "near_cusp": bool(dis < 1.0 or dis > 29.0)}

    def fmt(d):
        return d.strftime("%Y-%m-%d")
    return {
        "system": "jyotish", "input": meta or {},
        "conventions": "аянамша Лахири; дома знаковые; даша Вимшоттари; Раху — средний узел",
        "ayanamsa": ayan,
        "lagna": {"degree": round(asc, 3), "rashi": RASHI[lagna_rashi][0],
                  "rashi_sanskrit": RASHI[lagna_rashi][1]},
        "moon_nakshatra": {"nakshatra": NAKSHATRAS[mni], "pada": mpada, "lord": NAK_LORD[mni]},
        "grahas": grahas,
        "navamsa": {"lagna_rashi": RASHI[d9_lagna][0], "lagna_sanskrit": RASHI[d9_lagna][1],
                    "lagna_lord": SIGN_LORD[d9_lagna],
                    "note": "D9 (варга-9) — ключевая карта брака/дхармы; d9_house у грах = от навамша-Лагны "
                            "(знаковый счёт). vargottama (тот же знак в D1 и D9) = усиление; d9_dignity "
                            "показывает, крепнет ли граха в варге (падший в D1 → сильный в D9 = смягчение)."},
        "house_lords": [{"house": h + 1, "rashi": RASHI[(lagna_rashi + h) % 12][0],
                         "lord": SIGN_LORD[(lagna_rashi + h) % 12]} for h in range(12)],
        "dasha_as_of": fmt(as_of),
        "maha_dasha": {"lord": maha["lord"], "from": fmt(maha["start"]), "to": fmt(maha["end"])},
        "antar_dasha": ({"lord": antar["lord"], "from": fmt(antar["start"]), "to": fmt(antar["end"])}
                        if antar else None),
        "dasha_timeline": [{"lord": s["lord"], "from": fmt(s["start"]), "to": fmt(s["end"]), "years": s["years"]}
                           for s in dasha_tl],
        "yogas": [{"name": n, "meaning": m} for n, m in _yogas(graha_rashi, graha_rashi.get("moon"))],
        "tropical": {
            "note": "Западный взгляд (тропический зодиак): те же планеты и тот же момент, но круг "
                    "отсчитан от точки весеннего равноденствия, а не от звёзд — поэтому знаки сдвинуты "
                    "на аянамшу относительно остального файла. НЕ отдельная система и НЕ новая "
                    "информация — мостик к привычному «кто я по гороскопу»; при сравнении систем "
                    "голосом не считать. near_cusp=true — точка у самой границы знака.",
            "shift_deg": round(ayan, 2),
            "sun": _trop_point(trop["sun"]["lon"]),
            "moon": _trop_point(trop["moon"]["lon"]),
            "ascendant": _trop_point(asc_trop),
        },
        "note": "Йоги перечислены НЕ исчерпывающе — только несколько базовых, чётко определённых.",
    }


def _test():
    ok = True
    print("jyotish.py --test"); print("─" * 60)

    # 1) инварианты данных
    p1 = (sum(DASHA_YEARS.values()) == 120 and len(NAKSHATRAS) == 27
          and len(RASHI) == 12 and NAK_LORD[0] == "Кету" and NAK_LORD[26] == "Меркурий")
    ok &= p1
    print(f"[{'PASS' if p1 else 'FAIL'}] данные: Σ Вимшоттари = {sum(DASHA_YEARS.values())} (=120), "
          f"27 накшатр, управители цикличны")

    # 2) тест-рождение Москва
    dt = datetime(1990, 3, 3, 12, 0, tzinfo=timezone.utc)
    ch = build_chart(dt, 55.75, 37.62, meta={"birth": "1990-03-03 12:00 UTC", "city": "Москва"})
    p2 = (len(ch["grahas"]) == 9 and 0 <= ch["lagna"]["degree"] < 360
          and all(1 <= g["house"] <= 12 and 1 <= g["pada"] <= 4 for g in ch["grahas"]))
    ok &= p2
    print(f"[{'PASS' if p2 else 'FAIL'}] карта: 9 грах, Лагна в диапазоне, дома 1-12, пады 1-4")

    # 3) накшатра Луны согласована с долготой
    moon = next(g for g in ch["grahas"] if g["graha"].startswith("Луна"))
    exp_idx = int(moon["lon"] // NAK_DEG) % 27
    p3 = ch["moon_nakshatra"]["nakshatra"] == NAKSHATRAS[exp_idx]
    ok &= p3
    print(f"[{'PASS' if p3 else 'FAIL'}] накшатра Луны = {ch['moon_nakshatra']['nakshatra']} "
          f"(пада {ch['moon_nakshatra']['pada']}, управитель {ch['moon_nakshatra']['lord']})")

    print(f"     Лагна: {ch['lagna']['rashi']} ({ch['lagna']['rashi_sanskrit']}) {ch['lagna']['degree']}°  "
          f"| аянамша {ch['ayanamsa']}°")
    print(f"     Маха-даша на {ch['dasha_as_of']}: {ch['maha_dasha']['lord']} "
          f"({ch['maha_dasha']['from']}→{ch['maha_dasha']['to']})"
          + (f", антар {ch['antar_dasha']['lord']}" if ch['antar_dasha'] else ""))
    print(f"     Йоги: {', '.join(y['name'] for y in ch['yogas']) or '—'}")
    print("     Грахи по домам:")
    for g in ch["grahas"]:
        r = " (R)" if g["retrograde"] else ""
        vg = " ВАРГ" if g.get("vargottama") else ""
        print(f"       {g['graha']:18s} {g['rashi']:9s} дом {g['house']:2d}  {g['nakshatra']}-{g['pada']}{r}"
              f"  | D9 {g['d9_rashi']:9s}{vg}")

    # 4) навамша D9 — опорные точки (классическое правило старта зашито в формулу)
    nav_cases = [(0.0, "Овен"), (30.0, "Козерог"), (60.0, "Весы"), (120.0, "Овен"),
                 (270.0, "Козерог"), (330.0, "Рак"), (359.99, "Рыбы")]
    nav_bad = [(d, RASHI[_navamsa(d)][0]) for d, exp in nav_cases if RASHI[_navamsa(d)][0] != exp]
    p4 = not nav_bad
    ok &= p4
    print(f"[{'PASS' if p4 else 'FAIL'}] навамша D9: 0°→Овен, 30°→Козерог, 60°→Весы, 330°→Рак"
          + (f"  ОШИБКИ: {nav_bad}" if nav_bad else ""))

    # 5) дигнити (экзальтация/падение/свой) и обработка узлов
    p5 = (_dignity("jupiter", 9) == "падение" and _dignity("sun", 0) == "экзальтация"
          and _dignity("saturn", 0) == "падение" and _dignity("venus", 1) == "свой знак"
          and _dignity("mercury", 5) == "экзальтация" and _dignity("node_mean", 0) is None)
    ok &= p5
    print(f"[{'PASS' if p5 else 'FAIL'}] дигнити: Юпитер↓Козерог, Сатурн↓Овен, Венера=Телец, узлы→None")

    # 6) D9-поля и управители домов присутствуют и согласованы
    g0 = ch["grahas"][0]
    p6 = (all(k in g0 for k in ("dignity", "d9_rashi", "d9_house", "d9_dignity", "vargottama"))
          and ch["navamsa"]["lagna_rashi"] in [r[0] for r in RASHI]
          and len(ch["house_lords"]) == 12
          and all(1 <= g["d9_house"] <= 12 for g in ch["grahas"]))
    ok &= p6
    print(f"[{'PASS' if p6 else 'FAIL'}] D9 в карте: навамша-Лагна {ch['navamsa']['lagna_rashi']}, "
          f"7-й управитель {ch['house_lords'][6]['lord']} ({ch['house_lords'][6]['rashi']})")

    # 7) западный мостик (tropical): внешний якорь + тождество тропика = сидерика + аянамша
    def _circ(a, b):
        d = abs(a - b) % 360
        return min(d, 360 - d)
    # якорь солнечного положения — любое 6 мая (здесь 1990-05-06 12:00 UTC): Солнце в Тельце по тропику
    ch_a = build_chart(datetime(1990, 5, 6, 12, 0, tzinfo=timezone.utc), 55.75, 37.62, meta={"birth": "1990-05-06 12:00 UTC"})
    tr = ch_a["tropical"]
    sun_sid = next(g for g in ch_a["grahas"] if g["graha"].startswith("Солнце"))["lon"]
    p7 = (tr["sun"]["sign"] == "Телец"  # внешний якорь: 6 мая — Телец в западном зодиаке
          and _circ(tr["sun"]["lon"], sun_sid + ch_a["ayanamsa"]) < 0.01
          and _circ(tr["moon"]["lon"], next(g for g in ch_a["grahas"] if g["graha"].startswith("Луна"))["lon"] + ch_a["ayanamsa"]) < 0.01
          and _circ(tr["ascendant"]["lon"], ch_a["lagna"]["degree"] + ch_a["ayanamsa"]) < 0.01
          and all(isinstance(tr[k]["near_cusp"], bool) for k in ("sun", "moon", "ascendant")))
    ok &= p7
    print(f"[{'PASS' if p7 else 'FAIL'}] западный мостик: Солнце {tr['sun']['sign']} "
          f"{tr['sun']['degree_in_sign']}° (якорь: 6 мая = Телец), сдвиг {tr['shift_deg']}° = аянамша, "
          f"тождество на 3 точках")

    # 8) внешние якоря тропика — Astro-Databank (рейтинг AA, свидетельства о рождении,
    #    позиции опубликованы с минутами; сверено живьём 2026-07-11, все Δ ≤ 0.6′):
    #    Монро 1926-06-01 09:30 PST(−8, поясное) Лос-Анджелес 34n03/118w15;
    #    Эйнштейн 1879-03-14 11:30 LMT(m10e0 → +0:40) Ульм 48n24/10e00 — проверка LMT-ветки.
    #    Допуск 3′ (публикация округлена до минуты). Вход = координаты ADB, не «точные» города.
    anchors = [
        ("Монро", datetime(1926, 6, 1, 17, 30, tzinfo=timezone.utc), 34.05, -118.25,
         {"sun": ("Близнецы", 10 + 27 / 60), "moon": ("Водолей", 19 + 6 / 60),
          "ascendant": ("Лев", 13 + 4 / 60)}),
        ("Эйнштейн", datetime(1879, 3, 14, 10, 50, tzinfo=timezone.utc), 48.4, 10.0,
         {"sun": ("Рыбы", 23 + 30 / 60), "moon": ("Стрелец", 14 + 32 / 60),
          "ascendant": ("Рак", 11 + 39 / 60)}),
    ]
    anchor_bad = []
    for name, adt, alat, alon, exp in anchors:
        atr = build_chart(adt, alat, alon)["tropical"]
        for k, (esign, edeg) in exp.items():
            t = atr[k]
            if t["sign"] != esign or abs(t["degree_in_sign"] - edeg) * 60 > 3:
                anchor_bad.append(f"{name}/{k}: {t['sign']} {t['degree_in_sign']}° ≠ {esign} {edeg:.3f}°")
    p8 = not anchor_bad
    ok &= p8
    print(f"[{'PASS' if p8 else 'FAIL'}] внешние якоря тропика (Astro-Databank AA): Монро + Эйнштейн(LMT), "
          f"6 позиций ≤ 3′" + (f"  ОШИБКИ: {anchor_bad}" if anchor_bad else ""))

    print("─" * 60); print(f"ИТОГ: {'ЗЕЛЁНО ✓' if ok else 'КРАСНОЕ ✗'}")
    return ok


def _cli_tz(args, usage):
    """Оффсет UTC — ОБЯЗАТЕЛЬНЫЙ аргумент: пропавший/незамещённый $OFFSET раньше
    молча давал карту в UTC+0 при exit 0. Мусор/плейсхолдер → stderr + exit 2.
    Формы: «+3», «-5», «+-5», «8.5», «UTC+4»; дробные (Сеул +8.5) законны."""
    cands = [a for a in args if not a.startswith("--")]
    if len(cands) != 1:
        what = ("оффсет UTC не передан" if not cands
                else f"ожидал один оффсет UTC, получил: {' '.join(cands)}")
        sys.stderr.write(f"{usage}\nОШИБКА: {what}\n")
        sys.exit(2)
    try:
        return float(cands[0].upper().replace("UTC", "", 1).replace("+", ""))
    except ValueError:
        sys.stderr.write(f"{usage}\nОШИБКА: не разобрал оффсет UTC из «{cands[0]}» — "
                         "незамещённый плейсхолдер?\n")
        sys.exit(2)


def _cli():
    _USAGE = ("jyotish.py YYYY-MM-DD HH:MM LAT LON ОФФСЕТ [--as-of YYYY-MM-DD] [--json] | "
              "jyotish.py --test   (оффсет UTC обязателен: +3, -5, 8.5, UTC+4)")
    if "--test" in sys.argv:
        sys.exit(0 if _test() else 1)
    elif len(sys.argv) >= 6:
        import json
        argv = sys.argv[1:]
        as_of = None  # дата, «на которую» считается даша; без неё — сегодня (дата уходит в dasha_as_of)
        if "--as-of" in argv:
            i = argv.index("--as-of")
            if i + 1 >= len(argv):
                sys.stderr.write(_USAGE + "\nОШИБКА: --as-of без даты\n")
                sys.exit(2)
            try:
                as_of = datetime.fromisoformat(argv[i + 1]).replace(tzinfo=timezone.utc)
            except ValueError:
                sys.stderr.write(f"{_USAGE}\nОШИБКА: не разобрал --as-of «{argv[i + 1]}»\n")
                sys.exit(2)
            del argv[i:i + 2]
        tz = _cli_tz(argv[4:], _USAGE)
        d = datetime.fromisoformat(f"{argv[0]} {argv[1]}")
        dt_utc = d.replace(tzinfo=timezone(timedelta(hours=tz))).astimezone(timezone.utc)
        ch = build_chart(dt_utc, float(argv[2]), float(argv[3]), as_of=as_of,
                         meta={"birth_local": f"{argv[0]} {argv[1]} UTC{tz:+g}"})
        if "--json" in sys.argv:
            print(json.dumps(ch, ensure_ascii=False, indent=2))
        else:
            print(f"Лагна: {ch['lagna']['rashi']} | Луна: {ch['moon_nakshatra']['nakshatra']}")
            print(f"Маха-даша: {ch['maha_dasha']['lord']} → {ch['antar_dasha']['lord'] if ch['antar_dasha'] else ''}")
            for g in ch["grahas"]:
                print(f"  {g['graha']:18s} {g['rashi']:9s} дом {g['house']}")
    else:
        sys.stderr.write(_USAGE + "\n")
        sys.exit(2)


if __name__ == "__main__":
    import cli_errors
    cli_errors.run(_cli)
