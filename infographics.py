#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""Инфографика для профилей — Tier-1 proof (Ба Цзы).

ПРИНЦИП: SVG строится КОДОМ из JSON калькулятора, агент его НЕ рисует руками.
Числа = [факт] из bazi.json; график лишь отображает их, не пересчитывает.
Чистый inline-SVG, без JS и внешних зависимостей — рендерится в PDF через
headless Chrome так же, как текст. Вставляется в .md внутри ```svg ... ``` —
md2html.py пропускает такой блок без экранирования.

Графики Ба Цзы (5): four_pillars (натальная карта), five_elements (баланс + 用神/忌神 overlay),
strength_gauge (сила ХД), ten_gods (十神 по 5 ролям), luck_timeline (大运, лента десятилетий).
ВАЖНО: иероглифы в SVG НЕ рисуем — только в HTML-подписях рядом (см. примечание у _esc).

CLI:
  python3 infographics.py bazi.json            → печатает оба ```svg блока
  python3 infographics.py bazi.json --demo-md   → готовый демо-.md (с подписями)
  python3 infographics.py --test                → golden-самопроверка
"""
import sys, json, math, re

# Традиционные цвета 五行 (различимы и в ч/б: насыщенность/светлота разная)
EL_ORDER = ["Дерево", "Огонь", "Земля", "Металл", "Вода"]
EL_COLOR = {"Дерево": "#4a9d4a", "Огонь": "#d6483b", "Земля": "#c79a3a",
            "Металл": "#8d95a1", "Вода": "#3f6fae",
            "Железо (Металл)": "#8d95a1", "Железо": "#8d95a1"}
EL_TINT = {"Дерево": "#e6f3e6", "Огонь": "#fbe4e1", "Земля": "#f6edd4",
           "Металл": "#eaecef", "Вода": "#e1ebf6"}    # светлые фоны ячеек (тёмный текст поверх читается)

# ИЕРОГЛИФЫ В SVG НЕ РИСУЕМ: headless Chrome рендерит CJK в SVG-тексте нестабильно
# (одиночные/смешанные раны выпадают в пустоту, см. историю отладки). Все китайские
# термины идут в HTML-подписи/заголовки рядом с графиком, где CJK надёжен через CSS-стек.
# Константы ниже — легаси, не используются (оставлены, чтобы не трогать CJK-диапазон в regex).
_CJK_RE = re.compile(r"([㐀-鿿豈-﫿]+)")
_CJK_FONT = "'PingFang SC','Hiragino Sans GB','Songti SC',sans-serif"


def _esc(t):
    """Escape текста для SVG. Иероглифов тут быть не должно — все китайские термины идут
    в HTML-подписи рядом с графиком (headless Chrome рендерит CJK в SVG нестабильно)."""
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def five_elements_svg(d):
    """Бары по 5 стихиям; ◆ = стихия Хозяина Дня; справа 用神(нужна)/忌神(избегать); пунктир — «ровно» 20%.
    CJK (五行/用神/忌神) в SVG не кладём рядом с кириллицей (баг рендера) — термины идут в HTML-подпись."""
    eb = d["element_balance"]
    dm_el = d["day_master"]["element"]
    yong = {x["element"] for x in d.get("yongshen", [])}    # 用神 — что усилить
    ji = {x["element"] for x in d.get("jishen", [])}         # 忌神 — что убавить
    mx = max(v["percent"] for v in eb.values())
    axis = max(50.0, math.ceil(mx / 10.0) * 10.0)            # шкала 0..axis%
    W, left, barmax, top, rowh = 720, 118, 430, 58, 34
    n = len(EL_ORDER)
    H = top + n * rowh + 10
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Баланс пяти стихий">']
    p.append(f'<text x="{left-110}" y="26" font-size="15" font-weight="700" fill="#1a1a1a">Баланс пяти стихий</text>')
    p.append(f'<text x="{left-110}" y="44" font-size="10.5" fill="#666">'
             f'% — вес · пунктир = «ровно» 20% · ◆ Хозяин Дня · справа: что усилить / убрать</text>')
    evenx = left + barmax * (20.0 / axis)
    p.append(f'<line x1="{evenx:.1f}" y1="{top-4}" x2="{evenx:.1f}" y2="{top+n*rowh-10}" '
             f'stroke="#bbb" stroke-width="1" stroke-dasharray="3 3"/>')
    for k, el in enumerate(EL_ORDER):
        v = eb[el]; pct = v["percent"]; y = top + k * rowh
        bw = barmax * (pct / axis)
        is_dm = (el == dm_el)
        lbl = el + (" ◆" if is_dm else "")
        p.append(f'<text x="{left-10}" y="{y+15}" font-size="11.5" text-anchor="end" '
                 f'fill="#1a1a1a" font-weight="{700 if is_dm else 400}">{_esc(lbl)}</text>')
        p.append(f'<rect x="{left}" y="{y+3}" width="{barmax}" height="17" rx="3" fill="#f0f0f0"/>')
        p.append(f'<rect x="{left}" y="{y+3}" width="{bw:.1f}" height="17" rx="3" fill="{EL_COLOR[el]}"/>')
        p.append(f'<text x="{left+bw+7:.1f}" y="{y+16}" font-size="11" fill="#333">{pct:.1f}%</text>')
        tag = ("#2e7d32", "нужна") if el in yong else ("#c62828", "избегать") if el in ji else None
        if tag:
            p.append(f'<circle cx="{left+barmax+34}" cy="{y+11}" r="4" fill="{tag[0]}"/>')
            p.append(f'<text x="{left+barmax+44}" y="{y+15}" font-size="10.5" fill="{tag[0]}">{tag[1]}</text>')
    p.append('</svg>')
    return "\n".join(p)


def _current_pillar_index(lp, cur_age):
    # окно столпа — [age_start, age_start+10); age_end в JSON с issue #8 равен age_start+10 (до того +9 → «дыра» раз в 10 лет)
    for idx, pil in enumerate(lp):
        if pil["age_start"] <= cur_age < pil["age_start"] + 10:
            return idx
    return None


def _current_age(d):
    """Точный возраст на дату as-of (из dynamic_interactions.age_exact, bazi.py ≥ 2026-11-09); иначе целый по годам."""
    dyn = d.get("dynamic_interactions") or {}
    if isinstance(dyn.get("age_exact"), (int, float)):
        return dyn["age_exact"]
    return d["current_year"]["year"] - int(d["input"]["date"][:4])


def luck_timeline_svg(d):
    """Лента десятилетних столпов 大运; верхняя полоска = стихия столпа, ▲ = где ты сейчас."""
    lp = d["luck_pillars"]["pillars"]
    cur_year = d["current_year"]["year"]
    cur_age = _current_age(d)
    cur_idx = _current_pillar_index(lp, cur_age)
    n = len(lp)
    cw, pad, ctop, ch = 96, 30, 64, 96     # ширина ячейки, отступ, верх ленты, высота ячейки
    W = pad * 2 + n * cw
    H = ctop + ch + 16
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" '
         f'aria-label="Большие Удачи">']
    p.append(f'<text x="{pad}" y="24" font-size="15" font-weight="700" fill="#1a1a1a">'
             f'Большие Удачи — десятилетия</text>')
    p.append(f'<text x="{pad}" y="42" font-size="10.5" fill="#666">'
             f'полоска сверху = стихия столпа · ▲ ты сейчас</text>')
    for idx, pil in enumerate(lp):
        x = pad + idx * cw
        cx = x + cw / 2
        st_el = pil["stem"]["element"]; br_el = pil["branch"]["element"]
        cur = (idx == cur_idx)
        # фон ячейки + рамка (текущая — жирная тёмная)
        p.append(f'<rect x="{x}" y="{ctop}" width="{cw-4}" height="{ch}" rx="4" '
                 f'fill="{"#fcfbf6" if cur else "#ffffff"}" '
                 f'stroke="{"#1a1a1a" if cur else "#d2d2d2"}" '
                 f'stroke-width="{2.4 if cur else 1}"/>')
        # верхняя полоска — стихия столпа (стебель)
        p.append(f'<rect x="{x}" y="{ctop}" width="{cw-4}" height="7" rx="3" fill="{EL_COLOR[st_el]}"/>')
        age = f'{round(pil["age_start"])}–{round(pil["age_end"])}'
        p.append(f'<text x="{cx:.1f}" y="{ctop+22}" font-size="9.5" text-anchor="middle" fill="#666">{age} лет</text>')
        # стихии столпа крупно, своими цветами: ствол над ветвью (干支 — в подписи под графиком)
        p.append(f'<text x="{cx:.1f}" y="{ctop+45}" font-size="13" text-anchor="middle" '
                 f'font-weight="700" fill="{EL_COLOR[st_el]}">{_esc(st_el)}</text>')
        p.append(f'<text x="{cx:.1f}" y="{ctop+61}" font-size="11.5" text-anchor="middle" '
                 f'font-weight="700" fill="{EL_COLOR[br_el]}">{_esc(br_el)}</text>')
        tg = pil["ten_god_ru"].split(" ", 1)
        p.append(f'<text x="{cx:.1f}" y="{ctop+78}" font-size="8.2" text-anchor="middle" fill="#777">{_esc(tg[0])}</text>')
        if len(tg) > 1:
            p.append(f'<text x="{cx:.1f}" y="{ctop+88}" font-size="8.2" text-anchor="middle" fill="#777">{_esc(tg[1])}</text>')
        if cur:
            p.append(f'<text x="{cx:.1f}" y="{ctop-6}" font-size="11" text-anchor="middle" '
                     f'fill="#1a1a1a" font-weight="700">▲ {cur_year} (~{int(cur_age)})</text>')
    p.append('</svg>')
    return "\n".join(p)


# ── Четыре Столпа: порядок и подписи как в проекте (Час·День·Месяц·Год) ──
PILLAR_ORDER = ["hour", "day", "month", "year"]
PILLAR_RU = {"hour": ("Час", "时"), "day": ("День", "日"),
             "month": ("Месяц", "月"), "year": ("Год", "年")}
POL_RU = {"yang": "ян", "yin": "инь"}


def _cell(x, y, w, h, el, big, small):
    """Ячейка ствола/ветви: цветной фон по стихии, крупная подпись (стихия/животное) + мелкая.
    Без иероглифов — 干支 столпов показаны в HTML-подписи под графиком."""
    cx = x + w / 2
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="{EL_TINT[el]}" '
            f'stroke="{EL_COLOR[el]}" stroke-width="1.2"/>'
            f'<rect x="{x}" y="{y}" width="{w}" height="6" rx="3" fill="{EL_COLOR[el]}"/>'
            f'<text x="{cx:.1f}" y="{y+32}" font-size="15" text-anchor="middle" font-weight="700" '
            f'fill="#1a1a1a">{_esc(big)}</text>'
            f'<text x="{cx:.1f}" y="{y+h-7}" font-size="10" text-anchor="middle" fill="#555">{_esc(small)}</text>')


def four_pillars_svg(d):
    """Натальная карта — 4 столпа. Столп Дня = Хозяин Дня (это «ты»), столбец обведён."""
    P = d["pillars"]
    cw, pad, top, H = 152, 14, 8, 286
    st_y, br_y, ch, hid_y = 64, 126, 54, 192
    W = pad * 2 + len(PILLAR_ORDER) * cw
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Четыре столпа">']
    for ci, key in enumerate(PILLAR_ORDER):
        pil = P[key]; x = pad + ci * cw; cx = x + cw / 2
        is_day = (key == "day"); ru = PILLAR_RU[key][0]
        if is_day:
            p.append(f'<rect x="{x+2}" y="{top}" width="{cw-8}" height="{H-top-8}" rx="7" '
                     f'fill="#fcfbf6" stroke="#1a1a1a" stroke-width="2"/>')
        p.append(f'<text x="{cx:.1f}" y="{top+18}" font-size="12.5" text-anchor="middle" '
                 f'font-weight="700" fill="#1a1a1a">{ru}</text>')
        tg = "Хозяин Дня" if is_day else pil["ten_god_ru"]
        p.append(f'<text x="{cx:.1f}" y="{top+38}" font-size="9" text-anchor="middle" '
                 f'fill="{"#1a1a1a" if is_day else "#777"}" font-weight="{700 if is_day else 400}">{_esc(tg)}</text>')
        s = pil["stem"]                                          # ствол: стихия + полярность
        p.append(_cell(x+10, st_y, cw-20, ch, s["element"], s["element"], POL_RU.get(s["polarity"], "")))
        b = pil["branch"]                                        # ветвь: животное + стихия
        p.append(_cell(x+10, br_y, cw-20, ch, b["element"], b["animal"], b["element"]))
        p.append(f'<text x="{x+12}" y="{hid_y}" font-size="8.5" fill="#999">скрытые:</text>')
        for hi, h in enumerate(b["hidden_stems"][:3]):
            hy = hid_y + 14 + hi * 15
            p.append(f'<rect x="{x+12}" y="{hy-8}" width="9" height="9" rx="2" fill="{EL_COLOR[h["element"]]}"/>')
            p.append(f'<text x="{x+25}" y="{hy}" font-size="8.6" fill="#555">{_esc(h["ten_god_ru"])}</text>')
    p.append('</svg>')
    return "\n".join(p)


def strength_gauge_svg(d):
    """Шкала силы Хозяина Дня. Цвета НЕЙТРАЛЬНЫ: сильный ≠ хорошо (это «много себя»)."""
    s = d["strength"]; score = s["score"]; label = s["label"]; supp = s.get("support_share")
    dm_el = d["day_master"]["element"]
    lo, hi = -20, 80
    W, H, left, barw, gy = 660, 112, 30, 600, 44
    xp = lambda v: left + barw * ((max(lo, min(hi, v)) - lo) / (hi - lo))
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Сила Хозяина Дня">']
    p.append(f'<text x="{left}" y="20" font-size="15" font-weight="700" fill="#1a1a1a">Сила Хозяина Дня</text>')
    p.append(f'<text x="{left}" y="37" font-size="10.5" fill="#666">'
             f'сильный ≠ «хорошо»: это «много себя» — карту разряжают, а не питают</text>')
    for a, b, name in [(-20, 0, "СЛАБЫЙ"), (0, 40, "СРЕДНИЙ"), (40, 80, "СИЛЬНЫЙ")]:
        x0, x1 = xp(a), xp(b); active = (name == label)
        p.append(f'<rect x="{x0:.1f}" y="{gy}" width="{x1-x0:.1f}" height="20" '
                 f'fill="{EL_COLOR[dm_el] if active else "#e6e6e6"}" stroke="#fff" stroke-width="1.5"/>')
        p.append(f'<text x="{(x0+x1)/2:.1f}" y="{gy+34}" font-size="9.5" text-anchor="middle" '
                 f'fill="{"#1a1a1a" if active else "#999"}" font-weight="{700 if active else 400}">{name}</text>')
    px = xp(score)
    p.append(f'<path d="M{px:.1f},{gy-3} l-5,-9 l10,0 z" fill="#1a1a1a"/>')
    p.append(f'<text x="{px:.1f}" y="{gy-16}" font-size="11" text-anchor="middle" font-weight="700" fill="#1a1a1a">{score}</text>')
    if supp is not None:
        p.append(f'<text x="{left}" y="{gy+58}" font-size="9.5" fill="#888">доля поддержки (своё + ресурс): {round(supp*100)}%</text>')
    p.append('</svg>')
    return "\n".join(p)


# Десятибог → роль (по китайскому имени); сдвиг = от стихии ХД к стихии роли (mod 5).
TG_ROLE = {"比肩": "companion", "劫财": "companion", "正印": "resource", "偏印": "resource",
           "食神": "output", "伤官": "output", "正财": "wealth", "偏财": "wealth",
           "正官": "power", "七杀": "power"}
ROLE_SEQ = [("resource", "Ресурс", "印", 4), ("companion", "Соратники", "比劫", 0),
            ("output", "Самовыражение", "食伤", 1), ("wealth", "Богатство", "财", 2),
            ("power", "Власть", "官杀", 3)]


def ten_gods_svg(d):
    """Десять Богов, сведённые в 5 ролей; длина = вес роли, цвет = её стихия для этого ХД."""
    dm_i = d["day_master"]["element_index"]
    sums = {}
    for g in d["ten_gods"]:
        role = TG_ROLE.get(g["name"])
        if role:
            sums[role] = sums.get(role, 0) + g["weight"]
    mx = max(sums.values()) if sums else 1.0
    W, left, barmax, top, rowh = 660, 150, 420, 54, 36
    H = top + len(ROLE_SEQ) * rowh + 8
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Десять богов">']
    p.append(f'<text x="10" y="22" font-size="15" font-weight="700" fill="#1a1a1a">Десять Богов — по ролям</text>')
    p.append(f'<text x="10" y="40" font-size="10.5" fill="#666">вес роли в карте · цвет = стихия роли для твоего ХД</text>')
    for k, (role, ru, cjk, shift) in enumerate(ROLE_SEQ):
        val = sums.get(role, 0); y = top + k * rowh
        el = EL_ORDER[(dm_i + shift) % 5]
        bw = barmax * (val / mx) if mx else 0
        p.append(f'<text x="{left-12}" y="{y+15}" font-size="11" text-anchor="end" fill="#1a1a1a" font-weight="700">{ru}</text>')
        p.append(f'<rect x="{left}" y="{y+2}" width="{barmax}" height="18" rx="3" fill="#f0f0f0"/>')
        p.append(f'<rect x="{left}" y="{y+2}" width="{bw:.1f}" height="18" rx="3" fill="{EL_COLOR[el]}"/>')
        p.append(f'<text x="{left+bw+7:.1f}" y="{y+15}" font-size="10.5" fill="#333">{val:g} · {el}</text>')
    p.append('</svg>')
    return "\n".join(p)


def _branch_node(x, y, w, h, el, animal):
    """Маленькая карточка ветви: животное + стихия, цвет по стихии (для графов связей/звёзд)."""
    cx = x + w / 2
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="{EL_TINT[el]}" '
            f'stroke="{EL_COLOR[el]}" stroke-width="1.2"/>'
            f'<rect x="{x}" y="{y}" width="{w}" height="5" rx="2" fill="{EL_COLOR[el]}"/>'
            f'<text x="{cx:.1f}" y="{y+22}" font-size="12.5" text-anchor="middle" font-weight="700" fill="#1a1a1a">{_esc(animal)}</text>'
            f'<text x="{cx:.1f}" y="{y+35}" font-size="8.5" text-anchor="middle" fill="#666">{_esc(el)}</text>')


def annual_year_svg(d):
    """Годовой столп (流年): стихии и роль текущего года + есть ли удар (冲) по какой-либо ветви карты."""
    cy = d["current_year"]; yr = cy["year"]
    se = cy["stem"]["element"]; be = cy["branch"]["element"]; an = cy["branch"]["animal"]
    tg = cy["ten_god_ru"]; clash = cy.get("clashes_natal")
    yong = {x["element"] for x in d.get("yongshen", [])}
    ji = {x["element"] for x in d.get("jishen", [])}
    W, H = 660, 170
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Годовой столп">']
    p.append(f'<text x="18" y="22" font-size="15" font-weight="700" fill="#1a1a1a">Год {yr} — что приносит</text>')
    p.append(f'<text x="18" y="40" font-size="10.5" fill="#666">годовой столп и его связь с твоей картой</text>')
    cardx, cardw, cy0, ch2 = 18, 150, 52, 52
    p.append(_cell(cardx, cy0, cardw, ch2, se, se, "ствол года"))
    p.append(_cell(cardx, cy0 + ch2 + 6, cardw, ch2, be, an, be))
    tx = cardx + cardw + 30
    p.append(f'<text x="{tx}" y="{cy0+14}" font-size="11.5" fill="#1a1a1a">Роль года: '
             f'<tspan font-weight="700">{_esc(tg)}</tspan></text>')
    relabel = "полезна тебе" if se in yong else "во вред" if se in ji else "нейтральна (не лечит и не усиливает)"
    relcol = "#2e7d32" if se in yong else "#c62828" if se in ji else "#777"
    p.append(f'<text x="{tx}" y="{cy0+38}" font-size="11" fill="{relcol}">Стихия года — {_esc(se)}: {relabel}</text>')
    if clash:
        p.append(f'<text x="{tx}" y="{cy0+64}" font-size="11.5" font-weight="700" fill="#c62828">'
                 f'⚡ Год бьёт по одной из ветвей карты — год на прочность</text>')
    else:
        p.append(f'<text x="{tx}" y="{cy0+64}" font-size="11" fill="#555">Удара года по ветвям карты нет</text>')
    p.append('</svg>')
    return "\n".join(p)


# первый символ строки взаимодействия → (русское имя, цвет)
INTER_TYPE = {"冲": ("Удар", "#d6483b"), "刑": ("Наказание", "#e08a2b"), "合": ("Союз", "#4a9d4a"),
              "害": ("Вред", "#8e5bb5"), "破": ("Разрушение", "#a0703a"), "三": ("Тройной союз", "#3a8a5a")}


def interactions_svg(d):
    """Граф взаимодействий ветвей (冲合刑害): дуги между столпами, подписанные типом связи."""
    order = ["hour", "day", "month", "year"]; ruP = {"hour": "Час", "day": "День", "month": "Месяц", "year": "Год"}
    P = d["pillars"]
    parsed = []
    for s in d.get("interactions", []):
        s = s.strip()
        if not s:
            continue
        m = re.search(r"\(([^)]+)\)", s)
        if not m:
            continue
        ps = [x.strip() for x in m.group(1).split("-")]
        parsed.append((s[0], ps))
    n, cw, pad, nodew = len(order), 150, 18, 120
    nodey, nodeh = 130, 42
    W, H = pad * 2 + n * cw, nodey + nodeh + 26
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Взаимодействия ветвей">']
    p.append(f'<text x="{pad}" y="22" font-size="15" font-weight="700" fill="#1a1a1a">Взаимодействия ветвей</text>')
    p.append(f'<text x="{pad}" y="40" font-size="10.5" fill="#666">союз / удар / наказание / вред между ветвями · сигнал, не вердикт</text>')
    xc = {}
    for i, key in enumerate(order):
        x = pad + i * cw + (cw - nodew) / 2
        b = P[key]["branch"]
        p.append(_branch_node(x, nodey, nodew, nodeh, b["element"], b["animal"]))
        p.append(f'<text x="{pad + i*cw + cw/2:.1f}" y="{nodey+nodeh+14}" font-size="8.5" '
                 f'text-anchor="middle" fill="#999">{ruP[key]}</text>')
        xc[ruP[key]] = pad + i * cw + cw / 2
    if not parsed:
        p.append(f'<text x="{W/2:.1f}" y="{nodey-30}" font-size="11" text-anchor="middle" fill="#888">'
                 f'крупных взаимодействий между ветвями нет</text>')
    for k, (t, ps) in enumerate(parsed[:3]):
        lab, col = INTER_TYPE.get(t, ("связь", "#777"))
        if len(ps) >= 2 and ps[0] in xc and ps[-1] in xc and xc[ps[0]] != xc[ps[-1]]:
            x1, x2 = xc[ps[0]], xc[ps[-1]]; mx = (x1 + x2) / 2
            cyc = nodey - 44 - k * 30; ly = (nodey + cyc) / 2
            p.append(f'<path d="M{x1:.1f},{nodey} Q{mx:.1f},{cyc:.1f} {x2:.1f},{nodey}" fill="none" stroke="{col}" stroke-width="2"/>')
            p.append(f'<rect x="{mx-36:.1f}" y="{ly-9:.1f}" width="72" height="16" rx="8" fill="#fff" stroke="{col}"/>')
            p.append(f'<text x="{mx:.1f}" y="{ly+3:.1f}" font-size="9.5" text-anchor="middle" fill="{col}" font-weight="700">{lab}</text>')
    p.append('</svg>')
    return "\n".join(p)


# короткие подписи для длинных имён звёзд (чтобы влезали в бейдж)
SHEN_SHORT = {"Странствующий Конь": "Конь (путь)", "Балдахин": "Балдахин"}


def shensha_svg(d):
    """Особые звёзды (神煞), звёзды любви (天喜/红鸾) и пустота (空亡) по ветвям карты."""
    order = ["hour", "day", "month", "year"]; ruP = {"hour": "Час", "day": "День", "month": "Месяц", "year": "Год"}
    P = d["pillars"]
    void = {b["name"] for b in d.get("kong_wang_active", [])}
    shen = {}
    for s in d.get("shensha", []):
        shen.setdefault(s["branch"], []).append(SHEN_SHORT.get(s["name_ru"], s["name_ru"]))
    romance = {}
    for star, lab in ((d.get("hongluan"), "Любовь"), (d.get("tianxi"), "Радость")):
        if star:
            romance.setdefault(star["name"], []).append(lab)
    n, cw, pad, nodew = len(order), 150, 18, 120
    nodey, nodeh = 46, 42
    W, H = pad * 2 + n * cw, nodey + nodeh + 76
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Особые звёзды">']
    p.append(f'<text x="{pad}" y="22" font-size="15" font-weight="700" fill="#1a1a1a">Особые звёзды и пустота</text>')
    p.append(f'<text x="{pad}" y="40" font-size="10.5" fill="#666">приметы по ветвям · «пусто» = пустая ветвь (значения — в подписи)</text>')
    for i, key in enumerate(order):
        x = pad + i * cw + (cw - nodew) / 2; cx = pad + i * cw + cw / 2
        b = P[key]["branch"]; bn = b["name"]
        p.append(_branch_node(x, nodey, nodew, nodeh, b["element"], b["animal"]))
        p.append(f'<text x="{cx:.1f}" y="{nodey+nodeh+13}" font-size="8.5" text-anchor="middle" fill="#999">{ruP[key]}</text>')
        badges = [(s, "#5a5a8a") for s in shen.get(bn, [])]
        badges += [(r, "#b5487a") for r in romance.get(bn, [])]
        if bn in void:
            badges.append(("пусто", "#999"))
        for bi, (txt, col) in enumerate(badges[:3]):
            yy = nodey + nodeh + 26 + bi * 15
            p.append(f'<rect x="{cx-48:.1f}" y="{yy-9}" width="96" height="13" rx="6" fill="#fff" stroke="{col}"/>')
            p.append(f'<text x="{cx:.1f}" y="{yy}" font-size="7.8" text-anchor="middle" fill="{col}">{_esc(txt)}</text>')
        if not badges:
            p.append(f'<text x="{cx:.1f}" y="{nodey+nodeh+30}" font-size="9" text-anchor="middle" fill="#bbb">—</text>')
    p.append('</svg>')
    return "\n".join(p)


def _arrow(src, tgt, rs, rt, color, dashed=False, width=2):
    """Стрелка от края узла src к краю узла tgt (с наконечником)."""
    x1, y1 = src; x2, y2 = tgt
    dx, dy = x2 - x1, y2 - y1; L = math.hypot(dx, dy) or 1
    ux, uy = dx / L, dy / L
    sx, sy = x1 + ux * rs, y1 + uy * rs
    ex, ey = x2 - ux * (rt + 7), y2 - uy * (rt + 7)
    dash = ' stroke-dasharray="4 3"' if dashed else ''
    px, py, s = -uy, ux, 5
    return (f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="{color}" stroke-width="{width}"{dash}/>'
            f'<path d="M{ex:.1f},{ey:.1f} L{ex-ux*9+px*s:.1f},{ey-uy*9+py*s:.1f} '
            f'L{ex-ux*9-px*s:.1f},{ey-uy*9-py*s:.1f} z" fill="{color}"/>')


def wuxing_cycle_svg(d):
    """Колесо 五行: узлы-стихии (размер ∝ вес) + стрелки 生 (кормит, по кругу) и 克 (держит, крест-накрест).
    EL_ORDER = Дерево·Огонь·Земля·Металл·Вода — это и есть порядок порождения, поэтому i→i+1 = 生, i→i+2 = 克."""
    eb = d["element_balance"]; dm_el = d["day_master"]["element"]
    yong = {x["element"] for x in d.get("yongshen", [])}
    ji = {x["element"] for x in d.get("jishen", [])}
    W, H, cx, cy, R = 470, 402, 235, 230, 128
    pmax = max(v["percent"] for v in eb.values()) or 1
    pos, rad = {}, {}
    for i, el in enumerate(EL_ORDER):
        a = math.radians(-90 + i * 72)
        pos[el] = (cx + R * math.cos(a), cy + R * math.sin(a))
        rad[el] = 18 + 22 * (eb[el]["percent"] / pmax) ** 0.5
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Колесо пяти стихий">']
    p.append(f'<text x="14" y="22" font-size="15" font-weight="700" fill="#1a1a1a">Пять стихий: кто кого кормит и держит</text>')
    p.append(f'<text x="14" y="40" font-size="10.5" fill="#666">сплошные → «кормит» · пунктир ⇢ «держит» · размер = вес стихии</text>')
    p.append(f'<text x="14" y="56" font-size="10.5" fill="#666">обводка: зелёная — усилить · красная — убрать · чёрная — Хозяин Дня</text>')
    for i, el in enumerate(EL_ORDER):                       # 克 (контроль) — пунктир, под узлами
        t = EL_ORDER[(i + 2) % 5]
        p.append(_arrow(pos[el], pos[t], rad[el], rad[t], "#d3a0a0", dashed=True, width=1.6))
    for i, el in enumerate(EL_ORDER):                       # 生 (порождение) — сплошные, по кругу
        t = EL_ORDER[(i + 1) % 5]
        p.append(_arrow(pos[el], pos[t], rad[el], rad[t], "#8ab48a", dashed=False, width=2.2))
    for el in EL_ORDER:                                     # узлы поверх
        x, y = pos[el]; r = rad[el]
        p.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{EL_COLOR[el]}" stroke="#fff" stroke-width="2"/>')
        if el in yong:
            p.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r+3.5:.1f}" fill="none" stroke="#2e7d32" stroke-width="2.5"/>')
        elif el in ji:
            p.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r+3.5:.1f}" fill="none" stroke="#c62828" stroke-width="2.5"/>')
        if el == dm_el:
            p.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r+7:.1f}" fill="none" stroke="#1a1a1a" stroke-width="2"/>')
        p.append(f'<text x="{x:.1f}" y="{y-1:.1f}" font-size="10.5" text-anchor="middle" fill="#fff" font-weight="700">{_esc(el)}</text>')
        p.append(f'<text x="{x:.1f}" y="{y+12:.1f}" font-size="9.5" text-anchor="middle" fill="#fff">{eb[el]["percent"]:.0f}%</text>')
    p.append('</svg>')
    return "\n".join(p)


# ветвь месяца → сезон рождения (для 调候)
SEASON = {"寅": "ранняя весна", "卯": "весна", "辰": "поздняя весна",
          "巳": "раннее лето", "午": "лето", "未": "позднее лето",
          "申": "ранняя осень", "酉": "осень", "戌": "поздняя осень",
          "亥": "ранняя зима", "子": "зима", "丑": "поздняя зима"}


def tiaohou_svg(d):
    """Климатическая настройка 调候: какие стихии карту согревают/растят (по сезону) + совпадение с 用神."""
    th = d.get("tiaohou")
    W, H = 660, 150
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Климат карты">']
    p.append(f'<text x="18" y="22" font-size="15" font-weight="700" fill="#1a1a1a">Климат карты</text>')
    p.append(f'<text x="18" y="40" font-size="10.5" fill="#666">что карту согревает и растит (по сезону) · вспомогательный слой</text>')
    if not th:
        p.append(f'<text x="{W/2:.1f}" y="90" font-size="11" text-anchor="middle" fill="#888">данных по климату нет</text>')
        p.append('</svg>'); return "\n".join(p)
    pe = th["primary"]["element"]; ae = th["auxiliary"]["element"]
    aligns = th.get("aligns_with_yongshen")
    season = SEASON.get(d["pillars"]["month"]["branch"]["name"], "—")
    p.append(f'<text x="18" y="66" font-size="11.5" fill="#1a1a1a">Сезон рождения: <tspan font-weight="700">{_esc(season)}</tspan></text>')

    def chip(x, el, role):
        return (f'<rect x="{x}" y="80" width="150" height="46" rx="6" fill="{EL_TINT[el]}" stroke="{EL_COLOR[el]}" stroke-width="1.2"/>'
                f'<rect x="{x}" y="80" width="150" height="6" rx="3" fill="{EL_COLOR[el]}"/>'
                f'<text x="{x+75}" y="104" font-size="14" text-anchor="middle" font-weight="700" fill="#1a1a1a">{_esc(el)}</text>'
                f'<text x="{x+75}" y="119" font-size="9" text-anchor="middle" fill="#666">{role}</text>')
    p.append(chip(18, pe, "главный"))
    p.append(chip(180, ae, "вспомогательный"))
    tx = 350
    if aligns:
        p.append(f'<text x="{tx}" y="100" font-size="11.5" font-weight="700" fill="#2e7d32">✓ совпадает с тем, что</text>')
        p.append(f'<text x="{tx}" y="116" font-size="11.5" font-weight="700" fill="#2e7d32">и так полезно</text>')
    else:
        p.append(f'<text x="{tx}" y="100" font-size="11.5" font-weight="700" fill="#e08a2b">климат и сила тянут</text>')
        p.append(f'<text x="{tx}" y="116" font-size="11.5" font-weight="700" fill="#e08a2b">в разные стороны</text>')
    p.append('</svg>')
    return "\n".join(p)


def nayin_svg(d):
    """纳音 — «звучащая» (мелодическая) стихия каждого столпа (третий слой; названия — в подписи)."""
    order = ["hour", "day", "month", "year"]; ruP = {"hour": "Час", "day": "День", "month": "Месяц", "year": "Год"}
    P = d["pillars"]
    n, cw, pad, chw = 4, 150, 18, 120
    cy0, chh = 56, 50
    W, H = pad * 2 + n * cw, cy0 + chh + 16
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Звучащая стихия столпов">']
    p.append(f'<text x="{pad}" y="22" font-size="15" font-weight="700" fill="#1a1a1a">Звучащая стихия столпов</text>')
    p.append(f'<text x="{pad}" y="40" font-size="10.5" fill="#666">«мелодический» третий элемент столпа (поэтические названия — в подписи)</text>')
    for i, key in enumerate(order):
        x = pad + i * cw + (cw - chw) / 2; cx = x + chw / 2
        el = P[key].get("nayin_element") or "—"
        col = EL_COLOR.get(el, "#cccccc"); tint = EL_TINT.get(el, "#eeeeee")
        p.append(f'<text x="{cx:.1f}" y="{cy0-6}" font-size="9.5" text-anchor="middle" fill="#999">{ruP[key]}</text>')
        p.append(f'<rect x="{x}" y="{cy0}" width="{chw}" height="{chh}" rx="6" fill="{tint}" stroke="{col}" stroke-width="1.2"/>')
        p.append(f'<rect x="{x}" y="{cy0}" width="{chw}" height="6" rx="3" fill="{col}"/>')
        p.append(f'<text x="{cx:.1f}" y="{cy0+33}" font-size="15" text-anchor="middle" font-weight="700" fill="#1a1a1a">{_esc(el)}</text>')
    p.append('</svg>')
    return "\n".join(p)


SEV_COLOR = {"high": "#c62828", "medium": "#e08a2b", "info": "#8d95a1"}
SEV_RU = {"high": "очень чувствителен", "medium": "чувствителен", "info": "инфо"}
SEV_RANK = {"high": 3, "medium": 2, "info": 1}


def fragility_svg(d):
    """Насколько столпы чувствительны к точности времени рождения (boundary_warnings)."""
    order = ["hour", "day", "month", "year"]; ruP = {"hour": "Час", "day": "День", "month": "Месяц", "year": "Год"}
    worst = {}
    for w in d.get("boundary_warnings", []):
        k = w["pillar"]
        if SEV_RANK.get(w["severity"], 0) > SEV_RANK.get(worst.get(k, ""), 0):
            worst[k] = w["severity"]
    n, cw, pad, chw = 4, 150, 18, 120
    cy0, chh = 56, 46
    W, H = pad * 2 + n * cw, cy0 + chh + 16
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Хрупкость к времени">']
    p.append(f'<text x="{pad}" y="22" font-size="15" font-weight="700" fill="#1a1a1a">Чувствительность к точности времени</text>')
    p.append(f'<text x="{pad}" y="40" font-size="10.5" fill="#666">какие столпы «поплывут», если время рождения неточно</text>')
    for i, key in enumerate(order):
        x = pad + i * cw + (cw - chw) / 2; cx = x + chw / 2
        sev = worst.get(key)
        col = SEV_COLOR.get(sev, "#4a9d4a"); lab = SEV_RU.get(sev, "устойчив")
        p.append(f'<text x="{cx:.1f}" y="{cy0-6}" font-size="9.5" text-anchor="middle" fill="#999">{ruP[key]}</text>')
        p.append(f'<rect x="{x}" y="{cy0}" width="{chw}" height="{chh}" rx="6" fill="#fff" stroke="{col}" stroke-width="2"/>')
        p.append(f'<circle cx="{cx:.1f}" cy="{cy0+18}" r="5" fill="{col}"/>')
        p.append(f'<text x="{cx:.1f}" y="{cy0+39}" font-size="9" text-anchor="middle" fill="{col}" font-weight="700">{lab}</text>')
    p.append('</svg>')
    return "\n".join(p)


def _parse_dyn(s):
    t = s.strip()[0]
    m = re.search(r"\(([^)]+)\)", s)
    if not m:
        return None
    parts = [x.strip() for x in m.group(1).split("-")]
    return (t, parts[0], parts[1]) if len(parts) == 2 else None


def _dynnode(cx, y, w, h, el, title, animal, accent):
    """Узел динамики (год/удача): тинт по стихии ветви, акцентная рамка, заголовок + животное."""
    x = cx - w / 2
    return (f'<rect x="{x:.1f}" y="{y}" width="{w}" height="{h}" rx="7" fill="{EL_TINT.get(el,"#eee")}" '
            f'stroke="{accent}" stroke-width="2"/>'
            f'<rect x="{x:.1f}" y="{y}" width="{w}" height="6" rx="3" fill="{EL_COLOR.get(el,"#999")}"/>'
            f'<text x="{cx:.1f}" y="{y+22}" font-size="10.5" text-anchor="middle" font-weight="700" fill="{accent}">{_esc(title)}</text>'
            f'<text x="{cx:.1f}" y="{y+38}" font-size="11.5" text-anchor="middle" font-weight="700" fill="#1a1a1a">{_esc(animal)}</text>')


def dynamic_interactions_svg(d):
    """Граф: как текущий год (流年) и столп удачи (大运) задевают натальные ветви карты."""
    dyn = d.get("dynamic_interactions") or {}
    order = ["hour", "day", "month", "year"]; ruP = {"hour": "Час", "day": "День", "month": "Месяц", "year": "Год"}
    P = d["pillars"]
    n, cw, pad, nodew = 4, 150, 18, 116
    natal_y, nodeh, dyn_y, dnh = 196, 42, 60, 46
    W, H = pad * 2 + n * cw, natal_y + nodeh + 22
    yr = dyn.get("year") or {}; lk = dyn.get("luck") or {}
    year_b = d.get("current_year", {}).get("branch", {})
    luck_pil = next((pp for pp in d.get("luck_pillars", {}).get("pillars", []) if pp.get("name") == lk.get("pillar")), None)
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Динамика год и удача">']
    p.append(f'<text x="{pad}" y="22" font-size="15" font-weight="700" fill="#1a1a1a">Что активируется сейчас: год и удача × карта</text>')
    p.append(f'<text x="{pad}" y="40" font-size="10.5" fill="#666">ветви {dyn.get("as_of_year", "текущего года")} и удачи vs натальные · сигнал-окно, не вердикт (без трансформации)</text>')
    natal_cx = {}
    for i, key in enumerate(order):
        x = pad + i * cw + (cw - nodew) / 2; cx = pad + i * cw + cw / 2
        b = P[key]["branch"]
        p.append(_branch_node(x, natal_y, nodew, nodeh, b["element"], b["animal"]))
        p.append(f'<text x="{cx:.1f}" y="{natal_y+nodeh+14}" font-size="8.5" text-anchor="middle" fill="#999">{ruP[key]}</text>')
        natal_cx[ruP[key]] = cx
    year_cx, luck_cx = W * 0.30, W * 0.70
    nodes_xy = {"流年": (year_cx, dyn_y + dnh), "大运": (luck_cx, dyn_y + dnh)}
    p.append(_dynnode(year_cx, dyn_y, 150, dnh, year_b.get("element", ""),
                      f"Год {dyn.get('as_of_year','')}", year_b.get("animal", ""), "#b5487a"))
    if lk and luck_pil:
        lb = luck_pil["branch"]
        p.append(_dynnode(luck_cx, dyn_y, 150, dnh, lb.get("element", ""),
                          f"Удача {round(lk['age_start'])}–{round(lk['age_end'])}", lb.get("animal", ""), "#3f6fae"))
    edges = []
    for s in yr.get("vs_natal", []):
        pr = _parse_dyn(s)
        if pr:
            edges.append((pr[0], "流年", pr[2]))
    for s in lk.get("vs_natal", []):
        pr = _parse_dyn(s)
        if pr:
            edges.append((pr[0], "大运", pr[2]))
    for s in dyn.get("year_vs_luck", []):
        pr = _parse_dyn(s)
        if pr:
            edges.append((pr[0], "流年", "大运"))
    for t, src, tgt in edges[:6]:
        lab, col = INTER_TYPE.get(t, ("связь", "#777"))
        s_xy = nodes_xy.get(src)
        t_xy = nodes_xy.get("大运") if tgt == "大运" else (natal_cx.get(tgt), natal_y)
        if not s_xy or not t_xy or t_xy[0] is None:
            continue
        p.append(_arrow(s_xy, t_xy, 24, 22, col, dashed=(t != "冲"), width=2.2))
        mx, my = (s_xy[0] + t_xy[0]) / 2, (s_xy[1] + t_xy[1]) / 2
        p.append(f'<rect x="{mx-32:.1f}" y="{my-9:.1f}" width="64" height="16" rx="8" fill="#fff" stroke="{col}"/>')
        p.append(f'<text x="{mx:.1f}" y="{my+3:.1f}" font-size="9.5" text-anchor="middle" fill="{col}" font-weight="700">{lab}</text>')
    if not edges:
        p.append(f'<text x="{W/2:.1f}" y="140" font-size="11" text-anchor="middle" fill="#888">'
                 f'год и удача натальные ветви напрямую не задевают</text>')
    p.append('</svg>')
    return "\n".join(p)


# ── Дизайн Человека: Бодиграф ───────────────────────────────────────────────
# Канонические позиции 9 центров (cx, cy, форма, ширина, высота). Формы:
# sq=квадрат, dia=ромб, td=треуг.вниз, tu=вверх, tl=влево, tr=вправо.
BG_POS = {
    "Голова": (170, 76, "td", 78, 44), "Аджна": (170, 148, "tu", 78, 44),
    "Горло": (170, 224, "sq", 70, 54), "G-центр (Самость)": (170, 320, "dia", 76, 76),
    "Сердце (Эго)": (262, 352, "tl", 54, 52), "Сакрал": (170, 420, "sq", 70, 54),
    "Селезёнка": (72, 420, "tr", 54, 70), "Солнечное сплетение": (276, 430, "tl", 54, 70),
    "Корень": (170, 512, "sq", 74, 54),
}
BG_SHORT = {"Голова": "Голова", "Аджна": "Аджна", "Горло": "Горло", "G-центр (Самость)": "G",
            "Сердце (Эго)": "Эго", "Сакрал": "Сакрал", "Селезёнка": "Селез.",
            "Солнечное сплетение": "Эмоц.", "Корень": "Корень"}


def _shape(sh, cx, cy, w, h, fill, stroke, sw, dash=""):
    hw, hh = w / 2, h / 2
    da = f' stroke-dasharray="{dash}"' if dash else ""
    if sh == "sq":
        return f'<rect x="{cx-hw:.0f}" y="{cy-hh:.0f}" width="{w}" height="{h}" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{da}/>'
    if sh == "dia":
        pts = f"{cx},{cy-hh} {cx+hw},{cy} {cx},{cy+hh} {cx-hw},{cy}"
    elif sh == "td":
        pts = f"{cx-hw},{cy-hh} {cx+hw},{cy-hh} {cx},{cy+hh}"
    elif sh == "tu":
        pts = f"{cx},{cy-hh} {cx+hw},{cy+hh} {cx-hw},{cy+hh}"
    elif sh == "tl":
        pts = f"{cx-hw},{cy} {cx+hw},{cy-hh} {cx+hw},{cy+hh}"
    else:  # tr
        pts = f"{cx+hw},{cy} {cx-hw},{cy-hh} {cx-hw},{cy+hh}"
    return f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{da}/>'


def bodygraph_svg(d):
    """Бодиграф ДЧ: 9 центров (закрашены = определены) + определённые каналы + сводка справа."""
    defined = set(d.get("defined_centers", []))
    cw = (d.get("convention_warnings") or [{}])[0]
    flip = (defined ^ set(cw.get("defined_centers_alt", []))) if cw.get("defined_centers_alt") else set()
    W, H = 640, 588
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Бодиграф">']
    p.append(f'<text x="16" y="24" font-size="16" font-weight="700" fill="#1a1a1a">Бодиграф</text>')
    p.append(f'<text x="16" y="42" font-size="10.5" fill="#666">закрашен — центр определён (стабилен) · белый — открыт (переменчив)</text>')
    # каналы за центрами: ВСЕ 36 (потенциальные — бледно, определённые — ярко); параллельные смещаем
    chans, seen = [], {}
    for ch in (d.get("all_channels") or d.get("defined_channels", [])):
        parts = ch.get("centers", "").split("↔")
        if len(parts) != 2 or parts[0] not in BG_POS or parts[1] not in BG_POS:
            continue
        key = tuple(sorted(parts)); off = seen.get(key, 0); seen[key] = off + 1
        chans.append((ch, parts, off))

    def _chan_line(parts, off, col, wdt):
        ax, ay = BG_POS[parts[0]][:2]; bx, by = BG_POS[parts[1]][:2]
        dx, dy = bx - ax, by - ay; L = math.hypot(dx, dy) or 1
        ox, oy = -dy / L * off * 6, dx / L * off * 6
        ln = (f'<line x1="{ax+ox:.1f}" y1="{ay+oy:.1f}" x2="{bx+ox:.1f}" y2="{by+oy:.1f}" '
              f'stroke="{col}" stroke-width="{wdt}"/>')
        return ln, (ax + bx) / 2 + ox, (ay + by) / 2 + oy
    for ch, parts, off in chans:                              # бледные потенциальные
        if not ch.get("defined", True):
            p.append(_chan_line(parts, off, "#e2e2e2", 1.2)[0])
    for ch, parts, off in chans:                              # яркие определённые + метки ворот
        if ch.get("defined", True):
            ln, mx, my = _chan_line(parts, off, "#d9743f", 3)
            p.append(ln)
            p.append(f'<rect x="{mx-15:.1f}" y="{my-7:.1f}" width="30" height="13" rx="6" fill="#fff" stroke="#d9743f" stroke-width="0.8"/>')
            p.append(f'<text x="{mx:.1f}" y="{my+3:.1f}" font-size="7.8" text-anchor="middle" fill="#a85a2a" font-weight="700">{_esc(ch.get("gates",""))}</text>')
    # центры
    for name, (cx, cy, sh, w, h) in BG_POS.items():
        on = name in defined; fl = name in flip
        if fl:                                            # центр «плавает» между конвенциями узлов
            p.append(_shape(sh, cx, cy, w, h, "#c2d0d8", "#d9743f", 2.4, dash="4 2"))
            txtc = "#7a4a1a"
        else:
            p.append(_shape(sh, cx, cy, w, h, "#79a3b8" if on else "#ffffff", "#33525f" if on else "#bbbbbb", 2 if on else 1.3))
            txtc = "#fff" if on else "#999"
        ly = cy + 3 if sh != "tu" else cy + 9
        p.append(f'<text x="{cx:.0f}" y="{ly:.0f}" font-size="9" text-anchor="middle" fill="{txtc}" font-weight="700">{_esc(BG_SHORT[name])}{"?" if fl else ""}</text>')
    # сводка справа
    px = 398
    cross = d.get("incarnation_cross", {})
    rows = [("Тип", d.get("type", "")),
            ("Стратегия", (d.get("strategy", "") or "").split("(")[0].strip()),
            ("Авторитет", (d.get("authority", "") or "").split(" — ")[0]),
            ("Профиль", str(d.get("profile", ""))),
            ("Определение", d.get("definition", "")),
            ("Крест", cross.get("notation", ""))]
    y = 84
    for lab, val in rows:
        p.append(f'<text x="{px}" y="{y}" font-size="9.5" fill="#999">{_esc(lab)}</text>')
        p.append(f'<text x="{px}" y="{y+15}" font-size="11.5" font-weight="700" fill="#1a1a1a">{_esc(val[:30])}</text>')
        y += 42
    if cw:
        _canon = d.get("node_convention") == cw.get("canonical", "node_true")
        p.append(f'<rect x="{px}" y="{y-4}" width="226" height="68" rx="6" fill="#fff7ed" stroke="#e08a2b"/>')
        if _canon:
            p.append(f'<text x="{px+8}" y="{y+13}" font-size="9.3" font-weight="700" fill="#b5701a">Канон: истинный узел (офиц.)</text>')
            p.append(f'<text x="{px+8}" y="{y+28}" font-size="8.4" fill="#7a5a1a">сплошные центры — каноническая карта.</text>')
            p.append(f'<text x="{px+8}" y="{y+40}" font-size="8.4" fill="#7a5a1a">пунктир «?» — усреднённый узел (стороннее)</text>')
            p.append(f'<text x="{px+8}" y="{y+52}" font-size="8.4" fill="#7a5a1a">дал бы: {_esc(cw.get("authority_alt",""))}</text>')
        else:
            p.append(f'<text x="{px+8}" y="{y+13}" font-size="9.3" font-weight="700" fill="#b5701a">⚠ Усреднённый узел — НЕ канон</text>')
            p.append(f'<text x="{px+8}" y="{y+28}" font-size="8.4" fill="#7a5a1a">сплошное — стороннее. Канон (офиц.):</text>')
            p.append(f'<text x="{px+8}" y="{y+40}" font-size="8.4" fill="#7a5a1a">истинный узел, Авторитет {_esc(cw.get("authority_alt",""))}.</text>')
            p.append(f'<text x="{px+8}" y="{y+52}" font-size="8.4" fill="#7a5a1a">пунктир «?» — каноническая версия</text>')
    p.append('</svg>')
    return "\n".join(p)


HD_BODY_ORDER = ["Солнце", "Земля", "Сев.Узел", "Юж.Узел", "Луна", "Меркурий", "Венера",
                 "Марс", "Юпитер", "Сатурн", "Уран", "Нептун", "Плутон"]


def activations_svg(d):
    """26 активаций: Дизайн (бессозн., красным) и Личность (созн., чёрным) — планета → ворота.линия."""
    act = d.get("activations", {})
    P = {a["body_ru"]: f'{a["gate"]}.{a["line"]}' for a in act.get("personality", [])}
    D = {a["body_ru"]: f'{a["gate"]}.{a["line"]}' for a in act.get("design", [])}
    bodies = [b for b in HD_BODY_ORDER if b in P or b in D] or list(P.keys())
    W, top, rowh = 480, 64, 24
    H = top + len(bodies) * rowh + 8
    midx = W / 2
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Активации">']
    p.append(f'<text x="16" y="22" font-size="15" font-weight="700" fill="#1a1a1a">Активации (планеты → ворота.линия)</text>')
    p.append(f'<text x="16" y="40" font-size="10.5" fill="#666">Дизайн — бессознательное (тело), Личность — сознание (разум)</text>')
    p.append(f'<text x="{midx-44:.0f}" y="56" font-size="11" text-anchor="end" fill="#c0392b" font-weight="700">Дизайн</text>')
    p.append(f'<text x="{midx+44:.0f}" y="56" font-size="11" text-anchor="start" fill="#1a1a1a" font-weight="700">Личность</text>')
    p.append(f'<line x1="{midx:.0f}" y1="62" x2="{midx:.0f}" y2="{H-8}" stroke="#eee" stroke-width="1"/>')
    for i, b in enumerate(bodies):
        y = top + i * rowh + 15
        p.append(f'<text x="{midx-44:.0f}" y="{y}" font-size="11.5" text-anchor="end" fill="#c0392b" font-weight="700">{_esc(D.get(b,"—"))}</text>')
        p.append(f'<text x="{midx:.0f}" y="{y}" font-size="9.5" text-anchor="middle" fill="#777">{_esc(b)}</text>')
        p.append(f'<text x="{midx+44:.0f}" y="{y}" font-size="11.5" text-anchor="start" fill="#1a1a1a" font-weight="700">{_esc(P.get(b,"—"))}</text>')
    p.append('</svg>')
    return "\n".join(p)


def fragility_hd_svg(d):
    """Хрупкость активаций: какие планеты ближе всего к смене линии (что «перевернётся» при неточном времени)."""
    fr = d.get("fragile_activations", [])[:5]
    W, top, rowh = 580, 60, 30
    H = top + max(1, len(fr)) * rowh + 8
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Хрупкость активаций">']
    p.append(f'<text x="16" y="22" font-size="15" font-weight="700" fill="#1a1a1a">Хрупкость к точности времени (активации)</text>')
    p.append(f'<text x="16" y="40" font-size="10.5" fill="#666">ближе всего к смене линии — «перевернутся» первыми при неточном времени</text>')
    if not fr:
        p.append(f'<text x="{W/2:.0f}" y="{top+20}" font-size="11" text-anchor="middle" fill="#888">данных нет</text>')
        p.append('</svg>'); return "\n".join(p)
    for i, a in enumerate(fr):
        y = top + i * rowh
        mins = a.get("minutes", 9999)
        col = "#c62828" if mins < 30 else "#e08a2b" if mins < 120 else "#4a9d4a"
        p.append(f'<circle cx="26" cy="{y+8}" r="5" fill="{col}"/>')
        p.append(f'<text x="42" y="{y+12}" font-size="11.5" fill="#1a1a1a">{_esc(a.get("body",""))} — ворота {_esc(a.get("gate_line",""))}</text>')
        p.append(f'<text x="{W-16}" y="{y+12}" font-size="11" text-anchor="end" fill="{col}" font-weight="700">{mins:.0f} мин до смены линии</text>')
    p.append('</svg>')
    return "\n".join(p)


def hd_demo_md(d):
    """Демо-срез чтения ДЧ: Бодиграф + подпись (вход — hd.json, не bazi.json)."""
    cross = d.get("incarnation_cross", {})
    o = ["# Дизайн Человека — инфографика (демо)"]
    o.append(f"Тип: **{d.get('type')}** · Авторитет: **{d.get('authority')}** · Профиль: **{d.get('profile')}**.\n")
    o.append("## Твой Бодиграф")
    o.append(_block(bodygraph_svg(d)))
    o.append("*Как читать:* 9 центров — **закрашенные определены** (работают стабильно, «всегда включены»), "
             "**белые открыты** (переменчивы, тут учишься и обуславливаешься). Оранжевые линии — определённые "
             f"каналы (с номерами ворот). Стратегия: {d.get('strategy')}. Сигнатура: {d.get('signature')}, "
             f"не-самость: {d.get('not_self_theme')}. Крест: {cross.get('notation')} — {cross.get('angle')}. "
             "[факт] — центры/каналы/тип из калькулятора; [интерпретация] — смысл.\n")
    o.append("## Активации: Дизайн и Личность")
    o.append(_block(activations_svg(d)))
    o.append("*Как читать:* 13 тел (Солнце…Плутон) на двух уровнях. **Личность** (чёрным) — что ты осознаёшь, "
             "ум, «как ты себя ощущаешь». **Дизайн** (красным) — бессознательное, тело, заложено до рождения "
             "(~88° Солнца раньше). Пары планета→ворота.линия и складываются в твои каналы. [факт] — из эфемерид.\n")

    o.append("## Что «поплывёт» первым: хрупкость активаций")
    o.append(_block(fragility_hd_svg(d)))
    o.append("*Как читать:* активации у самой границы линии — при неточном времени рождения они сменятся "
             "первыми (а с ними может поехать профиль/авторитет). Красные — критично близко. Если время "
             "неточное — стоит ректифицировать. [факт] — минуты из калькулятора.\n")

    for w in d.get("convention_warnings", []):
        o.append(f"> ⚠ **Конвенция узлов:** {w.get('text')}\n")
    return "\n".join(o)


# ── Джйотиш: южноиндийская карта раши (знаки фиксированы, по часовой от Рыб) ──
RASHI_CELL = {
    "Рыбы": (0, 0), "Овен": (0, 1), "Телец": (0, 2), "Близнецы": (0, 3),
    "Рак": (1, 3), "Лев": (2, 3),
    "Дева": (3, 3), "Весы": (3, 2), "Скорпион": (3, 1), "Стрелец": (3, 0),
    "Козерог": (2, 0), "Водолей": (1, 0),
}
GRAHA_ABBR = {"Солнце": "Со", "Луна": "Лу", "Марс": "Ма", "Меркурий": "Ме", "Юпитер": "Юп",
              "Венера": "Ве", "Сатурн": "Са", "Раху": "Ра", "Кету": "Ке"}


def rashi_chart_svg(d):
    """Карта раши D-1 (южноиндийская): 12 знаков фиксированы, планеты в своих знаках, центр — сводка."""
    cell, pad, top = 92, 16, 52
    W, H = pad * 2 + 4 * cell, top + 4 * cell + 12
    r2h = {h["rashi"]: h["house"] for h in d.get("house_lords", [])}
    bycell = {}
    for g in d.get("grahas", []):
        ab = GRAHA_ABBR.get(g["graha"].split(" ")[0], g["graha"][:2])
        bycell.setdefault(g["rashi"], []).append(ab)
    lagna_r = d.get("lagna", {}).get("rashi")
    moon_r = next((g["rashi"] for g in d.get("grahas", []) if g["graha"].startswith("Луна")), "")
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Карта раши">']
    p.append(f'<text x="{pad}" y="22" font-size="15" font-weight="700" fill="#1a1a1a">Карта раши (D-1, южноиндийская)</text>')
    p.append(f'<text x="{pad}" y="40" font-size="10.5" fill="#666">знаки фиксированы · цифра в углу — дом · «Λ» — Лагна</text>')
    gx, gy = pad, top
    for i in range(5):
        p.append(f'<line x1="{gx+i*cell}" y1="{gy}" x2="{gx+i*cell}" y2="{gy+4*cell}" stroke="#c8c8c8" stroke-width="1"/>')
        p.append(f'<line x1="{gx}" y1="{gy+i*cell}" x2="{gx+4*cell}" y2="{gy+i*cell}" stroke="#c8c8c8" stroke-width="1"/>')
    for rashi, (r, c) in RASHI_CELL.items():
        x, y = gx + c * cell, gy + r * cell; cx = x + cell / 2
        if rashi == lagna_r:
            p.append(f'<rect x="{x+1}" y="{y+1}" width="{cell-2}" height="{cell-2}" fill="#fdf3da"/>')
            p.append(f'<line x1="{x}" y1="{y+18}" x2="{x+18}" y2="{y}" stroke="#c79a3a" stroke-width="2"/>')
            p.append(f'<text x="{x+4}" y="{y+13}" font-size="9" fill="#a8801f" font-weight="700">Λ</text>')
        p.append(f'<text x="{cx:.0f}" y="{y+14}" font-size="8.5" text-anchor="middle" fill="#888">{_esc(rashi)}</text>')
        h = r2h.get(rashi)
        if h:
            p.append(f'<text x="{x+cell-5}" y="{y+13}" font-size="8" text-anchor="end" fill="#bbb">{h}</text>')
        gs = bycell.get(rashi, [])
        for li in range(0, len(gs), 2):
            p.append(f'<text x="{cx:.0f}" y="{y+42+(li//2)*16}" font-size="11" text-anchor="middle" '
                     f'fill="#1a1a1a" font-weight="700">{_esc(" ".join(gs[li:li+2]))}</text>')
    # центр 2×2 — сводка (по одному факту на клетку)
    info = [((1, 1), "Лагна", lagna_r), ((1, 2), "Луна", moon_r),
            ((2, 1), "D9-Лагна", d.get("navamsa", {}).get("lagna_rashi", "")),
            ((2, 2), "Маха-даша", d.get("maha_dasha", {}).get("lord", ""))]
    for (r, c), lab, val in info:
        cx, cyy = gx + c * cell + cell / 2, gy + r * cell
        p.append(f'<text x="{cx:.0f}" y="{cyy+34}" font-size="8.5" text-anchor="middle" fill="#999">{_esc(lab)}</text>')
        p.append(f'<text x="{cx:.0f}" y="{cyy+52}" font-size="11.5" text-anchor="middle" fill="#1a1a1a" font-weight="700">{_esc(val)}</text>')
    p.append('</svg>')
    return "\n".join(p)


GRAHA_COLOR = {"Солнце": "#d98c3f", "Луна": "#9aa6b0", "Марс": "#d6483b", "Меркурий": "#4a9d4a",
               "Юпитер": "#caa23a", "Венера": "#c77fa6", "Сатурн": "#5a6b8c", "Раху": "#7a6f8a", "Кету": "#8a7a6a"}


def dasha_timeline_svg(d):
    """Лента маха-даш (Вимшоттари): большие периоды жизни под управлением планет, текущий подсвечен."""
    tl = d.get("dasha_timeline", [])
    cur_lord = d.get("maha_dasha", {}).get("lord"); cur_from = d.get("maha_dasha", {}).get("from")
    as_of_y = (d.get("dasha_as_of", "") or "")[:4]
    n, cw, pad, ctop, ch = max(1, len(tl)), 64, 16, 64, 80
    W, H = pad * 2 + n * cw, ctop + ch + 14
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Маха-даши">']
    p.append(f'<text x="{pad}" y="22" font-size="15" font-weight="700" fill="#1a1a1a">Маха-даши (Вимшоттари) — периоды жизни</text>')
    p.append(f'<text x="{pad}" y="40" font-size="10.5" fill="#666">каждый блок — большой период под планетой-управителем · ▲ сейчас</text>')
    if not tl:
        p.append(f'<text x="{W/2:.0f}" y="{ctop+30}" font-size="11" text-anchor="middle" fill="#888">нет данных</text>')
        p.append('</svg>'); return "\n".join(p)
    for i, s in enumerate(tl):
        x = pad + i * cw; cx = x + cw / 2
        col = GRAHA_COLOR.get(s["lord"], "#999999")
        cur = (s["lord"] == cur_lord and s["from"] == cur_from)
        p.append(f'<rect x="{x}" y="{ctop}" width="{cw-3}" height="{ch}" rx="4" '
                 f'fill="{"#fcfbf6" if cur else "#ffffff"}" stroke="{"#1a1a1a" if cur else "#d2d2d2"}" '
                 f'stroke-width="{2.4 if cur else 1}"/>')
        p.append(f'<rect x="{x}" y="{ctop}" width="{cw-3}" height="7" rx="3" fill="{col}"/>')
        p.append(f'<text x="{cx:.0f}" y="{ctop+27}" font-size="11" text-anchor="middle" font-weight="700" fill="#1a1a1a">{_esc(s["lord"])}</text>')
        p.append(f'<text x="{cx:.0f}" y="{ctop+45}" font-size="9.5" text-anchor="middle" fill="#666">{s["years"]:g} лет</text>')
        p.append(f'<text x="{cx:.0f}" y="{ctop+63}" font-size="8" text-anchor="middle" fill="#999">{_esc(s["from"][:4])}–{_esc(s["to"][:4])}</text>')
        if cur:
            p.append(f'<text x="{cx:.0f}" y="{ctop-6}" font-size="11" text-anchor="middle" font-weight="700" fill="#1a1a1a">▲ {_esc(as_of_y)}</text>')
    p.append('</svg>')
    return "\n".join(p)


def jy_demo_md(d):
    """Демо-срез чтения Джйотиш: карта раши + лента даш (вход — jyotish.json)."""
    lag = d.get("lagna", {})
    o = ["# Джйотиш — инфографика (демо)"]
    o.append(f"Лагна: **{lag.get('rashi')}** ({lag.get('rashi_sanskrit')}) · Луна в накшатре "
             f"**{d.get('moon_nakshatra', {}).get('nakshatra')}**.\n")
    o.append("## Карта раши (D-1)")
    o.append(_block(rashi_chart_svg(d)))
    md = d.get("maha_dasha", {}); ad = d.get("antar_dasha", {})
    o.append("*Как читать:* южноиндийская карта — 12 знаков на фиксированных местах, планеты стоят в своих "
             "знаках (Со=Солнце, Лу=Луна, Ма=Марс, Ме=Меркурий, Юп=Юпитер, Ве=Венера, Са=Сатурн, Ра=Раху, "
             "Ке=Кету). Цифра в углу — номер дома от Лагны. «Λ» — восходящий знак. "
             f"Период сейчас: маха-даша **{md.get('lord')}** ({md.get('from','')[:4]}–{md.get('to','')[:4]}), "
             f"антар **{ad.get('lord')}**. [факт] — позиции из эфемерид (аянамша Лахири).\n")
    o.append("## Периоды жизни: маха-даши (Вимшоттари)")
    o.append(_block(dasha_timeline_svg(d)))
    o.append("*Как читать:* жизнь делится на большие периоды (маха-даши) под управлением планет, по кругу. "
             f"Сейчас — **{md.get('lord')}** ({md.get('from','')[:4]}–{md.get('to','')[:4]}), внутри антар-даша "
             f"**{ad.get('lord') if ad else '—'}**. Что было и что впереди — видно слева и справа. "
             "[факт] — Вимшоттари от накшатры Луны.\n")

    o.append(f"> ⚠ Конвенции: {d.get('conventions')}\n")
    return "\n".join(o)


# ── Матрица Судьбы: центральный крест (ТОЛЬКО ядро — 5 арканов; октаграмму не считаем) ──
MATRIX_POS = [(-1, 0), (0, -1), (1, 0), (0, 1), (0, 0)]   # День·Месяц·Год·Сумма·Центр → лево/верх/право/низ/центр
MATRIX_LBL = ["День", "Месяц", "Год", "Сумма", ""]   # смыслы (Личность/Род/Задача/Назначение) — в подписи


def matrix_diamond_svg(d):
    """Ядро Матрицы Судьбы — центральный крест из 5 главных арканов (НЕ полная октаграмма)."""
    cps = list(d.get("core_points", {}).items())[:5]
    W, H, cx, cy, rad = 470, 466, 235, 256, 150
    pts = [(cx + dx * rad, cy + dy * rad) for dx, dy in MATRIX_POS]
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Ядро Матрицы Судьбы">']
    p.append(f'<text x="16" y="22" font-size="15" font-weight="700" fill="#1a1a1a">Матрица Судьбы — ядро (центральный крест)</text>')
    p.append(f'<text x="16" y="40" font-size="10.5" fill="#666">5 главных арканов · полная октаграмма НЕ считается (формулы вариативны)</text>')
    L, T, R, B, C = pts
    for (ax, ay), (bx, by) in [(L, T), (T, R), (R, B), (B, L), (L, R), (T, B)]:
        p.append(f'<line x1="{ax:.0f}" y1="{ay:.0f}" x2="{bx:.0f}" y2="{by:.0f}" stroke="#cdbfe0" stroke-width="1.4"/>')
    for i, ((k, v), (x, y)) in enumerate(zip(cps, pts)):
        is_c = (i == 4); r = 44 if is_c else 40
        p.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="{"#f6edd0" if is_c else "#ece4f5"}" '
                 f'stroke="{"#c79a3a" if is_c else "#8a6aaa"}" stroke-width="2"/>')
        p.append(f'<text x="{x:.0f}" y="{y-4:.0f}" font-size="19" text-anchor="middle" font-weight="700" fill="#3a2a4a">{v.get("arcana","")}</text>')
        words = str(v.get("name", "")).split()
        nм = [words[0], " ".join(words[1:])] if len(words) >= 2 else [words[0] if words else "", ""]
        p.append(f'<text x="{x:.0f}" y="{y+11:.0f}" font-size="8" text-anchor="middle" fill="#5a4a6a">{_esc(nм[0])}</text>')
        if nм[1]:
            p.append(f'<text x="{x:.0f}" y="{y+20:.0f}" font-size="8" text-anchor="middle" fill="#5a4a6a">{_esc(nм[1])}</text>')
        lab = MATRIX_LBL[i]
        if i == 0:
            p.append(f'<text x="{x-r-6:.0f}" y="{y:.0f}" font-size="9" text-anchor="end" fill="#999">{_esc(lab)}</text>')
        elif i == 1:
            p.append(f'<text x="{x:.0f}" y="{y-r-8:.0f}" font-size="9" text-anchor="middle" fill="#999">{_esc(lab)}</text>')
        elif i == 2:
            p.append(f'<text x="{x+r+6:.0f}" y="{y:.0f}" font-size="9" text-anchor="start" fill="#999">{_esc(lab)}</text>')
        elif i == 3:
            p.append(f'<text x="{x:.0f}" y="{y+r+16:.0f}" font-size="9" text-anchor="middle" fill="#999">{_esc(lab)}</text>')
        else:
            p.append(f'<text x="{x:.0f}" y="{y-r+12:.0f}" font-size="8" text-anchor="middle" fill="#a8801f" font-weight="700">центр</text>')
    p.append('</svg>')
    return "\n".join(p)


def matrix_demo_md(d):
    """Демо-срез чтения Матрицы Судьбы (вход — matrix.json)."""
    cps = d.get("core_points", {}); ca = d.get("central_arcana", {})
    o = ["# Матрица Судьбы — инфографика (демо)"]
    o.append(f"Метод: {d.get('method')}. Центральный аркан (суть): **{ca.get('arcana')} {ca.get('name')}**.\n")
    o.append("## Ядро Матрицы (центральный крест)")
    o.append(_block(matrix_diamond_svg(d)))
    lst = " · ".join(f"{v.get('arcana')} {v.get('name')}" for v in cps.values())
    o.append("*Как читать:* пять главных арканов: **День** (личность, «Я в этой жизни»), **Месяц** (родовая "
             "энергия), **Год** (духовная задача), **Сумма** (предназначение), **Центр** (суть, зона комфорта). "
             f"Числа — старшие арканы Таро (1–22). Здесь: {lst}. [факт] — арифметика по дате; "
             "[интерпретация] — значения арканов.\n")
    o.append(f"> ⚠ {d.get('honesty_note','')} {str(d.get('limitations',''))[:160]}…\n")
    return "\n".join(o)


# ── Джунгци: Меуа (sme ba) 1-9 → (цвет-рус, hex, стихия, цвет текста); магический квадрат Ло Шу ──
MEWA_INFO = {1: ("Белая", "#f0f0f0", "Металл", "#333"), 2: ("Чёрная", "#3a3a3a", "Вода", "#fff"),
             3: ("Синяя", "#3f6fae", "Вода", "#fff"), 4: ("Зелёная", "#4a9d4a", "Дерево", "#fff"),
             5: ("Жёлтая", "#e6c84e", "Земля", "#333"), 6: ("Белая", "#f0f0f0", "Металл", "#333"),
             7: ("Красная", "#d6483b", "Огонь", "#fff"), 8: ("Белая", "#f0f0f0", "Металл", "#333"),
             9: ("Красная", "#d6483b", "Огонь", "#fff")}
LOSHU = [[4, 9, 2], [3, 5, 7], [8, 1, 6]]


def mewa_square_svg(d):
    """Меуа — магический квадрат Ло Шу (9 дворцов); твоя Меуа подсвечена. Все 9 цветов — универсальны."""
    mine = d.get("mewa", {}).get("number")
    cell, pad, top = 100, 16, 56
    W, H = pad * 2 + 3 * cell, top + 3 * cell + 12
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Меуа квадрат">']
    p.append(f'<text x="{pad}" y="22" font-size="15" font-weight="700" fill="#1a1a1a">Меуа — квадрат 9 дворцов (Ло Шу)</text>')
    p.append(f'<text x="{pad}" y="40" font-size="10.5" fill="#666">твоя подсвечена · общая на весь лунный год</text>')
    for r in range(3):
        for c in range(3):
            n = LOSHU[r][c]; cname, hexc, elem, txt = MEWA_INFO[n]
            x, y = pad + c * cell, top + r * cell; cx = x + cell / 2; is_m = (n == mine)
            p.append(f'<rect x="{x+2}" y="{y+2}" width="{cell-4}" height="{cell-4}" rx="6" fill="{hexc}" '
                     f'stroke="{"#1a1a1a" if is_m else "#cfcfcf"}" stroke-width="{3 if is_m else 1}"/>')
            p.append(f'<text x="{cx:.0f}" y="{y+52}" font-size="30" text-anchor="middle" font-weight="700" fill="{txt}">{n}</text>')
            p.append(f'<text x="{cx:.0f}" y="{y+70}" font-size="9.5" text-anchor="middle" fill="{txt}">{_esc(elem)}</text>')
            if is_m:
                p.append(f'<text x="{cx:.0f}" y="{y+18}" font-size="8.5" text-anchor="middle" font-weight="700" fill="{txt}">★ твоя</text>')
    p.append('</svg>')
    return "\n".join(p)


def forces_svg(d):
    """Пять сил Джунгци: выданные (цвет по стихии) и придержанные; справа — связь с годом.
    Подпись считается из данных: до 2026-07-11 движок выдавал 3 из 5, теперь все 5."""
    forces = d.get("forces", {})
    fyr = d.get("forces_year_relation", {}) or {}
    rel = fyr.get("relations", {}); yr = fyr.get("year", "")
    items = list(forces.items())
    n_out = sum(1 for _, v in items if v.get("element"))
    n_held = len(items) - n_out
    if n_held:
        cap = f'{n_out} выданы · {n_held} честно придержаны (правила не выверены)'
    else:
        cap = f'все {n_out} выданы'
    W, top, rowh = 620, 64, 36
    H = top + max(1, len(items)) * rowh + 8
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Пять сил">']
    p.append(f'<text x="16" y="22" font-size="15" font-weight="700" fill="#1a1a1a">Пять сил (Джунгци)</text>')
    p.append(f'<text x="16" y="40" font-size="10.5" fill="#666">{cap} · справа — связь с годом {_esc(str(yr))}</text>')
    for i, (full, v) in enumerate(items):
        y = top + i * rowh
        short = full.split(" (")[0]
        mean = full[full.find("(") + 1:full.find(")")] if "(" in full else ""
        el = v.get("element")
        p.append(f'<text x="16" y="{y+15}" font-size="11.5" font-weight="700" fill="#1a1a1a">{_esc(short)}</text>')
        p.append(f'<text x="16" y="{y+28}" font-size="8.5" fill="#999">{_esc(mean)}</text>')
        if el:
            col = EL_COLOR.get(el) or EL_COLOR.get(str(el).split(" (")[0], "#888888")
            el_disp = str(el).split(" (")[0]
            p.append(f'<rect x="200" y="{y+4}" width="96" height="22" rx="5" fill="{col}"/>')
            p.append(f'<text x="248" y="{y+19}" font-size="10.5" text-anchor="middle" fill="#fff" font-weight="700">{_esc(el_disp)}</text>')
            r = rel.get(full, {})
            if r.get("relation"):
                p.append(f'<text x="320" y="{y+19}" font-size="10" fill="#555">год: <tspan font-weight="700">{_esc(r["relation"])}</tspan> — {_esc((r.get("reading","") or "").split("—")[-1].strip()[:34])}</text>')
        else:
            p.append(f'<rect x="200" y="{y+4}" width="96" height="22" rx="5" fill="#fff" stroke="#ccc" stroke-dasharray="3 2"/>')
            p.append(f'<text x="248" y="{y+19}" font-size="9.5" text-anchor="middle" fill="#aaa">не выдана</text>')
    p.append('</svg>')
    return "\n".join(p)


def tibetan_demo_md(d):
    """Демо-срез чтения Джунгци (вход — tibetan.json)."""
    ys = d.get("year_sign", {}); mw = d.get("mewa", {})
    o = ["# Джунгци (тибетская) — инфографика (демо)"]
    o.append(f"Знак года: **{ys.get('full')}** ({ys.get('animal')} — {ys.get('animal_quality')}). "
             f"Меуа: **{mw.get('number')} {mw.get('color')}** ({mw.get('element')}).\n")
    o.append("## Меуа — 9 дворцов")
    o.append(_block(mewa_square_svg(d)))
    o.append("*Как читать:* Меуа (sme ba) — число 1–9 в магическом квадрате Ло Шу, твоё подсвечено "
             f"(**{mw.get('number')} {mw.get('color')}, {mw.get('element')}**). Не зависит от пола — одинакова "
             "у всех, рождённых в этот лунный год. [факт] — якорь 1927 = Меуа 1.\n")
    o.append("## Пять сил")
    o.append(_block(forces_svg(d)))
    _out = [f.split(" (")[0] for f, v in (d.get("forces") or {}).items() if v.get("element")]
    _held = [f.split(" (")[0] for f, v in (d.get("forces") or {}).items() if not v.get("element")]
    _line = f"*Как читать:* пять личных сил. Выданы: **{', '.join(_out) or '—'}**."
    if _held:
        _line += f" Честно НЕ выданы: **{', '.join(_held)}** (правила не выверены — не выдумываю)."
    _line += " Справа — как сила соотносится со стихией текущего года. [факт]" + (" / [придержано].\n" if _held else ".\n")
    o.append(_line)
    o.append(f"> ⚠ Уверенность системы: {str(d.get('confidence',''))[:70]}… Онлайн-Джунгци = упрощение монастырской традиции.\n")
    return "\n".join(o)


# ── Генные Ключи ────────────────────────────────────────────────────────────
def _short_sphere(s):
    return str(s.get("sphere_ru", "")).split("(")[0].split(" — ")[0].strip()


def spectrum_svg(d):
    """Главные Дары — спектр сознания Тень → Дар → Сиддхи (реакция → дар → высшее)."""
    gifts = d.get("prime_gifts", [])
    W, top, rowh = 640, 78, 48
    H = top + max(1, len(gifts)) * rowh + 8
    cxs = [236, 392, 548]
    cols = [("#9a4444", "#fff", "Тень"), ("#c79a3a", "#fff", "Дар"), ("#ddc97a", "#3a2e15", "Сиддхи")]
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Спектр Главных Даров">']
    p.append(f'<text x="16" y="22" font-size="15" font-weight="700" fill="#1a1a1a">Главные Дары: Тень → Дар → Сиддхи</text>')
    sub = "спектр: реакция (тень) → дар → высшее (сиддхи) · названия сверены с genekeys.com"
    p.append(f'<text x="16" y="40" font-size="10.5" fill="#666">{_esc(sub)}</text>')
    for (c, _t, lab), cx in zip(cols, cxs):
        p.append(f'<text x="{cx}" y="64" font-size="10" text-anchor="middle" font-weight="700" fill="{c}">{_esc(lab)}</text>')
    for i, g in enumerate(gifts):
        y = top + i * rowh
        p.append(f'<text x="16" y="{y+18}" font-size="10.5" font-weight="700" fill="#1a1a1a">{_esc(_short_sphere(g))}</text>')
        p.append(f'<text x="16" y="{y+32}" font-size="9" fill="#999">ключ {_esc(g.get("key_line",""))}</text>')
        states = [g.get("shadow_ru") or g.get("shadow"), g.get("gift_ru") or g.get("gift"),
                  g.get("siddhi_ru") or g.get("siddhi")]
        for j, (st, (c, txt, _l), cx) in enumerate(zip(states, cols, cxs)):
            p.append(f'<rect x="{cx-66}" y="{y+6}" width="132" height="26" rx="6" fill="{c}"/>')
            fs = 10 if len(str(st)) <= 14 else 9
            p.append(f'<text x="{cx}" y="{y+23}" font-size="{fs}" text-anchor="middle" fill="{txt}" font-weight="700">{_esc(st)}</text>')
            if j < 2:
                p.append(f'<text x="{(cx+cxs[j+1])/2:.0f}" y="{y+24}" font-size="13" text-anchor="middle" fill="#bbb">→</text>')
    p.append('</svg>')
    return "\n".join(p)


SEQ_INFO = {"Активация": ("#5a7db5", "призвание и вызов — кто ты"),
            "Венера": ("#c77fa6", "отношения и сердце"),
            "Жемчужина": ("#caa23a", "процветание и вклад в мир")}


def spheres_overview_svg(d):
    """11 сфер Голограммы по 3 последовательностям (Активация / Венера / Жемчужина)."""
    by_seq = {}
    for s in d.get("spheres", []):
        by_seq.setdefault(s.get("sequence", "?"), []).append(s)
    seqs = [q for q in ("Активация", "Венера", "Жемчужина") if q in by_seq]
    W, pad, top = 640, 14, 76
    colw = (W - pad * 2) / max(1, len(seqs))
    maxn = max((len(by_seq[q]) for q in seqs), default=0)
    H = top + maxn * 40 + 14
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="11 сфер Голограммы">']
    p.append(f'<text x="{pad}" y="22" font-size="15" font-weight="700" fill="#1a1a1a">Голограмма — 11 сфер по 3 путям</text>')
    p.append(f'<text x="{pad}" y="40" font-size="10.5" fill="#666">каждая сфера: ворота.линия и её Дар (раскрытое качество)</text>')
    for ci, q in enumerate(seqs):
        x = pad + ci * colw; col, mean = SEQ_INFO.get(q, ("#888", ""))
        p.append(f'<rect x="{x+4}" y="{top-22}" width="{colw-8}" height="20" rx="5" fill="{col}"/>')
        p.append(f'<text x="{x+colw/2:.0f}" y="{top-8}" font-size="10.5" text-anchor="middle" fill="#fff" font-weight="700">{_esc(q)}</text>')
        for si, s in enumerate(by_seq[q]):
            y = top + si * 40
            p.append(f'<text x="{x+12}" y="{y+12}" font-size="10.5" font-weight="700" fill="#1a1a1a">{_esc(_short_sphere(s))}</text>')
            p.append(f'<text x="{x+colw-12:.0f}" y="{y+12}" font-size="9" text-anchor="end" fill="#999">{_esc(str(s.get("gate"))+"."+str(s.get("line")))}</text>')
            p.append(f'<text x="{x+12}" y="{y+27}" font-size="9.5" fill="{col}">Дар: {_esc(s.get("gift_ru") or s.get("gift",""))}</text>')
    p.append('</svg>')
    return "\n".join(p)


def gk_demo_md(d):
    """Демо-срез чтения Генных Ключей (вход — gene_keys.json)."""
    pg = d.get("prime_gifts", [])
    o = ["# Генные Ключи — инфографика (демо)"]
    lw = next((g for g in pg if g.get("sphere") == "Life's Work"), {})
    o.append(f"Призвание (Life's Work): ключ **{lw.get('key_line')}** — путь "
             f"**{lw.get('shadow')} → {lw.get('gift')} → {lw.get('siddhi')}**.\n")
    o.append("## Главные Дары: Тень → Дар → Сиддхи")
    o.append(_block(spectrum_svg(d)))
    o.append("*Как читать:* каждый Ключ — спектр из трёх состояний одной энергии. **Тень** — реактивный "
             "низ (стресс, страх). **Дар** — раскрытое, рабочее качество. **Сиддхи** — высшая, просветлённая "
             "грань. Это не «ты плохой/хороший», а карта роста по одной линии. [факт] — ворота из эфемерид.\n")
    o.append("## Голограмма: 11 сфер")
    o.append(_block(spheres_overview_svg(d)))
    o.append("*Как читать:* 11 сфер на трёх путях. **Активация** — про тебя и твою работу; **Венера** — про "
             "отношения и сердце; **Жемчужина** — про процветание и вклад. Полную диаграмму-голограмму "
             "(с золотым путём) тут не рисую — только содержание сфер. [факт] — позиции; [интерпретация] — смысл.\n")
    o.append("> Названия Тень/Дар/Сиддхи (англ. оригиналы) сверены с genekeys.com — им можно доверять; "
             "рус.— перевод, а развёрнутая трактовка — интерпретация. Система: Ричард Радд, 2009.\n")
    return "\n".join(o)


# ── Синтез: КОНСТАНТЫ о самих системах (не зависят от человека = честный [факт]) ──
SYN_CLUSTERS = [   # независимый язык: (имя, цвет, [системы], зависимость-внутри)
    ("Западные ворота И-Цзин", "#5a7db5", ["Дизайн Человека", "Генные Ключи"], "ГК выведены из ворот ДЧ — почти тавтология"),
    ("Китайская лунно-солнечная", "#c0894a", ["Ба Цзы", "Джунгци"], "общий знак года рождения"),
    ("Индийская сидерическая", "#5a9d6a", ["Джйотиш"], "независимый язык"),
    ("Нумерология / Таро", "#9a6aaa", ["Матрица"], "независимый, современный"),
]
SYN_WEIGHT = [   # (система, богатство≈факторов, эпоха, уверенность, цвет кластера) — отсортировано
    ("Ба Цзы", 10, "древняя", "высокая", "#c0894a"),
    ("Джйотиш", 7, "древняя", "высокая", "#5a9d6a"),
    ("Дизайн Человека", 6, "1987", "ср. — узлы!", "#5a7db5"),
    ("Генные Ключи", 4, "2009", "ср. — из ДЧ", "#5a7db5"),
    ("Джунгци", 3, "онлайн-упрощ.", "средняя", "#c0894a"),
    ("Матрица", 2, "2006", "ср. — ядро", "#9a6aaa"),
]


def synthesis_independence_svg(meta=None):
    """6 систем → ~4 независимых языка: визуальный антидот «смотри, все совпали»."""
    W, H, bw, bh, gx, gy, gap = 660, 392, 312, 152, 18, 58, 18
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Карта независимости систем">']
    p.append(f'<text x="{gx}" y="24" font-size="15" font-weight="700" fill="#1a1a1a">6 систем ≠ 6 голосов: карта независимости</text>')
    p.append(f'<text x="{gx}" y="42" font-size="10.5" fill="#666">реально независимых языков ~4 · совпадение между языками ≠ доказательство</text>')
    for i, (name, col, sysz, note) in enumerate(SYN_CLUSTERS):
        r, c = divmod(i, 2); x = gx + c * (bw + gap); y = gy + r * (bh + gap)
        p.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="8" fill="#fafafa" stroke="{col}" stroke-width="1.5"/>')
        p.append(f'<rect x="{x}" y="{y}" width="{bw}" height="24" rx="4" fill="{col}"/>')
        p.append(f'<text x="{x+bw/2:.0f}" y="{y+16}" font-size="11" text-anchor="middle" fill="#fff" font-weight="700">{_esc(name)}</text>')
        if len(sysz) == 2:
            cx1, cx2, cyc = x + bw * 0.27, x + bw * 0.73, y + 70
            p.append(f'<line x1="{cx1:.0f}" y1="{cyc}" x2="{cx2:.0f}" y2="{cyc}" stroke="#999" stroke-width="2" stroke-dasharray="3 2"/>')
            for cxx, s in ((cx1, sysz[0]), (cx2, sysz[1])):
                p.append(f'<rect x="{cxx-58:.0f}" y="{cyc-16}" width="116" height="32" rx="6" fill="#fff" stroke="{col}"/>')
                p.append(f'<text x="{cxx:.0f}" y="{cyc+4}" font-size="10" text-anchor="middle" fill="#1a1a1a" font-weight="700">{_esc(s)}</text>')
            p.append(f'<text x="{x+bw/2:.0f}" y="{y+110}" font-size="8.6" text-anchor="middle" fill="#a8801f">⚠ {_esc(note)}</text>')
            p.append(f'<text x="{x+bw/2:.0f}" y="{y+128}" font-size="8.6" text-anchor="middle" fill="#999">→ один голос, не два</text>')
        else:
            p.append(f'<rect x="{x+bw/2-70:.0f}" y="{y+54}" width="140" height="34" rx="6" fill="#fff" stroke="{col}"/>')
            p.append(f'<text x="{x+bw/2:.0f}" y="{y+76}" font-size="11" text-anchor="middle" fill="#1a1a1a" font-weight="700">{_esc(sysz[0])}</text>')
            p.append(f'<text x="{x+bw/2:.0f}" y="{y+112}" font-size="8.6" text-anchor="middle" fill="#999">{_esc(note)}</text>')
    p.append('</svg>')
    return "\n".join(p)


def synthesis_weight_svg(meta=None):
    """Вес систем: длина = сколько факторов система реально дала (НЕ «насколько правда»)."""
    rows = SYN_WEIGHT
    W, top, rowh, left, barmax = 660, 64, 34, 150, 300
    H = top + len(rows) * rowh + 8
    mx = max(r[1] for r in rows)
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Вес систем">']
    p.append(f'<text x="14" y="22" font-size="15" font-weight="700" fill="#1a1a1a">Вес систем: богатство · эпоха · уверенность</text>')
    p.append(f'<text x="14" y="40" font-size="10.5" fill="#666">длина = сколько факторов система реально дала (не «насколько это правда»)</text>')
    for i, (sys, rich, era, conf, col) in enumerate(rows):
        y = top + i * rowh
        p.append(f'<text x="{left-10}" y="{y+15}" font-size="10.5" text-anchor="end" fill="#1a1a1a" font-weight="700">{_esc(sys)}</text>')
        p.append(f'<rect x="{left}" y="{y+3}" width="{barmax}" height="18" rx="3" fill="#f0f0f0"/>')
        p.append(f'<rect x="{left}" y="{y+3}" width="{barmax*rich/mx:.0f}" height="18" rx="3" fill="{col}"/>')
        p.append(f'<text x="{left+barmax+8}" y="{y+16}" font-size="9" fill="#777">{_esc(era)} · {_esc(conf)}</text>')
    p.append('</svg>')
    return "\n".join(p)


def _syn_wrap(s, maxlen):
    """Перенос текста ячейки по словам в строки ≤ maxlen символов (сверхдлинное слово рубим)."""
    s = str(s).strip()
    if not s:
        return ["—"]
    lines, cur = [], ""
    for w in s.split():
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= maxlen:
            cur += " " + w
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    out = []
    for ln in lines:
        while len(ln) > maxlen:
            out.append(ln[:maxlen]); ln = ln[maxlen:]
        if ln:
            out.append(ln)
    return out or ["—"]


def _syn_tspans(lines, cx, cy, line_h, font, fill, anchor="middle", weight=None):
    """Многострочный <text>, вертикально отцентрованный относительно cy (перенос строк в ячейке)."""
    y0 = cy - (len(lines) - 1) * line_h / 2.0
    wattr = f' font-weight="{weight}"' if weight else ""
    spans = "".join(f'<tspan x="{cx:.0f}" y="{y0 + k * line_h:.1f}">{_esc(ln)}</tspan>'
                    for k, ln in enumerate(lines))
    return f'<text font-size="{font}" text-anchor="{anchor}" fill="{fill}"{wattr}>{spans}</text>'


def synthesis_resonance_svg(m):
    """Резонанс тема×язык. Колонки = НЕЗАВИСИМЫЕ языки (тавтологии свёрнуты) → «6 голосов» нарисовать нельзя.
    Текст ячеек переносится по словам (не обрезается), высота строки подстраивается под число линий."""
    clusters = m.get("clusters", []); themes = m.get("themes", [])
    cells = m.get("cells", {}); res = m.get("resonance", {})
    n = max(1, len(clusters))
    W, left, rcol, top, line_h = 700, 90, 128, 76, 11
    colw = (W - left - rcol) / n
    maxlen_col = max(8, int(colw / 5.8))
    maxlen_res = max(8, int(rcol / 6.0))
    rows = []  # (theme, [lines_per_col...], res_lines, mark, row_h)
    for th in themes:
        row = cells.get(th, [])
        col_lines = [_syn_wrap(str(row[j]) if j < len(row) else "—", maxlen_col) for j in range(n)]
        mark = res.get(th, "")
        res_lines = _syn_wrap(mark, maxlen_res) if mark else ["—"]
        nmax = max([len(c) for c in col_lines] + [len(res_lines), 1])
        rows.append((th, col_lines, res_lines, mark, max(40, nmax * line_h + 16)))
    H = top + sum(r[4] for r in rows) + 8
    p = [f'<svg viewBox="0 0 {W} {H:.0f}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Резонанс по темам">']
    p.append(f'<text x="14" y="22" font-size="15" font-weight="700" fill="#1a1a1a">Резонанс по темам (между независимыми языками)</text>')
    p.append(f'<text x="14" y="40" font-size="10" fill="#666">колонки — независимые языки (тавтологии свёрнуты) · резонанс только МЕЖ языками · [интерпретация агента]</text>')
    for j, cl in enumerate(clusters):
        cx = left + j * colw + colw / 2
        p.append(f'<text x="{cx:.0f}" y="{top-6}" font-size="9" text-anchor="middle" fill="#555" font-weight="700">{_esc(cl)}</text>')
    rx = left + n * colw + rcol / 2
    p.append(f'<text x="{rx:.0f}" y="{top-6}" font-size="9" text-anchor="middle" fill="#555" font-weight="700">итог</text>')
    y = top
    for i, (th, col_lines, res_lines, mark, row_h) in enumerate(rows):
        cy = y + row_h / 2
        p.append(f'<rect x="14" y="{y:.0f}" width="{W-28}" height="{row_h-4:.0f}" rx="4" fill="{"#f7f7f7" if i%2 else "#fff"}" stroke="#eee"/>')
        p.append(_syn_tspans(_syn_wrap(th, 11), 18, cy, line_h, 10.5, "#1a1a1a", anchor="start", weight="700"))
        for j in range(n):
            cx = left + j * colw + colw / 2
            p.append(_syn_tspans(col_lines[j], cx, cy, line_h, 8.4, "#444"))
        mcol = "#c62828" if ("⚡" in mark or "конфликт" in mark) else "#2e7d32" if mark else "#bbb"
        p.append(_syn_tspans(res_lines, rx, cy, line_h, 8, mcol, weight="700"))
        y += row_h
    p.append('</svg>')
    return "\n".join(p)


def synthesis_demo_md(d=None):
    """Демо-срез синтеза: 3 графика (A константа, B константа, C от матрицы агента — пример)."""
    o = ["# Синтез 6 систем — инфографика (демо)"]
    o.append("Графики синтеза рисуют не «согласие как данные», а **эпистемику**: кто кому родственник, "
             "у кого какой вес, и где совпадение РЕАЛЬНОЕ, а где — эхо одного корня.\n")
    o.append("## Кто independent: карта независимости")
    o.append(_block(synthesis_independence_svg()))
    o.append("*Как читать:* 6 систем — это ~4 независимых языка. **ДЧ и Генные Ключи — один голос** (ГК выведены "
             "из ворот ДЧ), **Ба Цзы и Джунгци** делят знак года. Совпадение ВНУТРИ пары — тавтология, не "
             "подтверждение. Доказательством может быть только совпадение МЕЖДУ языками. [факт] о системах.\n")
    o.append("## Сколько весит каждая: богатство · эпоха · уверенность")
    o.append(_block(synthesis_weight_svg()))
    o.append("*Как читать:* длина = сколько факторов система реально дала в этом движке. Ба Цзы говорит десятками "
             "факторов, Матрица — двумя. Это НЕ «насколько правда», а «сколько сказала» — чтобы не давать Джунгци "
             "(3 штриха) тот же вес, что Ба Цзы. Эпоха и уверенность — рядом. [факт] о системах.\n")
    matrix = {
        "clusters": ["ДЧ · ГК", "Ба Цзы · Джунгци", "Джйотиш", "Матрица"],
        "themes": ["Характер", "Отношения", "Деньги", "Призвание", "2026"],
        "cells": {
            "Характер": ["Проектор — ведёт, ждёт", "сильный Металл, структура", "Козерог — дисциплина", "Колесо+Император"],
            "Отношения": ["ждать эмоц. ясности", "нужна Вода — гибкость", "Венера-период — фокус", "Иерофант — ценности"],
            "Деньги": ["—", "через усилие (Дерево слабо)", "Юпитер-период — рост", "—"],
            "Призвание": ["Проектор-гид", "власть/структура", "Юпитер — учитель", "Отшельник — мудрость"],
            "2026": ["— (не про годы)", "Семь Убийств — на прочность", "Венера — связи/комфорт", "— (не про годы)"],
        },
        "resonance": {"Характер": "↔ структура", "Призвание": "↔ наставник", "2026": "⚡ конфликт"},
    }
    o.append("## Где совпадает по-настоящему: резонанс по темам")
    o.append(_block(synthesis_resonance_svg(matrix)))
    o.append("*Как читать:* колонки — 4 независимых языка (ДЧ·ГК уже свёрнуты в один — нельзя нарисовать «6 за»). "
             "Резонанс (↔) зажигается только когда сходятся РАЗНЫЕ языки: структура (Ба Цзы+Джйотиш+Матрица), "
             "наставничество (ДЧ+Джйотиш+Матрица). На **2026 — честный конфликт**: Ба Цзы про напряжение, Джйотиш "
             "про мягкость, а ДЧ и Матрица вообще не про годы (молчат). Пример иллюстративный — "
             "**[интерпретация агента]**, в бою матрицу заполняет агент-сравнитель.\n")
    return "\n".join(o)


# ════════════════════════════════════════════════════════════════════════════
#  СОВМЕСТИМОСТЬ (вход — compat.json). Честность: НЕ единый %, НЕ вердикт.
#  Показываем СТРУКТУРУ — где традиции сошлись, где спорят, кто кого тянет.
#  Расхождение и неопределённость (хрупкость времени) — первоклассные элементы.
# ════════════════════════════════════════════════════════════════════════════
_SYS_COL = {"Ба Цзы": "#b8860b", "Джйотиш": "#5b6abf", "Дизайн Человека": "#2e8b8b"}
_V_FILL = {"+": "#2e7d32", "-": "#c62828", "~": "#c9a227", "·": "#e2e2e2"}   # легче/труднее/средне/молчит
_V_WORD = {"+": "легче", "-": "труднее", "~": "средне", "·": ""}


def _frac_v(score, mx, hi, lo):
    """Балл/макс → '+' легче / '-' труднее / '~' середина."""
    if not mx:
        return "~"
    f = score / mx
    return "+" if f >= hi else "-" if f <= lo else "~"


def _agg_v(vs):
    """Свод нескольких вердиктов ячейки: все+ →+, все− →−, есть и то и то →~, пусто →·."""
    vs = [v for v in vs if v]
    if not vs:
        return "·"
    if all(v == "+" for v in vs):
        return "+"
    if all(v == "-" for v in vs):
        return "-"
    return "~"


def _strip_cjk(t):
    """Убрать CJK из подписи ДЛЯ SVG (иероглифы Chrome рендерит нестабильно — правило проекта).
    Данные compat.json несут термины вроде «Дворец супруга (日支)» → станет «Дворец супруга»."""
    t = _CJK_RE.sub("", str(t))
    t = re.sub(r"\(\s*\)", "", t)            # пустые скобки после выкидывания иероглифа
    return re.sub(r"\s{2,}", " ", t).strip()


# Жаргон тем из compat.json → простой язык для подписей графиков (как переводит проза синтеза).
# Валентность (легче/труднее) несёт КОЛОНКА, поэтому ярлыки НЕЙТРАЛЬНЫ. Незнакомое — через _strip_cjk.
_PLAIN_TOPIC = {
    "Стволы дня": "склад характеров",
    "Ветви дня (дворцы)": "комфорт быть рядом",
    "Комплементарность стихий": "дополняете ли друг друга",
    "Звезда супруга": "образ партнёра внутри",
    "Дворец супруга (日支)": "какого партнёра ищешь",
    "Дворец супруга": "какого партнёра ищешь",
    "духовная/рабочая совместимость": "ценности и дело",
    "взаимное влияние и притяжение": "притяжение",
    "ментальная дружба и взаимопонимание": "понимание, общий язык",
    "телесная и интимная близость": "телесная близость",
    "эмоциональная и бытовая гармония": "быт и эмоции",
    "здоровье и потомство (традиционно)": "здоровье и дети (традиция)",
    "темперамент и характер": "темперамент",
    "благополучие и здоровье": "удача, благополучие",
    "притяжение (искра)": "искра, тяга",
    "похожесть/лёгкость": "похожи, легко рядом",
    "один тянет (компромисс)": "один подстраивается",
    "один перекрашивает другого": "один меняет другого под себя",
    "Марс (напор/конфликтность)": "напор, вспыльчивость",
}


def _svyaz(n):
    """Склонение «связь» под число (для подписей потока): 1 связь, 2–4 связи, 5+ связей."""
    n10, n100 = n % 10, n % 100
    if n10 == 1 and n100 != 11:
        return f"{n} связь"
    if 2 <= n10 <= 4 and not 12 <= n100 <= 14:
        return f"{n} связи"
    return f"{n} связей"


# домен → (критерии Ба Цзы, куты Джйотиш, корзины ДЧ). Кросс-системные строки идут первыми.
_COMPAT_DOMAINS = [
    ("Притяжение, искра",      ["Ветви дня (дворцы)", "Дворец супруга (日支)"], ["Вашья"],       ["electromagnetic", "companionship"]),
    ("Кто ведёт",              ["Стволы дня"],                                  [],               ["compromise", "dominance"]),
    ("Ум, общение",            [],                                              ["Граха-Майтри"], []),
    ("Ценности, дух и работа", [],                                              ["Варна"],        []),
    ("Темперамент",            [],                                              ["Гана"],         []),
    ("Тело, близость",         [],                                              ["Йони"],         []),
    ("Быт, эмоции",            [],                                              ["Бхакут"],       []),
    ("Благополучие, здоровье", [],                                              ["Тара", "Нади"], []),
    ("Дополняете друг друга",  ["Комплементарность стихий", "Звезда супруга"],  [],               []),
]


def _compat_cells(d):
    """(домен, система) → '+/-/~/·' детерминированно из compat.json. + флаг хрупкости джйотиш-ячейки."""
    bz = {c["name"]: c for c in d.get("bazi", {}).get("criteria", [])}
    ky = {k["name"]: k for k in d.get("jyotish", {}).get("kutas", [])}
    canc = d.get("jyotish", {}).get("dosha_cancellations", {})
    hd = d.get("human_design", {})
    hd_has = {b: bool(hd.get(b)) for b in ("electromagnetic", "companionship", "compromise", "dominance")}
    frag = set()
    for item in (d.get("jyotish", {}).get("time_fragility") or {}).get("A") or []:
        frag |= set(item.get("kutas_at_risk") or [])

    def bazi_v(name):
        c = bz.get(name)
        return _frac_v(c["score"], c["max"], 0.75, 0.25) if c else None

    def jy_v(name):
        k = ky.get(name)
        if not k:
            return None
        if name in ("Нади", "Бхакут") and k["score"] == 0:
            cancelled = canc.get("nadi") if name == "Нади" else canc.get("bhakut")
            return "~" if cancelled else "-"     # погашено → нейтрально, не «труднее»
        return _frac_v(k["score"], k["max"], 0.66, 0.34)

    def hd_v(buckets):
        present = [b for b in buckets if hd_has.get(b)]
        if not present:
            return None
        return _agg_v(["+" if b in ("electromagnetic", "companionship") else "-" for b in present])

    rows = []
    for label, bnames, jnames, hbuckets in _COMPAT_DOMAINS:
        bv = _agg_v([bazi_v(n) for n in bnames]) if bnames else "·"
        jv = _agg_v([jy_v(n) for n in jnames]) if jnames else "·"
        hv = (hd_v(hbuckets) or "·") if hbuckets else "·"
        rows.append((label, bv, jv, hv, any(n in frag for n in jnames)))
    return rows


def compat_matrix_svg(d):
    """Матрица сходимости: домены × 3 системы. Строка одного цвета = языки согласны; пёстрая = спорят."""
    rows = _compat_cells(d)
    cols = ["Ба Цзы", "Джйотиш", "Дизайн Человека"]
    W, left, top, rowh, colw = 664, 196, 96, 31, 150
    H = top + len(rows) * rowh + 28
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Матрица сходимости трёх систем">']
    p.append(f'<text x="14" y="24" font-size="15" font-weight="700" fill="#1a1a1a">Где традиции сошлись, где спорят</text>')
    p.append(f'<text x="14" y="42" font-size="10" fill="#666">строка одного цвета = языки согласны · пёстрая = спорят · пусто = система об этом молчит</text>')
    bx1, bx2 = left + 4, left + 2 * colw - 4
    p.append(f'<path d="M{bx1} {top-16} L{bx1} {top-24} L{bx2} {top-24} L{bx2} {top-16}" fill="none" stroke="#aaa" stroke-width="1"/>')
    p.append(f'<text x="{(bx1+bx2)/2:.0f}" y="{top-28}" font-size="8.5" text-anchor="middle" fill="#999">общий корень → их согласие менее независимо</text>')
    for j, cn in enumerate(cols):
        cx = left + j * colw + (colw - 8) / 2
        p.append(f'<text x="{cx:.0f}" y="{top-6}" font-size="10.5" text-anchor="middle" fill="{_SYS_COL[cn]}" font-weight="700">{_esc(cn)}</text>')
    y = top
    for label, bv, jv, hv, jfrag in rows:
        p.append(_syn_tspans(_syn_wrap(label, 24), 14, y + rowh / 2, 11, 9.5, "#1a1a1a", anchor="start", weight="600"))
        for j, v in enumerate((bv, jv, hv)):
            cx, cy = left + j * colw, y + 3
            op = 0.9 if v in "+-" else 0.55 if v == "~" else 0.3
            p.append(f'<rect x="{cx}" y="{cy}" width="{colw-8}" height="{rowh-8}" rx="5" '
                     f'fill="{_V_FILL[v]}" fill-opacity="{op}" stroke="#fff" stroke-width="1.5"/>')
            tcol = "#fff" if v in "+-" else "#6b6b6b"
            p.append(f'<text x="{cx+(colw-8)/2:.0f}" y="{cy+(rowh-8)/2+3:.0f}" font-size="9" '
                     f'text-anchor="middle" fill="{tcol}" font-weight="700">{_V_WORD[v]}</text>')
            if j == 1 and jfrag and v != "·":
                p.append(f'<text x="{cx+colw-18:.0f}" y="{cy+12}" font-size="11" text-anchor="middle" fill="#fff" font-weight="700">?</text>')
        y += rowh
    p.append(f'<text x="14" y="{H-9}" font-size="8.5" fill="#999">«?» у джйотиша — плывёт при неточном времени A · это карта тем, НЕ счёт и НЕ вердикт</text>')
    p.append('</svg>')
    return "\n".join(p)


def _flow_arrows(d):
    """Направленные сигналы → [(src, tgt, label, color)]. Из dir (Ба Цзы) и who (ДЧ)."""
    bz = {c["name"]: c for c in d.get("bazi", {}).get("criteria", [])}
    hd = d.get("human_design", {})
    out = []
    c1 = bz.get("Стволы дня", {})
    if c1.get("dir") in ("A→B", "B→A"):
        src, tgt = c1["dir"].split("→")
        ctrl = "контроль" in c1.get("detail", "")
        out.append((src, tgt, "характер сильнее, задаёт тон" if ctrl else "подпитывает энергией",
                    "#c62828" if ctrl else "#2e7d32"))
    c3 = bz.get("Комплементарность стихий", {})
    if c3.get("dir") in ("A→B", "B→A"):
        src, tgt = c3["dir"].split("→")
        out.append((src, tgt, "восполняет нехватку", "#2e7d32"))
    a_lead = b_lead = 0
    for ch in (hd.get("compromise") or []) + (hd.get("dominance") or []):
        who = ch.get("who", "")
        if who.startswith("A"):
            a_lead += 1
        elif who.startswith("B"):
            b_lead += 1
    if a_lead:
        out.append(("A", "B", f"A чаще ведёт — {_svyaz(a_lead)}", "#c9a227"))
    if b_lead:
        out.append(("B", "A", f"B чаще ведёт — {_svyaz(b_lead)}", "#c9a227"))
    return out


def compat_flow_svg(d):
    """Поток A↔B: кто кого тянет/питает. Направление, НЕ оценка («в этих слоях, не приговор»)."""
    arrows = _flow_arrows(d)
    W = 664
    ax, bx, R = 64, W - 64, 26
    y0 = 92
    H = y0 + max(1, len(arrows)) * 36 + 14
    midy = (y0 + H - 14) / 2
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Поток влияния A и B">']
    p.append(f'<text x="14" y="24" font-size="15" font-weight="700" fill="#1a1a1a">Кто кого тянет и питает</text>')
    p.append(f'<text x="14" y="42" font-size="10" fill="#666">стрелка от того, кто задаёт/даёт, к тому, кто принимает · направление, НЕ оценка · в этих слоях, не приговор</text>')
    for cx, lab, col in ((ax, "A", "#8a4b08"), (bx, "B", "#0d5c5c")):
        p.append(f'<circle cx="{cx}" cy="{midy:.0f}" r="{R}" fill="#fff" stroke="{col}" stroke-width="2"/>')
        p.append(f'<text x="{cx}" y="{midy+5:.0f}" font-size="15" text-anchor="middle" fill="{col}" font-weight="700">{lab}</text>')
    if not arrows:
        p.append(f'<text x="{W/2:.0f}" y="{midy:.0f}" font-size="11" text-anchor="middle" fill="#999">направленных сигналов нет — связь симметрична</text>')
    for i, (src, tgt, label, col) in enumerate(arrows):
        y = y0 + 18 + i * 36
        if src == "A":
            x1, x2, head = ax + R + 4, bx - R - 4, "►"
            hx = [(x2, y), (x2 - 9, y - 5), (x2 - 9, y + 5)]
        else:
            x1, x2, head = bx - R - 4, ax + R + 4, "◄"
            hx = [(x2, y), (x2 + 9, y - 5), (x2 + 9, y + 5)]
        p.append(f'<line x1="{x1:.0f}" y1="{y}" x2="{x2:.0f}" y2="{y}" stroke="{col}" stroke-width="2"/>')
        pts = " ".join(f"{px:.0f},{py}" for px, py in hx)
        p.append(f'<polygon points="{pts}" fill="{col}"/>')
        p.append(f'<text x="{(x1+x2)/2:.0f}" y="{y-6}" font-size="9.5" text-anchor="middle" fill="{col}" font-weight="600">{_esc(label)}</text>')
    p.append('</svg>')
    return "\n".join(p)


def _group_ef(items):
    """Свернуть ease/friction по (система, тема) с подсчётом, сохраняя порядок появления."""
    order, seen = [], {}
    for it in items:
        key = (it.get("system", ""), it.get("topic", ""))
        if key in seen:
            seen[key]["n"] += 1
        else:
            seen[key] = {"system": key[0], "topic": key[1], "n": 1}
            order.append(seen[key])
    return order


def compat_landscape_svg(d):
    """Ландшафт: слева «труднее» (красным), справа «легче» (зелёным), цвет точки = система. Карта, НЕ счёт."""
    ef = d.get("ease_friction", {})
    fr = _group_ef(ef.get("friction", []))
    ease = _group_ef(ef.get("ease", []))
    W, top, rowh = 664, 92, 26
    n = max(len(fr), len(ease), 1)
    H = top + n * rowh + 26
    colL, colR, cw = 14, W / 2 + 8, W / 2 - 22
    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Helvetica,Arial,sans-serif" role="img" aria-label="Ландшафт легче и труднее">']
    p.append(f'<text x="14" y="24" font-size="15" font-weight="700" fill="#1a1a1a">Где легче, где труднее</text>')
    p.append(f'<text x="14" y="42" font-size="10" fill="#666">карта тем, НЕ счёт · цвет точки = какая система говорит · числа систем не складываются</text>')
    p.append(f'<rect x="{colL}" y="{top-22}" width="{cw}" height="20" rx="5" fill="#c62828" fill-opacity="0.12"/>')
    p.append(f'<text x="{colL+10}" y="{top-8}" font-size="11" fill="#c62828" font-weight="700">ТРУДНЕЕ</text>')
    p.append(f'<rect x="{colR}" y="{top-22}" width="{cw}" height="20" rx="5" fill="#2e7d32" fill-opacity="0.12"/>')
    p.append(f'<text x="{colR+10}" y="{top-8}" font-size="11" fill="#2e7d32" font-weight="700">ЛЕГЧЕ</text>')

    def col(items, x0):
        for i, it in enumerate(items):
            y = top + i * rowh + rowh / 2
            dot = _SYS_COL.get(it["system"], "#999")
            p.append(f'<circle cx="{x0+8}" cy="{y:.0f}" r="4.5" fill="{dot}"/>')
            tag = f' ×{it["n"]}' if it["n"] > 1 else ""
            label = _PLAIN_TOPIC.get(it["topic"], _strip_cjk(it["topic"]))
            txt = _syn_wrap(label + tag, int((cw - 24) / 5.6))
            p.append(_syn_tspans(txt[:1], x0 + 20, y, 11, 10, "#2a2a2a", anchor="start"))
    col(fr, colL)
    col(ease, colR)
    p.append(f'<line x1="{W/2:.0f}" y1="{top-2}" x2="{W/2:.0f}" y2="{H-22}" stroke="#eee" stroke-width="1"/>')
    p.append(f'<text x="14" y="{H-8}" font-size="8.5" fill="#999">'
             f'жёлтая точка — Ба Цзы, синяя — Джйотиш, зелёная — Дизайн Человека · повтор темы свёрнут в «×N»</text>')
    p.append('</svg>')
    return "\n".join(p)


# ── ПРОДУКТОВЫЙ набор (Tier A + упрочнённый B; Tier C — shensha/nayin/activations — НЕ тут) ──
PRODUCT_CHARTS = {
    "bazi": [
        ("four_pillars_svg", "Твоя карта: 4 столпа; столбец Дня обведён — это ты."),
        ("five_elements_svg", "Баланс стихий: зелёным — что усилить, красным — убрать."),
        ("wuxing_cycle_svg", "Кто кого кормит (生) и держит (克); размер = вес стихии."),
        ("strength_gauge_svg", "Насколько ты «наполнен» (сильный ≠ хорошо)."),
        ("ten_gods_svg", "Какие роли в тебе преобладают."),
        ("tiaohou_svg", "Что карту согревает по сезону (вспомогательный слой)."),
        ("interactions_svg", "Натяжения между ветвями карты (сигнал, не вердикт)."),
        ("dynamic_interactions_svg", "Что активируют год и удача прямо сейчас."),
        ("luck_timeline_svg", "Где ты сейчас в десятилетних периодах (大运)."),
        ("annual_year_svg", "Что приносит {year} (流年)."),  # {year} → current_year.year из JSON (не литерал)
        ("fragility_svg", "Где карта чувствительна к точности времени."),
    ],
    "hd": [
        ("bodygraph_svg", "Бодиграф: закрашены — определённые центры. Если есть пунктир «?» — карта node-чувствительна: сплошное = канон (истинный узел, офиц.), пунктир = стороннее усреднённое."),
        ("fragility_hd_svg", "Что «поплывёт» первым при неточном времени."),
    ],
    "jyotish": [
        ("rashi_chart_svg", "Карта раши D-1: планеты по знакам, дома от Лагны."),
        ("dasha_timeline_svg", "Большие периоды жизни (маха-даши Вимшоттари)."),
    ],
    "matrix": [
        ("matrix_diamond_svg", "Ядро Матрицы: 5 главных арканов (полная октаграмма НЕ считается)."),
    ],
    "tibetan": [
        ("mewa_square_svg", "Твоя Меуа в квадрате 9 дворцов (Ло Шу)."),
        ("forces_svg", "Пять сил (2 из них честно не выданы)."),
    ],
    "gene_keys": [
        ("spectrum_svg", "Главные Дары: путь Тень → Дар → Сиддхи."),
        ("spheres_overview_svg", "11 сфер Голограммы по 3 путям."),
    ],
    "synthesis": [
        # Синтез БЕЗ графиков (запрос пользователя 2026-06-27): резонанс/независимость/вес НЕ идут в продукт.
        # product_section("synthesis", …) вернёт "" — «## Графики к чтению» к 7_synthesis.md не добавляется.
    ],
    "compat": [   # вход — compat.json (НЕ карта одного человека). НЕ единый %, НЕ вердикт.
        ("compat_matrix_svg", "Где три традиции сошлись (строка одного цвета), а где спорят (пёстрая); пусто — система молчит."),
        ("compat_flow_svg", "Кто кого тянет/питает — направление, не оценка («в этих слоях, не приговор»)."),
        ("compat_landscape_svg", "Карта тем «легче / труднее» по системам (НЕ счёт; числа систем не складываются)."),
    ],
}


def product_section(system, d):
    """Готовая markdown-секция Tier A/B графиков системы — для вставки в чтение профиля /profile3 (текст-первичный)."""
    charts = PRODUCT_CHARTS.get(system, [])
    if not charts:
        return ""
    cy = (d.get("current_year") or {}).get("year", "")
    out = ["", "## Графики к чтению", ""]
    for fn_name, cap in charts:
        out.append(_block(globals()[fn_name](d)))
        out.append(f"*{cap.format(year=cy) if '{year}' in cap else cap}*")
        out.append("")
    out.append("_Иллюстрации к чтению — не доказательство; текст выше первичен. "
               "Где чтение зависит от конвенции — график это показывает._")
    return "\n".join(out)


def _block(svg):
    return "```svg\n" + svg + "\n```"


def demo_md(d):
    """Демо-срез 1_bazi.md: 5 графиков в дуге, с подписями-выводами (как их пишет агент)."""
    eb = d["element_balance"]
    dom = max(eb, key=lambda e: eb[e]["percent"]); weak = min(eb, key=lambda e: eb[e]["percent"])
    dm = d["day_master"]["element"]; st = d["strength"]
    yong = [x["element"] for x in d.get("yongshen", [])]
    ji = [x["element"] for x in d.get("jishen", [])]
    lp = d["luck_pillars"]["pillars"]
    age = _current_age(d)
    ci = _current_pillar_index(lp, age); cur = lp[ci] if ci is not None else None
    o = []
    o.append("# Ба Цзы — инфографика (демо)")
    o.append(f"Хозяин Дня — **{dm}** ({d['day_master']['name']}), сила **{st['label']}** ({st['score']}). "
             "Ниже — натальная карта и пять разрезов простым языком.\n")

    o.append("## Твоя карта: Четыре Столпа (四柱)")
    o.append(_block(four_pillars_svg(d)))
    names = " · ".join(d["pillars"][k]["name"] for k in PILLAR_ORDER)
    o.append(f"Столпы (Час · День · Месяц · Год): **{names}**.")
    o.append("*Как читать:* четыре пары «ствол + ветвь». Верх ячейки — стихия небесного ствола (+ ян/инь), "
             "низ — земная ветвь (животное и её стихия). Столбец Дня обведён — его верхняя стихия и есть **ты** "
             "(Хозяин Дня). Внизу — «скрытые» энергии ветви (десятибоги). [факт] — всё рассчитано.\n")

    o.append("## Как ветви карты тянут друг друга (冲合刑害)")
    o.append(_block(interactions_svg(d)))
    inter = d.get("interactions", [])
    o.append("*Как читать:* дуги между столпами — где ветви в союзе / ударе / наказании / вреде. "
             + ("Здесь: " + "; ".join(inter) + ". " if inter
                else "Здесь крупных взаимодействий нет (карта без сильных внутренних натяжений). ")
             + "[факт] — из калькулятора.\n")

    o.append("## Особые звёзды и пустота (神煞 · 空亡)")
    o.append(_block(shensha_svg(d)))
    o.append("*Как читать:* приметы на ветвях. 驿马 (Конь) — путь и переезды; 华盖 (Балдахин) — уединение, "
             "творчество, эзотерика; 天喜 / 红鸾 — любовь и брак; «пусто» (空亡) — ветвь «полая», её темы "
             "даются труднее или позже. [факт] — звёзды из калькулятора; [интерпретация] — их смысл.\n")

    o.append("## Звучащая стихия столпов (纳音)")
    o.append(_block(nayin_svg(d)))
    ny = " · ".join(f"{d['pillars'][k]['name']} {d['pillars'][k].get('nayin','?')}" for k in PILLAR_ORDER)
    o.append("*Как читать:* у каждого столпа есть третья, «звучащая» стихия (纳音) — поверх ствола и ветви. "
             f"Здесь: {ny}. Слой архаичный (чаще в 合婚/совместимости), маркируем как [справочно].\n")

    o.append("## Насколько карта чувствительна к точности времени")
    o.append(_block(fragility_svg(d)))
    bw = d.get("boundary_warnings", [])
    o.append("*Как читать:* зелёный — столп устойчив; жёлтый/красный — «поплывёт» при неточном времени рождения. "
             + ("; ".join(w["detail"] for w in bw) + ". " if bw else "Здесь все столпы устойчивы. ")
             + "[факт] — окна из калькулятора.\n")

    o.append("## Из чего ты состоишь — и что с этим делать: пять стихий (五行)")
    o.append(_block(five_elements_svg(d)))
    cap = f"**{dom}** доминирует ({eb[dom]['percent']:.1f}%), **{weak}** в дефиците ({eb[weak]['percent']:.1f}%). "
    if dom in ji and weak in yong:
        cap += (f"Соль: избыток — это **{dom}** (忌神, во вред), а нехватка — **{weak}** (用神, нужна) — "
                "перекос раскармливает и без того сильного Хозяина Дня. ")
    cap += (f"Зелёным — что усилить (用神: {', '.join(yong)}), красным — что убавить (忌神: {', '.join(ji)}). "
            "[факт] — высоты и 用神/忌神 из калькулятора; [интерпретация] — вывод про перекос.")
    o.append("*Как читать:* " + cap + "\n")

    o.append("## Кто кого кормит и держит: колесо стихий (五行 生克)")
    o.append(_block(wuxing_cycle_svg(d)))
    o.append("*Как читать:* сплошные стрелки — «кормит» (生), пунктир — «держит/контролирует» (克); размер "
             "кружка = вес стихии. Видно живьём: большая Земля (忌神, красная обводка) кормит твой Металл "
             "(ХД, чёрная) — оттого он и силён; тонкие Вода и Дерево (用神, зелёные) — то, что стоит подпитывать. "
             "[факт] — связи и веса; [интерпретация] — вывод.\n")

    o.append("## Что карту согревает: климат (调候)")
    o.append(_block(tiaohou_svg(d)))
    th = d.get("tiaohou")
    if th:
        o.append(f"*Как читать:* по сезону рождения карте для тепла/роста нужны "
                 f"**{th['primary']['element']}** (главный) и **{th['auxiliary']['element']}** (вспомогательный). "
                 + ("И это совпадает с тем, что и так полезно (用神) — климат и сила заодно. "
                    if th.get("aligns_with_yongshen")
                    else "Но это расходится с 用神 — климат и сила тянут в разные стороны. ")
                 + "[факт] — из калькулятора; [интерпретация] — смысл.\n")
    else:
        o.append("*Как читать:* данных 调候 по этой карте нет.\n")

    o.append("## Насколько ты «наполнен»: сила Хозяина Дня")
    o.append(_block(strength_gauge_svg(d)))
    o.append(f"*Как читать:* стрелка — твой балл ({st['score']}). **{st['label']}** значит не «лучше», а «много себя»: "
             f"карту разряжают через {', '.join(yong)}, а не подпитывают. [факт] — балл; [интерпретация] — что делать.\n")

    o.append("## Какие роли в тебе сильнее: Десять Богов (十神)")
    o.append(_block(ten_gods_svg(d)))
    roles = ", ".join(f"{ru} ({cjk})" for _r, ru, cjk, _s in ROLE_SEQ)
    o.append(f"Роли и их 十神: {roles}.")
    o.append("*Как читать:* десять «богов» сведены в 5 ролей; длина — вес роли в карте, цвет — её стихия для тебя. "
             "Видно, какая тема (ресурс / самовыражение / деньги / власть / соратники) перевешивает. "
             "[факт] — веса из калькулятора; [интерпретация] — название темы.\n")

    o.append("## Где ты сейчас по жизни: Большие Удачи (大运)")
    o.append(_block(luck_timeline_svg(d)))
    tail = ""
    if cur:
        tail = (f"Сейчас тебе ~{age} — десятилетие **{cur['name']}** ({round(cur['age_start'])}–{round(cur['age_end'])}): "
                f"{cur['stem']['element']} над {cur['branch']['element']}, {cur['ten_god_ru']}. ")
    o.append("*Как читать:* каждая клетка — 10 лет; верхняя полоска = стихия столпа. " + tail
             + "[факт] — столпы и возраст; [интерпретация] — что это значит.\n")

    o.append(f"## А конкретно {cy} (流年)")
    o.append(_block(annual_year_svg(d)))
    cyx = d["current_year"]; cyse = cyx["stem"]["element"]
    o.append(f"*Как читать:* {cyx['year']} — столп **{cyx['pillar']}**, роль **{cyx['ten_god_ru']}**. "
             + ("Год **бьёт (冲)** по одной из ветвей карты — проверка на прочность. " if cyx.get("clashes_natal")
                else "Удара (冲) года по ветвям карты нет. ")
             + f"Стихия года {cyse} — " + ("полезна тебе. " if cyse in yong
                                           else "во вред. " if cyse in ji else "нейтральна. ")
             + "[факт] — столп и роль; [интерпретация] — тон года.\n")

    o.append("## Что активируется сейчас: год и удача × карта (大运 / 流年)")
    o.append(_block(dynamic_interactions_svg(d)))
    dyn = d.get("dynamic_interactions") or {}
    hits = (dyn.get("year", {}).get("vs_natal", []) + ((dyn.get("luck") or {}).get("vs_natal", []))
            + dyn.get("year_vs_luck", []))
    o.append(f"*Как читать:* стрелки — как ветвь {cy} (流年) и текущего столпа удачи (大运) бьют/связывают "
             "натальные ветви. "
             + ("Сейчас: " + "; ".join(hits) + ". " if hits else "Сейчас прямых задеваний нет. ")
             + "[факт] — взаимодействия из калькулятора (冲合刑害 / 三合); [интерпретация] — что это для тебя.\n")
    return "\n".join(o)


def _test():
    """Golden-самопроверка на встроенной фикстуре (структура реального bazi.json)."""
    def _pil(name, sru, sel, spol, bname, bel, ban, hid, tg):
        return {"name": name, "ten_god_ru": tg, "nayin_element": sel,
                "stem": {"name": sru, "element": sel, "polarity": spol},
                "branch": {"name": bname, "element": bel, "animal": ban,
                           "hidden_stems": [{"element": e, "ten_god_ru": t} for e, t in hid]}}
    fx = {
        "input": {"date": "1990-03-03"},
        "day_master": {"name": "庚", "element": "Металл", "element_index": 3},
        "strength": {"score": 64, "label": "СИЛЬНЫЙ", "support_share": 0.638},
        "element_balance": {
            "Дерево": {"percent": 8.75}, "Огонь": {"percent": 11.25},
            "Земля": {"percent": 47.5}, "Металл": {"percent": 16.25},
            "Вода": {"percent": 16.25}},
        "yongshen": [{"element": "Вода"}, {"element": "Дерево"}],
        "jishen": [{"element": "Металл"}, {"element": "Земля"}],
        "tiaohou": {"primary": {"element": "Дерево"}, "auxiliary": {"element": "Огонь"}, "aligns_with_yongshen": True},
        "boundary_warnings": [{"pillar": "hour", "severity": "medium", "detail": "13 мин до границы 时辰"}],
        "dynamic_interactions": {"as_of_year": 2026, "age": 37,
            "year": {"branch": "午", "pillar": "丙午", "vs_natal": ["冲 午-子 (流年-День)"]},
            "luck": {"branch": "子", "pillar": "甲子", "age_start": 31.69, "age_end": 41.69, "vs_natal": []},
            "year_vs_luck": ["冲 午-子 (流年-大运)"]},
        "ten_gods": [{"name": "偏印", "weight": 3.5}, {"name": "七杀", "weight": 1.0},
                     {"name": "伤官", "weight": 1.0}, {"name": "正印", "weight": 1},
                     {"name": "偏财", "weight": 0.5}, {"name": "正财", "weight": 0.5},
                     {"name": "比肩", "weight": 0.5}],
        "pillars": {
            "hour": _pil("戊寅", "戊", "Земля", "yang", "寅", "Дерево", "Тигр",
                         [("Дерево", "Косвенное Богатство"), ("Огонь", "Семь Убийств")], "Косвенная Печать"),
            "day": _pil("庚子", "庚", "Металл", "yang", "子", "Вода", "Крыса",
                        [("Вода", "Ранящий Чиновник")], "Друг"),
            "month": _pil("戊辰", "戊", "Земля", "yang", "辰", "Земля", "Дракон", [], "Косвенная Печать"),
            "year": _pil("己巳", "己", "Земля", "yin", "巳", "Огонь", "Змея", [], "Прямая Печать"),
        },
        "current_year": {"year": 2026, "pillar": "丙午", "ten_god_ru": "Семь Убийств", "clashes_natal": True,
                         "stem": {"element": "Огонь"}, "branch": {"animal": "Лошадь", "element": "Огонь"}},
        "interactions": ["刑 寅-巳 (Час-Год)"],
        "shensha": [{"name": "驿马", "branch": "寅", "name_ru": "Странствующий Конь"},
                    {"name": "华盖", "branch": "辰", "name_ru": "Балдахин"}],
        "kong_wang_active": [{"name": "辰"}, {"name": "巳"}],
        "hongluan": {"name": "戌"}, "tianxi": {"name": "辰"},
        "luck_pillars": {"pillars": [
            {"age_start": 1.69, "age_end": 11.69, "name": "丁卯",
             "stem": {"element": "Огонь"}, "branch": {"element": "Дерево"}, "ten_god_ru": "Прямой Чиновник"},
            {"age_start": 31.69, "age_end": 41.69, "name": "甲子",
             "stem": {"element": "Дерево"}, "branch": {"element": "Вода", "animal": "Крыса"}, "ten_god_ru": "Косвенное Богатство"},
        ]},
    }
    errs = []
    # 1. проценты суммируются ~100
    s = sum(v["percent"] for v in fx["element_balance"].values())
    if abs(s - 100) > 0.5:
        errs.append(f"сумма процентов {s} != 100")
    # 2. все 13 генераторов: валидная обёртка, без NaN/None, без иероглифов в SVG
    for fn in (five_elements_svg, luck_timeline_svg, four_pillars_svg, strength_gauge_svg, ten_gods_svg,
               interactions_svg, shensha_svg, annual_year_svg, wuxing_cycle_svg, tiaohou_svg,
               nayin_svg, fragility_svg, dynamic_interactions_svg):
        svg = fn(fx)
        if not svg.startswith("<svg") or not svg.rstrip().endswith("</svg>"):
            errs.append(f"{fn.__name__}: не обёрнут <svg>")
        if "NaN" in svg or ">None<" in svg or "None%" in svg:
            errs.append(f"{fn.__name__}: NaN/None в выводе")
        if _CJK_RE.search(svg):
            errs.append(f"{fn.__name__}: иероглиф внутри SVG (по правилу — только в HTML-подписях)")
    # 3. текущий столп найден однозначно (возраст 2026-1989=37 → 31.69..40.69 = индекс 1)
    if _current_pillar_index(fx["luck_pillars"]["pillars"], 2026 - 1989) != 1:
        errs.append("current pillar idx != 1")
    # 4. бар не вылезает за шкалу
    pmax = max(v["percent"] for v in fx["element_balance"].values())
    if pmax > max(50.0, math.ceil(pmax / 10) * 10):
        errs.append("бар > шкалы")
    # 5. каждый десятибог сопоставлен роли (иначе вес потеряется молча)
    unmapped = [g["name"] for g in fx["ten_gods"] if TG_ROLE.get(g["name"]) is None]
    if unmapped:
        errs.append(f"несопоставленные десятибоги: {unmapped}")
    # 6. строка взаимодействия распарсилась в дугу (тип связи → русская подпись)
    if "Наказание" not in interactions_svg(fx):
        errs.append("interactions: тип связи не распознан")
    # 7. Бодиграф ДЧ (вход — hd.json): валиден, без NaN/None/CJK
    hd_fx = {
        "type": "Проектор", "strategy": "Ждать приглашения (признания)", "authority": "Эмоциональный — Солн.спл.",
        "profile": "6/2", "profile_names": ["Ролевая модель", "Отшельник"], "definition": "Раздельное (сплит)",
        "defined_centers": ["Горло", "G-центр (Самость)", "Сердце (Эго)", "Солнечное сплетение", "Селезёнка"],
        "open_centers": ["Голова", "Аджна", "Сакрал", "Корень"],
        "defined_channels": [{"gates": "1-8", "name": "Вдохновение", "centers": "G-центр (Самость)↔Горло"},
                             {"gates": "37-40", "name": "Общность", "centers": "Солнечное сплетение↔Сердце (Эго)"}],
        "incarnation_cross": {"gates": [51, 57, 61, 62], "notation": "51/57 | 61/62", "angle": "Левосторонний крест"},
        "all_channels": [{"gates": "1-8", "name": "Вдохновение", "centers": "G-центр (Самость)↔Горло", "defined": True},
                         {"gates": "2-14", "name": "Бит", "centers": "G-центр (Самость)↔Сакрал", "defined": False}],
        "activations": {"personality": [{"body_ru": "Солнце", "gate": 51, "line": 6}],
                        "design": [{"body_ru": "Солнце", "gate": 57, "line": 6}]},
        "fragile_activations": [{"body": "Луна (Личн)", "gate_line": "35.2", "minutes": 16.1}],
        "convention_warnings": [{"text": "mean/true меняет авторитет"}],
    }
    for fn in (bodygraph_svg, activations_svg, fragility_hd_svg):
        svg = fn(hd_fx)
        if not svg.startswith("<svg") or "NaN" in svg or ">None<" in svg:
            errs.append(f"{fn.__name__}: битый вывод")
        if _CJK_RE.search(svg):
            errs.append(f"{fn.__name__}: иероглиф в SVG")
    # 8. Карта раши Джйотиш (вход — jyotish.json)
    jy_fx = {
        "lagna": {"rashi": "Козерог", "rashi_sanskrit": "Макара"},
        "moon_nakshatra": {"nakshatra": "Рохини", "pada": 3},
        "grahas": [{"graha": "Луна (Чандра)", "rashi": "Телец", "house": 5},
                   {"graha": "Сатурн (Шани)", "rashi": "Стрелец", "house": 12}],
        "house_lords": [{"house": 1, "rashi": "Козерог"}, {"house": 5, "rashi": "Телец"}, {"house": 12, "rashi": "Стрелец"}],
        "navamsa": {"lagna_rashi": "Водолей"},
        "maha_dasha": {"lord": "Юпитер", "from": "2017-03-27", "to": "2033-03-27"},
        "antar_dasha": {"lord": "Венера"},
        "dasha_as_of": "2026-06-23",
        "dasha_timeline": [{"lord": "Раху", "from": "1999-03-27", "to": "2017-03-27", "years": 18},
                           {"lord": "Юпитер", "from": "2017-03-27", "to": "2033-03-27", "years": 16}],
    }
    for fn in (rashi_chart_svg, dasha_timeline_svg):
        svg = fn(jy_fx)
        if not svg.startswith("<svg") or "NaN" in svg or ">None<" in svg:
            errs.append(f"{fn.__name__}: битый вывод")
        if _CJK_RE.search(svg):
            errs.append(f"{fn.__name__}: иероглиф в SVG")
    # 9. Ядро Матрицы Судьбы (вход — matrix.json)
    mx_fx = {"core_points": {
        "Личность (день)": {"arcana": 10, "name": "Колесо Фортуны"}, "Род/месяц": {"arcana": 4, "name": "Император"},
        "Год": {"arcana": 9, "name": "Отшельник"}, "Сумма": {"arcana": 5, "name": "Иерофант"},
        "Центр": {"arcana": 10, "name": "Колесо Фортуны"}}, "central_arcana": {"arcana": 10, "name": "Колесо Фортуны"}}
    mx = matrix_diamond_svg(mx_fx)
    if not mx.startswith("<svg") or "NaN" in mx or ">None<" in mx:
        errs.append("matrix_diamond_svg: битый вывод")
    if _CJK_RE.search(mx):
        errs.append("matrix_diamond_svg: иероглиф в SVG")
    # 10. Джунгци: квадрат Меуа + пять сил (вход — tibetan.json); 2 силы withheld (null element)
    tb_fx = {
        "mewa": {"number": 2, "color": "Чёрная", "element": "Вода"},
        "year_sign": {"full": "Земля Змея", "animal": "Змея"},
        "forces": {"Срог (жизненная сила)": {"element": "Огонь"}, "Ла (душа)": {"element": "Дерево"},
                   "Вангтанг (личная сила)": {"element": "Земля"},
                   "Лю (тело)": {"element": None, "withheld": "правило не выверено"},
                   "Лунгта (конь ветра)": {"element": None, "withheld": "таблица повреждена"}},
        "forces_year_relation": {"year": 2026, "relations": {
            "Срог (жизненная сила)": {"relation": "тождество", "reading": "год той же стихии — подкреплена"}}},
        "confidence": "СРЕДНЯЯ",
    }
    for fn in (mewa_square_svg, forces_svg):
        svg = fn(tb_fx)
        if not svg.startswith("<svg") or "NaN" in svg or ">None<" in svg:
            errs.append(f"{fn.__name__}: битый вывод")
        if _CJK_RE.search(svg):
            errs.append(f"{fn.__name__}: иероглиф в SVG")
    # 11. Генные Ключи: спектр Главных Даров + 11 сфер (вход — gene_keys.json)
    gk_fx = {
        "prime_gifts": [{"sphere": "Life's Work", "sphere_ru": "Жизненная работа (призвание)", "key_line": "51.6",
                         "shadow": "Agitation", "gift": "Initiative", "siddhi": "Awakening"}],
        "spheres": [{"sphere_ru": "Жизненная работа (призвание)", "sequence": "Активация", "gate": 51, "line": 6, "gift": "Initiative"},
                    {"sphere_ru": "Притяжение (отношения)", "sequence": "Венера", "gate": 22, "line": 6, "gift": "Graciousness"},
                    {"sphere_ru": "Жемчужина (процветание)", "sequence": "Жемчужина", "gate": 20, "line": 6, "gift": "Self-assurance"}],
        "spectrum_provenance": "англ. ярлыки 1-64 сверены (43-64 по genekeys.com 2026-07-01)",
    }
    for fn in (spectrum_svg, spheres_overview_svg):
        svg = fn(gk_fx)
        if not svg.startswith("<svg") or "NaN" in svg or ">None<" in svg:
            errs.append(f"{fn.__name__}: битый вывод")
        if _CJK_RE.search(svg):
            errs.append(f"{fn.__name__}: иероглиф в SVG")
    # 12. Синтез: карта независимости + вес (константы) + резонанс (матрица агента)
    syn_m = {"clusters": ["A", "B", "C"], "themes": ["X", "Y"],
             "cells": {"X": ["a", "b", "c"], "Y": ["d", "e"]}, "resonance": {"X": "↔ ок"}}
    for svg in (synthesis_independence_svg(), synthesis_weight_svg(), synthesis_resonance_svg(syn_m)):
        if not svg.startswith("<svg") or "NaN" in svg or ">None<" in svg:
            errs.append("synthesis_*: битый вывод")
        if _CJK_RE.search(svg):
            errs.append("synthesis_*: иероглиф в SVG")
    # 13. Совместимость: матрица сходимости + поток A↔B + ландшафт (вход — compat.json)
    cp_fx = {
        "bazi": {"criteria": [
            {"name": "Стволы дня", "score": 0.5, "max": 2, "detail": "контроль — A подавляет/правит B",
             "directional": True, "dir": "A→B"},
            {"name": "Ветви дня (дворцы)", "score": 1.5, "max": 2, "detail": "三合"},
            {"name": "Комплементарность стихий", "score": 1.0, "max": 2, "detail": "одностороннее (B→A)",
             "directional": True, "dir": "B→A"},
            {"name": "Звезда супруга", "score": 1.0, "max": 2, "detail": "...", "directional": True},
            {"name": "Дворец супруга (日支)", "score": 2.0, "max": 2, "detail": "оба благоприятны", "directional": True},
        ], "total": 6.0},
        "jyotish": {
            "kutas": [{"name": "Варна", "score": 1.0, "max": 1, "detail": "каста ок"},
                      {"name": "Вашья", "score": 2.0, "max": 2, "detail": "притяжение"},
                      {"name": "Тара", "score": 1.5, "max": 3, "detail": "средне"},
                      {"name": "Йони", "score": 0.0, "max": 4, "detail": "враждебные"},
                      {"name": "Граха-Майтри", "score": 5.0, "max": 5, "detail": "дружба умов"},
                      {"name": "Гана", "score": 5.0, "max": 6, "detail": "темперамент"},
                      {"name": "Бхакут", "score": 0.0, "max": 7, "detail": "доша"},
                      {"name": "Нади", "score": 0.0, "max": 8, "detail": "доша"}],
            "total_display": "14.5",
            "dosha_cancellations": {"nadi": None, "bhakut": None, "mangal_A": "падение", "mangal_B": "падение"},
            "mangal_signal": {"A_present": True, "A_cancel": "падение", "B_present": True, "B_cancel": "падение",
                              "note_verdict": "гасится"},
            "time_fragility": {"A": [{"boundary": "накшатра", "minutes_approx": 78,
                                      "kutas_at_risk": ["Тара", "Йони", "Гана", "Нади"]}], "B": None},
        },
        "human_design": {
            "electromagnetic": [{"channel": "10-34", "name": "Исследование"}, {"channel": "20-57", "name": "Мозговая волна"}],
            "companionship": [],
            "compromise": [{"channel": "4-63", "name": "Логика", "who": "B целиком, A половина"}],
            "dominance": [{"channel": "43-23", "name": "Суждение", "who": "A определяет, у B пусто"},
                          {"channel": "21-45", "name": "Сила", "who": "B определяет, у A пусто"}],
            "counts": {"electromagnetic": 2, "companionship": 0, "compromise": 1, "dominance": 2},
        },
        "ease_friction": {
            "ease": [{"system": "Дизайн Человека", "topic": "притяжение (искра)", "detail": "канал"},
                     {"system": "Дизайн Человека", "topic": "притяжение (искра)", "detail": "канал"},
                     {"system": "Ба Цзы", "topic": "Дворец супруга (日支)", "detail": "..."},  # CJK в теме → должен срезаться в SVG
                     {"system": "Джйотиш", "topic": "ментальная дружба", "detail": "..."}],
            "friction": [{"system": "Джйотиш", "topic": "телесная близость", "detail": "враждебные"},
                         {"system": "Джйотиш", "topic": "здоровье и потомство", "detail": "доша"}],
            "directional": [{"system": "Ба Цзы", "topic": "Стволы дня", "detail": "..."}],
        },
    }
    for fn in (compat_matrix_svg, compat_flow_svg, compat_landscape_svg):
        svg = fn(cp_fx)
        if not svg.startswith("<svg") or not svg.rstrip().endswith("</svg>"):
            errs.append(f"{fn.__name__}: не обёрнут <svg>")
        if "NaN" in svg or ">None<" in svg or "None%" in svg:
            errs.append(f"{fn.__name__}: NaN/None в выводе")
        if _CJK_RE.search(svg):
            errs.append(f"{fn.__name__}: иероглиф в SVG (по правилу — только в HTML-подписях)")
    cells = {r[0]: r for r in _compat_cells(cp_fx)}
    if cells["Притяжение, искра"][1:4] != ("+", "+", "+"):
        errs.append(f"матрица: Притяжение не сошлось в «+++»: {cells['Притяжение, искра'][1:4]}")
    if cells["Тело, близость"][2] != "-" or not cells["Тело, близость"][4]:
        errs.append("матрица: Тело/Йони — ожидался '-' труднее + флаг хрупкости A")
    if cells["Быт, эмоции"][2] != "-":
        errs.append("матрица: Быт/Бхакут (непогашенная доша) ожидался '-'")
    if cells["Дополняете друг друга"][2:4] != ("·", "·"):
        errs.append("матрица: «Дополняете друг друга» — Джйотиш и ДЧ должны молчать (·)")
    dirs = [(s, t) for s, t, _l, _c in _flow_arrows(cp_fx)]
    if ("A", "B") not in dirs or ("B", "A") not in dirs:
        errs.append(f"поток: ожидались стрелки в обе стороны, получено {dirs}")

    if errs:
        print("FAIL:\n  " + "\n  ".join(errs)); sys.exit(1)
    print("OK — infographics --test (13 проверок, 29 графиков: 23 системных + 3 синтеза + 3 совместимости)")


if __name__ == "__main__":
    _USAGE = ("infographics.py КАРТА.json [--product СИСТЕМА [--append-to ФАЙЛ.md]] | "
              "[--demo-md|--demo-hd|--demo-jy|--demo-mx|--demo-tb|--demo-gk|--demo-syn] | --test\n"
              "  СИСТЕМА ∈ " + ", ".join(sorted(PRODUCT_CHARTS)))
    if "--test" in sys.argv:
        _test(); sys.exit(0)
    if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
        sys.stderr.write(_USAGE + "\n")
        sys.exit(2)
    path = sys.argv[1]
    d = json.load(open(path, encoding="utf-8"))
    if "--product" in sys.argv:
        pidx = sys.argv.index("--product") + 1
        if pidx >= len(sys.argv):
            sys.stderr.write(_USAGE + "\nОШИБКА: --product без имени системы\n")
            sys.exit(2)
        system = sys.argv[pidx]
        if system not in PRODUCT_CHARTS:
            # опечатка не должна быть тихим no-op с exit 0 — профиль остался бы без графиков молча
            sys.stderr.write(f"ОШИБКА: неизвестный --product «{system}»; допустимо: "
                             + ", ".join(sorted(PRODUCT_CHARTS)) + "\n")
            sys.exit(2)
        section = product_section(system, d)
        if "--append-to" in sys.argv:
            # идемпотентный аппенд В КОДЕ: повторный прогон (ретрай Шага 4.5) не дублирует блок
            aidx = sys.argv.index("--append-to") + 1
            if aidx >= len(sys.argv):
                sys.stderr.write(_USAGE + "\nОШИБКА: --append-to без файла\n")
                sys.exit(2)
            target = sys.argv[aidx]
            try:
                existing = open(target, encoding="utf-8").read()
            except OSError as e:
                sys.stderr.write(f"ОШИБКА --append-to: {e}\n")
                sys.exit(2)
            if "## Графики к чтению" in existing:
                sys.stderr.write(f"{target}: блок «## Графики к чтению» уже есть — не дублирую\n")
                sys.exit(0)
            if section.strip():
                with open(target, "a", encoding="utf-8") as fh:
                    fh.write(section + "\n")
            sys.exit(0)
        sys.stdout.write(section + "\n")
    elif "--demo-hd" in sys.argv:
        sys.stdout.write(hd_demo_md(d) + "\n")
    elif "--demo-jy" in sys.argv:
        sys.stdout.write(jy_demo_md(d) + "\n")
    elif "--demo-mx" in sys.argv:
        sys.stdout.write(matrix_demo_md(d) + "\n")
    elif "--demo-tb" in sys.argv:
        sys.stdout.write(tibetan_demo_md(d) + "\n")
    elif "--demo-gk" in sys.argv:
        sys.stdout.write(gk_demo_md(d) + "\n")
    elif "--demo-syn" in sys.argv:
        sys.stdout.write(synthesis_demo_md() + "\n")
    elif "--demo-md" in sys.argv:
        sys.stdout.write(demo_md(d) + "\n")
    else:
        blocks = [four_pillars_svg(d), interactions_svg(d), shensha_svg(d), nayin_svg(d), fragility_svg(d),
                  five_elements_svg(d), wuxing_cycle_svg(d), tiaohou_svg(d), strength_gauge_svg(d),
                  ten_gods_svg(d), luck_timeline_svg(d), annual_year_svg(d), dynamic_interactions_svg(d)]
        sys.stdout.write("\n\n".join(_block(b) for b in blocks) + "\n")
