#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""bazi_report.py — Markdown-отчёт по карте Ба Цзы из JSON калькулятора, с выбором разделов.

Только факты расчёта: каждое число и каждая оговорка взяты из `bazi.py --json`; отчёт ничего не толкует
(толкование — дело скилла `bazi` и агента). Разделы независимы, их выбирает пользователь: в веб-интерфейсе
(web.py) — галочками, в CLI — `--sections`. Шапка с оговорками расчёта и хвост «чего здесь нет» входят всегда:
оговорки обязаны дойти до читателя.

CLI:
  .venv/bin/python bazi.py 1990-05-15 14:30 М --city Москва --json > chart.json
  python3 bazi_report.py chart.json                          # разделы по умолчанию → stdout («-» — JSON из stdin)
  python3 bazi_report.py chart.json --sections pillars,luck --charts -o chart_1990-05-15_Москва.md
  python3 bazi_report.py --list                              # какие разделы есть
  .venv/bin/python bazi_report.py --test                     # самопроверка (нужен .venv: гоняет bazi.py)
Графики (`--charts`) — блоки ```svg из infographics.py: их рендерит md2pdf.sh; обычный просмотрщик Markdown
покажет их как код.
"""
import json
import os
import re
import subprocess
import sys
from datetime import date, timedelta

DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DIR)
import infographics as ig  # noqa: E402  (только stdlib; SVG строится из того же JSON)

PILLAR_ORDER = ["hour", "day", "month", "year"]
PILLAR_HEAD = {"hour": "Час (时)", "day": "День (日)", "month": "Месяц (月)", "year": "Год (年)"}
SLOT_RU = {"hour": "столп часа", "day": "столп дня", "month": "столп месяца", "year": "столп года"}
SEVERITY = {"high": "‼", "medium": "⚠", "info": "ℹ"}
POLARITY = {"yang": "ян", "yin": "инь"}
# Копия bazi.TEN_GODS / TEN_GODS_RU: движок сюда не импортируется (ему нужен swisseph из .venv, отчёту — нет).
# Совпадение с движком проверяет --test.
TEN_GODS = ["比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"]
TEN_GODS_RU = ["Друг", "Грабитель Богатства", "Бог Пищи", "Ранящий Чиновник", "Косвенное Богатство",
               "Прямое Богатство", "Семь Убийств", "Прямой Чиновник", "Косвенная Печать", "Прямая Печать"]
VERDICT_RU = {"agree": "школы согласны", "partial": "совпадение частичное", "conflict": "школы расходятся",
              "n/a": "не сравнивается"}
CONVENTION_RU = {
    "late_zi_day": "Час 子 (23:00–23:59): какие сутки",
    "late_zi_hour_stem": "Час 子 (23:00–23:59): ствол часа",
    "year_change": "Смена года",
    "month_change": "Смена месяца",
    "hidden_stem_weights": "Веса скрытых стволов",
    "yongshen": "Выбор 用神",
    "shensha_base": "От чего считаются Шэнь Ша",
    "tianyi_version": "Версия 天乙贵人",
    "yangren_yin_stems": "羊刃 у инь-стволов",
}
CONVENTION_VALUE_RU = {
    ("late_zi_day", "same_day"): "день остаётся текущим, сутки меняются в полночь",
    ("late_zi_hour_stem", "next_day"): "от следующего дня",
    ("late_zi_hour_stem", "same_day"): "от текущего дня",
    ("year_change", "lichun_exact_moment"): "в точный момент 立春, а не 1 января",
    ("month_change", "jie_exact_moment"): "в точный момент солнечного термина 节",
}
CHART_CAPTIONS = dict(ig.PRODUCT_CHARTS["bazi"])
NOT_COMPUTED = ("12 стадий роста (十二长生), комбинации и столкновения стволов, самонаказания 自刑 и разрушения 六破, "
                "звёзды 将星 и 天德/月德")


# ── мелкие помощники ─────────────────────────────────────────────────────────────────────────────

def _cell(v):
    """Значение в ячейку таблицы: без переводов строк и без «|», который ломает разметку."""
    return str(v).replace("\n", " ").replace("|", "¦").strip()


def _table(header, rows):
    out = ["| " + " | ".join(_cell(h) for h in header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _num(x, digits=1):
    """18 → «18», 7.19 → «7.2»: без хвостов двоичной арифметики."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return str(x)
    r = round(float(x), digits)
    return str(int(r)) if r == int(r) else f"{r:.{digits}f}"


def _utc(off):
    if not isinstance(off, (int, float)) or isinstance(off, bool):
        return "UTC?"
    sign = "+" if off >= 0 else "−"
    total = round(abs(off) * 60)
    h, m = divmod(total, 60)
    return f"UTC{sign}{h}" + (f":{m:02d}" if m else "")


def _branch(b):
    return f"{b['name']} ({b['animal']})"


def _names(items, key="element"):
    return ", ".join(str(x[key]) for x in items or []) or "—"


def _god(zh):
    return f"{zh} ({TEN_GODS_RU[TEN_GODS.index(zh)]})" if zh in TEN_GODS else str(zh)


def _year_at(birth_iso, age):
    """Календарный год, в который человеку исполняется `age` лет (дробных)."""
    try:
        y, m, d = (int(x) for x in birth_iso.split("-"))
        whole = int(age)
        try:
            base = date(y + whole, m, d)
        except ValueError:                      # 29 февраля в невисокосный год
            base = date(y + whole, 3, 1)
        return (base + timedelta(days=(age - whole) * 365.2425)).year
    except (ValueError, OverflowError, TypeError):
        return None


# ── оговорки (общие для шапки отчёта и баннера в веб-интерфейсе) ────────────────────────────────────

def caveats(d):
    """Оговорки расчёта из honesty-полей JSON: [{severity, topic, text}]. Новой логики нет — только сбор полей."""
    i = d.get("input") or {}
    out = []
    for w in d.get("boundary_warnings") or []:
        sev = w.get("severity") if w.get("severity") in SEVERITY else "medium"
        out.append({"severity": sev, "topic": SLOT_RU.get(w.get("pillar"), str(w.get("pillar"))),
                    "text": str(w.get("detail", ""))})
    note = i.get("tz_note") or ""
    if "⚠" in note:
        out.append({"severity": "medium", "topic": "пояс", "text": note.replace("⚠", "").strip()})
    if not i.get("city"):
        out.append({"severity": "medium", "topic": "пояс",
                    "text": "пояс задан вручную: исторический пояс места не проверялся, поправка на истинное "
                            "солнечное время не делалась"})
    shift = i.get("solar_day_shift")
    if shift:
        out.append({"severity": "medium", "topic": "столп дня",
                    "text": f"солнечная поправка перенесла момент через полночь: столп дня взят от солнечных суток "
                            f"{i.get('solar_date')} (сдвиг {shift:+d} сут.), а не от календарной даты {i.get('date')}; "
                            f"школа «день по настенной дате» даёт другого Хозяина Дня"})
    if d.get("yongshen_borderline"):
        share = (d.get("strength") or {}).get("support_share")
        pct = f" (поддержка {_num(share * 100, 0)} %)" if isinstance(share, (int, float)) else ""
        alt = _names(d.get("yongshen_alt"))
        out.append({"severity": "medium", "topic": "用神",
                    "text": f"сила Хозяина Дня пограничная{pct}: выбор полезных стихий трактуем"
                            + (f"; альтернатива — {alt}" if alt != "—" else "")})
    g = d.get("geju") or {}
    cmp_ = g.get("comparison") or {}
    if cmp_.get("verdict") == "conflict":
        out.append({"severity": "medium", "topic": "школы расходятся",
                    "text": f"школа 格局 и школа силы дают разное: {cmp_.get('text', '')}"})
    elif cmp_.get("verdict") == "partial":
        out.append({"severity": "info", "topic": "школы сходятся не во всём",
                    "text": f"школа 格局 и школа силы: {cmp_.get('text', '')}"})
    for s in g.get("special_candidates") or []:
        out.append({"severity": "medium", "topic": "格局", "text": str(s)})
    if not d.get("luck_pillars"):
        out.append({"severity": "info", "topic": "столпы удачи",
                    "text": "не рассчитаны: пол не указан, а от него зависит направление столпов"})
    th = d.get("tiaohou")
    if th and th.get("aligns_with_yongshen") is False:
        out.append({"severity": "info", "topic": "调候",
                    "text": "климатическая стихия (调候) не совпадает с 用神 по силе — это два независимых регистра"})
    return out


# ── разделы ──────────────────────────────────────────────────────────────────────────────────────

def _head(d):
    i = d["input"]
    city, wall = i.get("city"), i.get("wall_time")
    rows = [("Дата рождения", i.get("date"))]
    rows.append(("Время по часам", (wall if city else i.get("time")) or "не указано"))
    rows.append(("Пол", i.get("gender") or "не указан"))
    if city:
        rows.append(("Место и пояс", f"{city} — {i['tz_note']}" if i.get("tz_note") else f"{city}, {_utc(i.get('utc_offset'))}"))
        if wall and i.get("time"):
            sd = i.get("solar_date")
            rows.append(("Истинное солнечное время", i["time"] + (f", солнечная дата {sd}" if sd and sd != i.get("date") else "")))
    else:
        rows.append(("Пояс", f"{_utc(i.get('utc_offset'))}, задан вручную"))
    rows.append(("Год и месяц Ба Цзы", f"{d.get('bazi_year')} (граница года — 立春), месяц № {d.get('bazi_month_number')} "
                                       f"({d.get('bazi_month_branch')})"))
    cy = d.get("current_year") or {}
    as_of = (cy.get("year_boundary") or {}).get("as_of")
    if as_of:
        rows.append(("Прогнозные слои на дату", f"{as_of} (год Ба Цзы {cy.get('year')})"))
    o = ["# Карта Ба Цзы (八字) — расчёт", "", _table(["Параметр", "Значение"], rows), "",
         "> Числа ниже — вывод калькулятора `bazi.py` (Swiss Ephemeris): [факт] расчёта, без толкования.", "",
         "## Оговорки расчёта", ""]
    cv = caveats(d)
    if cv:
        o += [f"- {SEVERITY[c['severity']]} **{c['topic']}:** {c['text']}" for c in cv]
    else:
        o.append("Калькулятор не выдал оговорок для этой карты.")
    return "\n".join(o)


def _pillars(d):
    P = d["pillars"]
    cols = [P.get(k) or {} for k in PILLAR_ORDER]

    def row(fn):
        return [(fn(k, p) or "—") if p.get("name") else "—" for k, p in zip(PILLAR_ORDER, cols)]

    rows = [
        ["10 божеств"] + row(lambda k, p: "**Хозяин Дня**" if k == "day" else f"{p['ten_god_ru']} ({p['ten_god']})"),
        ["Ствол"] + row(lambda k, p: f"{p['stem']['name']} {p['stem']['element']}, {POLARITY.get(p['stem']['polarity'], p['stem']['polarity'])}"),
        ["Ветвь"] + row(lambda k, p: f"{p['branch']['name']} {p['branch']['animal']} ({p['branch']['element']})"),
        ["Скрытые стволы"] + row(lambda k, p: "; ".join(
            f"{h['name']} {h.get('ten_god_ru') or h['element']}" for h in p["branch"].get("hidden_stems") or [])),
        ["На Инь (纳音)"] + row(lambda k, p: f"{p['nayin']} ({p['nayin_element']})"),
        ["№ в цикле 60"] + row(lambda k, p: p["sexagenary_position"]),
    ]
    names = " · ".join(p.get("name") or "—" for p in cols)
    o = ["## Четыре столпа (四柱)", "", _table([""] + [PILLAR_HEAD[k] for k in PILLAR_ORDER], rows), "",
         f"Столпы (Час · День · Месяц · Год): **{names}**."]
    if not cols[0].get("name"):
        o.append("Время рождения не указано — столп часа не рассчитан.")
    return "\n".join(o)


def _day_master(d):
    dm, dp, st = d["day_master"], d["day_pillar"], d["strength"]
    o = ["## Хозяин Дня и его сила", "",
         f"- **Хозяин Дня (日主):** {dm['name']} — {dm['element']}, {POLARITY.get(dm['polarity'], dm['polarity'])}.",
         f"- **Столп дня:** {dp['name']}, № {dp['sexagenary_position']} в цикле 60; На Инь {dp['nayin']}.",
         f"- **Сила:** {st['label']} (балл {_num(st['score'])})"
         + (f"; доля поддерживающих стихий — {_num(st['support_share'] * 100)} %." if isinstance(st.get("support_share"), (int, float)) else ".")]
    if st.get("borderline"):
        o.append("- Оценка силы пограничная: при другой школе весов вывод может смениться.")
    return "\n".join(o)


def _elements(d):
    dm = d["day_master"]["element_index"]
    ys = {x["index"] for x in d.get("yongshen") or []}
    js = {x["index"] for x in d.get("jishen") or []}

    def role(e):
        if e == dm:
            return "стихия Хозяина Дня"
        if (e + 1) % 5 == dm:
            return "порождает Хозяина Дня (生)"
        if (dm + 1) % 5 == e:
            return "порождается Хозяином Дня (生)"
        if (e + 2) % 5 == dm:
            return "контролирует Хозяина Дня (克)"
        return "под контролем Хозяина Дня (克)"

    rows = []
    for name, v in sorted(d["element_balance"].items(), key=lambda kv: kv[1]["index"]):
        mark = "用神" if v["index"] in ys else "忌神" if v["index"] in js else ""
        rows.append([name, f"{_num(v['percent'])} %", "█" * round(v["percent"] / 5) or "▏", role(v["index"]), mark or "—"])
    return "\n".join(["## Баланс пяти стихий (五行)", "",
                      _table(["Стихия", "Доля", "Шкала", "Отношение к Хозяину Дня", "Роль"], rows), "",
                      "Доля — вес стихии по восьми знакам и скрытым стволам; один блок шкалы — 5 %."])


def _ten_gods(d):
    present = d.get("ten_gods") or []
    rows = [[f"{g['name_ru']} ({g['name']})", _num(g["weight"])] for g in present]
    have = {g["name"] for g in present}
    missing = [f"{ru} ({zh})" for zh, ru in zip(TEN_GODS, TEN_GODS_RU) if zh not in have]
    o = ["## Десять божеств (十神)", "", _table(["Божество", "Вес"], rows), "",
         "Вес — сумма по стволам и скрытым стволам карты (Хозяин Дня не считается)."]
    o.append("Нет в карте: " + ", ".join(missing) + "." if missing else "В карте представлены все десять божеств.")
    return "\n".join(o)


def _yongshen(d):
    o = ["## Полезные и неблагоприятные стихии (用神 / 忌神)", "",
         f"- **用神 (полезные):** {_names(d.get('yongshen'))} — школа силы 旺衰"
         + (f"; основание: {d['yongshen_basis']}." if d.get("yongshen_basis") else "."),
         f"- **忌神 (неблагоприятные):** {_names(d.get('jishen'))}."]
    if d.get("yongshen_borderline") and d.get("yongshen_alt"):
        o.append(f"- **Альтернатива при пограничной силе:** {_names(d['yongshen_alt'])} [трактуемо].")
    th = d.get("tiaohou")
    if th:
        pr, aux = th.get("primary") or {}, th.get("auxiliary") or {}
        line = f"- **调候 (климат по сезону рождения):** {pr.get('stem')} {pr.get('element')}"
        if aux:
            line += f", вспомогательный {aux.get('stem')} {aux.get('element')}"
        line += (" — совпадает с 用神 по силе." if th.get("aligns_with_yongshen")
                 else " — не совпадает с 用神 по силе: это два независимых регистра.")
        o.append(line)
    else:
        o.append("- **调候:** калькулятор не выдал климатической стихии для этой карты.")
    return "\n".join(o)


def _geju(d):
    g = d.get("geju")
    o = ["## Структура карты (格局) — второй взгляд на 用神", ""]
    if not g:
        return "\n".join(o + ["Калькулятор не определил структуру для этой карты."])
    b = g.get("basis") or {}
    o.append(f"- **Структура:** {g.get('structure')} — по ветви месяца {b.get('month_branch')}: "
             f"{b.get('stem')} {_god(b.get('ten_god'))}, {b.get('how')}.")
    o.append(f"- **Статус:** {g.get('status')}.")
    if g.get("use"):
        o.append(f"- **Способ использования:** {g['use']}.")
    present = g.get("present") or {}
    for key, label in (("favourable", "Благоприятно (相神)"), ("unfavourable", "Неблагоприятно")):
        side = g.get(key)
        if isinstance(side, dict) and side.get("ten_gods"):
            have = ", ".join(_god(x) for x in present.get(key) or []) or "нет"
            o.append(f"- **{label}:** {', '.join(_god(x) for x in side['ten_gods'])} → стихии "
                     f"{', '.join(side.get('elements') or []) or '—'}; из них в карте: {have}.")
    if g.get("rule_note"):
        o.append(f"- **Правило структуры:** {g['rule_note']}.")
    if g.get("note"):
        o.append(f"- **Примечание:** {g['note']}.")
    cmp_ = g.get("comparison") or {}
    if cmp_:
        o.append(f"- **Сравнение со школой силы:** {VERDICT_RU.get(cmp_.get('verdict'), cmp_.get('verdict'))} — {cmp_.get('text')}.")
    for s in g.get("special_candidates") or []:
        o.append(f"- ⚠ {s}.")
    if g.get("source"):
        o += ["", f"*Источник правил: {g['source']}.*"]
    return "\n".join(o)


def _interactions(d):
    items = d.get("interactions") or []
    o = ["## Взаимодействия ветвей карты (冲 · 合 · 刑 · 害)", ""]
    o += [f"- {x}" for x in items] if items else ["Калькулятор не нашёл взаимодействий между ветвями карты."]
    return "\n".join(o)


def _stars(d):
    o = ["## Особые звёзды и пустота (神煞 · 空亡)", ""]
    stars = d.get("shensha") or []
    if stars:
        o += [_table(["Звезда", "Ветвь"], [[f"{s['name']} ({s['name_ru']})", s["branch"]] for s in stars]), ""]
    else:
        o += ["Звёзд из набора калькулятора в карте нет.", ""]
    kw = d.get("kong_wang") or []
    active = d.get("kong_wang_active") or []
    o.append(f"- **空亡 (пустота):** {', '.join(_branch(b) for b in kw) or '—'}; "
             + ("в карте на них стоят: " + ", ".join(_branch(b) for b in active) + "." if active
                else "ветвей карты среди них нет."))
    if d.get("hongluan"):
        o.append(f"- **红鸾 (Красный Феникс):** {_branch(d['hongluan'])}.")
    if d.get("tianxi"):
        o.append(f"- **天喜 (Небесная Радость):** {_branch(d['tianxi'])}.")
    return "\n".join(o)


def _luck(d):
    lp = d.get("luck_pillars") or {}
    pillars = lp.get("pillars") or []
    if not pillars:
        return "\n".join(["## Столпы удачи (大运)", "",
                          "Не рассчитаны: пол не указан, а от него зависит направление столпов."])
    cur = ((d.get("dynamic_interactions") or {}).get("luck") or {}).get("pillar")
    birth = (d.get("input") or {}).get("date", "")
    rows = []
    for p in pillars:
        y0, y1 = _year_at(birth, p["age_start"]), _year_at(birth, p["age_end"])
        rows.append([f"{_num(p['age_start'])}–{_num(p['age_end'])}", f"{y0}–{y1}" if y0 and y1 else "—", p["name"],
                     f"{p['stem']['element']} / {p['branch']['element']}", f"{p['ten_god_ru']} ({p['ten_god']})",
                     "◀ сейчас" if cur and p["name"] == cur else ""])
    direction = {"forward": "прямое", "reverse": "обратное"}.get(lp.get("direction"), str(lp.get("direction")))
    return "\n".join(["## Столпы удачи (大运)", "",
                      f"Направление — {direction}; первый столп начинается в {_num(lp.get('start_age'))} года.", "",
                      _table(["Возраст", "Годы (примерно)", "Столп", "Стихии: ствол / ветвь", "Божество ствола", "Сейчас"], rows)])


def _year(d):
    cy = d.get("current_year") or {}
    dyn = d.get("dynamic_interactions") or {}
    as_of = (cy.get("year_boundary") or {}).get("as_of") or ""
    st, br = cy.get("stem") or {}, cy.get("branch") or {}
    o = [f"## Текущий год и активации (на {as_of})" if as_of else "## Текущий год и активации", "",
         f"- **Год Ба Цзы {cy.get('year')}:** {cy.get('pillar')} — ствол {st.get('element')} "
         f"({POLARITY.get(st.get('polarity'), st.get('polarity'))}), ветвь {br.get('animal')} ({br.get('element')}); "
         f"для Хозяина Дня ствол года — {cy.get('ten_god_ru')} ({cy.get('ten_god')})."]
    basis = (cy.get("year_boundary") or {}).get("basis")
    if basis:
        o.append(f"- **Граница года:** {basis}.")
    o.append("- **Столкновение (冲) ветви года с ветвями карты:** " + ("есть." if cy.get("clashes_natal") else "нет."))
    if isinstance(dyn.get("age_exact"), (int, float)):
        o.append(f"- **Возраст на дату:** {_num(dyn['age_exact'])}.")
    luck = dyn.get("luck") or {}
    if luck.get("pillar"):
        o.append(f"- **Текущий столп удачи:** {luck['pillar']} (возраст {_num(luck.get('age_start'))}–{_num(luck.get('age_end'))}).")
    elif not d.get("luck_pillars"):
        o.append("- **Текущий столп удачи:** не рассчитан (пол не указан).")
    else:
        o.append("- **Текущий столп удачи:** на эту дату нет (до начала первого столпа или после последнего).")
    for label, items in (("Год × карта", (dyn.get("year") or {}).get("vs_natal")),
                         ("Удача × карта", luck.get("vs_natal")),
                         ("Год × удача", dyn.get("year_vs_luck"))):
        o.append(f"- **{label}:** " + ("; ".join(items) + "." if items else "взаимодействий нет."))
    return "\n".join(o)


def _archetype(d):
    dp = d["day_pillar"]
    pos = dp["sexagenary_position"]
    o = [f"## Архетип столпа дня — {dp['name']}", ""]
    try:
        lines = open(os.path.join(DIR, "60_pillars.md"), encoding="utf-8").read().split("\n")
    except OSError:
        return "\n".join(o + ["Справочник `60_pillars.md` не найден рядом с калькулятором."])
    start = next((n for n, ln in enumerate(lines) if ln.startswith(f"**{pos}. ")), None)
    if start is None:
        return "\n".join(o + [f"В справочнике `60_pillars.md` нет записи № {pos}."])
    body = []
    for ln in lines[start + 1:]:
        if re.match(r"^(\*\*\d+\. |#|---)", ln):
            break
        body.append(ln)
    o += [lines[start], "", "\n".join(body).strip(), "",
          "*[интерпретация] — компиляция популярной традиции «日柱论命» из справочника `60_pillars.md`: не расчёт, "
          "не классический текст и не приговор.*"]
    return "\n".join(o)


def _conventions(d):
    conv = d.get("conventions") or {}
    o = ["## Конвенции расчёта", "",
         "Школы считают по-разному; ниже — то, как посчитана эта карта. Другая конвенция может дать другой результат."]
    o.append("")
    for k, v in conv.items():
        if k == "switches" and isinstance(v, dict):
            o.append("- **Переключатели запуска:** " + ", ".join(f"`{a} {b}`" for a, b in v.items()) + ".")
        else:
            human = CONVENTION_VALUE_RU.get((k, v))
            o.append(f"- **{CONVENTION_RU.get(k, k)}:** " + (f"{human} (`{v}`)." if human else f"{v}."))
    return "\n".join(o)


def _json(d):
    return "\n".join(["## JSON калькулятора", "", "```json", json.dumps(d, ensure_ascii=False, indent=1), "```"])


def _about(d):
    return "\n".join([
        "## Чего здесь нет", "",
        "- **Толкования.** Отчёт перечисляет результаты расчёта; чтение карты — отдельная работа (скилл `bazi`).",
        f"- **Того, что калькулятор не считает:** {NOT_COMPUTED}.",
        "- **Предсказаний.** Ба Цзы — язык тенденций традиции, а не прогноз и не медицинская, психологическая "
        "или финансовая рекомендация.", "",
        f"*Сформировано {date.today().isoformat()} — `bazi_report.py` по выводу `bazi.py --json`.*"])


SECTIONS = [
    # id, заголовок для выбора, по умолчанию, обязательный, сборщик, графики, подсказка
    ("head", "Исходные данные и оговорки", True, True, _head, ["fragility_svg"],
     "входит всегда: дата, пояс, солнечное время и все оговорки расчёта"),
    ("pillars", "Четыре столпа", True, False, _pillars, ["four_pillars_svg"],
     "стволы, ветви, скрытые стволы, 10 божеств, На Инь"),
    ("day_master", "Хозяин Дня и сила", True, False, _day_master, ["strength_gauge_svg"], "стихия, балл и доля поддержки"),
    ("elements", "Баланс пяти стихий", True, False, _elements, ["five_elements_svg", "wuxing_cycle_svg"], "доли стихий и их роль"),
    ("ten_gods", "Десять божеств", True, False, _ten_gods, ["ten_gods_svg"], "какие есть, с каким весом, каких нет"),
    ("yongshen", "用神 / 忌神 и 调候", True, False, _yongshen, ["tiaohou_svg"], "полезные и неблагоприятные стихии, климат"),
    ("geju", "Структура 格局", True, False, _geju, [], "второй взгляд на 用神 и сравнение школ"),
    ("interactions", "Взаимодействия ветвей", True, False, _interactions, ["interactions_svg"], "冲 · 合 · 刑 · 害 внутри карты"),
    ("stars", "Шэнь Ша и пустота", True, False, _stars, [], "звёзды, 空亡, 红鸾 / 天喜"),
    ("luck", "Столпы удачи", True, False, _luck, ["luck_timeline_svg"], "десятилетия 大运 с возрастами и годами"),
    ("year", "Текущий год и активации", True, False, _year, ["annual_year_svg", "dynamic_interactions_svg"],
     "столп года, текущая удача и их связи с картой"),
    ("archetype", "Архетип столпа дня", False, False, _archetype, [],
     "текст из справочника 60_pillars.md — [интерпретация], не расчёт"),
    ("conventions", "Конвенции расчёта", True, False, _conventions, [], "по каким правилам школ посчитано"),
    ("json", "Сырой JSON", False, False, _json, [], "полный вывод калькулятора"),
    ("about", "Чего здесь нет", True, True, _about, [], "входит всегда: границы отчёта"),
]
SECTION_IDS = [s[0] for s in SECTIONS]


def _charts_md(d, fns):
    """Блоки ```svg с подписью для раздела; сбой отдельного графика не роняет отчёт, но и не прячется."""
    out = []
    year = (d.get("current_year") or {}).get("year", "")
    for fn in fns:
        try:
            svg = getattr(ig, fn)(d)
        except Exception as e:  # график — иллюстрация: отчёт важнее
            why = ("не строится для карты без времени рождения" if not (d["pillars"].get("hour") or {}).get("name")
                   else "не строится без столпов удачи (пол не указан)" if not d.get("luck_pillars")
                   else f"сбой {type(e).__name__}")
            out.append(f"*График `{fn}` пропущен: {why}.*")
            continue
        cap = CHART_CAPTIONS.get(fn, "")
        out.append("```svg\n" + svg + "\n```")
        if cap:
            out.append(f"*{cap.format(year=year) if '{year}' in cap else cap}*")
    return "\n\n".join(out)


def build_parts(d):
    """Все разделы отчёта по карте: [{id, title, hint, default, locked, md, charts_md}]."""
    if not isinstance(d, dict) or "pillars" not in d or "input" not in d:
        raise ValueError("это не вывод bazi.py --json: нет полей input/pillars")
    parts = []
    for sid, title, default, locked, builder, charts, hint in SECTIONS:
        parts.append({"id": sid, "title": title, "hint": hint, "default": default, "locked": locked,
                      "md": builder(d), "charts_md": _charts_md(d, charts) if charts else ""})
    return parts


def assemble(parts, selected=None, charts=False):
    """Собрать отчёт из выбранных разделов. selected=None — разделы по умолчанию; обязательные входят всегда."""
    chosen = None if selected is None else set(selected)
    out = []
    for p in parts:
        if not (p["locked"] or (p["default"] if chosen is None else p["id"] in chosen)):
            continue
        out.append(p["md"])
        if charts and p["charts_md"]:
            out.append(p["charts_md"])
    return "\n\n".join(out).rstrip() + "\n"


def default_filename(d):
    """chart_<дата>_<город>.md — под шаблон `chart_*.md` из .gitignore: личное чтение не попадёт в репозиторий."""
    i = d.get("input") or {}
    place = re.sub(r"[^\w-]+", "_", str(i.get("city") or _utc(i.get("utc_offset"))), flags=re.UNICODE).strip("_")
    return f"chart_{i.get('date', 'bazi')}_{place or 'bazi'}.md"


# ── самопроверка ────────────────────────────────────────────────────────────────────────────────

def _table_shapes_ok(md):
    """У каждой таблицы все строки той же ширины, что и шапка (иначе «|» из данных сломал разметку)."""
    lines, n = md.split("\n"), 0
    while n < len(lines):
        if lines[n].startswith("|") and n + 1 < len(lines) and re.match(r"^\|(---\|)+$", lines[n + 1]):
            width = lines[n].count("|")
            n += 2
            while n < len(lines) and lines[n].startswith("|"):
                if lines[n].count("|") != width:
                    return False
                n += 1
        else:
            n += 1
    return True


def _test():
    import md2html
    py = os.path.join(DIR, ".venv", "bin", "python")
    py = py if os.path.exists(py) else sys.executable
    ok = True

    def chk(cond, label):
        nonlocal ok
        ok &= bool(cond)
        print(("  ✓ " if cond else "  ✗ ") + label)

    def chart(*args):
        p = subprocess.run([py, os.path.join(DIR, "bazi.py"), *args, "--as-of", "2026-11-09", "--json"],
                           capture_output=True, text=True, cwd=DIR, timeout=120)
        if p.returncode != 0:
            raise RuntimeError(f"bazi.py {' '.join(args)}: {p.stderr.strip()[-300:]}")
        return json.loads(p.stdout)

    code = "import json, bazi; print(json.dumps([bazi.TEN_GODS, bazi.TEN_GODS_RU], ensure_ascii=False))"
    p = subprocess.run([py, "-c", code], capture_output=True, text=True, cwd=DIR, timeout=60)
    chk(p.returncode == 0 and json.loads(p.stdout) == [TEN_GODS, TEN_GODS_RU], "TEN_GODS / TEN_GODS_RU совпадают с bazi.py")
    chk(set(CHART_CAPTIONS) >= {fn for s in SECTIONS for fn in s[5]}, "у каждого графика отчёта есть подпись в infographics.PRODUCT_CHARTS")

    cases = [("время + город", ("1990-05-15", "14:30", "М", "--city", "Москва")),
             ("без времени", ("1985-12-03", "Ж", "--city", "Москва")),
             ("пояс вручную", ("1990-05-15", "14:30", "М", "UTC+8")),
             ("солнечная полночь", ("1990-03-03", "01:00", "М", "--city", "Пермь")),
             ("у 立春, школы расходятся", ("2010-02-04", "02:00", "Ж", "--city", "Москва"))]
    for label, args in cases:
        d = chart(*args)
        parts = build_parts(d)
        by = {x["id"]: x for x in parts}
        full = assemble(parts, SECTION_IDS, charts=True)
        chk([x["id"] for x in parts] == SECTION_IDS, f"{label}: все {len(SECTION_IDS)} разделов на месте")
        names = [d["pillars"][k]["name"] for k in PILLAR_ORDER if d["pillars"][k].get("name")]
        chk(all(nm in by["pillars"]["md"] for nm in names), f"{label}: столпы {' '.join(names)} в таблице")
        chk(all(w["detail"] in by["head"]["md"] for w in d.get("boundary_warnings") or []),
            f"{label}: все boundary_warnings ({len(d.get('boundary_warnings') or [])}) в шапке")
        chk(all(lp["name"] in by["luck"]["md"] for lp in d["luck_pillars"]["pillars"]), f"{label}: все столпы удачи в таблице")
        chk("None" not in full.replace(json.dumps(d, ensure_ascii=False, indent=1), ""), f"{label}: в тексте нет «None»")
        chk(_table_shapes_ok(full), f"{label}: таблицы ровные")
        html_ = md2html.convert(md2html.normalize_symbols(full))
        chk(html_.count("<svg") == full.count("```svg") > 0 and "<table" in html_,
            f"{label}: md2html рендерит {full.count('```svg')} графиков и таблицы")
        minimal = assemble(parts, [], charts=False)
        chk("## Оговорки расчёта" in minimal and "## Чего здесь нет" in minimal and "## Столпы удачи" not in minimal
            and "```svg" not in minimal, f"{label}: без галочек остаются только обязательные разделы")

    d = chart("1990-03-03", "01:00", "М", "--city", "Пермь")
    chk("через полночь" in _head(d), "солнечная полночь попала в оговорки")
    d = chart("1990-05-15", "14:30", "М", "UTC+8")
    chk("задан вручную" in _head(d) and default_filename(d) == "chart_1990-05-15_UTC_8.md", "пояс вручную: оговорка и имя файла")
    d = chart("1990-05-15", "14:30", "М", "--city", "Москва")
    chk("День Добродетели" in _archetype(d) and "**18. " not in _archetype(d), "архетип 庚辰 (№ 17) взят из 60_pillars.md без соседней записи")
    chk("◀ сейчас" in _luck(d) and "1997–2007" in _luck(d), "столпы удачи: текущий отмечен, годы посчитаны")
    chk(default_filename(d) == "chart_1990-05-15_Москва.md", "имя файла chart_<дата>_<город>.md")
    default = assemble(build_parts(d))
    chk("## Архетип столпа дня" not in default and "## JSON калькулятора" not in default and "## Четыре столпа" in default,
        "по умолчанию: без архетипа и сырого JSON")
    d = chart("1990-05-15", "14:30", "--city", "Москва")
    full = assemble(build_parts(d), SECTION_IDS, charts=True)
    chk("None" not in full.replace(json.dumps(d, ensure_ascii=False, indent=1), "") and "пол не указан" in _luck(d)
        and "пол не указан" in _head(d) and "не рассчитан (пол не указан)" in _year(d),
        "без пола: столпы удачи честно «не рассчитаны», в тексте нет «None»")
    chk(_year_at("2000-01-01", 1) == 2001 and _year_at("2000-01-01", 0.5) == 2000 and _year_at("2000-02-29", 1) == 2001,
        "годы по возрасту: 1 год от 2000-01-01 — это 2001; 29 февраля не роняет расчёт")
    p = subprocess.run([sys.executable, os.path.abspath(__file__), "-", "--sections", "pillars"], input=json.dumps(d),
                       capture_output=True, text=True, cwd=DIR, timeout=60)
    chk(p.returncode == 0 and "## Четыре столпа" in p.stdout and "## Столпы удачи" not in p.stdout, "CLI: JSON из stdin через «-», --sections")
    d = chart("1990-05-15", "14:30", "М", "--city", "Москва")
    chk(any(c["topic"] == "школы сходятся не во всём" for c in caveats(d)), "частичное расхождение школ (partial) попало в оговорки")
    try:
        build_parts({"foo": 1})
        chk(False, "чужой JSON отклонён")
    except ValueError:
        chk(True, "чужой JSON отклонён")
    print("bazi_report --test:", "ЗЕЛЕНО ✓" if ok else "КРАСНОЕ ✗")
    return 0 if ok else 1


def main(argv):
    if "--test" in argv:
        return _test()
    if "--list" in argv:
        for sid, title, default, locked, _b, charts, hint in SECTIONS:
            flag = "всегда" if locked else "по умолчанию" if default else "по запросу"
            print(f"{sid:13} {title} — {hint} [{flag}{', есть графики' if charts else ''}]")
        return 0
    opts = {a: argv[n + 1] for n, a in enumerate(argv[:-1]) if a in ("--sections", "-o")}
    skip = {n + 1 for n, a in enumerate(argv[:-1]) if a in opts}
    args = [a for n, a in enumerate(argv) if n not in skip and (a == "-" or not a.startswith("-"))]
    if len(args) != 1:
        sys.stderr.write(__doc__)
        return 2
    try:
        d = json.load(sys.stdin if args[0] == "-" else open(args[0], encoding="utf-8"))
        parts = build_parts(d)
    except (OSError, ValueError) as e:
        sys.stderr.write(f"ОШИБКА: {e}\n")
        return 2
    selected = None
    if "--sections" in opts:
        selected = [s.strip() for s in opts["--sections"].split(",") if s.strip()]
        unknown = [s for s in selected if s not in SECTION_IDS]
        if unknown:
            sys.stderr.write(f"ОШИБКА: неизвестные разделы: {', '.join(unknown)}; есть: {', '.join(SECTION_IDS)}\n")
            return 2
    md = assemble(parts, selected, charts="--charts" in argv)
    if "-o" in opts:
        with open(opts["-o"], "w", encoding="utf-8") as fh:
            fh.write(md)
    else:
        sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
