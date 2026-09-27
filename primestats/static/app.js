/* PrimeStats – kleine UI-Helfer ohne Build-Schritt. */
(function () {
  "use strict";

  const PALETTE = ["#7c5cff", "#20d3c2", "#ffb547", "#ff5a6a", "#4c8dff", "#2fd48a", "#f472b6",
                   "#a3e635", "#fb923c", "#38bdf8", "#c084fc", "#facc15", "#94a3b8", "#e879f9"];

  function readJSON(id) {
    const el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  }

  /* ---------- Lade-Overlay für langsame Seiten (API-Abrufe) ---------- */
  document.addEventListener("submit", (ev) => {
    if (ev.target.matches("[data-loading]")) {
      const overlay = document.getElementById("loading");
      if (overlay) {
        overlay.querySelector(".msg").textContent = ev.target.dataset.loading || "Lade Daten …";
        overlay.classList.add("on");
      }
    }
  });
  window.addEventListener("pageshow", () => {
    const overlay = document.getElementById("loading");
    if (overlay) overlay.classList.remove("on");
  });

  /* ---------- Spielauswahl ---------- */
  function initGameSelection(root) {
    const form = root.querySelector("form.game-select") || root;
    const boxes = () => Array.from(form.querySelectorAll("input[name=m]"));
    const counter = form.querySelector("[data-count]");
    const submit = form.querySelector("[data-submit]");
    const update = () => {
      let n = 0;
      boxes().forEach((b) => {
        b.closest(".game, tr")?.classList.toggle("selected", b.checked);
        if (b.checked) n++;
      });
      if (counter) counter.textContent = n;
      if (submit) submit.disabled = n === 0;
    };
    form.addEventListener("click", (ev) => {
      const row = ev.target.closest(".game");
      if (row && !ev.target.closest("a, button, input, select, label")) {
        const box = row.querySelector("input[name=m]");
        box.checked = !box.checked;
      }
      const action = ev.target.closest("[data-select]");
      if (action) {
        const mode = action.dataset.select;
        boxes().forEach((b) => {
          if (mode === "all") b.checked = true;
          else if (mode === "none") b.checked = false;
          else if (mode === "included") b.checked = b.dataset.included === "1";
        });
      }
      update();
    });
    form.addEventListener("change", update);
    update();
  }
  document.querySelectorAll("[data-game-select]").forEach(initGameSelection);

  /* ---------- sortierbare Tabellen ---------- */
  document.querySelectorAll("table[data-sortable]").forEach((table) => {
    const heads = Array.from(table.querySelectorAll("th[data-sort]"));
    heads.forEach((th) => {
      th.addEventListener("click", () => {
        const idx = Array.from(th.parentNode.children).indexOf(th);
        const desc = !th.classList.contains("sorted-desc");
        heads.forEach((h) => h.classList.remove("sorted-asc", "sorted-desc"));
        th.classList.add(desc ? "sorted-desc" : "sorted-asc");
        const body = table.tBodies[0];
        const rows = Array.from(body.rows);
        const val = (row) => {
          const cell = row.children[idx];
          const raw = cell?.dataset.value ?? cell?.textContent.trim();
          const num = parseFloat(raw);
          return isNaN(num) ? raw.toLowerCase() : num;
        };
        rows.sort((a, b) => {
          const x = val(a), y = val(b);
          const cmp = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
          return desc ? -cmp : cmp;
        });
        rows.forEach((r) => body.appendChild(r));
      });
    });
  });

  /* ---------- Team-Formular: weitere Spielerzeile ---------- */
  document.querySelectorAll("[data-add-member]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const list = document.getElementById("members");
      const tpl = list.querySelector(".member-row");
      const row = tpl.cloneNode(true);
      row.querySelectorAll("input").forEach((i) => (i.value = ""));
      row.querySelectorAll("select").forEach((s) => (s.value = ""));
      list.appendChild(row);
      row.querySelector("input").focus();
    });
  });
  document.addEventListener("click", (ev) => {
    const rm = ev.target.closest("[data-remove-row]");
    if (rm) {
      const rows = document.querySelectorAll("#members .member-row");
      if (rows.length > 1) rm.closest(".member-row").remove();
      else rm.closest(".member-row").querySelectorAll("input").forEach((i) => (i.value = ""));
    }
  });

  /* ---------- Charts ---------- */
  if (window.Chart) {
    Chart.defaults.color = "#8d99b3";
    Chart.defaults.borderColor = "rgba(38, 49, 80, .6)";
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    Chart.defaults.plugins.legend.labels.boxWidth = 12;
    Chart.defaults.maintainAspectRatio = false;
  }

  const fmt = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1 });

  function lineOptions(yTitle) {
    return {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      spanGaps: true,
      elements: { point: { radius: 0, hoverRadius: 4 }, line: { tension: 0.25, borderWidth: 2 } },
      scales: {
        x: { title: { display: true, text: "Minute" }, grid: { display: false } },
        y: { title: { display: !!yTitle, text: yTitle }, ticks: { callback: (v) => fmt.format(v) } },
      },
      plugins: {
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.parsed.y == null ? "–" : fmt.format(c.parsed.y)}` } },
      },
    };
  }

  /* Analyse-Seite */
  const analysis = readJSON("analysis-data");
  if (analysis && window.Chart) {
    const canvas = document.getElementById("analysis-chart");
    const statSelect = document.getElementById("stat-select");
    const chips = document.getElementById("player-chips");
    const colors = {};
    analysis.players.forEach((p, i) => (colors[p.puuid] = PALETTE[i % PALETTE.length]));
    const initial = analysis.players.filter((p) => p.focus);
    const active = new Set((initial.length ? initial : analysis.players.slice(0, 5)).map((p) => p.puuid));

    analysis.players.forEach((p) => {
      const chip = document.createElement("span");
      chip.className = "chip" + (active.has(p.puuid) ? " on" : "");
      chip.style.setProperty("--chip-color", colors[p.puuid]);
      chip.innerHTML = `<span class="dot"></span>${p.name} <span class="muted small">${p.position_label} · ${p.games}×</span>`;
      chip.addEventListener("click", () => {
        if (active.has(p.puuid)) active.delete(p.puuid); else active.add(p.puuid);
        chip.classList.toggle("on");
        draw();
      });
      chips.appendChild(chip);
    });

    const labels = Array.from({ length: analysis.minutes }, (_, i) => i);
    const chart = new Chart(canvas, { type: "line", data: { labels, datasets: [] }, options: lineOptions("") });

    function draw() {
      const stat = statSelect.value;
      const series = analysis.series[stat] || {};
      chart.data.datasets = analysis.players
        .filter((p) => active.has(p.puuid))
        .map((p) => ({ label: p.name, data: series[p.puuid] || [], borderColor: colors[p.puuid], backgroundColor: colors[p.puuid] }));
      chart.options.scales.y.title = { display: true, text: statSelect.selectedOptions[0].textContent };
      chart.update();
      try { localStorage.setItem("ps-stat", stat); } catch (e) { /* egal */ }
    }
    try {
      const saved = localStorage.getItem("ps-stat");
      if (saved && analysis.series[saved]) statSelect.value = saved;
    } catch (e) { /* egal */ }
    statSelect.addEventListener("change", draw);
    document.querySelectorAll("[data-chips]").forEach((btn) => btn.addEventListener("click", () => {
      active.clear();
      if (btn.dataset.chips === "all") analysis.players.forEach((p) => active.add(p.puuid));
      if (btn.dataset.chips === "focus") analysis.players.filter((p) => p.focus).forEach((p) => active.add(p.puuid));
      chips.querySelectorAll(".chip").forEach((c, i) => c.classList.toggle("on", active.has(analysis.players[i].puuid)));
      draw();
    }));
    draw();
  }

  /* Team-Seite */
  const team = readJSON("team-data");
  if (team && window.Chart) {
    const goldCanvas = document.getElementById("gold-chart");
    if (goldCanvas) {
      const curves = team.gold_curves;
      const len = Math.max(...Object.values(curves).map((c) => c.values.length), 0);
      const mk = (key, label, color, dash) => ({
        label, data: curves[key].values, borderColor: color, backgroundColor: color, borderDash: dash || [],
      });
      const opts = lineOptions("Gold (eigenes Team − Gegner)");
      opts.plugins.tooltip.callbacks.afterLabel = (c) => {
        const key = ["all", "win", "loss"][c.datasetIndex];
        return `n = ${curves[key].counts[c.dataIndex] || 0}`;
      };
      new Chart(goldCanvas, {
        type: "line",
        data: {
          labels: Array.from({ length: len }, (_, i) => i),
          datasets: [mk("all", "Alle Spiele", "#7c5cff"), mk("win", "Siege", "#2fd48a", [5, 4]), mk("loss", "Niederlagen", "#ff5a6a", [5, 4])],
        },
        options: opts,
      });
    }
    const trendCanvas = document.getElementById("trend-chart");
    if (trendCanvas) {
      const rows = team.trend;
      new Chart(trendCanvas, {
        type: "bar",
        data: {
          labels: rows.map((r) => r.date),
          datasets: [{
            label: "Golddifferenz @15",
            data: rows.map((r) => r.gd15),
            backgroundColor: rows.map((r) => (r.win ? "rgba(47, 212, 138, .75)" : "rgba(255, 90, 106, .75)")),
            borderRadius: 4,
          }],
        },
        options: {
          responsive: true,
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: {
              title: (items) => rows[items[0].dataIndex].date,
              label: (c) => {
                const r = rows[c.dataIndex];
                return [`${r.win ? "Sieg" : "Niederlage"} · ${r.kills}–${r.deaths}`,
                        `GD@15: ${r.gd15 == null ? "–" : fmt.format(r.gd15)}`];
              },
            } },
          },
          scales: { x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true } },
                    y: { ticks: { callback: (v) => fmt.format(v) } } },
        },
      });
    }
  }
})();
