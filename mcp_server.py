#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""mcp_server.py — MCP-сервер над калькуляторами проекта (issue #21).

Один процесс (stdio) отдаёт любому MCP-клиенту (OpenCode, Claude Desktop, Cursor…) те же JSON, что получают
скиллы через CLI — без знания пути к репозиторию. Новой логики нет: каждый инструмент запускает
соответствующий калькулятор под `.venv/bin/python` и возвращает его `--json` как есть (включая все honesty-поля:
boundary_warnings, tz_note, conventions, fragile_activations, losar…). Образец — cantian-ai/bazi-mcp и
bazaar-of-fates (docs/related_projects.md §4 п. 6).

Запуск (stdio):           .venv/bin/python mcp_server.py
Самопроверка:             .venv/bin/python mcp_server.py --selftest   (функции + протокол в памяти, если mcp установлен)
Ошибки: функции-инструменты возвращают {"error": текст, "kind": input|internal} (так их читает веб-страница), а для
MCP-клиента обёртка _as_tool превращает отказ в результат с isError=true.
Подключение в OpenCode:   opencode mcp add bazi --global -- /abs/path/.venv/bin/python /abs/path/mcp_server.py (см. README)
Зависимость: pip install "mcp>=2" (в .venv проекта; не входит в requirements.txt — ставится по желанию).
"""
import json
import os
import subprocess
import sys
from typing import Any

DIR = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(DIR, ".venv", "bin", "python")
if not os.path.exists(PY):
    PY = sys.executable


TIMEOUT = 300   # секунд на один расчёт


def _run(script: str, args: list[str]) -> dict[str, Any]:
    """Запустить калькулятор и вернуть его JSON. Отказ — словарь {"error": текст, "kind": input|internal}:
    так его читают и веб-страница, и MCP (там он превращается в результат с isError, см. _as_tool)."""
    try:
        p = subprocess.run([PY, os.path.join(DIR, script), *args, "--json"], capture_output=True, text=True, cwd=DIR, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return {"error": f"{script} не ответил за {TIMEOUT} с", "kind": "internal", "script": script}
    try:
        data = json.loads(p.stdout) if p.stdout.strip() else None
    except json.JSONDecodeError:
        data = None
    if p.returncode != 0:
        # калькуляторы сообщают об ошибке по контракту cli_errors: конверт {"error": {kind, message}} + код 2/1
        env = data.get("error") if isinstance(data, dict) else None
        if isinstance(env, dict) and env.get("message"):
            return {"error": env["message"], "kind": env.get("kind", "internal"), "script": script}
        return {"error": p.stderr.strip()[-600:] or f"{script} завершился с кодом {p.returncode}",
                "kind": "input" if p.returncode == 2 else "internal", "script": script}
    if not isinstance(data, dict):
        return {"error": "калькулятор вернул не JSON", "kind": "internal", "script": script, "stdout": p.stdout[:300]}
    return data


def _tz_args(city: str | None, utc_offset: float | None) -> list[str]:
    if city:
        return ["--city", city]
    if utc_offset is None:
        return []
    return [f"UTC{utc_offset:+g}"]


# ── инструменты (чистые функции — их же дёргает --selftest) ───────────────────────────────────────

def bazi_chart(date: str, time: str | None = None, gender: str = "М", city: str | None = None,
               utc_offset: float | None = None, as_of: str | None = None) -> dict[str, Any]:
    """Карта Ба Цзы (八字): четыре столпа по точному 节气, скрытые стволы, 10 божеств, сила ХД, 用神/忌神, 调候,
    空亡, Шэнь Ша, столпы удачи, текущий год и динамика; honesty-поля boundary_warnings/tz_note/conventions.
    date ГГГГ-ММ-ДД; time ЧЧ:ММ (без времени — три столпа); gender М|Ж; city (предпочтительно: исторический
    пояс + истинное солнечное время) ИЛИ utc_offset; as_of ГГГГ-ММ-ДД — прогнозный год/удача на дату."""
    args = [date] + ([time] if time else []) + [gender] + _tz_args(city, utc_offset) + (["--as-of", as_of] if as_of else [])
    if not city and utc_offset is None:
        return {"error": "нужен city или utc_offset — без пояса Ба Цзы не считаем (issue #9)"}
    return _run("bazi.py", args)


def historical_utc_offset(city: str, date: str) -> dict[str, Any]:
    """Исторический UTC-оффсет и координаты города на дату (IANA tzdb + советские городские окна + алиасы
    Ленинград/Горький/Свердловск…). NOTE с «⚠» — обязательная оговорка чтения."""
    code = ("import json,sys; sys.path.insert(0, %r); from timezones import historical_utc_offset, resolve_city; from geo import resolve; "
            "y,m,d=map(int,%r.split('-')); off,note=historical_utc_offset(%r,y,m,d); city,_=resolve_city(%r); lat,lon=resolve(city); "
            "print(json.dumps({'city':city,'utc_offset':off,'note':note,'lat':lat,'lon':lon}, ensure_ascii=False))") % (DIR, date, city, city)
    p = subprocess.run([PY, "-c", code], capture_output=True, text=True, cwd=DIR, timeout=60)
    if p.returncode != 0:
        return {"error": p.stderr.strip()[-400:]}
    return json.loads(p.stdout)


def _place(city, date, lat, lon, utc_offset):
    """city → (lat, lon, utc_offset, tz_note) через historical_utc_offset; без city — как передано."""
    if city:
        r = historical_utc_offset(city, date)
        if "error" in r:
            return None, None, None, r["error"]
        return r["lat"], r["lon"], r["utc_offset"], r.get("note")
    return lat, lon, utc_offset, None


def _with_tz_note(res, note):
    if note and isinstance(res, dict) and "error" not in res:
        res.setdefault("input", {})["tz_note"] = note
    return res


def jyotish_chart(date: str, time: str, lat: float | None = None, lon: float | None = None, utc_offset: float | None = None,
                  city: str | None = None, as_of: str | None = None) -> dict[str, Any]:
    """Джйотиш: Лагна, 9 грах по раши/накшатрам/домам, Вимшоттари даша, йоги, тропический «западный взгляд».
    Лахири, знаковые дома, средний Раху (conventions в ответе). Место: city (исторический пояс + координаты из базы)
    ИЛИ lat/lon/utc_offset явно."""
    lat, lon, utc_offset, note = _place(city, date, lat, lon, utc_offset)
    if lat is None or utc_offset is None:
        return {"error": note or "нужны city или lat+lon+utc_offset"}
    return _with_tz_note(_run("jyotish.py", [date, time, str(lat), str(lon), f"{utc_offset:+g}"] + (["--as-of", as_of] if as_of else [])), note)


def human_design_chart(date: str, time: str, utc_offset: float | None = None, city: str | None = None) -> dict[str, Any]:
    """Дизайн Человека: Тип, Стратегия, Авторитет, Профиль, центры, каналы, крест, PHS; fragile_activations
    (хрупкость к минутам), convention_warnings (узлы true/mean). Время критично. Пояс: city (исторический) или utc_offset."""
    _, _, utc_offset, note = _place(city, date, None, None, utc_offset)
    if utc_offset is None:
        return {"error": note or "нужны city или utc_offset"}
    return _with_tz_note(_run("hd.py", [date, time, f"{utc_offset:+g}"]), note)


def gene_keys_profile(date: str, time: str, utc_offset: float | None = None, city: str | None = None) -> dict[str, Any]:
    """Генные Ключи: 11 сфер Голограммы, Тень → Дар → Сиддхи, программные партнёры; spectrum_provenance.
    Пояс: city (исторический) или utc_offset."""
    _, _, utc_offset, note = _place(city, date, None, None, utc_offset)
    if utc_offset is None:
        return {"error": note or "нужны city или utc_offset"}
    return _with_tz_note(_run("gene_keys.py", [date, time, f"{utc_offset:+g}"]), note)


def bazi_find_dates(year_pillar: str, month_pillar: str, day_pillar: str, hour_pillar: str | None = None,
                    year_from: int = 1900, year_to: int = 2100, utc_offset: float = 8) -> dict[str, Any]:
    """Обратный поиск по столпам Ба Цзы (ректификация): даты (и двухчасовые окна, если дан час), когда бывают
    заданные 干支 — год каждые 60 лет, месяц по точным 节, день по 60-дневному циклу. Несогласованные столпы
    (五虎遁/五鼠遁) → пустой список с причиной. Столпы — иероглифами, например «庚午» «辛巳» «庚辰» «癸未»."""
    args = [year_pillar, month_pillar, day_pillar] + ([hour_pillar] if hour_pillar else []) + \
           ["--from", str(year_from), "--to", str(year_to), f"UTC{utc_offset:+g}"]
    return _run("bazi_reverse.py", args)


def tibetan_year(date: str, as_of: str | None = None) -> dict[str, Any]:
    """Джунгци (тибетская): знак года (животное + стихия), Меуа, 5 сил, обструктивные годы; граница года по
    фактическому Лосару (Пхугпа) — losar.bazi_divergence, alt_if_before_losar."""
    return _run("tibetan.py", [date] + (["--as-of", as_of] if as_of else []))


def qimen_board(datetime_local: str, utc_offset: float, method: str = "chaibu") -> dict[str, Any]:
    """Ци Мэнь Дунь Цзя: доска 9 дворцов на момент (时家, 转盘) — 地盘/天盘/九星/八门/八神, 值符/值使;
    meta.conventions. datetime_local — «ГГГГ-ММ-ДД ЧЧ:ММ»; method — chaibu (拆补, сверен с kinqimen) | zhirun
    (置闰 超神接气; в ответе meta.ju_term и meta.chaojie)."""
    parts = datetime_local.split()
    if len(parts) != 2:
        return {"error": "datetime_local — «ГГГГ-ММ-ДД ЧЧ:ММ» (дата и время через пробел)", "kind": "input"}
    return _run("qimen.py", [*parts, f"UTC{utc_offset:+g}", "--method", method])


def ziwei_chart(lunar_year: int, lunar_month: int, lunar_day: int, hour: int, gender: str = "М") -> dict[str, Any]:
    """Цзы Вэй Доу Шу по ЛУННОЙ дате: 命宫, 身宫, 五行局, 12 дворцов с главными/вспомогательными звёздами и 四化
    (сверено с iztro). hour — час 0–23 местного времени."""
    return _run("ziwei.py", ["--lunar", str(lunar_year), str(lunar_month), str(lunar_day), str(hour), gender])


def meihua_cast(numbers: list[int] | None = None, datetime_local: str | None = None, lunar: list[int] | None = None,
                minutes_mode: bool = False, month: int | None = None) -> dict[str, Any]:
    """Мэй Хуа И Шу (梅花易数): гексаграмма по 2–3 числам (numbers) ИЛИ по моменту datetime_local «ГГГГ-ММ-ДД ЧЧ:ММ»
    (лунная дата — lunar-python, либо lunar=[год, месяц, день] явно). Отдаёт 本卦/变卦/互卦/错卦/综卦, 动爻, 体/用 и их
    отношение, 卦气 (month — лунный месяц для расчёта по числам). minutes_mode — современное расширение (помечается)."""
    if numbers:
        args = ["--numbers", *map(str, numbers)] + (["--month", str(month)] if month else [])
    elif datetime_local:
        parts = datetime_local.split()
        if len(parts) != 2:
            return {"error": "datetime_local — «ГГГГ-ММ-ДД ЧЧ:ММ» (дата и время через пробел)", "kind": "input"}
        d, t = parts
        args = ["--time", d, t] + (["--lunar", *map(str, lunar)] if lunar else []) + (["--minutes"] if minutes_mode else [])
    else:
        return {"error": "нужны numbers или datetime_local"}
    return _run("meihua.py", args)


TOOLS = [bazi_chart, historical_utc_offset, jyotish_chart, human_design_chart, gene_keys_profile, tibetan_year,
         qimen_board, ziwei_chart, meihua_cast, bazi_find_dates]


def _selftest() -> int:
    ok = True
    r = historical_utc_offset("Москва", "1990-05-15"); ok &= r.get("utc_offset") == 4; print("✓" if r.get("utc_offset") == 4 else "✗", "historical_utc_offset Москва 1990 →", r.get("utc_offset"), r.get("lat"), r.get("lon"))
    r = bazi_chart("1990-05-15", "14:30", "М", city="Москва"); good = r.get("pillars", {}).get("day", {}).get("name") == "庚辰"; ok &= good; print("✓" if good else "✗", "bazi_chart день", r.get("pillars", {}).get("day", {}).get("name"), "| conventions:", bool(r.get("conventions")))
    r = bazi_chart("1990-05-15", "14:30", "М"); good = "error" in r; ok &= good; print("✓" if good else "✗", "bazi_chart без пояса → ошибка:", r.get("error", "")[:40])
    r = jyotish_chart("1990-05-15", "14:30", 55.75, 37.62, 4); good = r.get("lagna", {}).get("rashi") == "Лев"; ok &= good; print("✓" if good else "✗", "jyotish_chart Лагна", r.get("lagna", {}).get("rashi"))
    r = human_design_chart("1990-05-15", "14:30", 4); good = r.get("type") == "Проектор" and r.get("profile") == "6/2"; ok &= good; print("✓" if good else "✗", "human_design_chart", r.get("type"), r.get("profile"))
    r = gene_keys_profile("1990-05-15", "14:30", 4); good = "spheres" in r; ok &= good; print("✓" if good else "✗", "gene_keys_profile spheres:", len(r.get("spheres", [])) if isinstance(r.get("spheres"), (list, dict)) else r.get("error"))
    r = tibetan_year("1990-05-15"); good = "year_sign" in r; ok &= good; print("✓" if good else "✗", "tibetan_year", r.get("year_sign"))
    r = qimen_board("2026-04-08 14:30", 8); good = r.get("meta", {}).get("ju") == 4; ok &= good; print("✓" if good else "✗", "qimen_board 局", r.get("meta", {}).get("ju"))
    r = ziwei_chart(1990, 4, 15, 14, "М"); good = r.get("zi_wei", {}).get("branch") == "辰"; ok &= good; print("✓" if good else "✗", "ziwei_chart 紫微", r.get("zi_wei", {}).get("branch"))
    r = meihua_cast(numbers=[17, 29]); good = r.get("ben_gua", {}).get("number") == 44; ok &= good; print("✓" if good else "✗", "meihua_cast 17 29 →", r.get("ben_gua", {}).get("number"), r.get("ben_gua", {}).get("name"))
    r = human_design_chart("1990-05-15", "14:30", city="Москва"); good = r.get("type") == "Проектор" and "UTC+4" in (r.get("input", {}).get("tz_note") or ""); ok &= good; print("✓" if good else "✗", "human_design_chart city=Москва →", r.get("type"), "| tz_note:", (r.get("input", {}).get("tz_note") or "")[:40])
    r = jyotish_chart("1990-05-15", "14:30", city="Москва"); good = r.get("lagna", {}).get("rashi") == "Лев"; ok &= good; print("✓" if good else "✗", "jyotish_chart city=Москва → Лагна", r.get("lagna", {}).get("rashi"))
    r = bazi_find_dates("庚午", "辛巳", "庚辰", "癸未", 1980, 2000, 4); good = [m["date"] for m in r.get("matches", [])] == ["1990-05-15"]; ok &= good; print("✓" if good else "✗", "bazi_find_dates 庚午 辛巳 庚辰 癸未 →", [(m["date"], m["hours"]) for m in r.get("matches", [])])
    r = qimen_board("2026-04-08 14:30", 5.5); good = r.get("input", {}).get("utc_offset") == 5.5; ok &= good; print("✓" if good else "✗", "qimen_board дробный пояс UTC+5.5 →", r.get("input", {}).get("utc_offset"))
    r = ziwei_chart(1990, 13, 15, 14, "М"); good = r.get("kind") == "input" and "месяц" in r.get("error", ""); ok &= good; print("✓" if good else "✗", "ziwei_chart лунный месяц 13 → отказ:", r.get("error", "")[:50])
    ok &= _selftest_protocol()
    print("mcp_server --selftest:", "ЗЕЛЕНО ✓" if ok else "КРАСНОЕ ✗")
    return 0 if ok else 1


def _as_tool(fn):
    """Обёртка инструмента для MCP: отказ калькулятора ({"error": …}) и кривые аргументы становятся ToolError —
    клиент получает результат с isError=true и текстом причины, а не «успешный» JSON с ключом error."""
    import functools
    from mcp.server.mcpserver.exceptions import ToolError

    @functools.wraps(fn)
    def tool(*args, **kwargs):
        try:
            result = fn(*args, **kwargs)
        except (ValueError, TypeError, KeyError) as exc:
            raise ToolError(f"неверные аргументы: {exc}") from exc
        if isinstance(result, dict) and "error" in result:
            raise ToolError(str(result["error"]))
        return result
    return tool


def build_server():
    """Собрать MCP-сервер (без запуска транспорта) — его же поднимает в памяти --selftest."""
    from mcp.server.mcpserver import MCPServer
    from mcp.types import ToolAnnotations
    server = MCPServer(name="bazi", instructions=(
        "Калькуляторы китайской и ведической метафизики (Swiss Ephemeris). Считает код; интерпретация — за "
        "клиентом. Пояс для Ба Цзы задавай городом (historical_utc_offset/city) — исторические пояса СССР и "
        "истинное солнечное время учитываются сами. Все оговорки (boundary_warnings, tz_note, conventions, "
        "fragile_activations, losar.*) — обязательная часть чтения."))
    # все инструменты — чистые локальные расчёты: ничего не меняют, в сеть не ходят
    hints = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
    for fn in TOOLS:
        server.tool(annotations=hints)(_as_tool(fn))
    return server


def _selftest_protocol() -> bool:
    """Проверка через сам протокол MCP (клиент и сервер в памяти): список инструментов, схемы, успех и isError."""
    try:
        import anyio
        from mcp import Client, StdioServerParameters
    except ImportError:
        print("~ пакет mcp не установлен — проверка по протоколу пропущена (pip install 'mcp>=2')")
        return True
    import logging
    logging.getLogger("mcp").setLevel(logging.WARNING)   # ожидаемые отказы инструментов не шумят в выводе проверки
    ok = True

    def chk(cond, label):
        nonlocal ok
        ok &= bool(cond)
        print(("✓" if cond else "✗"), label)

    async def go():
        async with Client(build_server()) as client:
            tools = (await client.list_tools()).tools
            names = sorted(t.name for t in tools)
            chk(names == sorted(fn.__name__ for fn in TOOLS), f"MCP tools/list: {len(tools)} инструментов, имена совпадают с TOOLS")
            chk(all(t.input_schema.get("type") == "object" and t.description for t in tools), "у каждого инструмента есть описание и схема входа")
            chk(all(t.annotations and t.annotations.read_only_hint and t.annotations.open_world_hint is False for t in tools),
                "аннотации: только чтение, без выхода в сеть")
            bazi = next(t for t in tools if t.name == "bazi_chart")
            chk(set(bazi.input_schema.get("required", [])) == {"date"} and "city" in bazi.input_schema["properties"],
                "схема bazi_chart выведена из сигнатуры функции (date обязателен, city есть)")
            r = await client.call_tool("bazi_chart", {"date": "1990-05-15", "time": "14:30", "gender": "М", "city": "Москва"})
            chk(not r.is_error and (r.structured_content or {}).get("pillars", {}).get("day", {}).get("name") == "庚辰",
                "MCP bazi_chart → structuredContent со столпом дня 庚辰, isError=false")
            r = await client.call_tool("bazi_chart", {"date": "1990-05-15", "time": "14:30", "gender": "М"})
            chk(r.is_error and "city" in r.content[0].text, f"MCP bazi_chart без пояса → isError=true: {r.content[0].text[:50]}")
            r = await client.call_tool("bazi_chart", {"date": "1990-05-15", "time": "14:30", "gender": "М", "city": "Нетакого"})
            chk(r.is_error and "не найден" in r.content[0].text, f"MCP неизвестный город → isError=true: {r.content[0].text[:50]}")
            r = await client.call_tool("qimen_board", {"datetime_local": "2026-04-08 14:30", "utc_offset": 5.5})
            chk(not r.is_error and (r.structured_content or {}).get("input", {}).get("utc_offset") == 5.5, "MCP qimen_board с дробным поясом UTC+5.5 считается")
            r = await client.call_tool("qimen_board", {"datetime_local": "без-времени", "utc_offset": 3})
            chk(r.is_error and "ГГГГ-ММ-ДД" in r.content[0].text, f"MCP кривая дата → isError=true с подсказкой формата: {r.content[0].text[-45:]}")
        # настоящий процесс по stdio: stdout сервера чист для протокола, запуск и завершение проходят штатно
        async with Client(StdioServerParameters(command=PY, args=[os.path.abspath(__file__)], cwd=DIR)) as client:
            tools = (await client.list_tools()).tools
            r = await client.call_tool("historical_utc_offset", {"city": "Москва", "date": "1990-05-15"})
            chk(len(tools) == len(TOOLS) and not r.is_error and (r.structured_content or {}).get("utc_offset") == 4,
                f"MCP по stdio (отдельный процесс): {len(tools)} инструментов, historical_utc_offset → UTC+4")

    anyio.run(go)
    return ok


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    try:
        server = build_server()
    except ImportError:
        print("Нужен пакет mcp ≥ 2: .venv/bin/pip install 'mcp>=2'", file=sys.stderr)
        return 2
    server.run("stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
