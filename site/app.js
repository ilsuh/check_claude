"use strict";

// Порядок форм для каждой части речи (как PARADIGMS в zaliz.py).
const ADJ = ["ием", "рем", "дем", "вемн", "вемо", "тем", "пем",
             "иеж", "реж", "деж", "вежн", "вежо", "теж", "пеж",
             "иес", "рес", "дес", "весн", "весо", "тес", "пес",
             "им", "рм", "дм", "вмн", "вмо", "тм", "пм"];
const ADJ_FULL = ADJ.map(c => "п" + c).concat(["кием", "киеж", "киес", "кимм"]);
const PARADIGMS = {
  "с": ["ие", "ре", "де", "ве", "те", "пе", "им", "рм", "дм", "вм", "тм", "пм"],
  "п": ADJ_FULL.concat(["с"]),
  "мс": ["и", "р", "д", "в", "т", "п"],
  "мс-п": ADJ,
  "числ": ["и", "р", "д", "вн", "во", "т", "п"],
  "числ-п": ADJ,
  "г": ["и", "пем", "пеж", "пес", "пм",
        "н1е", "н2е", "н3е", "н1м", "н2м", "н3м",
        "б1е", "б2е", "б3е", "б1м", "б2м", "б3м",
        "!2е", "!2м", "дн", "дп"]
       .concat(...["чнд", "чпд", "чнс", "чпс"].map(p => ADJ_FULL.map(c => p + "-" + c))),
};
const CASES = {"и": "Именительный", "р": "Родительный", "д": "Дательный",
               "в": "Винительный", "т": "Творительный", "п": "Предложный"};
const ANIM = {"н": " (неод.)", "о": " (одуш.)"};
const GENDER = {"м": "муж. р.", "ж": "жен. р.", "с": "ср. р."};
const PARTICIPLES = {"чнд": "Причастие действительное, настоящее время",
                     "чпд": "Причастие действительное, прошедшее время",
                     "чнс": "Причастие страдательное, настоящее время",
                     "чпс": "Причастие страдательное, прошедшее время"};
const SG = "ед. ч.", PL = "мн. ч.";

function adjPlace(title, code) {
  const sep = title ? ". " : "";
  if (code === "с") return [title + sep + "Сравнительная степень", "", ""];
  if (code[0] === "к") return [title + sep + "Краткая форма", "", code === "кимм" ? PL : GENDER[code[3]]];
  const kase = code[1], num = code[2], rest = code.slice(3);
  if (num === "м") return [title, CASES[kase] + (ANIM[rest] || ""), PL];
  return [title, CASES[kase] + (ANIM[rest.slice(1)] || ""), GENDER[rest[0]]];
}

// Код формы -> [раздел, строка, столбец]
function slotPlace(pos, code) {
  switch (pos) {
    case "с": return ["", CASES[code[0]], code[1] === "е" ? SG : PL];
    case "мс": return ["", CASES[code], ""];
    case "числ": return ["", CASES[code[0]] + (ANIM[code.slice(1)] || ""), ""];
    case "мс-п": case "числ-п": return adjPlace("", "п" + code);
    case "п": return adjPlace("", code);
    case "г":
      if (code === "и") return ["Инфинитив", "", ""];
      if (code[0] === "п") return ["Прошедшее время", code === "пм" ? PL : GENDER[code[2]], ""];
      if ("нб!".includes(code[0])) {
        const title = {"н": "Настоящее время", "б": "Будущее время",
                       "!": "Повелительное наклонение"}[code[0]];
        return [title, code[1] + "-е лицо", code[2] === "е" ? SG : PL];
      }
      if (code[0] === "д") return ["Деепричастие", code === "дн" ? "наст. вр." : "прош. вр.", ""];
      if (code[0] === "ч") {
        const [part, adj] = code.split("-");
        return adjPlace(PARTICIPLES[part], adj);
      }
  }
  return ["", code, ""];
}

// Ключ поиска: нижний регистр, без ударений, ё -> е (как normalize в zaliz.py).
function normalize(word) {
  return word.trim().toLowerCase().normalize("NFD")
    .replace(/[̀́̈]/g, "").normalize("NFC").replace(/ё/g, "е");
}
const stripAccents = s => s.replace(/[̀́]/g, "");
const formText = f => (typeof f === "string" ? f : f[0]);

const shardCache = new Map();
function shardName(key) {
  const prefix = Array.from(key).slice(0, 3).join("");
  return Array.from(new TextEncoder().encode(prefix), b => b.toString(16).padStart(2, "0")).join("");
}
function loadShard(key) {
  const name = shardName(key);
  if (!shardCache.has(name)) {
    shardCache.set(name, fetch("d/" + name + ".json")
      .then(r => (r.ok ? r.json() : {}))
      .catch(() => { shardCache.delete(name); throw new Error("network"); }));
  }
  return shardCache.get(name);
}

function hasForm(entry, key) {
  return entry.some(variants => variants.some(rec =>
    (rec.f || []).some(slot => slot.some(f => normalize(formText(f)) === key))));
}

// ---------------------------------------------------------------- вывод

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
  for (const c of children) node.append(c);
  return node;
}

function renderForm(f, key, plain) {
  let text = formText(f);
  const prep = typeof f === "string" ? "" : f[1];
  const notes = typeof f === "string" ? "" : f[2];
  if (plain) text = stripAccents(text);
  const span = el("span");
  if (prep) span.append(prep + " ");
  span.append(normalize(text) === key ? el("mark", {}, text) : text);
  if (notes) span.append(" ", el("span", {class: "n"}, "(" + notes + ")"));
  return span;
}

function renderCell(forms, key, plain) {
  const td = el("td");
  if (!forms || !forms.length) {
    td.className = "absent";
    td.textContent = "—";
    return td;
  }
  const seen = new Set();
  forms.forEach(f => {
    const id = JSON.stringify(f);
    if (seen.has(id)) return;
    if (seen.size) td.append(", ");
    seen.add(id);
    td.append(renderForm(f, key, plain));
  });
  return td;
}

function renderSection(title, sec, key, plain) {
  const div = el("div", {class: "sec"});
  if (title) div.append(el("h4", {}, title));
  const showRows = !(sec.rows.length === 1 && sec.rows[0] === "");
  const showCols = !(sec.cols.length === 1 && sec.cols[0] === "");
  const table = el("table");
  if (showCols) {
    const tr = el("tr");
    if (showRows) tr.append(el("th"));
    sec.cols.forEach(c => tr.append(el("th", {scope: "col"}, c)));
    table.append(el("thead", {}, tr));
  }
  const tbody = el("tbody");
  sec.rows.forEach(r => {
    const tr = el("tr");
    if (showRows) tr.append(el("th", {scope: "row"}, r));
    sec.cols.forEach(c => tr.append(renderCell(sec.cells.get(r + "\0" + c), key, plain)));
    tbody.append(tr);
  });
  table.append(tbody);
  div.append(el("div", {class: "scroll"}, table));
  return div;
}

function renderRecord(rec, key, plain) {
  const frag = document.createDocumentFragment();
  if (rec.i) frag.append(el("p", {class: "info"}, rec.i));
  (rec.z || []).forEach(z => frag.append(el("p", {class: "note"}, z)));
  if (!rec.f) {
    frag.append(el("p", {class: "info"}, "неизменяемое слово"));
    return frag;
  }
  const codes = PARADIGMS[rec.t];
  const sections = new Map();
  rec.f.forEach((forms, i) => {
    const [title, row, col] = codes ? slotPlace(rec.t, codes[i]) : ["", String(i + 1), ""];
    if (!sections.has(title)) sections.set(title, {rows: [], cols: [], cells: new Map(), any: false});
    const sec = sections.get(title);
    if (!sec.rows.includes(row)) sec.rows.push(row);
    if (!sec.cols.includes(col)) sec.cols.push(col);
    if (forms.length) {
      sec.cells.set(row + "\0" + col, forms);
      sec.any = true;
    }
  });
  sections.forEach((sec, title) => { if (sec.any) frag.append(renderSection(title, sec, key, plain)); });
  return frag;
}

function renderLemma(lemma, entry, key, plain) {
  const card = el("section", {class: "lemma"}, el("h2", {}, lemma));
  entry.forEach((variants, i) => {
    if (entry.length > 1) card.append(el("h3", {}, "Значение " + (i + 1)));
    variants.forEach((rec, j) => {
      if (variants.length > 1) card.append(el("h3", {}, "Вариант склонения " + (j + 1)));
      card.append(renderRecord(rec, key, plain));
    });
  });
  return card;
}

// ---------------------------------------------------------------- поиск

const out = document.getElementById("out");
const input = document.getElementById("q");
const plainBox = document.getElementById("plain");

function splitWords(text) {
  return [...new Set(text.split(/[\s,;]+/).map(w => w.trim()).filter(Boolean))];
}

async function show(text) {
  const words = splitWords(text);
  out.replaceChildren();
  if (!words.length) return;
  out.append(el("p", {class: "msg"}, "Загрузка…"));
  const plain = plainBox.checked;
  const blocks = [];
  for (const word of words) {
    const key = normalize(word);
    let shard;
    try {
      shard = await loadShard(key);
    } catch (e) {
      blocks.push(el("p", {class: "msg"}, "Не удалось загрузить словарь. Проверьте подключение."));
      continue;
    }
    const lemmas = Object.keys(shard).filter(l => normalize(l) === key);
    const others = Object.keys(shard).filter(l => !lemmas.includes(l) && hasForm(shard[l], key));
    if (!lemmas.length && !others.length) {
      blocks.push(el("p", {class: "msg"}, `Слово «${word}» не найдено в словаре.`));
      continue;
    }
    if (!lemmas.length) {
      blocks.push(el("p", {class: "also"}, `«${word}» — форма слов: ${others.join(", ")}`));
      others.forEach(l => blocks.push(renderLemma(l, shard[l], key, plain)));
      continue;
    }
    lemmas.forEach(l => blocks.push(renderLemma(l, shard[l], key, plain)));
    if (others.length) {
      const p = el("p", {class: "also"}, `«${word}» также является формой слов: `);
      others.forEach((l, i) => {
        if (i) p.append(", ");
        const a = el("a", {href: "#" + encodeURIComponent(l)}, l);
        p.append(a);
      });
      blocks.push(p);
    }
  }
  out.replaceChildren(...blocks);
}

function fromHash() {
  const text = decodeURIComponent(location.hash.slice(1));
  input.value = text;
  show(text);
}

document.getElementById("search").addEventListener("submit", e => {
  e.preventDefault();
  const hash = "#" + encodeURIComponent(input.value.trim());
  if (location.hash === hash) show(input.value);
  else location.hash = hash;
});
plainBox.addEventListener("change", () => show(input.value));
window.addEventListener("hashchange", fromHash);
fromHash();
