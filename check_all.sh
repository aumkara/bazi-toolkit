#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
# check_all.sh — ОДНА кнопка: все самопроверки проекта разом.
# Гонять после ЛЮБОЙ правки кода (и перед выверкой скиллов). Всё зелёное ⇒ числам можно доверять.
# Состав — см. вызовы run ниже: окружение и скиллы, golden и кросс-тождества движков, --test калькуляторов, отчёт,
# веб, MCP по протоколу, формат ошибок CLI, гейт утечек, внешние оракулы. Оракул без установленной библиотеки
# пропускается с кодом 0 (пропуск ≠ сверка; CI требует их флагом --require). Выход 0 = всё зелёное; 1 = есть FAIL.
# Использование:  bash check_all.sh [--network]
#   --network (или BAZI_NETWORK_CHECKS=1) — дополнительно три сверки, которые СКАЧИВАЮТ И ВЫПОЛНЯЮТ сторонний код
#   (Ciallo под node, mingpan через npx, ziwei_cli.py с GitHub). Без флага они не запускаются вовсе: обычная
#   установка не должна выполнять чужой код без явного согласия.
set -u
cd "$(dirname "$0")" || exit 1
NETWORK="${BAZI_NETWORK_CHECKS:-0}"
for a in "$@"; do
  case "$a" in
    --network) NETWORK=1 ;;
    *) echo "неизвестный аргумент: $a (использование: bash check_all.sh [--network])" >&2; exit 2 ;;
  esac
done
export PYTHONDONTWRITEBYTECODE=1
PY=".venv/bin/python"; [ -x "$PY" ] || PY=python3

fail=0; net_skipped=0
run() { # run <ярлык> <команда...>
  echo ""
  echo "──────── $1"
  shift
  "$@" || { echo "✗ FAIL: $*"; fail=1; }
}
run_net() { # run_net <ярлык> <команда...> — сверка скачивает и выполняет сторонний код: только с --network
  if [ "$NETWORK" = 1 ]; then run "$@"; return; fi
  echo ""
  echo "──────── $1"
  echo "~ не запускалась: сверка скачивает и выполняет сторонний код — включается флагом --network"
  net_skipped=$((net_skipped + 1))
}

# окружение: swisseph обязан быть в .venv (issue #6) — иначе движки честно откажутся считать
check_env() {
  [ -x .venv/bin/python ] || { echo "✗ нет .venv — bash setup.sh"; return 1; }
  .venv/bin/python -c "import swisseph, ephem" 2>/dev/null || { echo "✗ в .venv нет pyswisseph/ephem — bash setup.sh"; return 1; }
  echo "✓ .venv: $(.venv/bin/python -c 'import sys,swisseph; print(f"python {sys.version.split()[0]}, swisseph {swisseph.version}")')"
}
# скиллы: вывод skill tool OpenCode обрезается на ~45 КБ — ядро любого скилла держим ≤ 40 КБ (issue #14)
check_skill_sizes() {
  local bad=0
  for f in skills/*/SKILL.md; do
    local sz; sz=$(wc -c < "$f")
    if [ "$sz" -gt 40960 ]; then echo "✗ $f: $sz байт > 40 КБ — вынеси часть в references/"; bad=1; fi
  done
  [ "$bad" = 0 ] && echo "✓ $(ls skills/*/SKILL.md | wc -l | tr -d ' ') SKILL.md, все ≤ 40 КБ"
  return $bad
}
# скиллы находят проект только через ${BAZI_DIR:-$HOME/.bazi}: зашитый путь чьей-то машины ломает их у всех остальных
check_skill_paths() {
  local bad=0 hits
  hits=$(grep -rnE 'BAZI_DIR:-' skills | grep -vF '${BAZI_DIR:-$HOME/.bazi}' || true)
  [ -z "$hits" ] || { echo "✗ корень проекта задан не через \${BAZI_DIR:-\$HOME/.bazi}:"; echo "$hits" | cut -c1-160; bad=1; }
  hits=$(grep -rnE '(~|\$HOME|/Users/[^/ ]+|/home/[^/ ]+)/(Documents|Desktop|Downloads)/' skills || true)
  [ -z "$hits" ] || { echo "✗ в скиллах зашит путь в домашней папке:"; echo "$hits" | cut -c1-160; bad=1; }
  [ "$bad" = 0 ] && echo "✓ $(grep -rlF '${BAZI_DIR:-$HOME/.bazi}' skills | wc -l | tr -d ' ') файлов скиллов берут корень из \${BAZI_DIR:-\$HOME/.bazi}, зашитых домашних путей нет"
  return $bad
}

# версия и зависимости записаны в двух местах — они обязаны совпадать
check_meta() {
  local v_py v_ch bad=0 dep
  v_py=$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)
  v_ch=$(sed -n 's/^## \[\([0-9][^]]*\)\].*/\1/p' CHANGELOG.md | head -1)
  if [ -z "$v_py" ] || [ "$v_py" != "$v_ch" ]; then echo "✗ версия: pyproject.toml «$v_py» ≠ верхняя запись CHANGELOG.md «$v_ch»"; bad=1; fi
  for dep in $(grep -oE '^[A-Za-z0-9_.-]+==[0-9][^ ]*' requirements.txt requirements-dev.txt | cut -d: -f2); do
    grep -qF "\"$dep\"" pyproject.toml || { echo "✗ $dep есть в requirements*.txt, но в pyproject.toml другая версия или его нет"; bad=1; }
  done
  [ "$bad" = 0 ] && echo "✓ версия $v_py: pyproject.toml = CHANGELOG.md; закреплённые зависимости requirements*.txt = pyproject.toml"
  return $bad
}

run "окружение — .venv с pyswisseph и ephem"                        check_env
run "версия и зависимости — pyproject.toml = CHANGELOG.md = requirements*.txt" check_meta
run "размер скиллов — SKILL.md ≤ 40 КБ (обрезка skill tool)"        check_skill_sizes
run "пути в скиллах — корень только через BAZI_DIR или ~/.bazi"     check_skill_paths
run "verify_all — чистый тест движков (golden + кросс-тождества)"   "$PY" verify_all.py
run "timezones --test — исторические оффсеты (якоря Wikipedia/IANA)" "$PY" timezones.py --test
run "time_window --test — устойчивость показателей к минуте рождения" "$PY" time_window.py --test
run "retro_signals --test — кандидаты вопросов о прошлом с основаниями из JSON" "$PY" retro_signals.py --test
run "recheck_profiles --test — проверка персистов на синтетических данных" "$PY" recheck_profiles.py --test
run "compat --selftest — инварианты совместимости"     "$PY" compat.py --selftest
run "infographics --test — все генераторы графиков"    "$PY" infographics.py --test
run "validate_layouts — раскладка SVG на 8 рождениях"  "$PY" validate_layouts.py
run "validate_synthesis --test — линтер синтеза (ложные HARD + протечки)" "$PY" validate_synthesis.py --test
run "bazi_report --test — .md-отчёт по карте: разделы, оговорки, таблицы, графики" "$PY" bazi_report.py --test
run "web --selftest — локальная веб-версия: карта = bazi.py --json, отказы, только localhost" "$PY" web.py --selftest
run "fact_check_reading --test — сверка фактов чтения с JSON (самопроверка)" "$PY" fact_check_reading.py --test
run "mcp_server --selftest — инструменты MCP: функции, протокол в памяти и по stdio (isError, схемы)" "$PY" mcp_server.py --selftest
run "verify_honesty_map — карта honesty-полей скилла = фактический вывод движков" "$PY" verify_honesty_map.py
run "check_public — гейт утечек: пути, email, токены, личные чтения (самопроверка + дерево)" sh -c "\"$PY\" check_public.py --test && \"$PY\" check_public.py"
# внешние оракулы (issue #17): пропуск, если библиотека не установлена; FAIL только на настоящих расхождениях
run "verify_vs_lunar — оракул lunar-python: 4 столпа Ба Цзы (пропуск, если не установлен)" "$PY" verify_vs_lunar.py 120
run "verify_vs_iztro — оракул x-iztro: карта 紫微 (пропуск, если не установлен)"     "$PY" verify_vs_iztro.py 40
run "verify_vs_pyhd — оракул pyhd: карта Дизайна Человека (пропуск, если не установлен)" "$PY" verify_vs_pyhd.py 40
run "verify_vs_caltib — оракул caltib: таблица Лосара (пропуск, если не установлен)"    "$PY" verify_vs_caltib.py
run "check_cli_errors — единый формат ошибок CLI: код 2, сообщение в stderr, JSON-конверт" "$PY" check_cli_errors.py
run "ziwei --test — 命宫, 身宫, 五行局, 安紫微 на известных случаях"                 "$PY" ziwei.py --test
run "qimen --test — 置闰: известные случаи + инварианты 2020–2025"                 "$PY" qimen.py --test
run "meihua --test — 64 гексаграммы = таблица скилла, 互/变/错/综, 体用, 卦气"      "$PY" meihua.py --test
run "verify_meihua_table — 64 гексаграммы против Wikipedia (офлайн-фикстура)"       "$PY" verify_meihua_table.py
run "bazi_reverse --test — обратный поиск дат по столпам (ректификация)"            "$PY" bazi_reverse.py --test
run "geju --test — структура 格局 по 月令 и школа 子平真诠 вторым взглядом на 用神"      "$PY" geju.py
run "verify_vs_kinqimen — оракул kinqimen: доска 奇门 拆补 (пропуск, если не установлен)" "$PY" verify_vs_kinqimen.py 40
run "verify_vs_kinqimen --method zhirun — доска 置闰 (局 kinqimen — эвристика, информативно)" "$PY" verify_vs_kinqimen.py 30 --method zhirun
run_net "verify_vs_ciallo — оракул Ciallo (node): 置闰 局/元/闰 + доска (пропуск без node/сети)"  "$PY" verify_vs_ciallo.py 40
run_net "verify_vs_mingpan — оракул mingpan (MCP, npx): 梅花 起卦 + 奇门 拆补 (пропуск без npx/сети)" "$PY" verify_vs_mingpan.py 20
run_net "verify_vs_numerologist — 2-й оракул 紫微 без iztro (ziwei_cli.py; пропуск без сети)"       "$PY" verify_vs_numerologist.py 30
run "verify_vs_dashaflow — оракул dashaflow: Лагна/грахи/накшатра/махадаша (пропуск, если не установлен)" "$PY" verify_vs_dashaflow.py 30

echo ""
echo "════════════════════════════════════════════════"
[ "$net_skipped" -eq 0 ] || echo "~ сверок со сторонним кодом из сети не запускалось: $net_skipped (включить: bash check_all.sh --network)"
if [ "$fail" -eq 0 ]; then
  echo "✓ CHECK_ALL: всё зелёное ($(date +%F))"
else
  echo "✗ CHECK_ALL: есть FAIL — не интерпретируй сломанное, чини"
fi
exit "$fail"
