#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Tim
"""check_public.py — гейт утечек: что не должно попасть в публичный репозиторий.

Запуск:
  python3 check_public.py               # файлы, которые уйдут в снимок: git-файлы (и новые) минус .gitignore и export-ignore
  python3 check_public.py --tree ПАПКА  # готовый снимок (его делает publish_snapshot.sh) — все файлы папки
  python3 check_public.py --staged      # только то, что проиндексировано для коммита (хук hooks/pre-commit)
  python3 check_public.py --test        # самопроверка на подложенных утечках

Что ищет в каждом файле и в его имени (текст и байты бинарных файлов):
  • домашние пути (`/Users/<имя>`, `/home/<имя>`, следы scratch-каталогов агентов);
  • email-адреса (кроме служебных noreply/example);
  • токены и ключи по известным префиксам, URL с логином и паролем;
  • файлы, которым в публичном дереве не место: личные чтения, резервные копии, архивы, symlink'и,
    рабочее состояние агентов.
Только на машине владельца (чего нет — честно пропускается):
  • даты рождения из имён локальных чтений (`profiles/`, `chart_*`, `Подарок_*`, `year_*`) в любой записи:
    ГГГГ-ММ-ДД, ДД.ММ.ГГГГ, Д/М/ГГГГ, кортеж (ГГГГ, М, Д); датой рождения считается КАЖДАЯ дата в имени
    (у папки пары их две), кроме даты с меткой прогона `run-` (`…__run-2026-11-17`): без метки дата прогона
    попала бы в этот список, и гейт начал бы блокировать любой файл с ней — например CHANGELOG.md;
  • строки из локального `.public-denylist` (по одной на строку, `#` — комментарий): ники, домены, имена.
Выход 0 — чисто, 1 — есть находки.

Чего гейт НЕ видит (это сито по известным шаблонам, не доказательство отсутствия утечек):
  • имена людей, время рождения и даты, которых нет в именах локальных чтений и в denylist;
  • секреты без узнаваемого префикса — для них второй сканер (publish_snapshot.sh запускает trufflehog);
  • текст внутри сжатых потоков PDF и картинок — такие файлы перед публикацией смотреть глазами.
"""
import fnmatch
import os
import re
import subprocess
import sys
import tempfile

DIR = os.path.dirname(os.path.abspath(__file__))

FORBIDDEN_FILES = ["profiles/*", "profiles_backup_*", "chart_*.md", "chart_*.pdf", "chart_*.json", "Подарок_*", "year_*_*.md",
                   "calendar_2026/*", "*.bak", "*.bak_*", ".env", ".env.*", "*.pem", "*.key", "wg.conf", ".claude/*",
                   ".opencode/*", "PROGRESS.md", "tasks.json", ".public-denylist", "docs/private/*", "bench/out/*",
                   "*.zip", "*.tar", "*.tar.gz", "*.tgz", "*.7z", "*.rar"]   # архивы гейт не раскрывает — им тут не место
EMAIL_OK = re.compile(r"^(noreply|no-reply)@|@users\.noreply\.github\.com$|@example\.(com|org|net)$|^git@", re.I)
PATTERNS = [
    ("домашний путь", re.compile(r"/Users/[A-Za-z0-9._-]+|/home/[a-z0-9._-]+/|-Users-[A-Za-z0-9]|/private/tmp/cl[a]ude")),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")),
    ("токен или ключ", re.compile(
        r"glpat-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{24,}"
        r"|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|PrivateKey\s*=\s*[A-Za-z0-9+/]{40,}")),
    ("URL с паролем", re.compile(r"https?://[^/\s:@\"'<>]+:[^/\s@\"'<>]+@[A-Za-z0-9.-]+")),
]
DATE_IN_NAME = re.compile(r"(?<!run-)(?:19|20)\d{2}-\d{2}-\d{2}")   # дата после метки run- — дата прогона, не рождения


def date_regex(iso):
    """Одна дата во всех ходовых записях: ГГГГ-ММ-ДД, ДД.ММ.ГГГГ, Д/М/ГГГГ, кортеж (ГГГГ, М, Д)."""
    y, m, d = iso.split("-")
    m, d = int(m), int(d)
    sep = r"\s*[,./ -]\s*"
    return re.compile(rf"(?<!\d){y}{sep}0?{m}{sep}0?{d}(?!\d)|(?<!\d)0?{d}{sep}0?{m}{sep}{y}(?!\d)")


def local_dates(root):
    """Даты из имён локальных чтений → {ISO-дата: шаблон всех её записей}. Пусто, если чтений на машине нет."""
    names = []
    try:
        names += os.listdir(os.path.join(root, "profiles"))
    except OSError:
        pass
    try:
        names += [n for n in os.listdir(root) if n.startswith(("chart_", "Подарок_", "year_"))]
    except OSError:
        pass
    return {iso: date_regex(iso) for n in names for iso in DATE_IN_NAME.findall(n)}


def local_denylist(root):
    try:
        lines = open(os.path.join(root, ".public-denylist"), encoding="utf-8").read().split("\n")
    except OSError:
        return []
    return [ln.strip().lower() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def snapshot_files(root):
    """Файлы git (отслеживаемые и новые, не из .gitignore) без export-ignore — то, что уйдёт в публичный снимок."""
    ls = subprocess.run(["git", "-C", root, "ls-files", "-z", "-co", "--exclude-standard"], capture_output=True)
    if ls.returncode != 0:
        raise RuntimeError("не git-репозиторий: задайте --tree ПАПКА")
    files = [f for f in ls.stdout.decode("utf-8").split("\0") if f]
    attr = subprocess.run(["git", "-C", root, "check-attr", "-z", "--stdin", "export-ignore"],
                          input="\0".join(files).encode("utf-8"), capture_output=True)
    fields = attr.stdout.decode("utf-8").split("\0")
    ignored = {fields[n] for n in range(0, len(fields) - 2, 3) if fields[n + 2] == "set"}
    return [f for f in files if f not in ignored and os.path.exists(os.path.join(root, f))]


def staged_files(root):
    """Проиндексированные для коммита файлы и их содержимое из индекса (а не с диска) + множество symlink'ов."""
    ls = subprocess.run(["git", "-C", root, "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMRT"], capture_output=True)
    if ls.returncode != 0:
        raise RuntimeError("не git-репозиторий")
    files = [f for f in ls.stdout.decode("utf-8").split("\0") if f]
    modes = subprocess.run(["git", "-C", root, "ls-files", "-s", "-z", "--", *files], capture_output=True).stdout.decode("utf-8") if files else ""
    links = {rec.split("\t", 1)[1] for rec in modes.split("\0") if rec.startswith("120000")}

    def read(rel):
        return subprocess.run(["git", "-C", root, "show", f":{rel}"], capture_output=True, check=True).stdout
    return files, read, links


def tree_files(root):
    if not os.path.isdir(root):
        raise FileNotFoundError(f"нет такой папки: {root}")
    out = []
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        links = [d for d in dirs if os.path.islink(os.path.join(base, d))]   # os.walk в них не заходит — отметим сами
        out += [os.path.relpath(os.path.join(base, n), root) for n in names + links]
    return sorted(out)


def _mask(kind, text):
    return text[:6] + "…" if kind in ("токен или ключ", "URL с паролем") else text[:80]


def _decode(raw):
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError:
            pass
    return raw.decode("latin-1")     # бинарный файл (PDF): ищем те же шаблоны в байтах


def scan(root, files, dates=None, deny=None, read=None, links=None):
    """→ список находок (путь, строка, вид, фрагмент). Строка 0 — находка в самом имени файла.
    read(путь) → байты и links (множество symlink'ов) задаются для проверки индекса; по умолчанию читается диск."""
    dates, deny, found = dates or {}, deny or [], []

    def check(rel, n, line):
        for kind, rx in PATTERNS:
            for m in rx.finditer(line):
                if kind == "email" and EMAIL_OK.search(m.group(0)):
                    continue
                found.append((rel, n, kind, _mask(kind, m.group(0))))
        for iso, rx in dates.items():
            m = rx.search(line)
            if m:
                found.append((rel, n, "дата из локальных чтений", f"{m.group(0)} (чтение от {iso})"))
        low = line.lower()
        for word in deny:
            if word in low:
                found.append((rel, n, "строка из .public-denylist", word))

    for rel in files:
        unix = rel.replace(os.sep, "/")
        full = os.path.join(root, rel)
        hit = next((p for p in FORBIDDEN_FILES if fnmatch.fnmatch(unix, p) or fnmatch.fnmatch(os.path.basename(unix), p)), None)
        if hit:
            found.append((rel, 0, "файл не для публикации", f"шаблон {hit}"))
            continue
        if (rel in links) if links is not None else os.path.islink(full):
            found.append((rel, 0, "symlink", "цель ссылки гейт не проверяет — в публичном дереве ссылок быть не должно"))
            continue
        check(rel, 0, unix)
        try:
            raw = read(rel) if read else open(full, "rb").read()
        except (OSError, subprocess.CalledProcessError) as e:
            found.append((rel, 0, "файл не читается", str(e)))
            continue
        for n, line in enumerate(_decode(raw).split("\n"), 1):
            check(rel, n, line)
    return found


def _test():
    from datetime import date, timedelta

    ok = True

    def chk(cond, label):
        nonlocal ok
        ok &= bool(cond)
        print(("  ✓ " if cond else "  ✗ ") + label)

    with tempfile.TemporaryDirectory() as tmp:
        def put(name, text):
            path = os.path.join(tmp, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)

        # утечки собираются по частям, чтобы сам этот файл не содержал ни одного шаблона целиком
        put("clean.md", "Карта 1990-05-15 14:30, Москва. Путь: /путь/к/bazi, почта: bot@example.com\n")
        put("path.py", "ROOT = '" + "/Us" + "ers/" + "someone/Documents'\n")
        put("mail.md", "пишите на " + "person" + "@" + "mail.test\n")
        put("token.env.txt", "TOKEN=" + "glp" + "at-" + "x" * 24 + "\n")
        put("url.txt", "https://" + "user:pa55" + "@" + "host.test/repo.git\n")
        put("date.md", "родился 03.02.1971, см. 1971-02-03\n")
        put("tuple.py", "ANCHOR = ('Город', (1971, 2, 3), 3)\n")
        put("fake_noreply.md", "почта: " + "person+noreply" + "@" + "corp.test\n")
        put("good_noreply.md", "автор: 12345+user@users.noreply.github.com, noreply@corp.test\n")
        os.symlink(os.path.join(tmp, "clean.md"), os.path.join(tmp, "link.md"))
        os.symlink(tmp, os.path.join(tmp, "linkdir"))
        put("nick.md", "автор — SecretNick\n")
        put("profiles/1971-02-03_Город/1_bazi.md", "личное чтение\n")
        # Вторую синтетическую дату получаем сдвигом нейтральной фикстуры проекта.
        pair_date = date(1990, 5, 15) + timedelta(days=1)
        put(f"profiles/compat__1971-02-03_Город__{pair_date.isoformat()}_Город/1.md", "чтение пары\n")
        put("profiles/1971-02-03_Город__run-2001-01-01/1_bazi.md", "повторный прогон\n")
        put("date2.md", f"второй человек пары: {pair_date:%d.%m.%Y}\n")
        put("rundate.md", "выпуск от 2001-01-01\n")
        put("old.py.bak", "x = 1\n")
        files = tree_files(tmp)
        found = scan(tmp, files, dates=local_dates(tmp), deny=["secretnick"])
        by = {}
        for rel, _n, kind, _x in found:
            by.setdefault(rel.replace(os.sep, "/"), set()).add(kind)
        chk("clean.md" not in by, "чистый файл с нейтральной датой и example.com не задет")
        chk(by.get("path.py") == {"домашний путь"}, "домашний путь найден")
        chk(by.get("mail.md") == {"email"}, "email найден")
        chk(by.get("token.env.txt") == {"токен или ключ"}, "токен найден")
        chk("URL с паролем" in by.get("url.txt", set()), "URL с паролем найден")
        chk(by.get("date.md") == {"дата из локальных чтений"}, "дата из имени локального чтения найдена в записях ГГГГ-ММ-ДД и ДД.ММ.ГГГГ")
        chk(by.get("tuple.py") == {"дата из локальных чтений"}, "та же дата найдена в записи кортежем (ГГГГ, М, Д)")
        chk(by.get("date2.md") == {"дата из локальных чтений"}, "вторая дата рождения из имени папки пары тоже защищена")
        chk("rundate.md" not in by and "2001-01-01" not in local_dates(tmp),
            "дата прогона с меткой run- в имени папки датой рождения не считается")
        chk(by.get("fake_noreply.md") == {"email"} and "good_noreply.md" not in by, "«noreply» в середине адреса не спасает; настоящие noreply-адреса пропущены")
        chk(by.get("link.md") == {"symlink"} and by.get("linkdir") == {"symlink"}, "symlink на файл и на папку отмечены")
        chk(by.get("nick.md") == {"строка из .public-denylist"}, "строка из denylist найдена без учёта регистра")
        chk(by.get("profiles/1971-02-03_Город/1_bazi.md") == {"файл не для публикации"} and by.get("old.py.bak") == {"файл не для публикации"},
            "личное чтение и .bak отмечены как файлы не для публикации")
        chk(not any("x" * 24 in frag for _r, _n, _k, frag in found), "токен в выводе замаскирован")
    try:
        tree_files(os.path.join(tempfile.gettempdir(), "нет-такой-папки-check-public"))
        chk(False, "несуществующая папка — ошибка, а не «чисто»")
    except FileNotFoundError:
        chk(True, "несуществующая папка — ошибка, а не «чисто»")
    print("check_public --test:", "ЗЕЛЕНО ✓" if ok else "КРАСНОЕ ✗")
    return 0 if ok else 1


def main(argv):
    if "--test" in argv:
        return _test()
    read = links = None
    try:
        if "--staged" in argv:
            root = DIR
            (files, read, links), what = staged_files(root), "проиндексировано для коммита"
        elif "--tree" in argv:
            root = os.path.abspath(argv[argv.index("--tree") + 1])
            files, what = tree_files(root), f"снимок {root}"
        else:
            root = DIR
            files, what = snapshot_files(root), "файлы git без export-ignore"
    except IndexError:
        sys.stderr.write("ОШИБКА: --tree ожидает папку\n")
        return 2
    except FileNotFoundError as e:
        sys.stderr.write(f"ОШИБКА: {e}\n")
        return 2
    except RuntimeError:
        # скачанный архив без .git: списка файлов снимка взять неоткуда — честный пропуск, не ложная тревога
        print("check_public: это не git-репозиторий — гейт пропущен (для готовой папки: check_public.py --tree ПАПКА)")
        return 0
    dates, deny = local_dates(DIR), local_denylist(DIR)
    found = scan(root, files, dates, deny, read=read, links=links)
    for rel, n, kind, frag in found:
        print(f"✗ {rel}{':' + str(n) if n else ''}: {kind} — {frag}")
    if found and "--staged" in argv:
        print("Коммит остановлен: уберите находки из индекса (git restore --staged ФАЙЛ) или исправьте их. "
              "Обход через --no-verify публикует их навсегда.")
    local = (f"локальные проверки: {len(dates)} дат из чтений" if dates else "локальных чтений нет — даты не проверялись") \
        + (f", {len(deny)} строк denylist" if deny else ", .public-denylist нет")
    print(f"check_public: {len(files)} файлов ({what}); {local}; находок: {len(found)}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
