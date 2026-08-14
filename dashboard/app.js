let token = "";
const statusMsg = document.getElementById("statusMsg");

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(path, { ...options, headers });
  if (!res.ok) throw new Error(`${path} -> ${res.status} ${await res.text()}`);
  const type = res.headers.get("content-type") || "";
  return type.includes("application/json") ? res.json() : res.text();
}

function money(v) {
  return Number(v || 0).toLocaleString("en-US", { style: "currency", currency: "USD" });
}

document.getElementById("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    username: document.getElementById("user").value,
    password: document.getElementById("pass").value,
  };
  const out = await api("/auth/login", { method: "POST", body: JSON.stringify(body) });
  token = out.access_token;
  statusMsg.textContent = `JWT issued for ${out.role}`;
  await refresh();
});

document.querySelectorAll("nav button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("nav button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".tab").forEach((t) => t.classList.add("hidden"));
    document.getElementById(btn.dataset.tab).classList.remove("hidden");
  });
});

function renderOverview(summary) {
  const el = document.getElementById("overview");
  const kpis = [
    ["Canonical feeds", summary.feedCount],
    ["Notional", money(summary.totalAmount)],
    ["DLQ", (summary.dlq || []).length],
    ["Sagas", (summary.recentSagas || []).length],
  ];
  el.innerHTML = `
    <div class="kpis">${kpis.map(([l,v]) => `<article class="kpi"><span>${l}</span><strong>${v}</strong></article>`).join("")}</div>
    <div class="grid" style="margin-top:16px">
      <article class="card"><h3>By source system</h3><pre>${JSON.stringify(summary.bySource || {}, null, 2)}</pre></article>
      <article class="card"><h3>Amount by region</h3><pre>${JSON.stringify(summary.amountByRegion || {}, null, 2)}</pre></article>
      <article class="card"><h3>Event bus backlog</h3><pre>${JSON.stringify(summary.bus || {}, null, 2)}</pre></article>
      <article class="card"><h3>Status mix</h3><pre>${JSON.stringify(summary.byStatus || {}, null, 2)}</pre></article>
    </div>`;
}

function renderFeeds(feeds) {
  document.getElementById("feedRows").innerHTML = feeds.map((f) => `
    <tr>
      <td>${f.feed_id}</td>
      <td>${f.source_system}</td>
      <td>${f.partner || ""}</td>
      <td>${f.region}</td>
      <td>${money(f.amount)}</td>
      <td><span class="pill ${f.status}">${f.status}</span></td>
      <td>${(f.event_time || "").replace("T", " ").replace("Z", "")}</td>
    </tr>`).join("");
}

function renderList(id, rows, pick) {
  document.getElementById(id).innerHTML = `<div class="table-wrap"><table><tbody>${
    rows.map(pick).join("") || "<tr><td>Empty</td></tr>"
  }</tbody></table></div>`;
}

async function refresh() {
  if (!token) {
    statusMsg.textContent = "Login to load secured Experience APIs.";
    return;
  }
  const status = document.getElementById("statusFilter").value;
  const q = status ? `?status=${encodeURIComponent(status)}&limit=200` : "?limit=200";
  const [summary, feeds, health] = await Promise.all([
    api("/experience/v1/summary"),
    api(`/experience/v1/feeds${q}`),
    api("/health"),
  ]);
  renderOverview(summary);
  renderFeeds(feeds);
  renderList("sagas", summary.recentSagas || [], (s) => `<tr><td>${s.saga_id}</td><td>${s.state}</td><td>${s.updated_at}</td></tr>`);
  renderList("dlq", summary.dlq || [], (d) => `<tr><td>${d.topic}</td><td>${d.error}</td><td>${d.failed_at}</td></tr>`);
  document.getElementById("health").innerHTML = `<pre>${JSON.stringify(health, null, 2)}</pre>`;
  statusMsg.textContent = `${feeds.length} experience-layer rows`;
}

document.getElementById("batchBtn").addEventListener("click", async () => {
  statusMsg.textContent = "Batch ingest running…";
  const out = await api("/process/v1/feeds/batch", { method: "POST" });
  statusMsg.textContent = `Batch complete: ${out.ingested} ok / ${out.failed} failed`;
  await refresh();
});
document.getElementById("drainBtn").addEventListener("click", async () => {
  await api("/process/v1/events/drain", { method: "POST" });
  await refresh();
});
document.getElementById("statusFilter").addEventListener("change", refresh);
