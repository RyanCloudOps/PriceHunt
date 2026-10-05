let vertical = "tech";

export const setVertical = (v) => {
  vertical = v;
};

async function request(path, options = {}) {
  const resp = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = await resp.json();
      detail = Array.isArray(body.detail) ? body.detail.map((d) => d.msg).join(", ") : body.detail;
    } catch {
      /* respuesta sin JSON */
    }
    throw new Error(detail);
  }
  return resp.status === 204 ? null : resp.json();
}

const qs = (params) =>
  new URLSearchParams(
    Object.entries({ vertical, ...params }).filter(([, v]) => v !== "" && v != null),
  ).toString();

export const api = {
  stats: () => request(`/stats?${qs({})}`),
  deals: (params) => request(`/deals?${qs(params)}`),
  history: (id) => request(`/deals/${id}/history`),
  categories: () => request(`/categories?${qs({})}`),
  stores: () => request(`/stores?${qs({})}`),
  addStore: (body) =>
    request("/stores", { method: "POST", body: JSON.stringify({ ...body, vertical }) }),
  deleteStore: (id) => request(`/stores/${id}`, { method: "DELETE" }),
  watchlist: () => request(`/watchlist?${qs({})}`),
  addTerm: (query) =>
    request("/watchlist", { method: "POST", body: JSON.stringify({ query, vertical }) }),
  deleteTerm: (id) => request(`/watchlist/${id}`, { method: "DELETE" }),
  runs: () => request("/runs?limit=8"),
  refresh: () => request("/refresh", { method: "POST" }),
};
