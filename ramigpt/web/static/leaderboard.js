/**
 * Collaborative benchmark leaderboard UI.
 */
(function () {
  const $ = (id) => document.getElementById(id);
  const LIMIT = 6;
  let currentMetric = "got_root_count";
  /** @type {any} */
  let lastPayload = null;

  const SHORT_COLORS = [
    "#00ff00",
    "#33ff99",
    "#66ff33",
    "#99ff00",
    "#00cc66",
    "#22aa22",
  ];

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function shortLabel(label, max) {
    const text = String(label || "unknown");
    const lim = max || 28;
    if (text.length <= lim) return text;
    return text.slice(0, lim - 1) + "…";
  }

  function fmtInt(value) {
    if (value == null || Number.isNaN(Number(value))) return "—";
    return Math.round(Number(value)).toLocaleString();
  }

  function fmtNum(value, digits) {
    if (value == null || Number.isNaN(Number(value))) return "—";
    return Number(value).toFixed(digits == null ? 1 : digits);
  }

  function fmtPct(rate) {
    if (rate == null || Number.isNaN(Number(rate))) return "—";
    return `${(Number(rate) * 100).toFixed(1)}%`;
  }

  function fmtTokens(value) {
    const usable = value == null ? null : Number(value);
    if (usable == null || Number.isNaN(usable) || usable <= 0) return "—";
    return Math.round(usable).toLocaleString();
  }

  function setStatus(msg, isError) {
    const el = $("lb-status");
    if (!el) return;
    if (!msg) {
      el.hidden = true;
      el.textContent = "";
      el.classList.remove("is-error");
      return;
    }
    el.hidden = false;
    el.textContent = msg;
    el.classList.toggle("is-error", !!isError);
  }

  async function api(path) {
    const res = await fetch(path);
    let data = null;
    try {
      data = await res.json();
    } catch (_) {
      data = null;
    }
    if (!res.ok) {
      const err = new Error((data && data.error) || res.statusText || "Request failed");
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  function emptyChart(el, message) {
    if (!el) return;
    el.innerHTML = `<div class="lb-empty">${escapeHtml(message || "No data")}</div>`;
  }

  function barChart(el, rows, opts) {
    if (!el) return;
    const getValue = opts.getValue;
    const getLabel = opts.getLabel || ((r) => r.profile_label);
    const format = opts.format || fmtNum;
    const maxHint = opts.max;
    const values = rows.map((r) => {
      const v = getValue(r);
      return v == null || Number.isNaN(Number(v)) ? null : Number(v);
    });
    if (!rows.length || values.every((v) => v == null)) {
      emptyChart(el, opts.empty || "No data for this chart");
      return;
    }
    const present = values.filter((v) => v != null);
    const max = Math.max(maxHint || 0, ...present, 0.0001);
    const width = 520;
    const rowH = 28;
    const left = 150;
    const right = 54;
    const top = 8;
    const height = top + rows.length * rowH + 8;
    const barW = width - left - right;
    let html = `<svg viewBox="0 0 ${width} ${height}" role="presentation">`;
    rows.forEach((row, i) => {
      const y = top + i * rowH;
      const val = values[i];
      const w = val == null ? 0 : Math.max(2, (val / max) * barW);
      const color = SHORT_COLORS[i % SHORT_COLORS.length];
      html += `<text x="0" y="${y + 16}" class="lb-axis-label">${escapeHtml(shortLabel(getLabel(row), 22))}</text>`;
      html += `<rect x="${left}" y="${y + 4}" width="${barW}" height="16" fill="rgba(0,255,0,0.06)" />`;
      if (val != null) {
        html += `<rect x="${left}" y="${y + 4}" width="${w.toFixed(1)}" height="16" fill="${color}" />`;
        html += `<text x="${left + w + 6}" y="${y + 16}">${escapeHtml(format(val))}</text>`;
      } else {
        html += `<text x="${left + 6}" y="${y + 16}">—</text>`;
      }
    });
    html += "</svg>";
    el.innerHTML = html;
  }

  function groupedBars(el, rows, series) {
    if (!el) return;
    if (!rows.length) {
      emptyChart(el, "No token telemetry");
      return;
    }
    const width = 520;
    const rowH = 36;
    const left = 150;
    const right = 20;
    const top = 28;
    const height = top + rows.length * rowH + 8;
    const barArea = width - left - right;
    const groupGap = 8;
    const barH = 10;
    let max = 0;
    rows.forEach((row) => {
      series.forEach((s) => {
        const v = s.getValue(row);
        if (v != null && v > max) max = v;
      });
    });
    if (max <= 0) {
      emptyChart(el, "Token telemetry unavailable (zeros excluded)");
      return;
    }
    let html = `<svg viewBox="0 0 ${width} ${height}" role="presentation">`;
    series.forEach((s, si) => {
      html += `<rect x="${left + si * 110}" y="6" width="10" height="10" fill="${s.color}" />`;
      html += `<text x="${left + si * 110 + 16}" y="15">${escapeHtml(s.label)}</text>`;
    });
    rows.forEach((row, i) => {
      const y = top + i * rowH;
      html += `<text x="0" y="${y + 18}" class="lb-axis-label">${escapeHtml(shortLabel(row.profile_label, 22))}</text>`;
      series.forEach((s, si) => {
        const val = s.getValue(row);
        const w = val == null || val <= 0 ? 0 : Math.max(2, (val / max) * barArea);
        const yy = y + si * (barH + 2);
        html += `<rect x="${left}" y="${yy}" width="${barArea}" height="${barH}" fill="rgba(0,255,0,0.05)" />`;
        if (w > 0) {
          html += `<rect x="${left}" y="${yy}" width="${w.toFixed(1)}" height="${barH}" fill="${s.color}" />`;
        }
      });
      void groupGap;
    });
    html += "</svg>";
    el.innerHTML = html;
  }

  function stackedOutcomes(el, rows) {
    if (!el) return;
    if (!rows.length) {
      emptyChart(el, "No outcomes");
      return;
    }
    const width = 520;
    const rowH = 28;
    const left = 150;
    const right = 64;
    const top = 24;
    const height = top + rows.length * rowH + 8;
    const barW = width - left - right;
    const max = Math.max(
      ...rows.map((r) => (r.got_root_count || 0) + (r.unresolved_count || 0)),
      1
    );
    let html = `<svg viewBox="0 0 ${width} ${height}" role="presentation">`;
    html += `<rect x="${left}" y="6" width="10" height="10" fill="#00ff00" /><text x="${left + 16}" y="15">Resolved</text>`;
    html += `<rect x="${left + 110}" y="6" width="10" height="10" fill="#335533" /><text x="${left + 126}" y="15">Unresolved</text>`;
    rows.forEach((row, i) => {
      const y = top + i * rowH;
      const resolved = row.got_root_count || 0;
      const unresolved = row.unresolved_count || 0;
      const total = resolved + unresolved;
      const rw = total ? (resolved / max) * barW : 0;
      const uw = total ? (unresolved / max) * barW : 0;
      html += `<text x="0" y="${y + 16}" class="lb-axis-label">${escapeHtml(shortLabel(row.profile_label, 22))}</text>`;
      html += `<rect x="${left}" y="${y + 4}" width="${rw.toFixed(1)}" height="16" fill="#00ff00" />`;
      html += `<rect x="${left + rw}" y="${y + 4}" width="${uw.toFixed(1)}" height="16" fill="#335533" />`;
      html += `<text x="${left + rw + uw + 6}" y="${y + 16}">${resolved}/${total || 0}</text>`;
    });
    html += "</svg>";
    el.innerHTML = html;
  }

  function scatterChart(el, rows) {
    if (!el) return;
    const points = rows
      .map((r, i) => ({
        row: r,
        i,
        x: r.score_percent,
        y: r.usable_mean_tokens_to_root,
        n: r.attempted || 1,
      }))
      .filter((p) => p.x != null && p.y != null && p.y > 0);
    if (!points.length) {
      emptyChart(el, "Need success rate + usable tokens-to-root");
      return;
    }
    const width = 640;
    const height = 280;
    const pad = { t: 20, r: 20, b: 36, l: 48 };
    const maxX = 100;
    const maxY = Math.max(...points.map((p) => p.y)) * 1.15;
    const maxN = Math.max(...points.map((p) => p.n));
    const xScale = (v) => pad.l + (v / maxX) * (width - pad.l - pad.r);
    const yScale = (v) => height - pad.b - (v / maxY) * (height - pad.t - pad.b);
    let html = `<svg viewBox="0 0 ${width} ${height}" role="presentation">`;
    html += `<line x1="${pad.l}" y1="${height - pad.b}" x2="${width - pad.r}" y2="${height - pad.b}" stroke="rgba(0,255,0,0.35)" />`;
    html += `<line x1="${pad.l}" y1="${pad.t}" x2="${pad.l}" y2="${height - pad.b}" stroke="rgba(0,255,0,0.35)" />`;
    html += `<text x="${width / 2}" y="${height - 8}">Success rate (%)</text>`;
    html += `<text x="12" y="${height / 2}" transform="rotate(-90 12 ${height / 2})">Tokens → root</text>`;
    points.forEach((p) => {
      const r = 6 + (p.n / maxN) * 10;
      const color = SHORT_COLORS[p.i % SHORT_COLORS.length];
      html += `<circle cx="${xScale(p.x).toFixed(1)}" cy="${yScale(p.y).toFixed(1)}" r="${r.toFixed(1)}" fill="${color}" fill-opacity="0.75" stroke="#0f0" />`;
      html += `<text x="${(xScale(p.x) + r + 4).toFixed(1)}" y="${(yScale(p.y) + 3).toFixed(1)}">${escapeHtml(shortLabel(p.row.profile_label, 18))}</text>`;
    });
    html += "</svg>";
    el.innerHTML = html;
  }

  function radarChart(el, radarRows) {
    if (!el) return;
    if (!radarRows || !radarRows.length) {
      emptyChart(el, "No radar scores");
      return;
    }
    const axes = ["success", "speed", "token_efficiency", "request_efficiency"];
    const labels = ["Success", "Speed", "Tokens", "Requests"];
    const width = 420;
    const height = 280;
    const cx = width / 2;
    const cy = height / 2 + 6;
    const radius = 90;
    const angle = (i) => (-Math.PI / 2) + (i * 2 * Math.PI) / axes.length;
    let html = `<svg viewBox="0 0 ${width} ${height}" role="presentation">`;
    for (let ring = 1; ring <= 4; ring++) {
      const rr = (radius * ring) / 4;
      const pts = axes
        .map((_, i) => {
          const a = angle(i);
          return `${cx + Math.cos(a) * rr},${cy + Math.sin(a) * rr}`;
        })
        .join(" ");
      html += `<polygon points="${pts}" fill="none" stroke="rgba(0,255,0,0.2)" />`;
    }
    axes.forEach((_, i) => {
      const a = angle(i);
      const x = cx + Math.cos(a) * radius;
      const y = cy + Math.sin(a) * radius;
      html += `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="rgba(0,255,0,0.25)" />`;
      html += `<text x="${cx + Math.cos(a) * (radius + 18)}" y="${cy + Math.sin(a) * (radius + 18)}" text-anchor="middle">${labels[i]}</text>`;
    });
    radarRows.slice(0, LIMIT).forEach((row, idx) => {
      const color = SHORT_COLORS[idx % SHORT_COLORS.length];
      const pts = axes
        .map((key, i) => {
          const score = (row.axes && row.axes[key]) != null ? Number(row.axes[key]) : 0;
          const a = angle(i);
          const rr = (Math.max(0, Math.min(100, score)) / 100) * radius;
          return `${cx + Math.cos(a) * rr},${cy + Math.sin(a) * rr}`;
        })
        .join(" ");
      html += `<polygon points="${pts}" fill="${color}" fill-opacity="0.12" stroke="${color}" stroke-width="1.5" />`;
    });
    radarRows.slice(0, LIMIT).forEach((row, idx) => {
      html += `<rect x="8" y="${12 + idx * 14}" width="8" height="8" fill="${SHORT_COLORS[idx % SHORT_COLORS.length]}" />`;
      html += `<text x="20" y="${20 + idx * 14}">${escapeHtml(shortLabel(row.profile_label, 24))}</text>`;
    });
    html += "</svg>";
    el.innerHTML = html;
  }

  function heatmap(el, heat) {
    if (!el) return;
    const families = (heat && heat.families) || [];
    const profiles = (heat && heat.profiles) || [];
    const cells = (heat && heat.cells) || [];
    if (!families.length || !profiles.length) {
      emptyChart(el, "No family coverage yet");
      return;
    }
    const cellMap = {};
    cells.forEach((c) => {
      cellMap[`${c.family}|${c.profile_key}`] = c;
    });
    const left = 100;
    const top = 90;
    const cellW = 56;
    const cellH = 28;
    const width = left + profiles.length * cellW + 20;
    const height = top + families.length * cellH + 20;
    let html = `<svg viewBox="0 0 ${width} ${height}" role="presentation">`;
    profiles.forEach((p, i) => {
      const x = left + i * cellW + cellW / 2;
      html += `<text x="${x}" y="80" text-anchor="start" transform="rotate(-55 ${x} 80)">${escapeHtml(shortLabel(p.profile_label, 18))}</text>`;
    });
    families.forEach((family, fi) => {
      const y = top + fi * cellH;
      html += `<text x="0" y="${y + 18}" class="lb-axis-label">${escapeHtml(family)}</text>`;
      profiles.forEach((p, pi) => {
        const cell = cellMap[`${family}|${p.profile_key}`];
        const rate = cell && cell.got_root_rate != null ? cell.got_root_rate : null;
        const x = left + pi * cellW;
        let fill = "rgba(0,255,0,0.05)";
        if (rate != null) {
          const a = 0.12 + rate * 0.75;
          fill = `rgba(0,255,0,${a.toFixed(2)})`;
        }
        html += `<rect x="${x}" y="${y}" width="${cellW - 2}" height="${cellH - 2}" fill="${fill}" stroke="rgba(0,255,0,0.25)" />`;
        html += `<text x="${x + cellW / 2 - 1}" y="${y + 17}" text-anchor="middle">${rate == null ? "—" : escapeHtml(fmtPct(rate))}</text>`;
      });
    });
    html += "</svg>";
    el.innerHTML = html;
  }

  function trendChart(el, points) {
    if (!el) return;
    if (!points || points.length < 2) {
      emptyChart(el, "Need at least two dated runs for a trend");
      return;
    }
    const width = 680;
    const height = 260;
    const pad = { t: 20, r: 24, b: 40, l: 48 };
    const maxPassed = Math.max(...points.map((p) => p.cumulative_passed || 0), 1);
    const xScale = (i) => pad.l + (i / (points.length - 1)) * (width - pad.l - pad.r);
    const yRate = (v) => height - pad.b - ((v || 0) * (height - pad.t - pad.b));
    const yCount = (v) => height - pad.b - ((v || 0) / maxPassed) * (height - pad.t - pad.b);
    const rateLine = points
      .map((p, i) => `${i === 0 ? "M" : "L"} ${xScale(i).toFixed(1)} ${yRate(p.cumulative_pass_rate).toFixed(1)}`)
      .join(" ");
    const countLine = points
      .map((p, i) => `${i === 0 ? "M" : "L"} ${xScale(i).toFixed(1)} ${yCount(p.cumulative_passed).toFixed(1)}`)
      .join(" ");
    let html = `<svg viewBox="0 0 ${width} ${height}" role="presentation">`;
    html += `<line x1="${pad.l}" y1="${height - pad.b}" x2="${width - pad.r}" y2="${height - pad.b}" stroke="rgba(0,255,0,0.35)" />`;
    html += `<line x1="${pad.l}" y1="${pad.t}" x2="${pad.l}" y2="${height - pad.b}" stroke="rgba(0,255,0,0.35)" />`;
    html += `<path d="${rateLine}" fill="none" stroke="#00ff00" stroke-width="2" />`;
    html += `<path d="${countLine}" fill="none" stroke="#66aa66" stroke-width="2" stroke-dasharray="4 3" />`;
    html += `<text x="${pad.l}" y="14">Cum. pass rate</text>`;
    html += `<text x="${pad.l + 120}" y="14">Cum. passed (dashed)</text>`;
    const first = points[0];
    const last = points[points.length - 1];
    html += `<text x="${pad.l}" y="${height - 12}">${escapeHtml(first.date)}</text>`;
    html += `<text x="${width - pad.r}" y="${height - 12}" text-anchor="end">${escapeHtml(last.date)}</text>`;
    html += "</svg>";
    el.innerHTML = html;
  }

  function renderSummary(summary) {
    const el = $("lb-summary");
    if (!el) return;
    const cards = [
      { label: "Profiles", value: fmtInt(summary.profiles) },
      { label: "Runs", value: fmtInt(summary.runs) },
      { label: "Observations", value: fmtInt(summary.observations) },
      { label: "Resolved", value: fmtInt(summary.got_root_count) },
    ];
    el.innerHTML = cards
      .map(
        (c) => `<div class="lb-stat"><span class="label">${escapeHtml(c.label)}</span><span class="value">${escapeHtml(c.value)}</span></div>`
      )
      .join("");
  }

  function renderTable(rows) {
    const body = $("lb-table-body");
    if (!body) return;
    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="9" class="muted">No collaborative results yet.</td></tr>`;
      return;
    }
    body.innerHTML = rows
      .map((row) => {
        return `<tr>
          <td class="lb-rank">${escapeHtml(row.rank)}</td>
          <td class="lb-name">${escapeHtml(row.profile_label || row.model_key_name || "—")}</td>
          <td>${escapeHtml(fmtInt(row.got_root_count))}</td>
          <td>${escapeHtml(row.score_percent != null ? row.score_percent.toFixed(1) + "%" : "—")}</td>
          <td>${escapeHtml(fmtInt(row.attempted))}</td>
          <td>${escapeHtml(fmtInt(row.runs))}</td>
          <td>${escapeHtml(fmtTokens(row.usable_mean_prompt_tokens || row.mean_prompt_tokens))}</td>
          <td>${escapeHtml(fmtTokens(row.usable_mean_tokens_to_root || row.mean_tokens_to_root))}</td>
          <td>${escapeHtml(row.mean_elapsed_to_root == null ? "—" : fmtNum(row.mean_elapsed_to_root) + "s")}</td>
        </tr>`;
      })
      .join("");
  }

  function renderMethodology(methodology) {
    const el = $("lb-methodology");
    if (!el || !methodology) return;
    const items = [
      methodology.score,
      methodology.resolved,
      methodology.tokens,
      methodology.trend,
    ].filter(Boolean);
    el.innerHTML = items.map((t) => `<li>${escapeHtml(t)}</li>`).join("");
  }

  function renderCharts(payload) {
    const top = payload.top || [];
    const charts = payload.charts || {};

    barChart($("lb-chart-resolved"), top, {
      getValue: (r) => r.got_root_count,
      format: fmtInt,
      empty: "No resolved counts",
    });
    barChart($("lb-chart-success"), top, {
      getValue: (r) => (r.got_root_rate == null ? null : r.got_root_rate * 100),
      format: (v) => `${fmtNum(v, 1)}%`,
      max: 100,
      empty: "No success rates",
    });
    groupedBars($("lb-chart-tokens"), top, [
      {
        label: "Avg input",
        color: "#66ff33",
        getValue: (r) => r.usable_mean_prompt_tokens || null,
      },
      {
        label: "Tok → root",
        color: "#00ff00",
        getValue: (r) => r.usable_mean_tokens_to_root || null,
      },
    ]);
    barChart($("lb-chart-time"), top, {
      getValue: (r) => r.mean_elapsed_to_root,
      format: (v) => `${fmtNum(v, 1)}s`,
      empty: "No time-to-root data",
    });
    barChart($("lb-chart-requests"), top, {
      getValue: (r) => r.mean_ai_requests_to_root,
      format: (v) => fmtNum(v, 2),
      empty: "No AI request data",
    });
    barChart($("lb-chart-commands"), top, {
      getValue: (r) => r.mean_commands_to_root,
      format: (v) => fmtNum(v, 2),
      empty: "No command data",
    });
    barChart($("lb-chart-tps"), top, {
      getValue: (r) => r.usable_tokens_per_second_to_root || r.tokens_per_second_to_root,
      format: (v) => fmtNum(v, 2),
      empty: "No usable tokens/sec (zeros excluded)",
    });
    radarChart($("lb-chart-radar"), charts.radar || []);
    scatterChart($("lb-chart-scatter"), top);
    stackedOutcomes($("lb-chart-outcomes"), top);
    barChart($("lb-chart-coverage"), charts.coverage || [], {
      getLabel: (r) => r.profile_label,
      getValue: (r) => (r.coverage_rate == null ? null : r.coverage_rate * 100),
      format: (v) => `${fmtNum(v, 1)}%`,
      max: 100,
      empty: "No coverage data",
    });
    heatmap($("lb-chart-heatmap"), charts.family_heatmap || {});
    trendChart($("lb-chart-trend"), charts.trend || []);
    barChart($("lb-chart-hardware"), charts.hardware_comparison || [], {
      getLabel: (r) => `${shortLabel(r.model_key_name, 16)} · ${r.hardware_label || r.hardware_key}`,
      getValue: (r) => (r.got_root_rate == null ? null : r.got_root_rate * 100),
      format: (v) => `${fmtNum(v, 1)}%`,
      max: 100,
      empty: "No multi-hardware comparisons yet",
    });
    barChart($("lb-chart-tools"), charts.tools_impact || [], {
      getLabel: (r) => r.tools_label || "none",
      getValue: (r) => (r.got_root_rate == null ? null : r.got_root_rate * 100),
      format: (v) => `${fmtNum(v, 1)}%`,
      max: 100,
      empty: "No tools impact data",
    });
  }

  function renderPayload(payload) {
    lastPayload = payload;
    const updated = $("lb-updated");
    if (updated) {
      const when = payload.updated_at ? new Date(payload.updated_at).toLocaleString() : "—";
      const n = (payload.top || []).length;
      updated.textContent = `Updated ${when} · showing top ${n} · metric ${payload.metric || currentMetric}`;
    }
    renderSummary(payload.summary || {});
    renderTable(payload.top || []);
    renderCharts(payload);
    renderMethodology(payload.methodology || {});
  }

  async function loadLeaderboard() {
    setStatus("Loading rankings…", false);
    try {
      const data = await api(
        `/api/benchmark/results/leaderboard?limit=${LIMIT}&by=${encodeURIComponent(currentMetric)}`
      );
      if (!data.ok) {
        setStatus(data.error || "No leaderboard data", true);
        renderPayload({
          top: [],
          summary: {},
          charts: {},
          methodology: data.methodology,
          metric: currentMetric,
          updated_at: null,
        });
        return;
      }
      setStatus("");
      renderPayload(data);
    } catch (err) {
      setStatus(err.message || "Failed to load leaderboard", true);
      if (!lastPayload) {
        renderPayload({ top: [], summary: {}, charts: {}, metric: currentMetric });
      }
    }
  }

  function bind() {
    document.querySelectorAll(".lb-metric-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        const metric = btn.getAttribute("data-metric") || "got_root_count";
        currentMetric = metric;
        document.querySelectorAll(".lb-metric-tab").forEach((el) => {
          el.classList.toggle("is-active", el === btn);
        });
        loadLeaderboard();
      });
    });
    const refresh = $("lb-refresh");
    if (refresh) refresh.addEventListener("click", () => loadLeaderboard());
    const printBtn = $("lb-print");
    if (printBtn) printBtn.addEventListener("click", () => window.print());
  }

  bind();
  loadLeaderboard();
})();
