/**
 * Privilege-escalation benchmark UI.
 */
(function () {
  const $ = (id) => document.getElementById(id);
  let pollTimer = null;

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

  function mode() {
    const checked = document.querySelector('input[name="bench-mode"]:checked');
    return checked ? checked.value : "local";
  }

  function syncModeUI() {
    const remote = $("bench-remote-fields");
    if (remote) remote.hidden = mode() !== "remote";
  }

  function openModal() {
    const modal = $("benchmark-modal");
    if (!modal) return;
    modal.classList.add("open");
    modal.setAttribute("aria-hidden", "false");
    syncModeUI();
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

  function startPolling() {
    stopPolling();
    pollTimer = setInterval(() => {
      refresh().catch(() => {});
    }, 1500);
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
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

  function setAllTargets(checked) {
    const list = $("bench-target-list");
    if (!list) return;
    list.dataset.userTouched = "1";
    list.querySelectorAll("input[data-target-id]").forEach((el) => {
      el.checked = !!checked;
    });
  }

  function renderTargets(targets, defaults) {
    const list = $("bench-target-list");
    if (!list) return;
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
        return `<li>
          <label class="bench-tool-check">
            <input type="checkbox" data-target-id="${escapeHtml(t.id)}" ${checked ? "checked" : ""}>
            <span>
              <strong>${escapeHtml(t.name)}</strong>
              <small>SSH :${t.port} · sudo ${escapeHtml(t.sudo_binary)} — ${escapeHtml(t.description || "")}</small>
            </span>
          </label>
        </li>`;
      })
      .join("");

    if (defaults) {
      if ($("bench-cred-user")) $("bench-cred-user").textContent = defaults.username || "lowpriv";
      if ($("bench-cred-pass")) $("bench-cred-pass").textContent = defaults.password || "password";
      if ($("bench-cred-ports"))
        $("bench-cred-ports").textContent = (defaults.ports || []).join(", ");
    }
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
        results.innerHTML = `<div class="muted small">No run yet. Configure AI, pick local/remote, then Start.</div>`;
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

  async function refresh() {
    const data = await api("/api/benchmark/status");
    if (!$("bench-target-list")?.dataset.userTouched) {
      renderTargets(data.targets, data.defaults);
    } else if (data.defaults) {
      if ($("bench-cred-user")) $("bench-cred-user").textContent = data.defaults.username || "lowpriv";
      if ($("bench-cred-pass")) $("bench-cred-pass").textContent = data.defaults.password || "password";
      if ($("bench-cred-ports"))
        $("bench-cred-ports").textContent = (data.defaults.ports || []).join(", ");
    }
    if (!$("bench-tool-list")?.dataset.userTouched) {
      renderTools(data.available_tools, data.defaults);
    }
    applyRemotePreset(data.remote_preset);
    renderRun(data.run, data.running, data.batch);
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
    if (preset.config_exists && preset.host) {
      const remoteRadio = document.querySelector('input[name="bench-mode"][value="remote"]');
      if (remoteRadio && !document.querySelector('input[name="bench-mode"]:checked')?.dataset.userPicked) {
        remoteRadio.checked = true;
        syncModeUI();
      }
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
      mode: mode(),
      timeout_seconds: parseInt($("bench-timeout").value, 10) || 180,
      repetitions: Math.max(1, Math.min(50, parseInt($("bench-runs")?.value, 10) || 1)),
      tools: selectedTools(),
      target_ids: targetIds,
    };
    if (payload.mode === "remote") {
      payload.remote = {
        host: ($("bench-remote-host").value || "").trim(),
        port: parseInt($("bench-remote-port").value, 10) || 22,
        username: ($("bench-remote-user").value || "").trim(),
        password: $("bench-remote-pass").value || "",
      };
      // Empty password falls back to data/benchmark/remote.json on the server.
    }
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

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function bind() {
    document.querySelectorAll("[data-bench-close]").forEach((el) => {
      el.addEventListener("click", closeModal);
    });
    document.querySelectorAll('input[name="bench-mode"]').forEach((el) => {
      el.addEventListener("change", () => {
        el.dataset.userPicked = "1";
        syncModeUI();
      });
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
      });
    }
    const selectAll = $("bench-targets-all");
    const selectNone = $("bench-targets-none");
    if (selectAll) selectAll.addEventListener("click", () => setAllTargets(true));
    if (selectNone) selectNone.addEventListener("click", () => setAllTargets(false));
    const start = $("bench-start");
    const stop = $("bench-stop");
    const cleanBtn = $("bench-clean-logs");
    const openBtn = $("btn-benchmark");
    const testBtn = $("bench-test-remote");
    if (start) start.addEventListener("click", startBenchmark);
    if (stop) stop.addEventListener("click", stopBenchmark);
    if (cleanBtn) cleanBtn.addEventListener("click", cleanLogs);
    if (openBtn) openBtn.addEventListener("click", openModal);
    if (testBtn) testBtn.addEventListener("click", testRemoteAccess);
  }

  window.BenchmarkUI = { open: openModal, close: closeModal, refresh };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})();
