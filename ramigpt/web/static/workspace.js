/**
 * RamiGPT multi-session workspace.
 */
(function () {
    const state = {
    inventory: { groups: [], sessions: [], recent_ids: [] },
    selectedId: null,
    filter: "",
    socket: null,
    joinedRooms: new Set(),
    fullAiRunningBySession: {},
    terminalLoadToken: 0,
    _socketHadDisconnect: false,
  };

  const $ = (id) => document.getElementById(id);

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

  function selected() {
    return state.inventory.sessions.find((s) => s.id === state.selectedId) || null;
  }

  function statusClass(status) {
    return status || "disconnected";
  }

  function formatLast(iso) {
    if (!iso) return "never";
    try {
      return new Date(iso).toLocaleString();
    } catch (_) {
      return iso;
    }
  }

  function ensureSocket() {
    if (state.socket) return state.socket;
    state.socket = io.connect(
      location.protocol + "//" + document.domain + ":" + location.port + "/get"
    );
    state.socket.on("connect", () => {
      // Rooms are dropped on reconnect; re-subscribe so emit_session reaches us again.
      const rooms = new Set(state.joinedRooms);
      if (state.selectedId) rooms.add(state.selectedId);
      state.joinedRooms.clear();
      rooms.forEach((id) => joinSessionRoom(id));
      // Catch up any lines missed while the socket was down (e.g. long AI waits).
      if (state.selectedId && state._socketHadDisconnect) {
        loadTerminalHistory(state.selectedId);
      }
      state._socketHadDisconnect = false;
    });
    state.socket.on("disconnect", () => {
      // Force joinSessionRoom to emit again after the next connect.
      state.joinedRooms.clear();
      state._socketHadDisconnect = true;
    });
    state.socket.on("message", (data) => {
      const sid = data.server_session_id;
      if (sid && state.selectedId && sid !== state.selectedId) return;
      const text = data.data == null ? "" : String(data.data);
      if (sid && /^\[Full AI\] finished\b/i.test(text)) {
        state.fullAiRunningBySession[sid] = false;
        updateFullAiButton();
      }
      addTerminalOutput(text, data.color || "#00ff00");
    });
    return state.socket;
  }

  function joinSessionRoom(sessionId) {
    if (!sessionId) return;
    const sock = ensureSocket();
    if (state.joinedRooms.has(sessionId)) return;
    sock.emit("join", { server_session_id: sessionId });
    state.joinedRooms.add(sessionId);
  }

  function addTerminalOutput(text, color) {
    const terminal = $("terminal");
    if (!terminal) return;
    const div = document.createElement("div");
    div.className = "output";
    const baseColor = color || "#00ff00";
    // Highlight "pwned!" in red so root wins are obvious in the scrollback.
    const parts = String(text ?? "").split(/(pwned!)/i);
    if (parts.length === 1) {
      div.style.color = baseColor;
      div.textContent = text;
    } else {
      parts.forEach((part) => {
        if (!part) return;
        const span = document.createElement("span");
        if (part.toLowerCase() === "pwned!") {
          span.style.color = "#ff0000";
          span.style.fontWeight = "700";
          span.style.fontSize = "1.25em";
        } else {
          span.style.color = baseColor;
        }
        span.textContent = part;
        div.appendChild(span);
      });
    }
    terminal.appendChild(div);
    terminal.scrollTop = terminal.scrollHeight;
  }

  function clearTerminal(placeholder) {
    const terminal = $("terminal");
    if (!terminal) return;
    terminal.innerHTML = "";
    if (placeholder !== false) {
      const div = document.createElement("div");
      div.className = "output muted";
      div.textContent =
        typeof placeholder === "string"
          ? placeholder
          : "* Awaiting connection. Output streams here.";
      terminal.appendChild(div);
    }
  }

  async function loadTerminalHistory(sessionId) {
    if (!sessionId) {
      clearTerminal();
      return;
    }
    const token = (state.terminalLoadToken = (state.terminalLoadToken || 0) + 1);
    try {
      const data = await api(`/api/sessions/${sessionId}/terminal?limit=800`);
      // Ignore stale responses (e.g. parallel selectSession / reconnect races).
      if (token !== state.terminalLoadToken || sessionId !== state.selectedId) return;
      const lines = data.lines || [];
      clearTerminal(false);
      if (!lines.length) {
        const sess = selected();
        const connected = sess && sess.status === "connected";
        clearTerminal(
          connected
            ? "[*] Connected — no prior scrollback in this run yet."
            : "* Awaiting connection. Output streams here."
        );
        return;
      }
      lines.forEach((line) => {
        addTerminalOutput(line.text, line.color || "#00ff00");
      });
    } catch (_) {
      if (token === state.terminalLoadToken && sessionId === state.selectedId) {
        clearTerminal();
      }
    }
  }

  function persistSelectedSession(id) {
    try {
      if (id) localStorage.setItem("ramigpt.selectedSessionId", id);
      else localStorage.removeItem("ramigpt.selectedSessionId");
    } catch (_) {}
  }

  function readPersistedSessionId() {
    try {
      return localStorage.getItem("ramigpt.selectedSessionId");
    } catch (_) {
      return null;
    }
  }

  function sessionPayloadExtras() {
    return { server_session_id: state.selectedId };
  }

  async function refreshInventory() {
    state.inventory = await api("/api/inventory");
    renderSidebar();
    renderLandingLists();
    if (state.selectedId) {
      const still = state.inventory.sessions.find((s) => s.id === state.selectedId);
      if (still) selectSession(still.id, { skipTerminalReload: true });
      else showLanding();
    }
  }

  function matchesFilter(sess) {
    const q = state.filter.trim().toLowerCase();
    if (!q) return true;
    return [sess.name, sess.host, sess.username, sess.environment]
      .join(" ")
      .toLowerCase()
      .includes(q);
  }

  function renderSessionItem(sess) {
    const li = document.createElement("li");
    li.className = "session-item" + (sess.id === state.selectedId ? " active" : "");
    li.draggable = true;
    li.dataset.id = sess.id;
    li.innerHTML = `
      <span class="dot ${statusClass(sess.status)}"></span>
      <div class="meta">
        <div class="name">${escapeHtml(sess.name)}</div>
        <div class="host">${escapeHtml(sess.host)}:${sess.port}</div>
      </div>`;
    li.addEventListener("click", () => selectSession(sess.id));
    li.addEventListener("dragstart", (e) => {
      e.dataTransfer.setData("text/session-id", sess.id);
    });
    return li;
  }

  function renderSidebar() {
    const fav = $("list-favorites");
    const recent = $("list-recent");
    const tree = $("groups-tree");
    fav.innerHTML = "";
    recent.innerHTML = "";
    tree.innerHTML = "";

    const sessions = state.inventory.sessions.filter(matchesFilter);
    const byId = Object.fromEntries(state.inventory.sessions.map((s) => [s.id, s]));

    sessions.filter((s) => s.favorite).forEach((s) => fav.appendChild(renderSessionItem(s)));
    (state.inventory.recent_ids || [])
      .map((id) => byId[id])
      .filter(Boolean)
      .filter(matchesFilter)
      .slice(0, 3)
      .forEach((s) => recent.appendChild(renderSessionItem(s)));

    (state.inventory.groups || []).forEach((group) => {
      const block = document.createElement("div");
      block.className = "group-block";
      const head = document.createElement("div");
      head.className = "group-head";
      head.textContent = group.name;
      head.dataset.groupId = group.id;
      head.addEventListener("dragover", (e) => {
        e.preventDefault();
        head.classList.add("drag-over");
      });
      head.addEventListener("dragleave", () => head.classList.remove("drag-over"));
      head.addEventListener("drop", async (e) => {
        e.preventDefault();
        head.classList.remove("drag-over");
        const sid = e.dataTransfer.getData("text/session-id");
        if (!sid) return;
        await api(`/api/sessions/${sid}/move`, {
          method: "POST",
          body: { group_id: group.id },
        });
        await refreshInventory();
      });
      const ul = document.createElement("ul");
      ul.className = "group-sessions";
      sessions
        .filter((s) => s.group_id === group.id)
        .forEach((s) => ul.appendChild(renderSessionItem(s)));
      block.appendChild(head);
      block.appendChild(ul);
      tree.appendChild(block);
    });
  }

  function renderLandingLists() {
    const byId = Object.fromEntries(state.inventory.sessions.map((s) => [s.id, s]));
    const recentEl = $("landing-recent");
    const favEl = $("landing-favorites");
    recentEl.innerHTML = "";
    favEl.innerHTML = "";

    (state.inventory.recent_ids || [])
      .map((id) => byId[id])
      .filter(Boolean)
      .slice(0, 3)
      .forEach((s) => {
        const li = document.createElement("li");
        li.textContent = `${s.name} · ${s.host}:${s.port}`;
        li.onclick = () => selectSession(s.id);
        recentEl.appendChild(li);
      });
    if (!recentEl.children.length) {
      recentEl.innerHTML = '<li class="muted">No recent sessions yet</li>';
    }

    state.inventory.sessions
      .filter((s) => s.favorite)
      .forEach((s) => {
        const li = document.createElement("li");
        li.textContent = `${s.name} · ${s.host}:${s.port}`;
        li.onclick = () => selectSession(s.id);
        favEl.appendChild(li);
      });
    if (!favEl.children.length) {
      favEl.innerHTML = '<li class="muted">Star a session to pin it here</li>';
    }
  }

  function showLanding() {
    state.selectedId = null;
    persistSelectedSession(null);
    $("pane-landing").classList.remove("hidden");
    $("pane-session").classList.add("hidden");
    clearTerminal();
    renderSidebar();
  }

  function selectSession(id, opts = {}) {
    state.selectedId = id;
    const sess = selected();
    if (!sess) return showLanding();

    persistSelectedSession(id);
    $("pane-landing").classList.add("hidden");
    $("pane-session").classList.remove("hidden");
    renderSidebar();

    $("sess-name").textContent = sess.name;
    $("sess-host").textContent = `${sess.host}:${sess.port}`;
    $("sess-env").textContent = sess.environment || sess.group_id;
    $("sess-last").textContent = "Last connected: " + formatLast(sess.last_connected_at);
    updateStatusPill(sess.status || "disconnected");
    $("current-prompt").textContent = `${sess.username || "user"}@${sess.hostname || sess.name}:~$`;

    const connected = sess.status === "connected";
    setActionEnabled("disconnect", connected);
    setActionEnabled("reconnect", true);
    setActionEnabled("connect", !connected);
    $("command-field").disabled = !connected;
    updateFullAiButton();

    joinSessionRoom(id);
    loadPromptContext(id);
    if (!opts.skipTerminalReload) {
      loadTerminalHistory(id);
    }
  }

  function updateFullAiButton() {
    const fullAiBtn = $("action1");
    if (!fullAiBtn) return;
    const running = !!(state.selectedId && state.fullAiRunningBySession[state.selectedId]);
    fullAiBtn.textContent = running ? "Stop" : "Full AI";
  }

  async function loadPromptContext(sessionId) {
    if (!sessionId) {
      renderQueues({ facts: [], hints: [], avoids: [] });
      return;
    }
    try {
      const ctx = await api(`/api/sessions/${sessionId}/prompt-context`);
      renderQueues(ctx);
    } catch (err) {
      // Fall back to inventory snapshot if available
      const sess = selected();
      renderQueues({
        facts: (sess && sess.facts) || [],
        hints: (sess && sess.hints) || [],
        avoids: (sess && sess.avoids) || [],
      });
    }
  }

  function renderQueues(ctx) {
    const map = {
      queue1: ctx.facts || [],
      queue2: ctx.hints || [],
      queue3: ctx.avoids || [],
    };
    const endpoints = { queue1: "/fact", queue2: "/hint", queue3: "/avoid" };
    Object.keys(map).forEach((qid) => {
      const tbody = document.querySelector("#" + qid + " tbody");
      if (!tbody) return;
      tbody.innerHTML = "";
      map[qid].forEach((text) => {
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.textContent = text;
        td.title = "Click to remove";
        td.onclick = async () => {
          if (!state.selectedId) return;
          try {
            await api(endpoints[qid], {
              method: "DELETE",
              body: { text, ...sessionPayloadExtras() },
            });
            await loadPromptContext(state.selectedId);
          } catch (err) {
            alert(err.message);
          }
        };
        tr.appendChild(td);
        tbody.appendChild(tr);
      });
    });
  }

  function requireSelectedSession() {
    if (!state.selectedId) {
      alert("Select a session first.");
      return false;
    }
    return true;
  }

  function requireConnectedSession() {
    if (!requireSelectedSession()) return false;
    const sess = selected();
    if (!sess || sess.status !== "connected") {
      alert("Connect this session first — Full AI / Guide Me / BeRoot need a live SSH shell.");
      return false;
    }
    return true;
  }

  function updateStatusPill(status) {
    const el = $("sess-status");
    el.className = "status-pill " + statusClass(status);
    const label =
      status === "connected"
        ? "Connected"
        : status === "connecting"
          ? "Connecting"
          : status === "error"
            ? "Error"
            : "Disconnected";
    el.innerHTML = `<i class="dot"></i> ${label}`;
  }

  function setActionEnabled(action, enabled) {
    document
      .querySelectorAll(`[data-action="${action}"]`)
      .forEach((btn) => (btn.disabled = !enabled));
  }

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /* ---- Session modal ---- */
  function openSessionModal(existing) {
    const modal = $("session-modal");
    $("session-modal-title").textContent = existing ? "Edit Session" : "New Session";
    $("sf-id").value = existing ? existing.id : "";
    $("sf-name").value = existing ? existing.name : "";
    $("sf-host").value = existing ? existing.host : "10.10.1.109";
    $("sf-port").value = existing ? existing.port : 2224;
    $("sf-username").value = existing ? existing.username : "";
    $("sf-password").value = "";
    $("sf-password").placeholder = existing && existing.has_saved_password
      ? "•••••••• (leave blank to keep saved)"
      : "Password";
    $("sf-remember").checked = existing ? existing.remember_credentials !== false : true;
    $("sf-hostname").value = existing ? existing.hostname || "pehost" : "pehost";
    $("sf-favorite").checked = existing ? !!existing.favorite : false;
    $("sf-notes").value = existing ? existing.notes || "" : "";
    $("sf-env").value = existing ? existing.environment || "development" : "development";

    const groupSel = $("sf-group");
    groupSel.innerHTML = "";
    (state.inventory.groups || []).forEach((g) => {
      const opt = document.createElement("option");
      opt.value = g.id;
      opt.textContent = g.name;
      groupSel.appendChild(opt);
    });
    groupSel.value = existing ? existing.group_id : "development";
    $("sf-status").textContent = "";
    modal.classList.add("open");
    modal.setAttribute("aria-hidden", "false");
  }

  function closeSessionModal() {
    const modal = $("session-modal");
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
  }

  async function saveSessionForm(e) {
    e.preventDefault();
    const id = $("sf-id").value;
    const payload = {
      name: $("sf-name").value.trim(),
      host: $("sf-host").value.trim(),
      port: parseInt($("sf-port").value, 10) || 22,
      username: $("sf-username").value.trim(),
      hostname: $("sf-hostname").value.trim(),
      group_id: $("sf-group").value,
      environment: $("sf-env").value,
      favorite: $("sf-favorite").checked,
      notes: $("sf-notes").value.trim(),
      remember_credentials: $("sf-remember").checked,
    };
    const pw = $("sf-password").value;
    if (pw) payload.password = pw;

    try {
      let result;
      if (id) {
        result = await api(`/api/sessions/${id}`, { method: "PUT", body: payload });
      } else {
        result = await api("/api/sessions", { method: "POST", body: payload });
      }
      closeSessionModal();
      await refreshInventory();
      if (result.session) selectSession(result.session.id);
    } catch (err) {
      $("sf-status").textContent = err.message;
    }
  }

  /* ---- Connect actions ---- */
  async function connectSelected(passwordOverride) {
    const sess = selected();
    if (!sess) return;
    updateStatusPill("connecting");
    setActionEnabled("connect", false);
    try {
      const body = {};
      if (passwordOverride) body.password = passwordOverride;
      const res = await api(`/api/sessions/${sess.id}/connect`, { method: "POST", body });
      joinSessionRoom(sess.id);
      await refreshInventory();
      selectSession(sess.id);
      switchTab("terminal");
      $("command-field").disabled = false;
      $("command-field").focus();
      return res;
    } catch (err) {
      updateStatusPill("error");
      setActionEnabled("connect", true);
      if (err.status === 400 && /password/i.test(err.message)) {
        const pw = prompt("Password required for " + sess.username + "@" + sess.host + ":");
        if (pw) return connectSelected(pw);
      }
      addTerminalOutput("[!] " + err.message, "#f85149");
      alert(err.message);
    }
  }

  async function disconnectSelected() {
    const sess = selected();
    if (!sess) return;
    await api(`/api/sessions/${sess.id}/disconnect`, { method: "POST", body: {} });
    await refreshInventory();
    selectSession(sess.id);
  }

  async function reconnectSelected() {
    const sess = selected();
    if (!sess) return;
    try {
      await api(`/api/sessions/${sess.id}/reconnect`, { method: "POST", body: {} });
      joinSessionRoom(sess.id);
      await refreshInventory();
      selectSession(sess.id);
      $("command-field").disabled = false;
    } catch (err) {
      alert(err.message);
    }
  }

  async function deleteSelected() {
    const sess = selected();
    if (!sess) return;
    if (!confirm(`Delete session “${sess.name}”?`)) return;
    await api(`/api/sessions/${sess.id}`, { method: "DELETE" });
    showLanding();
    await refreshInventory();
  }

  async function deleteAllLogs() {
    const ok = window.confirm(
      "Delete all folders under data/logs?\n\nThis removes session and benchmark logs, and clears debug.log / times.log. Inventory sessions and benchmark results are kept."
    );
    if (!ok) return;
    try {
      const data = await api("/api/logs/clean", { method: "POST", body: {} });
      const removed = data.removed != null ? data.removed : "?";
      const msg = `Cleared data/logs (${removed} items).`;
      if (state.selectedId) {
        state.terminalLoadToken = (state.terminalLoadToken || 0) + 1;
        clearTerminal(false);
        try {
          await api(`/api/sessions/${state.selectedId}/terminal`, { method: "DELETE" });
        } catch (err) {
          addTerminalOutput("[!] Clear failed: " + err.message, "#f85149");
        }
        addTerminalOutput(`[+] ${msg}`, "#58a6ff");
      } else {
        alert(msg);
      }
    } catch (err) {
      alert(err.message || String(err));
    }
  }

  function switchTab(name) {
    document.querySelectorAll(".tab").forEach((t) => {
      t.classList.toggle("active", t.dataset.tab === name);
    });
    document.querySelectorAll(".tab-panel").forEach((p) => {
      p.classList.toggle("active", p.id === "tab-" + name);
    });
  }

  async function executeCommand(command) {
    if (!state.selectedId) return;
    const res = await api("/execute", {
      method: "POST",
      body: { command, ...sessionPayloadExtras() },
    });
    return res;
  }

  async function refreshMetrics() {
    const sess = selected();
    if (!sess || sess.status !== "connected") {
      alert("Connect the session first.");
      return;
    }
    const script =
      "echo CPU:$(grep 'cpu ' /proc/stat | awk '{u=$2+$4; t=$2+$4+$5; if (NR==1){u1=u;t1=t;} else print ($2+$4-u1)*100/($2+$4+$5-t1) \"%\";}');" +
      "free -m | awk '/Mem:/{printf \"MEM:%d%%\\n\", $3*100/$2}';" +
      "df -h / | awk 'NR==2{print \"DISK:\"$5}';" +
      "uptime -p 2>/dev/null || uptime";
    await executeCommand(script);
    // Parse latest terminal lines loosely — also set placeholders from a dedicated follow-up
    try {
      // Lightweight dedicated samples
      const samples = [
        { key: "CPU", cmd: "grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$4+$5)} END {printf \"%.0f%%\", usage}'" },
        { key: "Memory", cmd: "free | awk '/Mem:/{printf \"%.0f%%\", $3/$2*100}'" },
        { key: "Disk", cmd: "df -h / | awk 'NR==2{print $5}'" },
        { key: "Uptime", cmd: "uptime -p 2>/dev/null || cut -d' ' -f1 /proc/uptime" },
      ];
      // Show sampling notice; detailed parsing left to streamed output for now
      document.querySelectorAll("#metrics-grid .metric strong").forEach((el) => {
        el.textContent = "…";
      });
      for (const s of samples) {
        await executeCommand(`echo METRIC_${s.key}:$(${s.cmd})`);
      }
      addTerminalOutput("[*] Metric probes sent — values appear in the terminal stream.", "#58a6ff");
    } catch (err) {
      alert(err.message);
    }
  }

  /* ---- AI helpers (core RamiGPT features — scoped to selected session) ---- */
  async function guideMe() {
    if (!requireConnectedSession()) return;
    try {
      await executeCommand("");
    } catch (err) {
      alert(err.message);
    }
  }

  async function clearChat() {
    if (!requireSelectedSession()) return;
    const sessionId = state.selectedId;
    // Invalidate any in-flight history load so it cannot refill after clear.
    state.terminalLoadToken = (state.terminalLoadToken || 0) + 1;
    clearTerminal(false);
    try {
      await api(`/api/sessions/${sessionId}/terminal`, { method: "DELETE" });
    } catch (err) {
      addTerminalOutput("[!] Clear failed: " + err.message, "#f85149");
    }
  }

  const TOOL_API_IDS = {
    beRoot: "beroot",
    linEnum: "linenum",
    linPeas: "linpeas",
  };

  async function runTool() {
    if (!requireConnectedSession()) return;
    const tool = $("toolSelector").value;
    const withAi = !($("toolAiCheckbox") && !$("toolAiCheckbox").checked);
    const toolId = TOOL_API_IDS[tool];
    if (!toolId) {
      alert("Unknown tool: " + tool);
      return;
    }
    const sel = $("toolSelector");
    const toolName =
      sel && sel.selectedIndex >= 0
        ? sel.options[sel.selectedIndex].textContent.trim()
        : toolId;
    addTerminalOutput(
      `[${toolName}] Sending tool run to server…`,
      "#58a6ff"
    );
    try {
      await api("/action3", {
        method: "POST",
        body: {
          action: "start",
          ai: withAi,
          tool: toolId,
          ...sessionPayloadExtras(),
        },
      });
      addTerminalOutput(
        `[${toolName}] Request accepted — tool is being sent and executed on the remote host. Waiting for results…`,
        "#58a6ff"
      );
      if (withAi && state.selectedId) {
        state.fullAiRunningBySession[state.selectedId] = true;
        updateFullAiButton();
      }
    } catch (err) {
      addTerminalOutput(`[${toolName}] Tool run failed: ${err.message}`, "#f85149");
      alert(err.message);
    }
  }

  function wireQueues() {
    const map = {
      queue1: "/fact",
      queue2: "/hint",
      queue3: "/avoid",
    };
    Object.keys(map).forEach((qid) => {
      const input = $(qid + "-input");
      if (!input) return;
      input.addEventListener("keydown", async (e) => {
        if (e.key !== "Enter") return;
        const text = input.value.trim();
        if (!text) return;
        if (!requireSelectedSession()) return;
        try {
          await api(map[qid], {
            method: "POST",
            body: { text, ...sessionPayloadExtras() },
          });
          input.value = "";
          await loadPromptContext(state.selectedId);
        } catch (err) {
          alert(err.message);
        }
      });
    });
  }

  function importConfig() {
    if (!requireSelectedSession()) return;
    $("file-input").click();
  }

  function importConfigFile(input) {
    const file = input.files[0];
    if (!file) return;
    if (!requireSelectedSession()) return;
    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const config = JSON.parse(e.target.result);
        await api(`/api/sessions/${state.selectedId}/prompt-context`, {
          method: "PUT",
          body: {
            facts: config.facts || [],
            hints: config.hints || [],
            avoids: config.avoids || [],
          },
        });
        await loadPromptContext(state.selectedId);
        addTerminalOutput(
          "[*] Imported Facts/Hints/Avoid for this session",
          "#00ff00"
        );
      } catch (err) {
        alert("Invalid config: " + err.message);
      } finally {
        input.value = "";
      }
    };
    reader.readAsText(file);
  }

  async function exportConfig() {
    if (!requireSelectedSession()) return;
    try {
      const ctx = await api(`/api/sessions/${state.selectedId}/prompt-context`);
      const sess = selected();
      const blob = new Blob(
        [
          JSON.stringify(
            {
              session: sess ? sess.name : state.selectedId,
              facts: ctx.facts || [],
              hints: ctx.hints || [],
              avoids: ctx.avoids || [],
            },
            null,
            2
          ),
        ],
        { type: "application/json" }
      );
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = (sess ? sess.name : "session") + "-config.json";
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (err) {
      alert(err.message);
    }
  }

  /* ---- Wire UI ---- */
  document.addEventListener("DOMContentLoaded", async () => {
    ensureSocket();
    wireQueues();

    $("btn-new-session").onclick = () => openSessionModal(null);
    $("btn-landing-new").onclick = () => openSessionModal(null);
    $("session-search").addEventListener("input", (e) => {
      state.filter = e.target.value;
      renderSidebar();
    });

    $("session-form").addEventListener("submit", saveSessionForm);
    document.querySelectorAll("#session-modal [data-close]").forEach((el) => {
      el.addEventListener("click", closeSessionModal);
    });

    document.getElementById("quick-actions").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-action]");
      if (!btn || btn.disabled) return;
      const action = btn.dataset.action;
      if (action === "connect") connectSelected();
      if (action === "disconnect") disconnectSelected();
      if (action === "reconnect") reconnectSelected();
      if (action === "open-terminal") switchTab("terminal");
      if (action === "edit") openSessionModal(selected());
      if (action === "delete") deleteSelected();
    });

    const deleteLogsBtn = $("btn-delete-logs");
    if (deleteLogsBtn) deleteLogsBtn.addEventListener("click", () => deleteAllLogs());

    document.querySelectorAll("#session-tabs .tab").forEach((tab) => {
      tab.addEventListener("click", () => switchTab(tab.dataset.tab));
    });

    document.querySelectorAll('#tab-settings [data-action="edit"]').forEach((btn) => {
      btn.addEventListener("click", () => openSessionModal(selected()));
    });

    $("btn-refresh-metrics").onclick = refreshMetrics;

    const cmd = $("command-field");
    cmd.addEventListener("keydown", async (e) => {
      if (e.key !== "Enter") return;
      const command = cmd.value.trim();
      cmd.value = "";
      if (!command) return;
      try {
        await executeCommand(command);
      } catch (err) {
        addTerminalOutput("[!] " + err.message, "#f85149");
      }
    });

    const fullAiBtn = $("action1");
    fullAiBtn.addEventListener("click", async () => {
      if (!requireConnectedSession()) return;
      const sid = state.selectedId;
      const running = !!state.fullAiRunningBySession[sid];
      try {
        await api("/action1", {
          method: running ? "DELETE" : "POST",
          body: { action: running ? "stop" : "start", ...sessionPayloadExtras() },
        });
        state.fullAiRunningBySession[sid] = !running;
        updateFullAiButton();
      } catch (err) {
        alert(err.message);
      }
    });

    try {
      await refreshInventory();
      const savedId = readPersistedSessionId();
      const stillThere =
        savedId &&
        state.inventory.sessions.some((s) => s.id === savedId);
      if (stillThere) {
        selectSession(savedId);
        switchTab("terminal");
      } else {
        showLanding();
      }
    } catch (err) {
      console.error(err);
      addTerminalOutput?.("[!] Failed to load inventory: " + err.message);
    }
  });

  window.Workspace = {
    showLanding,
    selectSession,
    refreshInventory,
    guideMe,
    clearChat,
    runTool,
    importConfig,
    importConfigFile,
    exportConfig,
    openSessionModal,
  };
})();
