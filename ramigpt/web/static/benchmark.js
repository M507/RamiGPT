/**
 * Privilege-escalation benchmark UI.
 */
(function () {
  const $ = (id) => document.getElementById(id);
  let pollTimer = null;
  let pollRunning = null;
  /** @type {Array<{id:string,port:number,name?:string}>} */
  let knownTargets = [];
  /** @type {Array<{id:string,name:string,description?:string,target_ids:string[]}>} */
  let knownProfiles = [];

  async function api(path, options = {}) {
    const opts = {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    };
    if (opts.body && typeof opts.body === "object") {
      opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(path, opts);
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

  function setStatus(msg, isError) {
    const el = $("bench-status");
    if (!el) return;
    el.textContent = msg || "";
    el.style.color = isError ? "var(--danger)" : "var(--muted)";
  }

  function openModal() {
    const modal = $("benchmark-modal");
    if (!modal) return;
    modal.classList.add("open");
    modal.setAttribute("aria-hidden", "false");
    refresh().catch((e) => setStatus(e.message, true));
    startPolling();
  }

  function closeModal() {
    const modal = $("benchmark-modal");
    if (!modal) return;
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
    stopPolling();
  }

  function pollIntervalMs(running) {
    // Faster while a run is active; slower when idle to avoid busy-spinning the API.
    return running ? 1200 : 4000;
  }

  function startPolling(running) {
    const next = !!running;
    if (pollTimer && pollRunning === next) return;
    stopPolling();
    pollRunning = next;
    pollTimer = setInterval(() => {
      refresh().catch(() => {});
    }, pollIntervalMs(next));
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    pollRunning = null;
  }

  function renderTools(available, defaults) {
    const list = $("bench-tool-list");
    if (!list) return;
    const tools = available && available.length ? available : [
      {
        id: "beroot",
        name: "BeRoot",
        description: "Scan first, then Full AI uses findings until root",
        default: true,
      },
    ];
    const selected = (defaults && defaults.tools) || {};
    list.innerHTML = tools
      .map((t) => {
        const checked =
          selected[t.id] != null ? !!selected[t.id] : t.default !== false;
        return `<label class="bench-tool-check">
          <input type="checkbox" data-tool-id="${escapeHtml(t.id)}" ${checked ? "checked" : ""}>
          <span>
            <strong>${escapeHtml(t.name || t.id)}</strong>
            <small>${escapeHtml(t.description || "")}</small>
          </span>
        </label>`;
      })
      .join("");
  }

  function selectedTools() {
    const out = {};
    document.querySelectorAll("#bench-tool-list input[data-tool-id]").forEach((el) => {
      out[el.getAttribute("data-tool-id")] = !!el.checked;
    });
    if (!Object.keys(out).length) {
      out.beroot = true;
    }
    return out;
  }

  function selectedTargetIds() {
    return Array.from(document.querySelectorAll("#bench-target-list input[data-target-id]"))
      .filter((el) => el.checked)
      .map((el) => el.getAttribute("data-target-id"))
      .filter(Boolean);
  }

  function sameTargetIds(left, right) {
    if (left.length !== right.length) return false;
    const expected = new Set(right);
    return left.every((id) => expected.has(id));
  }

  function syncTargetProfileSelector() {
    const select = $("bench-target-profile");
    if (!select) return;
    const selected = selectedTargetIds();
    const allIds = knownTargets.map((target) => target.id);
    if (sameTargetIds(selected, allIds)) {
      select.value = "all";
      return;
    }
    if (!selected.length) {
      select.value = "none";
      return;
    }
    const profile = knownProfiles.find((item) => sameTargetIds(selected, item.target_ids || []));
    select.value = profile ? `profile:${profile.id}` : "custom";
  }

  function setTargetIds(targetIds) {
    const list = $("bench-target-list");
    if (!list) return;
    const selected = new Set(targetIds);
    list.dataset.userTouched = "1";
    list.querySelectorAll("input[data-target-id]").forEach((el) => {
      el.checked = selected.has(el.getAttribute("data-target-id"));
    });
    updateSelectedPortsLabel();
    syncTargetProfileSelector();
  }

  function renderTargetProfiles(profiles) {
    const select = $("bench-target-profile");
    if (!select) return;
    knownProfiles = Array.isArray(profiles) ? profiles : [];
    select.innerHTML = `
      <option value="all">Select all</option>
      <option value="none">None</option>
      <optgroup label="Profiles">
        ${knownProfiles
          .map(
            (profile) =>
              `<option value="profile:${escapeHtml(profile.id)}">${escapeHtml(profile.name)} (${(profile.target_ids || []).length})</option>`
          )
          .join("")}
      </optgroup>
      <option value="custom" hidden>Custom selection</option>`;
    syncTargetProfileSelector();
  }

  function selectedPortsLabel() {
    const ids = new Set(selectedTargetIds());
    const ports = knownTargets
      .filter((t) => ids.has(t.id))
      .map((t) => t.port)
      .filter((p) => p != null);
    if (!ports.length) return "none selected";
    if (ports.length === 1) return String(ports[0]);
    const sorted = [...ports].sort((a, b) => a - b);
    return `${sorted[0]}–${sorted[sorted.length - 1]} (${sorted.length} selected)`;
  }

  function updateSelectedPortsLabel() {
    const el = $("bench-cred-ports");
    if (!el) return;
    el.textContent = selectedPortsLabel();
  }

  function renderTargets(targets, defaults) {
    const list = $("bench-target-list");
    if (!list) return;
    if (targets && targets.length) {
      knownTargets = targets.map((t) => ({
        id: t.id,
        port: t.port,
        name: t.name,
      }));
    }
    const prev = {};
    list.querySelectorAll("input[data-target-id]").forEach((el) => {
      prev[el.getAttribute("data-target-id")] = !!el.checked;
    });
    const preserve = !!list.dataset.userTouched;
    const defaultIds = new Set((defaults && defaults.target_ids) || (targets || []).map((t) => t.id));

    list.innerHTML = (targets || [])
      .map((t) => {
        const checked = preserve
          ? prev[t.id] !== false && (prev[t.id] != null ? prev[t.id] : defaultIds.has(t.id))
          : defaultIds.has(t.id);
        const primitive = t.primitive || t.sudo_binary || "";
        const family = t.family || "misc";
        return `<li>
          <label class="bench-tool-check">
            <input type="checkbox" data-target-id="${escapeHtml(t.id)}" ${checked ? "checked" : ""}>
            <span>
              <strong>${escapeHtml(t.name)}</strong>
              <small>SSH :${t.port} · ${escapeHtml(family)} · ${escapeHtml(primitive)} — ${escapeHtml(t.description || "")}</small>
            </span>
          </label>
        </li>`;
      })
      .join("");

    if (defaults) {
      if ($("bench-cred-user")) $("bench-cred-user").textContent = defaults.username || "lowpriv";
      if ($("bench-cred-pass")) $("bench-cred-pass").textContent = defaults.password || "password";
    }
    updateSelectedPortsLabel();
    syncTargetProfileSelector();
  }

  function phaseLabel(phase) {
    return phase || "idle";
  }

  function renderRun(run, running, batch) {
    const phaseEl = $("bench-phase");
    const results = $("bench-results");
    const logEl = $("bench-log");
    const startBtn = $("bench-start");
    const stopBtn = $("bench-stop");

    if (phaseEl) {
      const phase = run ? run.phase : "idle";
      const reps = (batch && batch.repetitions) || (run && run.repetitions) || 1;
      const rep = (batch && batch.repetition) || (run && run.repetition) || 1;
      const repLabel = reps > 1 ? ` · run ${rep}/${reps}` : "";
      phaseEl.className = "status-pill " + (run ? phase : "idle");
      phaseEl.innerHTML = `<i class="dot"></i> ${phaseLabel(run ? phase : "Idle")}${escapeHtml(repLabel)}`;
    }

    if (results) {
      if (!run || !(run.targets || []).length) {
        results.innerHTML = `<div class="muted small">No run yet. Configure AI and remote host, then Start.</div>`;

      } else {
        const modelLabel =
          run.provider || run.model
            ? `<div class="muted small">Model: ${escapeHtml(run.provider || "?")}/${escapeHtml(run.model || "?")}</div>`
            : "";
        const resultDir = run.result_dir
          ? `<div class="muted small">Results: <code>${escapeHtml(run.result_dir)}</code></div>`
          : "";
        results.innerHTML =
          modelLabel +
          resultDir +
          run.targets
            .map((t) => {
              const klass = t.status || "pending";
              const elapsed = t.elapsed_seconds != null ? `${t.elapsed_seconds}s` : "—";
              const cmds =
                t.ai_requests != null ? `${t.ai_requests} cmds` : "";
              const tools = (t.tools_used || []).length
                ? `tools=${(t.tools_used || []).join(",")}`
                : "";
              const meta = [elapsed, cmds, tools, t.message || ""]
                .filter(Boolean)
                .join(" · ");
              return `<div class="bench-result-row status-${escapeHtml(klass)}">
              <span class="bench-result-name">${escapeHtml(t.name)} <span class="muted">:${t.port}</span></span>
              <span class="bench-result-status">${escapeHtml(klass)}</span>
              <span class="bench-result-meta muted">${escapeHtml(meta)}</span>
            </div>`;
            })
            .join("");
      }
    }

    if (logEl) {
      const lines = (run && run.log) || [];
      logEl.textContent = lines.slice(-80).join("\n");
      logEl.scrollTop = logEl.scrollHeight;
    }

    if (startBtn) startBtn.disabled = !!running;
    if (stopBtn) stopBtn.disabled = !running;
    const cleanBtn = $("bench-clean-logs");
    if (cleanBtn) cleanBtn.disabled = !!running;

    if (run && run.error) setStatus(run.error, true);
  }

  function renderAiSettings(ai) {
    const el = $("bench-ai-model-label");
    if (!el) return;
    if (!ai || (!ai.provider && !ai.model)) {
      el.textContent = "Model: —";
      return;
    }
    el.textContent = `Model: ${ai.provider || "?"} / ${ai.model || "?"}`;
  }

  async function refresh() {
    const data = await api("/api/benchmark/status");
    if (data.targets && data.targets.length) {
      knownTargets = data.targets.map((t) => ({
        id: t.id,
        port: t.port,
        name: t.name,
      }));
    }
    renderTargetProfiles(data.profiles);
    if (!$("bench-target-list")?.dataset.userTouched) {
      renderTargets(data.targets, data.defaults);
    } else if (data.defaults) {
      if ($("bench-cred-user")) $("bench-cred-user").textContent = data.defaults.username || "lowpriv";
      if ($("bench-cred-pass")) $("bench-cred-pass").textContent = data.defaults.password || "password";
      updateSelectedPortsLabel();
    }
    if (!$("bench-tool-list")?.dataset.userTouched) {
      renderTools(data.available_tools, data.defaults);
    }
    applyRemotePreset(data.remote_preset);
    renderAiSettings(data.ai_settings);
    renderRun(data.run, data.running, data.batch);
    // Retune poll cadence when run activity changes.
    startPolling(!!data.running);
    if (data.defaults && $("bench-timeout") && !data.running) {
      const field = $("bench-timeout");
      const presetTimeout =
        (data.remote_preset && data.remote_preset.timeout_seconds) ||
        data.defaults.timeout_seconds ||
        180;
      if (document.activeElement !== field && !field.dataset.touched) {
        field.value = presetTimeout;
      }
    }
    if (data.defaults && $("bench-runs") && !data.running) {
      const runsField = $("bench-runs");
      if (document.activeElement !== runsField && !runsField.dataset.touched) {
        runsField.value = data.defaults.repetitions || 1;
      }
    }
    return data;
  }

  let remotePresetApplied = false;

  function applyRemotePreset(preset) {
    if (!preset || remotePresetApplied) return;
    const source = $("bench-remote-source");
    if (source) {
      source.innerHTML = preset.config_exists
        ? `Prefills from <code>${escapeHtml(preset.config_path || "data/benchmark/remote.json")}</code>.`
        : `No <code>data/benchmark/remote.json</code> yet — enter remote credentials below (see remote.example.json).`;
    }
    if (preset.host && $("bench-remote-host") && !$("bench-remote-host").value) {
      $("bench-remote-host").value = preset.host;
    }
    if (preset.port && $("bench-remote-port")) {
      $("bench-remote-port").value = preset.port;
    }
    if (preset.username && $("bench-remote-user") && !$("bench-remote-user").value) {
      $("bench-remote-user").value = preset.username;
    }
    if (preset.password && $("bench-remote-pass") && !$("bench-remote-pass").value) {
      $("bench-remote-pass").value = preset.password;
    }
    remotePresetApplied = true;
  }

  async function testRemoteAccess() {
    setStatus("Testing SSH…");
    try {
      const data = await api("/api/benchmark/remote/test", {
        method: "POST",
        body: {
          host: ($("bench-remote-host").value || "").trim(),
          port: parseInt($("bench-remote-port").value, 10) || 22,
          username: ($("bench-remote-user").value || "").trim(),
          password: $("bench-remote-pass").value || "",
        },
      });
      setStatus(data.ok ? `SSH OK — ${data.output}` : data.error || "SSH failed", !data.ok);
    } catch (err) {
      setStatus(err.message || String(err), true);
    }
  }

  async function startBenchmark() {
    setStatus("");
    const targetIds = selectedTargetIds();
    if (!targetIds.length) {
      setStatus("Select at least one target to run.", true);
      return;
    }
    const payload = {
      mode: "remote",
      timeout_seconds: parseInt($("bench-timeout").value, 10) || 180,
      repetitions: Math.max(1, Math.min(50, parseInt($("bench-runs")?.value, 10) || 1)),
      tools: selectedTools(),
      target_ids: targetIds,
      remote: {
        host: ($("bench-remote-host").value || "").trim(),
        port: parseInt($("bench-remote-port").value, 10) || 22,
        username: ($("bench-remote-user").value || "").trim(),
        password: $("bench-remote-pass").value || "",
      },
    };
    // Empty password falls back to data/benchmark/remote.json on the server.
    try {
      $("bench-start").disabled = true;
      await api("/api/benchmark/start", { method: "POST", body: payload });
      setStatus(`Benchmark started (${targetIds.length} target${targetIds.length === 1 ? "" : "s"})…`);
      await refresh();
      if (window.Workspace && typeof window.Workspace.refreshInventory === "function") {
        window.Workspace.refreshInventory();
      }
    } catch (err) {
      setStatus(err.message || String(err), true);
      $("bench-start").disabled = false;
    }
  }

  async function stopBenchmark() {
    try {
      await api("/api/benchmark/stop", { method: "POST", body: {} });
      setStatus("Stop requested…");
      await refresh();
    } catch (err) {
      setStatus(err.message || String(err), true);
    }
  }

  async function cleanLogs() {
    const ok = window.confirm(
      "Delete all session logs under data/logs/sessions?\n\nThis removes normal session logs and benchmark suite logs. Benchmark results under data/benchmark/results are kept."
    );
    if (!ok) return;
    setStatus("Cleaning logs…");
    try {
      const data = await api("/api/benchmark/clean-logs", { method: "POST", body: {} });
      const removed = data.removed != null ? data.removed : "?";
      setStatus(`Cleaned session logs (${removed} items removed).`);
      if (window.Workspace && typeof window.Workspace.refreshInventory === "function") {
        window.Workspace.refreshInventory();
      }
    } catch (err) {
      setStatus(err.message || String(err), true);
    }
  }

  function verifyHost() {
    return ($("bench-remote-host").value || "").trim() || "";
  }

  function renderVerify(run) {
    const results = $("bench-verify-results");
    const logEl = $("bench-verify-log");
    const stopBtn = $("bench-verify-stop");
    const startBtn = $("bench-verify-targets");
    if (logEl) logEl.textContent = (run && run.log) || "";
    if (stopBtn) stopBtn.disabled = !(run && run.running);
    if (startBtn) startBtn.disabled = !!(run && run.running);
    if (!results) return;
    if (!run || !(run.results || []).length) {
      results.innerHTML = run && run.running ? `<div class="muted small">Testing…</div>` : "";
      return;
    }
    results.innerHTML = (run.results || [])
      .map((r) => {
        const klass = r.status || "unknown";
        return `<div class="bench-result-row status-${escapeHtml(klass)}">
          <span class="bench-result-name">${escapeHtml(r.id)} <span class="muted">:${r.port}</span></span>
          <span class="bench-result-status">${escapeHtml(klass)}</span>
          <span class="bench-result-meta muted">${escapeHtml((r.detail || "").split("\n")[0])}</span>
        </div>`;
      })
      .join("");
    if (!run.running && run.summary) {
      const s = run.summary;
      const fail = (s.failed_ids || []).join(", ") || "none";
      const flagged = (s.flagged_ids || []).join(", ") || "none";
      setStatus(
        `Verify done — pass=${s.pass || 0} fail=${s.fail || 0} flagged=${s.flagged_no_root || 0}. Failed: ${fail}. Flagged: ${flagged}`,
        (s.fail || 0) > 0
      );
    }
  }

  let verifyPoll = null;
  async function refreshVerify() {
    try {
      const data = await api("/api/benchmark/verify/status");
      renderVerify(data.run);
      if (data.running) {
        if (!verifyPoll) verifyPoll = setInterval(refreshVerify, 1500);
      } else if (verifyPoll) {
        clearInterval(verifyPoll);
        verifyPoll = null;
      }
    } catch (err) {
      /* ignore poll errors while modal closed */
    }
  }

  async function startVerify() {
    const targetIds = selectedTargetIds();
    if (!targetIds.length) {
      setStatus("Select at least one target to test.", true);
      return;
    }
    const host = verifyHost();
    if (!host) {
      setStatus("Enter the remote lab host / IP first.", true);
      return;
    }
    setStatus(`Testing ${targetIds.length} target(s) on ${host}…`);
    try {
      await api("/api/benchmark/verify", {
        method: "POST",
        body: {
          host,
          target_ids: targetIds,
        },
      });
      await refreshVerify();
      if (!verifyPoll) verifyPoll = setInterval(refreshVerify, 1500);
    } catch (err) {
      setStatus(err.message || String(err), true);
    }
  }

  async function stopVerify() {
    try {
      await api("/api/benchmark/verify/stop", { method: "POST", body: {} });
      await refreshVerify();
    } catch (err) {
      setStatus(err.message || String(err), true);
    }
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function copyRunLog() {
    const logEl = $("bench-log");
    const btn = $("bench-copy-log");
    const text = (logEl && logEl.textContent) || "";
    if (!text.trim()) {
      setStatus("Nothing to copy yet.", true);
      return;
    }
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.setAttribute("readonly", "");
        ta.style.position = "fixed";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      setStatus("Run log copied.");
      if (btn) {
        btn.classList.add("is-copied");
        const icon = btn.querySelector("i");
        if (icon) {
          icon.classList.remove("fa-copy");
          icon.classList.add("fa-check");
        }
        window.setTimeout(() => {
          btn.classList.remove("is-copied");
          if (icon) {
            icon.classList.remove("fa-check");
            icon.classList.add("fa-copy");
          }
        }, 1200);
      }
    } catch (err) {
      setStatus(err.message || "Copy failed", true);
    }
  }

  function bind() {
    document.querySelectorAll("[data-bench-close]").forEach((el) => {
      el.addEventListener("click", closeModal);
    });
    const timeout = $("bench-timeout");
    if (timeout) {
      timeout.addEventListener("input", () => {
        timeout.dataset.touched = "1";
      });
    }
    const runs = $("bench-runs");
    if (runs) {
      runs.addEventListener("input", () => {
        runs.dataset.touched = "1";
      });
    }
    const toolList = $("bench-tool-list");
    if (toolList) {
      toolList.addEventListener("change", () => {
        toolList.dataset.userTouched = "1";
      });
    }
    const targetList = $("bench-target-list");
    if (targetList) {
      targetList.addEventListener("change", () => {
        targetList.dataset.userTouched = "1";
        updateSelectedPortsLabel();
        syncTargetProfileSelector();
      });
    }
    const targetProfile = $("bench-target-profile");
    if (targetProfile) {
      targetProfile.addEventListener("change", () => {
        if (targetProfile.value === "all") {
          setTargetIds(knownTargets.map((target) => target.id));
        } else if (targetProfile.value === "none") {
          setTargetIds([]);
        } else if (targetProfile.value.startsWith("profile:")) {
          const profileId = targetProfile.value.slice("profile:".length);
          const profile = knownProfiles.find((item) => item.id === profileId);
          if (profile) setTargetIds(profile.target_ids || []);
        }
      });
    }
    const start = $("bench-start");
    const stop = $("bench-stop");
    const cleanBtn = $("bench-clean-logs");
    const openBtn = $("btn-benchmark");
    const testBtn = $("bench-test-remote");
    const verifyBtn = $("bench-verify-targets");
    const verifyStop = $("bench-verify-stop");
    const copyLog = $("bench-copy-log");
    if (start) start.addEventListener("click", startBenchmark);
    if (stop) stop.addEventListener("click", stopBenchmark);
    if (cleanBtn) cleanBtn.addEventListener("click", cleanLogs);
    if (openBtn) openBtn.addEventListener("click", openModal);
    if (testBtn) testBtn.addEventListener("click", testRemoteAccess);
    if (verifyBtn) verifyBtn.addEventListener("click", startVerify);
    if (verifyStop) verifyStop.addEventListener("click", stopVerify);
    if (copyLog) copyLog.addEventListener("click", copyRunLog);
  }

  window.BenchmarkUI = { open: openModal, close: closeModal, refresh };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})();
