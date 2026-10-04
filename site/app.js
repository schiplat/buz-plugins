/* Buz Step Library — multi-language single-page renderer over
   site-data.json. No framework, no build step.

   Adding a UI language = append one entry to I18N + LOCALE_NAMES.
   Template descriptions: any `description_<lang>` field in the spec is
   emitted by build_site.py automatically; rendering falls back
   description_<lang> → description → first available. */
"use strict";

const LOCALE_NAMES = {
  en: "English",
  zh: "中文",
  // Add UI languages here (translate I18N below + list the code in SUPPORTED):
  // ja: "日本語", ko: "한국어", es: "Español", ...
};
const SUPPORTED = Object.keys(LOCALE_NAMES);
const DEFAULT_LANG = "en";

const I18N = {
  en: {
    tagline: "Reusable step templates for Buz — reference them from pipelines with uses:",
    search: "Search by name, id, keyword, author…",
    details: "Details",
    report: "Report a template",
    security: "Security concerns: report privately",
    inputs: "Inputs",
    usage: "Usage",
    integrity: "Integrity",
    name: "Name",
    type: "Type",
    required: "Required",
    masking: "Masking",
    description: "Description",
    yes: "yes",
    no: "no",
    inputsCount: (n) => `${n} input${n === 1 ? "" : "s"}`,
    by: "by",
    templates: (n) => `${n} template${n === 1 ? "" : "s"}`,
    emptySearch: "No templates match your search.",
    empty: "No templates installed yet — clone github.com/schiplat/buz-plugins into the Manager's step directory.",
    loadFail: "Failed to load the step library",
    incompatible: "needs a newer Buz",
    sourceRepo: "Source repository",
    reportHint: "Report a problem with this template",
    timeout: "timeout",
    reviewed: "reviewed",
    unreviewed: "unreviewed",
    official: "official",
    community: "community",
    reviewedTip: "Officially reviewed at this content hash — a point-in-time check, not a runtime-safety guarantee",
    unreviewedTip: "Not in the official review manifest",
    pinHint: "Review is a point-in-time check of this exact hash — pin with @sha256: to bind a pipeline to it.",
  },
  zh: {
    tagline: "Buz 流水线的可复用步骤模板——在流水线中通过 uses: 引用",
    search: "按名称、ID、关键词、作者搜索…",
    details: "详情",
    report: "反馈模板问题",
    security: "安全问题请私下举报",
    inputs: "输入参数",
    usage: "用法",
    integrity: "完整性",
    name: "名称",
    type: "类型",
    required: "必填",
    masking: "打码",
    description: "说明",
    yes: "是",
    no: "否",
    inputsCount: (n) => `${n} 个输入`,
    by: "作者",
    templates: (n) => `${n} 个模板`,
    emptySearch: "没有匹配的模板。",
    empty: "尚未安装模板——将 github.com/schiplat/buz-plugins 克隆到 Manager 的步骤目录即可。",
    loadFail: "插件库加载失败",
    incompatible: "需要更新版本的 Buz",
    sourceRepo: "源仓库",
    reportHint: "反馈此模板的问题",
    timeout: "超时",
    reviewed: "已审核",
    unreviewed: "未审核",
    official: "官方",
    community: "社区",
    reviewedTip: "官方已审核该内容哈希——时间点检查，不构成运行时安全保证",
    unreviewedTip: "不在官方审核清单中",
  },
};

let lang = detectLanguage();
let templates = [];

function detectLanguage() {
  const saved = localStorage.getItem("buz-steps-lang");
  if (saved && I18N[saved]) return saved;
  for (const candidate of navigator.languages || [navigator.language || DEFAULT_LANG]) {
    const code = String(candidate).toLowerCase();
    if (I18N[code]) return code; // exact: "zh", "en"
    const base = code.split("-")[0];
    if (I18N[base]) return base; // "zh-CN" → zh, "en-US" → en
  }
  return DEFAULT_LANG;
}

const t = (key, ...args) => {
  const value = I18N[lang][key] ?? I18N[DEFAULT_LANG][key] ?? key;
  return typeof value === "function" ? value(...args) : value;
};

const esc = (s) =>
  String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/** Description for the active locale, with fallback to what exists. */
function localizedDescription(tmpl) {
  const candidates =
    lang === DEFAULT_LANG
      ? ["description"]
      : [`description_${lang}`, "description", ...Object.keys(tmpl)
          .filter((k) => k.startsWith("description_") && k !== `description_${lang}`)];
  for (const key of candidates) if (tmpl[key]) return tmpl[key];
  return "";
}

function reviewedBadge(tmpl) {
  return tmpl.reviewed
    ? `<span class="badge reviewed" title="${esc(t.reviewedTip)}${tmpl.reviewed_at ? " (" + esc(tmpl.reviewed_at) + ")" : ""}">✓ ${esc(t("reviewed"))}</span>`
    : `<span class="badge unreviewed" title="${esc(t("unreviewedTip"))}">${esc(t("unreviewed"))}</span>`;
}

function publisherBadge(tmpl) {
  const publisher = tmpl.publisher || "community";
  return `<span class="badge ${publisher === "official" ? "official" : "community"}">${esc(t(publisher))}</span>`;
}

function card(tmpl) {
  const name = tmpl.name || tmpl.id;
  const compatible = tmpl.buz_compatible !== false;
  return `
  <article class="card" data-key="${esc(tmpl.id)}@${esc(tmpl.version)}">
    <div class="card-head">
      <span class="name">${esc(name)}</span>
      <span class="badges">${reviewedBadge(tmpl)}${publisherBadge(tmpl)}</span>
    </div>
    <div class="mono dim card-id">${esc(tmpl.id)} <span class="sep">·</span> v${esc(tmpl.version)}</div>
    <p class="desc">${esc(localizedDescription(tmpl))}</p>
    <div class="chips">
      <span class="chip">${esc(tmpl.engine)}</span>
      ${tmpl.default_timeout ? `<span class="chip">${esc(tmpl.default_timeout)}</span>` : ""}
      ${tmpl.inputs ? `<span class="chip">${esc(t("inputsCount", tmpl.inputs.length))}</span>` : ""}
      ${compatible ? "" : `<span class="chip warn">${esc(t("incompatible"))}</span>`}
    </div>
    <div class="card-foot">
      <span class="dim small">${tmpl.author ? `${esc(t("by"))} ${esc(tmpl.author)}` : ""}</span>
      <button class="btn" data-open="${esc(tmpl.id)}@${esc(tmpl.version)}">${esc(t("details"))} →</button>
    </div>
  </article>`;
}

function applyI18n() {
  document.documentElement.lang = lang;
  document.title = lang === DEFAULT_LANG ? "Buz Step Library" : `${lang === "zh" ? "Buz 插件库" : "Buz Step Library"} · Buz`;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.getElementById("search").placeholder = t("search");
  document.getElementById("lang-select").value = lang;
}

function render() {
  applyI18n();
  const q = document.getElementById("search").value.trim().toLowerCase();
  const grid = document.getElementById("grid");
  const list = templates.filter((tmpl) => {
    if (!q) return true;
    const haystack = Object.entries(tmpl)
      .filter(([key, value]) => typeof value === "string" || Array.isArray(value) || key === "inputs")
      .map(([key, value]) =>
        key === "inputs"
          ? (value || []).map((i) => `${i.name} ${i.description || ""}`).join(" ")
          : Array.isArray(value)
            ? value.join(" ")
            : key.startsWith("description_") || ["id", "name", "author", "engine"].includes(key)
              ? value
              : "",
      )
      .join(" ")
      .toLowerCase();
    return haystack.includes(q);
  });
  document.getElementById("count").textContent = t("templates", list.length);
  const emptyEl = document.getElementById("empty");
  emptyEl.textContent = document.getElementById("search").value.trim() ? t("emptySearch") : t("empty");
  emptyEl.classList.toggle("hidden", list.length > 0);
  grid.innerHTML = list.map(card).join("");
  grid.querySelectorAll("[data-open]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const [id, version] = btn.dataset.open.split("@");
      const tmpl = templates.find((x) => x.id === id && x.version === version);
      if (tmpl) openDetail(tmpl);
    });
  });
}

function openDetail(tmpl) {
  document.getElementById("d-id").textContent = `${tmpl.id}@${tmpl.version}`;
  document.getElementById("d-badges").innerHTML = reviewedBadge(tmpl) + publisherBadge(tmpl);

  const usage = [
    `- name: ${(tmpl.id || "").split("/").pop()}`,
    `  uses: ${tmpl.id}@${tmpl.version}`,
    ...((tmpl.inputs || []).filter((i) => i.required).length
      ? ["  with:", ...(tmpl.inputs || []).filter((i) => i.required).map((i) => `    ${i.name}: `)]
      : []),
  ].join("\n");

  const inputRows = (tmpl.inputs || [])
    .map(
      (i) => `<tr>
      <td class="mono">${esc(i.name)}</td>
      <td>${esc(i.type || "string")}</td>
      <td>${i.required ? t("yes") : t("no")}</td>
      <td>${i.masking ? t("yes") : t("no")}</td>
      <td class="dim">${esc(i.description || "")}</td>
    </tr>`,
    )
    .join("");

  const report = `https://github.com/schiplat/buz-plugins/issues/new?template=report.yml&title=${encodeURIComponent(`[report] ${tmpl.id}@${tmpl.version}`)}`;

  document.getElementById("d-body").innerHTML = `
    <p class="desc-full">${esc(localizedDescription(tmpl))}</p>
    <div class="facts">
      ${tmpl.default_timeout ? `<span class="badge plain">${esc(t("timeout"))}: ${esc(tmpl.default_timeout)}</span>` : ""}
      ${tmpl.license ? `<span class="badge plain">${esc(tmpl.license)}</span>` : ""}
      ${tmpl.author ? `<span class="badge plain">${esc(t("by"))} ${esc(tmpl.author)}</span>` : ""}
    </div>
    <h3>${esc(t("usage"))}</h3>
    <pre class="code">${esc(usage)}</pre>
    ${inputRows ? `<h3>${esc(t("inputs"))}</h3><table class="inputs"><thead><tr><th>${esc(t("name"))}</th><th>${esc(t("type"))}</th><th>${esc(t("required"))}</th><th>${esc(t("masking"))}</th><th>${esc(t("description"))}</th></tr></thead><tbody>${inputRows}</tbody></table>` : ""}
    <h3>${esc(t("integrity"))}</h3>
    <p class="dim mono small">sha256: ${esc(tmpl.content_sha256 || "")}</p>
    <p class="dim small">${esc(t("pinHint"))}</p>
    <p class="small">
      <a href="${report}" target="_blank" rel="noopener" class="report">${esc(t("reportHint"))}</a>
      ${tmpl.source_repo ? ` · <a href="${esc(tmpl.source_repo)}" target="_blank" rel="noopener">${esc(t("sourceRepo"))}</a>` : ""}
    </p>`;

  document.getElementById("detail").showModal();
}

function setLang(next) {
  if (!I18N[next]) return;
  lang = next;
  localStorage.setItem("buz-steps-lang", next);
  render();
}

async function main() {
  // Language selector from supported locales (native names).
  const select = document.getElementById("lang-select");
  for (const code of SUPPORTED) {
    const option = document.createElement("option");
    option.value = code;
    option.textContent = LOCALE_NAMES[code];
    select.appendChild(option);
  }
  select.value = lang;
  select.addEventListener("change", () => setLang(select.value));

  document.getElementById("search").addEventListener("input", render);
  document.getElementById("d-close").addEventListener("click", () => document.getElementById("detail").close());

  const data = await (await fetch("site-data.json")).json();
  templates = data.templates || [];
  document.getElementById("generated-line").textContent = `Index generated at ${data.generated_at || ""}`;
  render();
}

main().catch((e) => {
  const banner = document.getElementById("banner");
  banner.classList.remove("hidden");
  banner.textContent = `${t("loadFail")}: ${e}`;
});
