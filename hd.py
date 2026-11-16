#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""
hd.py — Дизайн Человека (Human Design).

Отображение долгот → ворота/линии И-Цзин, 26 активаций (13 Личности + 13 Дизайна),
центры, 36 каналов, Тип, Авторитет, Профиль, определённость, крест воплощения.

ВЫВЕРКА ДАННЫХ (важно для доверия):
  • Колесо ворот сверено внешней таблицей (barneyandflow/bonniesorsby): ворота 41
    @ 302°00′ тропика, 64 шт по 5.625°, 6 линий по 0.9375°.
  • Карта «ворота→центр» НЕ вводится вручную, а ВЫВОДИТСЯ из списка 36 каналов;
    --test проверяет инварианты: каждые ворота ровно в одном центре, все 64
    покрыты, число ворот по центрам = эталон (3/6/11/8/4/9/7/7/9).
  • Тождество Дизайна: Солнце Дизайна = Солнце Личности − 88° дуги (через ephem_core).
  • Подструктура линии (цвет 1-6 / тон 1-6 / база 1-5) + PHS: детерминация («как есть»)
    по цвету Солнца Дизайна (подтип — по тону), среда — по цвету Узлов Дизайна.
    СВЕРЕНО 2026-07-11: (а) привязки и нарезка — с hdkit + SharpAstrology (дословные таблицы/код),
    офиц. страницами Jovian Archive и API bodygraph.com (2 полные карты); (б) КАНОН-ШТАМП —
    per-chart сверка с офиц. Maia Mechanics (полный PDF-экспорт): планеты/Солнце/Земля 22/22
    идеально (ворота/линия/цвет/тон/база), детерминация/среда/Variable/когниция/дата Дизайна
    (до минуты) совпали. Известный зазор: у УЗЛОВ тон/база могут отличаться на 1 бин —
    движки истинного узла расходятся до ~0.5′ (тоновый бин 1.56′); ворота/линия/ЦВЕТ узлов
    устойчивы (цветовой бин 9.4′) → среда надёжна. ОПИСАНИЯ подтипов — пересказы (см. phs.note).

Конвенция узлов: СРЕДНИЙ узел по умолчанию [требует сверки с Jovian]. Влияет на
ворота Узлов → на каналы/центры с их участием.
"""
import sys
from collections import defaultdict
from datetime import datetime, timezone
import ephem_core as ec

# ── выверенное колесо ───────────────────────────────────────────────────────
WHEEL = [41, 19, 13, 49, 30, 55, 37, 63, 22, 36, 25, 17, 21, 51, 42, 3,
         27, 24, 2, 23, 8, 20, 16, 35, 45, 12, 15, 52, 39, 53, 62, 56,
         31, 33, 7, 4, 29, 59, 40, 64, 47, 6, 46, 18, 48, 57, 32, 50,
         28, 44, 1, 43, 14, 34, 9, 5, 26, 11, 10, 58, 38, 54, 61, 60]
START = 302.0
GATE = 360.0 / 64    # 5.625°
LINE = GATE / 6      # 0.9375°
COLOR = LINE / 6     # 0.15625° — цвет (1-6)
TONE = COLOR / 6     # ≈0.026042° — тон (1-6)
BASE = TONE / 5      # ≈0.005208° — база (1-5)
assert len(WHEEL) == 64 == len(set(WHEEL)), "колесо: 64 уникальных ворот"

# ── центры и 36 каналов ─────────────────────────────────────────────────────
# Центр-коды. Моторы — источники энергии (важно для Типа).
CENTERS = ["head", "ajna", "throat", "g", "heart", "sacral", "solar", "spleen", "root"]
MOTORS = {"sacral", "solar", "heart", "root"}
CENTER_RU = {"head": "Голова", "ajna": "Аджна", "throat": "Горло", "g": "G-центр (Самость)",
             "heart": "Сердце (Эго)", "sacral": "Сакрал", "solar": "Солнечное сплетение",
             "spleen": "Селезёнка", "root": "Корень"}
EXPECTED_CENTER_COUNTS = {"head": 3, "ajna": 6, "throat": 11, "g": 8, "heart": 4,
                          "sacral": 9, "solar": 7, "spleen": 7, "root": 9}

# (ворота_A, ворота_B, центр_A, центр_B, имя). 36 каналов.
CHANNELS = [
    (1, 8, "g", "throat", "Вдохновение"), (2, 14, "g", "sacral", "Бит (Ключ)"),
    (3, 60, "sacral", "root", "Мутация"), (4, 63, "ajna", "head", "Логика"),
    (5, 15, "sacral", "g", "Ритм"), (6, 59, "solar", "sacral", "Близость"),
    (7, 31, "g", "throat", "Альфа"), (9, 52, "sacral", "root", "Концентрация"),
    (10, 20, "g", "throat", "Пробуждение"), (10, 34, "g", "sacral", "Исследование"),
    (10, 57, "g", "spleen", "Совершенная форма"), (11, 56, "ajna", "throat", "Любопытство"),
    (12, 22, "throat", "solar", "Открытость"), (13, 33, "g", "throat", "Блудный сын"),
    (16, 48, "throat", "spleen", "Талант (Волна)"), (17, 62, "ajna", "throat", "Принятие"),
    (18, 58, "spleen", "root", "Суждение"), (19, 49, "root", "solar", "Синтез"),
    (20, 34, "throat", "sacral", "Харизма"), (20, 57, "throat", "spleen", "Мозговая волна"),
    (21, 45, "heart", "throat", "Деньги"), (23, 43, "throat", "ajna", "Структурирование"),
    (24, 61, "ajna", "head", "Осознание"), (25, 51, "g", "heart", "Инициация"),
    (26, 44, "heart", "spleen", "Сдача"), (27, 50, "sacral", "spleen", "Сохранение"),
    (28, 38, "spleen", "root", "Борьба"), (29, 46, "sacral", "g", "Открытие"),
    (30, 41, "solar", "root", "Признание"), (32, 54, "spleen", "root", "Преображение"),
    (34, 57, "sacral", "spleen", "Сила"), (35, 36, "throat", "solar", "Мимолётность"),
    (37, 40, "solar", "heart", "Общность"), (39, 55, "root", "solar", "Эмоциональность"),
    (42, 53, "sacral", "root", "Зрелость"), (47, 64, "ajna", "head", "Абстракция"),
]


def _build_gate_center():
    """Выводит {ворота: центр} из CHANNELS с проверкой непротиворечивости."""
    gc = {}
    for a, b, ca, cb, _ in CHANNELS:
        for g, c in ((a, ca), (b, cb)):
            if g in gc and gc[g] != c:
                raise ValueError(f"ворота {g}: конфликт центров {gc[g]} vs {c}")
            gc[g] = c
    return gc


GATE_CENTER = _build_gate_center()

DEFAULT_NODE = "node_true"  # КАНОН: сверено с офиц. Maia Mechanics/Jovian (2026-06-30) — узлы карты совпали с true, не mean; mean даёт ИНЫЕ ворота Узлов (его показывают лишь сторонние сервисы)


def hd_bodies(node=DEFAULT_NODE):
    return ["sun", "earth", node, "south_" + node, "moon", "mercury", "venus",
            "mars", "jupiter", "saturn", "uranus", "neptune", "pluto"]
BODY_RU = {"sun": "Солнце", "earth": "Земля", "node_mean": "Сев.Узел",
           "south_node_mean": "Юж.Узел", "node_true": "Сев.Узел", "south_node_true": "Юж.Узел",
           "moon": "Луна", "mercury": "Меркурий", "venus": "Венера", "mars": "Марс",
           "jupiter": "Юпитер", "saturn": "Сатурн", "uranus": "Уран",
           "neptune": "Нептун", "pluto": "Плутон"}

PROFILE_NAMES = {1: "Исследователь", 2: "Отшельник", 3: "Мученик",
                 4: "Оппортунист", 5: "Еретик", 6: "Ролевая модель"}
TYPE_INFO = {  # тип: (стратегия, сигнатура, не-я-тема)
    "Генератор": ("Отклик — ждать и откликаться", "Удовлетворение", "Фрустрация"),
    "Манифестирующий Генератор": ("Отклик, затем информировать", "Удовлетворение", "Фрустрация и гнев"),
    "Проектор": ("Ждать приглашения (признания)", "Успех", "Горечь"),
    "Манифестор": ("Информировать до действия", "Покой", "Гнев"),
    "Рефлектор": ("Ждать лунный цикл (~28 дней)", "Удивление", "Разочарование"),
}


# ── ворота/линии/подструктура ────────────────────────────────────────────────
def gate_line(lon):
    offset = (lon - START) % 360
    idx = int(offset // GATE)
    gate = WHEEL[idx]
    within_gate = offset - idx * GATE
    line = int(within_gate // LINE) + 1
    return gate, line, within_gate - (line - 1) * LINE


def line_substructure(within_line_deg):
    """Подструктура линии по возрастанию долготы: цвет 1-6, тон 1-6, база 1-5.
    Возвращает (цвет, тон, база, остаток_в_цвете, остаток_в_тоне)."""
    color = min(int(within_line_deg // COLOR), 5) + 1
    wc = within_line_deg - (color - 1) * COLOR
    tone = min(int(wc // TONE), 5) + 1
    wt = wc - (tone - 1) * TONE
    base = min(int(wt // BASE), 4) + 1
    return color, tone, base, wc, wt


def _minutes_to_boundary(within_deg, span, speed_deg_per_day):
    """Минут хода тела до БЛИЖАЙШЕЙ границы бина (вперёд или назад) — мера хрупкости ко времени."""
    v = abs(speed_deg_per_day)
    if v < 1e-9:
        return float("inf")
    return min(span - within_deg, within_deg) / v * 24 * 60


def activations(birth_dt_utc, node=DEFAULT_NODE):
    jd_p = ec.jd_ut(birth_dt_utc)
    jd_d = ec.design_jd(jd_p)
    out = {"design_jd": jd_d}
    for key, jd in (("personality", jd_p), ("design", jd_d)):
        lons = ec.longitudes(jd, sidereal=False)
        items = []
        for b in hd_bodies(node):
            lon, spd = lons[b]["lon"], lons[b]["speed"]
            g, ln, wl = gate_line(lon)
            color, tone, base, wc, wt = line_substructure(wl)
            items.append({"body": b, "body_ru": BODY_RU[b], "lon": round(lon, 4),
                          "gate": g, "line": ln,
                          "color": color, "tone": tone, "base": base,
                          "minutes_to_line_change": round(_minutes_to_boundary(wl, LINE, spd), 1),
                          "minutes_to_color_change": round(_minutes_to_boundary(wc, COLOR, spd), 1),
                          "minutes_to_tone_change": round(_minutes_to_boundary(wt, TONE, spd), 1)})
        out[key] = items
    return out


# ── определённость: центры, каналы, Тип, Авторитет, определение ──────────────
def _defined(active_gates):
    chans = [c for c in CHANNELS if c[0] in active_gates and c[1] in active_gates]
    centers = set()
    for a, b, ca, cb, _ in chans:
        centers.add(ca); centers.add(cb)
    return centers, chans


def _motor_to_throat(def_channels):
    adj = defaultdict(set)
    for a, b, ca, cb, _ in def_channels:
        adj[ca].add(cb); adj[cb].add(ca)
    if "throat" not in adj:
        return False
    seen, stack = {"throat"}, ["throat"]
    while stack:
        for n in adj[stack.pop()]:
            if n not in seen:
                seen.add(n); stack.append(n)
    return any(m in seen for m in MOTORS)


def _type(defined_centers, def_channels):
    if not defined_centers:
        return "Рефлектор"
    mt = _motor_to_throat(def_channels)
    if "sacral" in defined_centers:
        return "Манифестирующий Генератор" if mt else "Генератор"
    return "Манифестор" if mt else "Проектор"


def _authority(defined_centers):
    if not defined_centers:
        return "Лунный (Рефлектор) — ждать полный цикл Луны"
    for c, name in (("solar", "Эмоциональный — Солнечное сплетение (ясность приходит со временем)"),
                    ("sacral", "Сакральный — отклик тела (звук/импульс «угу/не-а»)"),
                    ("spleen", "Селезёночный — мгновенная интуиция, говорит один раз"),
                    ("heart", "Эго/Сердце — что хочу/на что есть воля"),
                    ("g", "Самопроецируемый — через речь, слушая себя")):
        if c in defined_centers:
            return name
    return "Ментальный/Внешний — нет внутреннего авторитета, нужна среда и звучание вслух"


def _definition(defined_centers, def_channels):
    if not defined_centers:
        return 0, "Нет определения (Рефлектор)"
    parent = {c: c for c in defined_centers}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for a, b, ca, cb, _ in def_channels:
        parent[find(ca)] = find(cb)
    n = len({find(c) for c in defined_centers})
    return n, {1: "Единое определение", 2: "Раздельное (сплит)", 3: "Тройной сплит",
               4: "Четверной сплит"}.get(n, f"{n} компонент")


def _cross_angle(p_sun_line, d_sun_line):
    prof = f"{p_sun_line}/{d_sun_line}"
    if prof == "4/1":
        return "Юкстапозиция (фиксированная судьба)"
    if prof in {"5/1", "5/2", "6/2", "6/3"}:
        return "Левосторонний крест (трансперсональная судьба)"
    return "Правосторонний крест (личная судьба)"


def _resolve_node(jd_p, jd_d, node):
    active = set()
    for jd in (jd_p, jd_d):
        L = ec.longitudes(jd)
        for b in hd_bodies(node):
            active.add(gate_line(L[b]["lon"])[0])
    return _defined(active)


# ── PHS (Primary Health System) ──────────────────────────────────────────────
# Детерминация («как есть») — ЦВЕТ Солнца Дизайна; подтип — ТОН (1-3 «левый», 4-6 «правый»).
# Среда — ЦВЕТ Узлов Дизайна (Южный ≡ Северный: точки строго противоположны, 180° = 32 ворот).
# Названия — публичная структура полузакрытых курсов Ра (IHDS); дословность подтипов не гарантирована.
DETERMINATION_RU = {1: ("Аппетит", "Последовательный", "Чередующийся"),
                    2: ("Вкус", "Открытый", "Закрытый"),
                    3: ("Жажда", "Горячая", "Холодная"),
                    4: ("Прикосновение", "Спокойное", "Нервное"),
                    5: ("Звук", "Высокий", "Низкий"),
                    6: ("Свет", "Прямой", "Непрямой")}
ENVIRONMENT_RU = {1: "Пещеры", 2: "Рынки", 3: "Кухни", 4: "Горы", 5: "Долины", 6: "Берега"}


def _phs(jd_d, node):
    """PHS из точных долгот момента Дизайна (без потери точности на округлении JSON)."""
    L = ec.longitudes(jd_d, sidereal=False)
    sun_lon, sun_spd = L["sun"]["lon"], L["sun"]["speed"]
    _, _, wl = gate_line(sun_lon)
    color, tone, base, wc, wt = line_substructure(wl)
    v = abs(sun_spd)
    m_color = _minutes_to_boundary(wc, COLOR, sun_spd)
    m_tone = _minutes_to_boundary(wt, TONE, sun_spd)
    # смена СТОРОНЫ подтипа = только граница тонов 3↔4 ВНУТРИ цвета: тон 5→6 подтип не меняет.
    # Смену цвета (и с ней всей детерминации) отдельно ловит color-warning — не пугать вилкой, которой нет.
    side_flip_deg = ((3 - tone) * TONE + (TONE - wt)) if tone <= 3 else ((tone - 4) * TONE + wt)
    m_side = side_flip_deg / v * 24 * 60 if v > 1e-9 else float("inf")
    name, left, right = DETERMINATION_RU[color]
    subtype, side = (left, "левый") if tone <= 3 else (right, "правый")
    # сосед по ближайшей границе цвета — чтобы честно называть альтернативу
    alt_color = ((6 if color == 1 else color - 1) if wc < COLOR / 2
                 else (1 if color == 6 else color + 1))
    warnings = []
    if m_side < 45:
        warnings.append(f"граница стороны подтипа (тона 3↔4) в {m_side:.0f} мин хода Солнца: подтип "
                        f"«{left}/{right}» ненадёжен при обычной неточности времени рождения — давать оба")
    if m_color < 90:
        warnings.append(f"цвет Солнца Дизайна в {m_color:.0f} мин от границы с цветом {alt_color} "
                        f"(«{DETERMINATION_RU[alt_color][0]}») — детерминация ненадёжна, давать обе версии")
    n_lon, n_spd = L[node]["lon"], L[node]["speed"]
    _, _, nwl = gate_line(n_lon)
    ncolor, ntone, _, nwc, _ = line_substructure(nwl)
    return {
        "note": ("PHS — «как есть», не «что есть»: условия пищеварения, не списки продуктов. "
                 "КАНОН (сверено 2026-07-11): привязки и нарезка подтверждены офиц. Maia Mechanics "
                 "per-chart (детерминация, среда, стороны Variable, когниция, дата Дизайна — "
                 "совпали; планеты 22/22 вплоть до базы) + независимыми реализациями (hdkit, "
                 "SharpAstrology), офиц. страницами Jovian Archive и API bodygraph.com — [факт "
                 "привязки]. Известный зазор: тон/база УЗЛОВ могут отличаться от Maia на 1 бин "
                 "(движки истинного узла расходятся ≤0.5′) — цвет узлов, а с ним среда, устойчивы. "
                 "ОПИСАНИЯ подтипов (что именно делать) — по пересказам полузакрытых материалов Ра "
                 "(IHDS), дословность не гарантирована — [интерпретация]. "
                 "Требует точного времени рождения (см. sensitivity/warnings)."),
        "determination": {
            "based_on": "цвет Солнца Дизайна (подтип — тон: 1-3 левый / 4-6 правый)",
            "color": color, "tone": tone, "base": base,
            "name": name, "subtype": subtype, "side": side,
            "full": f"{name} — {subtype}",
            "minutes_to_color_change": round(m_color, 1),
            "minutes_to_tone_change": round(m_tone, 1),
            "minutes_to_subtype_flip": (round(m_side, 1) if m_side != float("inf") else None),
        },
        "environment": {
            "based_on": "цвет Узлов Дизайна (Южный ≡ Северный — точки противоположны)",
            "color": ncolor, "tone": ntone, "name": ENVIRONMENT_RU[ncolor],
            "side": "левый" if ntone <= 3 else "правый",
            "minutes_to_color_change": round(_minutes_to_boundary(nwc, COLOR, n_spd), 1),
        },
        "sensitivity": {
            "tone_bin_minutes": round(TONE / v * 24 * 60, 1) if v > 1e-9 else None,
            "color_bin_minutes": round(COLOR / v * 24 * 60, 1) if v > 1e-9 else None,
            "text": "тон сменяется каждые ~37 мин времени рождения; СТОРОНА подтипа — только на "
                    "границе тонов 3↔4 (раз внутри цвета); цвет (сама детерминация) — каждые ~3.7 ч; "
                    "среда по Узлам держится ~3 дня (ко времени надёжна)",
        },
        "warnings": warnings,
    }


def build_chart(birth_dt_utc, meta=None, node=DEFAULT_NODE):
    act = activations(birth_dt_utc, node)
    jd_p = ec.jd_ut(birth_dt_utc); jd_d = act["design_jd"]
    active = {a["gate"] for a in act["personality"]} | {a["gate"] for a in act["design"]}
    defined_centers, def_chans = _defined(active)
    typ = _type(defined_centers, def_chans)
    # сверка конвенции узлов: расходится ли карта при альтернативной конвенции?
    _alt = "node_true" if node == "node_mean" else "node_mean"
    _dc_alt, _ch_alt = _resolve_node(jd_p, jd_d, _alt)
    _typ_alt = _type(_dc_alt, _ch_alt)
    convention_warnings = []
    if _dc_alt != defined_centers or _typ_alt != typ:
        # КАНОН — истинный узел (сверено с офиц. Maia Mechanics/Jovian 2026-06-30: узлы карты совпали с true).
        _cur_auth = _authority(defined_centers).split(" —")[0]
        _alt_auth = _authority(_dc_alt).split(" —")[0]
        if node == "node_true":
            _txt = (f"Карта node-чувствительна, но это РАЗРЕШЕНО: расчёт по истинному узлу — "
                    f"КАНОН (как офиц. Maia Mechanics/Jovian): Тип {typ}, Авторитет {_cur_auth}, "
                    f"центров {len(defined_centers)}. По усреднённому узлу (его дают лишь сторонние "
                    f"сервисы) было бы: Тип {_typ_alt}, Авторитет {_alt_auth}, центров {len(_dc_alt)} — "
                    f"эту версию НЕ использовать.")
        else:
            _txt = (f"ВНИМАНИЕ: расчёт по УСРЕДНЁННОМУ узлу — это НЕ канон (его дают лишь сторонние сервисы): "
                    f"Тип {typ}, Авторитет {_cur_auth}, центров {len(defined_centers)}. Канон — истинный узел "
                    f"(как офиц. Maia Mechanics/Jovian): Тип {_typ_alt}, Авторитет {_alt_auth}, "
                    f"центров {len(_dc_alt)}. Используй каноническую версию (node_true).")
        convention_warnings.append({
            "issue": "node_convention", "current": node, "alternative": _alt, "canonical": "node_true",
            "type_alt": _typ_alt, "authority_alt": _alt_auth,
            "defined_centers_alt": [CENTER_RU[c] for c in CENTERS if c in _dc_alt],
            "text": _txt,
        })
    p_sun = next(a for a in act["personality"] if a["body"] == "sun")
    d_sun = next(a for a in act["design"] if a["body"] == "sun")
    p_earth = next(a for a in act["personality"] if a["body"] == "earth")
    d_earth = next(a for a in act["design"] if a["body"] == "earth")
    ncomp, defname = _definition(defined_centers, def_chans)
    strat, sign, notself = TYPE_INFO[typ]
    fragile = sorted([a for s in ("personality", "design") for a in act[s]],
                     key=lambda a: a["minutes_to_line_change"])[:5]
    return {
        "system": "human_design",
        "input": meta or {},
        "type": typ, "strategy": strat, "signature": sign, "not_self_theme": notself,
        "authority": _authority(defined_centers),
        "profile": f"{p_sun['line']}/{d_sun['line']}",
        "profile_names": [PROFILE_NAMES[p_sun["line"]], PROFILE_NAMES[d_sun["line"]]],
        "definition": defname, "definition_components": ncomp,
        "defined_centers": [CENTER_RU[c] for c in CENTERS if c in defined_centers],
        "open_centers": [CENTER_RU[c] for c in CENTERS if c not in defined_centers],
        "defined_channels": [{"gates": f"{a}-{b}", "name": nm,
                              "centers": f"{CENTER_RU[ca]}↔{CENTER_RU[cb]}"}
                             for a, b, ca, cb, nm in def_chans],
        "all_channels": [{"gates": f"{a}-{b}", "name": nm,
                          "centers": f"{CENTER_RU[ca]}↔{CENTER_RU[cb]}",
                          "defined": (a, b, ca, cb, nm) in def_chans}
                         for a, b, ca, cb, nm in CHANNELS],
        "incarnation_cross": {
            "gates": [p_sun["gate"], p_earth["gate"], d_sun["gate"], d_earth["gate"]],
            "notation": f"{p_sun['gate']}/{p_earth['gate']} | {d_sun['gate']}/{d_earth['gate']}",  # офиц. группировка Maia: Личность | Дизайн
            "angle": _cross_angle(p_sun["line"], d_sun["line"]),
        },
        "activations": {"personality": act["personality"], "design": act["design"]},
        "fragile_activations": [{"body": f"{a['body_ru']} ({'Личн' if a in act['personality'] else 'Диз'})",
                                 "gate_line": f"{a['gate']}.{a['line']}",
                                 "minutes": a["minutes_to_line_change"]} for a in fragile],
        "phs": _phs(jd_d, node),
        "node_convention": node,
        "convention_warnings": convention_warnings,
    }


# ── self-test ────────────────────────────────────────────────────────────────
def _test():
    ok = True
    print("hd.py --test"); print("─" * 60)

    # 1) колесо по граничным градусам
    checks = [(302.0, 41, 1), (307.625, 19, 1), (358.25, 25, 1), (0.0, 25, 2), (301.99, 60, 6)]
    p1 = all(gate_line(l)[:2] == (g, ln) for l, g, ln in checks)
    ok &= p1
    print(f"[{'PASS' if p1 else 'FAIL'}] колесо: граничные градусы")

    # 2) инварианты карты ворота→центр (САМОПРОВЕРКА данных каналов)
    counts = defaultdict(int)
    for g, c in GATE_CENTER.items():
        counts[c] += 1
    p2 = (len(GATE_CENTER) == 64
          and all(counts[c] == EXPECTED_CENTER_COUNTS[c] for c in CENTERS)
          and len(CHANNELS) == 36)
    ok &= p2
    print(f"[{'PASS' if p2 else 'FAIL'}] данные: 64 ворот, 36 каналов, числа по центрам "
          f"{dict(counts)} = эталон")

    # 3) тест-рождение — нейтральная фикстура 1990-03-03 12:00 UTC (= 15:00 Москва); node-чувствительна (п. 5)
    dt = datetime(1990, 3, 3, 12, 0, tzinfo=timezone.utc)
    ch = build_chart(dt, {"birth": "1990-03-03 12:00 UTC", "city": "Москва"})
    p3 = (len(ch["activations"]["personality"]) == 13
          and 1 <= int(ch["profile"][0]) <= 6
          and ch["type"] in TYPE_INFO)
    ok &= p3
    print(f"[{'PASS' if p3 else 'FAIL'}] карта собрана")
    print(f"     Тип: {ch['type']} | Авторитет: {ch['authority'].split(' —')[0]}")
    print(f"     Профиль: {ch['profile']} ({'/'.join(ch['profile_names'])}) | {ch['definition']}")
    print(f"     Определённые центры ({len(ch['defined_centers'])}): {', '.join(ch['defined_centers'])}")
    print(f"     Каналов: {len(ch['defined_channels'])} | Крест: {ch['incarnation_cross']['notation']} "
          f"({ch['incarnation_cross']['angle'].split(' (')[0]})")
    print(f"     Самая хрупкая активация: {ch['fragile_activations'][0]['body']} "
          f"{ch['fragile_activations'][0]['gate_line']} ±{ch['fragile_activations'][0]['minutes']:.0f} мин")

    # 4) тождество Дизайна
    p_sun = next(a for a in ch["activations"]["personality"] if a["body"] == "sun")
    d_sun = next(a for a in ch["activations"]["design"] if a["body"] == "sun")
    arc = (p_sun["lon"] - d_sun["lon"]) % 360
    p4 = abs(arc - 88.0) < 1e-3
    ok &= p4
    print(f"[{'PASS' if p4 else 'FAIL'}] дуга Дизайна {arc:.4f}° (ждём 88)")

    # 5) сверка конвенции узлов: для этой карты mean/true расходятся → предупреждение обязано быть
    p5 = len(ch["convention_warnings"]) >= 1
    ok &= p5
    print(f"[{'PASS' if p5 else 'FAIL'}] предупреждение о конвенции узлов выставлено (карта node-зависима)")
    if ch["convention_warnings"]:
        print("     ⚠ " + ch["convention_warnings"][0]["text"])

    # 6) подструктура: граничные значения + свип-инвариант (обратная сборка долготы из бинов)
    p6 = (line_substructure(0.0)[:3] == (1, 1, 1)
          and line_substructure(LINE - 1e-9)[:3] == (6, 6, 5)
          and gate_line(START + GATE + LINE + COLOR + TONE + BASE / 2)[:2] == (19, 2)
          and line_substructure(COLOR + TONE + BASE / 2)[:3] == (2, 2, 1))
    for k in range(12345):
        lon = (k * 0.029137) % 360.0
        g, ln, wl = gate_line(lon)
        c, t, b, _, _ = line_substructure(wl)
        if not (1 <= c <= 6 and 1 <= t <= 6 and 1 <= b <= 5):
            p6 = False; break
        start = (START + WHEEL.index(g) * GATE + (ln - 1) * LINE
                 + (c - 1) * COLOR + (t - 1) * TONE + (b - 1) * BASE) % 360
        d = (lon - start + 180.0) % 360.0 - 180.0  # центрировано: float-хвост у границы не «оборачивается» в ~360
        if not (-1e-6 <= d < BASE + 1e-6):
            p6 = False; break
    ok &= p6
    print(f"[{'PASS' if p6 else 'FAIL'}] подструктура: границы + свип 12345 долгот (обратная сборка бинов)")

    # 7) тождества 180°: Земля ≡ Солнце и Юж.Узел ≡ Сев.Узел по (линия, цвет, тон, база)
    p7 = True
    for side_key in ("personality", "design"):
        A = {a["body"]: a for a in ch["activations"][side_key]}
        for x, y in (("earth", "sun"), ("south_node_true", "node_true")):
            p7 &= all(A[x][k] == A[y][k] for k in ("line", "color", "tone", "base"))
    ok &= p7
    print(f"[{'PASS' if p7 else 'FAIL'}] тождества 180°: Земля≡Солнце, Юж.Узел≡Сев.Узел (линия/цвет/тон/база)")

    # 8) PHS-блок: имя ← цвет, подтип ← тон, среда ← цвет Узлов
    det, env = ch["phs"]["determination"], ch["phs"]["environment"]
    p8 = (det["name"] == DETERMINATION_RU[det["color"]][0]
          and det["subtype"] == DETERMINATION_RU[det["color"]][1 if det["tone"] <= 3 else 2]
          and env["name"] == ENVIRONMENT_RU[env["color"]]
          and det["minutes_to_tone_change"] <= det["minutes_to_color_change"] * 6)
    ok &= p8
    print(f"[{'PASS' if p8 else 'FAIL'}] PHS: детерминация «{det['full']}» (цвет {det['color']}, "
          f"тон {det['tone']}, {det['side']}), среда «{env['name']}»")
    print(f"     хрупкость: тон ±{det['minutes_to_tone_change']:.0f} мин, "
          f"цвет ±{det['minutes_to_color_change']:.0f} мин; среда ±{env['minutes_to_color_change']:.0f} мин")

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
    _USAGE = ("hd.py YYYY-MM-DD HH:MM ОФФСЕТ [--json] | hd.py --test   "
              "(оффсет UTC обязателен: +3, -5, 8.5, UTC+4)")
    if "--test" in sys.argv:
        sys.exit(0 if _test() else 1)
    elif len(sys.argv) >= 4:
        import json
        tz = _cli_tz(sys.argv[3:], _USAGE)
        d = datetime.fromisoformat(f"{sys.argv[1]} {sys.argv[2]}")
        dt_utc = d.replace(tzinfo=timezone(__import__("datetime").timedelta(hours=tz))).astimezone(timezone.utc)
        ch = build_chart(dt_utc, {"birth_local": f"{sys.argv[1]} {sys.argv[2]} UTC{tz:+g}"})
        if "--json" in sys.argv:
            print(json.dumps(ch, ensure_ascii=False, indent=2))
        else:
            print(f"Тип: {ch['type']}  |  Стратегия: {ch['strategy']}")
            print(f"Авторитет: {ch['authority']}")
            print(f"Профиль: {ch['profile']} ({'/'.join(ch['profile_names'])})  |  {ch['definition']}")
            print(f"Крест воплощения: {ch['incarnation_cross']['notation']} ({ch['incarnation_cross']['angle']})")
            print(f"Определённые центры: {', '.join(ch['defined_centers'])}")
            print(f"Открытые центры: {', '.join(ch['open_centers'])}")
            det, env = ch["phs"]["determination"], ch["phs"]["environment"]
            print(f"PHS: {det['full']} (цвет {det['color']}, тон {det['tone']}, {det['side']}) | "
                  f"Среда: {env['name']}")
            for w in ch["phs"]["warnings"]:
                print(f"  ⚠ {w}")
    else:
        sys.stderr.write(_USAGE + "\n")
        sys.exit(2)


if __name__ == "__main__":
    import cli_errors
    cli_errors.run(_cli)
