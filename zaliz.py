#!/usr/bin/env python3
"""Все формы слова по грамматическому словарю А. А. Зализняка.

Данные: zaliz_1.yml и zaliz_2.yml из https://github.com/jurta/nlp-rus-zaliz
(формат описан в README.md того репозитория).

Запуск:
    python3 zaliz.py стол идти          # формы указанных слов
    python3 zaliz.py                    # интерактивный режим
    python3 zaliz.py --plain шёл        # без знаков ударения

Можно вводить не только начальную форму, но и любую словоформу
(например, «столами» или «шёл») - программа найдёт исходное слово.
"""

import argparse
import os
import re
import sys
import unicodedata

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DATA_FILES = ("zaliz_1.yml", "zaliz_2.yml")

ACCENTS = "́̀"  # основное и побочное ударение (комбинируемые знаки)

# Порядок форм в свойстве «п» для каждой части речи
# (из Lingua/RU/Zaliz/Inflect.pm, хеш %paradigms).
_ADJ = ["ием", "рем", "дем", "вемн", "вемо", "тем", "пем",
        "иеж", "реж", "деж", "вежн", "вежо", "теж", "пеж",
        "иес", "рес", "дес", "весн", "весо", "тес", "пес",
        "им", "рм", "дм", "вмн", "вмо", "тм", "пм"]
_ADJ_FULL = ["п" + c for c in _ADJ] + ["кием", "киеж", "киес", "кимм"]

PARADIGMS = {
    "с": ["ие", "ре", "де", "ве", "те", "пе",
          "им", "рм", "дм", "вм", "тм", "пм"],
    "п": _ADJ_FULL + ["с"],
    "мс": ["и", "р", "д", "в", "т", "п"],
    "мс-п": _ADJ,
    "числ": ["и", "р", "д", "вн", "во", "т", "п"],
    "числ-п": _ADJ,
    "г": ["и",
          "пем", "пеж", "пес", "пм",
          "н1е", "н2е", "н3е", "н1м", "н2м", "н3м",
          "б1е", "б2е", "б3е", "б1м", "б2м", "б3м",
          "!2е", "!2м",
          "дн", "дп"]
         + [p + "-" + c for p in ("чнд", "чпд", "чнс", "чпс") for c in _ADJ_FULL],
}

POS_NAMES = {
    "с": "существительное", "п": "прилагательное", "мс": "местоимение",
    "мс-п": "местоименное прилагательное", "г": "глагол", "н": "наречие",
    "числ": "числительное", "числ-п": "счётное прилагательное",
    "вводн": "вводное слово", "межд": "междометие", "предик": "предикатив",
    "предл": "предлог", "союз": "союз", "сравн": "сравнительная степень",
    "част": "частица",
}
DECLENSIONS = {"п": "адъективное", "мс": "местоименное", "мс-п": "местоименное",
               "ч": "как у числительных"}
GENDERS = {"м": "мужской род", "ж": "женский род", "с": "средний род",
           "мж": "мужской и женский род", "мс": "мужской и средний род",
           "жс": "женский и средний род", "см": "средний и мужской род",
           "сж": "средний и женский род", "о": "общий род"}
ANIMACY = {"н": "неодушевлённое", "о": "одушевлённое",
           "но": "неодушевлённое и одушевлённое"}
ASPECTS = {"нсв": "несовершенный вид", "св": "совершенный вид",
           "св-нсв": "двувидовой"}
TRANSITIVITY = {"нп": "непереходный", "п": "переходный"}

CASES = [("и", "Именительный"), ("р", "Родительный"), ("д", "Дательный"),
         ("в", "Винительный"), ("т", "Творительный"), ("п", "Предложный")]
CASE_NAMES = dict(CASES)
ANIM_SUFFIX = {"н": " (неод.)", "о": " (одуш.)"}
GENDER_COLS = {"м": "муж. р.", "ж": "жен. р.", "с": "ср. р."}
PARTICIPLES = {"чнд": "Причастие действительное, настоящее время",
               "чпд": "Причастие действительное, прошедшее время",
               "чнс": "Причастие страдательное, настоящее время",
               "чпс": "Причастие страдательное, прошедшее время"}

# Пометы при словоформе (см. adb2yml.pl)
MARKS = {"*": "форма затруднительна", "?": "форма предположительна"}


def normalize(word):
    """Ключ поиска: нижний регистр, без ударений, ё -> е."""
    word = unicodedata.normalize("NFD", word.strip().lower())
    word = "".join(ch for ch in word if ch not in ACCENTS and ch != "̈")
    return unicodedata.normalize("NFC", word).replace("ё", "е")


def strip_accents(text):
    return "".join(ch for ch in text if ch not in ACCENTS)


def _unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


# ---------------------------------------------------------------- данные

class Dictionary:
    """Словарь: лемма -> сырые строки статьи; разбор статей ленивый."""

    _BASE_RE = re.compile(r"^[ -]*о\d?: (.*)$")

    def __init__(self, paths):
        self.entries = {}        # лемма -> список строк статьи
        self.by_norm = {}        # нормализованная лемма -> [леммы]
        self.by_base = {}        # нормализованная основа -> {леммы}
        for path in paths:
            self._load(path)

    def _load(self, path):
        lemma = None
        lines = None
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line or line.startswith("#"):
                    continue
                if line[0] not in " -" or (line.endswith(":") and not line.startswith("- ")
                                           and ": " not in line):
                    lemma = line[:-1]
                    lines = self.entries.setdefault(lemma, [])
                    self.by_norm.setdefault(normalize(lemma), []).append(lemma)
                    continue
                lines.append(line)
                m = self._BASE_RE.match(line)
                if m:
                    base = normalize(_unquote(m.group(1)))
                    self.by_base.setdefault(base, set()).add(lemma)

    def lookup(self, word):
        """Леммы, у которых заглавное слово совпадает с word."""
        return list(dict.fromkeys(self.by_norm.get(normalize(word), [])))

    def lemmas_of_form(self, word):
        """Леммы, среди словоформ которых есть word."""
        key = normalize(word)
        candidates = set()
        for i in range(len(key) + 1):
            candidates |= self.by_base.get(key[:i], set())
        found = []
        for lemma in sorted(candidates):
            for meaning in self.parse(lemma):
                if any(key in {normalize(f.text) for f in forms}
                       for v in meaning for _, forms in inflect(v)):
                    found.append(lemma)
                    break
        return found

    def parse(self, lemma):
        """Статья -> список значений, каждое - список вариантов (dict)."""
        meanings = []
        record = None
        for line in self.entries.get(lemma, []):
            prefix = re.match(r"^[ -]*", line).group(0)
            if "-" in prefix or record is None:
                record = {}
                if line.startswith("-") or not meanings:
                    meanings.append([])
                meanings[-1].append(record)
            key, _, value = line[len(prefix):].partition(": ")
            if key == "с" and value.startswith("{"):
                # краткие свойства хранятся отдельно: их «о» (одушевлённость)
                # не должно смешиваться с основой «о»
                record["с"] = {k: _unquote(v) for k, v in
                               re.findall(r'([^\s{},:]+): ("[^"]*"|[^,}]*)', value)}
            else:
                record[key] = _unquote(value)
        return meanings


# ---------------------------------------------------------------- формы

class Form:
    __slots__ = ("text", "notes")

    def __init__(self, text, notes=()):
        self.text = text
        self.notes = list(notes)

    def render(self, plain=False):
        text = strip_accents(self.text) if plain else self.text
        prefix = ""
        notes = []
        for note in self.notes:
            if note.startswith("П2:"):
                prep = note[3:]
                if prep:
                    prefix = "/".join(prep.split(",")) + " "
                else:
                    notes.append("П2")
            else:
                notes.append(note)
        return prefix + text + (" (" + ", ".join(notes) + ")" if notes else "")


_SUFFIX_RE = re.compile(r"^(\d*)(.*?)(\([^)]*\))?(\[[^\]]*\])?(\[\])?([*?-])?$")


def parse_form(token, record):
    """Элемент свойства «п» -> Form или None (если формы нет)."""
    if token == "-":
        return None
    m = _SUFFIX_RE.match(token)
    num, suffix, comment, bracket, r2, mark = m.groups()
    if mark == "-":
        return None
    notes = []
    if comment:
        notes.append(comment[1:-1])
    if bracket == "[]":            # [] без предлога - 2-й родительный
        bracket, r2 = None, bracket
    if bracket:
        prep = bracket[1:-1]
        notes.append("П2:" + ("" if prep == ":" else prep))
    if r2:
        notes.append("Р2")
    if mark:
        notes.append(MARKS[mark])
    base = record.get("о" + num, "")
    return Form(base + suffix, notes)


def inflect(record):
    """Вариант статьи -> список (код, [Form...]) в порядке парадигмы."""
    paradigm_str = record.get("п")
    if paradigm_str is None:
        return []
    codes = PARADIGMS.get(record.get("с", {}).get("т"))
    slots = paradigm_str.split(";")
    if codes is None or len(codes) != len(slots):
        codes = [str(i + 1) for i in range(len(slots))]
    result = []
    for code, slot in zip(codes, slots):
        forms = [parse_form(t, record) for t in slot.split(",")]
        result.append((code, [f for f in forms if f is not None]))
    return result


# ---------------------------------------------------------------- вывод

def slot_place(pos, code):
    """Код формы -> (раздел, строка, столбец) для табличного вывода."""
    if pos == "с":
        return "", CASE_NAMES[code[0]], "ед. ч." if code[1] == "е" else "мн. ч."
    if pos == "мс":
        return "", CASE_NAMES[code], ""
    if pos == "числ":
        return "", CASE_NAMES[code[0]] + ANIM_SUFFIX.get(code[1:], ""), ""
    if pos in ("мс-п", "числ-п"):
        return adj_place("", "п" + code)
    if pos == "п":
        return adj_place("", code)
    if pos == "г":
        if code == "и":
            return "Инфинитив", "", ""
        if code[0] == "п":
            col = "мн. ч." if code == "пм" else GENDER_COLS[code[2]]
            return "Прошедшее время", col, ""
        if code[0] in "нб!":
            title = {"н": "Настоящее время", "б": "Будущее время",
                     "!": "Повелительное наклонение"}[code[0]]
            return title, code[1] + "-е лицо", "ед. ч." if code[2] == "е" else "мн. ч."
        if code[0] == "д":
            return "Деепричастие", "наст. вр." if code == "дн" else "прош. вр.", ""
        if code[0] == "ч":
            part, _, adj = code.partition("-")
            return adj_place(PARTICIPLES[part], adj)
    return "", code, ""


def adj_place(title, code):
    sep = ". " if title else ""
    if code == "с":
        return title + sep + "Сравнительная степень", "", ""
    if code[0] == "к":
        col = "мн. ч." if code == "кимм" else GENDER_COLS[code[3]]
        return title + sep + "Краткая форма", "", col
    case, number, rest = code[1], code[2], code[3:]
    if number == "м":
        return title, CASE_NAMES[case] + ANIM_SUFFIX.get(rest, ""), "мн. ч."
    return title, CASE_NAMES[case] + ANIM_SUFFIX.get(rest[1:], ""), GENDER_COLS[rest[0]]


def _width(text):
    return sum(1 for ch in text if not unicodedata.combining(ch))


def _pad(text, width):
    return text + " " * (width - _width(text))


def render_table(rows, cols, cells):
    """Простая текстовая таблица; cells[(row, col)] -> строка."""
    show_cols = cols != [""]
    show_rows = rows != [""]
    header = ([""] if show_rows else []) + (cols if show_cols else [])
    table = []
    for r in rows:
        line = ([r] if show_rows else []) + [cells.get((r, c), "—") for c in cols]
        table.append(line)
    if show_cols:
        table.insert(0, header)
    widths = [max(_width(line[i]) for line in table) for i in range(len(table[0]))]
    return ["  " + "   ".join(_pad(v, w) for v, w in zip(line, widths)).rstrip()
            for line in table]


def describe(record):
    """Краткие грамматические сведения о варианте статьи."""
    record = record.get("с", {})
    parts = []
    pos = record.get("т")
    if pos:
        parts.append(POS_NAMES.get(pos, pos))
    if record.get("т2") and record["т2"] != pos and not (record["т2"] == "ч" and pos == "числ"):
        parts.append("склонение " + DECLENSIONS.get(record["т2"], record["т2"]))
    if record.get("р"):
        parts.append(GENDERS.get(record["р"], record["р"]))
    if record.get("о") and pos == "с" and record["о"] in ANIMACY:
        parts.append(ANIMACY[record["о"]])
    if record.get("гв"):
        parts.append(ASPECTS.get(record["гв"], record["гв"]))
    if record.get("гп"):
        parts.append(TRANSITIVITY.get(record["гп"], record["гп"]))
    if record.get("гбл"):
        parts.append("безличный")
    if record.get("и") not in (None, ""):
        index = record["и"] + ("*" if record.get("ч") else "") + record.get("у1", "")
        if record.get("у2"):
            index += "/" + record["у2"]
        parts.append("тип " + index)
    return ", ".join(parts)


def render_record(record, plain=False):
    lines = []
    info = describe(record)
    if info:
        lines.append("  [" + info + "]")
    for key in ("з", "з2", "з3"):
        if record.get(key):
            lines.append("  Значение/помета: " + record[key])
    slots = inflect(record)
    if not slots:
        lines.append("  (неизменяемое слово)")
        return lines
    pos = record.get("с", {}).get("т")
    sections = {}  # раздел -> (строки, столбцы, ячейки)
    for code, forms in slots:
        title, row, col = slot_place(pos, code)
        rows, cols, cells = sections.setdefault(title, ([], [], {}))
        if row not in rows:
            rows.append(row)
        if col not in cols:
            cols.append(col)
        if forms:
            cells[(row, col)] = ", ".join(dict.fromkeys(f.render(plain) for f in forms))
    for title, (rows, cols, cells) in sections.items():
        if not cells:
            continue  # ни одной существующей формы в разделе
        lines.append("")
        if title:
            lines.append("  " + title + ":")
        lines.extend(render_table(rows, cols, cells))
    return lines


def render_lemma(dictionary, lemma, plain=False):
    meanings = dictionary.parse(lemma)
    lines = ["=" * 60, lemma.upper(), "=" * 60]
    for i, variants in enumerate(meanings, 1):
        if len(meanings) > 1:
            lines.append("")
            lines.append(f"Значение {i}:")
        for j, record in enumerate(variants, 1):
            if len(variants) > 1:
                lines.append("")
                lines.append(f" Вариант склонения {j}:")
            lines.extend(render_record(record, plain))
    return "\n".join(lines)


def answer(dictionary, word, plain=False):
    lemmas = dictionary.lookup(word)
    other = [l for l in dictionary.lemmas_of_form(word) if l not in lemmas]
    if not lemmas and not other:
        return f"Слово «{word}» не найдено в словаре."
    out = [render_lemma(dictionary, l, plain) for l in lemmas]
    if lemmas and other:
        out.append(f"\n«{word}» также является формой слов: " + ", ".join(other))
    elif other:
        out.append(f"«{word}» - форма слов: " + ", ".join(other))
        out += [render_lemma(dictionary, l, plain) for l in other]
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Все формы слова по словарю Зализняка (jurta/nlp-rus-zaliz).")
    parser.add_argument("words", nargs="*", help="слова (без них - интерактивный режим)")
    parser.add_argument("--plain", action="store_true", help="не показывать ударения")
    parser.add_argument("--data", default=DATA_DIR, help="каталог с zaliz_1.yml и zaliz_2.yml")
    args = parser.parse_args(argv)

    paths = [os.path.join(args.data, name) for name in DATA_FILES]
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        sys.exit("Не найдены файлы словаря: " + ", ".join(missing))

    if not args.words:
        print("Загрузка словаря...", file=sys.stderr)
    dictionary = Dictionary(paths)

    if args.words:
        print("\n\n".join(answer(dictionary, w, args.plain) for w in args.words))
        return
    print("Введите слово (пустая строка или Ctrl+D - выход).")
    while True:
        try:
            word = input("\nСлово: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not word:
            break
        print(answer(dictionary, word, args.plain))


if __name__ == "__main__":
    main()
