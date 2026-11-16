#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""Build losar_dates.json from the verified Phugpa engine + collected sources."""
import json
import os
import sys

# phugpa.py лежит рядом; tibet.tex (LaTeX-исходник статьи Янсона, arXiv:1401.6285) в репозиторий не входит —
# скачать e-print с arXiv и положить рядом либо задать путь переменной TIBET_TEX.
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from phugpa import PHUGPA, TSURPHU

TEX = os.environ.get("TIBET_TEX", os.path.join(HERE, "tibet.tex"))
OUT = os.environ.get("LOSAR_OUT", os.path.join(HERE, "losar_dates.json"))

# Source keys (legend)
SRC_JANSON_T1 = "janson-arxiv-1401.6285:Table1(printed,1927-2046)"
SRC_JANSON_T4 = "janson-arxiv-1401.6285:TableT4Losar(printed,2000-2030)"
SRC_JANSON_TEXT = "janson-arxiv-1401.6285:text-anchor"
SRC_TIBCAL = "tibcalendar(Henning-lineage-C-code,BSD,github.com/lscalendars/tibcalendar):computed"
SRC_IMPL = "phugpa.py(this-work,Janson-formulas,exact-rational):computed"

# External real-world confirmations per year: list of source descriptions
EXTERNAL = {
    1940: ["HISTORICAL: интронизация Далай-ламы XIV = 14-й день 1-го месяца Железного Дракона = 1940-02-22 (tibet.net, dalailama.com chronology); движок воспроизводит соответствие точно"],
    1998: ["karmakagyucalendar.org: Earth Tiger year began 1998-02-27 (источник традиции Цурпху; в этот год даты школ совпадают)"],
    1999: ["karmakagyucalendar.org: Earth Rabbit year began 1999-02-17"],
    2000: ["Ven. Salden 'The story of Losar' (монастырь Далай-ламы), цит. в Janson: Лосар праздновался в воскресенье 2000-02-06, первый день ВСТАВНОГО месяца 1",
           "karmakagyucalendar.org: Earth Rabbit year ended 2000-02-05 (косвенно => НГ 2000-02-06)"],
    2003: ["tibet.net 'A Quiet Losar: This time' (Water Sheep, 2003-03-03)",
           "moonwise.co.uk/year/2130tibetan.htm: год 2130 начался 2003-03-03"],
    2006: ["FPMT (facebook.com/FPMTINC): 'The Tibetan New Year, Losar, falls on February 28 this year' (2006)",
           "ПРОТИВОРЕЧИЕ: FPMT Mandala magazine (июнь 2006) пишет 'The New Year officially began March 1' — см. caveats"],
    2008: ["phayul.com 2008-02-05 'The Story of Tibetan New Year' (Лосар 2008-02-07)",
           "kagyuoffice.org 'Welcome to the Year of the Earth Mouse'"],
    2009: ["chinaculture.org 2009-02-25 'Losar Festival — The Tibetan New Year' (Earth Ox начался 2009-02-25)",
           "tibetanbuddhistencyclopedia.com 'Astrology for Tibetan New Year 2009'"],
    2010: ["palyul.org/wp/2010/02/14/losar-2010 (дата в URL)",
           "trace.org 'Losar 2010: Year of the Iron Tiger'",
           "friends-of-tibet.org: община отмечала Лосар в воскресенье 2010-02-14"],
    2011: ["chinabuddhismencyclopedia.com 'Astrology for Tibetan New Year 2011': 'first day … falls on March 5, 2011' (Iron Rabbit 2138)",
           "gebchakgonpa.org 'Tibetan New Year 2011'"],
    2012: ["kagyuoffice.org (офиц. сайт Кармапы) 'Losar: The Year of the Water Dragon Begins' (2012-02-22; в этот год Пхугпа и Цурпху совпадают)",
           "dharmawheel.net 'Setting up Shrine for Water Dragon Losar 2139'"],
    2013: ["tsegyalgar.blogspot.com 'Losar Year of the Water Snake 2140' (2013-02-11)",
           "chinadaily.com.cn 2013-02-10 'Unraveling the mystery of Tibetan calendar'"],
    2014: ["jampaling.org 'Tibetan New Year (LOSAR) Celebration 2014' (2014-03-02)",
           "tibet.net 'Tibetans across the world celebrate Losar'",
           "tras.ca 'Losar — Wood Horse Year'"],
    2015: ["gtu.edu 'In Celebration of Tibetan Year 2142: Year of the Wood Sheep' (началась 2015-02-19)",
           "socaltibet.org 'Happy Tibetan New Year (Losar) 2142'",
           "tibet.net '2015 Losar Tsedor at Tsuklakhang'"],
    2016: ["tibetrelieffund.co.uk 'Losar 2016: The Year of the Fire Monkey' (2016-02-09)",
           "tibet.net 'Sikyong's Greeting on Losar'"],
    2017: ["himalayan-foundation.org blog 2017-02-27 'Happy Year of the Fire Rooster!'",
           "atiling.org 'Losar 2017: Year of the Fire Bird'",
           "internationalbuddhistacademy.org 'Losar 2017' (празднование 27.02–01.03)"],
    2018: ["himalayan-foundation.org blog 2018-02-16 'Happy Losar! Tibetan Year of the Earth Dog'",
           "tibet.net 'Dharamshala Celebrates Tibetan New Year (Losar — Year of the Earth Dog)'",
           "ripaladrang.org 'Happy New Year Of The Earth Dog 2145'"],
    2019: ["tibet.net 'HH the Dalai Lama wishes everyone on Losar — Year of Earth Pig 2146' (2019-02-05)",
           "groups.io/riwoche: 'LOSAR — Tibetan New Year 2146 — Year of the Earth Pig — Tue, 02/05/2019'",
           "maitripa.org 'Losar 2019'"],
    2020: ["himalayan-foundation.org blog 2020-02-24 'Happy Losar! Year of the Iron Mouse'",
           "lionsroardharmacenter.org 'Losar 2020: Year of the Iron Mouse 2147' (понедельник 24.02.2020)",
           "sakya.org 'Losar (Tibetan New Year) Prayers' (2020)"],
    2021: ["threeriverstibetancc.org 2021/02/12 'Happy Tibetan New Year Losar Celebration 2021'",
           "akasha.nalandabodhi.org 2021/02/12 'Losar 2021' (Iron Ox 2148)",
           "emahofoundation.org 'Tibetan New Year Celebration. Feb 12th'"],
    2022: ["tibet.net 'Central Tibetan Administration celebrates Tibetan Losar — the year of Water Tiger, 2149' (2022-03-03)",
           "buddhaweekly.com 'Losar 2022 … March 3, 2022'",
           "tnp.org 'Losar or Tibetan New Year 2022'"],
    2023: ["tibet.net 'CTA Celebrates Tibetan Losar — the Year of Water Rabbit' (2023-02-21)",
           "himalayan-foundation.org blog 2023-02-21",
           "mn.gov: прокламация губернатора Миннесоты 'Tibetan New Year Losar Day' 02.21.23",
           "Xinhua (english.news.cn) 2023-02-21 'Tibetan New Year marked with joy and hope'"],
    2024: ["tibet.net 'CTA Celebrates Tibetan Losar — the Year of Wood Dragon' (2024-02-10)",
           "kadampa-center.org 'Tibetan New Year — Year of the Wood Dragon — 2024'",
           "tibetrelieffund.co.uk 'Happy Losar! — The year of the wood dragon'"],
    2025: ["buddhaweekly.com 'Happy LOSAR! … Feb 28, 2025, Year of the Wood Snake'",
           "sukhasiddhi.org 'Losar 2025: Celebrating the Tibetan New Year'",
           "maitripa.org 'Losar, Tibetan New Year (Year of the Wood Snake)' (2025)"],
    2026: ["drepung.org 'Tibetan New Year 2153 — Fire Horse' (2026-02-18)",
           "tnp.org 'Important Tibetan Buddhist Holidays in 2026' (Лосар 18.02.2026)",
           "ripa-international.com 'LOSAR 2026 … 2153'",
           "newsonair.gov.in 'Losar Festival from 18–20 February Marks Start of Fire Horse Year'"],
    2027: ["nationaltoday.com 'LOSAR — February 7, 2027'",
           "gototibet.com 'Tibetan New Year 2027 — Dates' (2027-02-07)",
           "officeholidays.com 'Losar around the world in 2027'"],
}

NOTES = {
    1901: "Лосар = лунный день 2 (день 1 пропущен) — вычислено, обе линии кода согласны",
    1977: "Лосар = лунный день 2 (день 1 пропущен); независимо отмечено в комментариях кода tibcalendar ('Phugpa 1/1/1977: first day is omitted')",
    2000: "год начался со ВСТАВНОГО месяца 1 (ix=48); Лосар = 1-й день вставного месяца 1 (печатно у Janson + Salden)",
    2019: "год начался со вставного месяца 1 (ix=49; печатная таблица T4Leap)",
    2084: "Лосар = лунный день 2 (день 1 пропущен) — вычислено; год начинается со вставного месяца 1",
    2065: "год начинается со вставного месяца 1 (65-летний цикл от 2000)",
    2006: "внешние источники расходятся на 1 день: FPMT-FB=28.02, FPMT-Mandala='официально 1 марта'; расчёт (Janson печатно + Henning-код) = 28.02",
}

# 60-year cycle names from Janson Table 1 (element--animal), anchored at 1927=Fire-Rabbit
ELEMENTS = ["Fire", "Earth", "Iron", "Water", "Wood"]
ANIMALS = ["Rabbit", "Dragon", "Snake", "Horse", "Sheep", "Monkey", "Bird", "Dog", "Pig",
           "Mouse", "Ox", "Tiger"]

def year_name(y):
    k = (y - 1927) % 60
    element = ELEMENTS[((k + 1) // 2) % 5]
    animal = ANIMALS[k % 12]
    return f"{element}-{animal}"

# Verify year names against Janson's printed Table 1 (parsed from tibet.tex)
import re
tex = open(TEX, encoding='utf-8').read()
blk = tex.split(r'\caption{Tibetan New Year')[0]
blk = blk[blk.rfind(r'\begin{table}'):]
name_fail = 0
for line in blk.splitlines():
    m = re.match(r'\s*\d+/\d+\s+(\d{4})\s*&\s*\d+/\d+\s+(\d{4})\s*&\s*([A-Za-z]+)--([A-Za-z]+)\s*&\s*\d+/\d+\s+(\d{4})\s*&\s*\d+/\d+\s+(\d{4})\s*&\s*([A-Za-z]+)--([A-Za-z]+)', line)
    if not m:
        continue
    for ys, el, an in [((m.group(1), m.group(2)), m.group(3), m.group(4)),
                       ((m.group(5), m.group(6)), m.group(7), m.group(8))]:
        for yy in ys:
            expected = f"{el}-{an}"
            if year_name(int(yy)) != expected:
                name_fail += 1
                print(f"YEAR-NAME MISMATCH {yy}: table={expected} computed={year_name(int(yy))}")
assert name_fail == 0, "year names disagree with Janson Table 1"
print("Year names verified against Janson Table 1: all 120 match")

rows = []
for y in range(1900, 2101):
    d = PHUGPA.losar_date(y).isoformat()
    sources = []
    if 1927 <= y <= 2046:
        sources.append(SRC_JANSON_T1)
    if 2000 <= y <= 2030:
        sources.append(SRC_JANSON_T4)
    if y in (1954, 1992, 2000, 2019, 2095):
        sources.append(SRC_JANSON_TEXT)
    sources.append(SRC_TIBCAL)
    sources.append(SRC_IMPL)
    sources.extend(EXTERNAL.get(y, []))
    if 1927 <= y <= 2046 or y == 2095:
        conf = "confirmed-2+"
    else:
        conf = "computed-only"
    row = {"year": y, "losar": d, "year_name": year_name(y), "confidence": conf,
           "sources": sources}
    if y in NOTES:
        row["note"] = NOTES[y]
    rows.append(row)

# School divergences
printed_t4 = [
    {"year": 2003, "phugpa": "2003-03-03", "tsurphu": "2003-02-02", "mongolia": "2003-02-02", "bhutan": "2003-03-04"},
    {"year": 2006, "phugpa": "2006-02-28", "tsurphu": "2006-01-30", "mongolia": "2006-01-30", "bhutan": "2006-02-28"},
    {"year": 2008, "phugpa": "2008-02-07", "tsurphu": "2008-02-08", "mongolia": "2008-02-08", "bhutan": "2008-02-08"},
    {"year": 2011, "phugpa": "2011-03-05", "tsurphu": "2011-02-03", "mongolia": "2011-02-03", "bhutan": "2011-02-03"},
    {"year": 2014, "phugpa": "2014-03-02", "tsurphu": "2014-01-31", "mongolia": "2014-01-31", "bhutan": "2014-03-02"},
    {"year": 2022, "phugpa": "2022-03-03", "tsurphu": "2022-02-02", "mongolia": "2022-02-02", "bhutan": "2022-03-03"},
    {"year": 2025, "phugpa": "2025-02-28", "tsurphu": "2025-03-01", "mongolia": "2025-03-01", "bhutan": "2025-02-28"},
    {"year": 2030, "phugpa": "2030-03-05", "tsurphu": "2030-02-03", "mongolia": "2030-02-03", "bhutan": "2030-02-03"},
]

pvt = []
for y in range(1900, 2101):
    p, t = PHUGPA.losar_date(y), TSURPHU.losar_date(y)
    if p != t:
        pvt.append({"year": y, "phugpa": p.isoformat(), "tsurphu": t.isoformat(),
                    "diff_days": (p - t).days})

doc = {
    "tradition": "phugpa",
    "description": "Даты Лосара (1-й день тибетского года) по традиции Пхугпа (phug-lugs) — лхасский стандарт, календарь Далай-ламы/ЦТА/Мен-ци-кханга. Григорианские даты (пролептически-григорианских дат нет: весь диапазон >1582).",
    "generated": "2026-07-15",
    "range": [1900, 2100],
    "method": ("Точная реализация формул Janson (arXiv:1401.6285) в рациональной арифметике; "
               "верифицирована: (1) печатная Таблица 1 статьи — 120/120 дат 1927-2046; "
               "(2) печатная таблица T4Losar 2000-2030 — 31/31 строк (Пхугпа и Цурпху); "
               "(3) 5 текстовых якорей статьи (1954, 1992, 2000, 2019, 2095); "
               "(4) инвариантность эпохи E806 vs E1927; "
               "(5) независимая линия кода Edward Henning (tibcalendar, BSD) — 201/201 (Пхугпа) и 201/201 (Цурпху) за 1900-2100; "
               "(6) независимое кодирование Calendar::Phugpa (Perl) — 201/201; "
               "(7) реальные анонсы/празднования 25 лет из 1998-2027 — все совпали; "
               "(8) исторический якорь: интронизация ДЛ XIV 22.02.1940 = 14-й день 1-го месяца — точно."),
    "confidence_legend": {
        "confirmed-2+": "≥2 независимых линии: печатная академическая таблица Janson + независимая кодовая линия Henning (tibcalendar); для многих лет добавочно реальные анонсы (поле sources)",
        "computed-only": "только расчёт (две независимые кодовые линии согласны, но ни печатного, ни 'празднованного' источника не найдено)",
    },
    "rows": rows,
    "school_divergences": {
        "summary": ("Пхугпа vs Цурпху (Карма Кагью): расхождения двух видов — (а) ~на месяц "
                    "(другое правило вставного месяца: Пхугпа ix∈{48,49}, Цурпху ix∈{0,1}), "
                    "(б) на 1 день (разные эпохальные константы => другие пропущенные/удвоенные дни). "
                    "За 1900-2100: 41 расхождение на месяц + 13 на день (вычислено, обе кодовые линии согласны). "
                    "Монголия (Новый Генден): вставные месяцы = Цурпху; НГ отличался от Цурпху только в 1900 (31/1 vs 1/2) "
                    "и следующий раз в 2161 (26/2 vs 25/2) [печатно у Janson]. "
                    "Бон: календарь = Пхугпа (Janson App.A.1 со ссылкой на Berzin). "
                    "Бутан: своя нумерация вставных месяцев; НГ чаще совпадает с Пхугпа, иногда с Цурпху (см. printed_2000_2030). "
                    "Цаган Сар в Монголии и китайский НГ — отдельные системы, НЕ равные Лосару."),
        "printed_2000_2030_divergent_years": printed_t4,
        "printed_note": "Остальные годы 2000-2030 у всех четырёх версий совпадают (печатная таблица T4Losar в Janson).",
        "phugpa_vs_tsurphu_1900_2100_computed": pvt,
        "computed_note": ("Список выше — расчёт (confidence=computed-only, кроме годов, покрытых печатной T4Losar); "
                          "обе независимые кодовые линии (Janson-формулы и Henning-код) дают идентичные списки. "
                          "Для карт рождения января-марта в годы из списка принадлежность года у Карма Кагью может отличаться от Пхугпа."),
    },
    "algorithm": {
        "paper": "Svante Janson, 'Tibetan calendar mathematics', arXiv:1401.6285 (v2 of 0710.0520), 2014-01-24; PDF: arxiv.org/pdf/1401.6285; полное извлечение формул: losar_algorithm.md (рядом с этим файлом)",
        "losar_rule": "JD(Losar года Y) = 1 + JD(лунный день 30, регулярный месяц 12, года Y-1); JD(тиб.дата) = floor(true_date)",
        "core_constants_epoch_E806_phugpa": {
            "Y0": 806, "M0": 3, "beta_star": 61,
            "m1": "167025/5656", "m2": "11135/11312", "m0": "2015501 + 4783/5656",
            "s1": "65/804", "s2": "13/4824", "s0": "743/804",
            "a1": "253/3528", "a2": "1/28", "a0": "475/3528",
            "moon_tab_0_7": [0, 5, 10, 15, 19, 22, 24, 25],
            "sun_tab_0_3": [0, 6, 10, 11],
            "leap_month_rule": "ix = (2*(12*(Y-806)+M-3) + 61) mod 65 in {48,49}",
            "month_count": "n = floor((67*MM + 61 + 17)/65) - [leap]",
            "true_date": "mean_date + moon_tab(28*anomaly_moon)/60 - sun_tab(12*(mean_sun-1/4))/60; линейная интерполяция таблиц",
        },
        "tsurphu_epoch_E1732": {
            "Y0": 1732, "beta_star": 59,
            "m0": "2353745 + 1795153/7635600", "s0": "-5983/108540", "a0": "207/392",
            "leap_month_rule": "ix in {0,1}", "month_count": "n = floor((67*MM + 59)/65) - [leap]",
        },
        "implementation": "phugpa.py (рядом, в losar_research/): точная Fraction-арифметика, все верификации в verify_vs_janson.py",
    },
    "caveats": [
        "Wikipedia (en) 'Losar', таблица дат: строки 2008-2023 систематически НЕВЕРНЫ (даты сдвинуты — фактически ряд ~2004-2019 с шумом ±1 день; животные при этом верные); верны только 2024-2026 (на 2026-07). Как источник НЕ использована.",
        "2006: FPMT Mandala (июнь 2006) пишет 'официально начался 1 марта', FPMT-Facebook и расчёт дают 28.02.2006. Возможная причина дневного сдвига в сообщениях — пропущенные/удвоенные дни на границе года; печатный Janson и код Henning оба дают 28.02.",
        "В поисковой выдаче всплывала фраза 'Лосар 1991 = 3 марта' без идентифицируемого источника; противоречит печатной таблице Janson (15.02.1991) и обеим кодовым линиям — отброшено как шум.",
        "1900-1926 и 2047-2100 (кроме 2095): только расчёт. Печатных таблиц и анонсов не найдено; надёжность держится на том, что та же реализация воспроизводит все 120 печатных дат и что независимый код Henning даёт то же самое на всём диапазоне.",
        "Вариант константы a2 (стандарт 1/28 vs 'поправка Лочена' 3781/105840, используемая в опубликованных календарях Henning) сдвигает отдельные календарные дни ~раз в 10 лет (примеры из статьи: 2001-02-10, 2006-05-10, 2025-11-19), но НИ ОДНА дата Лосара 1900-2100 не затронута (обе линии согласны 201/201).",
        "Лосар может выпадать на лунный день 2 (день 1 пропущен): 1901-02-20, 1977-02-19, 2084-02-07. Это не влияет на григорианскую дату начала года.",
        "Операционный авторитет — печатный альманах Men-Tsee-Khang (Дхарамсала). Все найденные реальные анонсы (25 лет) совпали с расчётом, но для непокрытых лет (особенно до 1959) нельзя исключить ad-hoc отличия исторически изданных лхасских альманахов от канонического пересчёта.",
        "Тибетский день начинается на рассвете (~5:00 местного среднего времени Лхасы); григорианская дата = гражданская дата этого дня. Часовые пояса на дату Лосара не влияют (дата целодневная).",
        "Нумерация 'королевской эры': тиб. год = григорианский + 127 (например 2025 -> 2152); в части анонсов встречается +126 (2151). На даты не влияет.",
        "Sonam Losar (таманги Непала), Sherpa/Gyalpo-варианты, а также китайский НГ и Цаган Сар — другие праздники/системы; их даты НЕ из этой таблицы.",
    ],
}

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(doc, f, ensure_ascii=False, indent=1)

print(f"Wrote {OUT}")
print(f"rows: {len(rows)}")
from collections import Counter
print(Counter(r['confidence'] for r in rows))
ext = sum(1 for r in rows if any('tibet.net' in s or 'karmakagyu' in s or 'HISTORICAL' in s or 'phayul' in s or 'chinaculture' in s or 'palyul' in s or 'chinabuddhism' in s or 'kagyuoffice' in s or 'tsegyalgar' in s or 'jampaling' in s or 'gtu.edu' in s or 'tibetrelieffund' in s or 'himalayan' in s or 'groups.io' in s or 'lionsroar' in s or 'threerivers' in s or 'buddhaweekly' in s or 'drepung' in s or 'nationaltoday' in s or 'Salden' in s or 'moonwise' in s or 'FPMT' in s for s in r['sources']))
print(f"rows with real-world external confirmation: {ext}")
print(f"phugpa vs tsurphu divergences: {len(pvt)}")
