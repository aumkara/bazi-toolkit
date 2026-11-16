#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""
Калькулятор Ци Мэнь Дунь Цзя (奇门遁甲) — метод вращающихся пластин (转盘).

Использование:
    python3 qimen.py                        # текущее время, UTC+8
    python3 qimen.py 2026-04-08 14:30       # конкретная дата
    python3 qimen.py 2026-04-08 14:30 UTC+3
    python3 qimen.py 2026-04-08 14:30 UTC+3 --json
    python3 qimen.py 2026-04-08 14:30 UTC+3 --method zhirun   # 置闰 (超神接气); по умолчанию 拆补
    python3 qimen.py --test
"""
import sys, math, json
from datetime import datetime, timedelta, timezone

# Импорт астрономии из jieqi.py
import os; sys.path.insert(0, os.path.dirname(__file__))
from jieqi import (get_solar_terms, julian_day, find_solar_term as find_term,
                    STEMS as _S, BRANCHES as _B)
from jieqi import jd_to_datetime as jd_to_dt

STEMS = _S
BRANCHES = _B

# ═══════════════════════════════════════════════════════════════
# КОНСТАНТЫ
# ═══════════════════════════════════════════════════════════════

LUOSHU = [1,2,3,4,5,6,7,8,9]
CIRCLE = [1,8,3,4,9,2,7,6]  # кольцо 8 внешних дворцов по часовой

EP_SEQ = ['戊','己','庚','辛','壬','癸','丁','丙','乙']

NINE_STARS = {1:'天蓬',2:'天芮',3:'天冲',4:'天辅',5:'天禽',6:'天心',7:'天柱',8:'天任',9:'天英'}
EIGHT_GATES = {1:'休门',2:'死门',3:'伤门',4:'杜门',6:'开门',7:'惊门',8:'生门',9:'景门'}
SPIRITS_YANG = ['值符','腾蛇','太阴','六合','白虎','玄武','九地','九天']
SPIRITS_YIN  = ['值符','腾蛇','太阴','六合','勾陈','朱雀','九地','九天']

TRIGRAMS = {1:'坎',2:'坤',3:'震',4:'巽',5:'中',6:'乾',7:'兑',8:'艮',9:'离'}
DIRECTIONS = {1:'N',2:'SW',3:'E',4:'SE',5:'中',6:'NW',7:'W',8:'NE',9:'S'}

SIX_JIA = {(0,0):4,(0,10):5,(0,8):6,(0,6):7,(0,4):8,(0,2):9}

JU = {
  'yang':{'冬至':(1,7,4),'小寒':(2,8,5),'大寒':(3,9,6),
          '立春':(8,5,2),'雨水':(9,6,3),'惊蛰':(1,7,4),
          '春分':(3,9,6),'清明':(4,1,7),'谷雨':(5,2,8),
          '立夏':(4,1,7),'小满':(5,2,8),'芒种':(6,3,9)},
  'yin': {'夏至':(9,3,6),'小暑':(8,2,5),'大暑':(7,1,4),
          '立秋':(2,5,8),'处暑':(1,4,7),'白露':(9,3,6),
          '秋分':(7,1,4),'寒露':(6,9,3),'霜降':(5,8,2),
          '立冬':(6,9,3),'小雪':(5,8,2),'大雪':(4,7,1)},
}

# 24 солнечных термина с долготой (все 24, не только Цзе)
ALL_TERMS = [
    (315,'立春'),(330,'雨水'),(345,'惊蛰'),(0,'春分'),
    (15,'清明'),(30,'谷雨'),(45,'立夏'),(60,'小满'),
    (75,'芒种'),(90,'夏至'),(105,'小暑'),(120,'大暑'),
    (135,'立秋'),(150,'处暑'),(165,'白露'),(180,'秋分'),
    (195,'寒露'),(210,'霜降'),(225,'立冬'),(240,'小雪'),
    (255,'大雪'),(270,'冬至'),(285,'小寒'),(300,'大寒'),
]

YANG_TERMS = {'冬至','小寒','大寒','立春','雨水','惊蛰','春分','清明','谷雨','立夏','小满','芒种'}

# ═══════════════════════════════════════════════════════════════
# ВЫЧИСЛЕНИЯ
# ═══════════════════════════════════════════════════════════════

def day_pillar(y, m, d):
    jdn = int(julian_day(y,m,d,12)+0.5)
    return (jdn+9)%10, (jdn+1)%12

def hour_pillar(ds, h):
    bi = 0 if h==23 else ((h+1)//2)%12
    base = [0,2,4,6,8]
    si = (base[ds%5]+bi)%10
    return si, bi

def get_xun(si, bi):
    offset = si
    xun_branch = (bi - offset) % 12
    return (0, xun_branch), offset

def current_solar_term(y, m, d, h, mi, tz_off):
    """Определить текущий солнечный термин."""
    target = datetime(y,m,d,h,mi,tzinfo=timezone(timedelta(hours=tz_off))).astimezone(timezone.utc)
    terms = []
    for yr in [y-1, y, y+1]:
        for lon, name in ALL_TERMS:
            jd = find_term(yr, lon)
            dt = jd_to_dt(jd)
            terms.append((dt, name))
    terms.sort(key=lambda x: x[0])
    current = None
    current_start = None
    for i in range(len(terms)-1):
        if terms[i][0] <= target < terms[i+1][0]:
            current = terms[i][1]
            current_start = terms[i][0]
            break
    return current, current_start

def determine_yuan(ds, db):
    """拆补法: 0=上元, 1=中元, 2=下元 — по 符头 дня (ближайший 甲- или 己-день, он же начало пятидневки).
    上元: 甲子 甲午 己卯 己酉 · 中元: 甲寅 甲申 己巳 己亥 · 下元: 甲辰 甲戌 己丑 己未.
    До 2026-11-09 元 считался по числу дней от начала 节气 (0–4/5–9/10+) — это не 拆补 и не 置闰,
    а грубое приближение: 54/80 досок получали неверный 局 (сверка с kinqimen, issue #17/#24)."""
    back = ds % 5                       # шагов назад до ближайшего 甲 (0) или 己 (5)
    futou_branch = (db - back) % 12
    if futou_branch in (0, 6, 3, 9):    # 子午卯酉
        return 0
    if futou_branch in (2, 8, 5, 11):   # 寅申巳亥
        return 1
    return 2                            # 辰戌丑未

# ── Метод определения 局: 拆补 (по умолчанию) или 置闰 (超神接气) — issue #24 ───────────────────────
METHOD = "chaibu"          # "chaibu" | "zhirun"
ZHIRUN_THRESHOLD = 8       # 闰, когда на 芒种/大雪 день термина − день 符头 ≥ N. 《奇门遁甲统宗》卷一 «置闰法» считает дни
                           # ВКЛЮЧИТЕЛЬНО («符头 16-го, 夏至 24-го — 超过九日 → 闰»), т. е. 9 дней включительно = разница 8;
                           # так же у независимой реализации Ciallo («首尾并数，即实差八日以上»). --zhirun-threshold 9 — чтение
                           # «实差九日» (современные пересказы «超神大于九日»); расходятся только в годы с 超神 ровно 8 (2010/2013/2016).

def _jdn(y, m, d):
    return int(julian_day(y, m, d, 12) + 0.5)

def shang_yuan_futou(jdn):
    """JDN дня 上元-符头 (甲子/甲午/己卯/己酉), открывающего 15-дневный блок, в который входит день jdn.
    甲子 ⇔ jdn ≡ 11 (mod 60), остальные 上元-符头 — через 15 дней."""
    return jdn - (jdn + 4) % 15

def _terms_local(y_from, y_to, tz_off):
    """[(jdn локального дня термина, имя, datetime)] для всех 24 节气 за годы y_from..y_to, по порядку."""
    tz = timezone(timedelta(hours=tz_off))
    out = []
    for yr in range(y_from, y_to + 1):
        for lon, name in ALL_TERMS:
            dt = jd_to_dt(find_term(yr, lon)).astimezone(tz)
            out.append((_jdn(dt.year, dt.month, dt.day), name, dt))
    out.sort(key=lambda t: t[0])
    return out

def zhirun_assign(y, m, d, tz_off, threshold=None):
    """置闰法 (超神接气): какому 节气 принадлежит 15-дневный блок (от 上元-符头), в который входит день.

    Блоки идут подряд каждые 15 дней; термины — каждые ~15.2 дня, поэтому 符头 постепенно обгоняет
    термин (超神 растёт на ~0.22 дня за термин). Когда на 芒种 или 大雪 符头 опережает термин на
    ≥ threshold дней, после этого термина вставляется 闰-блок (его 三元 повторяются), и следующий
    термин (夏至/冬至) снова получает 符头 после себя (接气). Симуляция идёт от 冬至 за 6 лет до
    даты: начальный блок — последний 上元-符头 не позже дня 冬至; ошибка начального выбора (на один
    блок) самоисправляется первым же 闰 (не позже чем через ~3.5 года), поэтому результат от эпохи
    не зависит. Сверено с 《统宗》 (пример Канси 57) и с Ciallo (verify_vs_ciallo.py), 2024: 闰大雪 11.12, 冬至上元 26.12 —
    как в опубликованном разборе (zyqmdj.com, 2024-12-21). Возвращает (термин, 超神 дней (>0 — 符头 раньше термина, <0 — 接气, 0 — 正授), 闰-блок?)."""
    threshold = ZHIRUN_THRESHOLD if threshold is None else threshold
    target = _jdn(y, m, d)
    terms = _terms_local(y - 6, y + 1, tz_off)
    i = next(k for k, t in enumerate(terms) if t[1] == '冬至')
    F = shang_yuan_futou(terms[i][0])
    while i < len(terms):
        tj, name, _ = terms[i]
        if F <= target < F + 15:
            return name, tj - F, False
        chao = tj - F
        F += 15
        if name in ('芒种', '大雪') and chao >= threshold:   # 闰: следующий блок повторяет 局 этого термина
            if F <= target < F + 15:
                return name, chao, True
            F += 15
        i += 1
    raise ValueError("置闰: дата вне диапазона терминов")

def earth_plate(ju, yang):
    """Земная пластина: размещение стволов."""
    start = LUOSHU.index(ju)
    plate = {}
    for i, stem in enumerate(EP_SEQ):
        if yang:
            p = LUOSHU[(start+i)%9]
        else:
            p = LUOSHU[(start-i)%9]
        plate[p] = stem
    return plate

def find_palace_of_stem(plate, stem):
    for p, s in plate.items():
        if s == stem: return p
    return 2

def rotate(home_palace, dest_palace):
    """Вычислить сдвиг в кольце."""
    if home_palace == 5: home_palace = 2
    if dest_palace == 5: dest_palace = 2
    hi = CIRCLE.index(home_palace)
    di = CIRCLE.index(dest_palace)
    return (di - hi) % 8

def apply_shift(default_palace, shift):
    if default_palace == 5: return 2
    idx = CIRCLE.index(default_palace)
    return CIRCLE[(idx + shift) % 8]

def build_chart(y, m, d, h, mi, tz_off):
    target = datetime(y,m,d,h,mi,tzinfo=timezone(timedelta(hours=tz_off))).astimezone(timezone.utc)

    # Столпы дня и часа
    ds, db = day_pillar(y, m, d)
    hs, hb = hour_pillar(ds, h)

    # Солнечный термин и юань
    term, term_start = current_solar_term(y, m, d, h, mi, tz_off)
    if not term:
        return None
    # Пограничные предупреждения (issue #34, приём из Numerologist_skills «边界提醒»): смена термина в пределах
    # суток — другой 局 (а на 夏至/冬至 ещё и 阴/阳遁); смена 时辰 в пределах 15 минут — другая доска целиком;
    # 符头-день меняет 元 — если рождение/вопрос около полуночи, 元 зависит от даты.
    warns = []
    tz = timezone(timedelta(hours=tz_off))
    for yr in (y - 1, y, y + 1):
        for lon_, nm_ in ALL_TERMS:
            tdt = jd_to_dt(find_term(yr, lon_)).astimezone(tz)
            dh = (tdt - target.astimezone(tz)).total_seconds() / 3600
            if abs(dh) <= 24:
                warns.append({"kind": "term", "severity": "high" if abs(dh) <= 2 else "medium",
                              "detail": f"{nm_} {'через' if dh > 0 else 'был'} {abs(dh):.1f} ч ({tdt:%Y-%m-%d %H:%M}) — с него другой 局"
                                        + ("" if nm_ not in ('夏至', '冬至') else " и смена 阴/阳遁")})
    mins_to_hour_edge = min((mi + 60 * ((h + 1) % 2)) % 120, 120 - (mi + 60 * ((h + 1) % 2)) % 120)
    if mins_to_hour_edge <= 15:
        warns.append({"kind": "hour", "severity": "high" if mins_to_hour_edge <= 5 else "medium",
                      "detail": f"до смены 时辰 {mins_to_hour_edge} мин — соседний час даёт другую доску (旬首, 值符, 值使)"})
    if h == 23 or h == 0:
        warns.append({"kind": "day", "severity": "medium",
                      "detail": "子-час у полуночи: дата и 符头 (元) зависят от конвенции суток — проверь дату запроса"})

    # Термин, чьи 局 берём: 拆补 — текущий; 置闰 — тот, которому принадлежит 15-дневный блок 符头
    chaojie = None
    if METHOD == "zhirun":
        ju_term, chao, in_run = zhirun_assign(y, m, d, tz_off)
        chaojie = {'ju_term': ju_term, 'status': '超神' if chao > 0 else ('接气' if chao < 0 else '正授'),
                   'days': abs(chao), 'run_block': in_run}
    else:
        ju_term = term
    yang = ju_term in YANG_TERMS
    dun = 'yang' if yang else 'yin'
    if ju_term not in JU[dun]:
        return None

    yuan = determine_yuan(ds, db)
    ju_num = JU[dun][ju_term][yuan]

    # Земная пластина
    ep = earth_plate(ju_num, yang)

    #旬首 и дежурная звезда/врата
    xun_head, hour_offset = get_xun(hs, hb)
    hidden_stem_idx = SIX_JIA[xun_head]
    hidden_stem = STEMS[hidden_stem_idx]

    duty_palace = find_palace_of_stem(ep, hidden_stem)
    duty_star = NINE_STARS.get(duty_palace, NINE_STARS[2])
    duty_gate = EIGHT_GATES.get(duty_palace, EIGHT_GATES.get(2))

    # Вращение звёзд: дежурная звезда → дворец часового ствола
    # час со стволом 甲 (旬首 сам) — 甲 на пластине нет, он скрыт под своей 六仪: 值符 остаётся дома (伏吟);
    # раньше find_palace_of_stem не находил 甲 и молча отдавал 坤 — 1 доска из 10 (все 甲-часы) была неверна
    hour_stem_palace = find_palace_of_stem(ep, STEMS[hs] if hs != 0 else hidden_stem)
    shift = rotate(duty_palace, hour_stem_palace)

    stars = {}
    for p, star in NINE_STARS.items():
        if p == 5: continue
        new_p = apply_shift(p, shift)
        stars[new_p] = star
    # Тянь Цинь → туда же, где Тянь Жуй
    tianrui_p = [p for p,s in stars.items() if s=='天芮']
    if tianrui_p:
        stars[tianrui_p[0]] = stars[tianrui_p[0]] + '/天禽'

    # Небесные стволы
    hp_stems = {}
    for new_p, star in stars.items():
        star_name = star.split('/')[0]
        home_p = [p for p,s in NINE_STARS.items() if s==star_name][0]
        hp_stems[new_p] = ep.get(home_p, '')

    # Вращение врат (исправлено 2026-11-09 по сверке с kinqimen, issue #17/#24):
    # 值使门 «летит» по НОМЕРАМ дворцов — на столько шагов, сколько часов прошло от 旬首
    # (阳遁 +1: 1→2→…→9→1; 阴遁 −1), 中宫 5 → 坤 2; остальные врата — от него по кольцу 八宫 в порядке
    # их родных дворцов. Раньше все врата сдвигались по кольцу на hour_offset — верно лишь случайно.
    circle = CIRCLE if yang else list(reversed(CIRCLE))
    # 中宫 5 считается шагом (не пропускается); если 值使 ПРИЗЕМЛЯЕТСЯ в 5 — 寄坤 (2). Сверено с kinqimen.
    target = duty_palace
    for _ in range(hour_offset):
        target = (target % 9) + 1 if yang else (target - 2) % 9 + 1
    if target == 5: target = 2
    gate_order = [EIGHT_GATES[p] for p in circle]           # врата по кольцу в порядке родных дворцов
    start_idx = circle.index(duty_palace if duty_palace != 5 else 2)
    target_idx = circle.index(target)
    gates = {}
    for k in range(8):
        gates[circle[(target_idx + k) % 8]] = gate_order[(start_idx + k) % 8]

    # Духи
    spirits_list = SPIRITS_YANG if yang else SPIRITS_YIN
    duty_star_new_p = hour_stem_palace
    if duty_star_new_p == 5: duty_star_new_p = 2
    sp_circle = CIRCLE if yang else list(reversed(CIRCLE))
    sp_start = sp_circle.index(duty_star_new_p)
    spirits = {}
    for i, sp in enumerate(spirits_list):
        p = sp_circle[(sp_start + i) % 8]
        spirits[p] = sp

    return {
        'palaces': {p: {
            'earth': ep.get(p,''),
            'heaven': hp_stems.get(p,''),
            'star': stars.get(p,''),
            'gate': gates.get(p,''),
            'spirit': spirits.get(p,''),
            'trigram': TRIGRAMS[p],
            'dir': DIRECTIONS[p],
        } for p in range(1,10)},
        'meta': {
            'dun': dun, 'ju': ju_num, 'term': term, 'yuan': ['上元','中元','下元'][yuan],
            'ju_term': ju_term, 'chaojie': chaojie, 'boundary_warnings': warns,
            'conventions': {'method': ('置闰 (超神接气: 局 — от термина 15-дневного блока 符头; 闰-блок после 芒种/大雪 '
                                       f'при 超神 ≥ {ZHIRUN_THRESHOLD} дней)' if METHOD == "zhirun"
                                       else '拆补 (局 — от текущего термина, 元 по 符头 дня: 甲/己)'), 'plates': '转盘', 'zhongfu': '值使 летит по номерам дворцов, 中宫 считается шагом, приземление в 5 → 寄坤',
                            'spirits_naming': '白虎/玄武 (в 阳遁 иные школы пишут 勾陈/朱雀)', 'oracle': 'kinqimen 300/300 (2026-11-09), кроме часового ствола в 中宫'},
            'duty_star': duty_star, 'duty_gate': duty_gate,
            'xun': f"甲{BRANCHES[xun_head[1]]}", 'hour': f"{STEMS[hs]}{BRANCHES[hb]}",
            'day': f"{STEMS[ds]}{BRANCHES[db]}",
            'yang': yang,
        }
    }

# ═══════════════════════════════════════════════════════════════
# ВЫВОД
# ═══════════════════════════════════════════════════════════════

def print_chart(chart):
    m = chart['meta']
    dun_str = "阳遁 Ян" if m['yang'] else "阴遁 Инь"
    print(f"\n{'═'*60}")
    print(f"  奇门遁甲 — ЦИ МЭНЬ ДУНЬ ЦЗЯ")
    print(f"  {dun_str} | 局{m['ju']} | {m['term']} {m['yuan']}")
    print(f"  日柱: {m['day']}  时柱: {m['hour']}  旬首: {m['xun']}")
    print(f"  值符: {m['duty_star']}  值使: {m['duty_gate']}")
    print(f"{'═'*60}")

    # Отображение доски 3x3
    layout = [[4,9,2],[3,5,7],[8,1,6]]
    dirs = {4:'SE巽',9:'S 离',2:'SW坤',3:'E 震',5:'中  ',7:'W 兑',8:'NE艮',1:'N 坎',6:'NW乾'}

    for row in layout:
        # Заголовок
        line = "  "
        for p in row:
            line += f"┌{'─'*18}┐ "
        print(line)

        # Дворец + направление
        line = "  "
        for p in row:
            d = chart['palaces'][p]
            line += f"│ {p} {dirs[p]:6}       │ "
        print(line)

        # Дух
        line = "  "
        for p in row:
            d = chart['palaces'][p]
            sp = d['spirit'][:6] if d['spirit'] else ''
            line += f"│ 神:{sp:13}│ "
        print(line)

        # Звезда
        line = "  "
        for p in row:
            d = chart['palaces'][p]
            st = d['star'][:8] if d['star'] else ''
            line += f"│ 星:{st:13}│ "
        print(line)

        # Небесный ствол
        line = "  "
        for p in row:
            d = chart['palaces'][p]
            hs = d['heaven'] if d['heaven'] else ''
            line += f"│ 天:{hs:14}│ "
        print(line)

        # Врата
        line = "  "
        for p in row:
            d = chart['palaces'][p]
            gt = d['gate'] if d['gate'] else ''
            line += f"│ 门:{gt:14}│ "
        print(line)

        # Земной ствол
        line = "  "
        for p in row:
            d = chart['palaces'][p]
            es = d['earth'] if d['earth'] else ''
            line += f"│ 地:{es:14}│ "
        print(line)

        # Нижняя граница
        line = "  "
        for p in row:
            line += f"└{'─'*18}┘ "
        print(line)

    # Паттерны
    print(f"\n  Паттерны:")
    for p in range(1,10):
        d = chart['palaces'][p]
        if d['earth'] and d['heaven'] and d['earth'] == d['heaven']:
            print(f"    ⚠ Дворец {p}: 伏吟 (застой) — небо = земля = {d['earth']}")

    # Три чуда
    for p in range(1,10):
        d = chart['palaces'][p]
        if d['heaven'] in ('乙','丙','丁') and d['gate'] in ('开门','休门','生门'):
            names = {'乙':'日奇','丙':'月奇','丁':'星奇'}
            print(f"    ★ Дворец {p}: {names[d['heaven']]} ({d['heaven']}) + {d['gate']} — благоприятно!")

    print(f"\n{'═'*60}\n")

# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def _test():
    """Самопроверка 置闰 (issue #24): известные случаи + инварианты на 6 годах."""
    global METHOD
    ok = True
    def chart(method, y, m, d):
        global METHOD
        METHOD = method
        try:
            return build_chart(y, m, d, 12, 0, 8)['meta']
        finally:
            METHOD = "chaibu"
    # 2024-06-15 (己酉 14.06 — 上元-符头 за 7 дней до 夏至 21.06): 拆补 — 芒种 陽六, 置闰 — 超神 → 夏至 陰九
    a, b = chart("chaibu", 2024, 6, 15), chart("zhirun", 2024, 6, 15)
    p1 = (a['dun'], a['ju'], a['yuan']) == ('yang', 6, '上元') and (b['dun'], b['ju'], b['ju_term']) == ('yin', 9, '夏至') \
        and b['chaojie']['status'] == '超神' and b['chaojie']['days'] == 7
    ok &= p1; print(f"[{'PASS' if p1 else 'FAIL'}] 2024-06-15: 拆补 {a['dun']} {a['ju']}局 {a['yuan']} | 置闰 {b['dun']} {b['ju']}局 "
                    f"{b['ju_term']} {b['chaojie']} (ожидалось 陽6 上元 | 陰9 夏至 超神 7; так же у kinqimen)")
    # 2024-01-01 甲子 — 符头 за 5 дней до 小寒: 置闰 → 小寒 陽二局上元 (拆补 — 冬至 陽一)
    a, b = chart("chaibu", 2024, 1, 1), chart("zhirun", 2024, 1, 1)
    p2 = (a['ju'], a['ju_term']) == (1, '冬至') and (b['ju'], b['ju_term'], b['chaojie']['days']) == (2, '小寒', 5)
    ok &= p2; print(f"[{'PASS' if p2 else 'FAIL'}] 2024-01-01 甲子: 拆补 {a['ju']}局 {a['ju_term']} | 置闰 {b['ju']}局 {b['ju_term']} 超神 "
                    f"{b['chaojie']['days']} (ожидалось 1 冬至 | 2 小寒 5)")
    # Инварианты 2020–2025 (ежедневно): 元 совпадает с 拆补; ju_term — текущий термин или соседний;
    # |超神| в разумных пределах; 闰-блоки только после 芒种/大雪 и ровно по 15 дней
    from datetime import date as _date
    order = [n for _, n in ALL_TERMS]
    bad, run_days, max_chao, min_chao, runs = [], 0, -99, 99, []
    d0 = _date(2020, 1, 1)
    for k in range(0, 6 * 366):
        dd = d0 + timedelta(days=k)
        if dd.year > 2025: break
        a, b = chart("chaibu", dd.year, dd.month, dd.day), chart("zhirun", dd.year, dd.month, dd.day)
        cj = b['chaojie']
        chao = cj['days'] if cj['status'] == '超神' else -cj['days']
        max_chao, min_chao = max(max_chao, chao), min(min_chao, chao)
        if a['yuan'] != b['yuan']: bad.append((str(dd), 'yuan'))
        i = order.index(a['term'])
        if b['ju_term'] not in (a['term'], order[(i + 1) % 24], order[(i - 1) % 24]): bad.append((str(dd), 'term', a['term'], b['ju_term']))
        if cj['run_block']:
            run_days += 1
            if b['ju_term'] not in ('芒种', '大雪'): bad.append((str(dd), 'run', b['ju_term']))
            if not runs or (dd - runs[-1][-1]).days > 1: runs.append([dd, dd])
            else: runs[-1][-1] = dd
    p3 = not bad and all((r[1] - r[0]).days == 14 for r in runs) and -7 <= min_chao and max_chao <= 12
    ok &= p3
    print(f"[{'PASS' if p3 else 'FAIL'}] инварианты 2020–2025: расхождений {len(bad)}; 超神 ∈ [{min_chao}, {max_chao}]; "
          f"闰-блоки: {[(str(r[0]), str(r[1])) for r in runs]}")
    for x in bad[:5]: print("    ", x)
    # Пограничные предупреждения (#34): 2024-06-21 (夏至 ~04:51 CST) в 06:00 → term high + смена 遁; 14:50 → hour-граница
    w1 = build_chart(2024, 6, 21, 6, 0, 8)['meta']['boundary_warnings']
    w2 = build_chart(2026, 4, 8, 14, 50, 8)['meta']['boundary_warnings']
    w3 = build_chart(2026, 4, 8, 12, 0, 8)['meta']['boundary_warnings']
    p4 = any(w['kind'] == 'term' and w['severity'] == 'high' and '阴/阳遁' in w['detail'] for w in w1) \
        and any(w['kind'] == 'hour' for w in w2) and not w3
    ok &= p4
    print(f"[{'PASS' if p4 else 'FAIL'}] boundary_warnings: 夏至+1ч → {[w['kind'] for w in w1]}; 14:50 → {[w['kind'] for w in w2]}; 12:00 → {w3}")
    print("qimen --test:", "ЗЕЛЁНО ✓" if ok else "КРАСНОЕ ✗")
    return 0 if ok else 1

def main():
    args = sys.argv[1:]
    json_mode = "--json" in args
    args = [a for a in args if a != "--json"]
    tz_off = 8
    now = datetime.now()
    y, m, d, h, mi = now.year, now.month, now.day, now.hour, now.minute

    global METHOD, ZHIRUN_THRESHOLD
    if "--test" in args:
        sys.exit(_test())
    if "--method" in args:
        METHOD = args[args.index("--method") + 1]
        if METHOD not in ("chaibu", "zhirun"):
            print(f"ОШИБКА: --method ожидает chaibu|zhirun, получено «{METHOD}»", file=sys.stderr); sys.exit(2)
        del args[args.index("--method"):args.index("--method") + 2]
    if "--zhirun-threshold" in args:
        ZHIRUN_THRESHOLD = int(args[args.index("--zhirun-threshold") + 1])
        del args[args.index("--zhirun-threshold"):args.index("--zhirun-threshold") + 2]

    for a in args:
        if '-' in a and len(a) == 10:
            p = a.split('-'); y,m,d = int(p[0]),int(p[1]),int(p[2])
        elif ':' in a:
            p = a.split(':'); h,mi = int(p[0]),int(p[1])
        elif a.upper().startswith('UTC'):
            v = float(a.upper().replace('UTC','').replace('+','').replace('−','-'))   # дробные пояса: UTC+5.5, UTC+5.75
            if not -12 <= v <= 14:
                import cli_errors
                raise cli_errors.InputError(f"пояс «{a}» вне диапазона UTC−12…UTC+14")
            tz_off = int(v) if v == int(v) else v

    datetime(y, m, d, h, mi)      # проверка ввода до расчёта: несуществующая дата или время — ошибка ввода (код 2)
    chart = build_chart(y, m, d, h, mi, tz_off)
    if chart:
        if json_mode:
            chart["input"] = {
                "date": f"{y}-{m:02d}-{d:02d}",
                "time": f"{h:02d}:{mi:02d}",
                "utc_offset": tz_off,
            }
            print(json.dumps(chart, ensure_ascii=False, indent=2))
        else:
            print_chart(chart)
    else:
        import cli_errors
        cli_errors.fail("не удалось определить солнечный термин для этого момента", kind="internal")

if __name__ == '__main__':
    import cli_errors
    cli_errors.run(main)
