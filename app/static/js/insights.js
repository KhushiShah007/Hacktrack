/* Insights charts: Chart.js from CDN, falling back to server-rendered matplotlib PNGs. */
(function () {
  "use strict";
  var el = document.getElementById("insight-data");
  if (!el) return;
  var data = JSON.parse(el.textContent);
  var palette = ["#ff4fb4", "#3df58a", "#4fd8ff", "#ffd23f", "#b48cff", "#ff8a3d"];

  function fallback(box) {
    var img = new Image();
    img.alt = box.querySelector("canvas").getAttribute("aria-label");
    img.onload = function () { HT.unskeleton(box); };
    img.onerror = function () { HT.unskeleton(box); box.insertAdjacentHTML("beforeend", "<p>Chart unavailable.</p>"); };
    img.src = "/insights/chart/" + box.dataset.chart + ".png";
    box.appendChild(img);
  }

  function render() {
    var night = document.documentElement.dataset.theme === "night";
    var ink = getComputedStyle(document.querySelector(".window")).color || (night ? "#2a0a3a" : "#1b1022");
    document.querySelectorAll("[data-chart]").forEach(function (box) {
      if (typeof Chart === "undefined") return fallback(box);
      var canvas = box.querySelector("canvas");
      var cfg;
      if (box.dataset.chart === "types") {
        cfg = { type: "bar", data: { labels: Object.keys(data.by_type), datasets: [{ label: "Quests", data: Object.values(data.by_type), backgroundColor: palette, borderColor: "#1b1022", borderWidth: 3 }] } };
      } else if (box.dataset.chart === "success") {
        cfg = { type: "bar", data: { labels: Object.keys(data.success_rate), datasets: [{ label: "% final or win", data: Object.values(data.success_rate), backgroundColor: "#3df58a", borderColor: "#1b1022", borderWidth: 3 }] },
                options: { indexAxis: "y", scales: { x: { min: 0, max: 100 } } } };
      } else {
        cfg = { type: "line", data: { labels: data.monthly.labels, datasets: [
          { label: "XP actions", data: data.monthly.actions, borderColor: "#ff4fb4", backgroundColor: "#ff4fb4", stepped: true, borderWidth: 3, pointRadius: 4, pointStyle: "rect" },
          { label: "Quests added", data: data.monthly.quests, borderColor: "#1fa7d9", backgroundColor: "#1fa7d9", stepped: true, borderWidth: 3, pointRadius: 4, pointStyle: "rect" }] } };
      }
      cfg.options = Object.assign({ responsive: true, maintainAspectRatio: false, animation: HT.reducedMotion() ? false : { duration: 500 },
        plugins: { legend: { labels: { color: ink, font: { family: "VT323", size: 18 } } } },
        scales: {} }, cfg.options || {});
      ["x", "y"].forEach(function (ax) {
        cfg.options.scales[ax] = Object.assign({ ticks: { color: ink, font: { family: "VT323", size: 16 } }, grid: { color: "rgba(0,0,0,.12)" } }, cfg.options.scales[ax] || {});
      });
      box.style.height = "280px";
      canvas.hidden = false;
      HT.unskeleton(box);
      if (box._chart) box._chart.destroy();
      box._chart = new Chart(canvas, cfg);
    });
  }
  // CDN may be blocked or slow: give it a moment, then fall back to matplotlib
  var tries = 0;
  (function wait() {
    if (typeof Chart !== "undefined" || tries++ > 20) return render();
    setTimeout(wait, 150);
  })();
  document.addEventListener("ht:theme", function () { if (typeof Chart !== "undefined") render(); });
})();
