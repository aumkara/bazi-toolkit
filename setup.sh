#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
# setup.sh — развернуть проект на машине: .venv + зависимости + скиллы для OpenCode и Claude Code + хук pre-commit.
# Идемпотентен: повторный запуск ничего не ломает. Флаг --no-skills — только окружение.
# Скиллы находят проект по symlink'у ~/.bazi → эта папка (либо по переменной BAZI_DIR), поэтому проект может
# лежать где угодно; после переноса папки достаточно `bash setup.sh --no-check`.
# Использование:  bash setup.sh [--no-skills] [--with-oracles] [--no-check] [--python /путь/к/python3]
set -euo pipefail
cd "$(dirname "$0")"
PYBIN="python3"; SKILLS=1; ORACLES=0; CHECK=1
while [ $# -gt 0 ]; do
  case "$1" in
    --no-skills) SKILLS=0 ;;
    --with-oracles) ORACLES=1 ;;   # внешние оракулы для check_all (requirements-dev.txt)
    --no-check) CHECK=0 ;;         # не гонять check_all.sh (быстрая перелинковка)
    --python) PYBIN="$2"; shift ;;
    *) echo "неизвестный аргумент: $1" >&2; exit 2 ;;
  esac
  shift
done

echo "── .venv"
[ -x .venv/bin/python ] || "$PYBIN" -m venv .venv
.venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt
.venv/bin/python -c "import swisseph, ephem; print('  swisseph', swisseph.version, '· ephem', ephem.__version__)"
if [ "$ORACLES" = 1 ]; then
  echo "── оракулы (requirements-dev.txt)"
  .venv/bin/python -m pip install -q --disable-pip-version-check -r requirements-dev.txt
  .venv/bin/python -m pip install -q --disable-pip-version-check --no-deps sxtwl==2.0.7 kinqimen==0.0.6.6   # kinqimen пинит старый ephem
fi

if [ "$SKILLS" = 1 ]; then
  echo "── скиллы (symlink'и)"
  mkdir -p ~/.config/opencode/skills ~/.claude/skills ~/.claude/commands
  link_dir() { # link_dir <папка скилла> <куда> — symlink на папку; чужую настоящую папку не трогаем
    if [ -e "$2" ] && [ ! -L "$2" ]; then echo "  ⚠ $2 уже существует и это не symlink — не трогаю"; else ln -sfn "$1" "$2"; fi
  }
  for d in skills/*/; do
    id=${d#skills/}; id=${id%/}
    link_dir "$PWD/skills/$id" ~/.config/opencode/skills/"$id"         # OpenCode: ID = имя папки
    link_dir "$PWD/skills/$id" ~/.claude/skills/"$id"                  # Claude Code: папка целиком, вместе с references/
    # прежний формат — одиночный файл-команда. Убираем только СВОЮ ссылку: на этот checkout либо повисшую
    # (checkout переехал); чужие файлы и ссылки на другие проекты не трогаем
    old=~/.claude/commands/"$id".md
    if [ -L "$old" ]; then
      target="$(readlink "$old")"
      if [ "$target" = "$PWD/skills/$id/SKILL.md" ]; then rm "$old"
      elif [ ! -e "$old" ]; then case "$target" in */skills/"$id"/SKILL.md) rm "$old" ;; esac
      fi
    fi
  done
  link_file() { # link_file <файл> <куда> — ссылка на файл; чужой обычный файл и чужую живую ссылку не заменяем
    if [ -L "$2" ]; then
      case "$(readlink "$2")" in "$1") : ;; */skills/bazi/references/*) [ -e "$2" ] && [ "$(readlink "$2")" != "$1" ] && { echo "  ⚠ $2 ведёт в другой проект — не трогаю"; return; } ;; *) echo "  ⚠ $2 — чужая ссылка, не трогаю"; return ;; esac
      ln -sf "$1" "$2"
    elif [ -e "$2" ]; then echo "  ⚠ $2 уже существует и это не symlink — не трогаю"
    else ln -s "$1" "$2"
    fi
  }
  link_file "$PWD/skills/bazi/references/bazi-year.md"    ~/.claude/commands/bazi-year.md      # подрежимы — отдельными командами Claude Code
  link_file "$PWD/skills/bazi/references/bazi-compare.md" ~/.claude/commands/bazi-compare.md
  echo "  $(ls skills | wc -l | tr -d ' ') скиллов → ~/.config/opencode/skills и ~/.claude/skills"
  # ~/.bazi → корень проекта: отсюда скиллы берут путь к калькуляторам (${BAZI_DIR:-$HOME/.bazi})
  if [ -e ~/.bazi ] && [ ! -L ~/.bazi ]; then
    echo "  ⚠ ~/.bazi уже существует и это не symlink — не трогаю. Чтобы скиллы нашли калькуляторы, задайте в окружении агента:"
    echo "      export BAZI_DIR=\"$PWD\""
  else
    ln -sfn "$PWD" ~/.bazi
    echo "  ~/.bazi → $PWD"
  fi
  if [ -n "${BAZI_DIR:-}" ] && [ "$(cd "$BAZI_DIR" 2>/dev/null && pwd -P)" != "$(pwd -P)" ]; then
    echo "  ⚠ в окружении задан BAZI_DIR=$BAZI_DIR — он перекрывает ~/.bazi и указывает не на эту папку"
  fi
fi

if git rev-parse --git-dir >/dev/null 2>&1; then
  echo "── хук pre-commit"
  git config core.hooksPath hooks        # hooks/pre-commit: гейт утечек по тому, что идёт в коммит
  echo "  core.hooksPath = hooks (перед каждым коммитом: check_public.py --staged)"
fi

if [ "$CHECK" = 1 ]; then
  echo "── проверка"
  bash check_all.sh
else
  echo "── проверка пропущена (--no-check); полная батарея: bash check_all.sh"
fi
