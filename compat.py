#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""
compat.py — совместимость двух карт по ТРЁМ независимым системам.

  • Ба Цзы (合婚, He Hun)            — 5 критериев, родная шкала /10
  • Джйотиш (Аштакута / Гуна Милан) — 8 кут, родная шкала /36 + Мангал-доша
  • Дизайн Человека (карта связей)   — электромагнетика / товарищество /
                                       компромисс / доминирование (КАЧЕСТВЕННО, без балла)

ПРИНЦИПЫ (наследует от проекта — см. AGENTS.md):
  • Вся арифметика — в КОДЕ, не в уме. Числа берём из JSON калькуляторов = [факт].
  • НЕ единый процент совместимости: каждый движок отдаёт СВОЮ родную шкалу.
    Системы меряют разные слои — сворачивать в одно число = ложная точность.
  • Направленность: где система асимметрична (用神 Ба Цзы; Варна/Тара/Гана Джйотиш;
    доминирование ДЧ) — считаем ОТДЕЛЬНО «для A» и «для B», не симметричный блоб.
  • Происхождение и расхождения школ — честно. У Аштакуты часть таблиц (промежуточные
    Йони, Вашья, направленная Гана) имеют школьные варианты — помечены provisional,
    пиннятся сверкой с эталонным калькулятором (compat_verify, как verify_all).
  • Совместимость = окна и точки напряжения, НЕ приговор «можно/нельзя».

  • Тип связи и пол — ЯВНО. Хэ Хунь и Аштакута — брачные системы: к не-романтической
    связи числа считаются, но помечаются «категориальная натяжка». Для однополых/
    неопределённых ролей направленные куты (Варна, Гана) даются в обе стороны, итог /36 —
    диапазоном, а не одним числом.
  • Доши (Нади/Бхакут/Мангал) — как СИГНАЛЫ, не вердикты: классические правила отмены
    не вычислены, поэтому не печатаем «доша/нельзя», а «традиционно фактор внимания».

Вход: JSON от bazi.py / jyotish.py / hd.py — по одному файлу на человека.
Использование:
  compat.py A_bazi A_jyotish A_hd B_bazi B_jyotish B_hd [--json] [--rel=романтика|деловые|дружба|семья]
  compat.py --selftest
"""
import sys
import json

# ════════════════════════════════════════════════════════════════════════════
#  Ба Цзы — таблицы взаимодействий (сверены с bazi.py проекта)
# ════════════════════════════════════════════════════════════════════════════
ELEMENTS_RU = ["Дерево", "Огонь", "Земля", "Металл", "Вода"]
PRODUCES = [1, 2, 3, 4, 0]          # 生: Дерево→Огонь→Земля→Металл→Вода→Дерево
CONTROLS = [2, 3, 4, 0, 1]          # 克: Дерево→Земля, Огонь→Металл, ...
STEM_HE = {(0, 5), (1, 6), (2, 7), (3, 8), (4, 9)}              # 五合 стволов
BR_HE = {(0, 1), (2, 11), (3, 10), (4, 9), (5, 8), (6, 7)}     # 六合 ветвей
BR_CLASH = {(0, 6), (1, 7), (2, 8), (3, 9), (4, 10), (5, 11)}   # 六冲
BR_HAI = {(0, 7), (1, 6), (2, 5), (3, 4), (8, 11), (9, 10)}     # 六害
BR_XING = {(2, 5), (5, 8), (2, 8), (0, 3), (1, 10), (7, 10), (1, 7)}  # 刑 (без 自刑)
TRIADS = [{8, 0, 4}, {11, 3, 7}, {2, 6, 10}, {5, 9, 1}]        # 三合 группы

STRONG_PCT = 24.0   # стихия «сильна» в карте, если её доля заметно выше ровной (20%)


def _pair(a, b):
    return (a, b) if a <= b else (b, a)


def _same_triad(a, b):
    return any(a in g and b in g for g in TRIADS)


# ── тип связи и роли (брачные системы + направленные куты) ────────────────────
def _normalize_rel(rt):
    s = (rt or "романтика").lower()
    if any(k in s for k in ("роман", "брак", "пара", "любов", "сожит", "супруг")):
        return "романтика"
    if any(k in s for k in ("дел", "бизнес", "партн", "работ", "основ", "коллег")):
        return "деловые"
    if any(k in s for k in ("семь", "родител", "дет", "брат", "сестр", "родств", "мам", "пап")):
        return "семья"
    if any(k in s for k in ("друж", "друз", "приятел")):
        return "дружба"
    return "другое"


def _is_romantic(rt):
    return _normalize_rel(rt) == "романтика"


def _marriage_caveat(rt):
    """Хэ Хунь и Аштакута — БРАЧНЫЕ системы. К не-романтической связи — категориальная натяжка."""
    if _is_romantic(rt):
        return None
    return (f"⚠ Это брачная система совместимости. Связь указана как «{_normalize_rel(rt)}»: "
            "числа посчитаны механически, но трактовать их как «пригодность» нельзя — "
            "система не про этот тип отношений.")


# ════════════════════════════════════════════════════════════════════════════
#  ДВИЖОК 1 — Ба Цзы (合婚): 5 критериев по /bazi-compare, каждый /2 → /10
# ════════════════════════════════════════════════════════════════════════════
def compat_bazi(b1, b2, rel_type="романтика"):
    dm1, e1 = b1["day_master"]["index"], b1["day_master"]["element_index"]
    dm2, e2 = b2["day_master"]["index"], b2["day_master"]["element_index"]
    db1 = b1["pillars"]["day"]["branch"]["index"]
    db2 = b2["pillars"]["day"]["branch"]["index"]
    dbe1 = b1["pillars"]["day"]["branch"]["element_index"]
    dbe2 = b2["pillars"]["day"]["branch"]["element_index"]
    g1 = b1["input"]["gender"]
    g2 = b2["input"]["gender"]

    # — Критерий 1: стволы дня (/2) — балл симметричен, но у порождения/контроля ЕСТЬ направление
    c1dir = None
    if _pair(dm1, dm2) in STEM_HE:
        c1, c1d = 2.0, "五合 — союз стволов дня (сильное притяжение)"
    elif e1 == e2:
        c1, c1d = 1.5, "одна стихия — похожесть, лёгкое понимание"
    elif PRODUCES[e1] == e2:
        c1, c1d, c1dir = 1.0, "порождение — A питает B", "A→B"
    elif PRODUCES[e2] == e1:
        c1, c1d, c1dir = 1.0, "порождение — B питает A", "B→A"
    elif CONTROLS[e1] == e2:
        c1, c1d, c1dir = 0.5, "контроль — A подавляет/правит B", "A→B"
    else:  # CONTROLS[e2] == e1 — между разными стихиями всегда остаётся контроль в одну сторону
        c1, c1d, c1dir = 0.5, "контроль — B подавляет/правит A", "B→A"

    # — Критерий 2: ветви дня = дворцы супругов в перекрёстке (/2) — симметрично
    p = _pair(db1, db2)
    if db1 == db2:
        c2, c2d = 1.0, "одна ветвь — нейтрально/похоже"
    elif p in BR_HE:
        c2, c2d = 2.0, "六合 — союз дворцов супругов"
    elif _same_triad(db1, db2):
        c2, c2d = 1.5, "三合 — частичная гармония дворцов"
    elif p in BR_CLASH:
        c2, c2d = 0.0, "六冲 — столкновение дворцов супругов"
    elif p in BR_XING:
        c2, c2d = 0.0, "刑 — наказание/напряжение дворцов"
    elif p in BR_HAI:
        c2, c2d = 0.5, "六害 — скрытый вред между дворцами"
    else:
        c2, c2d = 1.0, "нейтрально"

    # — Критерий 3: комплементарность стихий (/2) — НАПРАВЛЕННО [интерпретация]
    ys1 = {y["index"] for y in (b1.get("yongshen") or [])}
    ys2 = {y["index"] for y in (b2.get("yongshen") or [])}
    strong1 = {i for i in range(5)
               if b1["element_balance"][ELEMENTS_RU[i]]["percent"] >= STRONG_PCT}
    strong2 = {i for i in range(5)
               if b2["element_balance"][ELEMENTS_RU[i]]["percent"] >= STRONG_PCT}
    a_helped = ys1 & strong2   # B силён в том, что нужно A
    b_helped = ys2 & strong1   # A силён в том, что нужно B
    c3dir = None
    if a_helped and b_helped:
        c3, c3d, c3dir = 2.0, "взаимное дополнение: каждый силён в нужной другому стихии", "↔"
    elif a_helped or b_helped:
        who = "B→A" if a_helped else "A→B"
        c3, c3d, c3dir = 1.0, f"одностороннее дополнение ({who}) — поддержка не взаимна", who
    elif ys1 & ys2:
        c3, c3d = 0.5, "обоим не хватает одной стихии — общий дефицит, не компенсируют"
    else:
        c3, c3d = 1.0, "стихии нейтральны друг к другу"

    # — Критерий 4: звезда супруга в карте КАЖДОГО (/2) — НАПРАВЛЕННО по полу
    def spouse_star_pct(b, dm_el, gender):
        if "жен" in gender:                      # женщина: муж = 官 (то, что контролирует ХД)
            el = next(e for e in range(5) if CONTROLS[e] == dm_el)
            star = "正官/官杀 (звезда мужа)"
        else:                                    # мужчина: жена = 财 (то, что ХД контролирует)
            el = CONTROLS[dm_el]
            star = "正财/财 (звезда жены)"
        pct = b["element_balance"][ELEMENTS_RU[el]]["percent"]
        return pct, star, ELEMENTS_RU[el]
    pct1, star1, sel1 = spouse_star_pct(b1, e1, g1)
    pct2, star2, sel2 = spouse_star_pct(b2, e2, g2)

    def star_score(pct):
        return 2.0 if pct >= 15 else (1.0 if pct > 0 else 0.5)
    c4 = round((star_score(pct1) + star_score(pct2)) / 2, 2)
    c4d = (f"A: {star1} = {sel1} {pct1:.0f}%; B: {star2} = {sel2} {pct2:.0f}% "
           f"(сильная/живая звезда супруга = устойчивее)")
    same_sex = ("жен" in g1) == ("жен" in g2)
    if same_sex:
        c4d += " ⚠ однополая пара: 财/官 как «звезда супруга» завязаны на пол — роль условна"

    # — Критерий 5: благоприятность СВОЕГО дворца супруга (日支) (/2) — НАПРАВЛЕННО
    def palace_score(dbe, ys, ji):
        if dbe in ys:
            return 2.0, "благоприятен (нужная стихия)"
        if dbe in ji:
            return 0.0, "неблагоприятен (мешающая стихия)"
        return 1.0, "нейтрален"
    ji1 = {j["index"] for j in (b1.get("jishen") or [])}
    ji2 = {j["index"] for j in (b2.get("jishen") or [])}
    s5a, d5a = palace_score(dbe1, ys1, ji1)
    s5b, d5b = palace_score(dbe2, ys2, ji2)
    c5 = round((s5a + s5b) / 2, 2)
    c5d = f"A: дворец {d5a}; B: дворец {d5b}"

    total = round(c1 + c2 + c3 + c4 + c5, 2)
    verdict = ("Отличная" if total >= 8 else "Хорошая" if total >= 6
               else "Средняя, нужны усилия" if total >= 4 else "Сложная, серьёзные конфликты")
    return {
        "system": "bazi_hehun",
        "scale": "/10",
        "criteria": [
            {"name": "Стволы дня", "score": c1, "max": 2, "detail": c1d,
             **({"directional": True, "dir": c1dir} if c1dir else {})},
            {"name": "Ветви дня (дворцы)", "score": c2, "max": 2, "detail": c2d},
            {"name": "Комплементарность стихий", "score": c3, "max": 2, "detail": c3d,
             "directional": True, **({"dir": c3dir} if c3dir else {})},
            {"name": "Звезда супруга", "score": c4, "max": 2, "detail": c4d,
             "directional": True},
            {"name": "Дворец супруга (日支)", "score": c5, "max": 2, "detail": c5d,
             "directional": True},
        ],
        "total": total,
        "verdict": verdict,
        "relationship_type": _normalize_rel(rel_type),
        "marriage_caveat": _marriage_caveat(rel_type),
        "confidence": "факт (взаимодействия) + интерпретация (критерии 3–5 трактуемы)",
    }


# ════════════════════════════════════════════════════════════════════════════
#  ДВИЖОК 2 — Джйотиш (Аштакута / Гуна Милан): 8 кут /36 + Мангал-доша
# ════════════════════════════════════════════════════════════════════════════
RASHI = ["Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева", "Весы", "Скорпион",
         "Стрелец", "Козерог", "Водолей", "Рыбы"]
SIGN_LORD = ["Марс", "Венера", "Меркурий", "Луна", "Солнце", "Меркурий",
             "Венера", "Марс", "Юпитер", "Сатурн", "Сатурн", "Юпитер"]
NAKSHATRAS = ["Ашвини", "Бхарани", "Криттика", "Рохини", "Мригашира", "Ардра", "Пунарвасу",
              "Пушья", "Ашлеша", "Магха", "Пурва Пхалгуни", "Уттара Пхалгуни", "Хаста",
              "Читра", "Свати", "Вишакха", "Анурадха", "Джйештха", "Мула", "Пурва Ашадха",
              "Уттара Ашадха", "Шравана", "Дхаништха", "Шатабхиша", "Пурва Бхадрапада",
              "Уттара Бхадрапада", "Ревати"]
NAK_DEG = 40.0 / 3.0    # ширина накшатры 13°20′ (для оценки хрупкости Луны к времени)

# Варна по раши (4=Брахман..1=Шудра): вода>огонь>земля>воздух
VARNA = [3, 2, 1, 4, 3, 2, 1, 4, 3, 2, 1, 4]   # Овен..Рыбы

# Вашья: группы по раши (0=4ногое,1=человек,2=водное,3=дикое,4=насекомое)
VASHYA_GROUP = [0, 0, 1, 2, 3, 1, 1, 4, 0, 0, 1, 2]   # Овен..Рыбы

# Йони: животное по накшатре (0..13)
YONI_ANIMALS = ["Конь", "Слон", "Овца", "Змея", "Собака", "Кошка", "Крыса",
                "Корова", "Буйвол", "Тигр", "Олень", "Обезьяна", "Мангуст", "Лев"]
YONI = [0, 1, 2, 3, 3, 4, 5, 2, 5, 6, 6, 7, 8, 9, 8, 9, 10, 10, 4, 11, 12, 11, 13, 0, 13, 7, 1]
#       Ашв К  Кри Р  Мр Ар Пу Пш Ашл Мг ПП  УП  Х  Чи Св Виш Ан Дж  Мул ПА  УА  Шр  Дх  Шт  ПБ  УБ  Рев
# Полная матрица 14×14 (сверена: симметрична, диагональ=4, 7 «смертельных» пар=0; источник aaps.space,
# совпадает с подтверждёнными смертельными парами). Порядок = YONI_ANIMALS.
YONI_MATRIX = [
    [4, 2, 2, 3, 2, 2, 2, 1, 0, 1, 3, 3, 2, 1],  # Конь
    [2, 4, 3, 3, 2, 2, 2, 2, 3, 1, 2, 3, 2, 0],  # Слон
    [2, 3, 4, 2, 1, 2, 1, 3, 3, 1, 2, 0, 3, 1],  # Овца
    [3, 3, 2, 4, 2, 1, 1, 1, 1, 2, 2, 2, 0, 2],  # Змея
    [2, 2, 1, 2, 4, 2, 1, 2, 2, 1, 0, 2, 1, 1],  # Собака
    [2, 2, 2, 1, 2, 4, 0, 2, 2, 1, 3, 3, 2, 1],  # Кошка
    [2, 2, 1, 1, 1, 0, 4, 2, 2, 2, 2, 2, 1, 2],  # Крыса
    [1, 2, 3, 1, 2, 2, 2, 4, 3, 0, 3, 2, 2, 1],  # Корова
    [0, 3, 3, 1, 2, 2, 2, 3, 4, 1, 2, 2, 2, 1],  # Буйвол
    [1, 1, 1, 2, 1, 1, 2, 0, 1, 4, 1, 1, 2, 1],  # Тигр
    [3, 2, 2, 2, 0, 3, 2, 3, 2, 1, 4, 2, 2, 1],  # Олень
    [3, 3, 0, 2, 2, 3, 2, 2, 2, 1, 2, 4, 3, 2],  # Обезьяна
    [2, 2, 3, 0, 1, 2, 1, 2, 2, 2, 2, 3, 4, 2],  # Мангуст
    [1, 0, 1, 2, 1, 1, 2, 1, 1, 1, 1, 2, 2, 4],  # Лев
]

# Гана по накшатре (0=Дева,1=Манушья,2=Ракшаса)
GANA = [0, 1, 2, 1, 0, 1, 0, 0, 2, 2, 1, 1, 0, 2, 0, 2, 0, 2, 2, 1, 1, 0, 2, 2, 1, 1, 0]

# Нади по накшатре (0=Ади,1=Мадхья,2=Антья)
NADI = [0, 1, 2, 2, 1, 0, 0, 1, 2, 2, 1, 0, 0, 1, 2, 2, 1, 0, 0, 1, 2, 2, 1, 0, 0, 1, 2]

# Естественные отношения грах (наисаргика): друг/нейтрал/враг
PLANET_FRIENDS = {
    "Солнце":   ({"Луна", "Марс", "Юпитер"}, {"Меркурий"}, {"Венера", "Сатурн"}),
    "Луна":     ({"Солнце", "Меркурий"}, {"Марс", "Юпитер", "Венера", "Сатурн"}, set()),
    "Марс":     ({"Солнце", "Луна", "Юпитер"}, {"Венера", "Сатурн"}, {"Меркурий"}),
    "Меркурий": ({"Солнце", "Венера"}, {"Марс", "Юпитер", "Сатурн"}, {"Луна"}),
    "Юпитер":   ({"Солнце", "Луна", "Марс"}, {"Сатурн"}, {"Меркурий", "Венера"}),
    "Венера":   ({"Меркурий", "Сатурн"}, {"Марс", "Юпитер"}, {"Солнце", "Луна"}),
    "Сатурн":   ({"Меркурий", "Венера"}, {"Юпитер"}, {"Солнце", "Луна", "Марс"}),
}

# Гана-матрица [жених][невеста] (0=Дева,1=Ман,2=Ракшаса) — НАПРАВЛЕННАЯ, Drik Panchang (сверено)
GANA_MATRIX = [[6, 5, 0], [5, 6, 1], [0, 0, 6]]

# Вашья-матрица [группа НЕВЕСТЫ][группа ЖЕНИХА] (Q,H,W,V,K). НАПРАВЛЕННАЯ.
# Сверено по 2 независимым источникам (anytimeastro + поисковая сводка), группы совпадают
# с Drik Panchang. ВАЖНО: операционная схема этой школы = {2, 1.5, 1, 0} (1.5 — особо
# притягивающиеся пары 4ногое↔Лев и человек↔вода), а НЕ {2/1/0.5/0} — то другая традиция,
# не «чинить» 1.5 в 0.5. Невеста-Лев (дикое) почти всегда 0 — это намеренная асимметрия школы.
VASHYA_MATRIX = [
    [2.0, 1.0, 1.0, 1.5, 1.0],   # невеста 4ногое (Q)
    [1.0, 2.0, 1.5, 0.0, 1.0],   # невеста человек (H)
    [1.0, 1.5, 2.0, 1.0, 1.0],   # невеста водное (W)
    [0.0, 0.0, 0.0, 2.0, 0.0],   # невеста дикое (V) — Лев-невеста: 0 со всеми, кроме Льва
    [1.0, 1.0, 1.0, 0.0, 2.0],   # невеста насекомое (K)
]


def _vashya_group(rashi, lon):
    """Группа Вашья по раши; Стрелец/Козерог делятся пополам по долготе Луны (Drik Panchang)."""
    if rashi == 8 and lon is not None:    # Стрелец: 1-я пол. = человек(H), 2-я = 4ногое(Q)
        return 1 if (lon % 30) < 15 else 0
    if rashi == 9 and lon is not None:    # Козерог: 1-я пол. = 4ногое(Q), 2-я = водное(W)
        return 0 if (lon % 30) < 15 else 2
    return VASHYA_GROUP[rashi]


def _graha(j, name):
    for g in j["grahas"]:
        if g["graha"].startswith(name):
            return g
    raise KeyError(name)


def _moon_rashi_idx(j):
    return RASHI.index(_graha(j, "Луна")["rashi"])


def _nak_idx(j):
    return NAKSHATRAS.index(j["moon_nakshatra"]["nakshatra"])


def _planet_rel(a, b):
    if a == b:
        return "friend"
    fr, ne, en = PLANET_FRIENDS[a]
    return "friend" if b in fr else "enemy" if b in en else "neutral"


def _maitri_points(rel1, rel2):
    s = {rel1, rel2}
    if s == {"friend"}:
        return 5.0
    if s == {"friend", "neutral"}:
        return 4.0
    if s == {"neutral"}:
        return 3.0
    if s == {"friend", "enemy"}:
        return 1.0
    if s == {"neutral", "enemy"}:
        return 0.5
    return 0.0   # both enemy


def _mutual_friends(p1, p2):
    return (p1 in PLANET_FRIENDS and p2 in PLANET_FRIENDS and
            _planet_rel(p1, p2) == "friend" and _planet_rel(p2, p1) == "friend")


# ── отмены доши (parihara). Широко-согласованный набор; очки куты по школе остаются 0 ──
# 4 исключённые пары накшатр для Нади: Рохини-Магха, Рохини-П.Бхадрапада, Ашвини-Пунарвасу, Свати-У.Ашадха
NADI_EXEMPT_PAIRS = {frozenset({3, 9}), frozenset({3, 24}), frozenset({0, 6}), frozenset({14, 20})}
# ── Мангал, дом-знаковая таблица (parihara) ─────────────────────────────────────────────
# Знак Марса (индекс раши), гасящий дошу в данном доме ОТ ЛАГНЫ — СВЕРХ знак-правил (свой/
# экзальт/падение/йогакарака/Юпитер), которые проверяются раньше и от точки детекта не зависят.
# Логика школы: Марс безвреден в доме, если стоит в своём знаке ИЛИ в знаке планеты, «дружественной»
# теме дома (2-й/речь→Меркурий; 4-й/дом→Венера; 8-й/долголетие→Юпитер; 7-й→Рак/Козерог).
# ИСТОЧНИК: семейство AstroSage. Эти 5 строк подтверждены фактически ОДНОЙ страницей (astrosight.ai)
# + слабое подкрепление поисковыми ИИ-сводками. aaps.space даёт ту же таблицу, но шорткатом — пословный
# разбор знаков из неё извлечь не удалось (НЕ подтверждает и НЕ опровергает). Итог: по сути ОДИН
# источник → СРЕДНЯЯ уверенность на ячейку, НЕ двойная независимая сверка (как у Йони-матрицы 14×14).
# Дом 1 ОТСУТСТВУЕТ намеренно: в проверенных источниках для Лагны нет отдельных знаков сверх своего/
# экзальт/йогакараки (Овен/Скорпион/Козерог + Лагна Рак/Лев) — они уже гасят дошу в знак-правилах выше.
MANGAL_HOUSE_SIGN_CANCEL = {2: {0, 7, 2, 5}, 4: {1, 6, 0, 7}, 7: {3, 9}, 8: {8, 11}, 12: {2, 5, 1, 6}}
#   дом 2: Овен,Скорпион(свои)+Близнецы,Дева(Меркурий) | дом 4: Телец,Весы(Венера)+Овен,Скорпион(свои)
#   дом 7: Рак,Козерог | дом 8: Стрелец,Рыбы(Юпитер) | дом 12: Близнецы,Дева(Меркурий)+Телец,Весы(Венера)


def _nadi_cancel(gn, bn, gr, br, gpada, bpada):
    """Правило отмены Нади-доши или None (для пары с ОДНОЙ нади)."""
    lg, lb = SIGN_LORD[gr], SIGN_LORD[br]
    if lg == lb:
        return "общий управитель лунных знаков"
    if _mutual_friends(lg, lb):
        return "управители знаков — взаимные друзья"
    if frozenset({gn, bn}) in NADI_EXEMPT_PAIRS:
        return "исключённая пара накшатр"
    if gn == bn and gpada is not None and gpada != bpada:
        return "та же накшатра, но разные пады"
    if gn == bn and gr != br:
        return "та же накшатра, но разные знаки"
    if gn != bn and gr == br:
        return "тот же знак, но разные накшатры"
    return None


def _bhakut_cancel(gr, br, nav_g=None, nav_b=None):
    """Отмена Бхакут-доши: общий/дружественный управитель лунных знаков ИЛИ навамша-лагны."""
    lg, lb = SIGN_LORD[gr], SIGN_LORD[br]
    if lg == lb:
        return "общий управитель лунных знаков"
    if _mutual_friends(lg, lb):
        return "управители знаков — взаимные друзья"
    if nav_g and nav_b:
        if nav_g == nav_b:
            return "общий управитель навамша-лагны"
        if _mutual_friends(nav_g, nav_b):
            return "управители навамша-лагны — взаимные друзья"
    return None


def _mangal_status(j):
    """Мангал от Лагны+Луны+Венеры + отмены. → (present, points[список точек], cancel_rule|None)."""
    mars = _graha(j, "Марс")
    mr = RASHI.index(mars["rashi"])
    h_lagna = mars["house"]
    DOSHA_H = {1, 2, 4, 7, 8, 12}
    points = []
    if h_lagna in DOSHA_H:
        points.append("Лагна")
    moon_r = _moon_rashi_idx(j)
    if ((mr - moon_r) % 12 + 1) in DOSHA_H:
        points.append("Луна")
    try:
        venus_r = RASHI.index(_graha(j, "Венера")["rashi"])
        if ((mr - venus_r) % 12 + 1) in DOSHA_H:
            points.append("Венера")
    except KeyError:
        pass
    if not points:
        return (False, [], None)
    # ── Уровень 1: ЗНАК-зависимые отмены. Зависят от достоинства/аспекта Марса, а НЕ от дома,
    #    поэтому действуют от ЛЮБОЙ точки детекта (Лагна/Луна/Венера). ──
    if mr in (0, 7):
        return (True, points, "Марс в своём знаке (Овен/Скорпион)")
    if mr == 9:
        return (True, points, "Марс в экзальтации (Козерог)")
    if mr == 3:
        return (True, points, "Марс в падении (Рак)")
    if (RASHI.index(j["lagna"]["rashi"]) if j.get("lagna") else None) in (3, 4):
        return (True, points, "Лагна Рак/Лев — Марс йогакарака")
    try:
        jup_r = RASHI.index(_graha(j, "Юпитер")["rashi"])
        if (mr - jup_r) % 12 in (0, 4, 6, 8):
            return (True, points, "Юпитер в соединении/аспекте к Марсу")
    except KeyError:
        pass
    # ── Уровень 2: ДОМ-ЗНАКовая отмена. Применяется ТОЛЬКО когда доша идёт ОТ ЛАГНЫ (h_lagna —
    #    дом Марса от Лагны, по которому задана таблица AstroSage). Если доша лишь от Луны/Венеры
    #    ("Лагна" нет в points) — таблица НЕ применяется (упрощение, но защитимое). Дом 1 в таблице
    #    отсутствует → .get(...,()) вернёт пусто, и Лагна-доша в 1-м доме гасится только Уровнем 1. ──
    if "Лагна" in points and mr in MANGAL_HOUSE_SIGN_CANCEL.get(h_lagna, ()):
        return (True, points, f"знак Марса гасит дошу в {h_lagna}-м доме (от Лагны)")
    return (True, points, None)


MOON_DEG_PER_MIN = 13.176 / 1440.0   # средняя скорость Луны (прибл.): градусов в минуту


def _time_fragility(j):
    """Близость Луны к границам накшатры/знака → какие куты перевернутся от ошибки времени.
    ПРИБЛИЗИТЕЛЬНО (средняя скорость Луны) — флаг, не точный расчёт. None если данных нет."""
    lon = _graha(j, "Луна").get("lon")
    if lon is None:
        return None
    out = []
    d_nak = min(lon % NAK_DEG, NAK_DEG - lon % NAK_DEG)
    if d_nak < 1.0:    # < ~1° ≈ < ~110 минут хода Луны до границы накшатры
        out.append({"boundary": "накшатра", "minutes_approx": round(d_nak / MOON_DEG_PER_MIN),
                    "kutas_at_risk": ["Тара", "Йони", "Гана", "Нади"]})
    d_rashi = min(lon % 30.0, 30.0 - lon % 30.0)
    if d_rashi < 1.0:
        out.append({"boundary": "лунный знак", "minutes_approx": round(d_rashi / MOON_DEG_PER_MIN),
                    "kutas_at_risk": ["Варна", "Вашья", "Граха-Майтри", "Бхакут"]})
    return out or None


# ════════════════════════════════════════════════════════════════════════════
#  Джйотиш — ДОП. слои сверх 8 кут: состояние Марса, сектор брака, наложение домов.
#  ВСЕ информативны: НЕ меняют очки кут, НЕ сворачиваются в процент. Достоинства/дома/
#  долготы — из JSON (= [факт]); ярлыки/пороги — [интерпретация] (веса проектные,
#  компоненты классические). Любой недостающий вход → None/пусто (не падать на неполном
#  JSON, напр. на тест-заглушках без Солнца/Лагны/house_lords).
# ════════════════════════════════════════════════════════════════════════════
BENEFICS_J = {"Юпитер", "Венера", "Меркурий", "Луна"}      # естеств. благие (Меркурий/Луна — мягкие)
MALEFICS_J = {"Сатурн", "Марс", "Солнце", "Раху", "Кету"}  # естеств. вредители
DIGNITY_SCORE = {"экзальтация": 2, "свой знак": 1, "нейтрально": 0, "падение": -2}
DUSTHANA = {6, 8, 12}                 # дома тягости
KENDRA_TRIKONA = {1, 4, 5, 7, 9, 10}  # угловые + тригон
MARS_COMBUST_ORB = 17.0               # традиц. орб «сожжения» (асты) Марса; орб конвенционен
OVERLAY_HOUSES = {1: "тело и «я»", 2: "семья и быт", 4: "дом и сердце", 5: "романтика и дети",
                  7: "партнёрство", 8: "интимность и кризисы", 12: "уединение и постель"}


def _planet_short(graha_name):
    for nm in ("Солнце", "Луна", "Марс", "Меркурий", "Юпитер", "Венера", "Сатурн", "Раху", "Кету"):
        if nm in graha_name:
            return nm
    return graha_name


def _benefic_polarity(short_name):
    return "благо" if short_name in BENEFICS_J else "напряг" if short_name in MALEFICS_J else "нейтр"


def _mars_state(j):
    """Состояние Марса: ретроградность (из JSON) + сожжённость (|Марс−Солнце| < орб).
    Информативный флаг — НЕ меняет очки кут и НЕ считается отменой Мангала: трактовка
    школьно-спорна (часть школ — ослабленный Марс мягче для дош; часть — наоборот труднее).
    None, если Марс не ретро и не сожжён, либо данных нет."""
    try:
        mars = _graha(j, "Марс")
    except (KeyError, TypeError):
        return None
    retro = bool(mars.get("retrograde"))
    sep, combust = None, False
    ml = mars.get("lon")
    try:
        sl = _graha(j, "Солнце").get("lon")
    except (KeyError, TypeError):
        sl = None
    if ml is not None and sl is not None:
        d = abs(ml - sl) % 360.0
        sep = round(min(d, 360.0 - d), 2)
        combust = sep < MARS_COMBUST_ORB
    if not retro and not combust:
        return None
    bits = []
    if combust:
        bits.append(f"сожжён Солнцем (в {sep}° от него, орб {MARS_COMBUST_ORB:g}°)")
    if retro:
        bits.append("идёт обратным ходом (ретро)")
    return {
        "retrograde": retro, "combust": combust, "separation_deg": sep,
        "note": "Марс " + " и ".join(bits) + "; трактовка спорна (ослабляет напор ИЛИ, наоборот, "
                "делает труднее — школы расходятся). Информативно: на очки кут и отмены НЕ влияет.",
    }


def _aspected_houses(planet_short, house):
    """Дома под полным аспектом (дришти) планеты в доме `house`. 7-й — у всех;
    спец-аспекты: Марс 4/8, Юпитер 5/9, Сатурн 3/10."""
    asp = {((house - 1 + 6) % 12) + 1}
    for off in {"Марс": (3, 7), "Юпитер": (4, 8), "Сатурн": (2, 9)}.get(planet_short, ()):
        asp.add(((house - 1 + off) % 12) + 1)
    return asp


def _seventh_strength(j):
    """Сила СОБСТВЕННОГО сектора партнёрства (7-й дом) одного человека: управитель 7-го
    (достоинство + дом), обитатели 7-го, аспекты к 7-му → мягкий ярлык. [интерпретация]:
    компоненты классические, веса проектные. None при нехватке данных. НЕ про пару и
    НЕ часть 36 очков."""
    lords, grahas = j.get("house_lords"), j.get("grahas")
    if not lords or not grahas:
        return None
    seventh = next((h for h in lords if h.get("house") == 7), None)
    if not seventh:
        return None
    lord = seventh.get("lord")
    score, lord_dignity, lord_house = 0, None, None
    try:
        lg = _graha(j, lord)
        lord_dignity, lord_house = lg.get("dignity"), lg.get("house")
        score += DIGNITY_SCORE.get(lord_dignity, 0)
        if lord_house in DUSTHANA:
            score -= 2
        elif lord_house in KENDRA_TRIKONA:
            score += 1
    except (KeyError, TypeError):
        pass
    occupants, aspects = [], []
    for g in grahas:
        nm, h = _planet_short(g.get("graha", "")), g.get("house")
        pol = _benefic_polarity(nm)
        delta = 1 if pol == "благо" else -1 if pol == "напряг" else 0
        if h == 7:
            occupants.append({"planet": nm, "polarity": pol})
            score += delta
        elif h and 7 in _aspected_houses(nm, h):
            aspects.append({"planet": nm, "polarity": pol})
            score += delta
    label = "крепкий" if score >= 2 else "под нагрузкой" if score <= -2 else "средний"
    occ_s = ", ".join(f"{o['planet']}({o['polarity']})" for o in occupants) or "пусто"
    asp_s = ", ".join(f"{a['planet']}({a['polarity']})" for a in aspects) or "нет"
    return {
        "label": label, "score": score, "lord": lord,
        "lord_dignity": lord_dignity, "lord_house": lord_house,
        "occupants": occupants, "aspects": aspects,
        "detail": f"сектор партнёрства — {label}: его управитель {lord} "
                  f"({lord_dignity or '—'}, дом {lord_house or '—'}); в самом 7-м: {occ_s}; "
                  f"смотрят на 7-й: {asp_s}",
        "confidence": "интерпретация (компоненты классические, веса проектные); "
                      "про собственный брачный сектор человека, не про пару, не часть 36 очков",
    }


def _house_overlay(ja, jb):
    """Наложение домов: чьи планеты в какие ЗНАКОВЫЕ дома другого попадают (дом планеты X в
    карте Y = отсчёт знаков от Лагны Y). Слой синастрии, НЕ классическая кута и НЕ часть очков.
    None-безопасно (нет Лагны → пусто)."""
    def lay(src, dst):
        out = []
        lag_rashi = (dst.get("lagna") or {}).get("rashi")
        if lag_rashi not in RASHI:
            return out
        lag = RASHI.index(lag_rashi)
        for g in src.get("grahas", []):
            r = g.get("rashi")
            if r not in RASHI:
                continue
            house = (RASHI.index(r) - lag) % 12 + 1
            if house in OVERLAY_HOUSES:
                nm = _planet_short(g.get("graha", ""))
                out.append({"planet": nm, "house": house, "area": OVERLAY_HOUSES[house],
                            "polarity": _benefic_polarity(nm)})
        return out
    return {
        "A_in_B": lay(ja, jb), "B_in_A": lay(jb, ja),
        "note": "Чьи планеты в какие зоны другого попадают (дома знаковые, от Лагны другого). "
                "Слой синастрии, НЕ часть 36 очков; благ./напряж. — тенденции, не вердикт.",
    }


def compat_jyotish(j1, j2, gender1, gender2, rel_type="романтика"):
    male1, fem1 = "муж" in gender1, "жен" in gender1
    male2, fem2 = "муж" in gender2, "жен" in gender2
    opposite = (male1 and fem2) or (fem1 and male2)
    roles_defined = _is_romantic(rel_type) and opposite   # жених/невеста канонично определены?

    if roles_defined and fem1 and male2:
        gj, bj, groom_is = j2, j1, "B"
    else:
        gj, bj, groom_is = j1, j2, "A"   # гетеро-романтика с женихом A, либо роль условна
    gn, bn = _nak_idx(gj), _nak_idx(bj)
    gr, br = _moon_rashi_idx(gj), _moon_rashi_idx(bj)

    kutas = []
    ambiguous = []                # направленные куты, расходящиеся при смене роли
    varna_sw = gana_sw = None

    # 1 Варна (1) — НАПРАВЛЕННО (зависит от роли жених/невеста)
    varna = 1.0 if VARNA[gr] >= VARNA[br] else 0.0
    if roles_defined:
        kutas.append(("Варна", varna, 1,
                      "каста жениха ≥ касты невесты" if varna else "каста невесты выше → 0", True))
    else:
        varna_sw = 1.0 if VARNA[br] >= VARNA[gr] else 0.0
        if varna_sw != varna:
            ambiguous.append("Варна")
        kutas.append(("Варна", varna, 1,
                      f"роль не определена: в одну сторону {varna}, в обратную {varna_sw}",
                      True, "роль условна"))

    # 2 Вашья (2) — матрица [невеста][жених]; половинные знаки по долготе Луны
    bvg = _vashya_group(br, _graha(bj, "Луна").get("lon"))
    gvg = _vashya_group(gr, _graha(gj, "Луна").get("lon"))
    vashya = float(VASHYA_MATRIX[bvg][gvg])
    kutas.append(("Вашья", vashya, 2, "влияние/притяжение по группам знаков (направленно)", True))

    # 3 Тара (3) — обе стороны
    def tara_ok(a, b):
        cnt = ((b - a) % 27) + 1
        r = cnt % 9
        return r not in (3, 5, 7)   # r==0 → тара 9 (благо)
    tara = (1.5 if tara_ok(bn, gn) else 0.0) + (1.5 if tara_ok(gn, bn) else 0.0)
    kutas.append(("Тара", tara, 3, "здоровье/благополучие по счёту накшатр", True))

    # 4 Йони (4) — полная сверенная матрица 14×14 (симметрична)
    ya, yb = YONI[gn], YONI[bn]
    yoni = float(YONI_MATRIX[ya][yb])
    ylabel = {4: "одно животное — макс. близость", 3: "дружественные", 2: "нейтральные",
              1: "враждебные", 0: "смертельные враги (Йони-доша)"}[int(yoni)]
    kutas.append(("Йони", yoni, 4, f"{YONI_ANIMALS[ya]}/{YONI_ANIMALS[yb]} — {ylabel}", False))

    # 5 Граха-Майтри (5) — дружба управителей лунных знаков
    l1, l2 = SIGN_LORD[gr], SIGN_LORD[br]
    maitri = _maitri_points(_planet_rel(l1, l2), _planet_rel(l2, l1))
    kutas.append(("Граха-Майтри", maitri, 5, f"управители {l1} / {l2} — ум/дружба", False))

    # 6 Гана (6) — НАПРАВЛЕННАЯ матрица [жених][невеста]
    gana = float(GANA_MATRIX[GANA[gn]][GANA[bn]])
    gnames = ["Дева", "Манушья", "Ракшаса"]
    if roles_defined:
        kutas.append(("Гана", gana, 6,
                      f"темперамент {gnames[GANA[gn]]} (жених) / {gnames[GANA[bn]]} (невеста)", True))
    else:
        gana_sw = float(GANA_MATRIX[GANA[bn]][GANA[gn]])
        if gana_sw != gana:
            ambiguous.append("Гана")
        kutas.append(("Гана", gana, 6,
                      f"{gnames[GANA[gn]]}/{gnames[GANA[bn]]}: роль не определена, "
                      f"в одну сторону {gana}, в обратную {gana_sw}", True, "роль условна"))

    # 7 Бхакут (7) — доша + ПРОВЕРКА ОТМЕНЫ (parihara). Очки куты по школе остаются 0.
    diff = (gr - br) % 12
    bhakut = 0.0 if diff in (1, 11, 4, 8, 5, 7) else 7.0
    bhakut_cancel = None
    if bhakut == 0:
        bhakut_cancel = _bhakut_cancel(gr, br,
                                       gj.get("navamsa", {}).get("lagna_lord"),
                                       bj.get("navamsa", {}).get("lagna_lord"))
        bd = (f"знаки 2/12, 5/9 или 6/8, но доша ГАСИТСЯ: {bhakut_cancel} (очки по школе = 0)"
              if bhakut_cancel else
              "знаки 2/12, 5/9 или 6/8 — доша есть, классич. отмены не сработали; "
              "традиц. реальный фактор (всё равно окно, не приговор)")
    else:
        bd = "положение лунных знаков благоприятно"
    kutas.append(("Бхакут", bhakut, 7, bd, False))

    # 8 Нади (8) — доша + ПРОВЕРКА ОТМЕНЫ (parihara). Очки куты по школе остаются 0.
    nadi = 8.0 if NADI[gn] != NADI[bn] else 0.0
    nnames = ["Ади", "Мадхья", "Антья"]
    nadi_cancel = None
    if nadi:
        nd = f"разные нади ({nnames[NADI[gn]]}/{nnames[NADI[bn]]})"
    else:
        gpada, bpada = gj["moon_nakshatra"].get("pada"), bj["moon_nakshatra"].get("pada")
        nadi_cancel = _nadi_cancel(gn, bn, gr, br, gpada, bpada)
        nd = (f"одна нади ({nnames[NADI[gn]]}), но доша ГАСИТСЯ: {nadi_cancel} (очки по школе = 0)"
              if nadi_cancel else
              f"одна нади ({nnames[NADI[gn]]}) — доша есть, классич. отмены не сработали; "
              "традиц. реальный фактор (всё равно окно, не приговор)")
    kutas.append(("Нади", nadi, 8, nd, False))

    total = round(sum(k[1] for k in kutas), 2)
    if ambiguous:   # роль не определена и направленные куты расходятся
        total_alt = round(total - varna - gana + varna_sw + gana_sw, 2)
        lo, hi = sorted((total, total_alt))
        if lo == hi:   # двусмысленности взаимно погасились → итог устойчив к роли
            total_display = str(total)
            verdict = (f"итог {total}/36 устойчив к роли, хотя отдельные куты "
                       f"({', '.join(ambiguous)}) зависят от роли; порог 18 — ориентир, не приговор")
        else:          # итог реально плавает → диапазоном, не одним числом
            total_display = f"{lo}–{hi}"
            verdict = (f"роль жениха/невесты не определена → итог {lo}–{hi} из 36 "
                       "(направленные куты двусмысленны); порог 18 — ориентир, не приговор")
    else:
        total_display = str(total)
        verdict = ("высоко" if total >= 25 else
                   "над традиционным порогом 18 (ориентир школы)" if total >= 18 else
                   "ниже традиционного порога 18 — это ориентир школы, НЕ приговор")

    # Мангал от Лагны+Луны+Венеры + индивидуальные отмены + взаимное гашение
    p1, pts1, canc1 = _mangal_status(j1)
    p2, pts2, canc2 = _mangal_status(j2)
    act1, act2 = p1 and not canc1, p2 and not canc2   # активен = есть и индивидуально НЕ погашен
    if act1 and act2:
        mverdict = "Марс «жёсткий» у обоих, индивидуально не погашен — традиц. взаимно смягчается"
    elif act1 or act2:
        who, pts = ("A", pts1) if act1 else ("B", pts2)
        mverdict = (f"Марс «жёсткий» у {who} (от {', '.join(pts)}), отмены не сработали — "
                    "традиц. фактор внимания (НЕ приговор)")
    elif p1 or p2:
        bits = [f"{w}: {c}" for w, p, c in (("A", p1, canc1), ("B", p2, canc2)) if p and c]
        mverdict = "Марс «жёсткий», но гасится — " + "; ".join(bits)
    else:
        mverdict = "Марс не в «жёстких» позициях (Лагна/Луна/Венера) ни у кого"

    # — ДОП. слои (информативны, очки кут не меняют): состояние Марса, сектор брака, наложение —
    ms_A, ms_B = _mars_state(j1), _mars_state(j2)
    mbits = [f"{w}: {st['note']}" for w, active, st in
             (("A", act1, ms_A), ("B", act2, ms_B)) if active and st]
    if mbits:
        mverdict += " | состояние Марса — " + "; ".join(mbits)
    seventh = {"A": _seventh_strength(j1), "B": _seventh_strength(j2)}
    house_overlay = _house_overlay(j1, j2)

    return {
        "system": "jyotish_ashtakoota",
        "scale": "/36",
        "relationship_type": _normalize_rel(rel_type),
        "marriage_caveat": _marriage_caveat(rel_type),
        "roles_defined": roles_defined,
        "groom_is": groom_is if roles_defined else "роль условна (по умолчанию A=жених)",
        "ambiguous_kutas": ambiguous,
        "kutas": [
            {"name": k[0], "score": k[1], "max": k[2], "detail": k[3],
             "directional": k[4], **({"status": k[5]} if len(k) > 5 and k[5] else {})}
            for k in kutas
        ],
        "total": total,
        "total_display": total_display,
        "verdict": verdict,
        "dosha_cancellations": {
            "nadi": nadi_cancel, "bhakut": bhakut_cancel,
            "mangal_A": canc1 if p1 else None, "mangal_B": canc2 if p2 else None,
        },
        "mangal_signal": {
            "A_points": pts1, "A_present": p1, "A_cancel": canc1,
            "B_points": pts2, "B_present": p2, "B_cancel": canc2,
            "A_mars_state": ms_A, "B_mars_state": ms_B,
            "note_verdict": mverdict,
            "method_note": "детект от Лагны+Луны+Венеры. ЗНАК-отмены (свой/экзальт/падение/йогакарака "
                           "Рак,Лев/аспект Юпитера) — от любой точки детекта; ДОМ-ЗНАКовая таблица — "
                           "ТОЛЬКО от Лагны (от Луны/Венеры не применяется). Плюс взаимное гашение. "
                           "Ретро/комбуст Марса — ВЫЧИСЛЕНЫ (A_mars_state/B_mars_state): информативный "
                           "флаг спорной трактовки, на очки и отмены НЕ влияет. Возрастные смягчения "
                           "намеренно опущены (нет классической основы). Сила 7-го дома и наложение "
                           "домов — отдельными полями (seventh_house/house_overlay), синастрия-слой, не "
                           "часть 36 очков; межкарточные аспекты и D9-синастрия по-прежнему НЕ считаются",
        },
        "seventh_house": seventh,
        "house_overlay": house_overlay,
        "time_fragility": {"A": _time_fragility(j1), "B": _time_fragility(j2)},
        "confidence": "факт (накшатры/раши/Марс); Йони/Гана/Вашья сверены по Drik Panchang/AstroSage; "
                      "детект Мангала и знак-отмены (свой/экзальт/падение/йогакарака) — широко-согласованы; "
                      "дом-знаковая таблица Мангала — ОДИН источник (семейство AstroSage), средняя "
                      "уверенность на ячейку (НЕ двойная независимая сверка, как у Йони)",
        "school_note": "Северо-индийский Аштакута (Drik Panchang/AstroSage). Вашья — самая "
                       "разнящаяся кута: тут схема {2/1.5/1/0}, у части школ {2/1/0.5/0}. "
                       "Веса кут и Гана/Бхакут/Нади как вето различаются по школам — не приговор.",
    }


# ════════════════════════════════════════════════════════════════════════════
#  ДВИЖОК 3 — Дизайн Человека: карта связей (качественно, без балла)
# ════════════════════════════════════════════════════════════════════════════
def _hd_gates(h):
    acts = h["activations"]
    return {a["gate"] for a in acts["personality"]} | {a["gate"] for a in acts["design"]}


def _hd_channels(h):
    out = []
    for ch in h["all_channels"]:
        ga, gb = (int(x) for x in ch["gates"].split("-"))
        out.append((ga, gb, ch.get("name", ""), ch.get("centers", "")))
    return out


def compat_hd(h1, h2):
    g1, g2 = _hd_gates(h1), _hd_gates(h2)
    em, comp, compromise, dom = [], [], [], []
    for ga, gb, name, centers in _hd_channels(h1):
        a_full = ga in g1 and gb in g1
        b_full = ga in g2 and gb in g2
        a_has = (ga in g1) + (gb in g1)
        b_has = (ga in g2) + (gb in g2)
        entry = {"channel": f"{ga}-{gb}", "name": name, "centers": centers}
        if a_full and b_full:
            comp.append(entry)
        elif a_full and b_has == 0:
            dom.append({**entry, "who": "A определяет, у B пусто"})
        elif b_full and a_has == 0:
            dom.append({**entry, "who": "B определяет, у A пусто"})
        elif a_full and b_has == 1:
            compromise.append({**entry, "who": "A целиком, B половина"})
        elif b_full and a_has == 1:
            compromise.append({**entry, "who": "B целиком, A половина"})
        elif a_has == 1 and b_has == 1 and not a_full and not b_full:
            # электромагнетика: каждый держит РАЗНЫЕ ворота, вместе замыкают канал
            a_gate = ga if ga in g1 else gb
            b_gate = ga if ga in g2 else gb
            if a_gate != b_gate:
                em.append({**entry, "who": f"A:{a_gate} ↔ B:{b_gate}"})
    return {
        "system": "human_design_connection",
        "scale": "качественно (без единого балла — у ДЧ нет очковой системы)",
        "types": {"A": h1.get("type"), "B": h2.get("type")},
        "authorities": {"A": h1.get("authority"), "B": h2.get("authority")},
        "electromagnetic": em,      # притяжение: разные половинки одного канала
        "companionship": comp,      # одинаковость: один и тот же канал у обоих
        "compromise": compromise,   # один тянет: целый канал vs половина
        "dominance": dom,           # один «перекрашивает» открытое другого
        "counts": {"electromagnetic": len(em), "companionship": len(comp),
                   "compromise": len(compromise), "dominance": len(dom)},
        "type_note": _type_interaction(h1.get("type"), h2.get("type")),
        "confidence": "факт (ворота обоих из калькулятора); метод реальный, но СОВРЕМЕННЫЙ (1987)",
    }


def _type_interaction(t1, t2):
    s = {t1, t2}
    if "Проектор" in s and ("Генератор" in s or "Манифестирующий Генератор" in s):
        return ("Проектор + Генератор: классическая пара — Генератор даёт жизненную силу, "
                "Проектор направляет; но Проектору нужно ПРИГЛАШЕНИЕ, иначе горечь.")
    if t1 == t2 == "Манифестор":
        return "Два Манифестора: оба инициируют — критично информировать друг друга, иначе гнев."
    if "Рефлектор" in s:
        return "С Рефлектором: ему нужен лунный цикл на решения — не торопить."
    return ("Типы: " + (t1 or "?") + " + " + (t2 or "?") +
            " — сверять стратегии и авторитеты (как каждый принимает решения).")


# ════════════════════════════════════════════════════════════════════════════
#  Дайджест «легче / труднее» — перевод баллов в человеческий язык (детерминирован)
# ════════════════════════════════════════════════════════════════════════════
KUTA_MEANING = {
    "Варна": "духовная/рабочая совместимость",
    "Вашья": "взаимное влияние и притяжение",
    "Тара": "благополучие и здоровье",
    "Йони": "телесная и интимная близость",
    "Граха-Майтри": "ментальная дружба и взаимопонимание",
    "Гана": "темперамент и характер",
    "Бхакут": "эмоциональная и бытовая гармония",
    "Нади": "здоровье и потомство (традиционно)",
}


def _ease_friction(result):
    """Детерминированно раскладывает сигналы трёх движков на «легче / труднее / по-разному
    для A и B». Числа НЕ складываются — это перевод баллов в язык, а не сумма."""
    ease, friction, directional = [], [], []

    def add_dir(system, topic, detail):
        directional.append({"system": system, "topic": topic, "detail": detail})

    # — Ба Цзы (5 критериев, /2) —
    for c in result["bazi"]["criteria"]:
        frac = c["score"] / c["max"]
        it = {"system": "Ба Цзы", "topic": c["name"], "detail": c["detail"]}
        if frac >= 0.75:
            ease.append(it)
        elif frac <= 0.25:
            friction.append(it)
        if c.get("directional"):
            add_dir("Ба Цзы", c["name"], c["detail"])

    # — Джйотиш (8 кут; доши — напряжение лишь если НЕ погашены) —
    canc = result["jyotish"]["dosha_cancellations"]
    for k in result["jyotish"]["kutas"]:
        name, topic = k["name"], KUTA_MEANING.get(k["name"], k["name"])
        it = {"system": "Джйотиш", "topic": topic, "detail": k["detail"]}
        if name in ("Нади", "Бхакут") and k["score"] == 0:
            cancelled = canc["nadi"] if name == "Нади" else canc["bhakut"]
            if not cancelled:
                friction.append(it)          # доша есть и не погашена → реальное напряжение
            continue                          # погашена → нейтрально, не тащим в легче/труднее
        frac = k["score"] / k["max"]
        if frac >= 0.66:
            ease.append(it)
        elif frac <= 0.34:
            friction.append(it)
        if k.get("directional"):
            add_dir("Джйотиш", topic, k["detail"])
    ms = result["jyotish"]["mangal_signal"]    # Мангал активен (не погашен) → напряжение
    if (ms["A_present"] and not ms["A_cancel"]) or (ms["B_present"] and not ms["B_cancel"]):
        friction.append({"system": "Джйотиш", "topic": "Марс (напор/конфликтность)",
                         "detail": ms["note_verdict"]})

    # — Дизайн Человека (электромагнетика/товарищество = легче; компромисс/доминирование = труднее) —
    hd = result["human_design"]
    for ch in hd["electromagnetic"]:
        ease.append({"system": "Дизайн Человека", "topic": "притяжение (искра)",
                     "detail": f"канал «{ch['name']}» — {ch.get('who', '')}"})
    for ch in hd["companionship"]:
        ease.append({"system": "Дизайн Человека", "topic": "похожесть/лёгкость",
                     "detail": f"общий канал «{ch['name']}»"})
    for ch in hd["compromise"]:
        friction.append({"system": "Дизайн Человека", "topic": "один тянет (компромисс)",
                         "detail": f"канал «{ch['name']}» — {ch.get('who', '')}"})
        add_dir("Дизайн Человека", "компромисс", f"«{ch['name']}»: {ch.get('who', '')}")
    for ch in hd["dominance"]:
        friction.append({"system": "Дизайн Человека", "topic": "один перекрашивает другого",
                         "detail": f"канал «{ch['name']}» — {ch.get('who', '')}"})
        add_dir("Дизайн Человека", "доминирование", f"«{ch['name']}»: {ch.get('who', '')}")

    # — Доп. слои Джйотиша (per-person/направленные → «по-разному для A и B») —
    jres = result.get("jyotish", {})
    sev = jres.get("seventh_house") or {}
    for who in ("A", "B"):
        s = sev.get(who)
        if s:
            add_dir("Джйотиш", f"сектор партнёрства (у {who})", s["detail"])
    ov = jres.get("house_overlay") or {}
    for key, frm, to in (("A_in_B", "A", "B"), ("B_in_A", "B", "A")):
        for it in ov.get(key, []):
            if it["house"] in (4, 5, 7, 8) and it["polarity"] != "нейтр":
                tone = "мягко поддерживает" if it["polarity"] == "благо" else "добавляет трения"
                add_dir("Джйотиш", "наложение домов",
                        f"{it['planet']} ({frm}) в зоне «{it['area']}» у {to} — {tone}")

    return {"ease": ease, "friction": friction, "directional": directional,
            "note": "Перевод баллов в язык «легче/труднее». Числа трёх систем НЕ складываются — "
                    "они о разном. Это окна и точки внимания, не приговор."}


# ════════════════════════════════════════════════════════════════════════════
#  Сборка
# ════════════════════════════════════════════════════════════════════════════
def compare(b1, j1, h1, b2, j2, h2, rel_type="романтика"):
    g1 = b1["input"]["gender"]
    g2 = b2["input"]["gender"]
    res = {
        "meta": {
            "relationship_type": _normalize_rel(rel_type),
            "note": "НЕ единый процент. Три независимых языка, разные слои и шкалы.",
            "independence": "Ба Цзы / Джйотиш / Дизайн Человека — 3 независимых корня.",
            "framing": "Окна и точки напряжения, НЕ приговор «вам можно/нельзя».",
            "marriage_systems_note": _marriage_caveat(rel_type),  # None если романтика
        },
        "bazi": compat_bazi(b1, b2, rel_type),
        "jyotish": compat_jyotish(j1, j2, g1, g2, rel_type),
        "human_design": compat_hd(h1, h2),   # ДЧ-связи не зависят от типа отношений
    }
    res["ease_friction"] = _ease_friction(res)   # первичный слой — числа вторичны
    return res


# ════════════════════════════════════════════════════════════════════════════
#  Самопроверка (инварианты — не сверка значений, та отдельно)
# ════════════════════════════════════════════════════════════════════════════
def selftest():
    ok = True
    def check(cond, msg):
        nonlocal ok
        ok = ok and cond
        print(f"[{'PASS' if cond else 'FAIL'}] {msg}")

    check(len(YONI) == 27, f"Йони: карта на 27 накшатр (={len(YONI)})")
    check(max(YONI) == 13 and min(YONI) == 0, "Йони: животные 0..13")
    check(len(GANA) == 27 and sorted(set(GANA)) == [0, 1, 2], "Гана: 27 накшатр, 3 класса")
    check([GANA.count(i) for i in (0, 1, 2)] == [9, 9, 9], "Гана: ровно 9/9/9")
    check([NADI.count(i) for i in (0, 1, 2)] == [9, 9, 9], "Нади: ровно 9/9/9")
    check(len(VARNA) == 12 and len(VASHYA_GROUP) == 12, "Варна/Вашья: 12 раши")
    # Йони-матрица: симметрична, диагональ=4, ровно 7 смертельных (нулевых) пар
    check(all(YONI_MATRIX[i][j] == YONI_MATRIX[j][i] for i in range(14) for j in range(14)),
          "Йони-матрица симметрична")
    check(all(YONI_MATRIX[i][i] == 4 for i in range(14)), "Йони: диагональ = 4")
    zeros = sum(1 for i in range(14) for j in range(i + 1, 14) if YONI_MATRIX[i][j] == 0)
    check(zeros == 7, f"Йони: ровно 7 смертельных пар (={zeros})")
    check(GANA_MATRIX[1][2] == 1 and GANA_MATRIX[2][1] == 0,
          "Гана: Манушья→Ракшаса=1, Ракшаса→Манушья=0 (Drik Panchang)")
    check(all(VASHYA_MATRIX[i][i] == 2 for i in range(5)), "Вашья: диагональ (та же группа) = 2")
    check(VASHYA_MATRIX[0][3] == 1.5 and VASHYA_MATRIX[3][0] == 0.0,
          "Вашья направленна: невеста-4ногое×жених-Лев=1.5, невеста-Лев×жених-4ногое=0")
    check(all(VASHYA_MATRIX[3][j] == (2.0 if j == 3 else 0.0) for j in range(5)),
          "Вашья: невеста-Лев (дикое) = 0 со всеми, кроме Льва")
    check(sorted({v for row in VASHYA_MATRIX for v in row}) == [0.0, 1.0, 1.5, 2.0],
          "Вашья: схема значений = {0, 1, 1.5, 2} (НЕ 0.5 — то другая школа)")
    # Граха-Майтри диапазон
    pts = {_maitri_points(_planet_rel(a, b), _planet_rel(b, a))
           for a in PLANET_FRIENDS for b in PLANET_FRIENDS}
    check(all(0 <= p <= 5 for p in pts), "Граха-Майтри: очки в [0,5]")
    check(all(0 <= v <= 6 for row in GANA_MATRIX for v in row), "Гана-матрица в [0,6]")
    check(1 + 2 + 3 + 4 + 5 + 6 + 7 + 8 == 36, "Аштакута: максимум кут = 36")

    # — Юнит-тесты ЛОГИКИ кут на парах, разобранных вручную (ловит ошибки счёта/направления) —
    def stub(nak, moon_rashi, mars_house=3, mars_rashi=4, pada=1):
        return {"moon_nakshatra": {"nakshatra": NAKSHATRAS[nak], "pada": pada, "lord": "-"},
                "grahas": [{"graha": "Луна (Чандра)", "rashi": RASHI[moon_rashi], "house": 5},
                           {"graha": "Марс (Мангала)", "rashi": RASHI[mars_rashi], "house": mars_house}]}

    def kscore(res, name):
        return next(k["score"] for k in res["kutas"] if k["name"] == name)

    # Пара-1: жених Ашвини/Рак(М) × невеста Бхарани/Овен(Ж) — разобрана вручную, итог 31
    r1 = compat_jyotish(stub(0, 3), stub(1, 0), "мужской", "женский")
    exp = {"Варна": 1.0, "Вашья": 1.0, "Тара": 3.0, "Йони": 2.0,
           "Граха-Майтри": 4.0, "Гана": 5.0, "Бхакут": 7.0, "Нади": 8.0}
    for n, v in exp.items():
        check(kscore(r1, n) == v, f"Аштакута·{n}: {kscore(r1, n)} (ждали {v})")
    check(r1["total"] == 31.0, f"Аштакута·итог пары-1 = {r1['total']} (ждали 31)")
    # направленность Варны: поменяли знаки → жених ниже → 0
    check(kscore(compat_jyotish(stub(0, 0), stub(1, 3), "мужской", "женский"), "Варна") == 0.0,
          "Варна направленна (жених ниже невесты → 0)")
    # направленность Ганы: Манушья(жених)×Ракшаса(невеста)=1, наоборот=0
    check(kscore(compat_jyotish(stub(1, 0), stub(2, 0), "мужской", "женский"), "Гана") == 1.0,
          "Гана: Манушья→Ракшаса = 1")
    check(kscore(compat_jyotish(stub(2, 0), stub(1, 0), "мужской", "женский"), "Гана") == 0.0,
          "Гана: Ракшаса→Манушья = 0")
    # Йони смертельная пара (Конь×Буйвол) = 0; Нади-доша (одна нади) = 0; Бхакут 7-й (diff 6) = 7
    check(kscore(compat_jyotish(stub(0, 0), stub(12, 0), "мужской", "женский"), "Йони") == 0.0,
          "Йони: Конь×Буйвол = 0")
    check(kscore(compat_jyotish(stub(0, 0), stub(5, 0), "мужской", "женский"), "Нади") == 0.0,
          "Нади: одна нади (Ади) → 0")
    check(kscore(compat_jyotish(stub(0, 0), stub(0, 6), "мужской", "женский"), "Бхакут") == 7.0,
          "Бхакут: 7-й знак (Овен/Весы) → 7")

    # — Отмены доши (parihara): очки куты по школе остаются 0, но доша помечается погашенной —
    # Нади гасится общим управителем знаков (оба Овен → Марс)
    rn = compat_jyotish(stub(0, 0), stub(5, 0), "мужской", "женский")
    check(kscore(rn, "Нади") == 0.0 and rn["dosha_cancellations"]["nadi"],
          "Нади-доша ГАСИТСЯ (общий управитель), очки = 0")
    # Нади НЕ гасится: разные накшатры/знаки/управители в одной нади (Овен/Марс vs Дева/Меркурий)
    rn2 = compat_jyotish(stub(0, 0), stub(12, 5), "мужской", "женский")
    check(kscore(rn2, "Нади") == 0.0 and rn2["dosha_cancellations"]["nadi"] is None,
          "Нади-доша НЕ гасится (разные знаки/управители)")
    # Бхакут (6/8 Овен/Скорпион) гасится общим управителем Марс
    rb = compat_jyotish(stub(0, 0), stub(17, 7), "мужской", "женский")
    check(kscore(rb, "Бхакут") == 0.0 and rb["dosha_cancellations"]["bhakut"],
          "Бхакут-доша ГАСИТСЯ (общий управитель Овен/Скорпион)")
    # Мангал активен: Марс в Льве (не свой/экзальт/падение) в доме 7
    rm = compat_jyotish(stub(0, 0, mars_house=7, mars_rashi=4), stub(1, 3), "мужской", "женский")
    check(rm["mangal_signal"]["A_present"] and rm["mangal_signal"]["A_cancel"] is None,
          "Мангал активен (Марс в Льве, дом 7, отмены нет)")
    # Мангал гасится: Марс в своём знаке (Овен) в доме 7
    rm2 = compat_jyotish(stub(0, 0, mars_house=7, mars_rashi=0), stub(1, 3), "мужской", "женский")
    check(rm2["mangal_signal"]["A_present"] and rm2["mangal_signal"]["A_cancel"],
          "Мангал гасится (Марс в своём знаке Овен)")
    # — Расширенный parihara: 3 точки детекта, дом-знак, навамша-Бхакут, исключённые пары Нади —
    r3pt = compat_jyotish(stub(0, 0, mars_house=3, mars_rashi=1), stub(1, 3), "мужской", "женский")
    check("Луна" in r3pt["mangal_signal"]["A_points"], "Мангал детект от Луны (не только Лагны)")
    rmh = compat_jyotish(stub(0, 0, mars_house=8, mars_rashi=8), stub(1, 3), "мужской", "женский")
    check(rmh["mangal_signal"]["A_present"] and "доме" in (rmh["mangal_signal"]["A_cancel"] or ""),
          "Мангал гасится дом-знаковой таблицей (8-й дом, Стрелец)")
    # — Golden: сверенные ячейки таблицы AstroSage зафиксированы; дом 1 намеренно отсутствует —
    check(MANGAL_HOUSE_SIGN_CANCEL == {2: {0, 7, 2, 5}, 4: {1, 6, 0, 7}, 7: {3, 9}, 8: {8, 11},
                                       12: {2, 5, 1, 6}},
          "Дом-знак Мангала: ячейки = сверенной таблице AstroSage")
    check(1 not in MANGAL_HOUSE_SIGN_CANCEL,
          "Дом 1 вне таблицы намеренно (гасится только знак-правилами)")
    # — Дом-знак применяется ТОЛЬКО от Лагны (бул.2). Марс в Близнецах (есть в табл. домов 2 и 12): —
    #   доша лишь от Луны (Марс в 3-м доме от Лагны = не-доша, но 2-й от Луны) → дом-знак НЕ гасит
    rmoon = compat_jyotish(stub(0, 1, mars_house=3, mars_rashi=2), stub(1, 3), "мужской", "женский")
    check(rmoon["mangal_signal"]["A_points"] == ["Луна"] and
          rmoon["mangal_signal"]["A_cancel"] is None,
          "Дом-знак НЕ гасит дошу от Луны (Близнецы, не от Лагны) → Мангал активен")
    #   тот же знак Марса, но 2-й дом ОТ ЛАГНЫ → дом-знак гасит
    rlag = compat_jyotish(stub(0, 4, mars_house=2, mars_rashi=2), stub(1, 3), "мужской", "женский")
    check("Лагна" in rlag["mangal_signal"]["A_points"] and
          "2-м доме" in (rlag["mangal_signal"]["A_cancel"] or ""),
          "Дом-знак гасит дошу от Лагны (Близнецы, 2-й дом)")
    # — Дом 1 без знак-таблицы (бул.1): Марс в Овне гасится как СВОЙ знак, не как дом-знак —
    rl_own = compat_jyotish(stub(0, 4, mars_house=1, mars_rashi=0), stub(1, 3), "мужской", "женский")
    check(rl_own["mangal_signal"]["A_cancel"] == "Марс в своём знаке (Овен/Скорпион)",
          "Дом 1: Марс в Овне → отмена по знаку (не по дом-знаку)")
    #   Марс в Близнецах в 1-м доме: нет знак-правила и нет строки дома 1 → доша активна
    rl_act = compat_jyotish(stub(0, 4, mars_house=1, mars_rashi=2), stub(1, 3), "мужской", "женский")
    check(rl_act["mangal_signal"]["A_present"] and rl_act["mangal_signal"]["A_cancel"] is None,
          "Дом 1: Марс в Близнецах → доша активна (для дома 1 знак-таблицы нет)")
    check(_bhakut_cancel(1, 3, "Сатурн", "Сатурн") == "общий управитель навамша-лагны",
          "Бхакут гасится навамша-управителем")
    check(_nadi_cancel(0, 6, 0, 2, 1, 1) == "исключённая пара накшатр",
          "Нади гасится исключённой парой накшатр (Ашвини-Пунарвасу)")

    # — Тип связи и роли (новое поведение) —
    # пара с НЕгасящейся двусмысленностью: плавает только Варна (Гана: Дева×Ракшаса=0 в обе стороны)
    rss = compat_jyotish(stub(0, 0), stub(2, 3), "мужской", "мужской")  # оба М → роль не определена
    check(rss["roles_defined"] is False, "Однополая пара: роль жениха/невеста НЕ определена")
    check("Варна" in rss["ambiguous_kutas"] and "–" in rss["total_display"],
          f"Однополая: итог диапазоном ({rss['total_display']}), Варна двусмысленна")
    check(any(k.get("status") == "роль условна" for k in rss["kutas"]),
          "Однополая: направленные куты помечены «роль условна»")
    # пара, где двусмысленности Варны(+1) и Ганы(−1) гасятся → итог устойчив, но куты помечены
    rcancel = compat_jyotish(stub(1, 0), stub(2, 3), "мужской", "мужской")
    check("–" not in rcancel["total_display"] and rcancel["ambiguous_kutas"],
          f"Однополая со взаимным гашением: итог устойчив ({rcancel['total_display']}), куты помечены")
    rhetero = compat_jyotish(stub(1, 0), stub(2, 3), "мужской", "женский")
    check(rhetero["roles_defined"] is True and "–" not in rhetero["total_display"],
          "Гетеро-романтика: роли определены, итог — одно число")
    check(_marriage_caveat("деловые") is not None and _marriage_caveat("романтика") is None,
          "Оговорка-брак: есть для деловых, нет для романтики")
    check(_normalize_rel("бизнес-партнёр") == "деловые" and _normalize_rel("любовь") == "романтика",
          "Нормализация типа связи (деловые/романтика)")

    # — Дайджест «легче/труднее» (детерминированная раскладка) —
    fake = {
        "bazi": {"criteria": [
            {"name": "Стволы", "score": 2, "max": 2, "detail": "союз"},                 # → легче
            {"name": "Ветви", "score": 0, "max": 2, "detail": "冲", "directional": True},  # → труднее+напр
        ]},
        "jyotish": {
            "kutas": [
                {"name": "Йони", "score": 4, "max": 4, "detail": "одно животное"},        # → легче
                {"name": "Нади", "score": 0, "max": 8, "detail": "одна нади"},            # доша
            ],
            "dosha_cancellations": {"nadi": None, "bhakut": None},
            "mangal_signal": {"A_present": False, "A_cancel": None,
                              "B_present": False, "B_cancel": None, "note_verdict": ""},
        },
        "human_design": {"electromagnetic": [{"name": "Альфа", "channel": "7-31", "who": "x"}],
                         "companionship": [], "compromise": [], "dominance": []},
    }
    ef = _ease_friction(fake)
    check(any(i["topic"] == "Стволы" for i in ef["ease"]) and
          any("близость" in i["topic"] for i in ef["ease"]), "Дайджест: высокие баллы → «легче»")
    check(any("потомство" in i["topic"] for i in ef["friction"]),
          "Дайджест: НЕпогашенная Нади-доша → «труднее»")
    check(any(i["topic"] == "Ветви" for i in ef["directional"]),
          "Дайджест: направленный критерий → «по-разному для A и B»")
    fake["jyotish"]["dosha_cancellations"]["nadi"] = "правило"
    check(not any("потомство" in i["topic"] for i in _ease_friction(fake)["friction"]),
          "Дайджест: ПОГАШЕННАЯ Нади-доша НЕ в «труднее»")

    # — ДОП. слои: состояние Марса (ретро/комбуст), сектор брака, наложение домов —
    def _mj(sun_lon, mars_lon, retro=False):
        return {"grahas": [{"graha": "Солнце (Сурья)", "lon": sun_lon},
                           {"graha": "Марс (Мангала)", "lon": mars_lon, "retrograde": retro}]}
    st = _mars_state(_mj(100.0, 110.0))
    check(bool(st) and st["combust"] and not st["retrograde"] and st["separation_deg"] == 10.0,
          "Марс сожжён: |110−100|=10° < 17° орб")
    check(_mars_state(_mj(0.0, 40.0)) is None, "Марс на 40° от Солнца, не ретро → None")
    stw = _mars_state(_mj(355.0, 5.0, retro=True))
    check(bool(stw) and stw["combust"] and stw["retrograde"] and stw["separation_deg"] == 10.0,
          "Марс: дуга через 0° (355↔5)=10° → сожжён + ретро")
    check(_mars_state(stub(0, 0)) is None,
          "Заглушка без Солнца/долгот → _mars_state None (движок не падает)")

    j7s = {"house_lords": [{"house": 7, "lord": "Венера"}],
           "grahas": [{"graha": "Венера (Шукра)", "house": 4, "dignity": "экзальтация"},
                      {"graha": "Юпитер (Гуру)", "house": 7, "dignity": "нейтрально"}]}
    check((_seventh_strength(j7s) or {}).get("label") == "крепкий",
          "Сектор брака КРЕПКИЙ (управитель экзальт.+угол, благой в 7-м)")
    j7w = {"house_lords": [{"house": 7, "lord": "Марс"}],
           "grahas": [{"graha": "Марс (Мангала)", "house": 12, "dignity": "падение"},
                      {"graha": "Сатурн (Шани)", "house": 7, "dignity": "нейтрально"}]}
    check((_seventh_strength(j7w) or {}).get("label") == "под нагрузкой",
          "Сектор брака ПОД НАГРУЗКОЙ (управитель падение+дустхана, вредитель в 7-м)")
    check(_seventh_strength(stub(0, 0)) is None,
          "Заглушка без house_lords → _seventh_strength None")

    ova = {"lagna": {"rashi": "Овен"},
           "grahas": [{"graha": "Венера (Шукра)", "rashi": "Весы"}]}
    ovb = {"lagna": {"rashi": "Рак"},
           "grahas": [{"graha": "Юпитер (Гуру)", "rashi": "Весы"}]}
    ov = _house_overlay(ova, ovb)
    check(("Венера", 4) in {(x["planet"], x["house"]) for x in ov["A_in_B"]},
          "Наложение: Венера A (Весы) → 4-й дом B (Лагна Рак)")
    check(("Юпитер", 7) in {(x["planet"], x["house"]) for x in ov["B_in_A"]},
          "Наложение: Юпитер B (Весы) → 7-й дом A (Лагна Овен)")
    ovs = _house_overlay(stub(0, 0), stub(0, 0))
    check(ovs["A_in_B"] == [] and ovs["B_in_A"] == [],
          "Заглушка без Лагны → наложение пусто (движок не падает)")

    print("\n" + ("ВСЕ ИНВАРИАНТЫ ОК" if ok else "ЕСТЬ ОШИБКИ"))
    print("✓ Йони(4), Гана(6), Вашья(2) сверены по Drik Panchang/AstroSage "
          "(Вашья — по 2 независимым источникам, направленная, схема {2/1.5/1/0}). "
          "Логика кут проверена юнит-тестами (эталонная пара = 31/36).")
    return ok


def main(argv):
    if "--selftest" in argv:
        sys.exit(0 if selftest() else 1)
    rel = next((a.split("=", 1)[1] for a in argv if a.startswith("--rel=")), "романтика")
    paths = [a for a in argv[1:] if not a.startswith("--")]
    if len(paths) != 6:
        print(__doc__, file=sys.stderr)       # подсказка — в stderr: stdout остаётся чистым для JSON-конверта
        print("\nНужно 6 путей: A_bazi A_jyotish A_hd B_bazi B_jyotish B_hd "
              "[--rel=романтика|деловые|дружба|семья]", file=sys.stderr)
        sys.exit(2)
    loaded = [json.load(open(p, encoding="utf-8")) for p in paths]
    result = compare(*loaded, rel_type=rel)
    if "--json" in argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result)


def _print_human(r):
    b, j, h = r["bazi"], r["jyotish"], r["human_design"]
    ef = r["ease_friction"]
    print("═" * 70)
    print("  СОВМЕСТИМОСТЬ — где легче, где труднее (НЕ единый процент)")
    print(f"  Тип связи: {r['meta']['relationship_type']}")
    print("═" * 70)
    if r["meta"].get("marriage_systems_note"):
        print(f"\n{r['meta']['marriage_systems_note']}")

    print("\n┌─ ГДЕ ЛЕГЧЕ ────────────────────────────────────────────────")
    for it in ef["ease"]:
        print(f"  + [{it['system']}] {it['topic']}: {it['detail']}")
    if not ef["ease"]:
        print("  (явных лёгких точек мало — это само по себе сигнал)")
    print("\n┌─ ГДЕ ТРУДНЕЕ ───────────────────────────────────────────────")
    for it in ef["friction"]:
        print(f"  − [{it['system']}] {it['topic']}: {it['detail']}")
    if not ef["friction"]:
        print("  (явных напряжений мало)")
    if ef["directional"]:
        print("\n┌─ ПО-РАЗНОМУ ДЛЯ A И B (несимметрично) ─────────────────────")
        for it in ef["directional"]:
            print(f"  ↔ [{it['system']}] {it['topic']}: {it['detail']}")
    print(f"\n  ⚠ {ef['note']}")

    print("\n" + "─" * 70)
    print("  ДЕТАЛИ ПО СИСТЕМАМ — числа ВТОРИЧНЫ и НЕ складываются (они о разном)")
    print("─" * 70)
    print(f"\n● Ба Цзы (合婚): {b['total']}/10 — {b['verdict']}")
    for c in b["criteria"]:
        d = " [направл.]" if c.get("directional") else ""
        print(f"    {c['name']:<28} {c['score']}/{c['max']}{d}  {c['detail']}")
    print(f"\n● Джйотиш (Аштакута): {j['total_display']}/36 — {j['verdict']}")
    if not j["roles_defined"]:
        print(f"    (роль жениха/невеста условна; направленные куты двусмысленны: "
              f"{', '.join(j['ambiguous_kutas']) or 'совпали в обе стороны'})")
    for k in j["kutas"]:
        st = f" ⚠{k['status']}" if k.get("status") else ""
        d = " [напр.]" if k.get("directional") else ""
        print(f"    {k['name']:<14} {k['score']}/{k['max']}{d}{st}  {k['detail']}")
    m = j["mangal_signal"]
    print(f"    Мангал: {m['note_verdict']}")
    for who in ("A", "B"):
        frag = j["time_fragility"].get(who)
        if frag:
            for f in frag:
                print(f"    ⏱ {who}: Луна в ~{f['minutes_approx']} мин от границы «{f['boundary']}» "
                      f"→ при неточном времени плывут: {', '.join(f['kutas_at_risk'])} (прибл.)")
    print(f"\n● Дизайн Человека (карта связей) — качественно:")
    c = h["counts"]
    print(f"    электромагнетика {c['electromagnetic']} · товарищество {c['companionship']}"
          f" · компромисс {c['compromise']} · доминирование {c['dominance']}")
    print(f"    {h['type_note']}")
    print(f"\n  ⚠ {r['meta']['framing']}")


if __name__ == "__main__":
    import cli_errors
    cli_errors.run(lambda: main(sys.argv), entry=main)
