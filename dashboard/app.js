const SOURCES = [
  "payments-core",
  "regulatory-in",
  "market-data",
  "crm-sync",
  "ledger-erp",
  "partner-sftp",
];
const COLORS = ["#e8a87c", "#f4d35e", "#9cbf8a", "#7eb8c9", "#c9a0dc", "#e85d4c"];
const svg = document.getElementById("fabric");
const beads = document.getElementById("beads");
const nodes = document.getElementById("nodes");
const statusMsg = document.getElementById("statusMsg");

let feeds = [];
let summary = {};

function money(v) {
  return Number(v || 0).toLocaleString("en-US", { style: "currency", currency: "USD" });
}
function row(f) {
  return {
    feedId: f.feedId || f.feed_id,
    sourceSystem: f.sourceSystem || f.source_system,
    partner: f.partner || "",
    region: f.region,
    channel: f.channel,
    amount: f.amount,
    status: f.status,
    eventTime: f.eventTime || f.event_time || "",
    correlationId: f.correlationId || f.correlation_id || "",
  };
}
function routeOf(f) {
  if (f.status === "failed") return "pSnag";
  if (Number(f.amount) >= 50000) return "pGold";
  return "pNorm";
}
function journey(f) {
  const lane =
    f.status === "failed"
      ? "content router → DLQ snag"
      : Number(f.amount) >= 50000
        ? "content router → gold warp (priority topic)"
        : "content router → standard topic";
  return [
    `${f.sourceSystem} emits ${f.channel} event`,
    "Gateway stamps JWT / API key and rate-limit token",
    "System API accepts with Idempotency-Key",
    "Spark/pandas weaves canonical.feed/1.0",
    lane,
    f.status === "failed" ? "Compensation: do not persist dirty cloth" : "Experience API exposes the woven ledger",
  ];
}

function drawNodes() {
  const left = SOURCES.map((name, i) => ({ name, x: 90, y: 70 + i * 76 }));
  const mid = [
    { name: "Gateway", x: 360, y: 250 },
    { name: "Saga loom", x: 520, y: 250 },
  ];
  const right = [
    { name: "Gold warp", x: 900, y: 120 },
    { name: "Canonical cloth", x: 900, y: 250 },
    { name: "DLQ snag", x: 900, y: 430 },
  ];
  [...left, ...mid, ...right].forEach((n) => {
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.innerHTML = `<rect class="node" x="${n.x - 58}" y="${n.y - 18}" rx="12" width="116" height="36"/><text x="${n.x}" y="${n.y + 5}" text-anchor="middle">${n.name}</text>`;
    nodes.appendChild(g);
  });
}

function spawnBead(feed, fromIndex) {
  const start = document.getElementById(`p${fromIndex}`);
  const end = document.getElementById(routeOf(feed));
  if (!start || !end) return;
  const bead = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  bead.setAttribute("r", Number(feed.amount) >= 50000 ? 7 : 5);
  bead.setAttribute("fill", feed.status === "failed" ? "#e85d4c" : COLORS[(fromIndex - 1) % COLORS.length]);
  bead.classList.add("bead");
  beads.appendChild(bead);
  const t0 = performance.now();
  const dur1 = 1100;
  const dur2 = 1200;
  function frame(now) {
    const elapsed = now - t0;
    let pt;
    if (elapsed < dur1) {
      pt = start.getPointAtLength((elapsed / dur1) * start.getTotalLength());
    } else if (elapsed < dur1 + dur2) {
      pt = end.getPointAtLength(((elapsed - dur1) / dur2) * end.getTotalLength());
    } else {
      bead.remove();
      return;
    }
    bead.setAttribute("cx", pt.x);
    bead.setAttribute("cy", pt.y);
    requestAnimationFrame(frame);
  }
  bead.addEventListener("click", () => inspect(feed));
  requestAnimationFrame(frame);
}

function inspect(feed) {
  const lane =
    feed.status === "failed"
      ? "DLQ snag"
      : Number(feed.amount) >= 50000
        ? "Gold warp"
        : "Canonical cloth";
  document.getElementById("insTitle").textContent = feed.feedId;
  document.getElementById("insFacts").innerHTML = [
    ["Partner", feed.partner || "—"],
    ["System", feed.sourceSystem],
    ["Channel", feed.channel],
    ["Region", feed.region],
    ["Amount", money(feed.amount)],
    ["Status", feed.status],
    ["Route", lane],
    ["When", (feed.eventTime || "").replace("T", " ").replace("Z", "")],
  ]
    .map(([k, v]) => `<div class="fact"><span>${k}</span><strong>${v}</strong></div>`)
    .join("");
  document.getElementById("insSteps").innerHTML = journey(feed)
    .map((s, i) => `<li class="on">${s}</li>`)
    .join("");
}

function renderKpis() {
  const el = document.getElementById("kpis");
  const items = [
    ["Threads woven", summary.feedCount || feeds.length],
    ["Notional cloth", money(summary.totalAmount)],
    ["Gold-lane events", feeds.filter((f) => f.amount >= 50000 && f.status !== "failed").length],
    ["Snagged (DLQ)", feeds.filter((f) => f.status === "failed").length],
  ];
  el.innerHTML = items
    .map(([l, v]) => `<article class="kpi"><span>${l}</span><strong>${v}</strong></article>`)
    .join("");
}

function renderTable() {
  const q = document.getElementById("q").value.toLowerCase();
  const rows = feeds
    .map(row)
    .filter((f) => JSON.stringify(f).toLowerCase().includes(q))
    .slice(0, 40);
  document.getElementById("feedRows").innerHTML = rows
    .map(
      (f) => `<tr>
      <td><a href="#" data-id="${f.feedId}">${f.feedId}</a></td>
      <td>${f.sourceSystem}</td><td>${f.partner}</td><td>${f.region}</td>
      <td>${f.channel}</td><td>${money(f.amount)}</td>
      <td><span class="pill ${f.status}">${f.status}</span></td>
    </tr>`
    )
    .join("");
}

function tickClock() {
  if (!feeds.length) return;
  const f = feeds[Math.floor(Math.random() * Math.min(feeds.length, 200))];
  document.getElementById("clockTime").textContent = (f.eventTime || "").replace("T", " ").replace("Z", " UTC");
}

function ambient() {
  if (!feeds.length) return;
  const f = row(feeds[Math.floor(Math.random() * feeds.length)]);
  const idx = Math.max(1, SOURCES.indexOf(f.sourceSystem) + 1);
  spawnBead(f, idx || 1);
}

document.getElementById("injectBtn").addEventListener("click", () => {
  const kind = document.getElementById("kind").value;
  const src = document.getElementById("src").value;
  const feed = row({
    feedId: `LIVE-${Date.now().toString().slice(-6)}`,
    sourceSystem: src,
    partner: "live-inject",
    region: "AMER",
    channel: "webhook",
    amount: kind === "gold" ? 76000 : kind === "failed" ? 420 : 1280,
    status: kind === "failed" ? "failed" : "settled",
    eventTime: new Date().toISOString(),
    correlationId: `corr-live-${Date.now()}`,
  });
  feeds.unshift(feed);
  spawnBead(feed, SOURCES.indexOf(src) + 1);
  inspect(feed);
  renderKpis();
  renderTable();
  statusMsg.textContent =
    kind === "failed"
      ? `${feed.feedId} snagged — content router sent it to the DLQ.`
      : kind === "gold"
        ? `${feed.feedId} took the gold warp (≥ $50k).`
        : `${feed.feedId} woven onto the canonical cloth.`;
});

document.getElementById("q").addEventListener("input", renderTable);
document.getElementById("feedRows").addEventListener("click", (e) => {
  const id = e.target.getAttribute("data-id");
  if (!id) return;
  e.preventDefault();
  const f = feeds.map(row).find((x) => x.feedId === id);
  if (f) inspect(f);
});

async function boot() {
  drawNodes();
  try {
    const health = await fetch("/health");
    if (health.ok) {
      const login = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: "ananya", password: "hub-demo" }),
      }).then((r) => r.json());
      const headers = { Authorization: `Bearer ${login.access_token}` };
      const [s, list] = await Promise.all([
        fetch("/experience/v1/summary", { headers }).then((r) => r.json()),
        fetch("/experience/v1/feeds?limit=500", { headers }).then((r) => r.json()),
      ]);
      summary = s;
      feeds = list.map(row);
      statusMsg.textContent = "Connected to live Process API.";
    } else throw new Error("static");
  } catch (_err) {
    feeds = (await fetch("data/feeds.json").then((r) => r.json())).map(row);
    summary = await fetch("data/summary.json").then((r) => r.json());
    statusMsg.textContent = "Live fabric demo · 800 partner threads pre-woven.";
  }
  renderKpis();
  renderTable();
  inspect(feeds[0]);
  setInterval(ambient, 900);
  setInterval(tickClock, 1600);
}

boot();
