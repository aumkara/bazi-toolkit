#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""retro_signals.py — кандидаты вопросов о прошлом из двух готовых карт.

retro_signals.py --bazi ФАЙЛ --jyotish ФАЙЛ [--years 15] [--as-of ГГГГ-ММ-ДД] [--json]
retro_signals.py --test
"""
import json
import math
import re
import sys
from datetime import date, datetime, timedelta

import bazi  # общий бутстрап ephemeris под .venv
import cli_errors
import jyotish


SOURCE_NOTE = (
    "Сигналы получены кодом по прошлым годам и сменам периодов до ответов человека. "
    "Часть расчётных оснований отсутствует в чтениях 1–3; они сохранены в JSON сигналов "
    "и исходных картах. Связь с жизненными темами — интерпретация, а не вычисленный факт."
)
HONESTY_NOTE = (
    "Это все подходящие кандидаты по ограниченному набору правил, не список случившихся событий. "
    "Столкновение ветвей или сочетание богов само по себе не доказывает конфликт; "
    "пара 伤官/正官 не доказывает сформировавшуюся структуру. "
    "Даты удачи приблизительны: исходный возраст округлён, биографический вопрос имеет допуск ±1 год. "
    "Порог «3 из 5» — эвристика скилла, не статистическая верификация и не доказательство системы. "
    "Несколько сигналов одного года могут зависеть друг от друга; их нельзя считать независимыми подтверждениями. "
    "Если кандидатов меньше пяти, данных для порога «3 из 5» недостаточно."
)
YEAR_NOTE = "Годы Ба Цзы — метки с границей в Личунь, не 1 января; календарные окна не обещают дат событий."


def _require(condition, message):
    if not condition:
        raise cli_errors.InputError(message)


def _object(value, label):
    _require(isinstance(value, dict) and "error" not in value, f"{label}: нужен JSON-объект без error")
    return value


def _date(value, label):
    _require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value),
             f"{label}: нужна дата ГГГГ-ММ-ДД")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise cli_errors.InputError(f"{label}: недопустимая дата") from exc


def _time(value, label):
    _require(isinstance(value, str) and re.fullmatch(r"\d{2}:\d{2}", value),
             f"{label}: нужно время ЧЧ:ММ")
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise cli_errors.InputError(f"{label}: недопустимое время") from exc
    return value


def _number(value, label, minimum=0):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value >= minimum
    except OverflowError:
        valid = False
    _require(valid,
             f"{label}: нужно конечное число не меньше {minimum}")
    return value


def _offset(value, label):
    _number(value, label, -24)
    _require(-24 < value < 24, f"{label}: оффсет должен быть строго между -24 и 24")
    return value


def _point(value, names, label):
    value = _object(value, label)
    index = value.get("index")
    _require(type(index) is int and 0 <= index < len(names), f"{label}.index: индекс вне диапазона")
    _require(value.get("name") == names[index], f"{label}.name: имя не соответствует индексу")
    return index


def _pillar(value, label):
    value = _object(value, label)
    si = _point(value.get("stem"), bazi.STEMS, label + ".stem")
    bi = _point(value.get("branch"), bazi.BRANCHES, label + ".branch")
    _require(si % 2 == bi % 2 and value.get("name") == bazi.STEMS[si] + bazi.BRANCHES[bi],
             f"{label}: несогласованные ствол, ветвь или имя столпа")
    return si, bi


def _luck_date(birth, age):
    try:
        return birth + timedelta(days=age * 365.2425)
    except (OverflowError, ValueError) as exc:
        raise cli_errors.InputError("luck_pillars: возраст выходит за диапазон календаря") from exc


def validate(b, j, years, as_of):
    """Валидация всего используемого ввода ДО вычисления сигналов."""
    _require(type(years) is int and 1 <= years <= 100, "--years: нужно целое число от 1 до 100")
    _require(type(as_of) is date, "--as-of: нужна календарная дата")
    b, j = _object(b, "bazi"), _object(j, "jyotish")
    bi, ji = _object(b.get("input"), "bazi.input"), _object(j.get("input"), "jyotish.input")
    birth = _date(bi.get("date"), "bazi.input.date")
    wall = bi.get("wall_time") if "wall_time" in bi else bi.get("time")
    if bi.get("city") or "solar_date" in bi:
        _require("wall_time" in bi, "bazi.input: солнечное время нельзя сопоставить без wall_time")
    wall = _time(wall, "bazi.input.wall_time/time")
    if "solar_date" in bi:
        _date(bi["solar_date"], "bazi.input.solar_date")
    if "solar_day_shift" in bi:
        _require(type(bi["solar_day_shift"]) is int, "bazi.input.solar_day_shift: нужен целый сдвиг")
    local = ji.get("birth_local")
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) UTC([+-]?\d+(?:\.\d+)?)",
                          local) if isinstance(local, str) else None
    _require(match is not None, "jyotish.input.birth_local: нужны настенные дата, время и смещение UTC")
    jd, jt, jo = match.groups()
    _require(_date(jd, "jyotish.input.birth_local") == birth
             and _time(jt, "jyotish.input.birth_local") == wall, "карты: разные настенные дата или время")
    jo = _offset(float(jo), "jyotish.input.birth_local.UTC")
    bo = _offset(bi.get("utc_offset"), "bazi.input.utc_offset")
    _require(abs(bo - jo) < 1e-9, "карты: разные UTC-смещения")
    try:
        birth_utc = (datetime.fromisoformat(f"{birth.isoformat()} {wall}")
                     - timedelta(hours=bo)).date()
    except OverflowError as exc:
        raise cli_errors.InputError("момент рождения в UTC выходит за диапазон календаря") from exc
    _require(as_of >= birth, "--as-of не может быть раньше рождения")
    _require(isinstance(b.get("conventions"), dict) and bool(b["conventions"]),
             "bazi.conventions: нужен непустой объект")
    _require(isinstance(j.get("conventions"), str) and bool(j["conventions"].strip()),
             "jyotish.conventions: нужна непустая строка")
    pillars = _object(b.get("pillars"), "bazi.pillars")
    ds, _db = _pillar(pillars.get("day"), "bazi.pillars.day")
    _pillar(pillars.get("month"), "bazi.pillars.month")
    dm = _point(b.get("day_master"), bazi.STEMS, "bazi.day_master")
    _require(dm == ds, "bazi.day_master: ствол не совпадает с дневным столпом")
    gods = b.get("ten_gods")
    _require(isinstance(gods, list), "bazi.ten_gods: нужен список")
    seen = set()
    for row in gods:
        row = _object(row, "bazi.ten_gods[]")
        name = row.get("name")
        _require(isinstance(name, str) and name in bazi.TEN_GODS and name not in seen,
                 "bazi.ten_gods: неизвестное или повторное имя")
        seen.add(name)
        _number(row.get("weight"), "bazi.ten_gods[].weight")
    _require("luck_pillars" in b, "bazi.luck_pillars: поле отсутствует (допустим явный null)")
    if b["luck_pillars"] is not None:
        luck = _object(b["luck_pillars"], "bazi.luck_pillars")
        rows = luck.get("pillars")
        _require(isinstance(rows, list) and bool(rows), "luck_pillars.pillars: нужен непустой список")
        previous = -1
        for row in rows:
            _pillar(row, "luck_pillars.pillars[]")
            age = _number(row.get("age_start"), "luck_pillars.pillars[].age_start")
            _require(age > previous, "luck_pillars: возраста должны строго возрастать")
            _luck_date(birth, age)
            previous = age
    timeline = j.get("dasha_timeline")
    _require(isinstance(timeline, list) and bool(timeline), "jyotish.dasha_timeline: нужен непустой список")
    previous = None
    for n, row in enumerate(timeline):
        row = _object(row, "dasha_timeline[]")
        _require(row.get("lord") in jyotish.DASHA_ORDER, "dasha_timeline[].lord: неизвестный владыка")
        start, end = _date(row.get("from"), "dasha_timeline[].from"), _date(row.get("to"), "dasha_timeline[].to")
        # Первый остаток может занимать менее суток; CLI округляет обе границы до даты.
        _require((start <= end if n == 0 else start < end) and (previous is None or previous == start),
                  "dasha_timeline: даты должны возрастать без разрывов и перекрытий")
        previous = end
    # Первый элемент CLI — остаток периода при рождении (UTC-дата может отличаться на сутки).
    first = timeline[0]
    _require(_date(first["from"], "dasha_timeline[0].from") <= birth_utc
             <= _date(first["to"], "dasha_timeline[0].to"),
             "dasha_timeline: первый период не охватывает рождение")
    return birth


def build_signals(b, j, years=15, as_of=None):
    as_of = date.today() if as_of is None else as_of
    birth = validate(b, j, years, as_of)
    start_year = max(1, as_of.year - years)
    start = max(birth, date(start_year, 1, 1))
    end = as_of  # исключающая граница: сегодня не считается прошлым
    signals = []

    def add(system, kind, year, when, window, precision, basis, question, suffix=""):
        stamp = when or str(year)
        signals.append({"id": f"{system}:{kind}:{stamp}{suffix}", "system": system, "kind": kind,
                        "year": year, "date": when, "window": window, "precision": precision,
                        "basis": basis, "question_ru": question})

    luck = b["luck_pillars"]
    if luck is not None:
        for n, row in enumerate(luck["pillars"]):
            when = _luck_date(birth, row["age_start"])
            if not start <= when < end:
                continue
            # Края вопроса обрезаются доступной историей; за будущими событиями не спрашиваем.
            lo = date.fromordinal(max(start.toordinal(), when.toordinal() - 366))
            hi = date.fromordinal(min(end.toordinal() - 1, when.toordinal() + 366))
            add("bazi", "luck_change", when.year, when.isoformat(),
                {"from": lo.isoformat(), "to": hi.isoformat()}, "приблизительная дата; вопрос с допуском ±1 год",
                {"fields": {"input.date": birth.isoformat(),
                            f"luck_pillars.pillars[{n}].age_start": row["age_start"],
                            f"luck_pillars.pillars[{n}].name": row["name"]},
                 "rule": "Настенная дата + age_start × 365.2425 суток; солнечный сдвиг повторно не применяется.",
                 "computed": {"approximate_date": when.isoformat()}},
                f"В промежутке {lo.isoformat()} — {hi.isoformat()} заметно менялись работа, место жизни "
                "или повседневный уклад? Подтвердите или опровергните; если ничего такого не было, так и ответьте.")

    dm = b["day_master"]["index"]
    natal = {row["name"]: (n, row["weight"]) for n, row in enumerate(b["ten_gods"]) if row["weight"] > 0}
    for year in range(max(start_year, birth.year), as_of.year):
        si, branch = bazi.year_pillar(year)
        god = bazi.TEN_GODS[bazi.ten_god(dm, si)]
        annual = {"year": year, "pillar": bazi.STEMS[si] + bazi.BRANCHES[branch],
                  "stem_index": si, "branch_index": branch, "ten_god": god}
        window = {"from": max(start, date(year, 1, 1)).isoformat(), "to": date(year, 12, 31).isoformat()}
        for target, topic in (("day", "близких отношениях или домашней жизни"),
                              ("month", "работе, учёбе или привычном окружении")):
            point = b["pillars"][target]["branch"]
            if bazi.CLASHES[branch] == point["index"]:
                add("bazi", target + "_clash", year, None, window, "метка года Ба Цзы; граница — Личунь",
                    {"fields": {f"pillars.{target}.branch.index": point["index"],
                                f"pillars.{target}.branch.name": point["name"], "day_master.index": dm},
                     "rule": "CLASHES[ветвь года] == натальная ветвь цели; " + YEAR_NOTE,
                     "computed": {**annual, "target": target, "clash_branch_index": bazi.CLASHES[branch]}},
                    f"В {year} году были заметные перемены или напряжение в {topic}? "
                    "Подтвердите или опровергните; отсутствие таких событий тоже ответ.")
        common = {"day_master.index": dm}
        if god == "七杀":
            add("bazi", "seven_killings", year, None, window, "метка года Ба Цзы; граница — Личунь",
                {"fields": common, "rule": "TEN_GODS[ten_god(ствол дня, ствол года)] == 七杀.",
                 "computed": annual},
                f"В {year} году приходилось сталкиваться с заметным внешним давлением или жёсткими требованиями? "
                "Подтвердите или опровергните; сам расчёт не означает, что конфликт был.")
        other = {"正官": "伤官", "伤官": "正官"}.get(god)
        if other in natal:
            n, weight = natal[other]
            add("bazi", "hurting_officer_meets_officer", year, None, window,
                "метка года Ба Цзы; кандидат по сочетанию, не установленная структура",
                {"fields": {**common, f"ten_gods[{n}].name": other, f"ten_gods[{n}].weight": weight},
                 "rule": "Годовой 正官 + натальное 伤官 либо годовой 伤官 + натальное 正官 с положительным весом.",
                 "computed": {**annual, "pair": [god, other]}},
                f"В {year} году возникали споры с начальством, правилами или официальными требованиями? "
                "Подтвердите или опровергните; этот вопрос — интерпретация сочетания, не факт биографии.")

    timeline = j["dasha_timeline"]
    for n, row in enumerate(timeline):
        when = _date(row["from"], "dasha_timeline[].from")
        if n == 0 or not start <= when < end or when <= birth:
            continue
        add("jyotish", "mahadasha_change", when.year, row["from"],
            {"from": row["from"], "to": row["from"]}, "дата из исходного JSON; не дата доказанного события",
            {"fields": {f"dasha_timeline[{n}].lord": row["lord"], f"dasha_timeline[{n}].from": row["from"],
                        f"dasha_timeline[{n}].to": row["to"]},
             "rule": "Начало следующего большого периода из готовой временной шкалы; первый остаток исключён."},
            f"Около {row['from']} вы замечали смену главной жизненной темы — например, в работе или отношениях? "
            "Подтвердите или опровергните; совпадение по дате не предполагается заранее.")
    signals.sort(key=lambda s: (s["date"] or s["window"]["from"], s["system"], s["kind"], s["id"]))
    not_computed = [
        "Дизайн Человека: датированного годового событийного слоя нет.",
        "Антардаши здесь не рассчитываются; новые прогнозные периоды не строятся.",
    ]
    if luck is None:
        not_computed.append("Смены десятилетних периодов Ба Цзы: в исходном JSON luck_pillars=null.")
    return {
        "input": {"as_of": as_of.isoformat(), "years": years, "window_from": start.isoformat(),
                  "window_to_exclusive": end.isoformat(),
                  "annual_years": {"from": max(start_year, birth.year), "to_exclusive": as_of.year},
                  "restrictions": ["Не раньше рождения; для смен периодов дата строго раньше as_of.",
                                   "Годовые сигналы только за завершённые годы; текущий год исключён.",
                                   "Начала периодов только из доступных исходных списков, без достраивания.",
                                   "Годовые сигналы внутри года не упорядочены по реальному времени событий."],
                  "dasha_coverage": {"from": timeline[0]["from"], "to_exclusive": timeline[-1]["to"]}},
        "signals": signals, "source_note": SOURCE_NOTE, "honesty_note": HONESTY_NOTE,
        "not_computed": not_computed,
        "conventions": {"annual_years": YEAR_NOTE,
                         "luck_dates": "Настенная input.date + age_start × 365.2425 суток; возраст округлён, допуск вопроса ±1 год.",
                         "dasha_dates": "Даты периодов в исходном JSON — по UTC, без точного времени перехода; первый остаток исключён.",
                        "sorting": "По дате начала или началу календарной метки года, затем system/kind/id.",
                        "bazi": b["conventions"], "jyotish": j["conventions"]},
    }


def read_input(path, label):
    try:
        with open(path, encoding="utf-8") as f:
            value = json.load(f)
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        raise cli_errors.InputError(f"{label}: файл отсутствует, недоступен или содержит неверный JSON") from exc
    return _object(value, label)


def parse_args(args):
    options, json_mode = {}, False
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--json" and not json_mode:
            json_mode = True
            i += 1
            continue
        _require(arg in ("--bazi", "--jyotish", "--years", "--as-of") and arg not in options,
                 "неизвестный или повторный аргумент")
        _require(i + 1 < len(args) and not args[i + 1].startswith("--"), "не хватает значения после флага")
        options[arg] = args[i + 1]
        i += 2
    _require("--bazi" in options and "--jyotish" in options, "нужны --bazi ФАЙЛ и --jyotish ФАЙЛ")
    try:
        years = int(options.get("--years", "15"))
    except ValueError as exc:
        raise cli_errors.InputError("--years: нужно целое число от 1 до 100") from exc
    _require(1 <= years <= 100, "--years: нужно целое число от 1 до 100")
    as_of = _date(options["--as-of"], "--as-of") if "--as-of" in options else date.today()
    return options["--bazi"], options["--jyotish"], years, as_of, json_mode


def _test():
    from copy import deepcopy
    from datetime import timezone
    from timezones import true_solar_datetime

    wall = datetime(1990, 5, 15, 14, 30)
    solar = true_solar_datetime(1990, 5, 15, 14, 30, 37.62, 4 * 15)
    b = bazi.build_chart_data(*solar[:5], gender="мужской", tz_off=4, as_of=wall.date())
    b["input"].update(date=wall.date().isoformat(), wall_time="14:30", city="Москва",
                      solar_date=wall.date().isoformat(), solar_day_shift=0)
    utc = wall.replace(tzinfo=timezone(timedelta(hours=4))).astimezone(timezone.utc)
    j = jyotish.build_chart(utc, 55.75, 37.62, as_of=utc,
                            meta={"birth_local": "1990-05-15 14:30 UTC+4"})
    as_of = date(2026, 11, 17)  # дата проверки, не ещё одно рождение
    data = build_signals(b, j, as_of=as_of)
    ok = True

    def chk(cond, label):
        nonlocal ok
        ok &= bool(cond)
        print(("  ✓ " if cond else "  ✗ ") + label)

    for kind in ("day_clash", "month_clash", "seven_killings", "hurting_officer_meets_officer"):
        actual = {s["year"] for s in data["signals"] if s["kind"] == kind}
        expected = set()
        for year in range(as_of.year - 15, as_of.year):
            si, branch = bazi.year_pillar(year)
            god = bazi.TEN_GODS[bazi.ten_god(b["day_master"]["index"], si)]
            natal = {g["name"] for g in b["ten_gods"] if g["weight"] > 0}
            if kind.endswith("_clash"):
                target = kind.split("_")[0]
                match = bazi.CLASHES[branch] == b["pillars"][target]["branch"]["index"]
            elif kind == "seven_killings":
                match = god == "七杀"
            else:
                match = (god == "正官" and "伤官" in natal) or (god == "伤官" and "正官" in natal)
            if match:
                expected.add(year)
        chk(actual == expected, f"{kind}: все годы и отсутствие лишних сверены с движком")
    dasha = [s for s in data["signals"] if s["kind"] == "mahadasha_change"]
    expected = [r for r in j["dasha_timeline"][1:] if data["input"]["window_from"] <= r["from"] < as_of.isoformat()]
    chk(len(dasha) == len(expected) and all(
        s["date"] == r["from"] and list(s["basis"]["fields"].values()) == [r["lord"], r["from"], r["to"]]
        for s, r in zip(dasha, expected)), "смены больших периодов: даты и основания ровно из dasha_timeline")
    synthetic = deepcopy(b)  # СИНТЕТИЧЕСКАЯ мутация метаданных солнечного сдвига, не другая карта
    synthetic["input"].update(solar_date=(wall.date() - timedelta(days=1)).isoformat(), solar_day_shift=-1)
    mutated = build_signals(synthetic, j, as_of=as_of)
    luck = [s for s in data["signals"] if s["kind"] == "luck_change"]
    expected_luck = [_luck_date(wall.date(), r["age_start"]).isoformat() for r in b["luck_pillars"]["pillars"]]
    chk(bool(luck) and data == mutated and all(s["date"] in expected_luck for s in luck),
        "удача: дата от настенного рождения, solar_date и solar_day_shift не сдвигают её повторно")
    chk(all(wall.year <= s["year"] <= as_of.year
            and (s["date"] is not None or s["year"] < as_of.year)
            and wall.date().isoformat() <= s["window"]["from"] <= s["window"]["to"] < as_of.isoformat()
            and (s["date"] is None or wall.date().isoformat() <= s["date"] < as_of.isoformat())
            for s in data["signals"]), "все сигналы в прошлом и не до рождения")
    chk(data == build_signals(b, j, as_of=as_of)
        and len({s["id"] for s in data["signals"]}) == len(data["signals"]), "детерминированность и уникальные ID")
    chk(not build_signals(b, j, as_of=wall.date())["signals"],
        "в день рождения прошлое пусто")
    boundary_ok = True
    for s in data["signals"]:
        if s["date"] is None:
            continue
        when = date.fromisoformat(s["date"])
        at = build_signals(b, j, as_of=when)
        after = build_signals(b, j, as_of=when + timedelta(days=1))
        found = next((row for row in after["signals"] if row["id"] == s["id"]), None)
        boundary_ok &= (not any(row["id"] == s["id"] for row in at["signals"])
                        and found is not None and found["window"]["to"] <= when.isoformat())
    chk(boundary_ok, "смены периодов: as_of исключён, на следующий день включены, окно обрезано")
    wide = build_signals(b, j, years=100, as_of=as_of)
    chk(all(s in wide["signals"] or s["kind"] == "luck_change" for s in data["signals"])
        and all(s["year"] >= wall.year for s in wide["signals"]), "длинное окно отсечено рождением")
    # СИНТЕТИЧЕСКИЙ пустой набор натальных богов: год 正官 в окне есть, пары нет.
    no_pair = deepcopy(b)
    no_pair["ten_gods"] = []
    negative = build_signals(no_pair, j, as_of=as_of)
    officer_years = {y for y in range(as_of.year - 15, as_of.year)
                     if bazi.TEN_GODS[bazi.ten_god(b["day_master"]["index"], bazi.year_pillar(y)[0])] == "正官"}
    chk(bool(officer_years) and not any(s["kind"] == "hurting_officer_meets_officer" for s in negative["signals"]),
        "год 正官 без натального 伤官 не объявляется 伤官见官")
    for natal_god, yearly in (("伤官", "正官"), ("正官", "伤官")):
        pair = deepcopy(no_pair)  # СИНТЕТИЧЕСКАЯ минимальная пара для обеих направленных веток
        pair["ten_gods"] = [{"name": natal_god, "weight": 1}]
        result = build_signals(pair, j, as_of=as_of)
        found = [s for s in result["signals"] if s["kind"] == "hurting_officer_meets_officer"]
        chk(bool(found) and all(s["basis"]["computed"]["pair"] == [yearly, natal_god] for s in found),
            f"пара: годовой {yearly} + натальное {natal_god}")
        pair["ten_gods"][0]["weight"] = 0
        chk(not any(s["kind"] == "hurting_officer_meets_officer"
                    for s in build_signals(pair, j, as_of=as_of)["signals"]),
            f"нулевой вес {natal_god} не создаёт пару")
    absent = deepcopy(b)
    absent["luck_pillars"] = None
    chk(any("luck_pillars=null" in s for s in build_signals(absent, j, as_of=as_of)["not_computed"]),
        "явный luck_pillars=null: честное not_computed")
    before = deepcopy(j)  # СИНТЕТИЧЕСКИЙ старт первого периода до рождения
    before["dasha_timeline"][0]["from"] = (wall.date() - timedelta(days=30)).isoformat()
    chk(all(s["date"] != before["dasha_timeline"][0]["from"] for s in build_signals(b, before, years=100, as_of=as_of)["signals"]),
         "первый период до рождения не выдан как смена")
    short = deepcopy(j)  # СИНТЕТИЧЕСКИЙ остаток менее суток, границы CLI — одна дата.
    short["dasha_timeline"][0]["to"] = short["dasha_timeline"][0]["from"]
    short["dasha_timeline"][1]["from"] = short["dasha_timeline"][0]["from"]
    chk(isinstance(build_signals(b, short, as_of=as_of)["signals"], list),
        "короткий первый остаток с одинаковыми from/to допустим")
    for time, offset in (("00:30", 4), ("23:30", -4)):
        bb, jj = deepcopy(b), deepcopy(short)  # СИНТЕТИЧЕСКИЙ перенос UTC-даты, не другая карта.
        bb["input"].update(wall_time=time, utc_offset=offset)
        jj["input"]["birth_local"] = f"1990-05-15 {time} UTC{offset:+g}"
        utc_day = (datetime.fromisoformat(f"1990-05-15 {time}") - timedelta(hours=offset)).date().isoformat()
        jj["dasha_timeline"][0].update({"from": utc_day, "to": utc_day})
        jj["dasha_timeline"][1]["from"] = utc_day
        chk(isinstance(build_signals(bb, jj, as_of=as_of)["signals"], list),
            f"первый короткий остаток проверяется по UTC-дате при {time} UTC{offset:+g}")
    bad = []
    for field, value in (("date", "мусор"), ("wall_time", "25:00"), ("utc_offset", float("nan"))):
        bb = deepcopy(b)
        bb["input"][field] = value
        bad.append((bb, j))
    for path, value in ((("day_master", "index"), 10), (("luck_pillars", "pillars", 0, "age_start"), "1"),
                        (("luck_pillars", "pillars", 0, "age_start"), 10**400),
                        (("luck_pillars", "pillars", 0, "age_start"), -1),
                        (("luck_pillars", "pillars"), []),
                        (("luck_pillars", "pillars", 1, "age_start"), 0),
                        (("day_master", "index"), True),
                        (("conventions",), {}),
                        (("ten_gods", 0, "weight"), float("inf")),
                        (("pillars", "day", "branch", "index"), -1)):
        bb = deepcopy(b)
        target = bb
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        bad.append((bb, j))
    missing = deepcopy(b)
    del missing["luck_pillars"]
    bad += [(missing, j), ([], j), ({"error": {}}, j)]
    missing_offset, wrong_offset = deepcopy(b), deepcopy(j)
    del missing_offset["input"]["utc_offset"]
    wrong_offset["input"]["birth_local"] = "1990-05-15 14:30 UTC+3"
    bad += [(missing_offset, j), (missing_offset, wrong_offset)]
    missing_wall = deepcopy(b)
    del missing_wall["input"]["wall_time"]
    bad.append((missing_wall, j))
    for local in (None, "1990-05-15 14:30", "1990-05-15 14:30 UTC+3",
                  (wall + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M") + " UTC+4"):
        jj = deepcopy(j)
        jj["input"]["birth_local"] = local
        bad.append((b, jj))
    jj = deepcopy(j)
    jj["dasha_timeline"][1]["from"] = "не дата"
    bad.append((b, jj))
    for field, value in (("lord", []), ("from", j["dasha_timeline"][0]["from"]),
                         ("to", "2026-02-30")):
        jj = deepcopy(j)
        jj["dasha_timeline"][1][field] = value
        bad.append((b, jj))
    rejected = 0
    for bb, jj in bad:
        try:
            build_signals(bb, jj, as_of=as_of)
        except cli_errors.InputError:
            rejected += 1
    for years, when in ((0, as_of), (101, as_of), (15, wall.date() - timedelta(days=1))):
        try:
            build_signals(b, j, years=years, as_of=when)
        except cli_errors.InputError:
            rejected += 1
    chk(rejected == len(bad) + 3, f"неверный/несовпадающий ввод: InputError {rejected}/{len(bad) + 3}")
    print(f"retro_signals: кандидатов — {len(data['signals'])}")
    print("retro_signals --test:", "ЗЕЛЕНО ✓" if ok else "КРАСНОЕ ✗")
    return ok


def main():
    if sys.argv[1:] == ["--test"]:
        return 0 if _test() else 1
    bp, jp, years, as_of, json_mode = parse_args(sys.argv[1:])
    result = build_signals(read_input(bp, "bazi"), read_input(jp, "jyotish"), years, as_of)
    if json_mode:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["source_note"])
        for s in result["signals"]:
            print(f"{s['id']} | {s['date'] or s['year']} | {s['question_ru']}")
        print(f"Кандидатов: {len(result['signals'])}.")
        print(result["honesty_note"])


if __name__ == "__main__":
    cli_errors.run(main)
