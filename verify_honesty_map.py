#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""verify_honesty_map.py — механическая сверка «карты honesty-полей» скилла /profile3
с ФАКТИЧЕСКИМ выводом движков.

Тикет ревью 2026-07-18: рукописная карта полей дрейфует за дни (фантом `*_note` у bazi,
суженная скобка boundary_warnings) — «зеркало кода стареет быстрее кода». Лекарство —
генерировать/сверять механически, не переписывать руками. Скрипт вшит в check_all.sh.

Три проверки:
  1. КОД ДЕРЖИТ КОНТРАКТ: каждое каноническое honesty-имя есть в фактическом JSON движка.
  2. ДРЕЙФ ВВЕРХ: в JSON не появилось НОВЫХ honesty-образных ключей (по паттерну имени),
     которых нет в каноне, — ловит поле, которое скилл ещё не читает.
  3. СКИЛЛ НЕ ВРЁТ: каждый `токен` из сегмента «Карта honesty-полей» profile3.md резолвится
     в фактический ключ своего движка (глоб вида `*_note` обязан матчить ≥1 ключ — фантом
     валит проверку), и каждое каноническое имя упомянуто в сегменте (полнота карты).

Уровень сверки — ИМЕНА ключей (не пути и не текст пояснений в скобках): содержание скобок
проверяет человек (спот-чеки Шагов 3.5/4.2). Тест-рождение — нейтральная фикстура 1990-03-03 15:00 Москва (как в
verify_all, НЕ карта пользователя); --as-of фиксирован вне граничных окон (июль), чтобы
условные окна (divergence) не мигали в наборе ключей.

Запуск: python3 verify_honesty_map.py           # сверка (exit 0 / 1)
        python3 verify_honesty_map.py --dump    # напечатать фактические honesty-ключи движков
"""
import json
import os
import re
import subprocess
import sys
from fnmatch import fnmatch

DIR = os.path.dirname(os.path.abspath(__file__))
# Скилл живёт в репозитории (с 2026-11-09); карта honesty-полей — в вынесенном Шаге 3.
SKILL = os.path.join(DIR, "skills", "profile3", "references", "step3-interpreters.md")
PY = os.path.join(DIR, ".venv", "bin", "python")
if not os.path.exists(PY):
    PY = sys.executable

# Эталонное тест-рождение (как в verify_all) + фиксированный as-of вне граничных окон.
AS_OF = "2026-07-01"
ENGINES = {
    "bazi.json": ["bazi.py", "1990-03-03", "15:00", "М", "--city", "Москва", "--as-of", AS_OF, "--json"],
    "jyotish.json": ["jyotish.py", "1990-03-03", "15:00", "55.75", "37.6", "3", "--json"],
    "hd.json": ["hd.py", "1990-03-03", "15:00", "3", "--json"],
    "gene_keys.json": ["gene_keys.py", "1990-03-03", "15:00", "3", "--json"],
    "tibetan.json": ["tibetan.py", "1990-03-03", "--as-of", AS_OF, "--json"],
    "time_window.json": ["time_window.py", "1990-05-15", "14:30", "55.75", "37.62", "+4", "--json"],
}

# honesty-образные имена ключей: оговорки, границы, уверенность, провенанс, «не выдано»
HONESTY_RX = re.compile(
    r"note|warn|confidence|fragile|honesty|borderline|not_computed|provenance"
    r"|divergence|boundary|alt_if|losar|withheld|convention|sensitiv", re.I)

# КАНОН: honesty-ключи, которые скилл обязан знать (сверен с фактическим выводом 2026-07-18;
# «borderline» = strength.borderline — пограничная сила дня-мастера, школы могут разойтись).
CANON = {
    "bazi.json": {"boundary_warnings", "yongshen_borderline", "borderline", "tz_note",
                  "time_note", "year_boundary", "conventions", "note", "rule_note"},   # note/rule_note — в блоке geju (#29)
    "jyotish.json": {"note", "conventions"},
    "hd.json": {"fragile_activations", "convention_warnings", "warnings", "note", "sensitivity",
                "node_convention"},
    "gene_keys.json": {"fragile_spheres", "spectrum_provenance", "note"},
    "tibetan.json": {"losar", "losar_warning", "not_computed", "confidence", "honesty_note",
                     "date_confidence", "note", "year_boundary", "bazi_divergence",
                      "alt_if_before_losar", "withheld_reason"},
    "time_window.json": {"honesty_note", "conventions", "stable_window", "stable_window_core"},
}
# honesty-образные ключи, СОЗНАТЕЛЬНО не входящие в карту скилла (внутренности/дубли) —
# каждое исключение аргументируй здесь, а не в голове:
IGNORE = {
    "bazi.json": set(),
    "jyotish.json": set(),
    "hd.json": set(),
    "gene_keys.json": set(),
    "tibetan.json": set(),
    "time_window.json": set(),
}


def _run(cmd):
    p = subprocess.run([PY] + [os.path.join(DIR, cmd[0])] + cmd[1:],
                       capture_output=True, text=True, timeout=300, cwd=DIR)
    if p.returncode != 0:
        raise RuntimeError(f"{cmd[0]} exit {p.returncode}: {p.stderr.strip()[:300]}")
    return json.loads(p.stdout)


def _key_names(obj, acc):
    if isinstance(obj, dict):
        for k, v in obj.items():
            acc.add(k)
            _key_names(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _key_names(v, acc)
    return acc


def _skill_map_tokens():
    """Токены `...` из сегмента «Карта honesty-полей … Дуга файла» profile3.md, по движкам."""
    text = open(SKILL, encoding="utf-8").read()
    m = re.search(r"Карта honesty-полей(.*?)Дуга файла", text, re.S)
    if not m:
        return None
    seg = m.group(1)
    engines = list(ENGINES)
    # позиции маркеров «bazi.json — …»: токены после маркера принадлежат этому движку
    marks = sorted((seg.find(e), e) for e in engines if seg.find(e) >= 0)
    out = {e: [] for e in engines}
    for i, (pos, e) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(seg)
        for tok in re.findall(r"`([^`]+)`", seg[pos:end]):
            if tok.endswith(".json") or " " in tok:
                continue
            out[e].append(tok)
    return out


def main():
    dump = "--dump" in sys.argv
    ok = True
    actual, honesty = {}, {}
    for name, cmd in ENGINES.items():
        try:
            data = _run(cmd)
        except Exception as e:
            print(f"[FAIL] {name}: движок не отработал — {e}")
            return 1
        keys = _key_names(data, set())
        actual[name] = keys
        honesty[name] = {k for k in keys if HONESTY_RX.search(k)}
        if dump:
            print(f"{name}: {sorted(honesty[name])}")
    if dump:
        return 0

    for name in ENGINES:
        missing = CANON[name] - actual[name]
        if missing:
            ok = False
            print(f"[FAIL] {name}: канонические honesty-ключи ПРОПАЛИ из вывода: {sorted(missing)}")
        drift = honesty[name] - CANON[name] - IGNORE[name]
        if drift:
            ok = False
            print(f"[FAIL] {name}: НОВЫЕ honesty-образные ключи вне канона (обнови канон+карту скилла): "
                  f"{sorted(drift)}")

    toks = _skill_map_tokens()
    if toks is None:
        ok = False
        print(f"[FAIL] сегмент «Карта honesty-полей … Дуга файла» не найден в {SKILL}")
    else:
        for name in ENGINES:
            leafs = {t.split(".")[-1] for t in toks[name]}
            for leaf in sorted(leafs):
                if not any(fnmatch(k, leaf) for k in actual[name]):
                    ok = False
                    print(f"[FAIL] скилл называет `{leaf}` для {name}, но в фактическом JSON такого "
                          f"ключа нет (фантом — поправь карту в скилле)")
            unmentioned = {c for c in CANON[name]
                           if not any(fnmatch(c, leaf) for leaf in leafs)}
            if unmentioned:
                ok = False
                print(f"[FAIL] {name}: канонические ключи не упомянуты в карте скилла: "
                      f"{sorted(unmentioned)}")

    n_canon = sum(len(v) for v in CANON.values())
    print(f"verify_honesty_map: {'ЗЕЛЁНО ✓' if ok else 'КРАСНОЕ ✗'} "
          f"({len(ENGINES)} JSON, {n_canon} канонических ключей, карта скилла сверена механически)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
