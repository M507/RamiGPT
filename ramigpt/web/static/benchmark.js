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

  function renderTargets(targets, defaults) {
    const list = $("bench-target-list");
    if (!list) return;
    list.innerHTML = (targets || [])
      .map(
        (t) => `<li>
          <strong>${escapeHtml(t.name)}</strong>
          <span class="muted">SSH :${t.port} · sudo ${escapeHtml(t.sudo_binary)}</span>
          <div class="muted small">${escapeHtml(t.description || "")}</div>
        </li>`
      )
      .join("");
    if (defaults) {
      if ($("bench-cred-user")) $("bench-cred-user").textContent = defaults.username || "zeus";
      if ($("bench-cred-pass")) $("bench-cred-pass").textContent = defaults.password || "benchmark";
      if ($("bench-cred-ports"))
        $("bench-cred-ports").textContent = (defaults.ports || []).join(", ");
      if ($("bench-timeout") && !document.activeElement?.id?.startsWith("bench-")) {
        // only set default when idle field not focused
      }
    }
  }

  function phaseLabel(phase) {
    return phase || "idle";
  }

  function renderRun(run, running) {
    const phaseEl = $("bench-phase");
    const results = $("bench-results");
    const logEl = $("bench-log");
    const startBtn = $("bench-start");
    const stopBtn = $("bench-stop");

    if (phaseEl) {
      phaseEl.className = "status-pill " + (run ? run.phase : "idle");
      phaseEl.innerHTML = `<i class="dot"></i> ${phaseLabel(run ? run.phase : "Idle")}`;
    }

    if (results) {
      if (!run || !(run.targets || []).length) {
        results.innerHTML = `<div class="muted small">No run yet. Configure AI, pick local/remote, then Start.</div>`;
      } else {
        results.innerHTML = run.targets
          .map((t) => {
            const klass = t.status || "pending";
            const elapsed = t.elapsed_seconds != null ? `${t.elapsed_seconds}s` : "—";
            return `<div class="bench-result-row status-${escapeHtml(klass)}">
              <span class="bench-result-name">${escapeHtml(t.name)} <span class="muted">:${t.port}</span></span>
              <span class="bench-result-status">${escapeHtml(klass)}</span>
              <span class="bench-result-meta muted">${escapeHtml(elapsed)} ${escapeHtml(t.message || "")}</span>
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

    if (run && run.error) setStatus(run.error, true);
  }

  async function refresh() {
    const data = await api("/api/benchmark/status");
    renderTargets(data.targets, data.defaults);
    if (!$("bench-tool-list")?.dataset.userTouched) {
      renderTools(data.available_tools, data.defaults);
    }
    applyRemotePreset(data.remote_preset);
    renderRun(data.run, data.running);
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
    const payload = {
      mode: mode(),
      timeout_seconds: parseInt($("bench-timeout").value, 10) || 180,
      tools: selectedTools(),
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
      setStatus("Benchmark started…");
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
    const toolList = $("bench-tool-list");
    if (toolList) {
      toolList.addEventListener("change", () => {
        toolList.dataset.userTouched = "1";
      });
    }
    const start = $("bench-start");
    const stop = $("bench-stop");
    const openBtn = $("btn-benchmark");
    const testBtn = $("bench-test-remote");
    if (start) start.addEventListener("click", startBenchmark);
    if (stop) stop.addEventListener("click", stopBenchmark);
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
