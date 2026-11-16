#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""
Калькулятор Цзы Вэй Доу Шу (紫微斗数) — Астрология Пурпурной Звезды.

Использование:
    python3 ziwei.py --lunar 1990 4 15 14 М    # лунный год/месяц/день, час, пол
    python3 ziwei.py --lunar 1990 4 15 14 М --stem 6  # с указанием ствола года (庚=6)
    python3 ziwei.py --solar 1990-05-15 14 М --json
    python3 ziwei.py --test
"""
import sys, json

STEMS = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
BRANCHES = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]

PALACE_NAMES = ["命宫","兄弟","夫妻","子女","财帛","疾厄","迁移","交友","事业","田宅","福德","父母"]
PALACE_NAMES_RU = ["Жизнь","Братья","Брак","Дети","Богатство","Здоровье",
                   "Путешествия","Друзья","Карьера","Дом","Благо","Родители"]

MAIN_STARS_ZW = ['紫微','天机','','太阳','武曲','天同','','','廉贞']
MAIN_STARS_TF = ['天府','太阴','贪狼','巨门','天相','天梁','七杀','破军']

# 四化 по стволу года: (化禄, 化权, 化科, 化忌)
SIHUA = [
    ('廉贞','破军','武曲','太阳'),  # 甲
    ('天机','天梁','紫微','太阴'),  # 乙
    ('天同','天机','文昌','廉贞'),  # 丙
    ('太阴','天同','天机','巨门'),  # 丁
    ('贪狼','太阴','右弼','天机'),  # 戊
    ('武曲','贪狼','天梁','文曲'),  # 己
    ('太阳','武曲','太阴','天同'),  # 庚
    ('巨门','太阳','文曲','文昌'),  # 辛
    ('天梁','紫微','左辅','武曲'),  # 壬
    ('破军','巨门','太阴','贪狼'),  # 癸
]
SIHUA_NAMES = ['化禄','化权','化科','化忌']

# ═══════════════════════════════════════════════════════════════
# 命宫 и 身宫
# ═══════════════════════════════════════════════════════════════

def ming_gong(month, hour_idx):
    """命宫 branch index. month=1-12 lunar, hour_idx=0-11."""
    return (1 + month - hour_idx) % 12

def shen_gong(month, hour_idx):
    """身宫 branch index."""
    return (1 + month + hour_idx) % 12

# ═══════════════════════════════════════════════════════════════
# 宫干 (Palace Heavenly Stems) — 五虎遁
# ═══════════════════════════════════════════════════════════════

def palace_stems(year_stem_idx):
    """Assign heavenly stems to all 12 palaces."""
    yin_stem = (year_stem_idx % 5 * 2 + 2) % 10
    stems = {}
    for i in range(12):
        branch = (2 + i) % 12  # start from 寅
        stems[branch] = (yin_stem + i) % 10
    return stems

# ═══════════════════════════════════════════════════════════════
# 五行局 (Wu Xing Ju)
# ═══════════════════════════════════════════════════════════════

# Na Yin → Ju: 30 pairs covering 60 Jia Zi
NAYIN_JU = [
    4,6,3,5,4, 6,2,5,4,3, 2,5,6,3,2,
    4,6,3,5,4, 6,2,5,4,3, 2,5,6,3,2,
]

def sexagenary_idx(si, bi):
    for n in range(60):
        if n%10 == si and n%12 == bi: return n
    return 0

def wu_xing_ju(ming_stem, ming_branch):
    """Determine Wu Xing Ju from Ming Gong stem-branch."""
    idx = sexagenary_idx(ming_stem, ming_branch)
    return NAYIN_JU[idx // 2]

JU_NAMES = {2:'水二局',3:'木三局',4:'金四局',5:'土五局',6:'火六局'}

# ═══════════════════════════════════════════════════════════════
# 紫微星 安星 (Zi Wei Placement)
# ═══════════════════════════════════════════════════════════════

def zi_wei_palace(day, ju):
    """紫微星 — классическое 安紫微星诀 (сверено с iztro/x-iztro 2026-11-09, issue #17).

    Для 局数 n и лунного дня d: k = наименьшее целое с k·n ≥ d (сколько «局» укладывается),
    r = k·n − d (сколько дней «заняли»). От 寅 отсчитать k дворцов (寅 = 1-й) — это база;
    затем при чётном r шагнуть ВПЕРЁД на r, при нечётном — НАЗАД на r.
    Пример: 土五局, день 15 → k=3, r=0 → 辰; 水二局, день 1 → k=1, r=1 → 丑.
    До 2026-11-09 стояла самодельная формула (верна только для дня 1): 42/60 карт получали
    неверное положение 紫微 и, как следствие, все 14 главных звёзд."""
    k = -(-day // ju)            # ceil(day / ju)
    r = k * ju - day
    pos = 2 + (k - 1)            # 寅 = 2, k-й дворец от 寅
    pos += r if r % 2 == 0 else -r
    return pos % 12

def tian_fu_palace(zw_branch):
    """天府 = mirror of 紫微 across 寅 axis."""
    return (4 - zw_branch) % 12

# ═══════════════════════════════════════════════════════════════
# 14 主星 Placement
# ═══════════════════════════════════════════════════════════════

def place_main_stars(zw_branch):
    """Place all 14 main stars. Returns dict: star_name → branch_index."""
    stars = {}

    # 紫微系 (offsets counterclockwise from 紫微)
    zw_offsets = {'紫微':0,'天机':-1,'太阳':-3,'武曲':-4,'天同':-5,'廉贞':-8}
    for star, off in zw_offsets.items():
        stars[star] = (zw_branch + off) % 12

    # 天府系 (offsets clockwise from 天府)
    tf = tian_fu_palace(zw_branch)
    # 府阴贪巨相梁杀 — подряд от 天府, затем три пустых дворца, 破军 = 天府 + 10 (не +7;
    # ошибка смещения найдена сверкой с x-iztro 2026-11-09 — 60/60 карт расходились только по 破军)
    tf_offsets = {'天府':0,'太阴':1,'贪狼':2,'巨门':3,'天相':4,'天梁':5,'七杀':6,'破军':10}
    for star, off in tf_offsets.items():
        stars[star] = (tf + off) % 12

    return stars

# ═══════════════════════════════════════════════════════════════
# 辅助星 (Auxiliary Stars)
# ═══════════════════════════════════════════════════════════════

def aux_stars(month, hour_idx, year_stem_idx, year_branch_idx):
    """Place important auxiliary stars."""
    stars = {}

    # 文昌 by hour (counterclockwise from 戌): 子→戌,丑→酉,寅→申...
    stars['文昌'] = (10 - hour_idx) % 12
    # 文曲 by hour (clockwise from 辰): 子→辰,丑→巳,寅→午...
    stars['文曲'] = (4 + hour_idx) % 12

    # 左辅 by month (clockwise from 辰): 正月→辰,二月→巳...
    stars['左辅'] = (3 + month) % 12
    # 右弼 by month (counterclockwise from 戌): 正月→戌,二月→酉...
    stars['右弼'] = (11 - month) % 12

    # 天魁/天钺 by year stem
    # 甲戊庚牛羊 (魁 丑, 钺 未) · 乙己鼠猴 (子/申) · 丙丁猪鸡 (亥/酉) · 六辛逢马虎 (午/寅) · 壬癸兔蛇 (卯/巳)
    # для 庚 стояло наоборот (魁 未, 钺 丑) — найдено сверкой с x-iztro 2026-11-09, исправлено
    TIANKUI = {0:1,1:0,2:11,3:11,4:1,5:0,6:1,7:6,8:3,9:3}
    TIANYUE = {0:7,1:8,2:9,3:9,4:7,5:8,6:7,7:2,8:5,9:5}
    stars['天魁'] = TIANKUI[year_stem_idx]
    stars['天钺'] = TIANYUE[year_stem_idx]

    # 禄存 by year stem
    LUCUN = {0:2,1:3,2:5,3:6,4:5,5:6,6:8,7:9,8:11,9:0}
    stars['禄存'] = LUCUN[year_stem_idx]

    # 擎羊 = 禄存 + 1, 陀罗 = 禄存 - 1
    lc = LUCUN[year_stem_idx]
    stars['擎羊'] = (lc + 1) % 12
    stars['陀罗'] = (lc - 1) % 12

    return stars

# ═══════════════════════════════════════════════════════════════
# 12 дворцов
# ═══════════════════════════════════════════════════════════════

def assign_palaces(ming_branch):
    """Assign 12 palace names to branch positions."""
    palaces = {}
    for i in range(12):
        branch = (ming_branch - i) % 12  # counterclockwise from 命宫
        palaces[branch] = (PALACE_NAMES[i], PALACE_NAMES_RU[i])
    return palaces

# ═══════════════════════════════════════════════════════════════
# ПОЛНЫЙ РАСЧЁТ
# ═══════════════════════════════════════════════════════════════

def build_chart(lunar_year, lunar_month, lunar_day, hour, gender, year_stem_idx=None):
    """Build complete ZWDS chart."""
    if year_stem_idx is None:
        year_stem_idx = (lunar_year + 6) % 10
    year_branch_idx = (lunar_year + 8) % 12

    # Hour branch
    hour_idx = 0 if hour == 23 else ((hour + 1) // 2) % 12

    # 命宫 / 身宫
    mg = ming_gong(lunar_month, hour_idx)
    sg = shen_gong(lunar_month, hour_idx)

    # Palace stems
    p_stems = palace_stems(year_stem_idx)

    # 五行局
    ju = wu_xing_ju(p_stems[mg], mg)

    # 紫微
    zw = zi_wei_palace(lunar_day, ju)

    # 14 主星
    main = place_main_stars(zw)

    # 辅助星
    aux = aux_stars(lunar_month, hour_idx, year_stem_idx, year_branch_idx)

    # 12 宫
    palaces = assign_palaces(mg)

    # 四化
    sihua = {}
    for i, name in enumerate(SIHUA_NAMES):
        star = SIHUA[year_stem_idx][i]
        sihua[star] = name

    return {
        'ming_gong': mg,
        'shen_gong': sg,
        'ju': ju,
        'ju_name': JU_NAMES[ju],
        'zi_wei': zw,
        'main_stars': main,
        'aux_stars': aux,
        'palaces': palaces,
        'palace_stems': p_stems,
        'sihua': sihua,
        'year_stem': year_stem_idx,
        'year_branch': year_branch_idx,
        'gender': gender,
    }

def solar_to_lunar(year, month, day):
    """Convert Gregorian date to Chinese lunar date using sxtwl when available."""
    try:
        import sxtwl
    except ImportError as exc:
        raise RuntimeError("sxtwl is required for Gregorian-to-lunar conversion") from exc

    lunar_day = sxtwl.fromSolar(year, month, day)
    return {
        "year": lunar_day.getLunarYear(),
        "month": lunar_day.getLunarMonth(),
        "day": lunar_day.getLunarDay(),
        "is_leap_month": bool(lunar_day.isLunarLeap()),
    }

def chart_json(chart, lunar_year, lunar_month, lunar_day, hour, source=None):
    palace_stars = {i: [] for i in range(12)}
    for star, bi in chart['main_stars'].items():
        palace_stars[bi].append({"name": star, "type": "main", "transformation": chart['sihua'].get(star)})
    for star, bi in chart['aux_stars'].items():
        palace_stars[bi].append({"name": star, "type": "aux", "transformation": chart['sihua'].get(star)})

    return {
        "input": {
            "lunar_year": lunar_year,
            "lunar_month": lunar_month,
            "lunar_day": lunar_day,
            "hour": hour,
            "source": source,
        },
        "year_pillar": f"{STEMS[chart['year_stem']]}{BRANCHES[chart['year_branch']]}",
        "ming_gong": {"index": chart['ming_gong'], "branch": BRANCHES[chart['ming_gong']]},
        "shen_gong": {"index": chart['shen_gong'], "branch": BRANCHES[chart['shen_gong']]},
        "ju": {"number": chart['ju'], "name": chart['ju_name']},
        "zi_wei": {"index": chart['zi_wei'], "branch": BRANCHES[chart['zi_wei']]},
        "palaces": {
            str(idx): {
                "branch": BRANCHES[idx],
                "name": chart['palaces'][idx][0],
                "name_ru": chart['palaces'][idx][1],
                "stem": STEMS[chart['palace_stems'][idx]],
                "stars": palace_stars[idx],
            }
            for idx in range(12)
        },
        "sihua": [{"star": star, "transformation": hua} for star, hua in chart['sihua'].items()],
        # конвенции (issue #31, по каталогу споров школ Renhuai123/ziwei-doushu school-config.ts): что выбрано, что нет
        "conventions": {
            "late_zi": "same_day — 23:xx = 子-час ТЕКУЩЕЙ лунной даты (мейнстрим排盘 и iztro: next_day — дата сдвигается на следующий день); не переключается — для рождений 23:00–23:59 показать обе карты",
            "leap_month": "闰月 считается тем же месяцем, что и обычный (prev-month / 整月当本月); мейнстрим: split — до 15-го как текущий, с 16-го как следующий; 倪海厦派: next-month; не переключается — для 闰月-рождений сказать в Тени",
            "geng_year_sihua": "阳武阴同 (庚: 太阳禄 武曲权 太阴科 天同忌) — мейнстрим, как iztro; варианты 阳武同阴/阳武府同/阳武府相/阳武同相 не реализованы",
            "year_boundary": "лунный год — с 正月初一 (не с 立春, как в Ба Цзы): ствол года 紫微 и Ба Цзы расходятся между 立春 и Новым годом",
            "solar_time": "истинное солнечное время НЕ применяется — час берётся как подан (мейнстрим 紫微-排盘); при желании пересчитай час заранее",
            "not_computed": "яркость звёзд (庙旺), 天马, 火星/铃星, 地空/地劫, 长生十二神, 截空/旬空, 大限/流年 (возраст 虚岁)",
            "oracles": "x-iztro 150/150 (2026-11-09); ziwei_cli.py Numerologist_skills (независимая реализация, 三合) 80/80 (2026-11-09)",
        },
        "raw": chart,
    }

# ═══════════════════════════════════════════════════════════════
# ВЫВОД
# ═══════════════════════════════════════════════════════════════

def print_chart(chart, lunar_year, lunar_month, lunar_day, hour):
    print(f"\n{'═'*64}")
    print(f"  紫微斗数 — ЦЗЫ ВЭЙ ДОУ ШУ")
    print(f"  Лунная дата: {lunar_year}年 {lunar_month}月 {lunar_day}日, {hour}:00")
    print(f"  Год: {STEMS[chart['year_stem']]}{BRANCHES[chart['year_branch']]}")
    print(f"  Пол: {chart['gender']}")
    mg, sg = chart['ming_gong'], chart['shen_gong']
    print(f"  命宫: {BRANCHES[mg]}  身宫: {BRANCHES[sg]}  {chart['ju_name']}")
    print(f"  紫微: {BRANCHES[chart['zi_wei']]}")
    print(f"{'═'*64}")

    # Собрать все звёзды по дворцам
    palace_stars = {i: [] for i in range(12)}
    for star, bi in chart['main_stars'].items():
        tag = chart['sihua'].get(star, '')
        palace_stars[bi].append(f"{star}{f'({tag})' if tag else ''}")
    for star, bi in chart['aux_stars'].items():
        tag = chart['sihua'].get(star, '')
        palace_stars[bi].append(f"{star}{f'({tag})' if tag else ''}")

    # Layout: 4 строки
    layout = [
        [5, 4, 3, 2],   # top
        [6, -1, -1, 1],  # middle-top
        [7, -1, -1, 0],  # middle-bottom
        [8, 9, 10, 11],  # bottom
    ]

    for row in layout:
        # Top border
        line = ""
        for p in row:
            if p == -1:
                line += "          "
            else:
                line += f"┌{'─'*14}┐"
        print(f"  {line}")

        # Palace name + branch
        line = ""
        for p in row:
            if p == -1:
                line += "          "
            else:
                pname = chart['palaces'].get(p, ('',''))[0]
                pname_r = chart['palaces'].get(p, ('',''))[1]
                marker = ""
                if p == mg: marker = "★"
                elif p == sg: marker = "◆"
                line += f"│{BRANCHES[p]} {pname[:4]:<4}{marker:>2}{STEMS[chart['palace_stems'].get(p,0)]:>3}│"
        print(f"  {line}")

        # Stars (up to 3 lines)
        for srow in range(3):
            line = ""
            for p in row:
                if p == -1:
                    line += "          "
                else:
                    st_list = palace_stars.get(p, [])
                    if srow < len(st_list):
                        s = st_list[srow]
                        line += f"│ {s:<13}│"
                    else:
                        line += f"│{' '*14}│"
            print(f"  {line}")

        # Bottom border
        line = ""
        for p in row:
            if p == -1:
                line += "          "
            else:
                line += f"└{'─'*14}┘"
        print(f"  {line}")

    # 四化 summary
    print(f"\n  四化 (Четыре Трансформации):")
    for star, hua in chart['sihua'].items():
        print(f"    {star} → {hua}")

    # Key analysis
    mg_stars = palace_stars.get(mg, [])
    print(f"\n  命宫 ({BRANCHES[mg]}) звёзды: {', '.join(mg_stars) if mg_stars else '无主星 (пустой дворец)'}")

    print(f"\n{'═'*64}\n")

# ═══════════════════════════════════════════════════════════════
# ТЕСТЫ
# ═══════════════════════════════════════════════════════════════

def run_tests():
    # Test Ming Gong
    assert ming_gong(1, 0) == 2, "Ming Gong: month 1, hour 子 should be 寅(2)"
    assert ming_gong(1, 1) == 1, "Ming Gong: month 1, hour 丑 should be 丑(1)"
    print("  ✓ 命宫 calculation correct")

    # Test Shen Gong
    assert shen_gong(1, 0) == 2, "Shen Gong: month 1, hour 子 should be 寅(2)"
    print("  ✓ 身宫 calculation correct")

    # Test Zi Wei placement
    assert zi_wei_palace(1, 2) == 1, "Zi Wei: day 1, Ju 2 should be 丑(1)"
    assert zi_wei_palace(2, 2) == 2, "Zi Wei: day 2, Ju 2 should be 寅(2)"
    assert zi_wei_palace(1, 3) == 4, "Zi Wei: day 1, Ju 3 should be 辰(4)"
    print("  ✓ 紫微 placement correct")

    # Test Tian Fu
    assert tian_fu_palace(2) == 2, "Tian Fu mirror of 寅 should be 寅"
    assert tian_fu_palace(3) == 1, "Tian Fu mirror of 卯 should be 丑"
    print("  ✓ 天府 mirror correct")

    # Full chart test
    chart = build_chart(1990, 4, 15, 14, "мужской", year_stem_idx=6)
    print(f"  ✓ Full chart built: 命宫={BRANCHES[chart['ming_gong']]}, {chart['ju_name']}")

    print("\n  Все тесты пройдены!")

# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__, file=sys.stderr); sys.exit(2)   # пустой вызов — подсказка в stderr и код 2, как у остальных

    json_mode = "--json" in args
    args = [a for a in args if a != "--json"]

    if args[0] == '--test':
        run_tests(); return

    def parse_stem(argv):
        ys = None
        for idx, a in enumerate(argv):
            if a.startswith('--stem='):
                return int(a.split('=', 1)[1])
            if a == '--stem':
                continue
            try:
                ys = int(a)
            except ValueError:
                pass
        if '--stem' in argv:
            idx = argv.index('--stem')
            if idx + 1 < len(argv):
                return int(argv[idx + 1])
        return ys

    if args[0] in ('--lunar', '--solar'):
        source = {"calendar": "lunar"}
        if args[0] == '--lunar':
            ly = int(args[1])
            lm = int(args[2])
            ld = int(args[3])
            lh = int(args[4])
            gender_arg = args[5]
            rest = args[6:]
        else:
            y, m, d = [int(x) for x in args[1].split('-')]
            lunar = solar_to_lunar(y, m, d)
            ly, lm, ld = lunar["year"], lunar["month"], lunar["day"]
            lh = int(args[2])
            gender_arg = args[3]
            rest = args[4:]
            source = {
                "calendar": "gregorian",
                "date": f"{y}-{m:02d}-{d:02d}",
                "converted_lunar": lunar,
            }

        import cli_errors
        if gender_arg in ('М','м','M','m','male'):
            gender = "мужской"
        elif gender_arg in ('Ж','ж','F','f','female'):
            gender = "женский"
        else:
            raise cli_errors.InputError(f"пол «{gender_arg}» — ожидается М или Ж")
        if not (1 <= lm <= 12 and 1 <= ld <= 30 and 0 <= lh <= 23):
            raise cli_errors.InputError(f"лунная дата и час вне диапазона: месяц {lm} (1–12), день {ld} (1–30), час {lh} (0–23)")
        ys = parse_stem(rest)

        chart = build_chart(ly, lm, ld, lh, gender, year_stem_idx=ys)
        if json_mode:
            print(json.dumps(chart_json(chart, ly, lm, ld, lh, source=source), ensure_ascii=False, indent=2))
        else:
            if source["calendar"] == "gregorian":
                leap = " leap" if source["converted_lunar"]["is_leap_month"] else ""
                print(f"Gregorian {source['date']} → lunar {ly}-{lm}-{ld}{leap}")
            print_chart(chart, ly, lm, ld, lh)
    else:
        print(__doc__, file=sys.stderr); sys.exit(2)

if __name__ == '__main__':
    import cli_errors
    cli_errors.run(main)
