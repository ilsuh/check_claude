#!/usr/bin/env python3
"""Сборка статического сайта для GitHub Pages.

    python3 build_site.py [каталог]     # по умолчанию _site

Словарь раскладывается на небольшие JSON-файлы (шарды) по первым трём
буквам словоформы: страница по введённому слову загружает только один шард,
в котором есть все леммы, имеющие словоформу с таким началом.
"""

import json
import os
import shutil
import sys

import zaliz

ROOT = os.path.dirname(os.path.abspath(__file__))
PREFIX_LEN = 3


def shard_name(key):
    """Имя файла шарда: UTF-8 начала слова в шестнадцатеричном виде."""
    return key[:PREFIX_LEN].encode("utf-8").hex()


def encode_form(form):
    """Form -> строка или [текст, предлоги П2, пометы]."""
    prep, notes = "", []
    for note in form.notes:
        if note.startswith("П2:"):
            prep = note[3:].replace(",", "/")
            if not prep:
                notes.append("П2")
        else:
            notes.append(note)
    if not prep and not notes:
        return form.text
    return [form.text, prep, ", ".join(notes)]


def encode_record(record):
    """Вариант статьи -> компактный dict для страницы."""
    props = record.get("с", {})
    out = {"t": props.get("т", ""), "i": zaliz.describe(record)}
    notes = [record[k] for k in ("з", "з2", "з3") if record.get(k)]
    if notes:
        out["z"] = notes
    slots = zaliz.inflect(record)
    if slots:
        if zaliz.PARADIGMS.get(out["t"]) is None or \
                len(zaliz.PARADIGMS[out["t"]]) != len(slots):
            out["t"] = ""  # неизвестный порядок форм - покажем списком
        out["f"] = [[encode_form(f) for f in forms] for _, forms in slots]
    return out


def main():
    out_dir = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "_site"))
    paths = [os.path.join(zaliz.DATA_DIR, n) for n in zaliz.DATA_FILES]
    dictionary = zaliz.Dictionary(paths)

    shards = {}
    for lemma in dictionary.entries:
        meanings = dictionary.parse(lemma)
        keys = {zaliz.normalize(lemma)}
        for variants in meanings:
            for record in variants:
                for _, forms in zaliz.inflect(record):
                    keys.update(zaliz.normalize(f.text) for f in forms)
        entry = [[encode_record(r) for r in variants] for variants in meanings]
        for name in {shard_name(k) for k in keys if k}:
            shards.setdefault(name, {})[lemma] = entry

    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    shutil.copytree(os.path.join(ROOT, "site"), out_dir)
    data_dir = os.path.join(out_dir, "d")
    os.makedirs(data_dir)
    total = 0
    for name, entries in shards.items():
        path = os.path.join(data_dir, name + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, separators=(",", ":"))
        total += os.path.getsize(path)
    # .nojekyll: отдавать файлы как есть, без обработки Jekyll
    open(os.path.join(out_dir, ".nojekyll"), "w").close()
    print(f"{len(dictionary.entries)} лемм, {len(shards)} шардов, "
          f"{total / 1e6:.1f} МБ -> {out_dir}")


if __name__ == "__main__":
    main()
