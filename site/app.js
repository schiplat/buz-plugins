/* Buz Step Library — single-page renderer over site-data.json. No framework,
   no build step: fetch, filter, render. */
"use strict";

let templates = [];
let reviewsOnly = false;

const esc = (s) =>
  String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

function badge(t) {
  if (t.reviewed) {
    return `<span class="badge reviewed" title="Officially reviewed at this content hash (${esc(
      t.reviewed_at || "",
    )}) — a point-in-time check, not a runtime-safety guarantee">✓ reviewed</span>`;
  }
  return `<span class="badge unreviewed" title="Not in the official review manifest">unreviewed</span>`;
}

function publisherBadge(t) {
  const official = (t.publisher || "community") === "official";
  return `<span class="badge ${official ? "official" : "community"}">${esc(
    t.publisher || "community",
  )}</span>`;
}

function card(t) {
  const desc = t.description_zh || t.description || "";
  return `
  <article class="card" data-id="${esc(t.id)}" data-version="${esc(t.version)}">
    <div class="row">
      <span class="mono strong">${esc(t.id)}</span>
      <span class="badges">${badge(t)}${publisherBadge(t)}</span>
    </div>
    <div class="meta">v${esc(t.version)} · ${esc(t.engine)}${t.default_timeout ? " · " + esc(t.default_timeout) : ""}</div>
    <p class="desc">${esc(desc)}</p>
    <div class="row foot">
      <span class="author">${t.author ? "by " + esc(t.author) : ""}</span>
      <button class="btn" data-open="${esc(t.id)}@${esc(t.version)}">Details / 详情</button>
    </div>
  </article>`;
}

function detailHTML(t) {
  const usage = [
    `- name: ${(t.id || "").split("/").pop()}`,
    `  uses: ${t.id}@${t.version}`,
    ...((t.inputs || []).filter((i) => i.required).length
      ? ["  with:", ...(t.inputs || []).filter((i) => i.required).map((i) => `    ${i.name}: `)]
      : []),
  ].join("\n");

  const inputRows = (t.inputs || [])
    .map(
      (i) => `<tr>
      <td class="mono">${esc(i.name)}</td>
      <td>${esc(i.type || "string")}</td>
      <td>${i.required ? "yes" : "no"}</td>
      <td>${i.masking ? "yes" : "no"}</td>
      <td class="dim">${esc(i.description || "")}</td>
    </tr>`,
    )
    .join("");

  return `
  <p class="dim">${esc(t.description || "")}</p>
  ${t.description_zh ? `<p class="dim">${esc(t.description_zh)}</p>` : ""}
  <div class="facts">
    <span>${badge(t)}</span>${publisherBadge(t)}
    <span class="badge plain">engine: ${esc(t.engine)}</span>
    ${t.default_timeout ? `<span class="badge plain">timeout: ${esc(t.default_timeout)}</span>` : ""}
    ${t.license ? `<span class="badge plain">${esc(t.license)}</span>` : ""}
    ${t.author ? `<span class="badge plain">by ${esc(t.author)}</span>` : ""}
  </div>
  <h3>Usage</h3>
  <pre class="code">${esc(usage)}</pre>
  ${
    inputRows
      ? `<h3>Inputs</h3><table class="inputs"><thead><tr><th>Name</th><th>Type</th><th>Req</th><th>Mask</th><th>Description</th></tr></thead><tbody>${inputRows}</tbody></table>`
      : ""
  }
  <h3>Integrity / 安全</h3>
  <p class="dim mono small">sha256: ${esc(t.sha256 || "")}</p>
  <p class="dim small">Review is a point-in-time check of this exact hash — pin with
  <span class="mono">@sha256:</span> to bind a pipeline to it. Report problems via the links in the footer.</p>
  ${
    t.source_repo
      ? `<p><a href="${esc(t.source_repo)}" target="_blank" rel="noopener">Source repository / 源仓库</a></p>`
      : ""
  }`;
}

function render() {
  const q = document.getElementById("search").value.trim().toLowerCase();
  const grid = document.getElementById("grid");
  const list = templates.filter((t) => {
    if (!q) return true;
    return [t.id, t.name, t.description, t.description_zh, t.author, t.engine, ...(t.keywords || [])]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(q);
  });
  document.getElementById("empty").classList.toggle("hidden", list.length > 0);
  grid.innerHTML = list.map(card).join("");

  grid.querySelectorAll("[data-open]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const [id, version] = btn.dataset.open.split("@");
      const t = templates.find((x) => x.id === id && x.version === version);
      if (!t) return;
      document.getElementById("d-title").textContent = `${t.id}@${t.version}`;
      document.getElementById("d-body").innerHTML = detailHTML(t);
      document.getElementById("detail").showModal();
    });
  });
}

async function main() {
  const data = await (await fetch("site-data.json")).json();
  templates = data.templates || [];
  document.getElementById("generated").textContent = `Index generated at ${esc(
    data.generated_at || "",
  )}`;
  document.getElementById("search").addEventListener("input", render);
  render();
}

document.getElementById("d-close").addEventListener("click", () => {
  document.getElementById("detail").close();
});

main().catch((e) => {
  const banner = document.getElementById("banner");
  banner.classList.remove("hidden");
  banner.textContent = `Failed to load the step library: ${e}`;
});
