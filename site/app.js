/* Buz Step Library — bilingual (zh/en) single-page renderer over
   site-data.json. No framework, no build step. */
"use strict";

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
    requiredInput: "required",
    inputsCount: (n) => `${n} input${n === 1 ? "" : "s"}`,
    by: "by",
    emptySearch: "No templates match your search.",
    empty: "No templates installed yet — clone github.com/schiplat/buz-plugins into the Manager's step directory.",
    loadFail: "Failed to load the step library",
    incompatible: "needs a newer Buz",
    sourceRepo: "Source repository",
    reviewedTip: "Officially reviewed at this content hash — a point-in-time check, not a runtime-safety guarantee",
    unreviewedTip: "Not in the official review manifest",
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
    requiredInput: "必填",
    inputsCount: (n) => `${n} 个输入`,
    by: "作者",
    emptySearch: "没有匹配的模板。",
    empty: "尚未安装模板——将 github.com/schiplat/buz-plugins 克隆到 Manager 的步骤目录即可。",
    loadFail: "插件库加载失败",
    incompatible: "需要更新版本的 Buz",
    sourceRepo: "源仓库",
    reviewedTip: "官方已审核该内容哈希——时间点检查，不构成运行时安全保证",
    unreviewedTip: "不在官方审核清单中",
  },
};

let lang = localStorage.getItem("buz-steps-lang") || (navigator.language || "").toLowerCase().startsWith("zh") ? localStorage.getItem("buz-steps-lang") || "zh" : "en";
let templates = [];

const t = (key, ...args) => {
  const v = I18N[lang][key] ?? I18N.en[key] ?? key;
  return typeof v === "function" ? v(...args) : v;
};

const esc = (s) =>
  String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

const desc = (tmpl) =>
  (lang === "zh" ? tmpl.description_zh || tmpl.description : tmpl.description || tmpl.description_zh) || "";

function reviewedBadge(tmpl) {
  return tmpl.reviewed
    ? `<span class="badge reviewed" title="${esc(t.reviewedTip)}${tmpl.reviewed_at ? " (" + esc(tmpl.reviewed_at) + ")" : ""}">✓ ${esc(t("name") === "名称" ? "已审核" : "reviewed")}</span>`
    : `<span class="badge unreviewed" title="${esc(t.unreviewedTip)}">${esc(lang === "zh" ? "未审核" : "unreviewed")}</span>`;
}

function publisherBadge(tmpl) {
  const official = (tmpl.publisher || "community") === "official";
  const label = official ? (lang === "zh" ? "官方" : "official") : (lang === "zh" ? "社区" : "community");
  return `<span class="badge ${official ? "official" : "community"}">${esc(label)}</span>`;
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
    <p class="desc">${esc(desc(tmpl))}</p>
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
  document.documentElement.lang = lang === "zh" ? "zh" : "en";
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.getElementById("search").placeholder = t("search");
  document.title = lang === "zh" ? "Buz 插件库" : "Buz Step Library";
}

function render() {
  applyI18n();
  const q = document.getElementById("search").value.trim().toLowerCase();
  const grid = document.getElementById("grid");
  const list = templates.filter((tmpl) => {
    if (!q) return true;
    return [tmpl.id, tmpl.name, tmpl.description, tmpl.description_zh, tmpl.author, tmpl.engine, ...(tmpl.keywords || [])]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(q);
  });
  document.getElementById("count").textContent =
    lang === "zh" ? `${list.length} 个模板` : `${list.length} template${list.length === 1 ? "" : "s"}`;
  document.getElementById("empty").textContent = searchQueryEmpty() ? t("emptySearch") : t("empty");
  document.getElementById("empty").classList.toggle("hidden", list.length > 0);
  grid.innerHTML = list.map(card).join("");
  grid.querySelectorAll("[data-open]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const [id, version] = btn.dataset.open.split("@");
      const tmpl = templates.find((x) => x.id === id && x.version === version);
      if (tmpl) openDetail(tmpl);
    });
  });
}

const searchQueryEmpty = () => document.getElementById("search").value.trim() !== "";

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
    <p class="desc-full">${esc(desc(tmpl))}</p>
    <div class="facts">
      ${tmpl.default_timeout ? `<span class="badge plain">${esc(t("usage") !== "Usage" ? "超时" : "timeout")}: ${esc(tmpl.default_timeout)}</span>` : ""}
      ${tmpl.license ? `<span class="badge plain">${esc(tmpl.license)}</span>` : ""}
      ${tmpl.author ? `<span class="badge plain">${esc(t("by"))} ${esc(tmpl.author)}</span>` : ""}
    </div>
    <h3>${esc(t("usage"))}</h3>
    <pre class="code">${esc(usage)}</pre>
    ${inputRows ? `<h3>${esc(t("inputs"))}</h3><table class="inputs"><thead><tr><th>${esc(t("name"))}</th><th>${esc(t("type"))}</th><th>${esc(t("required"))}</th><th>${esc(t("masking"))}</th><th>${esc(t("description"))}</th></tr></thead><tbody>${inputRows}</tbody></table>` : ""}
    <h3>${esc(t("integrity"))}</h3>
    <p class="dim mono small">sha256: ${esc(tmpl.content_sha256 || "")}</p>
    <p class="dim small">${esc(lang === "zh"
      ? "审核是对该哈希的时间点检查——在流水线中用 @sha256: 钉版可绑定到此内容。"
      : "Review is a point-in-time check of this exact hash — pin with @sha256: to bind a pipeline to it.")}</p>
    <p class="small">
      <a href="${report}" target="_blank" rel="noopener" class="report">${esc(t("report"))}</a>
      ${tmpl.source_repo ? ` · <a href="${esc(tmpl.source_repo)}" target="_blank" rel="noopener">${esc(t("sourceRepo"))}</a>` : ""}
    </p>`;

  document.getElementById("detail").showModal();
}

function setLang(next) {
  lang = next;
  localStorage.setItem("buz-steps-lang", next);
  render();
}

async function main() {
  const data = await (await fetch("site-data.json")).json();
  templates = data.templates || [];
  document.getElementById("generated-line").textContent = `Index generated at ${data.generated_at || ""}`;
  document.getElementById("lang-toggle").addEventListener("click", () => setLang(lang === "zh" ? "en" : "zh"));
  document.getElementById("search").addEventListener("input", render);
  document.getElementById("d-close").addEventListener("click", () => document.getElementById("detail").close());
  render();
}

main().catch((e) => {
  const banner = document.getElementById("banner");
  banner.classList.remove("hidden");
  banner.textContent = `${t("loadFail")}: ${e}`;
});
