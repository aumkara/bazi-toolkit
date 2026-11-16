#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""web.py — локальная веб-версия калькулятора Ба Цзы (только стандартная библиотека).

Запуск:    .venv/bin/python web.py                  → http://127.0.0.1:8765 (откроется в браузере)
           .venv/bin/python web.py --port 9000 --no-browser
Проверка:  .venv/bin/python web.py --selftest

Форма → `bazi.py --json` (тот же путь, что у скилла и MCP-сервера: mcp_server.bazi_chart) → страница с картой
и отчёт .md из bazi_report.py, разделы которого выбираются галочками. Новой логики расчёта здесь нет.
Сервер слушает только 127.0.0.1: данные рождения не покидают компьютер, не пишутся на диск и не попадают в лог.
"""
import json
import os
import re
import sys
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DIR = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(DIR, "web")
HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_BODY = 16 * 1024
YEARS = (1900, 2100)          # диапазон, на котором сверены 节气 и пояса
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


def _bootstrap():
    """Запущен не из .venv проекта — перезапуститься под ним: движку нужен swisseph, а коду — Python ≥ 3.10."""
    venv = os.path.join(DIR, ".venv")
    py = os.path.join(venv, "bin", "python")
    if os.path.exists(py) and os.path.realpath(sys.prefix) != os.path.realpath(venv) and not os.environ.get("BAZI_WEB_NO_REEXEC"):
        os.execv(py, [py, os.path.abspath(__file__), *sys.argv[1:]])


class BadRequest(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _city_index():
    from timezones import CITIES, CITY_ALIASES
    names = sorted(CITIES) + sorted(CITY_ALIASES)
    return names, {n.lower().replace("ё", "е"): n for n in names}


def _iso_date(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise BadRequest(f"{label}: нужен формат ГГГГ-ММ-ДД")
    try:
        d = date.fromisoformat(value)
    except ValueError:
        raise BadRequest(f"{label}: такой даты нет в календаре")
    if not YEARS[0] <= d.year <= YEARS[1]:
        raise BadRequest(f"{label}: поддерживаются годы {YEARS[0]}–{YEARS[1]}")
    return value


def parse_params(body, city_lookup):
    """Проверить ввод формы и вернуть аргументы для bazi_chart. Всё, что не прошло проверку, — BadRequest."""
    if not isinstance(body, dict):
        raise BadRequest("ожидается JSON-объект")
    out = {"date": _iso_date(body.get("date"), "Дата рождения")}
    time = body.get("time")
    if time in (None, ""):
        out["time"] = None
    elif isinstance(time, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", time):
        out["time"] = time
    else:
        raise BadRequest("Время: нужен формат ЧЧ:ММ или пусто, если время неизвестно")
    gender = {"М": "М", "Ж": "Ж", "M": "М", "F": "Ж"}.get(body.get("gender") if isinstance(body.get("gender"), str) else "")
    if not gender:
        raise BadRequest("Пол: М или Ж (нужен для направления столпов удачи)")
    out["gender"] = gender
    city, offset = body.get("city"), body.get("utc_offset")
    if city not in (None, "") and offset not in (None, ""):
        raise BadRequest("Задайте что-то одно: город из базы или пояс вручную")
    if city not in (None, ""):
        key = city.strip().lower().replace("ё", "е") if isinstance(city, str) else ""
        if key not in city_lookup:
            raise BadRequest("Этого города нет в базе: выберите из списка или задайте пояс вручную")
        out["city"], out["utc_offset"] = city_lookup[key], None
    elif offset not in (None, ""):
        if isinstance(offset, bool) or not isinstance(offset, (int, float)) or not -12 <= offset <= 14 or (offset * 4) % 1:
            raise BadRequest("Пояс: число от −12 до +14 с шагом 0.25 (например 3 или 5.5)")
        out["city"], out["utc_offset"] = None, offset
    else:
        raise BadRequest("Нужен город из базы или пояс UTC: без пояса Ба Цзы не считается")
    as_of = body.get("as_of")
    out["as_of"] = _iso_date(as_of, "Дата прогноза") if as_of not in (None, "") else None
    return out


def compute(params):
    """Параметры формы → ответ API: карта (JSON движка как есть), оговорки и разделы отчёта (md + html)."""
    import bazi_report
    import md2html
    from mcp_server import bazi_chart
    chart = bazi_chart(params["date"], params["time"], params["gender"], city=params["city"],
                       utc_offset=params["utc_offset"], as_of=params["as_of"])
    if not isinstance(chart, dict) or "error" in chart or "pillars" not in chart:
        raise BadRequest("Калькулятор отказался считать: " + str((chart or {}).get("error", "неизвестная ошибка"))[:400], 422)

    def html(md):
        return md2html.convert(md2html.normalize_symbols(md)) if md else ""

    parts = bazi_report.build_parts(chart)
    for p in parts:
        p["html"], p["charts_html"] = html(p["md"]), html(p["charts_md"])
    return {"chart": chart, "caveats": bazi_report.caveats(chart), "parts": parts,
            "filename": bazi_report.default_filename(chart)}


def meta(city_names):
    import bazi_report
    return {"cities": city_names, "years": list(YEARS), "today": date.today().isoformat(),
            "sections": [{"id": s[0], "title": s[1], "default": s[2], "locked": s[3], "has_charts": bool(s[5]), "hint": s[6]}
                         for s in bazi_report.SECTIONS]}


class Handler(BaseHTTPRequestHandler):
    server_version = "bazi-web"
    sys_version = ""
    # HTTP/1.0 (по умолчанию): одно соединение — один запрос, непрочитанное тело отклонённого POST никому не мешает

    def log_message(self, fmt, *args):
        # В лог — только метод, путь без строки запроса и код ответа: данных рождения там не бывает.
        if getattr(self.server, "quiet", False):
            return
        sys.stderr.write(f"{self.command} {self.path.split('?')[0].split('#')[0]} → {args[1] if len(args) > 1 else ''}\n")

    def _send(self, status, body, ctype):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _json(self, status, obj):
        self._send(status, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8")

    def _local(self):
        """Только свои: Host и Origin обязаны указывать на этот же локальный адрес (защита от DNS-rebinding и чужих сайтов)."""
        port = self.server.server_address[1]
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host", "") not in allowed:
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin in {f"http://{h}" for h in allowed}

    def do_GET(self):
        if not self._local():
            return self._json(403, {"error": "запросы принимаются только с этого компьютера"})
        path = self.path.split("?")[0].split("#")[0]
        if path == "/api/meta":
            return self._json(200, meta(self.server.city_names))
        if path in STATIC:
            name, ctype = STATIC[path]
            try:
                with open(os.path.join(WEB, name), "rb") as fh:
                    return self._send(200, fh.read(), ctype)
            except OSError:
                return self._json(500, {"error": f"нет файла web/{name}"})
        self._json(404, {"error": "нет такой страницы"})

    do_HEAD = do_GET

    def do_POST(self):
        if not self._local():
            return self._json(403, {"error": "запросы принимаются только с этого компьютера"})
        if self.path.split("?")[0] != "/api/bazi":
            return self._json(404, {"error": "нет такой страницы"})
        if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
            return self._json(415, {"error": "нужен Content-Type: application/json"})
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self._json(411, {"error": "нужен Content-Length"})
        if not 0 < length <= MAX_BODY:
            self.close_connection = True
            return self._json(413, {"error": "слишком большой запрос"})
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            result = compute(parse_params(body, self.server.city_lookup))
        except BadRequest as e:
            return self._json(e.status, {"error": str(e)})
        except (ValueError, UnicodeDecodeError):
            return self._json(400, {"error": "тело запроса — не JSON"})
        except Exception as e:  # расчёт упал — сказать прямо, без подробностей окружения
            return self._json(500, {"error": f"внутренняя ошибка: {type(e).__name__}"})
        self._json(200, result)


def make_server(port, quiet=False):
    sys.path.insert(0, DIR)
    srv = ThreadingHTTPServer((HOST, port), Handler)
    srv.daemon_threads = True
    srv.quiet = quiet
    srv.city_names, srv.city_lookup = _city_index()
    return srv


# ── самопроверка ────────────────────────────────────────────────────────────────────────────────

def _selftest():
    import subprocess
    import urllib.error
    import urllib.request
    import bazi_report

    srv = make_server(0, quiet=True)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://{HOST}:{port}"
    ok = True

    def chk(cond, label):
        nonlocal ok
        ok &= bool(cond)
        print(("  ✓ " if cond else "  ✗ ") + label)

    def call(path, payload=None, headers=None, raw=None):
        data = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else None)
        h = {"Content-Type": "application/json"} if data is not None else {}
        h.update(headers or {})
        req = urllib.request.Request(base + path, data=data, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, r.read().decode("utf-8"), r.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8"), e.headers

    st, body, hd = call("/")
    chk(st == 200 and 'id="birth-form"' in body and "script-src 'self'" in hd.get("Content-Security-Policy", ""),
        "GET / — страница отдаётся, CSP запрещает чужие скрипты")
    chk(not re.search(r"https?://(?!127\.0\.0\.1|localhost)", body), "страница не тянет ничего из интернета")
    chk(all(call(p)[0] == 200 for p in ("/app.js", "/app.css")), "GET /app.js, /app.css")
    st, body, _ = call("/api/meta")
    m = json.loads(body)
    chk(st == 200 and "Москва" in m["cities"] and [s["id"] for s in m["sections"]] == bazi_report.SECTION_IDS,
        f"GET /api/meta — {len(m['cities'])} городов, {len(m['sections'])} разделов отчёта")

    req = {"date": "1990-05-15", "time": "14:30", "gender": "М", "city": "Москва", "as_of": "2026-11-09"}
    st, body, _ = call("/api/bazi", req)
    r = json.loads(body)
    py = os.path.join(DIR, ".venv", "bin", "python")
    cli = subprocess.run([py if os.path.exists(py) else sys.executable, os.path.join(DIR, "bazi.py"), "1990-05-15", "14:30", "М",
                          "--city", "Москва", "--as-of", "2026-11-09", "--json"], capture_output=True, text=True, cwd=DIR)
    chk(st == 200 and r["chart"] == json.loads(cli.stdout), "POST /api/bazi — карта в вебе совпадает с `bazi.py --json` (JSON целиком)")
    chk(r["chart"]["pillars"]["day"]["name"] == "庚辰" and r["filename"] == "chart_1990-05-15_Москва.md",
        "день 庚辰, имя файла chart_1990-05-15_Москва.md")
    chk([p["id"] for p in r["parts"]] == bazi_report.SECTION_IDS and all(p["html"] for p in r["parts"])
        and "<table" in r["parts"][1]["html"] and "<svg" in r["parts"][1]["charts_html"],
        "все разделы отчёта пришли в md и html, графики — SVG")
    md = bazi_report.assemble(r["parts"])
    chk(md == bazi_report.assemble(bazi_report.build_parts(r["chart"])), "отчёт из веба = отчёт из CLI bazi_report.py")
    chk(any(c["severity"] == "high" for c in r["caveats"]), "оговорка о границе часа (4 мин) дошла до ответа")

    st, body, _ = call("/api/bazi", {"date": "1985-12-03", "time": "", "gender": "Ж", "city": "москва"})
    r = json.loads(body)
    chk(st == 200 and r["chart"]["pillars"]["hour"]["name"] is None and r["chart"]["input"]["city"] == "Москва",
        "без времени: три столпа; город находится без учёта регистра")
    st, body, _ = call("/api/bazi", {"date": "1990-03-03", "time": "01:00", "gender": "М", "city": "Пермь"})
    r = json.loads(body)
    chk(st == 200 and r["chart"]["pillars"]["day"]["name"] == "丙寅" and any("через полночь" in c["text"] for c in r["caveats"]),
        "солнечная полночь: день 丙寅 от солнечных суток + оговорка")
    st, body, _ = call("/api/bazi", {"date": "1990-05-15", "time": "14:30", "gender": "М", "utc_offset": 5.5})
    r = json.loads(body)
    chk(st == 200 and r["chart"]["input"]["utc_offset"] == 5.5 and any("вручную" in c["text"] for c in r["caveats"]),
        "пояс вручную UTC+5:30 + оговорка об отсутствии солнечной поправки")

    bad = [("кривая дата", {"date": "1990-13-45", "gender": "М", "city": "Москва"}, None, 400),
           ("год вне диапазона", {"date": "1500-01-01", "gender": "М", "city": "Москва"}, None, 400),
           ("неизвестный город", {"date": "1990-05-15", "gender": "М", "city": "Нетакого"}, None, 400),
           ("инъекция в городе", {"date": "1990-05-15", "gender": "М", "city": "Москва; rm -rf /"}, None, 400),
           ("нет пояса", {"date": "1990-05-15", "gender": "М"}, None, 400),
           ("и город, и пояс", {"date": "1990-05-15", "gender": "М", "city": "Москва", "utc_offset": 3}, None, 400),
           ("нет пола", {"date": "1990-05-15", "city": "Москва"}, None, 400),
           ("кривое время", {"date": "1990-05-15", "time": "25:00", "gender": "М", "city": "Москва"}, None, 400),
           ("не JSON-объект", [1, 2], None, 400),
           ("Content-Type text/plain", req, {"Content-Type": "text/plain"}, 415),
           ("чужой Host (DNS-rebinding)", req, {"Host": "evil.example"}, 403),
           ("чужой Origin", req, {"Origin": "https://evil.example"}, 403)]
    for label, payload, headers, want in bad:
        st, body, _ = call("/api/bazi", payload, headers)
        chk(st == want and "error" in json.loads(body), f"отказ {want}: {label}")
    st, _, _ = call("/api/bazi", raw=b"{" + b" " * MAX_BODY + b"}")
    chk(st == 413, "отказ 413: тело больше 16 КБ")
    chk(all(call(p)[0] == 404 for p in ("/bazi.py", "/../bazi.py", "/web/index.html", "/.git/config", "/api/unknown")),
        "файлы проекта наружу не отдаются (404)")
    srv.shutdown()
    print("web --selftest:", "ЗЕЛЕНО ✓" if ok else "КРАСНОЕ ✗")
    return 0 if ok else 1


def main(argv):
    _bootstrap()
    sys.path.insert(0, DIR)
    if "--selftest" in argv:
        return _selftest()
    port = DEFAULT_PORT
    if "--port" in argv:
        try:
            port = int(argv[argv.index("--port") + 1])
        except (IndexError, ValueError):
            sys.stderr.write("ОШИБКА: --port ожидает номер порта\n")
            return 2
    try:
        srv = make_server(port)
    except OSError as e:
        sys.stderr.write(f"ОШИБКА: порт {port} занят или недоступен ({e.strerror}). Попробуйте: web.py --port {port + 1}\n")
        return 1
    url = f"http://{HOST}:{srv.server_address[1]}/"
    print(f"Ба Цзы — локальная веб-версия: {url}\nТолько этот компьютер; данные рождения не сохраняются. Остановить — Ctrl+C.")
    if "--no-browser" not in argv:
        import webbrowser
        threading.Timer(0.4, webbrowser.open, [url]).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлено.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
