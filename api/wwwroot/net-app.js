async function getJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(url + " " + res.status);
  return res.json();
}
function money(v) {
  return Number(v).toLocaleString("en-US", { style: "currency", currency: "USD" });
}
(async () => {
  const [feeds, summary] = await Promise.all([getJson("/api/feeds"), getJson("/api/summary")]);
  document.getElementById("kpis").innerHTML = `
    <article class="kpi"><span>Feeds</span><strong>${summary.feedCount || feeds.length}</strong></article>
    <article class="kpi"><span>Engine</span><strong>${summary.engine || "dotnet"}</strong></article>`;
  document.getElementById("feedRows").innerHTML = feeds.slice(0, 50).map(f =>
    `<tr><td>${f.feedId}</td><td>${f.sourceSystem}</td><td>${f.region}</td><td>${money(f.amount)}</td><td>${f.status}</td></tr>`
  ).join("");
})();
