#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""
Полный калькулятор Ба Цзы (八字) — Четыре Столпа Судьбы.
Включает: 4 столпа, скрытые стволы, 10 божеств, сила ХД, 空亡,
Шэнь Ша, баланс стихий, столпы удачи, годовой анализ.

Использование:
    python3 bazi.py 1990-05-15 14:30 М --city Москва --json   # город: исторический пояс + истинное солнечное время
    python3 bazi.py 1990-05-15 14:30 М UTC+8                  # города нет в базе — явный пояс
    python3 bazi.py 1985-12-03 Ж UTC+3                        # без времени (три столпа); пояс всё равно обязателен
    python3 bazi.py 2000-01-28 08:00 М UTC+3
    python3 bazi.py 1990-05-15 14:30 М UTC+3 --as-of 2027-03-01   # прогнозный год/удача на дату
    python3 bazi.py 1990-05-15 23:30 М UTC+4 --late-zi-hour-stem same_day   # 夜子时: ствол часа как до 2026-11-09
    python3 bazi.py 1990-05-15 14:30 М UTC+4 --tianyi huma --yangren-yin none --shensha-base year   # школы Шэнь Ша
    python3 bazi.py --test                   # запуск тестов
    python3 bazi.py --help                   # эта справка
"""
import sys, math, json, os
from datetime import datetime, timedelta, timezone
from ephemeris import sun_lon, julian_day, jd_to_datetime as jd_to_dt, find_solar_term as find_term  # λ☉ — только Swiss Ephemeris

# ═══════════════════════════════════════════════════════════════════════════
# СПРАВОЧНЫЕ ДАННЫЕ
# ═══════════════════════════════════════════════════════════════════════════

STEMS = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
BRANCHES = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]
ANIMALS = ["Крыса","Бык","Тигр","Кролик","Дракон","Змея",
           "Лошадь","Коза","Обезьяна","Петух","Собака","Свинья"]
ELEMENTS_RU = ["Дерево","Огонь","Земля","Металл","Вода"]
STEM_ELEMENT = [0,0,1,1,2,2,3,3,4,4]  # 0=Wood..4=Water
STEM_POLARITY = [1,0,1,0,1,0,1,0,1,0] # 1=Yang, 0=Yin
BRANCH_ELEMENT = [4,2,0,0,2,1,1,2,3,3,2,4]

# Скрытые стволы: [本气, 中气, 余气] (индексы стволов, -1 = нет)
HIDDEN_STEMS = [
    [9,-1,-1],    # 子: 癸
    [5, 7, 9],    # 丑: 己辛癸
    [0, 2, 4],    # 寅: 甲丙戊
    [1,-1,-1],    # 卯: 乙
    [4, 9, 1],    # 辰: 戊癸乙
    [2, 6, 4],    # 巳: 丙庚戊
    [3, 5,-1],    # 午: 丁己
    [5, 3, 1],    # 未: 己丁乙
    [6, 8, 4],    # 申: 庚壬戊
    [7,-1,-1],    # 酉: 辛
    [4, 7, 3],    # 戌: 戊辛丁
    [8, 0,-1],    # 亥: 壬甲
]

# На Инь (纳音): индекс = (sexagenary_pos - 1) // 2
NAYIN = [
    "海中金","炉中火","大林木","路旁土","剑锋金","山头火",
    "涧下水","城头土","白蜡金","杨柳木","泉中水","屋上土",
    "霹雳火","松柏木","长流水","沙中金","山下火","平地木",
    "壁上土","金箔金","覆灯火","天河水","大驿土","钗钏金",
    "桑柘木","大溪水","沙中土","天上火","石榴木","大海水",
]
NAYIN_ELEMENT = [3,1,0,2,3,1,4,2,3,0,4,2,1,0,4,3,1,0,2,3,1,4,2,3,0,4,2,1,0,4]

# 十神 (Ten Gods) names
TEN_GODS = ["比肩","劫财","食神","伤官","偏财","正财","七杀","正官","偏印","正印"]
TEN_GODS_RU = ["Друг","Грабитель Богатства","Бог Пищи","Ранящий Чиновник",
               "Косвенное Богатство","Прямое Богатство","Семь Убийств",
               "Прямой Чиновник","Косвенная Печать","Прямая Печать"]

# Продуктивный цикл: produces[i] = element produced by i
PRODUCES = [1, 2, 3, 4, 0]  # Wood→Fire→Earth→Metal→Water→Wood
# Контрольный цикл: controls[i] = element controlled by i
CONTROLS = [2, 3, 4, 0, 1]  # Wood→Earth, Fire→Metal, Earth→Water, Metal→Wood, Water→Fire

# 调候用神 (климатический регулятор): TIAOHOU[dm_stem_idx][month_branch_idx] = (主 ствол, 辅 ствол)
# Источник: tiaohou.md (《穷通宝鉴》, адаптация Сюй Лэ У / Чжун И Мин). Сгенерировано парсером, 120 ячеек.
# Это ОТДЕЛЬНАЯ от 旺衰 школа (温寒燥湿 — климат), не путать с 用神 по силе.
TIAOHOU = {
    0: {0: (2, 6), 1: (2, 3), 2: (2, 9), 3: (2, 9), 4: (8, 6), 5: (9, 3), 6: (9, 3), 7: (9, 3), 8: (6, 3), 9: (3, 2), 10: (0, 6), 11: (2, 6)},  # 甲
    1: {0: (2, 4), 1: (2, 4), 2: (2, 9), 3: (2, 9), 4: (9, 2), 5: (9, 2), 6: (9, 2), 7: (9, 2), 8: (2, 9), 9: (2, 9), 10: (9, 2), 11: (2, 4)},  # 乙
    2: {0: (8, 0), 1: (0, 8), 2: (8, 6), 3: (8, 5), 4: (8, 0), 5: (8, 6), 6: (8, 6), 7: (8, 6), 8: (8, 4), 9: (8, 0), 10: (8, 0), 11: (0, 8)},  # 丙
    3: {0: (0, 6), 1: (0, 6), 2: (0, 6), 3: (0, 6), 4: (0, 8), 5: (0, 8), 6: (8, 0), 7: (0, 8), 8: (0, 6), 9: (0, 6), 10: (0, 6), 11: (0, 6)},  # 丁
    4: {0: (2, 0), 1: (2, 0), 2: (2, 0), 3: (2, 0), 4: (2, 0), 5: (8, 0), 6: (8, 0), 7: (9, 2), 8: (2, 9), 9: (2, 9), 10: (0, 8), 11: (2, 0)},  # 戊
    5: {0: (2, 0), 1: (2, 0), 2: (2, 0), 3: (0, 9), 4: (2, 9), 5: (9, 2), 6: (9, 2), 7: (9, 2), 8: (2, 9), 9: (2, 9), 10: (8, 0), 11: (2, 0)},  # 己
    6: {0: (3, 2), 1: (3, 0), 2: (2, 0), 3: (3, 0), 4: (0, 3), 5: (8, 2), 6: (8, 5), 7: (8, 3), 8: (3, 0), 9: (3, 0), 10: (0, 8), 11: (3, 0)},  # 庚
    7: {0: (2, 8), 1: (2, 8), 2: (8, 5), 3: (8, 0), 4: (8, 0), 5: (8, 9), 6: (8, 5), 7: (8, 6), 8: (8, 0), 9: (8, 0), 10: (8, 0), 11: (2, 8)},  # 辛
    8: {0: (2, 4), 1: (2, 0), 2: (2, 4), 3: (4, 7), 4: (0, 6), 5: (8, 7), 6: (9, 8), 7: (7, 0), 8: (4, 3), 9: (0, 2), 10: (0, 2), 11: (2, 4)},  # 壬
    9: {0: (2, 7), 1: (2, 7), 2: (2, 7), 3: (6, 7), 4: (2, 7), 5: (7, 8), 6: (6, 7), 7: (6, 7), 8: (3, 0), 9: (2, 7), 10: (7, 2), 11: (2, 6)},  # 癸
}

def tiaohou_gods(dm_idx, month_bi):
    """调候 (климатический) регулятор по ХД и месяцу. (primary_stem, aux_stem) или None."""
    if month_bi is None:
        return None
    return TIAOHOU.get(dm_idx, {}).get(month_bi)

def analyze_gods(dm, mb, pillars):
    """Единый источник 用神/忌神/调候 — заменяет 3 копии логики (bazi JSON, bazi текст, app.py).
    Чинит самопротиворечие: СРЕДНИЙ ХД больше не сваливается со СЛАБЫМ — разрешается
    по собственному порогу поддержки движка (>50% → к ослаблению) и помечается borderline
    (пограничная сила, выбор 用神 трактуем). Возвращает dict или None."""
    if mb is None:
        return None
    score, label = dm_strength(dm, mb, pillars)
    dm_el = STEM_ELEMENT[dm]
    resource = next(e for e in range(5) if PRODUCES[e] == dm_el)
    strengthen = [dm_el, resource]                  # 比劫 + 印
    weaken = [PRODUCES[dm_el], CONTROLS[dm_el]]      # 食伤 (слив) + 财 (богатство)
    bal = element_balance(pillars)
    total = sum(bal.values()) or 1.0
    support = (bal[dm_el] + bal[resource]) / total
    borderline = False
    if label == "СИЛЬНЫЙ":
        yongshen, jishen, basis = weaken, strengthen, "по силе: ослабить (сильный ХД)"
        if support < 0.5:   # край (issue #12): сила по сезону/корням против стихийного баланса — противоречие
            borderline = True
            basis = (f"сильный по сезону/корням, но стихийная поддержка {support:.0%} < 50% — показания "
                     f"расходятся; ведём по силе (ослабить), альтернативу показать")
    elif label == "СЛАБЫЙ":
        yongshen, jishen, basis = strengthen, weaken, "по силе: усилить (слабый ХД)"
        if support > 0.5:   # зеркальный край (issue #12): слабый ХД при поддержке >50% в балансе стихий
            borderline = True
            basis = (f"слабый по сезону/корням, но стихийная поддержка {support:.0%} > 50% — показания "
                     f"расходятся; ведём по силе (усилить), альтернативу показать")
    else:  # СРЕДНИЙ — пограничный; решаем по порогу поддержки самого движка (см. dm_strength)
        borderline = True
        if support > 0.5:
            yongshen, jishen, basis = weaken, strengthen, "средний, поддержка >50% → ослабить"
        else:
            yongshen, jishen, basis = strengthen, weaken, "средний, поддержка <50% → усилить"
    tiaohou = None
    th = tiaohou_gods(dm, mb)
    if th:
        prim, aux = th
        pe = STEM_ELEMENT[prim]
        tiaohou = {"primary_stem": prim, "primary_el": pe,
                   "aux_stem": aux, "aux_el": STEM_ELEMENT[aux], "aligns": pe in yongshen}
    return {"score": score, "label": label, "support": support,
            "borderline": borderline, "basis": basis,
            "yongshen": yongshen, "jishen": jishen,
            "alt_yongshen": (strengthen if yongshen == weaken else weaken),
            "tiaohou": tiaohou}

# Шэнь Ша: Тянь И Гуй Жэнь (по стволу дня → ветви)
TIANYI = {0:[1,7],1:[8,0],2:[9,11],3:[9,11],4:[1,7],5:[8,0],6:[1,7],7:[2,6],8:[3,5],9:[3,5]}
# Вэнь Чан (по стволу дня → ветвь)
WENCHANG = {0:5,1:6,2:8,3:9,4:8,5:9,6:11,7:0,8:2,9:3}
# Ян Жэнь (по стволу дня → ветвь)
YANGREN = {0:3,1:2,2:6,3:5,4:6,5:5,6:9,7:8,8:0,9:11}
# Лу Шэнь (по стволу дня → ветвь)
LUSHEN = {0:2,1:3,2:5,3:6,4:5,5:6,6:8,7:9,8:11,9:0}
# И Ма (по группе тройной гармонии года/дня → ветвь)
YIMA = {0:2, 1:5, 2:8, 3:11}  # group: 申子辰→寅, 亥卯未→巳, 寅午戌→申, 巳酉丑→亥
# (исправлено 2026-07-01: группы 1/3 были перепутаны — 驿马 = 冲 первой ветви рамки;
#  из-за бага у рождённых в год 巳 «Конь» ложно находился в собственной годовой ветви)
# Тао Хуа
TAOHUA = {0:9, 1:0, 2:3, 3:6}
# Хуа Гай
HUAGAI = {0:4, 1:7, 2:10, 3:1}

# Тройная гармония: ветвь → группа (0=申子辰Water, 1=亥卯未Wood, 2=寅午戌Fire, 3=巳酉丑Metal)
def san_he_group(branch_idx):
    groups = {8:0, 0:0, 4:0,  11:1, 3:1, 7:1,  2:2, 6:2, 10:2,  5:3, 9:3, 1:3}
    return groups.get(branch_idx, 0)

# 六冲 (Six Clashes)
CLASHES = {0:6,6:0, 1:7,7:1, 2:8,8:2, 3:9,9:3, 4:10,10:4, 5:11,11:5}
# 三合 (полные тройные группы) и их стихия: 申子辰=Вода, 亥卯未=Дерево, 寅午戌=Огонь, 巳酉丑=Металл
TRIADS = {0: {8, 0, 4}, 1: {11, 3, 7}, 2: {2, 6, 10}, 3: {5, 9, 1}}
TRIAD_ELEMENT = {0: 4, 1: 0, 2: 1, 3: 3}

# 红鸾 by year branch
HONGLUAN = [3,2,1,0,11,10,9,8,7,6,5,4]
TIANXI_STAR = [9,8,7,6,5,4,3,2,1,0,11,10]

# ═══════════════════════════════════════════════════════════════════════════
# СОЛНЕЧНЫЕ ТЕРМИНЫ (Meeus)
# ═══════════════════════════════════════════════════════════════════════════

SOLAR_TERMS_DATA = [
    (315,1,"寅"),(345,2,"卯"),(15,3,"辰"),(45,4,"巳"),(75,5,"午"),
    (105,6,"未"),(135,7,"申"),(165,8,"酉"),(195,9,"戌"),(225,10,"亥"),
    (255,11,"子"),(285,12,"丑"),
]

# julian_day / jd_to_dt / find_term — из ephemeris.py (единственная копия, issue #11); sun_lon — Swiss Ephemeris.

def get_jie_terms(year):
    results = []
    for lon, mnum, branch in SOLAR_TERMS_DATA:
        jd = find_term(year, lon)
        results.append((jd_to_dt(jd), mnum, branch))
    results.sort(key=lambda x: x[0])
    return results

def get_bazi_month(year, month, day, hour=0, minute=0, tz_off=0):
    from datetime import timezone as tz
    target = datetime(year,month,day,hour,minute,tzinfo=tz(timedelta(hours=tz_off))).astimezone(timezone.utc)
    jie = []
    for y in [year-1, year, year+1]:
        jie.extend(get_jie_terms(y))
    jie.sort(key=lambda x: x[0])
    bm, bb = None, None
    for i in range(len(jie)-1):
        if jie[i][0] <= target < jie[i+1][0]:
            bm, bb = jie[i][1], jie[i][2]; break
    # Год Ба Цзы
    by = year
    lichun = None
    for t in jie:
        if t[1] == 1 and t[0].year == year: lichun = t[0]; break
    if lichun and target < lichun: by = year - 1
    return bm, bb, by

def resolve_forecast_year(as_of_d, tz_off=8):
    """Год Ба Цзы, действующий на дату as_of_d: граница — момент ЛИЧУНЯ (立春), не 1 января.
    Без этого резолва окно 1 января → Личунь (~5 недель ежегодно) получало неверный 流年.
    Сравнение — полудень as_of_d в поясе tz_off против момента Личуня (UTC); сам день Личуня
    помечается отдельно (год сменяется внутри дня). Возвращает (год, словарь-обоснование)."""
    from datetime import timezone as tz
    y = as_of_d.year
    lichun = next((t[0] for t in get_jie_terms(y) if t[1] == 1 and t[0].year == y), None)
    boundary = {"as_of": as_of_d.isoformat(),
                "lichun_utc": lichun.strftime("%Y-%m-%d %H:%M") if lichun else None,
                "rule": "граница года Ба Цзы — момент Личуня (立春), не 1 января"}
    if lichun is None:  # страховка: эфемериды обязательны, но лгать молча нельзя
        boundary["basis"] = f"Личунь {y} не вычислен — взят календарный год (проверь эфемериды)"
        return y, boundary
    noon_utc = datetime(as_of_d.year, as_of_d.month, as_of_d.day, 12, 0,
                        tzinfo=tz(timedelta(hours=tz_off))).astimezone(tz.utc)
    if noon_utc < lichun:
        y -= 1
        boundary["basis"] = f"дата до Личуня ({boundary['lichun_utc']} UTC) → год Ба Цзы ещё {y}"
    else:
        boundary["basis"] = f"дата после Личуня ({boundary['lichun_utc']} UTC) → год Ба Цзы {y}"
    if as_of_d == (lichun + timedelta(hours=tz_off)).date():
        boundary["basis"] += ("; это САМ ДЕНЬ Личуня — год сменяется в течение дня "
                              "(сравнение по полудню пояса рождения)")
    return y, boundary

def boundary_warnings(year, month, day, hour, minute, tz_off):
    """Флаги чувствительности столпов к погрешности времени/даты рождения.
    Окна эвристические (отражают типичную неточность записи времени), не астрономические.
    Возвращает список {pillar, severity, detail}."""
    warns = []
    hh, mi = (hour, minute) if hour is not None else (12, 0)

    # ── 时辰: границы 2-часовой ветви на нечётных часах (+ 23:00) ──
    if hour is not None:
        tmin = hh * 60 + mi
        bounds = [23 * 60] + [h * 60 for h in range(1, 23, 2)]  # 23:00,01:00,...,21:00
        best = min(min((tmin - b) % 1440, (b - tmin) % 1440) for b in bounds)
        if best <= 15:
            warns.append({"pillar": "hour", "severity": "high" if best <= 5 else "medium",
                          "detail": f"{best} мин до границы 时辰 — часовой столп (ствол+ветвь) сменится при сдвиге времени"})
        if hh == 23:
            warns.append({"pillar": "day", "severity": "medium",
                          "detail": "夜子时 (23:00–23:59): здесь день остаётся текущим, ствол часа — от следующего дня "
                                    "(conventions.late_zi_*); школа «смена суток в 23:00» даст столп ДНЯ следующих суток — "
                                    "покажи обе версии, меняется сам Хозяин Дня"})
        elif hh == 0:
            warns.append({"pillar": "day", "severity": "medium",
                          "detail": "早子时 (00:00–00:59): столп дня — текущие сутки у обеих школ; ветвь часа 子"})
    else:
        warns.append({"pillar": "hour", "severity": "info",
                      "detail": "Время не указано — часовой столп пропущен; проверки месяца/года по полудню"})

    # ── 节气 (граница месяца) и 立春 (граница года) ──
    target = datetime(year, month, day, hh, mi,
                      tzinfo=timezone(timedelta(hours=tz_off))).astimezone(timezone.utc)
    jie = []
    for yy in (year - 1, year, year + 1):
        jie.extend(get_jie_terms(yy))
    jie.sort(key=lambda x: x[0])

    nearest = min(jie, key=lambda t: abs((target - t[0]).total_seconds()))
    dh = abs((target - nearest[0]).total_seconds()) / 3600
    if dh <= 24:
        sev = "high" if (dh <= 6 or hour is None) else "medium"
        warns.append({"pillar": "month", "severity": sev,
                      "detail": f"{dh:.1f} ч до смены 节气 ({nearest[2]}-месяц) — месячный столп чувствителен к дате/времени"})

    lichun = next((t for t in jie if t[1] == 1 and
                   abs((target - t[0]).total_seconds()) <= 5 * 86400), None)
    if lichun:
        dl = abs((target - lichun[0]).total_seconds()) / 3600
        if dl <= 48:
            sev = "high" if (dl <= 24 or hour is None) else "medium"
            warns.append({"pillar": "year", "severity": sev,
                          "detail": f"{dl:.1f} ч до 立春 — годовой столп и весь сдвиг 大运 могут смениться. Уточни точную дату/время."})
    return warns

# ═══════════════════════════════════════════════════════════════════════════
# РАСЧЁТ СТОЛПОВ
# ═══════════════════════════════════════════════════════════════════════════

def year_pillar(by):
    return (by+6)%10, (by+8)%12

def month_pillar(ys, mn):
    base = [2,4,6,8,0]
    ms = (base[ys%5] + mn - 1) % 10
    mb = (mn + 1) % 12
    return ms, mb

def day_pillar(y, m, d):
    jdn = int(julian_day(y,m,d,12) + 0.5)
    return (jdn+9)%10, (jdn+1)%12

# ── Конвенции (issue #16/#18): объявлены в JSON (`conventions`), чтобы чтение могло их назвать ──
# 夜子时 (23:00–23:59): столп ДНЯ остаётся текущим (школа «смена суток в полночь»), а ствол 子-часа
# берётся от СЛЕДУЮЩЕГО дня — классическое правило «日柱当天、时柱按次日起», так же считают lunar-python
# и большинство排盘-программ (сверено verify_vs_lunar.py 2026-11-09). До 2026-11-09 ствол брался от
# текущего дня — третий, нестандартный вариант; оставлен как "same_day" для сравнения со старыми чтениями.
LATE_ZI_HOUR_STEM = "next_day"   # "next_day" | "same_day"
CONVENTIONS = {
    "late_zi_day": "same_day",            # 23:00–23:59: столп дня — текущие сутки (смена в полночь)
    "late_zi_hour_stem": LATE_ZI_HOUR_STEM,  # ствол 子-часа для 23:xx — от следующего дня (мейнстрим)
    "year_change": "lichun_exact_moment",    # год Ба Цзы меняется в момент Личуня, не в день
    "month_change": "jie_exact_moment",      # месяц — точный момент 节 (Swiss Ephemeris)
    "hidden_stem_weights": "1.0 | 0.7/0.3 | 0.6/0.3/0.1",
    "yongshen": "旺衰 (сила ХД) + 调候 отдельной осью; СРЕДНИЙ ХД: поддержка >50% → ослаблять; школа 格局 (子平真诠) — вторым голосом в блоке geju (structure, 相神, status, comparison)",
    # три поля ниже перезаписываются из переключателей (issue #18) при сборке JSON — см. conventions_now()
    "shensha_base": None, "tianyi_version": None, "yangren_yin_stems": None,
}

# ── Переключатели Шэнь Ша (issue #18): школы расходятся, калькулятор обязан быть явным ──
TIANYI_VERSION = "niuyang"   # "niuyang" — «甲戊庚牛羊» (庚 → 丑未, 辛 → 午寅) | "huma" — «庚辛逢虎马» (庚辛 → 寅午)
YANGREN_YIN = "diwang"       # "diwang" — 羊刃 инь-ствола в его 帝旺 (乙→寅, 丁己→巳, 辛→申, 癸→亥) | "none" — «阴干无刃»
SHENSHA_BASE = "day+year"    # "day+year" — стволовые (天乙/文昌/羊刃/禄神) от ствола ДНЯ, ветвевые (驿马/桃花/华盖)
                             #   от ветвей года И дня (современная 子平-практика) | "day" — всё только от столпа дня |
                             #   "year" — всё от столпа года (древняя 禄命-школа)
TIANYI_HUMA = {**TIANYI, 6: [2, 6], 7: [2, 6]}   # 庚辛逢虎马

def conventions_now():
    """Блок conventions с учётом переключателей — что именно было использовано в этой карте."""
    c = dict(CONVENTIONS, late_zi_hour_stem=LATE_ZI_HOUR_STEM)
    c["tianyi_version"] = {"niuyang": "甲戊庚牛羊 (庚 → 丑未, 辛 → 午寅)", "huma": "庚辛逢虎马 (庚辛 → 寅午)"}[TIANYI_VERSION]
    c["yangren_yin_stems"] = {"diwang": "есть — 帝旺 инь-ствола (乙→寅, 丁己→巳, 辛→申, 癸→亥)",
                              "none": "нет — школа «阴干无刃» (羊刃 только у ян-стволов)"}[YANGREN_YIN]
    c["shensha_base"] = {"day+year": "天乙/文昌/羊刃/禄神 — от ствола дня; 驿马/桃花/华盖 — от ветвей года и дня; 红鸾/天喜 — от ветви года",
                         "day": "все Шэнь Ша — от столпа дня (天乙/文昌/羊刃/禄神 — ствол дня; 驿马/桃花/华盖 — ветвь дня); 红鸾/天喜 — от ветви года",
                         "year": "все Шэнь Ша — от столпа года (древняя 禄命-школа); 红鸾/天喜 — от ветви года"}[SHENSHA_BASE]
    c["switches"] = {"--late-zi-hour-stem": LATE_ZI_HOUR_STEM, "--tianyi": TIANYI_VERSION, "--yangren-yin": YANGREN_YIN,
                     "--shensha-base": SHENSHA_BASE}
    return c

def hour_pillar(ds, h, late_zi=None):
    """Столп часа. ds — индекс ствола ДНЯ (того, что в столпе дня). Для 23:xx ствол 子-часа
    по умолчанию берётся от следующего дня (см. CONVENTIONS['late_zi_hour_stem'])."""
    late_zi = late_zi or LATE_ZI_HOUR_STEM
    if h == 23:
        bi = 0
        if late_zi == "next_day":
            ds = (ds + 1) % 10
    else:
        bi = ((h+1)//2)%12
    base = [0,2,4,6,8]
    si = (base[ds%5] + bi) % 10
    return si, bi

# ═══════════════════════════════════════════════════════════════════════════
# АНАЛИТИКА
# ═══════════════════════════════════════════════════════════════════════════

def ten_god(dm_idx, other_idx):
    """Десятое Божество другого ствола относительно ХД."""
    dm_el = STEM_ELEMENT[dm_idx]
    ot_el = STEM_ELEMENT[other_idx]
    same_pol = (dm_idx % 2) == (other_idx % 2)
    if dm_el == ot_el: return 0 if same_pol else 1        # 比肩/劫财
    if PRODUCES[dm_el] == ot_el: return 2 if same_pol else 3  # 食神/伤官
    if CONTROLS[dm_el] == ot_el: return 4 if same_pol else 5  # 偏财/正财
    if CONTROLS[ot_el] == dm_el: return 6 if same_pol else 7  # 七杀/正官
    if PRODUCES[ot_el] == dm_el: return 8 if same_pol else 9  # 偏印/正印
    return -1

def element_balance(pillars, hidden=True):
    """Подсчёт стихий в карте. Возвращает {element_idx: weight}."""
    balance = {i: 0.0 for i in range(5)}
    for si, bi in pillars:
        if si is not None:
            balance[STEM_ELEMENT[si]] += 1.0
        if bi is not None:
            hs = HIDDEN_STEMS[bi]
            weights = [0.6, 0.3, 0.1] if hs[2] >= 0 else ([0.7, 0.3] if hs[1] >= 0 else [1.0])
            for j, h in enumerate(hs):
                if h >= 0: balance[STEM_ELEMENT[h]] += weights[j]
    return balance

def dm_strength(dm_idx, month_bi, pillars):
    """Оценка силы Хозяина Дня. Возвращает (score, label)."""
    dm_el = STEM_ELEMENT[dm_idx]
    score = 0
    # Фактор 1: Сезон (~40%)
    mb_el = BRANCH_ELEMENT[month_bi]
    if mb_el == dm_el: score += 40
    elif PRODUCES[mb_el] == dm_el: score += 25
    elif dm_el == PRODUCES[dm_el] and mb_el == dm_el: score += 20
    elif CONTROLS[mb_el] == dm_el: score -= 20
    # Скрытые стволы месяца
    for h in HIDDEN_STEMS[month_bi]:
        if h >= 0 and STEM_ELEMENT[h] == dm_el: score += 10; break
    # Фактор 2: Корни (~30%)
    for si, bi in pillars:
        if bi is not None:
            for h in HIDDEN_STEMS[bi]:
                if h >= 0 and STEM_ELEMENT[h] == dm_el:
                    score += 8; break
    # Фактор 3: Стволы (~20%)
    for si, bi in pillars:
        if si is not None and si != dm_idx:
            el = STEM_ELEMENT[si]
            if el == dm_el: score += 10
            elif PRODUCES[el] == dm_el: score += 7
    # Фактор 4: Баланс
    bal = element_balance(pillars)
    support = bal[dm_el] + bal.get([e for e in range(5) if PRODUCES[e]==dm_el][0], 0)
    total = sum(bal.values())
    if total > 0 and support/total > 0.5: score += 10
    elif total > 0 and support/total < 0.3: score -= 10

    if score >= 40: return score, "СИЛЬНЫЙ"
    elif score <= 0: return score, "СЛАБЫЙ"
    else: return score, "СРЕДНИЙ"

def kong_wang(day_si, day_bi):
    """Пустота (空亡). Возвращает список из 2 индексов пустых ветвей."""
    # Позиция дня в цикле 60
    k = 6*(day_si+1) - 5*(day_bi+1)
    s = k if k > 0 else k + 60
    xun_start = ((s-1)//10)*10
    first_branch = xun_start % 12
    return [(first_branch+10)%12, (first_branch+11)%12]

def find_shensha(dm_si, year_bi, day_bi, all_branches, year_si=None):
    """Найти Шэнь Ша в карте. База и версии таблиц — по переключателям TIANYI_VERSION / YANGREN_YIN /
    SHENSHA_BASE (issue #18); year_si нужен только для SHENSHA_BASE == "year"."""
    found = []
    tianyi = TIANYI_HUMA if TIANYI_VERSION == "huma" else TIANYI
    yangren = YANGREN if YANGREN_YIN == "diwang" else {k: v for k, v in YANGREN.items() if k % 2 == 0}
    base_si = dm_si
    branch_srcs = [year_bi, day_bi]
    if SHENSHA_BASE == "year":
        base_si = dm_si if year_si is None else year_si
        branch_srcs = [year_bi]
    elif SHENSHA_BASE == "day":
        branch_srcs = [day_bi]
    # По стволу (дня — 子平; года — 禄命)
    for bi in all_branches:
        if bi in tianyi.get(base_si, []): found.append(("天乙贵人", BRANCHES[bi], "Небесный Покровитель"))
        if bi == WENCHANG.get(base_si): found.append(("文昌", BRANCHES[bi], "Литературная Звезда"))
        if bi == yangren.get(base_si): found.append(("羊刃", BRANCHES[bi], "Клинок Овцы"))
        if bi == LUSHEN.get(base_si): found.append(("禄神", BRANCHES[bi], "Звезда Процветания"))
    # По ветви года/дня
    for src_bi in branch_srcs:
        grp = san_he_group(src_bi)
        for bi in all_branches:
            if bi == YIMA.get(grp): found.append(("驿马", BRANCHES[bi], "Странствующий Конь"))
            if bi == TAOHUA.get(grp): found.append(("桃花", BRANCHES[bi], "Цветок Персика"))
            if bi == HUAGAI.get(grp): found.append(("华盖", BRANCHES[bi], "Балдахин"))
    # Дедупликация
    return list(set(found))

def find_interactions(branches):
    """Найти взаимодействия между ветвями."""
    interactions = []
    labels = ["Час","День","Месяц","Год"]
    for i in range(len(branches)):
        for j in range(i+1, len(branches)):
            bi, bj = branches[i], branches[j]
            if bi is None or bj is None: continue
            if CLASHES.get(bi) == bj:
                interactions.append(f"冲 {BRANCHES[bi]}-{BRANCHES[bj]} ({labels[i]}-{labels[j]})")
            # 六合
            he_pairs = [(0,1),(2,11),(3,10),(4,9),(5,8),(6,7)]
            for a,b in he_pairs:
                if (bi==a and bj==b) or (bi==b and bj==a):
                    interactions.append(f"合 {BRANCHES[bi]}-{BRANCHES[bj]} ({labels[i]}-{labels[j]})")
            # 刑
            xing = [(2,5),(5,8),(8,2),(0,3),(3,0),(1,10),(10,7),(7,1)]
            if (bi,bj) in xing:
                interactions.append(f"刑 {BRANCHES[bi]}-{BRANCHES[bj]} ({labels[i]}-{labels[j]})")
    return interactions


# Динамика: одна ветвь (流年/大运) против натальных. Те же таблицы, что у натального
# find_interactions (六合/刑), + 六害 и замыкание 三合.
HE_PAIRS = [(0,1),(2,11),(3,10),(4,9),(5,8),(6,7)]                       # 六合
XING_PAIRS = [(2,5),(5,8),(8,2),(0,3),(3,0),(1,10),(10,7),(7,1)]         # 刑
HAI_PAIRS = [(0,7),(1,6),(2,5),(3,4),(8,11),(9,10)]                      # 六害

def find_branch_interactions(nb, nlabel, others):
    """Взаимодействия ветви nb (метка nlabel, напр. 流年/大运) с натальными others=[(idx,label)]."""
    if nb is None:
        return []
    out = []
    for ob, olabel in others:
        if ob is None:
            continue
        pair, tag = f"{BRANCHES[nb]}-{BRANCHES[ob]}", f"({nlabel}-{olabel})"
        if CLASHES.get(nb) == ob:
            out.append(f"冲 {pair} {tag}")
        if (nb, ob) in HE_PAIRS or (ob, nb) in HE_PAIRS:
            out.append(f"合 {pair} {tag}")
        if (nb, ob) in XING_PAIRS or (ob, nb) in XING_PAIRS:
            out.append(f"刑 {pair} {tag}")
        if (nb, ob) in HAI_PAIRS or (ob, nb) in HAI_PAIRS:
            out.append(f"害 {pair} {tag}")
    g = san_he_group(nb)                                                 # 三合: nb замыкает треугольник?
    if {nb} | {ob for ob, _ in others if ob in TRIADS[g]} == TRIADS[g]:
        trio = "".join(BRANCHES[x] for x in TRIADS[g])
        out.append(f"三合 {trio} → {ELEMENTS_RU[TRIAD_ELEMENT[g]]} ({nlabel} замыкает)")
    return out

# ═══════════════════════════════════════════════════════════════════════════
# СТОЛПЫ УДАЧИ
# ═══════════════════════════════════════════════════════════════════════════

def luck_pillars(year, month, day, hour, minute, tz_off, gender, ys, ms, mb, bm):
    from datetime import timezone as tz
    is_yang = (ys % 2 == 0)
    is_male = gender in ("М","м","M","m","male","мужской")
    forward = (is_yang and is_male) or (not is_yang and not is_male)
    direction = 1 if forward else -1

    target = datetime(year,month,day,hour,minute,
                      tzinfo=tz(timedelta(hours=tz_off))).astimezone(timezone.utc)
    jie = []
    for y in [year-1, year, year+1]:
        jie.extend(get_jie_terms(y))
    jie.sort(key=lambda x: x[0])

    target_jie = None
    if forward:
        for t in jie:
            if t[0] > target: target_jie = t[0]; break
    else:
        for t in reversed(jie):
            if t[0] <= target: target_jie = t[0]; break
    if not target_jie: return None

    diff = abs((target_jie - target).total_seconds()) / 86400.0
    start_age = diff / 3.0
    pillars = []
    cs, cb = ms, mb
    for i in range(10):
        cs = (cs + direction) % 10
        cb = (cb + direction) % 12
        pillars.append((start_age + i*10, cs, cb))
    return start_age, direction, pillars

# ═══════════════════════════════════════════════════════════════════════════
# ВЫВОД
# ═══════════════════════════════════════════════════════════════════════════

def sexagenary_pos(si, bi):
    k = 6*(si+1) - 5*(bi+1)
    return k if k > 0 else k + 60

def stem_json(si):
    if si is None:
        return None
    return {
        "index": si,
        "name": STEMS[si],
        "element": ELEMENTS_RU[STEM_ELEMENT[si]],
        "element_index": STEM_ELEMENT[si],
        "polarity": "yang" if STEM_POLARITY[si] else "yin",
    }

def branch_json(bi, dm=None):
    if bi is None:
        return None
    hidden = []
    for h in HIDDEN_STEMS[bi]:
        if h >= 0:
            item = stem_json(h)
            if dm is not None:
                tg = ten_god(dm, h)
                item["ten_god"] = TEN_GODS[tg]
                item["ten_god_ru"] = TEN_GODS_RU[tg]
            hidden.append(item)
    return {
        "index": bi,
        "name": BRANCHES[bi],
        "animal": ANIMALS[bi],
        "element": ELEMENTS_RU[BRANCH_ELEMENT[bi]],
        "element_index": BRANCH_ELEMENT[bi],
        "hidden_stems": hidden,
    }

def pillar_json(label, si, bi, dm=None):
    data = {"label": label, "stem": stem_json(si), "branch": branch_json(bi, dm)}
    if si is not None and bi is not None:
        data["name"] = f"{STEMS[si]}{BRANCHES[bi]}"
        data["sexagenary_position"] = sexagenary_pos(si, bi)
        ny = (data["sexagenary_position"] - 1) // 2
        data["nayin"] = NAYIN[ny]
        data["nayin_element"] = ELEMENTS_RU[NAYIN_ELEMENT[ny]]
    else:
        data["name"] = None
        data["sexagenary_position"] = None
        data["nayin"] = None
        data["nayin_element"] = None
    if dm is not None and si is not None:
        tg = ten_god(dm, si)
        data["ten_god"] = TEN_GODS[tg]
        data["ten_god_ru"] = TEN_GODS_RU[tg]
    else:
        data["ten_god"] = None
        data["ten_god_ru"] = None
    return data

def build_chart_data(year, month, day, hour=None, minute=0, gender=None, tz_off=8, as_of=None):
    bm, bb, by = get_bazi_month(year, month, day, hour or 12, minute, tz_off)
    ys, yb = year_pillar(by)
    ms, mb = month_pillar(ys, bm) if bm else (None, None)
    ds, db = day_pillar(year, month, day)
    hs, hb = hour_pillar(ds, hour) if hour is not None else (None, None)

    dm = ds
    pillars = [(hs, hb), (ds, db), (ms, mb), (ys, yb)]
    all_branches = [b for _, b in pillars if b is not None]

    bal = element_balance(pillars)
    total = sum(bal.values())
    balance = {
        ELEMENTS_RU[i]: {
            "index": i,
            "weight": bal[i],
            "percent": bal[i] / total * 100 if total else 0,
        }
        for i in range(5)
    }

    god_count = {}
    for si, bi in pillars:
        if si is not None and si != dm:
            tg = ten_god(dm, si)
            god_count[tg] = god_count.get(tg, 0) + 1
        if bi is not None:
            for h in HIDDEN_STEMS[bi]:
                if h >= 0:
                    tg = ten_god(dm, h)
                    god_count[tg] = god_count.get(tg, 0) + 0.5

    strength = None
    yongshen = []
    jishen = []
    tiaohou_field = None
    ys_basis, ys_borderline, ys_alt = None, False, None
    ana = analyze_gods(dm, mb, pillars)
    if ana:
        strength = {"score": ana["score"], "label": ana["label"],
                    "support_share": round(ana["support"], 3), "borderline": ana["borderline"]}
        yongshen, jishen = ana["yongshen"], ana["jishen"]
        ys_basis, ys_borderline = ana["basis"], ana["borderline"]
        ys_alt = ana["alt_yongshen"] if ana["borderline"] else None
        if ana["tiaohou"]:
            t = ana["tiaohou"]
            tiaohou_field = {
                "primary": {"stem": STEMS[t["primary_stem"]], "stem_index": t["primary_stem"],
                            "element": ELEMENTS_RU[t["primary_el"]], "element_index": t["primary_el"]},
                "auxiliary": {"stem": STEMS[t["aux_stem"]], "stem_index": t["aux_stem"],
                              "element": ELEMENTS_RU[t["aux_el"]], "element_index": t["aux_el"]},
                "aligns_with_yongshen": t["aligns"],
            }

    kw = kong_wang(ds, db)
    hl = HONGLUAN[yb]
    tx = TIANXI_STAR[yb]
    active_kw = []
    seen_kw = set()
    for b in all_branches:
        if b in kw and b not in seen_kw:
            seen_kw.add(b)
            active_kw.append(branch_json(b))

    luck = None
    if gender and bm and ms is not None:
        lp = luck_pillars(year, month, day, hour or 12, minute, tz_off, gender, ys, ms, mb, bm)
        if lp:
            start_age, direction, plist = lp
            luck = {
                "start_age": start_age,
                "direction": "forward" if direction == 1 else "reverse",
                "pillars": [
                    {
                        "age_start": age,
                        "age_end": age + 10,   # исключающая граница окна [age_start, age_end); подпись «7–17» (issue #8)
                        "stem": stem_json(si),
                        "branch": branch_json(bi, dm),
                        "name": f"{STEMS[si]}{BRANCHES[bi]}",
                        "ten_god": TEN_GODS[ten_god(dm, si)],
                        "ten_god_ru": TEN_GODS_RU[ten_god(dm, si)],
                    }
                    for age, si, bi in plist
                ],
            }

    from datetime import date
    # --as-of: детерминированный пересчёт (дифф персиста); год РЕЗОЛВИТСЯ Личунем, не 1 января (2026-07-18)
    cur_year, year_boundary = resolve_forecast_year(as_of or date.today(), tz_off)
    cur_ys, cur_yb = year_pillar(cur_year)

    # ── динамика: 流年 (текущий год) и текущий 大运 (столп удачи) против натальных ветвей ──
    natal_lbl = [(hb, "Час"), (db, "День"), (mb, "Месяц"), (yb, "Год")]
    cur_age = cur_year - year
    # Текущий 大运 — по ТОЧНОМУ возрасту на дату as-of и окну в 10 лет [age_start, age_start+10).
    # До 2026-11-09 сравнивался целый возраст (год − год) с полуинтервалом [age_start, age_start+9]:
    # целый возраст 17, 27, 37… не попадал ни в один столп, и раз в десять лет «текущий период» выходил
    # без столпа удачи (luck: null). С issue #8 age_end = age_start + 10 — честная исключающая граница.
    as_of_date = as_of or date.today()
    cur_age_exact = (as_of_date - date(year, month, day)).days / 365.2425
    cur_luck = (next((pp for pp in luck["pillars"]
                      if pp["age_start"] <= cur_age_exact < pp["age_start"] + 10), None)
                if luck else None)
    dynamic = {
        "as_of_year": cur_year,
        "year_boundary": year_boundary,
        "age": cur_age,
        "age_exact": round(cur_age_exact, 2),
        "year": {
            "branch": BRANCHES[cur_yb],
            "pillar": f"{STEMS[cur_ys]}{BRANCHES[cur_yb]}",
            "vs_natal": find_branch_interactions(cur_yb, "流年", natal_lbl),
        },
        "luck": None,
        "year_vs_luck": [],
    }
    if cur_luck:
        lb = cur_luck["branch"]["index"]
        dynamic["luck"] = {
            "branch": BRANCHES[lb],
            "pillar": cur_luck["name"],
            "age_start": cur_luck["age_start"],
            "age_end": cur_luck["age_end"],
            "vs_natal": find_branch_interactions(lb, "大运", natal_lbl),
        }
        dynamic["year_vs_luck"] = find_branch_interactions(cur_yb, "流年", [(lb, "大运")])

    return {
        "input": {
            "date": f"{year}-{month:02d}-{day:02d}",
            "time": f"{hour:02d}:{minute:02d}" if hour is not None else None,
            "gender": gender,
            "utc_offset": tz_off,
        },
        "conventions": conventions_now(),
        "bazi_year": by,
        "bazi_month_number": bm,
        "bazi_month_branch": bb,
        "pillars": {
            "hour": pillar_json("hour", hs, hb, dm),
            "day": pillar_json("day", ds, db, dm),
            "month": pillar_json("month", ms, mb, dm),
            "year": pillar_json("year", ys, yb, dm),
        },
        "day_master": stem_json(dm),
        "day_pillar": {
            "name": f"{STEMS[ds]}{BRANCHES[db]}",
            "sexagenary_position": sexagenary_pos(ds, db),
            "nayin": NAYIN[(sexagenary_pos(ds, db) - 1) // 2],
        },
        "strength": strength,
        "element_balance": balance,
        "ten_gods": [
            {"name": TEN_GODS[tg], "name_ru": TEN_GODS_RU[tg], "weight": god_count[tg]}
            for tg in sorted(god_count, key=god_count.get, reverse=True)
        ],
        "yongshen": [{"index": e, "element": ELEMENTS_RU[e], "source": "旺衰"} for e in yongshen],
        "yongshen_basis": ys_basis,
        "yongshen_borderline": ys_borderline,
        "yongshen_alt": ([{"index": e, "element": ELEMENTS_RU[e]} for e in ys_alt] if ys_alt else None),
        "jishen": [{"index": e, "element": ELEMENTS_RU[e]} for e in jishen],
        # школа 格局 (子平真诠 по geju.md) — второй взгляд на 用神, не замена школе силы (issue #29)
        "geju": (__import__("geju").analyze(dm, pillars, yongshen, jishen, strength) if mb is not None else None),
        "tiaohou": tiaohou_field,
        "boundary_warnings": boundary_warnings(year, month, day, hour, minute, tz_off),
        "kong_wang": [branch_json(kw[0]), branch_json(kw[1])],
        "kong_wang_active": active_kw,
        "interactions": find_interactions([hb, db, mb, yb]),
        "shensha": [
            {"name": zh, "branch": br, "name_ru": ru}
            for zh, br, ru in sorted(find_shensha(dm, yb, db, all_branches, ys))
        ],
        "hongluan": branch_json(hl),
        "tianxi": branch_json(tx),
        "luck_pillars": luck,
        "current_year": {
            "year": cur_year,
            "year_boundary": year_boundary,
            "pillar": f"{STEMS[cur_ys]}{BRANCHES[cur_yb]}",
            "stem": stem_json(cur_ys),
            "branch": branch_json(cur_yb, dm),
            "ten_god": TEN_GODS[ten_god(dm, cur_ys)],
            "ten_god_ru": TEN_GODS_RU[ten_god(dm, cur_ys)],
            "clashes_natal": CLASHES.get(cur_yb) in all_branches,
        },
        "dynamic_interactions": dynamic,
    }

def print_full_chart(year, month, day, hour=None, minute=0, gender=None, tz_off=8, as_of=None):
    bm, bb, by = get_bazi_month(year, month, day, hour or 12, minute, tz_off)
    ys, yb = year_pillar(by)
    ms, mb = month_pillar(ys, bm) if bm else (None, None)
    ds, db = day_pillar(year, month, day)
    hs, hb = hour_pillar(ds, hour) if hour is not None else (None, None)

    dm = ds  # Хозяин Дня
    pillars = [(hs,hb),(ds,db),(ms,mb),(ys,yb)]
    all_stems = [s for s,_ in pillars if s is not None]
    all_branches = [b for _,b in pillars if b is not None]

    # ── Заголовок ──
    print(f"\n{'═'*68}")
    print(f"  КАРТА БА ЦЗЫ (八字)")
    print(f"  Дата: {year}-{month:02d}-{day:02d}", end="")
    if hour is not None: print(f" {hour:02d}:{minute:02d}", end="")
    print(f" (UTC{tz_off:+g})", end="")
    if gender: print(f"  Пол: {gender}", end="")
    print(f"\n  Год Ба Цзы: {by}  Месяц: {bm} ({bb})")
    print(f"{'═'*68}")

    # ── Граничные предупреждения (чувствительность к точности ввода) ──
    bw = boundary_warnings(year, month, day, hour, minute, tz_off)
    if bw:
        print(f"\n  ⚠ ЧУВСТВИТЕЛЬНОСТЬ К ТОЧНОСТИ ВВОДА:")
        for w in bw:
            mark = {"high": "‼", "medium": "⚠", "info": "ℹ"}.get(w["severity"], "·")
            print(f"    {mark} [{w['pillar']}] {w['detail']}")

    # ── 4 Столпа ──
    labels = ["Час (时)","День (日)","Месяц (月)","Год (年)"]
    print(f"\n  {'':12}", end="")
    for l in labels: print(f"  {l:>12}", end="")
    print(f"\n  {'':12}", end="")
    for _ in labels: print(f"  {'─'*12}", end="")

    # 10 Божеств (стволы)
    print(f"\n  {'10 Божеств':12}", end="")
    for i,(si,bi) in enumerate(pillars):
        if si is None: print(f"  {'??':>12}", end=""); continue
        if i == 1: print(f"  {'▐ ХД ▌':>12}", end="")
        else:
            tg = ten_god(dm, si)
            print(f"  {TEN_GODS[tg]:>12}", end="")
    print()

    # Стволы
    print(f"  {'Стволы':12}", end="")
    for si,bi in pillars:
        if si is None: print(f"  {'??':>12}", end="")
        else: print(f"  {STEMS[si]} {ELEMENTS_RU[STEM_ELEMENT[si]][:3]}{'+'if STEM_POLARITY[si] else'-':>6}", end="")
    print()

    # Ветви
    print(f"  {'Ветви':12}", end="")
    for si,bi in pillars:
        if bi is None: print(f"  {'??':>12}", end="")
        else: print(f"  {BRANCHES[bi]} {ANIMALS[bi]:>10}", end="")
    print()

    # Скрытые стволы
    for row in range(3):
        print(f"  {'Скрытые' if row==0 else '':12}", end="")
        for si,bi in pillars:
            if bi is None: print(f"  {'':>12}", end=""); continue
            hs_list = HIDDEN_STEMS[bi]
            h = hs_list[row] if row < len(hs_list) and hs_list[row] >= 0 else -1
            if h >= 0:
                tg = ten_god(dm, h)
                print(f"  {STEMS[h]}({TEN_GODS[tg][:2]}){'':<3}", end="")
            else:
                print(f"  {'':>12}", end="")
        print()

    # ── Хозяин Дня ──
    dm_el = STEM_ELEMENT[dm]
    print(f"\n{'─'*68}")
    print(f"  Хозяин Дня: {STEMS[dm]} ({ELEMENTS_RU[dm_el]} {'Ян' if STEM_POLARITY[dm] else 'Инь'})")

    # На Инь дня
    day_sex = sexagenary_pos(ds, db)
    ny_idx = (day_sex - 1) // 2
    print(f"  Столп дня: {STEMS[ds]}{BRANCHES[db]} (#{day_sex}) — На Инь: {NAYIN[ny_idx]}")

    # ── Сила ХД ──
    if mb is not None:
        sc, lbl = dm_strength(dm, mb, pillars)
        print(f"\n  Сила ХД: {lbl} (очки: {sc})")

    # ── Баланс стихий ──
    bal = element_balance(pillars)
    total = sum(bal.values())
    print(f"\n  Баланс стихий:")
    for i in range(5):
        pct = bal[i]/total*100 if total > 0 else 0
        bar = "█" * int(pct / 5)
        rel = ""
        if i == dm_el: rel = " ← ХД"
        elif PRODUCES[i] == dm_el: rel = " (生ХД)"
        elif CONTROLS[i] == dm_el: rel = " (克ХД)"
        elif PRODUCES[dm_el] == i: rel = " (ХД生)"
        elif CONTROLS[dm_el] == i: rel = " (ХД克)"
        print(f"    {ELEMENTS_RU[i]:>7} {bar:<20} {pct:5.1f}%{rel}")

    # ── 10 Божеств — сводка ──
    god_count = {}
    for si,bi in pillars:
        if si is not None and si != dm:
            tg = ten_god(dm, si)
            god_count[tg] = god_count.get(tg, 0) + 1
        if bi is not None:
            for h in HIDDEN_STEMS[bi]:
                if h >= 0:
                    tg = ten_god(dm, h)
                    god_count[tg] = god_count.get(tg, 0) + 0.5
    print(f"\n  Десять Божеств (присутствие):")
    for tg_idx in sorted(god_count, key=god_count.get, reverse=True):
        print(f"    {TEN_GODS[tg_idx]} ({TEN_GODS_RU[tg_idx]}): {god_count[tg_idx]:.1f}")

    # ── 用神 / 忌神 / 调候 ──
    ana = analyze_gods(dm, mb, pillars)
    if ana:
        yongshen, jishen = ana["yongshen"], ana["jishen"]
        print(f"\n  用神 旺衰 ({ana['basis']}): {', '.join(ELEMENTS_RU[e] for e in yongshen)}")
        print(f"  忌神 (неблагоприятные): {', '.join(ELEMENTS_RU[e] for e in jishen)}")
        if ana["borderline"]:
            print(f"    ⚠ пограничная сила (поддержка {ana['support']*100:.0f}%) — "
                  f"альтернатива 用神: {', '.join(ELEMENTS_RU[e] for e in ana['alt_yongshen'])} [трактуемо]")
        if ana["tiaohou"]:
            t = ana["tiaohou"]
            mark = "✓ совпадает с 用神 по силе" if t["aligns"] else "⚠ расходится с 用神 по силе"
            print(f"  调候 (климат): {STEMS[t['primary_stem']]} {ELEMENTS_RU[t['primary_el']]} "
                  f"(доп. {STEMS[t['aux_stem']]} {ELEMENTS_RU[t['aux_el']]}) — {mark}")

    # ── 空亡 ──
    kw = kong_wang(ds, db)
    print(f"\n  空亡 (пустота): {BRANCHES[kw[0]]} {BRANCHES[kw[1]]}", end="")
    for bi in all_branches:
        if bi in kw: print(f" ⚠ {BRANCHES[bi]} в карте пуст!", end="")
    print()

    # ── Взаимодействия ──
    branch_list = [hb, db, mb, yb]
    ints = find_interactions(branch_list)
    if ints:
        print(f"\n  Взаимодействия ветвей:")
        for x in ints: print(f"    {x}")

    # ── Шэнь Ша ──
    ss = find_shensha(dm, yb, db, all_branches, ys)
    if ss:
        print(f"\n  Шэнь Ша (神煞):")
        seen = set()
        for zh, br, ru in sorted(ss):
            key = f"{zh}{br}"
            if key not in seen:
                seen.add(key)
                print(f"    {zh} ({ru}) — {br}")

    # ── 红鸾 / 天喜 ──
    hl = HONGLUAN[yb]
    tx = TIANXI_STAR[yb]
    print(f"\n  红鸾 (Красный Феникс): {BRANCHES[hl]}  天喜 (Небесная Радость): {BRANCHES[tx]}")

    # ── Столпы Удачи ──
    if gender and bm and ms is not None:
        lp = luck_pillars(year, month, day, hour or 12, minute, tz_off, gender, ys, ms, mb, bm)
        if lp:
            sa, d, plist = lp
            dstr = "прямое ↑" if d == 1 else "обратное ↓"
            print(f"\n  Столпы Удачи (大运): {dstr}, начало {sa:.1f} лет")
            print(f"  {'Возраст':>8}  {'Столп':>5}  {'Стихия':>10}  {'10 Божество':>12}")
            print(f"  {'─'*50}")
            for age, si, bi in plist:
                tg = ten_god(dm, si)
                print(f"  {age:4.0f}-{age+10:<4.0f}  {STEMS[si]}{BRANCHES[bi]}   "
                      f"{ELEMENTS_RU[STEM_ELEMENT[si]]:>10}  {TEN_GODS[tg]} ({TEN_GODS_RU[tg]})")

    # ── Текущий год ──
    from datetime import date
    # --as-of: детерминированный пересчёт; год резолвится Личунем, не 1 января (2026-07-18)
    cur_year, year_boundary = resolve_forecast_year(as_of or date.today(), tz_off)
    cur_ys, cur_yb = year_pillar(cur_year)
    cur_tg = ten_god(dm, cur_ys)
    print(f"\n  Текущий год {cur_year}: {STEMS[cur_ys]}{BRANCHES[cur_yb]} "
          f"— {TEN_GODS[cur_tg]} ({TEN_GODS_RU[cur_tg]})")
    print(f"    ({year_boundary['basis']})")
    if CLASHES.get(cur_yb) in all_branches:
        clash_b = CLASHES[cur_yb]
        print(f"    ⚠ Столкновение годовой ветви {BRANCHES[cur_yb]} с {BRANCHES[clash_b]} в карте!")
    if cur_yb == hl: print(f"    ♥ 红鸾 активирована — год брака/романтики")
    if cur_yb == tx: print(f"    ★ 天喜 активирована — радостные события")

    print(f"\n{'═'*68}\n")

# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ
# ═══════════════════════════════════════════════════════════════════════════

def run_tests():
    tests = [
        # (y,m,d, expected_day_stem, expected_day_branch, description)
        (2019, 1, 27, 0, 0, "甲子 — опорная дата"),
        (2024, 2, 10, 0, 4, "甲辰 — Новый год 2024 (проверочная)"),
        (1990, 5, 15, 6, 4, "庚辰 — из примера в skill"),
    ]
    passed = 0
    for y, m, d, exp_s, exp_b, desc in tests:
        ds, db = day_pillar(y, m, d)
        ok = ds == exp_s and db == exp_b
        status = "✓" if ok else "✗"
        print(f"  {status} {desc}: {y}-{m:02d}-{d:02d} → {STEMS[ds]}{BRANCHES[db]} "
              f"(ожидалось {STEMS[exp_s]}{BRANCHES[exp_b]})")
        if ok: passed += 1

    # Тест месяца
    bm, _, by = get_bazi_month(2024, 2, 3, 12, 0, 8)
    ok = bm == 12 and by == 2023
    print(f"  {'✓' if ok else '✗'} 2024-02-03 до Ли Чунь → год={by}, месяц={bm} (ожидалось 2023, 12)")
    if ok: passed += 1

    bm2, _, by2 = get_bazi_month(2024, 2, 5, 12, 0, 8)
    ok2 = bm2 == 1 and by2 == 2024
    print(f"  {'✓' if ok2 else '✗'} 2024-02-05 после Ли Чунь → год={by2}, месяц={bm2} (ожидалось 2024, 1)")
    if ok2: passed += 1

    # ПРОГНОЗНЫЙ год резолвится Личунем, не 1 января (фикс 2026-07-18):
    # январское окно (1 янв → Личунь, ~5 недель) прежде получало неверный 流年
    from datetime import date as _date
    fy1, fb1 = resolve_forecast_year(_date(2026, 1, 20), 8)
    ok3 = fy1 == 2025 and "до Личуня" in fb1["basis"]
    print(f"  {'✓' if ok3 else '✗'} прогноз as-of 2026-01-20 → год Ба Цзы {fy1} (ожидалось 2025, до Личуня)")
    if ok3: passed += 1

    fy2, fb2 = resolve_forecast_year(_date(2026, 2, 20), 8)
    ok4 = fy2 == 2026 and "после Личуня" in fb2["basis"]
    print(f"  {'✓' if ok4 else '✗'} прогноз as-of 2026-02-20 → год Ба Цзы {fy2} (ожидалось 2026, после Личуня)")
    if ok4: passed += 1

    lichun26 = next(t[0] for t in get_jie_terms(2026) if t[1] == 1 and t[0].year == 2026)
    _, fb3 = resolve_forecast_year((lichun26 + timedelta(hours=8)).date(), 8)
    ok5 = "САМ ДЕНЬ" in fb3["basis"]
    print(f"  {'✓' if ok5 else '✗'} прогноз в день Личуня → помечен как граничный "
          f"({(lichun26 + timedelta(hours=8)).date().isoformat()})")
    if ok5: passed += 1

    # ТЕКУЩИЙ 大运 — по точному возрасту, окно 10 лет (фикс 2026-11-09). Пример гайда: 1990-05-15 14:30 М,
    # UTC+4, столпы 壬午 7.19–17.19, 癸未 17.19–27.19, 甲申 27.19–37.19, 乙酉 37.19–…
    d_gap = build_chart_data(1990, 5, 15, 13, 4, "мужской", 4, as_of=_date(2007, 6, 1))
    lk_gap = d_gap["dynamic_interactions"]["luck"]
    ok6 = lk_gap is not None and lk_gap["pillar"] == "壬午"
    print(f"  {'✓' if ok6 else '✗'} 大运 as-of 2007-06-01 (возраст 17.05) → {lk_gap['pillar'] if lk_gap else None} "
          f"(ожидалось 壬午; раньше — «дыра», null)")
    if ok6: passed += 1

    d_edge = build_chart_data(1990, 5, 15, 13, 4, "мужской", 4, as_of=_date(2026, 11, 9))
    lk_edge = d_edge["dynamic_interactions"]["luck"]
    ok7 = lk_edge is not None and lk_edge["pillar"] == "甲申" and d_edge["dynamic_interactions"]["age_exact"] == 36.49
    print(f"  {'✓' if ok7 else '✗'} 大运 as-of 2026-11-09 (возраст 36.49) → {lk_edge['pillar'] if lk_edge else None} "
          f"(ожидалось 甲申: окно 27.19–37.19 = [age_start, age_end))")
    if ok7: passed += 1

    d_next = build_chart_data(1990, 5, 15, 13, 4, "мужской", 4, as_of=_date(2027, 9, 1))
    lk_next = d_next["dynamic_interactions"]["luck"]
    ok8 = lk_next is not None and lk_next["pillar"] == "乙酉"
    print(f"  {'✓' if ok8 else '✗'} 大运 as-of 2027-09-01 (возраст 37.30 > 37.19) → {lk_next['pillar'] if lk_next else None} "
          f"(ожидалось 乙酉; целый возраст 37 давал «дыру», null)")
    if ok8: passed += 1

    # 夜子时 (issue #16): день остаётся 庚辰, ствол 子-часа — от следующего дня (辛 → 戊子); старая конвенция — 丙子
    d_zi = build_chart_data(1990, 5, 15, 23, 30, "мужской", 8)
    ok9 = d_zi["pillars"]["day"]["name"] == "庚辰" and d_zi["pillars"]["hour"]["name"] == "戊子" \
        and d_zi["conventions"]["late_zi_hour_stem"] == "next_day"
    print(f"  {'✓' if ok9 else '✗'} 夜子时 23:30 15.05.1990 → день {d_zi['pillars']['day']['name']}, "
          f"час {d_zi['pillars']['hour']['name']} (ожидалось 庚辰 / 戊子 — ствол часа от следующего дня, как lunar-python)")
    if ok9: passed += 1
    ok10 = hour_pillar(6, 23, late_zi="same_day") == (2, 0)   # 庚-день, same_day → 丙子
    print(f"  {'✓' if ok10 else '✗'} 夜子时 same_day (конвенция до 2026-11-09) → {STEMS[hour_pillar(6, 23, 'same_day')[0]]}子 (ожидалось 丙子)")
    if ok10: passed += 1

    # Край 用神 (issue #12): метка силы против стихийного баланса — помечаем borderline, ведём по силе
    d_w = build_chart_data(2005, 10, 16, 22, 0, "мужской", 8)
    ok11 = (d_w["strength"]["label"] == "СЛАБЫЙ" and d_w["strength"]["support_share"] > 0.5
            and d_w["yongshen_borderline"] is True and d_w["yongshen"][0]["element"] == ELEMENTS_RU[STEM_ELEMENT[d_w["day_master"]["index"]]])
    print(f"  {'✓' if ok11 else '✗'} 用神-край: СЛАБЫЙ при поддержке {d_w['strength']['support_share']:.0%} → borderline={d_w['yongshen_borderline']}, "
          f"ведём по силе (усилить) (ожидалось True, 用神 = стихия ХД)")
    if ok11: passed += 1
    d_s = build_chart_data(2009, 2, 19, 9, 0, "мужской", 8)
    ok12 = (d_s["strength"]["label"] == "СИЛЬНЫЙ" and d_s["strength"]["support_share"] < 0.5
            and d_s["yongshen_borderline"] is True)
    print(f"  {'✓' if ok12 else '✗'} 用神-край: СИЛЬНЫЙ при поддержке {d_s['strength']['support_share']:.0%} → borderline={d_s['yongshen_borderline']} (ожидалось True)")
    if ok12: passed += 1

    # Переключатели Шэнь Ша (issue #18): 庚-день с 寅 в карте — 天乙 только в версии 庚辛逢虎马; 辛-день: 羊刃 申 исчезает при «阴干无刃»
    global TIANYI_VERSION, YANGREN_YIN, SHENSHA_BASE
    names = lambda ss: sorted(f"{z}{b}" for z, b, _ in ss)
    base = names(find_shensha(6, 0, 4, [2, 4, 0, 9]))          # 庚-день, ветви 寅辰子酉
    TIANYI_VERSION = "huma"; huma = names(find_shensha(6, 0, 4, [2, 4, 0, 9])); TIANYI_VERSION = "niuyang"
    ok13 = "天乙贵人寅" not in base and "天乙贵人寅" in huma
    print(f"  {'✓' if ok13 else '✗'} --tianyi: 庚 с 寅 → 牛羊 {[x for x in base if '天乙' in x]} | 虎马 {[x for x in huma if '天乙' in x]} (ожидалось 天乙 寅 только во второй)")
    if ok13: passed += 1
    xin = names(find_shensha(7, 0, 8, [8, 0, 3, 7]))           # 辛-день, ветви 申子卯未
    YANGREN_YIN = "none"; xin_none = names(find_shensha(7, 0, 8, [8, 0, 3, 7])); YANGREN_YIN = "diwang"
    ok14 = "羊刃申" in xin and "羊刃申" not in xin_none and build_chart_data(1990, 5, 15, 14, 30, "мужской", 8)["conventions"]["switches"]["--yangren-yin"] == "diwang"
    print(f"  {'✓' if ok14 else '✗'} --yangren-yin: 辛 с 申 → diwang {[x for x in xin if '羊刃' in x]} | none {[x for x in xin_none if '羊刃' in x]}; conventions.switches в JSON")
    if ok14: passed += 1
    SHENSHA_BASE = "year"; yr = names(find_shensha(6, 0, 4, [2, 4, 0, 9], year_si=0)); SHENSHA_BASE = "day+year"   # год 甲子: 禄神 寅, 羊刃 卯 нет, 天乙 丑未 нет
    ok15 = "禄神寅" in yr and not any("禄神" in x for x in base)
    print(f"  {'✓' if ok15 else '✗'} --shensha-base year: от года 甲 → {yr} (ожидалось 禄神 寅 от 甲, которого нет при базе от дня 庚)")
    if ok15: passed += 1

    # Солнечная поправка через полночь (2026-11-09): Пермь (−88 мин) 01:00 → солнечные сутки накануне; день 丙寅 (1990-03-02),
    # ствол 子-часа от следующего дня 丁 → 庚子. Проверяем через CLI --city, как считает скилл.
    import subprocess as _sp
    r = _sp.run([sys.executable, os.path.abspath(__file__), "1990-03-03", "01:00", "М", "--city", "Пермь", "--json"], capture_output=True, text=True)
    try:
        dj = json.loads(r.stdout)
        ok16 = (dj["pillars"]["day"]["name"] == "丙寅" and dj["pillars"]["hour"]["name"] == "庚子"
                and dj["input"]["date"] == "1990-03-03" and dj["input"]["solar_date"] == "1990-03-02" and dj["input"]["solar_day_shift"] == -1)
        got = f"день {dj['pillars']['day']['name']}, час {dj['pillars']['hour']['name']}, date {dj['input']['date']}, solar_date {dj['input'].get('solar_date')}"
    except Exception as e:  # noqa: BLE001
        ok16, got = False, f"ошибка: {e} / {r.stderr[-200:]}"
    print(f"  {'✓' if ok16 else '✗'} солнечная полночь: Пермь 1990-03-03 01:00 → {got} (ожидалось 丙寅 / 庚子, solar_date 1990-03-02)")
    if ok16: passed += 1
    dj2 = build_chart_data(1990, 3, 2, 23, 33, "мужской", 5)
    ok17 = dj2["pillars"]["day"]["name"] == "丙寅" and dj2["pillars"]["hour"]["name"] == "庚子"
    print(f"  {'✓' if ok17 else '✗'} тот же момент напрямую (1990-03-02 23:33 UTC+5) → {dj2['pillars']['day']['name']} {dj2['pillars']['hour']['name']} — совпадает с --city")
    if ok17: passed += 1

    total = len(tests) + 17
    print(f"\n  Результат: {passed}/{total} тестов пройдено")
    return passed == total

# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__, file=sys.stderr)  # usage → stderr: пустой вызов не должен давать «чистый» stdout при exit 0
        sys.exit(2)

    if args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    if args[0] == "--test":
        sys.exit(0 if run_tests() else 1)  # честный exit-код: FAIL тестов не должен глотаться

    json_mode = "--json" in args
    args = [a for a in args if a != "--json"]

    # Парсинг: YYYY-MM-DD [HH:MM] [М|Ж] [UTC+N] [--city Город] [--as-of YYYY-MM-DD]
    parts = args[0].split("-")
    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    hour, minute, gender, tz_off, city, as_of = None, 0, None, None, None, None

    i = 1
    while i < len(args):
        a = args[i]
        if a == "--as-of" and i + 1 < len(args):
            from datetime import date as _date
            try:
                as_of = _date.fromisoformat(args[i + 1])
            except ValueError:
                print(f"ОШИБКА: не разобрал --as-of «{args[i + 1]}» (ожидал YYYY-MM-DD)", file=sys.stderr)
                sys.exit(2)
            i += 1
        elif ":" in a:
            hp = a.split(":"); hour, minute = int(hp[0]), int(hp[1])
        elif a.upper().startswith("UTC"):
            # «UTC+3», «UTC-5», «UTC+-5», «UTC+8.5» → число; дробные оффсеты (Сеул +8.5) законны
            try:
                v = float(a.upper().replace("UTC", "").replace("+", ""))
            except ValueError:
                # единый exit-2-контракт с hd/jyotish/gene_keys (ревью 2026-07-18):
                # незамещённый плейсхолдер ($OFFSET / пустая подстановка) — громкий отказ, не traceback
                print(f"ОШИБКА: не разобрал оффсет «{a}» — незамещённый плейсхолдер? "
                      f"Ожидал UTC+3 / UTC-5 / UTC+8.5", file=sys.stderr)
                sys.exit(2)
            tz_off = int(v) if v == int(v) else v
        elif a == "--city" and i + 1 < len(args):
            city = args[i + 1]
            i += 1
        elif a in ("--tianyi", "--yangren-yin", "--shensha-base") and i + 1 < len(args):
            # переключатели школ Шэнь Ша (issue #18); использованное значение — в JSON conventions.switches
            global TIANYI_VERSION, YANGREN_YIN, SHENSHA_BASE
            allowed = {"--tianyi": ("niuyang", "huma"), "--yangren-yin": ("diwang", "none"),
                       "--shensha-base": ("day+year", "day", "year")}[a]
            if args[i + 1] not in allowed:
                print(f"ОШИБКА: {a} ожидает {'|'.join(allowed)}, получено «{args[i + 1]}»", file=sys.stderr)
                sys.exit(2)
            if a == "--tianyi": TIANYI_VERSION = args[i + 1]
            elif a == "--yangren-yin": YANGREN_YIN = args[i + 1]
            else: SHENSHA_BASE = args[i + 1]
            i += 1
        elif a == "--late-zi-hour-stem" and i + 1 < len(args):
            # конвенция 夜子时 для ствола часа: next_day (мейнстрим, по умолчанию) | same_day (как до 2026-11-09)
            global LATE_ZI_HOUR_STEM
            if args[i + 1] not in ("next_day", "same_day"):
                print(f"ОШИБКА: --late-zi-hour-stem ожидает next_day|same_day, получено «{args[i + 1]}»", file=sys.stderr)
                sys.exit(2)
            LATE_ZI_HOUR_STEM = args[i + 1]
            i += 1
        elif a in ("М","м","M","m","male","мужской"):
            gender = "мужской"
        elif a in ("Ж","ж","F","f","female","женский"):
            gender = "женский"
        else:
            try:
                from timezones import CITIES
                if a in CITIES:
                    city = a
            except Exception:
                pass
        i += 1

    # Пояс обязан быть явным: город (исторический оффсет + солнечная поправка) или UTC±N (issue #9).
    # Раньше молча брался UTC+8 — для рождений в России это тихая ошибка на 5 часов; hd/jyotish/gene_keys
    # давно требуют оффсет явно (exit 2) — выравниваем контракт.
    if not city and tz_off is None:
        print("ОШИБКА: не задан часовой пояс — укажи --city ГОРОД (предпочтительно: исторический пояс + "
              "истинное солнечное время) или UTC+N/UTC-N явно. Без пояса не считаем.", file=sys.stderr)
        sys.exit(2)

    tz_note, wall_time, wall_date, solar_shift = None, None, None, 0
    if city:
        try:
            from timezones import CITIES, historical_utc_offset, true_solar_datetime, resolve_city
            tz_off, tz_note = historical_utc_offset(city, y, m, d)  # алиасы резолвит сам, резолв — в note
            city, _ = resolve_city(city)   # современный ключ для долготы (CITIES) и персиста input.city
            if hour is not None:
                wall_time = f"{hour:02d}:{minute:02d}"   # настенное время ДО солнечной поправки
                wall_date = f"{y:04d}-{m:02d}-{d:02d}"
                _, lon, _ = CITIES[city]
                # солнечная поправка может перенести момент через полночь — тогда сдвигается и ДАТА
                # (столп дня от солнечных суток; до 2026-11-09 дата оставалась настенной — Хозяин Дня был неверен
                # у рождённых 00:xx–01:xx западнее меридиана пояса и 23:xx восточнее)
                y, m, d, hour, minute, _, solar_shift = true_solar_datetime(y, m, d, hour, minute, lon, tz_off * 15)
        except KeyError as exc:
            # Громкий отказ по общему контракту cli_errors: stderr (гейт errs.log) + код 2 + JSON-конверт при --json
            import cli_errors
            raise cli_errors.InputError(f"город «{city}» не найден в базе городов — задай пояс явно (UTC+N) "
                                        f"или добавь город в timezones.CITIES ({exc.args[0] if exc.args else exc})")
        except Exception as exc:
            import cli_errors
            raise cli_errors.InputError(f"не удалось определить пояс и солнечное время для «{city}»: {exc}")

    if json_mode:
        data = build_chart_data(y, m, d, hour, minute, gender, tz_off, as_of=as_of)
        if city:
            # персист ВХОДА как его назвал пользователь (фикс «солнечной ловушки» 2026-07-18):
            # input.time — истинное солнечное (пересчитано), сверку/пересчёт архива вести
            # по city + wall_time, НЕ по input.time
            data["input"]["city"] = city
            data["input"]["wall_time"] = wall_time
            if wall_date:
                data["input"]["solar_date"] = data["input"]["date"]   # дата солнечных суток (столп дня — от неё)
                data["input"]["date"] = wall_date                     # настенная дата, как ввёл пользователь
                data["input"]["solar_day_shift"] = solar_shift
            data["input"]["time_note"] = ("input.time — истинное солнечное время (пересчитано из "
                                          "wall_time по долготе города); сверка персиста и пересчёт — "
                                          "по city + date + wall_time, не по input.time/solar_date"
                                          + (f"; солнечная поправка перенесла момент через полночь: столп дня — от {data['input']['solar_date']} "
                                             f"(сдвиг {solar_shift:+d} сут), школа «день по настенной дате» дала бы другого Хозяина Дня" if solar_shift else ""))
            data["input"]["tz_note"] = tz_note   # оговорка пояса (⚠ — обязательная оговорка чтения)
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print_full_chart(y, m, d, hour, minute, gender, tz_off, as_of=as_of)
        if tz_note:
            print(f"  Город: {city}; пояс UTC{tz_off:+g}. {tz_note}")
        if solar_shift:
            print(f"  ⚠ Солнечная поправка перенесла рождение через полночь: столп дня — от {y:04d}-{m:02d}-{d:02d} "
                  f"(настенная дата {wall_date}, сдвиг {solar_shift:+d} сут).")

if __name__ == "__main__":
    import cli_errors
    cli_errors.run(main)
