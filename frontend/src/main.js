import "./style.css";
import { api, setVertical } from "./api.js";
import { createSphere } from "./sphere.js";

const $ = (sel, root = document) => root.querySelector(sel);

// ---------- utilidades ----------
const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ESC[c]);
const safeUrl = (u) => (/^https?:\/\//i.test(u ?? "") ? esc(u) : "#");
const safeColor = (c) => (/^#[0-9a-f]{6}$/i.test(c ?? "") ? c : "#f5a524");
const money = (v, currency = "EUR") =>
  new Intl.NumberFormat("es-ES", { style: "currency", currency }).format(v);
const rtf = new Intl.RelativeTimeFormat("es", { numeric: "auto" });
function ago(iso) {
  const diff = (new Date(iso) - Date.now()) / 1000;
  const units = [
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
  ];
  for (const [unit, secs] of units) {
    if (Math.abs(diff) >= secs) return rtf.format(Math.round(diff / secs), unit);
  }
  return "ahora mismo";
}
const clock = (iso) =>
  new Date(iso).toLocaleString("es-ES", { weekday: "short", hour: "2-digit", minute: "2-digit" });
const host = (u) => {
  try {
    return new URL(u).host.replace(/^www\./, "");
  } catch {
    return u;
  }
};
const debounce = (fn, ms) => {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
};

function toast(msg, kind = "info") {
  const el = $("#toast");
  el.textContent = msg;
  el.dataset.kind = kind;
  el.classList.add("show");
  clearTimeout(toast.t);
  toast.t = setTimeout(() => el.classList.remove("show"), 3800);
}

function animateCount(el, to) {
  const from = Number(el.dataset.value || 0);
  const suffix = el.dataset.suffix || "";
  const decimals = suffix.includes("%") ? 1 : 0;
  const start = performance.now();
  const dur = 1200;
  el.dataset.value = to;
  const step = (now) => {
    const p = Math.min(1, (now - start) / dur);
    const eased = 1 - Math.pow(1 - p, 4);
    const v = from + (to - from) * eased;
    el.textContent = v.toLocaleString("es-ES", { maximumFractionDigits: decimals }) + suffix;
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// ---------- animaciones de entrada ----------
const revealer = new IntersectionObserver(
  (entries) => {
    for (const e of entries) {
      if (e.isIntersecting) {
        e.target.classList.add("in");
        revealer.unobserve(e.target);
      }
    }
  },
  { threshold: 0.12, rootMargin: "0px 0px -40px 0px" },
);
const observeReveals = (root = document) =>
  root.querySelectorAll(".reveal:not(.in)").forEach((el) => revealer.observe(el));

// ---------- esfera ----------
const sphere = createSphere($("#network"));
const onScroll = () => sphere.setScroll(Math.min(1.2, window.scrollY / window.innerHeight));
window.addEventListener("scroll", onScroll, { passive: true });
onScroll();

// ---------- modo (tecnología / coches) ----------
const COPY = {
  tech: {
    eyebrow: "Rastreador interno · Todas las ofertas de tus marcas",
    title1: "CAZAMOS OFERTAS",
    title2: "DE TUS MARCAS.",
    sub: "Tú eliges las marcas y PriceHunt busca todas sus ofertas (tecnología, hogar, gaming…) en Amazon, LDLC, MediaMarkt y más tiendas seguras, cada día y de forma automática.",
    search: "Buscar producto o modelo…",
    watchPlaceholder: "Añadir marca (p. ej. glorious)",
    watchSub: "Marcas que se buscan en cada tienda rastreada.",
    count: (n) => `${n} ofertas activas`,
  },
  cars: {
    eyebrow: "Coches · Rebajas en concesionarios oficiales",
    title1: "CAZAMOS COCHES",
    title2: "EN REBAJAS.",
    sub: "PriceHunt vigila los coches de ocasión rebajados en concesionarios oficiales (Das WeltAuto: SEAT, CUPRA, Škoda…). Las subastas públicas del BOE quedan como acceso directo: su web no permite rastreo automático.",
    search: "Buscar marca o modelo…",
    watchPlaceholder: "Añadir marca (p. ej. seat)",
    watchSub: "Marcas de coche que se buscan en los concesionarios rastreados.",
    count: (n) => `${n} coches rebajados`,
  },
};
const readMode = () => {
  try {
    return localStorage.getItem("ph-mode") === "cars" ? "cars" : "tech";
  } catch {
    return "tech";
  }
};
let mode = readMode();

function applyMode() {
  setVertical(mode);
  document.body.dataset.mode = mode;
  const sw = $("#mode");
  sw.dataset.mode = mode;
  sw.querySelectorAll("button").forEach((b) =>
    b.setAttribute("aria-pressed", String(b.dataset.mode === mode)),
  );
  document.querySelectorAll("[data-copy]").forEach((el) => {
    const text = COPY[mode][el.dataset.copy];
    if (el.dataset.copyAttr) el.setAttribute(el.dataset.copyAttr, text);
    else el.textContent = text;
  });
}

// ---------- estado ----------
const filters = { q: "", store: "", category: "", sort: "discount", min_discount: 0 };
let polling = null;

// ---------- render ----------
function renderStatus(stats) {
  const pill = $("#status-pill");
  pill.classList.toggle("scanning", stats.refreshing);
  const demo = stats.demo_mode ? " · DEMO" : "";
  let text;
  if (stats.refreshing) text = "Escaneando tiendas…";
  else if (stats.last_run?.finished_at)
    text = `Actualizado ${ago(stats.last_run.finished_at)}`;
  else text = "Sin datos todavía";
  $("#status-text").textContent = text + demo;

  const btn = $("#refresh-btn");
  btn.disabled = stats.refreshing;
  btn.classList.toggle("busy", stats.refreshing);
  $(".label", btn).textContent = stats.refreshing ? "Escaneando…" : "Refrescar ahora";

  $("#next-run").textContent = stats.next_run
    ? `Próximo refresco automático: ${clock(stats.next_run)} · ${stats.stores_tracked}/${stats.stores_total} tiendas rastreadas`
    : "El refresco programado está desactivado.";
  sphere.setScanning(stats.refreshing);
}

function renderStats(stats) {
  document.querySelectorAll("[data-count]").forEach((el) => {
    animateCount(el, Number(stats[el.dataset.count] || 0));
  });
}

function renderStores(stores) {
  const sel = $("#f-store");
  const current = sel.value;
  sel.innerHTML =
    '<option value="">Todas las tiendas</option>' +
    stores
      .filter((s) => s.tracked)
      .map((s) => `<option value="${esc(s.slug)}">${esc(s.name)}</option>`)
      .join("");
  sel.value = current;

  $("#stores-list").innerHTML = stores
    .map(
      (s, i) => `
      <div class="store reveal" style="--accent:${safeColor(s.accent_color)};--i:${i}">
        <div class="store-top">
          <span class="store-avatar">${esc(s.name.slice(0, 1))}</span>
          <span class="store-tag ${s.tracked ? "tracked" : ""}">${s.tracked ? "Rastreada" : "Acceso directo"}</span>
          ${s.scraper ? "" : `<button class="store-del" data-del-store="${s.id}" title="Eliminar" aria-label="Eliminar ${esc(s.name)}">×</button>`}
        </div>
        <h3>${esc(s.name)}</h3>
        <p class="store-host">${esc(host(s.shortcut_url))}</p>
        <div class="store-actions">
          <a href="${safeUrl(s.shortcut_url)}" target="_blank" rel="noopener noreferrer">Abrir ↗</a>
          ${s.active_deals ? `<button data-filter-store="${esc(s.slug)}">${s.active_deals} ofertas</button>` : ""}
        </div>
      </div>`,
    )
    .join("");
  observeReveals($("#stores-list"));
}

function renderCategories(cats) {
  const all = [{ name: "", label: "Todo", count: cats.reduce((a, c) => a + c.count, 0) }];
  $("#f-cats").innerHTML = all
    .concat(cats.map((c) => ({ ...c, label: c.name })))
    .map(
      (c) =>
        `<button class="chip ${filters.category === c.name ? "active" : ""}" data-cat="${esc(c.name)}">${esc(c.label)}<small>${c.count}</small></button>`,
    )
    .join("");
}

function dealCard(d, i) {
  const media = d.image_url
    ? `<img src="${safeUrl(d.image_url)}" alt="" loading="lazy" referrerpolicy="no-referrer" />`
    : `<span class="placeholder">${esc(d.brand.slice(0, 1).toUpperCase())}</span>`;
  const savings = d.original_price ? d.original_price - d.price : 0;
  return `
    <article class="deal reveal" style="--accent:${safeColor(d.store_color)};--i:${i % 12}" data-id="${d.id}">
      <a href="${safeUrl(d.url)}" target="_blank" rel="noopener noreferrer nofollow">
        <div class="deal-media">
          ${media}
          ${d.discount_pct >= 0.5 ? `<span class="badge">−${Math.round(d.discount_pct)}%</span>` : '<span class="badge sale">Ocasión</span>'}
          ${d.is_new ? '<span class="new">Nueva</span>' : ""}
        </div>
        <div class="deal-body">
          <div class="deal-meta"><span class="dot"></span>${esc(d.store_name)} · ${esc(d.category)}</div>
          <h3>${esc(d.title)}</h3>
          <div class="price-row">
            <b>${money(d.price, d.currency)}</b>
            ${d.original_price ? `<s>${money(d.original_price, d.currency)}</s>` : ""}
          </div>
          <svg class="spark" viewBox="0 0 100 24" preserveAspectRatio="none" aria-hidden="true"></svg>
          <div class="deal-foot">
            <span>Cazada ${ago(d.first_seen_at)}</span>
            ${savings > 0 ? `<span class="save">Ahorras ${money(savings, d.currency)}</span>` : ""}
          </div>
        </div>
      </a>
    </article>`;
}

async function loadDeals() {
  const grid = $("#deals-grid");
  grid.classList.add("loading");
  try {
    const page = await api.deals({ ...filters, limit: 120 });
    grid.innerHTML = page.items.map(dealCard).join("");
    $("#deals-empty").hidden = page.items.length > 0;
    $("#deals-count").textContent = `${COPY[mode].count(page.total)} · se revalidan cada día`;
    observeReveals(grid);
  } catch (e) {
    toast(`No se pudieron cargar las ofertas: ${e.message}`, "error");
  } finally {
    grid.classList.remove("loading");
  }
}

function renderWatch(terms) {
  $("#watch-list").innerHTML = terms
    .map(
      (t) =>
        `<span class="chip static">${esc(t.query)}<button data-del-term="${t.id}" aria-label="Quitar ${esc(t.query)}">×</button></span>`,
    )
    .join("");
}

const RUN_LABEL = {
  startup: "Arranque",
  schedule: "Diario",
  stale: "Recuperación",
  manual: "Manual",
};
function renderRuns(runs) {
  $("#runs").innerHTML =
    runs
      .map(
        (r) => `
      <li class="run ${esc(r.status)} reveal">
        <span class="run-dot"></span>
        <div>
          <div class="run-head">
            <b>${esc(RUN_LABEL[r.trigger] ?? r.trigger)}</b>
            <span class="run-status">${esc(r.status)}</span>
            <time>${ago(r.started_at)}</time>
          </div>
          <p>${r.deals_found} ofertas · ${r.stores_ok} tiendas OK${r.stores_failed ? ` · ${r.stores_failed} con error` : ""}</p>
          ${r.log ? `<details><summary>Log</summary><pre>${esc(r.log)}</pre></details>` : ""}
        </div>
      </li>`,
      )
      .join("") || '<li class="run">Todavía no hay ejecuciones.</li>';
  observeReveals($("#runs"));
}

// ---------- carga ----------
async function loadMeta() {
  const [stats, stores, cats, terms, runs] = await Promise.all([
    api.stats(),
    api.stores(),
    api.categories(),
    api.watchlist(),
    api.runs(),
  ]);
  renderStatus(stats);
  renderStats(stats);
  renderStores(stores);
  renderCategories(cats);
  renderWatch(terms);
  renderRuns(runs);
  return stats;
}

async function loadAll() {
  try {
    const stats = await loadMeta();
    await loadDeals();
    if (stats.refreshing) startPolling();
  } catch (e) {
    $("#status-text").textContent = "API no disponible";
    $("#status-pill").classList.add("down");
    toast(`No hay conexión con la API (${e.message})`, "error");
  }
}

function startPolling() {
  if (polling) return;
  polling = setInterval(async () => {
    try {
      const stats = await api.stats();
      renderStatus(stats);
      if (!stats.refreshing) {
        clearInterval(polling);
        polling = null;
        await loadAll();
        toast(`Refresco terminado: ${stats.last_run?.deals_found ?? 0} ofertas encontradas`, "ok");
      }
    } catch {
      /* reintenta en el siguiente tick */
    }
  }, 2500);
}

// ---------- eventos ----------
$("#refresh-btn").addEventListener("click", async () => {
  try {
    await api.refresh();
    renderStatus({ ...(await api.stats()), refreshing: true });
    toast("Escaneando tiendas… puede tardar un par de minutos");
    startPolling();
  } catch (e) {
    toast(e.message, "error");
  }
});

$("#f-q").addEventListener(
  "input",
  debounce((e) => {
    filters.q = e.target.value.trim();
    loadDeals();
  }, 300),
);
$("#f-store").addEventListener("change", (e) => {
  filters.store = e.target.value;
  loadDeals();
});
$("#f-sort").addEventListener("change", (e) => {
  filters.sort = e.target.value;
  loadDeals();
});
$("#f-min").addEventListener("input", (e) => {
  $("#f-min-val").textContent = `${e.target.value}%`;
});
$("#f-min").addEventListener("change", (e) => {
  filters.min_discount = Number(e.target.value);
  loadDeals();
});
$("#f-cats").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-cat]");
  if (!btn) return;
  filters.category = btn.dataset.cat;
  document
    .querySelectorAll("#f-cats .chip")
    .forEach((c) => c.classList.toggle("active", c === btn));
  loadDeals();
});

$("#stores-list").addEventListener("click", async (e) => {
  const filterBtn = e.target.closest("[data-filter-store]");
  if (filterBtn) {
    filters.store = filterBtn.dataset.filterStore;
    $("#f-store").value = filters.store;
    await loadDeals();
    $("#deals").scrollIntoView({ behavior: "smooth" });
    return;
  }
  const del = e.target.closest("[data-del-store]");
  if (del && confirm("¿Eliminar este acceso directo?")) {
    try {
      await api.deleteStore(del.dataset.delStore);
      renderStores(await api.stores());
    } catch (err) {
      toast(err.message, "error");
    }
  }
});

$("#store-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const data = Object.fromEntries(new FormData(form));
  if (!data.search_url) delete data.search_url;
  try {
    await api.addStore(data);
    form.reset();
    $("#store-msg").textContent = "Guardada ✓";
    renderStores(await api.stores());
  } catch (err) {
    $("#store-msg").textContent = err.message;
  }
});

$("#watch-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = e.target.query;
  try {
    await api.addTerm(input.value.trim());
    input.value = "";
    renderWatch(await api.watchlist());
    toast("Marca añadida: se buscará en el próximo refresco", "ok");
  } catch (err) {
    toast(err.message, "error");
  }
});
$("#watch-list").addEventListener("click", async (e) => {
  const del = e.target.closest("[data-del-term]");
  if (!del) return;
  await api.deleteTerm(del.dataset.delTerm);
  renderWatch(await api.watchlist());
});

// Inclinación 3D de las tarjetas + sparkline de precio al pasar el ratón
const grid = $("#deals-grid");
grid.addEventListener("pointermove", (e) => {
  const card = e.target.closest(".deal");
  if (!card || e.pointerType !== "mouse") return;
  const r = card.getBoundingClientRect();
  const x = (e.clientX - r.left) / r.width - 0.5;
  const y = (e.clientY - r.top) / r.height - 0.5;
  card.style.setProperty("--rx", `${-y * 8}deg`);
  card.style.setProperty("--ry", `${x * 10}deg`);
  card.style.setProperty("--mx", `${(x + 0.5) * 100}%`);
  card.style.setProperty("--my", `${(y + 0.5) * 100}%`);
});
grid.addEventListener(
  "pointerleave",
  (e) => {
    const card = e.target.closest?.(".deal");
    if (card) {
      card.style.removeProperty("--rx");
      card.style.removeProperty("--ry");
    }
  },
  true,
);
grid.addEventListener(
  "pointerenter",
  async (e) => {
    const card = e.target.closest?.(".deal");
    if (!card || card.dataset.spark) return;
    card.dataset.spark = "1";
    try {
      const points = await api.history(card.dataset.id);
      const svg = $(".spark", card);
      if (points.length < 2) {
        svg.outerHTML = `<p class="spark-note">Precio estable desde que se cazó</p>`;
        return;
      }
      const prices = points.map((p) => p.price);
      const min = Math.min(...prices);
      const max = Math.max(...prices);
      const d = prices
        .map((p, i) => {
          const x = (i / (prices.length - 1)) * 100;
          const y = max === min ? 12 : 22 - ((p - min) / (max - min)) * 20;
          return `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .join(" ");
      svg.innerHTML = `<path d="${d}" />`;
      svg.classList.add("on");
    } catch {
      /* sin historial */
    }
  },
  true,
);

$("#mode").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-mode]");
  if (!btn || btn.dataset.mode === mode) return;
  mode = btn.dataset.mode;
  try {
    localStorage.setItem("ph-mode", mode);
  } catch {
    /* sin almacenamiento: el modo solo dura esta sesión */
  }
  Object.assign(filters, { q: "", store: "", category: "", min_discount: 0 });
  $("#f-q").value = "";
  $("#f-min").value = 0;
  $("#f-min-val").textContent = "0%";
  applyMode();
  loadAll();
});

// Arranque
applyMode();
requestAnimationFrame(() => document.body.classList.add("ready"));
observeReveals();
loadAll();
setInterval(async () => {
  if (polling || document.hidden) return;
  try {
    const stats = await api.stats();
    renderStatus(stats);
    if (stats.refreshing) startPolling();
  } catch {
    /* API caída: el pill ya lo refleja en la siguiente carga */
  }
}, 30000);
