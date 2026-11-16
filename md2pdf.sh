#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
# md2pdf.sh — Markdown → PDF через headless Google Chrome (без pandoc/LaTeX).
# Рендерит кириллицу, китайские иероглифы (八字) и таблицы; цветные эмодзи
# конвертер заранее заменяет на моно-символы (headless Chrome их не встраивает).
#
# Использование:
#   ./md2pdf.sh файл.md [файл2.md ...]   — конкретные файлы
#   ./md2pdf.sh путь/к/папке             — все *.md в папке (без рекурсии)
# Рядом с каждым X.md создаётся X.pdf. Переопределить браузер: CHROME=... ./md2pdf.sh
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MD2HTML="$SCRIPT_DIR/md2html.py"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
[ -f "$MD2HTML" ] || { echo "Нет $MD2HTML"; exit 1; }
[ -x "$CHROME" ] || { echo "Нет Google Chrome: $CHROME (задай переменную CHROME=путь)"; exit 1; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/md2pdf.XXXXXX")"
trap 'pkill -9 -f "$TMP" 2>/dev/null; rm -rf "$TMP"' EXIT

mds=()
for arg in "$@"; do
  if [ -d "$arg" ]; then
    while IFS= read -r f; do mds+=("$f"); done < <(find "$arg" -maxdepth 1 -name '*.md' | sort)
  elif [ -f "$arg" ]; then mds+=("$arg")
  else echo "пропуск (нет такого): $arg"; fi
done
[ ${#mds[@]} -gt 0 ] || { echo "Использование: md2pdf.sh файл.md ... | папка"; exit 1; }

n=0; ok=0; fail=0
for md in "${mds[@]}"; do
  n=$((n+1)); pdf="${md%.md}.pdf"; html="$TMP/$n.html"
  if ! python3 "$MD2HTML" "$md" "$(basename "${md%.md}")" > "$html"; then
    echo "✗ html: $md"; fail=$((fail+1)); continue
  fi
  rm -f "$pdf"
  # legacy --headless: --headless=new зависает на этой связке; не менять без проверки
  "$CHROME" --headless --disable-gpu --no-pdf-header-footer \
    --user-data-dir="$TMP/cp_$n" --print-to-pdf="$pdf" "file://$html" >/dev/null 2>&1 &
  pid=$!
  # ждать, пока Chrome ДОПИШЕТ pdf: размер стабилен 2 замера подряд И есть концевой маркер %%EOF
  # (иначе kill -9 мог обрезать большой документ — у усечённого pdf всё равно валидный заголовок %PDF)
  prev=-1
  for _ in $(seq 1 120); do
    sleep 0.5
    [ -s "$pdf" ] || continue
    cur=$(wc -c < "$pdf" 2>/dev/null | tr -d ' ')
    if [ "$cur" = "$prev" ] && tail -c 2048 "$pdf" 2>/dev/null | grep -qa '%%EOF'; then break; fi
    prev=$cur
  done
  kill -9 "$pid" 2>/dev/null
  # успех ТОЛЬКО если pdf непустой И завершён маркером %%EOF; усечённый/пустой — удалить и в fail
  if [ -s "$pdf" ] && tail -c 2048 "$pdf" 2>/dev/null | grep -qa '%%EOF'; then
    echo "✓ $(basename "$pdf")"; ok=$((ok+1))
  else
    echo "✗ $(basename "$md") (PDF неполный/пустой)"; rm -f "$pdf"; fail=$((fail+1))
  fi
done
echo "PDF: ok=$ok fail=$fail"
[ "$fail" -eq 0 ]
