#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""
Вычисление точных дат солнечных терминов (节气 Jie Qi) для Ба Цзы.
Астрономия: Swiss Ephemeris (pyswisseph) через ephemeris.py.
Точность: ~1″ по Солнцу → ошибка времени термина < ~3 сек (1900-2100).

Использование:
    python3 jieqi.py 1990           # все 24 термина за 1990 год
    python3 jieqi.py 1990 jie       # только 12 Цзе (节) — границы месяцев Ба Цзы
    python3 jieqi.py 1990 2000      # диапазон лет
    python3 jieqi.py 1990 2000 jie  # Цзе за диапазон
    python3 jieqi.py --month 1990-03-15  # какой месяц Ба Цзы для даты
"""

import sys
import math
from datetime import datetime, timedelta, timezone
from ephemeris import sun_lon, julian_day, jd_to_datetime, find_solar_term  # λ☉ и календарная арифметика — ephemeris.py

# ── Солнечные термины ──────────────────────────────────────────────────────

SOLAR_TERMS = [
    (315, "立春", "Li Chun",    "Начало Весны",        "节", 1,  "寅"),
    (330, "雨水", "Yu Shui",    "Дождевая Вода",       "气", None, None),
    (345, "惊蛰", "Jing Zhe",   "Пробуждение Насекомых","节", 2,  "卯"),
    (0,   "春分", "Chun Fen",   "Весеннее Равноденствие","气", None, None),
    (15,  "清明", "Qing Ming",  "Чистый Свет",         "节", 3,  "辰"),
    (30,  "谷雨", "Gu Yu",      "Хлебный Дождь",       "气", None, None),
    (45,  "立夏", "Li Xia",     "Начало Лета",         "节", 4,  "巳"),
    (60,  "小满", "Xiao Man",   "Малое Наполнение",    "气", None, None),
    (75,  "芒种", "Mang Zhong", "Колос в Ухе",         "节", 5,  "午"),
    (90,  "夏至", "Xia Zhi",    "Летнее Солнцестояние", "气", None, None),
    (105, "小暑", "Xiao Shu",   "Малая Жара",          "节", 6,  "未"),
    (120, "大暑", "Da Shu",     "Большая Жара",        "气", None, None),
    (135, "立秋", "Li Qiu",     "Начало Осени",        "节", 7,  "申"),
    (150, "处暑", "Chu Shu",    "Конец Жары",          "气", None, None),
    (165, "白露", "Bai Lu",     "Белая Роса",          "节", 8,  "酉"),
    (180, "秋分", "Qiu Fen",    "Осеннее Равноденствие","气", None, None),
    (195, "寒露", "Han Lu",     "Холодная Роса",       "节", 9,  "戌"),
    (210, "霜降", "Shuang Jiang","Выпадение Инея",     "气", None, None),
    (225, "立冬", "Li Dong",    "Начало Зимы",         "节", 10, "亥"),
    (240, "小雪", "Xiao Xue",   "Малый Снег",          "气", None, None),
    (255, "大雪", "Da Xue",     "Большой Снег",        "节", 11, "子"),
    (270, "冬至", "Dong Zhi",   "Зимнее Солнцестояние", "气", None, None),
    (285, "小寒", "Xiao Han",   "Малый Холод",         "节", 12, "丑"),
    (300, "大寒", "Da Han",     "Большой Холод",       "气", None, None),
]

# ── Расчёт долготы Солнца (Meeus, глава 25) ───────────────────────────────

# julian_day / jd_to_datetime — из ephemeris.py (единственная копия, issue #11).


def sun_longitude(jd):
    """Долгота Солнца (°) — Swiss Ephemeris (см. ephemeris.py).
    Прежнее приближение Meeus удалено (давало 3.5-13 мин ошибки на границе термина)."""
    return sun_lon(jd)


# find_solar_term — из ephemeris.py (issue #11); здесь оставлен только реэкспорт имени для qimen.py.


def get_solar_terms(year, jie_only=False):
    """Получить все солнечные термины за год.

    Возвращает список (datetime_utc, longitude, chinese, pinyin, russian, type, month_num, branch).
    Год Ба Цзы: от 小寒 предыдущего года до 大寒 текущего + 立春...大寒.
    Для простоты возвращает термины, попадающие в календарный год.
    """
    results = []
    for lon, zh, pinyin, ru, term_type, month_num, branch in SOLAR_TERMS:
        if jie_only and term_type != "节":
            continue

        # 小寒 (285°) и 大寒 (300°) с долготой > 270 попадают в январь
        # 立春 (315°) попадает в февраль
        if lon >= 285:
            # Эти термины: 小寒 ~6 янв, 大寒 ~20 янв, 立春 ~4 фев
            # Для данного year они попадают в начало year
            jd = find_solar_term(year, lon)
        else:
            jd = find_solar_term(year, lon)

        dt = jd_to_datetime(jd)

        # Проверка что дата в нужном году (±1 от целевого)
        if abs(dt.year - year) > 1:
            continue

        results.append((dt, lon, zh, pinyin, ru, term_type, month_num, branch))

    # Сортировка по дате
    results.sort(key=lambda x: x[0])
    return results


def get_bazi_month(year, month, day, hour=0, minute=0, tz_offset_hours=0):
    """Определить месяц Ба Цзы для заданной даты.

    Возвращает (month_number 1-12, branch_char, year_for_bazi).
    month_number: 1=寅, 2=卯, ..., 12=丑
    """
    # Получить все Цзе термины за текущий и прошлый год
    from datetime import timezone as tz
    target = datetime(year, month, day, hour, minute, tzinfo=tz(timedelta(hours=tz_offset_hours)))
    target_utc = target.astimezone(timezone.utc)

    jie_terms = []
    for y in [year - 1, year, year + 1]:
        jie_terms.extend(get_solar_terms(y, jie_only=True))
    jie_terms.sort(key=lambda x: x[0])

    # Найти в какой интервал попадает дата
    bazi_month = None
    bazi_branch = None
    bazi_year = year

    for i in range(len(jie_terms) - 1):
        dt_start = jie_terms[i][0]
        dt_end = jie_terms[i + 1][0]
        if dt_start <= target_utc < dt_end:
            bazi_month = jie_terms[i][6]  # month_num
            bazi_branch = jie_terms[i][7]  # branch
            # Если месяц >= 11 (子, 丑) и мы в начале календарного года,
            # год Ба Цзы = предыдущий
            if bazi_month is not None and bazi_month >= 11 and month <= 2:
                bazi_year = year - 1
            # Если до 立春, год Ба Цзы = предыдущий
            # 立春 = month 1
            if bazi_month is not None:
                # Ли Чунь — начало 1-го месяца (寅)
                # Если текущий месяц Ба Цзы < 1 (т.е. 11 или 12),
                # а календарный год = year, значит год Ба Цзы = year - 1
                pass
            break

    # Определяем год Ба Цзы: до Ли Чунь = предыдущий год
    lichun = None
    for t in jie_terms:
        if t[2] == "立春" and t[0].year == year:
            lichun = t[0]
            break
    if lichun is None:
        for t in jie_terms:
            if t[2] == "立春" and t[0].year == year + 1:
                lichun = t[0]
                break

    if lichun and target_utc < lichun:
        bazi_year = year - 1

    return bazi_month, bazi_branch, bazi_year


# ── Небесные Стволы и Земные Ветви ────────────────────────────────────────

STEMS = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
BRANCHES = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
ANIMALS = ["Крыса", "Бык", "Тигр", "Кролик", "Дракон", "Змея",
           "Лошадь", "Коза", "Обезьяна", "Петух", "Собака", "Свинья"]
ELEMENTS = ["Дерево", "Дерево", "Огонь", "Огонь", "Земля", "Земля",
            "Металл", "Металл", "Вода", "Вода"]
POLARITIES = ["Ян", "Инь", "Ян", "Инь", "Ян", "Инь", "Ян", "Инь", "Ян", "Инь"]


def year_pillar(bazi_year):
    stem_idx = (bazi_year + 6) % 10
    branch_idx = (bazi_year + 8) % 12
    return STEMS[stem_idx], BRANCHES[branch_idx], stem_idx, branch_idx


def month_pillar(year_stem_idx, month_num):
    """month_num: 1=寅月 ... 12=丑月"""
    five_tigers = [2, 4, 6, 8, 0]  # 0-indexed stem for month 1
    base = five_tigers[year_stem_idx % 5]
    month_stem_idx = (base + month_num - 1) % 10
    month_branch_idx = (month_num + 1) % 12  # 寅=2(idx), 卯=3, ..., 丑=1
    return STEMS[month_stem_idx], BRANCHES[month_branch_idx], month_stem_idx, month_branch_idx


def day_pillar(year, month, day):
    jd = julian_day(year, month, day, 12)  # полдень
    jdn = int(jd + 0.5)
    stem_idx = (jdn + 9) % 10
    branch_idx = (jdn + 1) % 12
    return STEMS[stem_idx], BRANCHES[branch_idx], stem_idx, branch_idx


def hour_pillar(day_stem_idx, hour, minute=0):
    """Определить столп часа."""
    # Определить ветвь часа
    h = hour
    if h == 23:
        branch_idx = 0  # 子
    else:
        branch_idx = ((h + 1) // 2) % 12

    # Ствол часа (五鼠遁)
    five_rats = [0, 2, 4, 6, 8]  # 0-indexed stem for 子 hour
    base = five_rats[day_stem_idx % 5]
    stem_idx = (base + branch_idx) % 10

    return STEMS[stem_idx], BRANCHES[branch_idx], stem_idx, branch_idx


def full_chart(year, month, day, hour=None, minute=0, gender=None, tz_offset=8):
    """Полный расчёт карты Ба Цзы."""
    bazi_month, bazi_branch, bazi_year = get_bazi_month(year, month, day, hour or 12, minute, tz_offset)

    yr = year_pillar(bazi_year)
    mo = month_pillar(yr[2], bazi_month) if bazi_month else (None, None, None, None)
    dy = day_pillar(year, month, day)
    hr = hour_pillar(dy[2], hour, minute) if hour is not None else (None, None, None, None)

    print(f"\n{'='*60}")
    print(f"  Дата: {year}-{month:02d}-{day:02d}", end="")
    if hour is not None:
        print(f" {hour:02d}:{minute:02d} (UTC+{tz_offset})", end="")
    if gender:
        print(f"  Пол: {gender}", end="")
    print(f"\n  Год Ба Цзы: {bazi_year}  Месяц Ба Цзы: {bazi_month} ({bazi_branch})")
    print(f"{'='*60}")

    print(f"\n  {'Час (时)':>12}  {'День (日)':>12}  {'Месяц (月)':>12}  {'Год (年)':>12}")
    print(f"  {'─'*12}  {'─'*12}  {'─'*12}  {'─'*12}")

    def fmt(stem, branch):
        if stem is None:
            return "    ??    "
        si = STEMS.index(stem)
        return f"  {stem} {ELEMENTS[si][:3]}{'+' if si % 2 == 0 else '-'}"

    print(f"  {fmt(hr[0], hr[1]):>12}  {fmt(dy[0], dy[1]):>12}  {fmt(mo[0], mo[1]):>12}  {fmt(yr[0], yr[1]):>12}")

    def fmt_branch(branch):
        if branch is None:
            return "    ??    "
        bi = BRANCHES.index(branch)
        return f"  {branch} {ANIMALS[bi]}"

    print(f"  {fmt_branch(hr[1]):>12}  {fmt_branch(dy[1]):>12}  {fmt_branch(mo[1]):>12}  {fmt_branch(yr[1]):>12}")

    day_stem = dy[0]
    day_si = STEMS.index(day_stem)
    print(f"\n  Хозяин Дня: {day_stem} ({ELEMENTS[day_si]} {POLARITIES[day_si]})")

    # Столпы Удачи
    if gender and bazi_month and mo[2] is not None:
        luck_pillars = calc_luck_pillars(
            year, month, day, hour or 12, minute, tz_offset,
            gender, yr[2], mo[2], mo[3], bazi_month
        )
        if luck_pillars:
            start_age, direction, pillars = luck_pillars
            dir_str = "прямое (顺)" if direction == 1 else "обратное (逆)"
            print(f"\n  Столпы Удачи (大运): направление {dir_str}, начало с {start_age:.1f} лет")
            print(f"  {'─'*70}")
            print(f"  {'Возраст':>8}  {'Столп':>6}  {'Ствол':>12}  {'Ветвь':>12}")
            print(f"  {'─'*70}")
            for age, s_idx, b_idx in pillars:
                age_end = age + 10   # исключающая граница окна, как в bazi.py (issue #8)
                print(f"  {age:4.0f}-{age_end:<4.0f}  {STEMS[s_idx]}{BRANCHES[b_idx]:>4}    "
                      f"{STEMS[s_idx]} {ELEMENTS[s_idx][:3]}{'+' if s_idx % 2 == 0 else '-':>4}  "
                      f"{BRANCHES[b_idx]} {ANIMALS[b_idx]}")
    print()


def calc_luck_pillars(year, month, day, hour, minute, tz_offset,
                      gender, year_stem_idx, month_stem_idx, month_branch_idx, bazi_month):
    """Рассчитать Столпы Удачи (大运)."""
    from datetime import timezone as tz

    # Направление: Ян-муж / Инь-жен = прямое, Инь-муж / Ян-жен = обратное
    is_yang_year = (year_stem_idx % 2 == 0)  # 0-indexed: 0=甲(ян), 1=乙(инь)
    is_male = gender in ("мужской", "М", "м", "M", "m", "male")
    forward = (is_yang_year and is_male) or (not is_yang_year and not is_male)
    direction = 1 if forward else -1

    # Получить Цзе термины
    target = datetime(year, month, day, hour, minute,
                      tzinfo=tz(timedelta(hours=tz_offset)))
    target_utc = target.astimezone(timezone.utc)

    jie_terms = []
    for y in [year - 1, year, year + 1]:
        jie_terms.extend(get_solar_terms(y, jie_only=True))
    jie_terms.sort(key=lambda x: x[0])

    # Найти ближайший Цзе в нужном направлении
    target_jie = None
    if forward:
        # Следующий Цзе после рождения
        for t in jie_terms:
            if t[0] > target_utc:
                target_jie = t[0]
                break
    else:
        # Предыдущий Цзе до рождения
        for t in reversed(jie_terms):
            if t[0] <= target_utc:
                target_jie = t[0]
                break

    if target_jie is None:
        return None

    # Подсчёт дней
    diff = abs((target_jie - target_utc).total_seconds()) / 86400.0
    start_age = diff / 3.0  # 3 дня = 1 год

    # Столпы Удачи: от месячного столпа в нужном направлении
    pillars = []
    current_stem = month_stem_idx
    current_branch = month_branch_idx
    for i in range(10):
        current_stem = (current_stem + direction) % 10
        current_branch = (current_branch + direction) % 12
        age = start_age + i * 10
        pillars.append((age, current_stem, current_branch))

    return start_age, direction, pillars


# ── CLI ────────────────────────────────────────────────────────────────────

def print_terms(year, jie_only=False):
    terms = get_solar_terms(year, jie_only)
    label = "Цзе (节) — границы месяцев" if jie_only else "Все 24 солнечных термина"
    print(f"\n{label} за {year} год:")
    print(f"{'─'*75}")
    print(f"  {'Дата UTC':20} {'Долг.':>6}  {'中文':5}  {'Pinyin':14} {'Русский':28} {'Тип':3}")
    print(f"{'─'*75}")
    for dt, lon, zh, pinyin, ru, ttype, mnum, branch in terms:
        # Фильтруем по целевому году
        date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        month_info = f"  → М{mnum} {branch}" if mnum else ""
        print(f"  {date_str:20} {lon:6.1f}°  {zh:5}  {pinyin:14} {ru:28} {ttype:3}{month_info}")
    print()


def main():
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        return

    if args[0] == "--month":
        # Определить месяц Ба Цзы для даты
        if len(args) < 2:
            print("Использование: python3 jieqi.py --month YYYY-MM-DD [HH:MM] [UTC+N]")
            return
        parts = args[1].split("-")
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        hour, minute = None, 0
        tz_off = 8  # по умолчанию UTC+8 (Пекин)
        if len(args) > 2 and ":" in args[2]:
            hp = args[2].split(":")
            hour, minute = int(hp[0]), int(hp[1])
        if len(args) > 3 and args[-1].startswith("UTC"):
            tz_off = int(args[-1].replace("UTC", "").replace("+", ""))
        elif len(args) > 2 and args[-1].startswith("UTC"):
            tz_off = int(args[-1].replace("UTC", "").replace("+", ""))

        bm, bb, by = get_bazi_month(y, m, d, hour or 12, minute, tz_off)
        print(f"\nДата: {y}-{m:02d}-{d:02d}", end="")
        if hour is not None:
            print(f" {hour:02d}:{minute:02d}", end="")
        print(f" (UTC+{tz_off})")
        print(f"Год Ба Цзы: {by}")
        print(f"Месяц Ба Цзы: {bm} (ветвь: {bb})")
        return

    if args[0] == "--chart":
        # Полный расчёт карты
        if len(args) < 2:
            print("Использование: python3 jieqi.py --chart YYYY-MM-DD [HH:MM] [М/Ж] [UTC+N]")
            return
        parts = args[1].split("-")
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        hour, minute = None, 0
        gender = None
        tz_off = 8
        for a in args[2:]:
            if ":" in a:
                hp = a.split(":")
                hour, minute = int(hp[0]), int(hp[1])
            elif a in ("М", "м", "M", "m", "male", "мужской"):
                gender = "мужской"
            elif a in ("Ж", "ж", "F", "f", "female", "женский"):
                gender = "женский"
            elif a.startswith("UTC"):
                tz_off = int(a.replace("UTC", "").replace("+", ""))
        full_chart(y, m, d, hour, minute, gender, tz_off)
        return

    # Парсинг аргументов для вывода терминов
    jie_only = "jie" in args or "цзе" in args
    years = [a for a in args if a.isdigit()]

    if len(years) == 1:
        print_terms(int(years[0]), jie_only)
    elif len(years) >= 2:
        for y in range(int(years[0]), int(years[1]) + 1):
            print_terms(y, jie_only)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
