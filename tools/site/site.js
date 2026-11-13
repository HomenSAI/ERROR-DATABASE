/* HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI */
/* Сайт-справочник: поиск по search.<lang>.json, переключатель темы, переход со старых адресов на странице 404.
   Поиск повторяет Catalog.search и нормализацию homensai_errors._texts (normalize, stem) — совпадение результатов
   проверяет tests/test_site.py через node. Без внешних библиотек; DOM строится через textContent. */
(function (root) {
  "use strict";

  var PLACEHOLDER = /\{[a-z_][a-z0-9_]*\}/g;
  var APOSTROPHES = /['’ʼ`]/g;
  var SPLIT = /[^\p{L}\p{N}]+/u;

  /** Строка для поиска: как _texts.normalize (casefold ≈ toLowerCase + ß→ss, ς→σ). */
  function normalize(text) {
    var out = String(text).replace(PLACEHOLDER, " ").toLowerCase()
      .replace(/ß/g, "ss").replace(/ς/g, "σ").replace(/ё/g, "е");
    out = out.replace(APOSTROPHES, "");
    return out.split(SPLIT).filter(Boolean).join(" ");
  }

  /** Простая основа слова: как _texts.stem. */
  function stem(token) {
    var chars = Array.from(token);
    if (chars.length >= 7) { return chars.slice(0, -2).join(""); }
    if (chars.length >= 5) { return chars.slice(0, -1).join(""); }
    return token;
  }

  /** Подготовить индекс search.<lang>.json: таблица имён (код, key, прежние коды) → код. */
  function prepare(index) {
    var names = new Map();
    var docs = index.docs.map(function (doc) {
      var all = [doc.code, doc.key].concat(doc.aliases || []);
      all.forEach(function (name) { if (!names.has(name)) { names.set(name, doc.code); } });
      return {doc: doc, names: all.map(normalize)};
    });
    return {index: index, names: names, docs: docs,
      byCode: new Map(index.docs.map(function (doc) { return [doc.code, doc]; }))};
  }

  /** Код по точному имени (как Catalog.find) или null. */
  function find(prepared, name) {
    return prepared.names.get(name) || prepared.names.get(String(name).trim().toUpperCase()) || null;
  }

  /** Поиск как Catalog.search: [[код, баллы], ...] по убыванию баллов, затем по коду; limit — необязателен. */
  function search(prepared, query, limit) {
    var raw = String(query).trim();
    if (!raw) { return []; }
    var scores = new Map();
    var exact = find(prepared, raw);
    if (exact) { scores.set(exact, 1000); }
    var prefix = raw.toUpperCase();
    if (prefix.indexOf("-") >= 0) {
      prepared.docs.forEach(function (item) {
        var code = item.doc.code;
        if (code.indexOf(prefix) === 0 && !scores.has(code)) { scores.set(code, 500); }
      });
    }
    var tokens = normalize(raw).split(" ").filter(Boolean);
    if (tokens.length) {
      prepared.docs.forEach(function (item) {
        var doc = item.doc;
        var score = 0;
        for (var i = 0; i < tokens.length; i++) {
          var token = tokens[i];
          var base = stem(token);
          var starts = function (term) { return term.indexOf(base) === 0; };
          if (item.names.some(function (n) { return n.indexOf(token) >= 0; })) {
            score += 5;
          } else if (doc.title_terms.some(starts)) {
            score += 3;
          } else if (doc.terms.some(starts)) {
            score += 1;
          } else {
            score = 0;
            break;
          }
        }
        if (score) { scores.set(doc.code, Math.max(scores.get(doc.code) || 0, score)); }
      });
    }
    var ranked = Array.from(scores.entries()).sort(function (a, b) {
      return (b[1] - a[1]) || (a[0] < b[0] ? -1 : (a[0] > b[0] ? 1 : 0));
    });
    return typeof limit === "number" ? ranked.slice(0, Math.max(limit, 0)) : ranked;
  }

  var api = {normalize: normalize, stem: stem, prepare: prepare, find: find, search: search};
  if (typeof module !== "undefined" && module.exports) { module.exports = api; }
  root.HSAIErrors = api;
  if (typeof document === "undefined") { return; }

  // --- страница ------------------------------------------------------------------------------------------------

  function loadIndex(url) {
    return fetch(url, {credentials: "same-origin"}).then(function (response) {
      if (!response.ok) { throw new Error(String(response.status)); }
      return response.json();
    }).then(prepare);
  }

  function fill(text, n) { return String(text).replace("{n}", String(n)); }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) { node.className = cls; }
    if (text !== undefined) { node.textContent = text; }
    return node;
  }

  function initSearch(form) {
    var labels = JSON.parse(form.getAttribute("data-labels"));
    var input = form.querySelector("input[type=search]");
    var status = document.getElementById("search-status");
    var list = document.getElementById("search-results");
    var pages = form.getAttribute("data-pages");
    var shown = parseInt(form.getAttribute("data-limit"), 10) || 100;
    var pending = null;
    var timer = null;

    function index() {
      if (!pending) { pending = loadIndex(form.getAttribute("data-index")); }
      return pending;
    }

    function render(prepared, query) {
      list.textContent = "";
      if (!query.trim()) { status.textContent = ""; return; }
      var hits = search(prepared, query);
      if (!hits.length) { status.textContent = labels.none; return; }
      status.textContent = fill(labels.found, hits.length) +
        (hits.length > shown ? " · " + fill(labels.first, shown) : "");
      hits.slice(0, shown).forEach(function (hit) {
        var doc = prepared.byCode.get(hit[0]);
        var li = el("li");
        var link = el("a");
        link.href = pages + doc.code + ".html";
        link.appendChild(el("code", "", doc.code));
        link.appendChild(document.createTextNode(" — " + doc.title));
        li.appendChild(link);
        li.appendChild(document.createTextNode(" "));
        li.appendChild(el("span", "badge level-" + doc.level, labels.levels[doc.level] || doc.level));
        if (doc.aliases && doc.aliases.length) {
          li.appendChild(document.createTextNode(" "));
          var label = doc.aliases.length === 1 ? labels.legacy_one : labels.legacy_many;
          li.appendChild(el("span", "legacy", "(" + label + ": " + doc.aliases.join(", ") + ")"));
        }
        list.appendChild(li);
      });
    }

    function run() {
      var query = input.value;
      try {
        var url = new URL(window.location.href);
        if (query.trim()) { url.searchParams.set("q", query); } else { url.searchParams.delete("q"); }
        window.history.replaceState(null, "", url.toString());
      } catch (e) { /* адрес не меняется — поиск всё равно работает */ }
      index().then(function (prepared) { render(prepared, query); }, function () {
        status.textContent = labels.failed;
      });
    }

    form.addEventListener("submit", function (event) { event.preventDefault(); run(); });
    input.addEventListener("input", function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(run, 150);
    });
    input.addEventListener("focus", function () { index().catch(function () {}); }, {once: true});
    var start = new URLSearchParams(window.location.search).get("q");
    if (start) { input.value = start; run(); }
  }

  function initTheme(button) {
    var order = ["auto", "light", "dark"];
    var key = "hsai-errors-theme";
    function current() {
      var value = document.documentElement.getAttribute("data-theme");
      return value === "light" || value === "dark" ? value : "auto";
    }
    function show() {
      var value = current();
      button.textContent = button.getAttribute("data-label") + ": " + button.getAttribute("data-" + value);
    }
    button.addEventListener("click", function () {
      var next = order[(order.indexOf(current()) + 1) % order.length];
      if (next === "auto") {
        document.documentElement.removeAttribute("data-theme");
      } else {
        document.documentElement.setAttribute("data-theme", next);
      }
      try {
        if (next === "auto") { window.localStorage.removeItem(key); } else { window.localStorage.setItem(key, next); }
      } catch (e) { /* выбор действует до закрытия страницы */ }
      show();
    });
    show();
    button.hidden = false;
  }

  /** 404: /errors/rent-dr-001/, /errors/<key>, /errors/<прежний код> → адрес кода, если он есть в индексе. */
  function initNotFound(base) {
    var path = window.location.pathname;
    if (path.indexOf(base) !== 0) { return; }
    var match = path.slice(base.length).match(/^(?:(ru|uk|en|de)\/)?errors\/([^\/]+?)(?:\.html)?\/?$/i);
    if (!match) { return; }
    var lang = match[1] ? match[1].toLowerCase() : "";
    var name;
    try { name = decodeURIComponent(match[2]); } catch (e) { return; }
    loadIndex(base + "search." + (lang || "en") + ".json").then(function (prepared) {
      var code = find(prepared, name);
      var target = code ? base + (lang ? lang + "/" : "") + "errors/" + code : null;
      if (target && target !== path) { window.location.replace(target); }
    }, function () {});
  }

  function start() {
    var form = document.getElementById("search");
    if (form) { initSearch(form); }
    var button = document.getElementById("theme");
    if (button) { initTheme(button); }
    var base = document.body.getAttribute("data-notfound-base");
    if (base) { initNotFound(base); }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})(typeof window !== "undefined" ? window : globalThis);
