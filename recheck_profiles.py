#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""recheck_profiles.py — найти сохранённые чтения, которые устарели после фиксов движков (issue #13).

Механизм: в каждой папке profiles/<дата>_<город>[__…]/ лежат персист `_bazi.json`, `_jyotish.json`,
`_hd.json`, `_gene_keys.json`, `_tibetan.json`, при наличии `_time_window.json` / `_retro_signals.json`,
и штамп `_engines.sha` (дата прогона + sha256 всех *.py).
Скрипт (а) отбирает кандидатов — папки, где отпечаток изменившегося движка старый или штампа нет;
(б) пересчитывает JSON ТЕКУЩИМ кодом с фиксацией даты (--as-of из сохранённого JSON — иначе любой профиль
«разойдётся» назавтра) и сравнивает НАТАЛЬНЫЕ поля; (в) печатает, какие профили перегенерировать.

Вход для пересчёта берётся из персиста правильно (правило profile3 «Куда сохранять»): настенное время и
город — `_bazi.input.wall_time`/`city` (старые персисты без них — `birth_local` из `_hd.json`, город из имени
папки), пол — `_bazi.input.gender`; солнечное `_bazi.input.time` обратно в CLI НЕ подаётся.

Запуск:  .venv/bin/python recheck_profiles.py [--all] [--only ПАПКА] [--verbose]
         .venv/bin/python recheck_profiles.py --test  # синтетические данные, profiles/ не читается
  по умолчанию пересчитываются только кандидаты по штампу; --all — все папки с персистом.
Данные людей остаются локально: скрипт ничего не пишет и не отправляет, только печатает отчёт.
Старые 7-файловые папки (/profile6), у которых есть свежий `<дата>_<город>__…3sys`, считаются ЗАМЕНЁННЫМИ и не пересчитываются.
Выход: 0 — все актуальны; 3 — есть устаревшие (список в выводе); 1 — ошибка пересчёта.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(DIR, ".venv", "bin", "python")
if not os.path.exists(PY):
    PY = sys.executable
sys.path.insert(0, DIR)

ENGINES = ["bazi.py", "jyotish.py", "hd.py", "gene_keys.py", "tibetan.py", "time_window.py", "retro_signals.py"]
# натальные поля для сравнения (пути через точку; списки сравниваются целиком)
NATAL = {
    "_bazi.json": ["pillars", "day_master", "strength", "element_balance", "yongshen", "jishen",
                   "yongshen_borderline", "kong_wang", "shensha", "interactions", "luck_pillars", "tiaohou"],
    "_jyotish.json": ["lagna", "moon_nakshatra", "grahas", "yogas", "house_lords"],
    "_hd.json": ["type", "authority", "profile", "defined_centers", "defined_channels", "incarnation_cross",
                 "activations", "definition"],
    "_gene_keys.json": ["spheres", "prime_gifts"],
    "_tibetan.json": ["year_sign", "mewa", "forces", "parkha", "losar", "obstacle_year"],
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def current_fingerprints():
    return {os.path.basename(p): sha256(os.path.join(DIR, p))
            for p in sorted(os.listdir(DIR)) if p.endswith(".py")}


def stamped_fingerprints(folder):
    path = os.path.join(folder, "_engines.sha")
    if not os.path.exists(path):
        return None, None
    lines = open(path, encoding="utf-8").read().splitlines()
    date = lines[0].strip() if lines else "?"
    fps = {}
    for ln in lines[1:]:
        m = re.match(r"([0-9a-f]{64})\s+(.*)$", ln.strip())
        if m:
            fps[os.path.basename(m.group(2))] = m.group(1)
    return date, fps


def load(folder, name):
    p = os.path.join(folder, name)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        value = json.load(f)
    if name in ("_time_window.json", "_retro_signals.json") and not isinstance(value, dict):
        raise RuntimeError(f"{name}: сохранённый файл должен содержать JSON-объект, не null или список")
    return value


def birth_inputs(folder, bz, hd):
    """(date, wall_time, offset_str, gender_arg, city) из персиста — без солнечного времени."""
    inp = (bz or {}).get("input", {})
    date = inp.get("date")
    wall = inp.get("wall_time")
    city = inp.get("city")
    gender = {"мужской": "М", "женский": "Ж"}.get(inp.get("gender"), None)
    off = inp.get("utc_offset")
    bl = ((hd or {}).get("input") or {}).get("birth_local")  # «1990-05-15 14:30 UTC+4»
    if bl:
        m = re.match(r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) UTC([+-]?[\d.]+)", bl)
        if m:
            date = date or m.group(1)
            wall = wall or m.group(2)
            off = off if off is not None else float(m.group(3))
    if not city:
        base = os.path.basename(folder.rstrip("/"))
        parts = base.split("__")[0].split("_", 1)
        city = parts[1] if len(parts) > 1 else None
    return date, wall, off, gender, city


def run_json(cmd):
    p = subprocess.run([PY] + cmd, capture_output=True, text=True, cwd=DIR, timeout=300)
    if p.returncode != 0:
        raise RuntimeError(f"{cmd[0]} exit {p.returncode}: {p.stderr.strip()[:200]}")
    return json.loads(p.stdout)


def diff_paths(a, b, prefix="", out=None, limit=40):
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append(f"+{prefix}{k}")
            elif k not in b:
                out.append(f"-{prefix}{k}")
            else:
                diff_paths(a[k], b[k], f"{prefix}{k}.", out, limit)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"~{prefix}len {len(a)}→{len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            diff_paths(x, y, f"{prefix}[{i}].", out, limit)
    else:
        if a != b and not (isinstance(a, float) and isinstance(b, float) and abs(a - b) < 1e-6):
            out.append(f"~{prefix.rstrip('.')}: {a!r}→{b!r}")
    return out


# Расхождения схемы/метаданных — не натальные: не повод перегенерировать чтение
IGNORE_RX = [
    re.compile(r"luck_pillars\.pillars\.\[\d+\]\.age_end$"),   # issue #8: граница окна +9 → +10 (подпись)
    re.compile(r"year_boundary\.as_of$"),                        # дата as-of пересчёта
    re.compile(r"^\+conventions"),                               # issue #18: новый блок конвенций
    re.compile(r"age_exact$"),
]


def _natal_only(paths):
    out = []
    for ln in paths:
        key = ln.lstrip("+-~").split(":")[0]
        if any(rx.search(key) or rx.search(ln) for rx in IGNORE_RX):
            continue
        out.append(ln)
    return out


def window_command(saved):
    """Воспроизвести именно сохранённую сетку, включая размер и даты через полночь."""
    inp = saved.get("input") if isinstance(saved, dict) else None
    required = ("date", "time", "latitude", "longitude", "utc_offset", "span_minutes")
    if not isinstance(inp, dict) or any(k not in inp for k in required):
        raise RuntimeError("_time_window.json: не хватает input для пересчёта окна")
    return ["time_window.py", str(inp["date"]), str(inp["time"]), str(inp["latitude"]),
            str(inp["longitude"]), str(inp["utc_offset"]), "--span", str(inp["span_minutes"]), "--json"]


def retro_command(folder, saved):
    """Дата проверки прошлого фиксирована: новый день запуска не добавляет сигналы."""
    inp = saved.get("input") if isinstance(saved, dict) else None
    if not isinstance(inp, dict) or any(k not in inp for k in ("as_of", "years")):
        raise RuntimeError("_retro_signals.json: не хватает input.as_of/years для пересчёта")
    return ["retro_signals.py", "--bazi", os.path.join(folder, "_bazi.json"),
            "--jyotish", os.path.join(folder, "_jyotish.json"),
            "--as-of", str(inp["as_of"]), "--years", str(inp["years"]), "--json"]


def recheck(folder, verbose=False):
    retro = load(folder, "_retro_signals.json")
    bz, hd = load(folder, "_bazi.json"), load(folder, "_hd.json")
    date, wall, off, gender, city = birth_inputs(folder, bz, hd)
    if not (date and wall and gender):
        return "SKIP", [f"не хватает входа: date={date} wall={wall} gender={gender}"]
    off_s = f"{off:+g}" if off is not None else None
    changes = {}
    # bazi — как-of из сохранённого года (резолв Личуня внутри года устойчив вне граничных дней)
    cy = ((bz or {}).get("current_year") or {}).get("year")
    as_of = ((bz or {}).get("current_year") or {}).get("year_boundary", {}).get("as_of") or (f"{cy}-07-01" if cy else None)
    cmd = ["bazi.py", date, wall, gender] + (["--city", city] if city else [f"UTC{off_s}"]) + \
          (["--as-of", as_of] if as_of else []) + ["--json"]
    new = run_json(cmd)
    d = []
    for k in NATAL["_bazi.json"]:
        diff_paths(bz.get(k), new.get(k), f"{k}.", d)
    d = _natal_only(d)
    # Исходники ретро сравниваются ПОСЛЕ фильтра метаданных: даже добавленная конвенция
    # должна помечать сохранённые вопросы устаревшими, а не исчезать как +conventions.*.
    if retro is not None:
        for k in ("ten_gods", "conventions"):
            diff_paths(bz.get(k), new.get(k), f"{k}.", d)
    if d:
        changes["_bazi.json"] = d
    # jyotish
    jy = load(folder, "_jyotish.json")
    if jy and off_s and city:
        from geo import resolve
        lat, lon = resolve(city)
        das = jy.get("dasha_as_of")
        cmd = ["jyotish.py", date, wall, str(lat), str(lon), off_s] + (["--as-of", das] if das else []) + ["--json"]
        try:
            new = run_json(cmd)
            d = []
            for k in NATAL["_jyotish.json"]:
                diff_paths(jy.get(k), new.get(k), f"{k}.", d)
            d = _natal_only(d)
            if retro is not None:
                for k in ("dasha_timeline", "conventions"):
                    diff_paths(jy.get(k), new.get(k), f"{k}.", d)
            if d:
                changes["_jyotish.json"] = d
        except RuntimeError as e:
            changes["_jyotish.json"] = [f"пересчёт не удался: {e}"]
    # hd / gene_keys — от даты запуска не зависят
    for name, script in (("_hd.json", "hd.py"), ("_gene_keys.json", "gene_keys.py")):
        old = load(folder, name)
        if old and off_s:
            new = run_json([script, date, wall, off_s, "--json"])
            d = []
            for k in NATAL[name]:
                diff_paths(old.get(k), new.get(k), f"{k}.", d)
            d = _natal_only(d)
            if d:
                changes[name] = d
    # tibetan
    tb = load(folder, "_tibetan.json")
    if tb:
        ty = (tb.get("forces_year_relation") or {}).get("year")
        new = run_json(["tibetan.py", date] + (["--as-of", f"{ty}-07-01"] if ty else []) + ["--json"])
        d = []
        for k in NATAL["_tibetan.json"]:
            diff_paths(tb.get(k), new.get(k), f"{k}.", d)
        d = _natal_only(d)
        if d:
            changes["_tibetan.json"] = d
    # Окно — самостоятельная обязательная оговорка новых профилей. Старые чтения без
    # этого файла не считаем изменившимися только из-за расширения формата персиста.
    window = load(folder, "_time_window.json")
    if window is not None:
        new = run_json(window_command(window))
        d = diff_paths(window, new)
        if d:
            changes["_time_window.json"] = d
    # Натальные исходники уже проверены выше; отдельно ловим изменения алгоритма
    # ретро-сигналов на тех же исходниках. Выбор ID человека не переписывается.
    if retro is not None:
        new = run_json(retro_command(folder, retro))
        d = diff_paths(retro, new)
        if d:
            changes["_retro_signals.json"] = d
    return ("CHANGED" if changes else "OK"), changes


def _test():
    """Пять карт неизменны: исправление только окна всё равно должно дать CHANGED."""
    import copy
    import tempfile
    from datetime import datetime
    from unittest.mock import patch
    from time_window import build_window

    ok = True

    def chk(cond, label):
        nonlocal ok
        ok &= bool(cond)
        print(("  ✓ " if cond else "  ✗ ") + label)

    # Не создаём и не открываем profiles/: load/run_json работают с копиями фикстур.
    wall = datetime(1990, 5, 15, 14, 30)
    saved = {name: {"input": {"birth_local": "1990-05-15 14:30 UTC+4"}} for name in NATAL}
    saved["_bazi.json"] = {
        "input": {"date": wall.date().isoformat(), "wall_time": "14:30", "time": "13:04",
                  "utc_offset": 4, "gender": "мужской", "city": "Москва"},
        "current_year": {"year": wall.year, "year_boundary": {"as_of": wall.date().isoformat()}},
    }
    saved["_jyotish.json"]["dasha_as_of"] = wall.date().isoformat()
    saved["_time_window.json"] = build_window(wall, 55.75, 37.62, 4, span=51)
    fresh = copy.deepcopy(saved)
    calls = []

    def fake_run(cmd):
        calls.append(cmd)
        name = "_" + cmd[0].removesuffix(".py") + ".json"
        return copy.deepcopy(fresh[name])

    def check():
        with patch(__name__ + ".load", side_effect=lambda _f, name: copy.deepcopy(saved.get(name))), \
                patch(__name__ + ".run_json", side_effect=fake_run):
            return recheck("1990-05-15_Москва")

    status, changes = check()
    chk(status == "OK" and not changes, "пять карт и сохранённое окно без изменений — OK")
    cmd = next(c for c in calls if c[0] == "time_window.py")
    chk(cmd == ["time_window.py", "1990-05-15", "14:30", "55.75", "37.62", "4", "--span", "51", "--json"],
        "пересчёт по настенному input окна, исходным координатам/поясу и span=51")
    for key in ("items", "stable_window", "stable_window_core", "honesty_note", "conventions"):
        fresh["_time_window.json"] = copy.deepcopy(saved["_time_window.json"])
        if key == "items":
            fresh["_time_window.json"][key][0]["value"] = "синтетическое изменение"
        elif key.startswith("stable_window"):
            fresh["_time_window.json"][key]["minutes_before"] += 1
        elif key == "honesty_note":
            fresh["_time_window.json"][key] += " Изменённая оговорка."
        else:
            fresh["_time_window.json"][key]["hd"] = "синтетическая конвенция"
        status, changes = check()
        chk(status == "CHANGED" and set(changes) == {"_time_window.json"},
            f"изменилось только {key} окна — CHANGED, не скрыто неизменностью пяти карт")
    legacy = saved.pop("_time_window.json")
    chk(check() == ("OK", {}), "старый персист без окна — прежнее поведение")
    saved["_time_window.json"] = copy.deepcopy(legacy)
    del saved["_time_window.json"]["input"]["latitude"]
    try:
        check()
    except RuntimeError:
        chk(True, "неполный input сохранённого окна — ошибка, не OK")
    else:
        chk(False, "неполный input сохранённого окна не отклонён")
    saved["_time_window.json"] = legacy
    fresh["_time_window.json"] = copy.deepcopy(legacy)
    # Синтетический результат проверяет интеграцию, не формулы retro_signals.
    saved["_retro_signals.json"] = {
        "input": {"as_of": "2026-11-17", "years": 15}, "signals": [{"id": "synthetic"}],
        "source_note": "Синтетический источник", "honesty_note": "Синтетическая оговорка",
        "not_computed": [], "conventions": {"annual_years": "Синтетическая конвенция"},
    }
    saved["_bazi.json"].update(ten_gods=[{"name": "正官", "weight": 1}], conventions={"test": "синтетическая"})
    saved["_jyotish.json"].update(dasha_timeline=[{"from": "синтетическая дата"}], conventions="синтетическая")
    fresh["_bazi.json"] = copy.deepcopy(saved["_bazi.json"])
    fresh["_jyotish.json"] = copy.deepcopy(saved["_jyotish.json"])
    fresh["_retro_signals.json"] = copy.deepcopy(saved["_retro_signals.json"])
    chk(check() == ("OK", {}), "сохранённые ретро-сигналы без изменений — OK")
    cmd = next(c for c in calls if c[0] == "retro_signals.py")
    chk(cmd == ["retro_signals.py", "--bazi", os.path.join("1990-05-15_Москва", "_bazi.json"),
                "--jyotish", os.path.join("1990-05-15_Москва", "_jyotish.json"),
                "--as-of", "2026-11-17", "--years", "15", "--json"],
        "ретро пересчитывается по сохранённым JSON с исходными as_of/years")
    for key in ("signals", "source_note", "honesty_note", "not_computed", "conventions"):
        fresh["_retro_signals.json"] = copy.deepcopy(saved["_retro_signals.json"])
        if key == "signals":
            fresh["_retro_signals.json"][key][0]["id"] = "synthetic-changed"
        elif key == "not_computed":
            fresh["_retro_signals.json"][key].append("Синтетическое ограничение")
        elif key == "conventions":
            fresh["_retro_signals.json"][key]["annual_years"] += " Изменение."
        else:
            fresh["_retro_signals.json"][key] += " Изменение."
        status, changes = check()
        chk(status == "CHANGED" and set(changes) == {"_retro_signals.json"},
            f"изменилось только {key} ретро — CHANGED")
    fresh["_retro_signals.json"] = copy.deepcopy(saved["_retro_signals.json"])
    for name, key in (("_bazi.json", "ten_gods"), ("_jyotish.json", "dasha_timeline"),
                      ("_bazi.json", "conventions"), ("_jyotish.json", "conventions")):
        original = copy.deepcopy(fresh[name])
        fresh[name][key] = "синтетическое изменение исходника ретро"
        status, changes = check()
        chk(status == "CHANGED" and name in changes,
            f"изменился только свежий {name}:{key} — устаревшее ретро не скрывает CHANGED")
        fresh[name] = original
    fresh["_bazi.json"]["conventions"]["new_rule"] = "синтетическое новое правило"
    status, changes = check()
    chk(status == "CHANGED" and any("+conventions.new_rule" in s for s in changes.get("_bazi.json", [])),
        "добавление +conventions.new_rule не отфильтровано — CHANGED")
    fresh["_bazi.json"] = copy.deepcopy(saved["_bazi.json"])
    del saved["_retro_signals.json"]
    chk(check() == ("OK", {}), "старый персист без ретро — прежнее поведение")
    with tempfile.TemporaryDirectory(prefix="recheck-null-test-") as folder:
        for name in ("_time_window.json", "_retro_signals.json"):
            chk(load(folder, name) is None, f"отсутствующий {name} допустим для легаси")
            with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
                json.dump(None, f)
            try:
                load(folder, name)
            except RuntimeError:
                chk(True, f"существующий {name} с JSON null — ошибка, не легаси")
            else:
                chk(False, f"JSON null в {name} не отклонён")
    print("recheck_profiles --test:", "ЗЕЛЕНО ✓" if ok else "КРАСНОЕ ✗")
    return 0 if ok else 1


def main():
    argv = sys.argv[1:]
    if argv == ["--test"]:
        return _test()
    verbose = "--verbose" in argv
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    do_all = "--all" in argv
    root = os.path.join(DIR, "profiles")
    if not os.path.isdir(root):
        print("profiles/ нет — нечего проверять")
        return 0
    cur = current_fingerprints()
    folders = sorted(os.path.join(root, f) for f in os.listdir(root)
                     if os.path.isdir(os.path.join(root, f)) and os.path.exists(os.path.join(root, f, "_bazi.json")))
    if only:
        folders = [f for f in folders if os.path.basename(f) == only]
    stale, ok, errors, skipped, uptodate, superseded = [], [], [], [], [], []
    names = set(os.listdir(root))
    for f in folders:
        # старый 7-файловый профиль (/profile6), у которого уже есть свежий __3sys-прогон того же человека:
        # по правилу profile3 «Куда сохранять» его не редактируют — он заменён, а не устарел
        base = os.path.basename(f).split("__")[0]
        if os.path.exists(os.path.join(f, "7_synthesis.md")) and any(
                n.startswith(base + "__") and n.endswith("3sys") and n != os.path.basename(f) for n in names):
            superseded.append(f)
            continue
        date, fps = stamped_fingerprints(f)
        if fps is None:
            reason = "без штампа"
        else:
            changed = sorted(k for k, v in fps.items() if k in cur and cur[k] != v)
            reason = f"штамп {date}, изменились: {', '.join(changed)}" if changed else None
        if reason is None and not do_all:
            uptodate.append(f)
            continue
        try:
            status, details = recheck(f, verbose)
        except Exception as e:  # noqa: BLE001
            errors.append((f, str(e)))
            continue
        if status == "SKIP":
            skipped.append((f, details))
        elif status == "CHANGED":
            stale.append((f, reason, details))
        else:
            ok.append((f, reason))
    name = os.path.basename
    print(f"recheck_profiles: папок с персистом {len(folders)}; заменены новым __3sys (не трогаем): {len(superseded)}; "
          f"штамп актуален (не пересчитывались): {len(uptodate)}; пересчитано {len(ok) + len(stale)}: без изменений {len(ok)}, "
          f"УСТАРЕЛИ {len(stale)}; пропущено {len(skipped)}; ошибок {len(errors)}")
    for f, reason, details in stale:
        n = sum(len(v) for v in details.values())
        print(f"  ✗ {name(f)}  ({reason}) — расхождений {n} в {', '.join(details)}")
        if verbose:
            for js, lines in details.items():
                for ln in lines[:12]:
                    print(f"       {js}: {ln}")
    for f, msg in errors:
        print(f"  ! {name(f)}: {msg}")
    for f, details in skipped:
        print(f"  – {name(f)}: {details[0]}")
    if stale:
        print("Перегенерировать чтения с расхождениями в натальных полях (profile3 «Куда сохранять», п. (б)); "
              "затронутые файлы — те, где лежат изменившиеся поля.")
    return 1 if errors else (3 if stale else 0)


if __name__ == "__main__":
    sys.exit(main())
