#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
# publish_snapshot.sh — выгрузить ЧИСТЫЙ СНИМОК проекта для публичного репозитория, без истории коммитов.
# Нужен один раз — для первого коммита публичного репозитория; дальше разработка идёт прямо в нём,
# а от утечек при каждом коммите страхует хук hooks/pre-commit.
#
# Использование:  bash publish_snapshot.sh <папка-назначения> [--worktree]
#   по умолчанию снимок берётся из HEAD и требует чистого дерева: публикуется ровно то, что закоммичено;
#   --worktree — пробный снимок из рабочего дерева вместе с незакоммиченным (посмотреть до коммита).
#
# Что делает: git archive (всё с export-ignore из .gitattributes остаётся дома) → временная папка →
#   гейт утечек check_public.py → trufflehog, если установлен → и только после этого папка назначения.
# Чего НЕ делает: git init, коммит и push в публичный репозиторий — это шаги владельца (подсказка в конце).
# Папка назначения должна быть пустой либо прежним снимком (в ней лежит метка .public-snapshot):
#   тогда всё, кроме .git, заменяется новым снимком — так выпускаются следующие версии.
set -euo pipefail
cd "$(dirname "$0")"
SRC="$(pwd -P)"
MARK=".public-snapshot"
DEST=""; MODE="head"
for a in "$@"; do
  case "$a" in
    --worktree) MODE="worktree" ;;
    -*) echo "неизвестный аргумент: $a" >&2; exit 2 ;;
    *) DEST="$a" ;;
  esac
done
[ -n "$DEST" ] || { sed -n '4,16p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
git rev-parse --git-dir >/dev/null 2>&1 || { echo "✗ запускать из git-репозитория проекта" >&2; exit 1; }

# ── папка назначения: проверить ДО любых действий; пересечение с проектом запрещено в обе стороны
CREATED=0; [ -e "$DEST" ] || CREATED=1
refuse() { [ "$CREATED" = 0 ] || rmdir "$DEST" 2>/dev/null || true; echo "✗ $1" >&2; exit 1; }   # за собой пустую папку не оставляем
mkdir -p "$DEST"
DEST="$(cd "$DEST" && pwd -P)"
case "$DEST/" in "$SRC/"*) refuse "папка назначения лежит внутри проекта — выберите другую" ;; esac
case "$SRC/" in "$DEST/"*) refuse "проект лежит внутри папки назначения — выберите другую" ;; esac
if [ "$DEST" = "/" ] || [ "$DEST" = "$(cd "$HOME" && pwd -P)" ]; then refuse "папка назначения — корень или домашний каталог"; fi
if [ -n "$(ls -A "$DEST")" ] && [ ! -f "$DEST/$MARK" ]; then
  refuse "$DEST не пуста и это не прежний снимок (нет метки $MARK) — ничего не трогаю"
fi

if [ "$MODE" = "head" ]; then
  if [ -n "$(git status --porcelain)" ]; then
    refuse "рабочее дерево не чистое: закоммитьте изменения или возьмите пробный снимок с --worktree"
  fi
  TREE="HEAD"; LABEL="коммит $(git rev-parse --short HEAD)"
fi

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/bazi-snapshot.XXXXXX")"
TMPIDX="$(mktemp "${TMPDIR:-/tmp}/bazi-snapshot-index.XXXXXX")"
THOUT="$(mktemp "${TMPDIR:-/tmp}/bazi-snapshot-scan.XXXXXX")"
trap 'rm -rf "$STAGE" "$TMPIDX" "$THOUT"' EXIT

if [ "$MODE" = "worktree" ]; then
  # временный индекс: настоящий индекс, ветки и рабочее дерево не меняются
  GIT_INDEX_FILE="$TMPIDX" git read-tree HEAD
  GIT_INDEX_FILE="$TMPIDX" git add -A
  TREE="$(GIT_INDEX_FILE="$TMPIDX" git write-tree)"; LABEL="рабочее дерево (пробный снимок, не для публикации)"
fi

# ── снимок собирается и проверяется во временной папке; папку назначения до успеха не трогаем
git archive --format=tar "$TREE" | tar -x -C "$STAGE"
echo "снимок проекта bazi: $LABEL, $(date +%F)" > "$STAGE/$MARK"
echo "── снимок: $(find "$STAGE" -type f | wc -l | tr -d ' ') файлов ($LABEL)"

PY=".venv/bin/python"; [ -x "$PY" ] || PY=python3
echo "── гейт утечек"
if ! "$PY" check_public.py --tree "$STAGE"; then
  echo "✗ В СНИМКЕ ЕСТЬ НАХОДКИ — НЕ ПУБЛИКОВАТЬ. Папка назначения не тронута. Исправьте в проекте и повторите." >&2
  exit 1
fi
if command -v trufflehog >/dev/null 2>&1; then
  echo "── trufflehog (без сетевой верификации)"
  if ! trufflehog filesystem "$STAGE" --no-verification --no-update --json > "$THOUT" 2>/dev/null; then
    echo "✗ trufflehog завершился с ошибкой — проверка НЕ выполнена, снимок не выпущен. Папка назначения не тронута." >&2
    exit 1
  fi
  n="$(grep -c '"DetectorName"' "$THOUT" || true)"
  if [ "$n" != "0" ]; then
    echo "✗ trufflehog: находок $n — НЕ ПУБЛИКОВАТЬ. Папка назначения не тронута. Разбор: bash $0 … после правок." >&2
    exit 1
  fi
  echo "✓ trufflehog: 0 находок"
else
  echo "~ trufflehog не установлен — второй сканер секретов пропущен (гейт ловит только известные шаблоны)"
fi

# ── только теперь — папка назначения
if [ -n "$(ls -A "$DEST")" ]; then
  find "$DEST" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
fi
cp -R "$STAGE/." "$DEST/"
echo "── выгружено в $DEST"

cat <<EOF

✓ Снимок готов и прошёл гейт. Дальше — руками владельца (первая публикация):
    cd "$DEST"
    git init -b main
    git add -A
    git -c user.name="<имя для публики>" -c user.email="<ID+логин@users.noreply.github.com>" commit -m "Первая публичная версия"
    git remote add origin git@github.com:<владелец>/<репозиторий>.git
    git push -u origin main
  Дальше работайте прямо в этой папке: bash setup.sh включит хук pre-commit и перенаправит ~/.bazi на неё.
  Повторный запуск скрипта в ту же папку (метка $MARK разрешает замену) нужен, только если первый коммит ещё не сделан.
EOF
[ "$MODE" = "head" ] || echo "⚠ Это пробный снимок из рабочего дерева: для публикации сначала закоммитьте изменения и запустите без --worktree."
