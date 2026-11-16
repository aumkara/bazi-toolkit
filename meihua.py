#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""
meihua.py — калькулятор Мэй Хуа И Шу (梅花易数, Нумерология Цветка Сливы): гексаграмма по числам или по моменту.

Считает только то, что считается: 本卦 (главная), 动爻 (изменяющаяся черта), 变卦 (изменённая), 互卦 (взаимная),
错卦 (дополнение), 综卦 (переворот), 体/用 и их стихийное отношение, 卦气 (сила 体 по сезону). Толкование — за скиллом.

Использование:
    python3 meihua.py --numbers 17 29              # два числа: верх = N1 mod 8, низ = N2 mod 8, 动爻 = (N1+N2) mod 6
    python3 meihua.py --numbers 17 29 5            # три числа: 动爻 = N3 mod 6
    python3 meihua.py --time 2026-04-08 14:30      # по моменту (时间起卦): лунная дата — через lunar-python
    python3 meihua.py --time 2026-04-08 14:30 --lunar 2026 2 21   # лунный год/месяц/день заданы явно (без зависимостей)
    python3 meihua.py --time 2026-04-08 14:30 --minutes           # современное расширение: минуты прибавляются к сумме 动爻
    python3 meihua.py --numbers 17 29 --month 3    # лунный месяц для 卦气, когда момент не задан
    python3 meihua.py --test
Везде можно добавить --json. Нумерация триграмм — 先天 (1 乾 2 兑 3 离 4 震 5 巽 6 坎 7 艮 8 坤), гексаграмм — 文王.
Зависимостей нет; lunar-python нужен только для --time без --lunar.
"""
import json
import sys

import cli_errors

# триграммы 先天: номер → (中文, черты снизу вверх (1 = ян), стихия, символ, рус.)
TRIGRAMS = {
    1: ("乾", (1, 1, 1), "Металл", "☰", "Цянь"), 2: ("兑", (1, 1, 0), "Металл", "☱", "Дуй"),
    3: ("离", (1, 0, 1), "Огонь", "☲", "Ли"),     4: ("震", (1, 0, 0), "Дерево", "☳", "Чжэнь"),
    5: ("巽", (0, 1, 1), "Дерево", "☴", "Сюнь"),  6: ("坎", (0, 1, 0), "Вода", "☵", "Кань"),
    7: ("艮", (0, 0, 1), "Земля", "☶", "Гэнь"),   8: ("坤", (0, 0, 0), "Земля", "☷", "Кунь"),
}
LINES_TO_TRI = {v[1]: k for k, v in TRIGRAMS.items()}
TRI_BY_NAME = {v[0]: k for k, v in TRIGRAMS.items()}
PRODUCES = {"Дерево": "Огонь", "Огонь": "Земля", "Земля": "Металл", "Металл": "Вода", "Вода": "Дерево"}
CONTROLS = {"Дерево": "Земля", "Земля": "Вода", "Вода": "Огонь", "Огонь": "Металл", "Металл": "Дерево"}

# 64 гексаграммы по порядку 文王: номер → (中文, верхняя, нижняя, рус. транскрипция, значение)
# (таблица совпадает с §1.4 skills/meihua/SKILL.md — сверяется в --test)
HEXAGRAMS = {
    1: ("乾", "乾", "乾", "Цянь", "Творчество"),
    2: ("坤", "坤", "坤", "Кунь", "Исполнение"),
    3: ("屯", "坎", "震", "Чжунь", "Начальная Трудность"),
    4: ("蒙", "艮", "坎", "Мэн", "Незрелость"),
    5: ("需", "坎", "乾", "Сюй", "Ожидание"),
    6: ("讼", "乾", "坎", "Сун", "Тяжба"),
    7: ("师", "坤", "坎", "Ши", "Войско"),
    8: ("比", "坎", "坤", "Би", "Близость"),
    9: ("小畜", "巽", "乾", "Сяо Чу", "Воспитание Малым"),
    10: ("履", "乾", "兑", "Люй", "Поступь"),
    11: ("泰", "坤", "乾", "Тай", "Расцвет"),
    12: ("否", "乾", "坤", "Пи", "Упадок"),
    13: ("同人", "乾", "离", "Тун Жэнь", "Единомышленники"),
    14: ("大有", "离", "乾", "Да Ю", "Великое Владение"),
    15: ("谦", "坤", "艮", "Цянь", "Смирение"),
    16: ("豫", "震", "坤", "Юй", "Вольность"),
    17: ("随", "兑", "震", "Суй", "Следование"),
    18: ("蛊", "艮", "巽", "Гу", "Исправление Порчи"),
    19: ("临", "坤", "兑", "Линь", "Посещение"),
    20: ("观", "巽", "坤", "Гуань", "Созерцание"),
    21: ("噬嗑", "离", "震", "Ши Хэ", "Стиснутые Зубы"),
    22: ("贲", "艮", "离", "Би", "Убранство"),
    23: ("剥", "艮", "坤", "Бо", "Разрушение"),
    24: ("复", "坤", "震", "Фу", "Возврат"),
    25: ("无妄", "乾", "震", "У Ван", "Безрассудство"),
    26: ("大畜", "艮", "乾", "Да Чу", "Воспитание Великим"),
    27: ("颐", "艮", "震", "И", "Питание"),
    28: ("大过", "兑", "巽", "Да Го", "Переразвитие Великого"),
    29: ("坎", "坎", "坎", "Кань", "Бездна"),
    30: ("离", "离", "离", "Ли", "Сияние"),
    31: ("咸", "兑", "艮", "Сянь", "Взаимодействие"),
    32: ("恒", "震", "巽", "Хэн", "Постоянство"),
    33: ("遁", "乾", "艮", "Дунь", "Отступление"),
    34: ("大壮", "震", "乾", "Да Чжуан", "Мощь Великого"),
    35: ("晋", "离", "坤", "Цзинь", "Продвижение"),
    36: ("明夷", "坤", "离", "Мин И", "Поражение Света"),
    37: ("家人", "巽", "离", "Цзя Жэнь", "Семья"),
    38: ("睽", "离", "兑", "Куй", "Разлад"),
    39: ("蹇", "坎", "艮", "Цзянь", "Препятствие"),
    40: ("解", "震", "坎", "Цзе", "Разрешение"),
    41: ("损", "艮", "兑", "Сунь", "Убыль"),
    42: ("益", "巽", "震", "И", "Приумножение"),
    43: ("夬", "兑", "乾", "Гуай", "Прорыв"),
    44: ("姤", "乾", "巽", "Гоу", "Встреча"),
    45: ("萃", "兑", "坤", "Цуй", "Собирание"),
    46: ("升", "坤", "巽", "Шэн", "Подъём"),
    47: ("困", "兑", "坎", "Кунь", "Истощение"),
    48: ("井", "坎", "巽", "Цзин", "Колодец"),
    49: ("革", "兑", "离", "Гэ", "Переворот"),
    50: ("鼎", "离", "巽", "Дин", "Жертвенник"),
    51: ("震", "震", "震", "Чжэнь", "Возбуждение"),
    52: ("艮", "艮", "艮", "Гэнь", "Покой"),
    53: ("渐", "巽", "艮", "Цзянь", "Постепенное"),
    54: ("归妹", "震", "兑", "Гуй Мэй", "Невеста"),
    55: ("丰", "震", "离", "Фэн", "Изобилие"),
    56: ("旅", "离", "艮", "Люй", "Странствие"),
    57: ("巽", "巽", "巽", "Сюнь", "Проникновение"),
    58: ("兑", "兑", "兑", "Дуй", "Радость"),
    59: ("涣", "巽", "坎", "Хуань", "Рассредоточение"),
    60: ("节", "坎", "兑", "Цзе", "Ограничение"),
    61: ("中孚", "巽", "兑", "Чжун Фу", "Внутренняя Правда"),
    62: ("小过", "震", "艮", "Сяо Го", "Переразвитие Малого"),
    63: ("既济", "坎", "离", "Цзи Цзи", "Завершение"),
    64: ("未济", "离", "坎", "Вэй Цзи", "Незавершённость"),
}
HEX_BY_TRI = {(TRI_BY_NAME[u], TRI_BY_NAME[lo]): n for n, (_, u, lo, _, _) in HEXAGRAMS.items()}

# 卦气: стихия сезона по лунному месяцу (§3.3 скилла: 1–2 木, 3 土, 4–5 火, 6 土, 7–8 金, 9 土, 10–11 水, 12 土) — конвенция
SEASON_ELEMENT = {1: "Дерево", 2: "Дерево", 3: "Земля", 4: "Огонь", 5: "Огонь", 6: "Земля",
                  7: "Металл", 8: "Металл", 9: "Земля", 10: "Вода", 11: "Вода", 12: "Земля"}
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def mod(n, k):
    r = n % k
    return k if r == 0 else r


def hexagram(upper, lower):
    """(upper, lower: номера триграмм) → dict с номером, именем, чертами снизу вверх."""
    n = HEX_BY_TRI[(upper, lower)]
    zh, _, _, ru, meaning = HEXAGRAMS[n]
    return {"number": n, "name": zh, "name_ru": ru, "meaning": meaning,
            "upper": tri(upper), "lower": tri(lower),
            "lines": list(TRIGRAMS[lower][1]) + list(TRIGRAMS[upper][1])}


def tri(k):
    zh, _, el, sym, ru = TRIGRAMS[k]
    return {"index": k, "name": zh, "name_ru": ru, "symbol": sym, "element": el}


def from_lines(lines):
    lower = LINES_TO_TRI[tuple(lines[0:3])]
    upper = LINES_TO_TRI[tuple(lines[3:6])]
    return hexagram(upper, lower)


def relation(a, b):
    """Отношение стихии a к стихии b: 比和 | a生b | a克b | b生a | b克a."""
    if a == b:
        return "比和"
    if PRODUCES[a] == b:
        return "生"      # a порождает b
    if CONTROLS[a] == b:
        return "克"      # a контролирует b
    if PRODUCES[b] == a:
        return "被生"    # a порождается b
    return "被克"        # a контролируется b


def ti_yong(ben, moving):
    """体 — триграмма без 动爻, 用 — с ней. Возвращает блок анализа."""
    yong_side = "lower" if moving <= 3 else "upper"
    ti_side = "upper" if yong_side == "lower" else "lower"
    ti, yong = ben[ti_side], ben[yong_side]
    rel = relation(yong["element"], ti["element"])
    verdict = {"比和": ("用 и 体 одной стихии — 比和", "благоприятно, ровно"),
               "生": ("用 порождает 体 (用生体)", "благоприятно: ситуация питает спрашивающего"),
               "克": ("用 подавляет 体 (用克体)", "неблагоприятно: давление извне сильнее"),
               "被生": ("体 порождает 用 (体生用)", "расход: спрашивающий отдаёт больше, чем получает"),
               "被克": ("体 подавляет 用 (体克用)", "благоприятно, но усилием: спрашивающий одолевает")}[rel]
    return {"ti": dict(ti, side=ti_side), "yong": dict(yong, side=yong_side), "relation": rel,
            "relation_text": verdict[0], "verdict": verdict[1]}


def guaqi(ti_element, month):
    """卦气 — сила стихии 体 по сезону лунного месяца: 旺 相 休 囚 死."""
    if month is None:
        return None
    s = SEASON_ELEMENT[month]
    if ti_element == s: state, text = "旺", "в своём сезоне — сильна"
    elif PRODUCES[s] == ti_element: state, text = "相", "сезон её порождает — поддержана"
    elif PRODUCES[ti_element] == s: state, text = "休", "она порождает сезон — отдыхает"
    elif CONTROLS[ti_element] == s: state, text = "囚", "она контролирует сезон — стеснена"
    else: state, text = "死", "сезон её контролирует — слаба"
    return {"month": month, "season_element": s, "state": state, "text": text,
            "note": "конвенция §3.3 скилла: 3/6/9/12-й месяцы — Земля; [интерпретация]"}


def cast(upper, lower, moving, month=None, meta=None):
    ben = hexagram(upper, lower)
    lines = ben["lines"]
    changed = lines.copy(); changed[moving - 1] ^= 1
    bian = from_lines(changed)
    hu = from_lines(lines[1:4] + lines[2:5])
    cuo = from_lines([1 - x for x in lines])
    zong_lines = lines[::-1]
    zong = None if zong_lines == lines else from_lines(zong_lines)
    ty = ti_yong(ben, moving)
    ti_el = ty["ti"]["element"]
    bian_tri = bian[ty["yong"]["side"]]
    return {
        "system": "梅花易数 Мэй Хуа И Шу", "input": meta or {},
        "ben_gua": ben, "moving_line": moving,
        "bian_gua": dict(bian, changed_trigram=bian_tri, relation_to_ti=relation(bian_tri["element"], ti_el)),
        "hu_gua": dict(hu, upper_relation_to_ti=relation(hu["upper"]["element"], ti_el),
                       lower_relation_to_ti=relation(hu["lower"]["element"], ti_el)),
        "cuo_gua": cuo,
        "zong_gua": zong,                   # None — гексаграмма симметрична (乾 坤 颐 大过 坎 离 中孚 小过)
        "ti_yong": ty,
        "guaqi": guaqi(ti_el, month),
        "conventions": {"trigram_numbering": "先天 (1 乾 … 8 坤)", "hexagram_numbering": "文王",
                        "hu_gua": "черты 2-3-4 → нижняя, 3-4-5 → верхняя", "zong_gua": "переворот черт 1↔6",
                        "season": "по лунному месяцу, 3/6/9/12 — Земля", "minutes_mode": bool((meta or {}).get("minutes_mode"))},
    }


@cli_errors.parser
def cast_numbers(nums, month=None):
    if len(nums) == 2:
        n1, n2 = nums; moving = mod(n1 + n2, 6); how = "два числа: 动爻 = (N1+N2) mod 6"
    elif len(nums) == 3:
        n1, n2, n3 = nums; moving = mod(n3, 6); how = "три числа: 动爻 = N3 mod 6"
    else:
        raise ValueError("--numbers ожидает 2 или 3 числа")
    return cast(mod(n1, 8), mod(n2, 8), moving, month,
                {"method": "数字起卦", "numbers": nums, "formula": how})


def lunar_from_solar(y, m, d, h, mi):
    """(лунный год, месяц (положительный; is_leap отдельно), день, ветвь года) через lunar-python."""
    from lunar_python import Solar  # noqa: PLC0415
    lun = Solar.fromYmdHms(y, m, d, h, mi, 0).getLunar()
    return lun.getYear(), abs(lun.getMonth()), lun.getDay(), lun.getYearZhi(), lun.getMonth() < 0


def cast_time(y, m, d, h, mi, lunar=None, minutes_mode=False):
    note = None
    if lunar:
        ly, lm, ld = lunar; leap = False
        year_branch = mod(ly - 3, 12)                      # 子 = 1 … 亥 = 12 по лунному году
    else:
        try:
            ly, lm, ld, zhi, leap = lunar_from_solar(y, m, d, h, mi)
        except ImportError:
            print("ОШИБКА: для --time без --lunar нужен lunar-python (.venv/bin/pip install lunar-python) "
                  "или задай лунную дату явно: --lunar ГОД МЕСЯЦ ДЕНЬ", file=sys.stderr)
            sys.exit(2)
        year_branch = BRANCHES.index(zhi) + 1
        if leap:
            note = f"лунный месяц {lm} — вставной (闰月); взят его номер, школы расходятся"
    hour_branch = ((h + 1) // 2) % 12 + 1                   # 23–00 → 1 子, 01–02 → 2 丑 … 21–22 → 12 亥
    s_upper = year_branch + lm + ld
    s_full = s_upper + hour_branch
    s_moving = s_full + (mi if minutes_mode else 0)
    meta = {"method": "时间起卦", "solar": f"{y:04d}-{m:02d}-{d:02d} {h:02d}:{mi:02d}",
            "lunar": {"year": ly, "month": lm, "day": ld, "year_branch": BRANCHES[year_branch - 1], "year_branch_no": year_branch,
                      "hour_branch": BRANCHES[hour_branch - 1], "hour_branch_no": hour_branch, "leap_month": leap},
            "sums": {"upper": s_upper, "full": s_full, "moving": s_moving}, "minutes_mode": minutes_mode,
            "formula": "верх = (год+месяц+день) mod 8; низ = (… + час) mod 8; 动爻 = (… + час" + (" + минуты" if minutes_mode else "") + ") mod 6"}
    if note:
        meta["note"] = note
    if minutes_mode:
        meta["warning"] = "минутный режим — современное расширение, не классический 时辰; сказать в выводе"
    return cast(mod(s_upper, 8), mod(s_full, 8), mod(s_moving, 6), lm, meta)


def draw(lines):
    return "\n".join(("  ━━━━━━━  " if x else "  ━━━ ━━━  ") + f"{i}" for i, x in reversed(list(enumerate(lines, start=1))))


def print_text(r):
    b, ty = r["ben_gua"], r["ti_yong"]
    print(f"\n  梅花易数 — {r['input'].get('method', '')}  {r['input'].get('solar', '')}")
    if "lunar" in r["input"]:
        L = r["input"]["lunar"]; print(f"  лунная дата {L['year']}-{L['month']}-{L['day']} ({L['year_branch']}-год {L['year_branch_no']}, час {L['hour_branch']} {L['hour_branch_no']}); суммы {r['input']['sums']}")
    if "numbers" in r["input"]:
        print(f"  числа {r['input']['numbers']}")
    print(f"\n  本卦 {b['number']}. {b['name']} {b['name_ru']} ({b['meaning']}) — {b['upper']['symbol']} над {b['lower']['symbol']}, 动爻 {r['moving_line']}")
    print(draw(b["lines"]))
    for key, label in (("hu_gua", "互卦"), ("bian_gua", "变卦"), ("cuo_gua", "错卦"), ("zong_gua", "综卦")):
        g = r[key]
        print(f"  {label}: " + (f"{g['number']}. {g['name']} {g['name_ru']} ({g['meaning']})" if g else "нет — гексаграмма симметрична"))
    print(f"\n  体 {ty['ti']['name']} {ty['ti']['element']} ({ty['ti']['side']}) · 用 {ty['yong']['name']} {ty['yong']['element']} ({ty['yong']['side']}) → {ty['relation_text']}: {ty['verdict']}")
    print(f"  变卦: сменившаяся триграмма {r['bian_gua']['changed_trigram']['name']} {r['bian_gua']['changed_trigram']['element']} → к 体: {r['bian_gua']['relation_to_ti']}")
    print(f"  互卦: верх → 体 {r['hu_gua']['upper_relation_to_ti']}, низ → 体 {r['hu_gua']['lower_relation_to_ti']}")
    if r["guaqi"]:
        g = r["guaqi"]; print(f"  卦气: месяц {g['month']} ({g['season_element']}) → 体 {g['state']} — {g['text']}")
    if r["input"].get("warning"):
        print(f"  ⚠ {r['input']['warning']}")
    print()


def _test():
    ok = True
    def chk(cond, msg):
        nonlocal ok
        ok &= bool(cond); print(f"[{'PASS' if cond else 'FAIL'}] {msg}")
    chk(sorted(HEXAGRAMS) == list(range(1, 65)) and len(HEX_BY_TRI) == 64, "64 гексаграммы, все пары триграмм уникальны")
    anchors = {1: ("乾", "乾"), 2: ("坤", "坤"), 11: ("坤", "乾"), 12: ("乾", "坤"), 63: ("坎", "离"), 64: ("离", "坎"), 43: ("兑", "乾"), 3: ("坎", "震")}
    chk(all(HEXAGRAMS[n][1:3] == uv for n, uv in anchors.items()), "якоря 文王: 1 乾, 2 坤, 11 泰 (坤/乾), 12 否, 63 既济 (坎/离), 64 未济, 43 夬 (兑/乾), 3 屯 (坎/震)")
    # сверка с таблицей §1.4 скилла (строка — нижняя, столбец — верхняя), если файл рядом
    import os, re
    skill = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills", "meihua", "SKILL.md")
    if os.path.exists(skill):
        TRI = "乾兑离震巽坎艮坤"; bad = []
        for l in open(skill, encoding="utf-8"):
            if re.match(r"\| \*\*\d ", l):
                cells = [c.strip() for c in l.strip().strip("|").split("|")]
                lo = int(cells[0].split()[0].strip("*"))
                for up, c in enumerate(cells[1:9], start=1):
                    m = re.match(r"(\d+)\.\s+(\S+)", c)
                    if HEX_BY_TRI[(up, lo)] != int(m.group(1)) or HEXAGRAMS[HEX_BY_TRI[(up, lo)]][0] != m.group(2):
                        bad.append((TRI[up - 1], TRI[lo - 1], c[:12]))
        chk(not bad, f"таблица §1.4 скилла = код (строка — нижняя, столбец — верхняя): расхождений {len(bad)} {bad[:3]}")
    r = cast_numbers([17, 29])
    chk(r["ben_gua"]["number"] == 44 and r["moving_line"] == 4 and r["bian_gua"]["number"] == 57
        and r["ti_yong"]["ti"]["name"] == "巽" and r["ti_yong"]["relation"] == "克",
        f"числа 17, 29 → {r['ben_gua']['number']} {r['ben_gua']['name']}, 动爻 {r['moving_line']}, 变卦 {r['bian_gua']['number']} {r['bian_gua']['name']}, "
        f"体 {r['ti_yong']['ti']['name']} ← 用 {r['ti_yong']['relation']} (ожидалось 44 姤, 4, 57 巽, 体 巽, 用克体)")
    tai = hexagram(8, 1)   # 泰
    hu = from_lines(tai["lines"][1:4] + tai["lines"][2:5])
    chk(hu["number"] == 54, f"互卦 泰 → {hu['number']} {hu['name']} (ожидалось 54 归妹)")
    r = cast(6, 4, 1)      # 屯
    chk(r["zong_gua"]["number"] == 4 and r["cuo_gua"]["number"] == 50, f"屯: 综卦 {r['zong_gua']['number']} {r['zong_gua']['name']} (ожидалось 4 蒙), 错卦 {r['cuo_gua']['number']} {r['cuo_gua']['name']} (ожидалось 50 鼎)")
    sym = [HEXAGRAMS[n][0] for n in range(1, 65) if cast(TRI_BY_NAME[HEXAGRAMS[n][1]], TRI_BY_NAME[HEXAGRAMS[n][2]], 1)["zong_gua"] is None]
    chk(sym == ["乾", "坤", "颐", "大过", "坎", "离", "中孚", "小过"], f"симметричные (без 综卦): {sym}")
    r = cast_time(2026, 4, 8, 14, 30, lunar=(2026, 2, 21))
    chk(r["ben_gua"]["number"] == 29 and r["moving_line"] == 2 and r["input"]["sums"] == {"upper": 30, "full": 38, "moving": 38},
        f"时间起卦 2026-04-08 14:30, лунная 2026-2-21 → суммы {r['input']['sums']}, {r['ben_gua']['number']} {r['ben_gua']['name']} 动爻 {r['moving_line']} (ожидалось 30/38/38, 29 坎, 2)")
    chk(guaqi("Дерево", 1)["state"] == "旺" and guaqi("Металл", 1)["state"] == "囚" and guaqi("Земля", 3)["state"] == "旺"
        and guaqi("Вода", 4)["state"] == "囚" and guaqi("Металл", 4)["state"] == "死" and guaqi("Огонь", 1)["state"] == "相",
        "卦气: Дерево в 1-м месяце 旺, Металл 囚, Огонь 相; Земля в 3-м 旺; в 4-м (Огонь) Вода 囚, Металл 死")
    try:
        from lunar_python import Solar  # noqa: F401
        r2 = cast_time(2026, 4, 8, 14, 30)
        chk(r2["input"]["lunar"]["year_branch"] == "午", f"lunar-python: 2026-04-08 → лунная {r2['input']['lunar']['year']}-{r2['input']['lunar']['month']}-{r2['input']['lunar']['day']}, год 午")
    except ImportError:
        print("[SKIP] lunar-python не установлен — --time без --lunar не проверялся")
    print("meihua --test:", "ЗЕЛЁНО ✓" if ok else "КРАСНОЕ ✗")
    return 0 if ok else 1


def main():
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(__doc__); return 0
    if not args:
        print(__doc__, file=sys.stderr); return 2   # пустой вызов — подсказка в stderr и код 2, как у остальных
    if "--test" in args:
        return _test()
    json_mode = "--json" in args
    month = int(args[args.index("--month") + 1]) if "--month" in args else None
    if "--numbers" in args:
        i = args.index("--numbers") + 1; nums = []
        while i < len(args) and args[i].lstrip("-").isdigit() and not args[i].startswith("--"):
            nums.append(int(args[i])); i += 1
        r = cast_numbers(nums, month)
    elif "--time" in args:
        i = args.index("--time"); y, m, d = map(int, args[i + 1].split("-")); h, mi = map(int, args[i + 2].split(":"))
        lunar = None
        if "--lunar" in args:
            j = args.index("--lunar"); lunar = (int(args[j + 1]), int(args[j + 2]), int(args[j + 3]))
        r = cast_time(y, m, d, h, mi, lunar=lunar, minutes_mode="--minutes" in args)
    else:
        print("нужно --numbers N1 N2 [N3] или --time ГГГГ-ММ-ДД ЧЧ:ММ [--lunar Г М Д] [--minutes]", file=sys.stderr); return 2
    if json_mode:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print_text(r)
    return 0


if __name__ == "__main__":
    import cli_errors
    cli_errors.run(main)
