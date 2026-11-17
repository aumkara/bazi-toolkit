#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""time_window.py — окно устойчивости показателей к минуте рождения.

time_window.py ГГГГ-ММ-ДД ЧЧ:ММ ШИРОТА ДОЛГОТА ОФФСЕТ [--span МИНУТ] [--json]
time_window.py --test
"""
import json
import math
import re
import sys
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import bazi  # ephemeris внутри обеспечивает общий бутстрап под .venv
import cli_errors
import hd
import jyotish
from timezones import true_solar_datetime


# Ключи уникальны и служат ссылками из limited_by_* на items.
ITEMS = (
    ("hd", "type", "Тип", "основа описания в Дизайне Человека"),
    ("hd", "authority", "Авторитет", "способ принятия решений в Дизайне Человека"),
    ("hd", "profile", "Профиль", "описание жизненной роли в Дизайне Человека"),
    ("jyotish", "lagna", "Знак Лагны", "восходящий знак"),
    ("jyotish", "moon_nakshatra", "Накшатра Луны", "лунный раздел карты"),
    ("bazi", "hour_pillar", "Часовой столп", "расчёт Ба Цзы по часу рождения"),
    ("bazi", "day_pillar", "Столп дня", "расчёт Ба Цзы по дню рождения"),
)
HONESTY_NOTE = (
    "Это сетка сдвигов времени рождения от указанной даты при том же месте и фиксированном "
    "UTC-смещении; через полночь дата меняется. Это не ректификация и не доказательство "
    "точности записанного времени. Шаг 5 минут может пропустить значение, которое менялось "
    "и вернулось внутри шага; найденная граница уточняется до целой минуты. "
    "Границы окна — последние проверенные целые минуты с базовыми показателями, "
    "а не точные секунды перехода. null означает отсутствие найденного перехода в пределах "
    "span_minutes, а не неограниченную устойчивость. Проверены только перечисленные показатели; "
    "линии, сферы, месячный и годовой столпы сюда не входят. Солнечная поправка Ба Цзы — "
    "из timezones.py, с его приближением уравнения времени."
)


def _solar(wall, lon, offset):
    return true_solar_datetime(wall.year, wall.month, wall.day, wall.hour, wall.minute,
                               lon, offset * 15)


def _charts(wall, lat, lon, offset):
    utc = wall.replace(tzinfo=timezone(timedelta(hours=offset))).astimezone(timezone.utc)
    return hd.build_chart(utc), jyotish.build_chart(utc, lat, lon, as_of=utc)


def _values(wall, lat, lon, offset):
    """Только готовые движки; полную аналитику Ба Цзы для двух столпов не строим."""
    h, j = _charts(wall, lat, lon, offset)
    y, m, d, hour, _minute, _correction, _shift = _solar(wall, lon, offset)
    ds, db = bazi.day_pillar(y, m, d)
    hs, hb = bazi.hour_pillar(ds, hour)
    return {
        "type": h["type"], "authority": h["authority"], "profile": h["profile"],
        "lagna": j["lagna"]["rashi"],
        "moon_nakshatra": j["moon_nakshatra"]["nakshatra"],
        "hour_pillar": bazi.pillar_json("hour", hs, hb)["name"],
        "day_pillar": bazi.pillar_json("day", ds, db)["name"],
    }


def _window(wall, items, span):
    out = {}
    for side, name, sign, edge in (("earlier", "before", -1, "from"),
                                   ("later", "after", 1, "to")):
        transitions = [i[side]["minutes"] for i in items if i[side] is not None]
        nearest = min(transitions) if transitions else None
        stable = nearest - 1 if nearest is not None else None
        limit = wall + timedelta(minutes=sign * (stable if stable is not None else span))
        out[edge] = limit.strftime("%H:%M")
        # Дата необходима для окна через полночь: одних ЧЧ:ММ недостаточно.
        out[edge + "_date"] = limit.date().isoformat()
        out["minutes_" + name] = stable
        out["limited_by_" + name] = [
            i["key"] for i in items if i[side] is not None and i[side]["minutes"] == nearest
        ]
    return out


def _summary(wall, window, span):
    labels = {key: plain for _system, key, _label, plain in ITEMS}

    def edge(name):
        date = window[name + "_date"]
        return (date + " " if date != wall.date().isoformat() else "") + window[name]

    changes = []
    for name, direction in (("before", "раньше"), ("after", "позже")):
        minutes = window["minutes_" + name]
        if minutes is None:
            changes.append(f"{direction} в пределах {span} минут изменений не найдено")
        else:
            what = ", ".join(labels[k] for k in window["limited_by_" + name])
            changes.append(f"при сдвиге на {minutes + 1} мин {direction} меняется: {what}")
    changes[0] = changes[0][0].upper() + changes[0][1:]
    return (f"В проверенной сетке профиль по выбранным показателям остаётся тем же "
            f"при времени рождения от {edge('from')} до {edge('to')}. "
            + "; ".join(changes) + ".")


def _validate(wall, lat, lon, offset, span):
    """Вызовы из Python тоже получают InputError до входа в движки."""
    if (not isinstance(wall, datetime) or wall.tzinfo is not None
            or wall.second or wall.microsecond):
        raise cli_errors.InputError("нужны местные дата и время с точностью до минуты, без пояса в дате")
    # Moshier в ephem_core работает до 3000 года; нужен запас для сетки и точки Дизайна.
    if not 2 <= wall.year <= 2999:
        raise cli_errors.InputError("год должен быть от 2 до 2999 (диапазон движков с запасом для сетки)")
    for value, low, high, label in ((lat, -90, 90, "широта"), (lon, -180, 180, "долгота"),
                                    (offset, -24, 24, "оффсет UTC")):
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            raise cli_errors.InputError(f"{label}: нужно конечное число")
        if not low <= value <= high or (label != "долгота" and value in (low, high)):
            raise cli_errors.InputError(f"{label}: вне допустимого диапазона {low}…{high}")
    if isinstance(span, bool) or not isinstance(span, int) or not 10 <= span <= 360:
        raise cli_errors.InputError("--span должен быть целым числом от 10 до 360 минут")


def build_window(wall, lat, lon, offset, span=120):
    _validate(wall, lat, lon, offset, span)

    @lru_cache(maxsize=None)
    def at(shift):
        return _values(wall + timedelta(minutes=shift), lat, lon, offset)

    base = at(0)
    items = [dict(system=s, key=k, label_ru=label, value=base[k], earlier=None, later=None)
             for s, k, label, _plain in ITEMS]
    grid = list(range(5, span + 1, 5))
    if grid[-1] != span:
        grid.append(span)
    for side, sign in (("earlier", -1), ("later", 1)):
        previous = 0
        for step in grid:
            values = at(sign * step)
            for item in items:
                key = item["key"]
                if item[side] is not None or values[key] == base[key]:
                    continue
                lo, hi = previous, step
                while hi - lo > 1:
                    mid = (lo + hi) // 2
                    if at(sign * mid)[key] == base[key]:
                        lo = mid
                    else:
                        hi = mid
                moment = wall + timedelta(minutes=sign * hi)
                item[side] = {"minutes": hi, "value": at(sign * hi)[key],
                              "wall_time": moment.strftime("%H:%M"), "date": moment.date().isoformat()}
            previous = step
    stable = _window(wall, items, span)
    h, j = _charts(wall, lat, lon, offset)
    return {
        "input": {"date": wall.date().isoformat(), "time": wall.strftime("%H:%M"),
                  "latitude": lat, "longitude": lon, "utc_offset": offset, "span_minutes": span},
        "items": items,
        "stable_window": stable,
        "stable_window_core": _window(wall, [i for i in items if i["key"] != "moon_nakshatra"], span),
        "summary_ru": _summary(wall, stable, span),
        "precision_minutes": 1,
        "honesty_note": HONESTY_NOTE,
        "conventions": {"hd": h["node_convention"], "jyotish": j["conventions"],
                        "bazi": bazi.conventions_now()},
    }


def parse_args(args):
    args = list(args)
    json_mode = "--json" in args
    if json_mode:
        args.remove("--json")
    span = 120
    try:
        if "--span" in args:
            pos = args.index("--span")
            span = int(args[pos + 1])
            del args[pos:pos + 2]
        if len(args) != 5:
            raise cli_errors.InputError(__doc__.splitlines()[2])
        date, time, lat, lon, offset = args
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) or not re.fullmatch(r"\d{2}:\d{2}", time):
            raise cli_errors.InputError("ожидались дата ГГГГ-ММ-ДД и время ЧЧ:ММ")
        wall = datetime.fromisoformat(f"{date} {time}")
        lat, lon = float(lat), float(lon)
        offset = float(offset.upper().removeprefix("UTC").removeprefix("+"))
    except (ValueError, IndexError, OverflowError) as exc:
        raise cli_errors.InputError("неверная дата, время, координаты, пояс или --span") from exc
    _validate(wall, lat, lon, offset, span)
    return wall, lat, lon, offset, span, json_mode


def _test():
    ok = True

    def chk(cond, label):
        nonlocal ok
        ok &= bool(cond)
        print(("  ✓ " if cond else "  ✗ ") + label)

    wall = datetime(1990, 5, 15, 14, 30)
    lat, lon, offset = 55.75, 37.62, 4

    @lru_cache(maxsize=None)
    def direct(shift):
        moment = wall + timedelta(minutes=shift)
        h, j = _charts(moment, lat, lon, offset)
        solar = _solar(moment, lon, offset)
        b = bazi.build_chart_data(*solar[:5], tz_off=offset, as_of=wall.date())
        return {"type": h["type"], "authority": h["authority"], "profile": h["profile"],
                "lagna": j["lagna"]["rashi"], "moon_nakshatra": j["moon_nakshatra"]["nakshatra"],
                "hour_pillar": b["pillars"]["hour"]["name"], "day_pillar": b["pillars"]["day"]["name"]}

    data = build_window(wall, lat, lon, offset)
    chk(all(i["value"] == direct(0)[i["key"]] for i in data["items"]),
        "база совпадает с полными картами трёх движков")
    count = 0
    for item in data["items"]:
        for side, sign in (("earlier", -1), ("later", 1)):
            event = item[side]
            if event is None:
                continue
            n, key = event["minutes"], item["key"]
            moment = wall + timedelta(minutes=sign * n)
            chk(direct(sign * (n - 1))[key] == item["value"]
                and direct(sign * n)[key] == event["value"] != item["value"]
                and event["date"] == moment.date().isoformat()
                and event["wall_time"] == moment.strftime("%H:%M"),
                f"{key}, {side}: на {n - 1} мин база, на {n} мин новое значение")
            count += 1
    solar = _solar(wall, lon, offset)
    warnings = bazi.boundary_warnings(*solar[:5], offset)
    hour = next(i for i in data["items"] if i["key"] == "hour_pillar")
    # Предупреждение округляет солнечное время вниз: назад граница включена
    # в текущий час, поэтому новое значение появляется на следующей целой минуте.
    chk(any(w["pillar"] == "hour" and w["detail"].startswith("4 мин") for w in warnings)
        and hour["earlier"]["minutes"] == 5, "Ба Цзы: «4 мин до границы», смена назад на 5-й минуте")
    for field in ("stable_window", "stable_window_core"):
        selected = [i for i in data["items"] if field == "stable_window" or i["key"] != "moon_nakshatra"]
        for side, name, sign, edge in (("earlier", "before", -1, "from"), ("later", "after", 1, "to")):
            events = [i[side]["minutes"] for i in selected if i[side]]
            nearest = min(events) if events else None
            expected = nearest - 1 if nearest is not None else None
            bound = wall + timedelta(minutes=sign * (expected if expected is not None else 120))
            chk(data[field]["minutes_" + name] == expected
                and data[field]["limited_by_" + name] ==
                [i["key"] for i in selected if i[side] and i[side]["minutes"] == nearest]
                and data[field][edge] == bound.strftime("%H:%M")
                and data[field][edge + "_date"] == bound.date().isoformat(),
                f"{field}, {name}: минимум по показателям и последняя устойчивая минута")
    short = build_window(wall, lat, lon, offset, span=10)
    chk(all(s[side] == (i[side] if i[side] and i[side]["minutes"] <= 10 else None)
            for s, i in zip(short["items"], data["items"]) for side in ("earlier", "later")),
        "--span 10: дальние переходы дают null")
    clipped = build_window(wall, lat, lon, offset, span=51)
    chk(next(i for i in clipped["items"] if i["key"] == "lagna")["later"]["minutes"] == 51,
        "последний неполный шаг сетки: переход ровно на краю --span")
    # Сдвигаем ту же фикстуру: солнечная и настенная полночь — разные события.
    shifted = wall + timedelta(hours=9)
    midnight = build_window(shifted, lat, lon, offset)
    day = next(i for i in midnight["items"] if i["key"] == "day_pillar")
    event = day["later"]
    n = event["minutes"]
    chk(day["value"] == direct(540)["day_pillar"]
        and direct(540 + n - 1)["day_pillar"] == day["value"]
        and direct(540 + n)["day_pillar"] == event["value"] != day["value"]
        and event["date"] == (shifted + timedelta(minutes=n)).date().isoformat()
        and event["date"] != wall.date().isoformat()
        and midnight["stable_window"]["from_date"] != midnight["stable_window"]["to_date"],
        "сдвиг той же фикстуры через полночь: дата перехода и солнечный столп дня")
    good = ["1990-05-15", "14:30", "55.75", "37.62", "+4"]
    bad = [[], good + ["--span"], good + ["--span", "9"], good + ["--span", "361"],
           ["1990-05-15", "25:00", *good[2:]], [*good[:2], "nan", *good[3:]],
           [*good[:3], "181", "+4"], [*good[:4], "inf"], good + ["--unknown"]]
    for args in bad:
        try:
            parse_args(args)
        except cli_errors.InputError:
            continue
        chk(False, f"неверный ввод не отклонён: {args}")
    chk(all(parse_args(good)[i] == v for i, v in enumerate((wall, lat, lon, offset, 120))),
        "валидный ввод разобран; неверный ввод проверен на InputError")
    print(f"time_window: проверено переходов — {count}")
    print("time_window --test:", "ЗЕЛЕНО ✓" if ok else "КРАСНОЕ ✗")
    return ok


def main():
    if sys.argv[1:] == ["--test"]:
        return 0 if _test() else 1
    wall, lat, lon, offset, span, json_mode = parse_args(sys.argv[1:])
    data = build_window(wall, lat, lon, offset, span)
    if json_mode:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print("Показатель | Значение | Раньше | Позже")
        for item in data["items"]:
            def fmt(event):
                if event is None:
                    return f"не найдено в пределах {span} мин"
                return f"{event['minutes']} мин → {event['value']} ({event['date']} {event['wall_time']})"
            print(f"{item['label_ru']} | {item['value']} | {fmt(item['earlier'])} | {fmt(item['later'])}")
        print(data["summary_ru"])
        print(data["honesty_note"])


if __name__ == "__main__":
    cli_errors.run(main)
