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
  const PLAN_PROVIDERS = [
    { id: "ollama", label: "Ollama" },
    { id: "openai", label: "OpenAI" },
    { id: "openwebui", label: "Open WebUI" },
    { id: "cursor", label: "Cursor" },
  ];
  const MAX_PLAN_ENTRIES = 10;
  const MAX_TOTAL_RUNS = 50;
  /** @type {Record<string, string[]>} */
  const modelListCache = {};
  /** @type {Record<string, string>} */
  let savedModelsByProvider = {};
  let currentAiProvider = "ollama";
  /** @type {string[]} */
  let knownRoles = [];
  let currentAiRole = "";
  let lastLoggedIssueKey = "";

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

  function syncAdvancedControls(advancedMode) {
    const resetBtn = $("bench-reset-results");
    if (!resetBtn) return;
    const enabled = !!Number(advancedMode);
    resetBtn.hidden = !enabled;
    if (!enabled) resetBtn.disabled = true;
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
      {
        id: "linenum",
        name: "LinEnum",
        description: "Run LinEnum.sh (-t), then Full AI uses findings until root",
        default: false,
      },
      {
        id: "linpeas",
        name: "LinPEAS",
        description: "Run linpeas.sh (fast mode, -P), then Full AI uses findings until root",
        default: false,
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

  function enabledToolIds(tools) {
    if (Array.isArray(tools)) {
      return tools.filter(Boolean);
    }
    if (!tools || typeof tools !== "object") {
      return [];
    }
    return Object.keys(tools).filter((id) => tools[id]);
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
    const groupOrder = ["Quick runs", "Themed runs", "Full families"];
    const grouped = new Map();
    knownProfiles.forEach((profile) => {
      const label = profile.group || "Profiles";
      if (!grouped.has(label)) grouped.set(label, []);
      grouped.get(label).push(profile);
    });
    const orderedGroups = [
      ...groupOrder.filter((label) => grouped.has(label)),
      ...[...grouped.keys()].filter((label) => !groupOrder.includes(label)),
    ];
    const profileOptions = orderedGroups
      .map(
        (label) => `<optgroup label="${escapeHtml(label)}">
        ${(grouped.get(label) || [])
          .map(
            (profile) =>
              `<option value="profile:${escapeHtml(profile.id)}">${escapeHtml(profile.name)} (${(profile.target_ids || []).length})</option>`
          )
          .join("")}
      </optgroup>`
      )
      .join("");
    select.innerHTML = `
      <option value="all">Select all (${knownTargets.length || "285"})</option>
      <option value="none">None</option>
      ${profileOptions}
      <option value="custom" hidden>Custom selection</option>`;
    syncTargetProfileSelector();
  }

  function selectedTargetProfileId() {
    const select = $("bench-target-profile");
    if (!select || !select.value.startsWith("profile:")) return "";
    return select.value.slice("profile:".length);
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
    const labels = {
      idle: "Idle",
      queued: "Queued",
      deploying: "Preparing",
      running: "Running",
      stopping: "Stopping",
      done: "Done",
      error: "Error",
    };
    return labels[(phase || "idle").toLowerCase()] || phase || "Idle";
  }

  function truncateText(text, maxLen) {
    const value = String(text || "").trim();
    if (value.length <= maxLen) return value;
    return `${value.slice(0, maxLen - 1)}…`;
  }

  function timelineHas(timeline, phase) {
    return (timeline || []).some((entry) => entry.phase === phase);
  }

  function logBenchmarkDiagnostics(run) {
    if (!run) {
      lastLoggedIssueKey = "";
      return;
    }
    const issues = [...(run.issues || [])];
    (run.targets || []).forEach((target) => {
      (target.issues || []).forEach((issue) => issues.push(issue));
    });
    if (!issues.length) {
      lastLoggedIssueKey = "";
      return;
    }
    const key = issues.join("\n");
    if (key === lastLoggedIssueKey) return;
    lastLoggedIssueKey = key;
    console.group("[benchmark] diagnostics");
    issues.forEach((issue) => console.warn(issue));
    console.groupEnd();
  }

  function describeTargetActivity(target, toolIds) {
    const status = (target.status || "pending").toLowerCase();
    const timeline = target.timeline || [];
    const aiTurns = target.ai_turns || [];
    const toolRuns = target.tool_runs || [];
    const lastEntry = timeline.length ? timeline[timeline.length - 1] : null;
    const lastPhase = lastEntry && lastEntry.phase;

    if (status === "passed") {
      return { pct: 100, label: "Root achieved" };
    }
    if (status === "failed") {
      return { pct: 100, label: target.message || "Finished without root" };
    }
    if (status === "error") {
      return { pct: 100, label: target.message || "Target error" };
    }
    if (status === "skipped") {
      return { pct: 100, label: "Stopped by user" };
    }
    if (status === "pending") {
      return { pct: 4, label: "Waiting to start…" };
    }

    if (lastPhase === "ai_turn") {
      const req = lastEntry.request || aiTurns.length || 1;
      const cmd =
        lastEntry.command ||
        (aiTurns.length ? aiTurns[aiTurns.length - 1].command : "") ||
        "";
      return {
        pct: 78,
        label: cmd
          ? `Executing AI command #${req}: ${truncateText(cmd, 72)}`
          : `Executing AI command #${req}…`,
      };
    }

    if (lastPhase === "shell_io" || timelineHas(timeline, "full_ai_start")) {
      const nextReq = aiTurns.length + 1;
      return { pct: 58, label: `AI thinking — choosing command #${nextReq}…` };
    }

    if (timelineHas(timeline, "beroot") || toolRuns.some((run) => run.tool === "beroot")) {
      return { pct: 46, label: "BeRoot finished — starting Full AI…" };
    }

    if (toolIds.includes("linpeas")) {
      if (timelineHas(timeline, "linpeas_start") && !toolRuns.some((run) => run.tool === "linpeas")) {
        return { pct: 28, label: "Running LinPEAS scan…" };
      }
      if (toolRuns.some((run) => run.tool === "linpeas")) {
        return { pct: 46, label: "LinPEAS finished — starting Full AI…" };
      }
    }

    if (toolIds.includes("linenum")) {
      if (timelineHas(timeline, "linenum_start") && !toolRuns.some((run) => run.tool === "linenum")) {
        return { pct: 28, label: "Running LinEnum scan…" };
      }
      if (toolRuns.some((run) => run.tool === "linenum")) {
        return { pct: 46, label: "LinEnum finished — starting Full AI…" };
      }
    }

    if (toolIds.includes("beroot")) {
      if (timelineHas(timeline, "beroot_start") || !toolRuns.length) {
        return { pct: 24, label: "Running BeRoot scan…" };
      }
    }

    if (timelineHas(timeline, "full_ai_requested") || timelineHas(timeline, "full_ai_start")) {
      return { pct: 50, label: "Starting Full AI…" };
    }

    if (status === "running") {
      return { pct: 12, label: "Connecting to target…" };
    }

    return { pct: 8, label: "Starting target…" };
  }

  function describeSuiteActivity(run) {
    const phase = (run && run.phase) || "idle";
    const logTail = ((run && run.log) || []).slice(-20).join("\n").toLowerCase();

    if (phase === "deploying") {
      if (logTail.includes("warmup")) {
        return { pct: 8, label: "Warming up AI model…" };
      }
      if (logTail.includes("ansible deploy") || logTail.includes("deploying")) {
        return { pct: 12, label: "Deploying benchmark targets on lab host…" };
      }
      if (logTail.includes("port check") || logTail.includes("verifying benchmark ssh")) {
        return { pct: 10, label: "Checking target SSH ports…" };
      }
      return { pct: 6, label: "Preparing benchmark environment…" };
    }
    if (phase === "queued") {
      return { pct: 2, label: "Benchmark queued…" };
    }
    if (phase === "stopping") {
      return { pct: 99, label: "Stopping benchmark…" };
    }

    const targets = (run && run.targets) || [];
    if (!targets.length) {
      return { pct: 0, label: "Idle" };
    }

    const toolIds = enabledToolIds(run.tools);
    const activities = targets.map((target) => describeTargetActivity(target, toolIds));
    const finished = targets.filter((target) =>
      ["passed", "failed", "error", "skipped"].includes((target.status || "").toLowerCase())
    ).length;
    const avgPct =
      activities.reduce((sum, activity) => sum + activity.pct, 0) / Math.max(activities.length, 1);
    const suitePct = Math.round((finished / targets.length) * 100 * 0.35 + avgPct * 0.65);

    const activeTarget =
      targets.find((target) => (target.status || "").toLowerCase() === "running") ||
      targets.find(
        (target) => !["passed", "failed", "error", "skipped"].includes((target.status || "").toLowerCase())
      );

    if (activeTarget) {
      const active = describeTargetActivity(activeTarget, toolIds);
      const targetName = activeTarget.name || activeTarget.target_id || "Target";
      return {
        pct: Math.min(98, Math.max(suitePct, active.pct)),
        label: `${targetName}: ${active.label}`,
      };
    }

    if (finished === targets.length) {
      return { pct: 100, label: "All targets finished" };
    }

    return { pct: Math.min(98, suitePct), label: "Running benchmark…" };
  }

  function renderProgress(run, running) {
    const root = $("bench-progress");
    const fill = $("bench-progress-fill");
    const label = $("bench-progress-label");
    if (!root || !fill || !label) return;

    const active = running && run && !["done", "error"].includes((run.phase || "").toLowerCase());
    if (!active) {
      root.hidden = true;
      fill.style.width = "0%";
      label.textContent = "";
      return;
    }

    const activity = describeSuiteActivity(run);
    const pct = Math.max(0, Math.min(100, Math.round(activity.pct || 0)));
    root.hidden = false;
    fill.style.width = `${pct}%`;
    label.textContent = activity.label || "Running benchmark…";
    root.setAttribute("role", "progressbar");
    root.setAttribute("aria-valuemin", "0");
    root.setAttribute("aria-valuemax", "100");
    root.setAttribute("aria-valuenow", String(pct));
    root.setAttribute("aria-label", activity.label || "Benchmark progress");
  }

  function renderRun(run, running, batch, collabSave) {
    const phaseEl = $("bench-phase");
    const results = $("bench-results");
    const logEl = $("bench-log");
    const startBtn = $("bench-start");
    const stopBtn = $("bench-stop");

    if (phaseEl) {
      const phase = run ? run.phase : "idle";
      const reps = (batch && batch.repetitions) || (run && run.repetitions) || 1;
      const rep = (batch && batch.repetition) || (run && run.repetition) || 1;
      const modelProvider =
        (batch && batch.current_provider) || (run && run.provider) || "";
      const modelName = (batch && batch.current_model) || (run && run.model) || "";
      const modelSuffix =
        modelProvider || modelName
          ? ` · ${modelProvider || "?"}/${modelName || "?"}`
          : "";
      const roleName =
        (batch && batch.current_role) || (run && run.role_objective) || "";
      const roleSuffix = roleName ? ` · ${roleName}` : "";
      const repLabel = reps > 1 ? ` · run ${rep}/${reps}${modelSuffix}${roleSuffix}` : `${modelSuffix}${roleSuffix}`;
      phaseEl.className = "status-pill " + (run ? phase : "idle");
      phaseEl.innerHTML = `<i class="dot"></i> ${phaseLabel(run ? phase : "Idle")}${escapeHtml(repLabel)}`;
    }

    logBenchmarkDiagnostics(run);
    renderProgress(run, running);

    if (results) {
      if (!run || !(run.targets || []).length) {
        results.innerHTML = `<div class="muted small">No run yet. Configure AI and remote host, then Start.</div>`;

      } else {
        const modelLabel =
          run.provider || run.model
            ? `<div class="muted small">Model: ${escapeHtml(run.provider || "?")}/${escapeHtml(run.model || "?")}</div>`
            : "";
        const modelKeyLabel = run.model_key_name
          ? `<div class="muted small">Model key: <code>${escapeHtml(run.model_key_name)}</code></div>`
          : "";
        const profileLabel = run.profile_label
          ? `<div class="muted small">Model profile: ${escapeHtml(run.profile_label)}</div>`
          : "";
        const suiteProfileLabel = run.suite_profile_name
          ? `<div class="muted small">Target profile: ${escapeHtml(run.suite_profile_name)}</div>`
          : "";
        const hardware = run.hardware || {};
        const vramLabel =
          hardware.gpu_vram != null && hardware.gpu_vram !== ""
            ? `${/^\d+$/.test(String(hardware.gpu_vram)) ? `${hardware.gpu_vram} MiB` : hardware.gpu_vram}`
            : "";
        const hardwareBits = [];
        if (hardware.gpu_name) hardwareBits.push(String(hardware.gpu_name));
        if (vramLabel) hardwareBits.push(`VRAM ${vramLabel}`);
        if (hardware.gpu_driver && !hardwareBits.includes(String(hardware.gpu_driver))) {
          hardwareBits.push(String(hardware.gpu_driver));
        }
        if (hardware.cuda_version) hardwareBits.push(`CUDA ${hardware.cuda_version}`);
        const hardwareLabel =
          !run.profile_label && hardwareBits.length
            ? `<div class="muted small">Hardware: ${escapeHtml(hardwareBits.join(" · "))}</div>`
            : "";
        const roleLabel = run.role_objective
          ? `<div class="muted small">Role: ${escapeHtml(run.role_objective)}</div>`
          : "";
        const runToolIds = enabledToolIds(run.tools);
        const toolsLabel = runToolIds.length
          ? `<div class="muted small">Tools: ${escapeHtml(runToolIds.join(", "))}</div>`
          : "";
        const resultDir = run.result_dir
          ? `<div class="muted small">Results: <code>${escapeHtml(run.result_dir)}</code></div>`
          : collabSave && collabSave.pending
            ? `<div class="muted small">Collab results pending — click <strong>Save collab results</strong> to write under <code>data/benchmark/results/</code>.</div>`
            : "";
        results.innerHTML =
          modelLabel +
          modelKeyLabel +
          profileLabel +
          suiteProfileLabel +
          hardwareLabel +
          roleLabel +
          toolsLabel +
          resultDir +
          run.targets
            .map((t) => {
              const klass = t.status || "pending";
              const statusLower = klass.toLowerCase();
              const isActive = running && ["pending", "running", "deploying"].includes(statusLower);
              const activity = describeTargetActivity(t, runToolIds);
              const elapsed = t.elapsed_seconds != null ? `${t.elapsed_seconds}s` : "—";
              const cmds =
                t.ai_requests != null ? `${t.ai_requests} cmds` : "";
              const timing = t.timing_summary || {};
              const timingParts = [];
              if (timing.ai_llm_seconds != null) timingParts.push(`ai=${timing.ai_llm_seconds}s`);
              if (timing.shell_seconds != null) timingParts.push(`shell=${timing.shell_seconds}s`);
              if (timing.other_seconds != null) timingParts.push(`other=${timing.other_seconds}s`);
              const timingLine = timingParts.length
                ? `<div class="muted small bench-timing">${escapeHtml(timingParts.join(" · "))}</div>`
                : "";
              const activityLine =
                isActive && activity.label
                  ? `<div class="bench-result-activity">${escapeHtml(activity.label)}</div>`
                  : "";
              const aiLines = (t.ai_turns || [])
                .map((turn) => {
                  const llm = turn.llm_duration_seconds != null ? `${turn.llm_duration_seconds}s llm` : "— llm";
                  const shell =
                    turn.shell_duration_seconds != null ? `${turn.shell_duration_seconds}s shell` : "— shell";
                  const tok =
                    turn.total_tokens != null
                      ? `${turn.total_tokens} tok`
                      : "— tok";
                  return `<div class="muted small bench-ai-turn">#${turn.request}: ${escapeHtml(llm)} · ${escapeHtml(shell)} · ${escapeHtml(tok)} · <code>${escapeHtml(turn.command || "")}</code></div>`;
                })
                .join("");
              const toolLines = (t.tool_runs || [])
                .map((tool) => {
                  const dur = tool.duration_seconds != null ? `${tool.duration_seconds}s` : "—";
                  return `<div class="muted small bench-tool-run">${escapeHtml(tool.tool || "tool")}: ${escapeHtml(dur)}</div>`;
                })
                .join("");
              const metaParts = [];
              if (!isActive) metaParts.push(elapsed);
              if (cmds) metaParts.push(cmds);
              if (!isActive && t.message) metaParts.push(t.message);
              const meta = metaParts.filter(Boolean).join(" · ");
              return `<div class="bench-result-row status-${escapeHtml(klass)}">
              <span class="bench-result-name">${escapeHtml(t.name)} <span class="muted">:${t.port}</span></span>
              <span class="bench-result-status">${escapeHtml(klass)}</span>
              <span class="bench-result-meta muted">${escapeHtml(meta)}</span>
              ${activityLine}${timingLine}${toolLines}${aiLines}
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
    const resetBtn = $("bench-reset-results");
    if (resetBtn) resetBtn.disabled = !!running || resetBtn.hidden;
    const saveBtn = $("bench-save-collab");
    const pendingSave = !!(collabSave && collabSave.pending);
    if (saveBtn) {
      saveBtn.hidden = !pendingSave;
      saveBtn.disabled = !!running || !pendingSave;
    }

    if (run && run.error) setStatus(run.error, true);
  }

  function clampReps(value) {
    const n = parseInt(value, 10);
    if (!Number.isFinite(n)) return 1;
    return Math.max(1, Math.min(50, n));
  }

  function extraModelRows() {
    const root = $("bench-run-plan-extra");
    return root ? Array.from(root.querySelectorAll(".bench-run-plan-row")) : [];
  }

  function modelRepsEach() {
    return clampReps($("bench-primary-reps")?.value);
  }

  function modelCount() {
    return 1 + extraModelRows().length;
  }

  function modelRunsTotal() {
    return modelCount() * modelRepsEach();
  }

  function roleRepsEach() {
    return clampReps($("bench-primary-role-reps")?.value);
  }

  function roleCount() {
    return 1 + extraRoleRows().length;
  }

  function roleRunsTotal() {
    return roleCount() * roleRepsEach();
  }

  function countBatchSlots() {
    return modelRunsTotal() * roleRunsTotal();
  }

  function extraRoleRows() {
    const root = $("bench-role-plan-extra");
    return root ? Array.from(root.querySelectorAll(".bench-run-plan-row")) : [];
  }

  function updateRunPlanSummary() {
    const summary = $("bench-run-plan-summary");
    if (!summary) return;
    const models = modelCount();
    const repsEach = modelRepsEach();
    summary.textContent =
      models === 1 && repsEach === 1
        ? "1 model · 1 run"
        : `${models} model${models === 1 ? "" : "s"} · ${repsEach} run${repsEach === 1 ? "" : "s"} each`;
    updateBatchPlanSummary();
  }

  function updateRolePlanSummary() {
    const summary = $("bench-role-plan-summary");
    if (!summary) return;
    const roles = roleCount();
    const repsEach = roleRepsEach();
    summary.textContent =
      roles === 1 && repsEach === 1
        ? "1 role · 1 run"
        : `${roles} role${roles === 1 ? "" : "s"} · ${repsEach} run${repsEach === 1 ? "" : "s"} each`;
    updateBatchPlanSummary();
  }

  function updateBatchPlanSummary() {
    const total = countBatchSlots();
    const modelSummary = $("bench-run-plan-summary");
    const roleSummary = $("bench-role-plan-summary");
    if (total > MAX_TOTAL_RUNS) {
      const suffix = ` (batch total ${total} > ${MAX_TOTAL_RUNS})`;
      if (modelSummary && !modelSummary.textContent.includes("batch total")) {
        modelSummary.textContent += suffix;
      }
      if (roleSummary && !roleSummary.textContent.includes("batch total")) {
        roleSummary.textContent += suffix;
      }
    }
  }

  function collectRunPlan() {
    const primaryReps = modelRepsEach();
    const plan = [{ repetitions: primaryReps }];
    extraModelRows().forEach((row) => {
      const provider = (row.querySelector(".bench-plan-provider")?.value || "").trim();
      const model = (row.querySelector(".bench-plan-model")?.value || "").trim();
      const entry = {};
      if (provider) entry.provider = provider;
      if (model) entry.model = model;
      plan.push(entry);
    });
    return plan;
  }

  function collectRolePlan() {
    const primaryReps = roleRepsEach();
    const plan = [{ repetitions: primaryReps }];
    extraRoleRows().forEach((row) => {
      const role = (row.querySelector(".bench-plan-role")?.value || "").trim();
      const entry = {};
      if (role) entry.role = role;
      plan.push(entry);
    });
    return plan;
  }

  function roleOptions(selected) {
    const roles = knownRoles.length ? knownRoles : selected ? [selected] : [];
    if (selected && roles.indexOf(selected) === -1) {
      roles.unshift(selected);
    }
    if (!roles.length) {
      return `<option value="">Configure roles in App Settings</option>`;
    }
    return roles
      .map(
        (name) =>
          `<option value="${escapeHtml(name)}"${
            name === selected ? " selected" : ""
          }>${escapeHtml(name)}</option>`
      )
      .join("");
  }

  function addExtraRoleRow(preset) {
    const root = $("bench-role-plan-extra");
    const addBtn = $("bench-add-role-run");
    if (!root) return;
    if (1 + extraRoleRows().length >= MAX_PLAN_ENTRIES) {
      setStatus(`At most ${MAX_PLAN_ENTRIES} role entries in the role plan.`, true);
      return;
    }
    const role = (preset && preset.role) || currentAiRole || knownRoles[0] || "";
    const row = document.createElement("div");
    row.className = "bench-run-plan-row bench-run-plan-extra";
    row.innerHTML = `
      <label class="bench-run-plan-field bench-run-plan-model-field">Role
        <select class="bench-plan-role">${roleOptions(role)}</select>
      </label>
      <span class="bench-plan-spacer"></span>
      <button type="button" class="icon-btn bench-plan-remove" title="Remove role">&times;</button>`;
    root.appendChild(row);
    row.querySelector(".bench-plan-remove")?.addEventListener("click", () => {
      row.remove();
      root.dataset.userTouched = "1";
      updateRolePlanSummary();
      if (addBtn) addBtn.disabled = 1 + extraRoleRows().length >= MAX_PLAN_ENTRIES;
    });
    row.querySelectorAll("input, select").forEach((el) => {
      el.addEventListener("input", () => {
        root.dataset.userTouched = "1";
        updateRolePlanSummary();
      });
    });
    if (addBtn) addBtn.disabled = 1 + extraRoleRows().length >= MAX_PLAN_ENTRIES;
    updateRolePlanSummary();
  }

  function populateModelSelect(select, models, preferred) {
    if (!select) return;
    const fetched = Array.isArray(models) ? models.slice() : [];
    let list = fetched.slice();
    const keep = (preferred || select.value || "").trim();
    select.innerHTML = "";

    if (!list.length) {
      const opt = document.createElement("option");
      opt.value = keep;
      opt.textContent = keep
        ? `${keep} (saved — refresh to list)`
        : "No models — configure AI or refresh";
      select.appendChild(opt);
      select.value = keep;
      select.disabled = !keep;
      return;
    }

    if (keep && list.indexOf(keep) === -1) {
      list.unshift(keep);
    }

    list.forEach((id) => {
      const opt = document.createElement("option");
      opt.value = id;
      const notListed = fetched.length > 0 && fetched.indexOf(id) === -1;
      if (notListed) {
        opt.textContent = `${id} (saved)`;
      } else if (id === "default" || id === "auto") {
        opt.textContent = "Auto (account default)";
      } else {
        opt.textContent = id;
      }
      select.appendChild(opt);
    });
    select.disabled = false;
    select.value = keep && list.indexOf(keep) !== -1 ? keep : list[0];
  }

  async function fetchModelsForProvider(provider, { force = false } = {}) {
    const key = (provider || "").trim().toLowerCase();
    if (!key) return { models: [], saved_model: "" };
    if (!force && modelListCache[key]) {
      return { models: modelListCache[key], saved_model: savedModelsByProvider[key] || "" };
    }
    const data = await api("/api/benchmark/models", {
      method: "POST",
      body: { provider: key },
    });
    if (data.success && Array.isArray(data.models)) {
      modelListCache[key] = data.models;
    }
    if (data.saved_model) {
      savedModelsByProvider[key] = data.saved_model;
    }
    return {
      models: data.models || [],
      saved_model: data.saved_model || savedModelsByProvider[key] || "",
      error: data.success ? "" : data.error || "Could not load models",
    };
  }

  async function refreshRowModels(row, { force = true } = {}) {
    const provider = (row.querySelector(".bench-plan-provider")?.value || "").trim().toLowerCase();
    const select = row.querySelector(".bench-plan-model");
    const refreshBtn = row.querySelector(".bench-plan-refresh-models");
    if (!select || !provider) return;

    const preferred =
      (select.value || "").trim() ||
      (row.dataset.preferredModel || "").trim() ||
      savedModelsByProvider[provider] ||
      "";

    select.disabled = true;
    if (refreshBtn) refreshBtn.disabled = true;
    populateModelSelect(select, preferred ? [preferred] : [], preferred);

    try {
      const result = await fetchModelsForProvider(provider, { force });
      populateModelSelect(select, result.models, preferred || result.saved_model);
      if (result.error && force) {
        row.title = result.error;
      } else {
        row.title = "";
      }
    } catch (err) {
      populateModelSelect(select, preferred ? [preferred] : [], preferred);
      row.title = err.message || "Failed to load models";
    } finally {
      if (refreshBtn) refreshBtn.disabled = false;
    }
  }

  function wireRunPlanRow(row) {
    const root = $("bench-run-plan-extra");
    const providerSelect = row.querySelector(".bench-plan-provider");
    const refreshBtn = row.querySelector(".bench-plan-refresh-models");

    providerSelect?.addEventListener("change", () => {
      if (root) root.dataset.userTouched = "1";
      row.dataset.preferredModel = savedModelsByProvider[providerSelect.value] || "";
      refreshRowModels(row, { force: true }).catch(() => {});
    });

    refreshBtn?.addEventListener("click", () => {
      refreshRowModels(row, { force: true }).catch((err) => setStatus(err.message, true));
    });

    row.querySelectorAll("input, select").forEach((el) => {
      if (el.classList.contains("bench-plan-provider") || el.classList.contains("bench-plan-model")) {
        return;
      }
      el.addEventListener("input", () => {
        if (root) root.dataset.userTouched = "1";
        updateRunPlanSummary();
      });
    });
    row.querySelector(".bench-plan-model")?.addEventListener("change", () => {
      if (root) root.dataset.userTouched = "1";
    });
  }

  function providerOptions(selected) {
    return PLAN_PROVIDERS.map(
      (item) =>
        `<option value="${escapeHtml(item.id)}"${
          item.id === selected ? " selected" : ""
        }>${escapeHtml(item.label)}</option>`
    ).join("");
  }

  function addExtraModelRow(preset) {
    const root = $("bench-run-plan-extra");
    const addBtn = $("bench-add-model-run");
    if (!root) return;
    if (1 + extraModelRows().length >= MAX_PLAN_ENTRIES) {
      setStatus(`At most ${MAX_PLAN_ENTRIES} model entries in the run plan.`, true);
      return;
    }
    const provider = (preset && preset.provider) || currentAiProvider || "ollama";
    const model =
      (preset && preset.model) ||
      savedModelsByProvider[provider] ||
      "";
    const row = document.createElement("div");
    row.className = "bench-run-plan-row bench-run-plan-extra";
    row.innerHTML = `
      <label class="bench-run-plan-field">Provider
        <select class="bench-plan-provider">${providerOptions(provider)}</select>
      </label>
      <label class="bench-run-plan-field bench-run-plan-model-field">Model
        <div class="bench-model-picker">
          <select class="bench-plan-model" disabled><option value="">Loading…</option></select>
          <button type="button" class="icon-btn bench-plan-refresh-models" title="Refresh models">
            <i class="fas fa-sync-alt" aria-hidden="true"></i>
          </button>
        </div>
      </label>
      <span class="bench-plan-spacer"></span>
      <button type="button" class="icon-btn bench-plan-remove" title="Remove model">&times;</button>`;
    row.dataset.preferredModel = model;
    root.appendChild(row);
    wireRunPlanRow(row);
    row.querySelector(".bench-plan-remove")?.addEventListener("click", () => {
      row.remove();
      root.dataset.userTouched = "1";
      updateRunPlanSummary();
      if (addBtn) addBtn.disabled = 1 + extraModelRows().length >= MAX_PLAN_ENTRIES;
    });
    if (addBtn) addBtn.disabled = 1 + extraModelRows().length >= MAX_PLAN_ENTRIES;
    updateRunPlanSummary();
    refreshRowModels(row, { force: false }).catch(() => {});
  }

  function refreshRoleSelects() {
    extraRoleRows().forEach((row) => {
      const select = row.querySelector(".bench-plan-role");
      if (!select) return;
      const current = select.value;
      select.innerHTML = roleOptions(current);
    });
  }

  function renderAiSettings(ai) {
    const modelEl = $("bench-ai-model-label");
    const roleEl = $("bench-ai-role-label");
    if (ai) {
      if (ai.provider) currentAiProvider = ai.provider;
      if (ai.role_objective) currentAiRole = ai.role_objective;
      if (Array.isArray(ai.role_objective_options)) {
        knownRoles = ai.role_objective_options.slice();
      }
      if (ai.saved_models && typeof ai.saved_models === "object") {
        savedModelsByProvider = { ...ai.saved_models };
      }
    }
    if (modelEl) {
      if (!ai || (!ai.provider && !ai.model)) {
        modelEl.textContent = "AI Settings · —";
      } else {
        modelEl.textContent = `AI Settings · ${ai.provider || "?"} / ${ai.model || "?"}`;
      }
    }
    if (roleEl) {
      if (!ai || !ai.role_objective) {
        roleEl.textContent = "AI Settings · —";
      } else {
        roleEl.textContent = `AI Settings · ${ai.role_objective}`;
      }
    }
    refreshRoleSelects();
    updateRunPlanSummary();
    updateRolePlanSummary();
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
    syncAdvancedControls(data.ai_settings && data.ai_settings.advanced_mode);
    renderRun(data.run, data.running, data.batch, data.collab_save);
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
    if (!data.running) {
      updateRunPlanSummary();
      updateRolePlanSummary();
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
    const runPlan = collectRunPlan();
    const rolePlan = collectRolePlan();
    const totalSlots = countBatchSlots();
    if (totalSlots > MAX_TOTAL_RUNS) {
      setStatus(
        `Batch plan exceeds ${MAX_TOTAL_RUNS} total runs (model × role = ${totalSlots}).`,
        true
      );
      return;
    }
    const payload = {
      mode: "remote",
      timeout_seconds: parseInt($("bench-timeout").value, 10) || 180,
      run_plan: runPlan,
      role_plan: rolePlan,
      repetitions: modelRepsEach(),
      role_repetitions: roleRepsEach(),
      tools: selectedTools(),
      target_ids: targetIds,
      suite_profile_id: selectedTargetProfileId() || undefined,
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

  async function saveCollabResults() {
    setStatus("Saving collab results…");
    try {
      const data = await api("/api/benchmark/results/save", { method: "POST", body: {} });
      const count = data.run_count != null ? data.run_count : "?";
      const where = data.batch_dir || (data.paths && data.paths[0]) || "data/benchmark/results/";
      setStatus(`Saved ${count} collab result sheet(s) → ${where}`);
      await refresh();
    } catch (err) {
      setStatus(err.message || String(err), true);
    }
  }

  async function resetResults() {
    const ok = window.confirm(
      "Reset all benchmark results?\n\nThis deletes every result sheet under data/benchmark/results/, rebuilds an empty master.json, and resets the README stats section. Session logs are kept."
    );
    if (!ok) return;
    setStatus("Resetting benchmark results…");
    try {
      const data = await api("/api/benchmark/results/reset", { method: "POST", body: {} });
      const removed = data.removed != null ? data.removed : "?";
      setStatus(`Benchmark results reset (${removed} item(s) removed).`);
      await refresh();
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
    const primaryReps = $("bench-primary-reps");
    if (primaryReps) {
      primaryReps.addEventListener("input", () => {
        primaryReps.dataset.touched = "1";
        updateRunPlanSummary();
      });
    }
    const addModelBtn = $("bench-add-model-run");
    if (addModelBtn) {
      addModelBtn.addEventListener("click", () => addExtraModelRow());
    }
    const primaryRoleReps = $("bench-primary-role-reps");
    if (primaryRoleReps) {
      primaryRoleReps.addEventListener("input", () => {
        primaryRoleReps.dataset.touched = "1";
        updateRolePlanSummary();
      });
    }
    const addRoleBtn = $("bench-add-role-run");
    if (addRoleBtn) {
      addRoleBtn.addEventListener("click", () => addExtraRoleRow());
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
    const resetBtn = $("bench-reset-results");
    const saveBtn = $("bench-save-collab");
    const openBtn = $("btn-benchmark");
    const testBtn = $("bench-test-remote");
    const verifyBtn = $("bench-verify-targets");
    const verifyStop = $("bench-verify-stop");
    const copyLog = $("bench-copy-log");
    if (start) start.addEventListener("click", startBenchmark);
    if (stop) stop.addEventListener("click", stopBenchmark);
    if (cleanBtn) cleanBtn.addEventListener("click", cleanLogs);
    if (saveBtn) saveBtn.addEventListener("click", saveCollabResults);
    if (resetBtn) resetBtn.addEventListener("click", resetResults);
    if (openBtn) openBtn.addEventListener("click", openModal);
    if (testBtn) testBtn.addEventListener("click", testRemoteAccess);
    if (verifyBtn) verifyBtn.addEventListener("click", startVerify);
    if (verifyStop) verifyStop.addEventListener("click", stopVerify);
    if (copyLog) copyLog.addEventListener("click", copyRunLog);
    updateRunPlanSummary();
    updateRolePlanSummary();
  }

  function invalidateModelCache() {
    Object.keys(modelListCache).forEach((key) => {
      delete modelListCache[key];
    });
    extraModelRows().forEach((row) => {
      refreshRowModels(row, { force: true }).catch(() => {});
    });
  }

  window.BenchmarkUI = { open: openModal, close: closeModal, refresh, invalidateModelCache };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})();
