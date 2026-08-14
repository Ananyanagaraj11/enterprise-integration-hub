const statusMsg = document.getElementById("statusMsg");
const feedRows = document.getElementById("feedRows");
const kpis = document.getElementById("kpis");
const statusFilter = document.getElementById("statusFilter");

async function getJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} -> ${res.status}`);
  return res.json();
}

function money(value) {
  return Number(value).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
  });
}

function renderKpis(summary) {
  const cards = [
    ["Feeds", summary.feedCount],
    ["Total amount", money(summary.totalAmount)],
    ["Engine", summary.engine],
    ["Sources", Object.keys(summary.bySource || {}).length],
  ];
  kpis.innerHTML = cards
    .map(
      ([label, value]) =>
        `<article class="kpi"><span>${label}</span><strong>${value}</strong></article>`
    )
    .join("");
}

function renderFeeds(feeds) {
  feedRows.innerHTML = feeds
    .map(
      (feed) => `
      <tr>
        <td>${feed.feedId}</td>
        <td>${feed.sourceSystem}</td>
        <td>${feed.region}</td>
        <td>${feed.channel}</td>
        <td>${money(feed.amount)}</td>
        <td><span class="pill ${feed.status}">${feed.status}</span></td>
        <td>${feed.eventTime.replace("T", " ").replace("Z", "")}</td>
      </tr>`
    )
    .join("");
}

async function load() {
  statusMsg.textContent = "Loading…";
  try {
    const status = statusFilter.value;
    const query = status ? `?status=${encodeURIComponent(status)}` : "";
    const [feeds, summary] = await Promise.all([
      getJson(`/api/feeds${query}`),
      getJson("/api/summary"),
    ]);
    renderKpis(summary);
    renderFeeds(feeds);
    statusMsg.textContent = `${feeds.length} rows from ASP.NET API`;
  } catch (err) {
    statusMsg.textContent = err.message;
  }
}

document.getElementById("refreshBtn").addEventListener("click", load);
statusFilter.addEventListener("change", load);
load();
