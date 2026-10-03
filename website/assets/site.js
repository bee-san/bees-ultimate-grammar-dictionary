"use strict";

const root = document.body.dataset.root || "";
const english = document.body.dataset.english === "true";
const search = document.querySelector("#grammar-search");

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function fold(text) {
  return String(text).normalize("NFKC").toLowerCase()
    .replace(/[\u30a1-\u30f6]/g, char => String.fromCharCode(char.charCodeAt(0) - 0x60))
    .replace(/[〜~]/g, "").replace(/\s+/g, " ").trim();
}

function grammarCard(record) {
  const card = element("a", "grammar-card");
  card.href = root + record.path;
  const top = element("div", "card-top");
  for (const level of record.levels) top.append(element("span", "level " + level.toLowerCase(), level));
  const arrow = element("span", "card-arrow", "↗");
  arrow.setAttribute("aria-hidden", "true");
  top.append(arrow);
  const title = element("h3", "", record.expression);
  title.lang = "ja";
  const reading = element("p", "card-reading", record.reading);
  reading.lang = "ja";
  const footer = element("div", "card-footer");
  const count = record.sources.length;
  footer.append(element("span", "", `${count} ${count === 1 ? "source" : "sources"}`));
  footer.append(element("span", "", "Read explanations →"));
  card.append(top, title, reading, element("p", "card-meaning", record.summary), footer);
  return card;
}

if (search) {
  const form = search.closest("form");
  const source = document.querySelector("#source-filter");
  const buttons = [...document.querySelectorAll("[data-level]")];
  const grid = document.querySelector("#grammar-results");
  const count = document.querySelector("#result-count");
  const more = document.querySelector("#load-more");
  const empty = document.querySelector("#search-empty");
  const error = document.querySelector("#search-error");
  const params = new URLSearchParams(location.search);
  let level = params.get("level") || "";
  let records = null;
  let shown = 36;
  let matches = [];
  search.value = params.get("q") || "";
  if ([...source.options].some(option => option.value === params.get("source"))) source.value = params.get("source");
  if (!buttons.some(button => button.dataset.level === level)) level = "";

  function render(reset = true) {
    if (!records) return;
    if (reset) shown = 36;
    const words = fold(search.value).split(" ").filter(Boolean);
    matches = records.filter(record => (!level || record.levels.includes(level)) &&
      (!source.value || record.sources.includes(source.value)) && words.every(word => record.search.includes(word)));
    if (words.length) {
      const query = fold(search.value);
      const rank = record => fold(record.expression) === query ? 0 : fold(record.expression).startsWith(query) ? 1 : 2;
      matches.sort((a, b) => rank(a) - rank(b));
    }
    const fragment = document.createDocumentFragment();
    for (const record of matches.slice(0, shown)) fragment.append(grammarCard(record));
    grid.replaceChildren(fragment);
    count.textContent = `${matches.length.toLocaleString()} grammar ${matches.length === 1 ? "entry" : "entries"}`;
    empty.hidden = matches.length > 0;
    more.hidden = shown >= matches.length;
    for (const button of buttons) {
      const active = button.dataset.level === level;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    }
    const query = new URLSearchParams();
    if (search.value) query.set("q", search.value);
    if (level) query.set("level", level);
    if (source.value) query.set("source", source.value);
    history.replaceState(null, "", location.pathname + (query.size ? "?" + query : "") + location.hash);
  }

  async function load() {
    error.hidden = true;
    try {
      const response = await fetch(root + (english ? "en/" : "") + "search.json");
      if (!response.ok) throw new Error("Search is unavailable");
      records = await response.json();
      for (const record of records) record.search = fold(record.terms + " " + record.summary);
      render();
    } catch {
      error.hidden = false;
    }
  }

  form.addEventListener("submit", event => { event.preventDefault(); render(); });
  search.addEventListener("input", () => render());
  source.addEventListener("change", () => render());
  for (const button of buttons) button.addEventListener("click", () => { level = button.dataset.level; render(); });
  more.addEventListener("click", () => { shown += 36; render(false); });
  document.querySelector("#clear-filters").addEventListener("click", () => {
    search.value = ""; source.value = ""; level = ""; render(); search.focus();
  });
  document.querySelector("#retry-search").addEventListener("click", load);
  document.addEventListener("keydown", event => {
    if (event.key === "/" && !event.ctrlKey && !event.metaKey && !event.altKey &&
        !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName) &&
        !document.activeElement.isContentEditable) { event.preventDefault(); search.focus(); }
  });
  load();
}

const furigana = document.querySelector("#furigana-toggle");
if (furigana) furigana.addEventListener("click", () => {
  const hidden = document.body.classList.toggle("hide-furigana");
  furigana.setAttribute("aria-pressed", String(hidden));
  furigana.textContent = hidden ? "Show furigana" : "Hide furigana";
});
