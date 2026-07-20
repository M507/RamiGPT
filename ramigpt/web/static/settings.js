/**
 * Settings modal — load / save / test AI provider configuration.
 */
(function () {
    const MASK_HINT = "...";
    const PROVIDER_GROUPS = ["openai", "ollama", "openwebui", "cursor"];

    let preferredOllamaModel = "";
    let ollamaModelsFetchSeq = 0;
    let preferredOpenWebUIModel = "";
    let openWebUIModelsFetchSeq = 0;
    let openWebUIApiKeySet = false;
    let preferredCursorModel = "";
    let cursorModelsFetchSeq = 0;
    let cursorApiKeySet = false;

    function $(id) {
        return document.getElementById(id);
    }

    function showStatus(message, isError) {
        const el = $("settings-status");
        if (!el) return;
        el.textContent = message;
        el.className = "settings-status" + (isError ? " error" : " success");
    }

    function setOllamaHint(message, isError) {
        const el = $("settings-ollama-models-hint");
        if (!el) return;
        el.textContent = message || "";
        el.className = "settings-hint" + (isError ? " error" : "");
    }

    function setOpenWebUIHint(message, isError) {
        const el = $("settings-openwebui-models-hint");
        if (!el) return;
        el.textContent = message || "";
        el.className = "settings-hint" + (isError ? " error" : "");
    }

    function setCursorHint(message, isError) {
        const el = $("settings-cursor-models-hint");
        if (!el) return;
        el.textContent = message || "";
        el.className = "settings-hint" + (isError ? " error" : "");
    }

    function toggleProviderFields(provider) {
        PROVIDER_GROUPS.forEach((name) => {
            document.querySelectorAll("[data-provider-group='" + name + "']").forEach((el) => {
                el.style.display = provider === name ? "" : "none";
            });
        });
        if (provider === "ollama") {
            refreshOllamaModels();
        }
        if (provider === "openwebui") {
            refreshOpenWebUIModels();
        }
        if (provider === "cursor") {
            refreshCursorModels();
        }
    }

    function populateOllamaModelSelect(models, selectedModel) {
        const select = $("settings-ollama-model");
        if (!select) return;

        const preferred = (selectedModel || preferredOllamaModel || "").trim();
        const list = Array.isArray(models) ? models.slice() : [];
        select.innerHTML = "";

        if (!list.length) {
            const opt = document.createElement("option");
            opt.value = preferred;
            opt.textContent = preferred
                ? preferred + " (host unreachable — keeping saved model)"
                : "No models available";
            select.appendChild(opt);
            select.value = preferred;
            select.disabled = !preferred;
            return;
        }

        if (preferred && list.indexOf(preferred) === -1) {
            list.unshift(preferred);
        }

        list.forEach((name) => {
            const opt = document.createElement("option");
            opt.value = name;
            opt.textContent = name === preferred && models.indexOf(name) === -1
                ? name + " (not on host)"
                : name;
            select.appendChild(opt);
        });
        select.disabled = false;
        select.value = preferred && list.indexOf(preferred) !== -1 ? preferred : list[0];
        preferredOllamaModel = select.value;
    }

    function populateOpenWebUIModelSelect(models, selectedModel) {
        const select = $("settings-openwebui-model");
        if (!select) return;

        const preferred = (selectedModel || preferredOpenWebUIModel || "").trim();
        const list = Array.isArray(models) ? models.slice() : [];
        select.innerHTML = "";

        if (!list.length) {
            const opt = document.createElement("option");
            opt.value = preferred;
            opt.textContent = preferred
                ? preferred + " (host unreachable — keeping saved model)"
                : "No models available";
            select.appendChild(opt);
            select.value = preferred;
            select.disabled = !preferred;
            return;
        }

        if (preferred && list.indexOf(preferred) === -1) {
            list.unshift(preferred);
        }

        list.forEach((name) => {
            const opt = document.createElement("option");
            opt.value = name;
            opt.textContent = name === preferred && models.indexOf(name) === -1
                ? name + " (not on host)"
                : name;
            select.appendChild(opt);
        });
        select.disabled = false;
        select.value = preferred && list.indexOf(preferred) !== -1 ? preferred : list[0];
        preferredOpenWebUIModel = select.value;
    }

    function populateCursorModelSelect(models, selectedModel, details) {
        const select = $("settings-cursor-model");
        if (!select) return;

        const preferred = (selectedModel || preferredCursorModel || "").trim();
        const detailMap = {};
        (Array.isArray(details) ? details : []).forEach((item) => {
            if (item && item.id) {
                detailMap[item.id] = item.displayName || item.id;
            }
        });

        const fetched = Array.isArray(models) ? models.slice() : [];
        let list = fetched.slice();
        if (!list.length && Array.isArray(details) && details.length) {
            list = details.map((item) => item.id).filter(Boolean);
        }

        select.innerHTML = "";

        if (!list.length) {
            const opt = document.createElement("option");
            opt.value = preferred;
            opt.textContent = preferred
                ? preferred + " (unavailable — keeping saved model)"
                : "No models available";
            select.appendChild(opt);
            select.value = preferred;
            select.disabled = !preferred;
            return;
        }

        if (preferred && list.indexOf(preferred) === -1) {
            list.unshift(preferred);
        }

        list.forEach((id) => {
            const opt = document.createElement("option");
            opt.value = id;
            const label = detailMap[id] || id;
            const notListed = fetched.length > 0 && fetched.indexOf(id) === -1;
            if (notListed) {
                opt.textContent = id + " (not listed)";
            } else if (id === "default" || id === "auto") {
                opt.textContent = label || "Auto (cheap / account default)";
            } else if (label && label !== id) {
                opt.textContent = label + " (" + id + ")";
            } else {
                opt.textContent = id;
            }
            select.appendChild(opt);
        });
        select.disabled = false;
        select.value = preferred && list.indexOf(preferred) !== -1 ? preferred : list[0];
        preferredCursorModel = select.value;
    }

    async function refreshCursorModels() {
        const select = $("settings-cursor-model");
        const refreshBtn = $("settings-cursor-refresh-models");
        const apiKeyInput = $("settings-cursor-api-key");
        const baseUrlInput = $("settings-cursor-base-url");
        if (!select) return;

        const apiKey = apiKeyInput ? apiKeyInput.value.trim() : "";
        const baseUrl = baseUrlInput ? baseUrlInput.value.trim() : "";
        const seq = ++cursorModelsFetchSeq;
        const keep = (select.value || preferredCursorModel || "").trim();
        preferredCursorModel = keep;

        if ((!apiKey || apiKey.includes(MASK_HINT)) && !cursorApiKeySet) {
            populateCursorModelSelect([], keep, []);
            setCursorHint("Enter an API key (or Save one) to load models from Cursor.", false);
            return;
        }

        select.disabled = true;
        if (refreshBtn) refreshBtn.disabled = true;
        setCursorHint("Loading models from Cursor…", false);

        try {
            const response = await fetch("/api/settings/cursor/models", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ cursor_api_key: apiKey, cursor_base_url: baseUrl }),
            });
            const data = await response.json();
            if (seq !== cursorModelsFetchSeq) return;

            if (!response.ok || !data.success) {
                populateCursorModelSelect([], keep, []);
                setCursorHint(
                    data.error || "Could not list models — keeping the saved model.",
                    true
                );
                return;
            }

            populateCursorModelSelect(data.models || [], keep, data.model_details || []);
            const count = (data.models || []).length;
            setCursorHint(
                count
                    ? "Loaded " + count + " model" + (count === 1 ? "" : "s") + " from Cursor."
                    : "Cursor responded but reported no models.",
                false
            );
        } catch (err) {
            if (seq !== cursorModelsFetchSeq) return;
            populateCursorModelSelect([], keep, []);
            setCursorHint(err.message || "Failed to load Cursor models.", true);
        } finally {
            if (seq === cursorModelsFetchSeq && refreshBtn) {
                refreshBtn.disabled = false;
            }
        }
    }

    async function refreshOpenWebUIModels() {
        const select = $("settings-openwebui-model");
        const refreshBtn = $("settings-openwebui-refresh-models");
        const apiKeyInput = $("settings-openwebui-api-key");
        const baseUrlInput = $("settings-openwebui-base-url");
        if (!select) return;

        const apiKey = apiKeyInput ? apiKeyInput.value.trim() : "";
        const baseUrl = baseUrlInput ? baseUrlInput.value.trim() : "";
        const seq = ++openWebUIModelsFetchSeq;
        const keep = (select.value || preferredOpenWebUIModel || "").trim();
        preferredOpenWebUIModel = keep;

        if ((!apiKey || apiKey.includes(MASK_HINT)) && !openWebUIApiKeySet) {
            populateOpenWebUIModelSelect([], keep);
            setOpenWebUIHint("Enter an API key (or Save one) to load models from Open WebUI.", false);
            return;
        }

        select.disabled = true;
        if (refreshBtn) refreshBtn.disabled = true;
        setOpenWebUIHint("Loading models from Open WebUI…", false);

        try {
            const response = await fetch("/api/settings/openwebui/models", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ openwebui_api_key: apiKey, openwebui_base_url: baseUrl }),
            });
            const data = await response.json();
            if (seq !== openWebUIModelsFetchSeq) return;

            if (!response.ok || !data.success) {
                populateOpenWebUIModelSelect([], keep);
                setOpenWebUIHint(
                    data.error || "Could not list models — keeping the saved model.",
                    true
                );
                return;
            }

            populateOpenWebUIModelSelect(data.models || [], keep);
            const count = (data.models || []).length;
            setOpenWebUIHint(
                count
                    ? "Loaded " + count + " model" + (count === 1 ? "" : "s") + " from " + (data.base_url || "Open WebUI") + "."
                    : "Open WebUI responded but reported no models.",
                false
            );
        } catch (err) {
            if (seq !== openWebUIModelsFetchSeq) return;
            populateOpenWebUIModelSelect([], keep);
            setOpenWebUIHint(err.message || "Failed to load Open WebUI models.", true);
        } finally {
            if (seq === openWebUIModelsFetchSeq && refreshBtn) {
                refreshBtn.disabled = false;
            }
        }
    }

    async function refreshOllamaModels() {
        const select = $("settings-ollama-model");
        const refreshBtn = $("settings-ollama-refresh-models");
        const baseUrlInput = $("settings-ollama-base-url");
        if (!select || !baseUrlInput) return;

        const baseUrl = baseUrlInput.value.trim();
        const seq = ++ollamaModelsFetchSeq;
        const keep = (select.value || preferredOllamaModel || "").trim();
        preferredOllamaModel = keep;

        select.disabled = true;
        if (refreshBtn) refreshBtn.disabled = true;
        setOllamaHint("Loading models from Ollama…", false);

        try {
            const response = await fetch("/api/settings/ollama/models", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ollama_base_url: baseUrl }),
            });
            const data = await response.json();
            if (seq !== ollamaModelsFetchSeq) return;

            if (!response.ok || !data.success) {
                populateOllamaModelSelect([], keep);
                setOllamaHint(
                    data.error || "Could not list models — keeping the saved model.",
                    true
                );
                return;
            }

            populateOllamaModelSelect(data.models || [], keep);
            const count = (data.models || []).length;
            setOllamaHint(
                count
                    ? "Loaded " + count + " model" + (count === 1 ? "" : "s") + " from " + (data.base_url || "Ollama") + "."
                    : "Ollama responded but reported no installed models.",
                false
            );
        } catch (err) {
            if (seq !== ollamaModelsFetchSeq) return;
            populateOllamaModelSelect([], keep);
            setOllamaHint(err.message || "Failed to load Ollama models.", true);
        } finally {
            if (seq === ollamaModelsFetchSeq && refreshBtn) {
                refreshBtn.disabled = false;
            }
        }
    }

    function applySettingsToForm(settings) {
        $("settings-provider").value = settings.ai_provider || "ollama";
        $("settings-openai-model").value = settings.openai_model || "";
        $("settings-openai-base-url").value = settings.openai_base_url || "";
        $("settings-openai-api-key").value = "";
        $("settings-openai-api-key").placeholder = settings.openai_api_key_set
            ? "•••••••• (leave blank to keep)"
            : "sk-...";

        $("settings-ollama-base-url").value = settings.ollama_base_url || "";
        preferredOllamaModel = settings.ollama_model || "";
        populateOllamaModelSelect(
            preferredOllamaModel ? [preferredOllamaModel] : [],
            preferredOllamaModel
        );
        $("settings-ollama-api-key").value = "";
        $("settings-ollama-api-key").placeholder = settings.ollama_api_key_set
            ? "•••••••• (leave blank to keep)"
            : "ollama";

        $("settings-openwebui-base-url").value = settings.openwebui_base_url || "";
        openWebUIApiKeySet = !!settings.openwebui_api_key_set;
        preferredOpenWebUIModel = settings.openwebui_model || "";
        populateOpenWebUIModelSelect(
            preferredOpenWebUIModel ? [preferredOpenWebUIModel] : [],
            preferredOpenWebUIModel
        );
        $("settings-openwebui-api-key").value = "";
        $("settings-openwebui-api-key").placeholder = settings.openwebui_api_key_set
            ? "•••••••• (leave blank to keep)"
            : "API key / JWT";

        $("settings-cursor-base-url").value = settings.cursor_base_url || "";
        cursorApiKeySet = !!settings.cursor_api_key_set;
        preferredCursorModel = settings.cursor_model || "";
        populateCursorModelSelect(
            preferredCursorModel ? [preferredCursorModel] : [],
            preferredCursorModel,
            []
        );
        $("settings-cursor-api-key").value = "";
        $("settings-cursor-api-key").placeholder = settings.cursor_api_key_set
            ? "•••••••• (leave blank to keep)"
            : "key_...";

        $("settings-max-reqs").value = settings.openai_max_num_of_reqs;
        toggleProviderFields(settings.ai_provider || "ollama");
    }

    function collectFormPayload(persist) {
        const modelSelect = $("settings-ollama-model");
        const openWebUIModelSelect = $("settings-openwebui-model");
        const cursorModelSelect = $("settings-cursor-model");
        const payload = {
            ai_provider: $("settings-provider").value,
            openai_model: $("settings-openai-model").value.trim(),
            openai_base_url: $("settings-openai-base-url").value.trim(),
            ollama_base_url: $("settings-ollama-base-url").value.trim(),
            ollama_model: (modelSelect && modelSelect.value || preferredOllamaModel || "").trim(),
            openwebui_base_url: $("settings-openwebui-base-url").value.trim(),
            openwebui_model: (openWebUIModelSelect && openWebUIModelSelect.value || preferredOpenWebUIModel || "").trim(),
            cursor_base_url: $("settings-cursor-base-url").value.trim(),
            cursor_model: (cursorModelSelect && cursorModelSelect.value || preferredCursorModel || "").trim(),
            openai_max_num_of_reqs: parseInt($("settings-max-reqs").value, 10) || 10,
            persist: persist !== false,
        };

        const openaiKey = $("settings-openai-api-key").value.trim();
        if (openaiKey && !openaiKey.includes(MASK_HINT)) {
            payload.openai_api_key = openaiKey;
        }

        const ollamaKey = $("settings-ollama-api-key").value.trim();
        if (ollamaKey && !ollamaKey.includes(MASK_HINT)) {
            payload.ollama_api_key = ollamaKey;
        }

        const openwebuiKey = $("settings-openwebui-api-key").value.trim();
        if (openwebuiKey && !openwebuiKey.includes(MASK_HINT)) {
            payload.openwebui_api_key = openwebuiKey;
        }

        const cursorKey = $("settings-cursor-api-key").value.trim();
        if (cursorKey && !cursorKey.includes(MASK_HINT)) {
            payload.cursor_api_key = cursorKey;
        }

        return payload;
    }

    async function loadSettings() {
        showStatus("Loading…", false);
        const response = await fetch("/api/settings");
        if (!response.ok) {
            throw new Error("Failed to load settings (" + response.status + ")");
        }
        const settings = await response.json();
        applySettingsToForm(settings);
        showStatus("Loaded from data/ai_settings.json and .env", false);
    }

    async function saveSettings() {
        showStatus("Saving…", false);
        const response = await fetch("/api/settings", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(collectFormPayload(true)),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Save failed");
        }
        applySettingsToForm(data.settings);
        showStatus("Choices saved to JSON; API keys saved to .env", false);
        if (window.BenchmarkUI && typeof window.BenchmarkUI.refresh === "function") {
            window.BenchmarkUI.refresh().catch(() => {});
        }
        if (window.BenchmarkUI && typeof window.BenchmarkUI.invalidateModelCache === "function") {
            window.BenchmarkUI.invalidateModelCache();
        }
    }

    async function reloadFromEnv() {
        showStatus("Reloading settings from disk…", false);
        const response = await fetch("/api/settings/reload", { method: "POST" });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Reload failed");
        }
        applySettingsToForm(data.settings);
        showStatus("Reloaded JSON choices and .env API keys", false);
    }

    async function testConnection() {
        const testBtn = $("settings-test");
        if (testBtn) testBtn.disabled = true;
        showStatus("Testing connection…", false);
        try {
            const response = await fetch("/api/settings/test", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(collectFormPayload(false)),
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || "Connection test failed");
            }
            const preview = data.preview ? " → " + data.preview : "";
            showStatus(
                "OK · " + (data.provider || "?") + " / " + (data.model || "?") + preview,
                false
            );
        } finally {
            if (testBtn) testBtn.disabled = false;
        }
    }

    function openSettings() {
        closeAppSettings();
        const modal = $("settings-modal");
        if (!modal) return;
        modal.classList.add("open");
        modal.setAttribute("aria-hidden", "false");
        loadSettings().catch((err) => showStatus(err.message, true));
    }

    function closeSettings() {
        const modal = $("settings-modal");
        if (!modal) return;
        modal.classList.remove("open");
        modal.setAttribute("aria-hidden", "true");
        if (window.BenchmarkUI && typeof window.BenchmarkUI.refresh === "function") {
            window.BenchmarkUI.refresh().catch(() => {});
        }
        if (window.BenchmarkUI && typeof window.BenchmarkUI.invalidateModelCache === "function") {
            window.BenchmarkUI.invalidateModelCache();
        }
    }

    function showAppStatus(message, isError) {
        const el = $("app-settings-status");
        if (!el) return;
        el.textContent = message;
        el.className = "settings-status" + (isError ? " error" : " success");
    }

    var TERMINAL_TOOL_UI = [
        { id: "beroot", value: "beRoot", label: "BeRoot" },
        { id: "linenum", value: "linEnum", label: "LinEnum" },
        { id: "linpeas", value: "linPeas", label: "LinPEAS" },
    ];

    function showAppSettingsMainView() {
        const main = $("app-settings-main");
        const tools = $("app-settings-tools-panel");
        const toolsBtn = $("app-settings-tools-open");
        if (main) main.hidden = false;
        if (tools) tools.hidden = true;
        if (toolsBtn) toolsBtn.hidden = false;
    }

    function showAppSettingsToolsView() {
        const main = $("app-settings-main");
        const tools = $("app-settings-tools-panel");
        const toolsBtn = $("app-settings-tools-open");
        if (main) main.hidden = true;
        if (tools) tools.hidden = false;
        if (toolsBtn) toolsBtn.hidden = true;
    }

    function renderTerminalToolsSettings(settings) {
        const list = $("app-settings-tools-list");
        if (!list) return;
        const visible = settings.terminal_tools_visible || {};
        const catalog = settings.available_tools || [];
        list.innerHTML = "";
        TERMINAL_TOOL_UI.forEach(function (opt) {
            const meta = catalog.find(function (t) {
                return t.id === opt.id;
            });
            const name = meta && meta.name ? meta.name : opt.label;
            const desc = meta && meta.description ? meta.description : "";
            const checked = visible[opt.id] !== false;

            const row = document.createElement("label");
            row.className = "settings-toggle-field";
            row.setAttribute("for", "app-tool-visible-" + opt.id);

            const copy = document.createElement("span");
            copy.className = "settings-toggle-copy";
            const title = document.createElement("span");
            title.className = "settings-toggle-title";
            title.textContent = name;
            copy.appendChild(title);
            if (desc) {
                const hint = document.createElement("span");
                hint.className = "settings-toggle-hint";
                hint.textContent = desc;
                copy.appendChild(hint);
            }

            const toggle = document.createElement("span");
            toggle.className = "settings-toggle";
            const input = document.createElement("input");
            input.type = "checkbox";
            input.id = "app-tool-visible-" + opt.id;
            input.setAttribute("data-tool-id", opt.id);
            input.checked = checked;
            const slider = document.createElement("span");
            slider.className = "settings-toggle-slider";
            slider.setAttribute("aria-hidden", "true");
            toggle.appendChild(input);
            toggle.appendChild(slider);

            row.appendChild(copy);
            row.appendChild(toggle);
            list.appendChild(row);
        });
    }

    function collectTerminalToolsVisible() {
        const out = {};
        document.querySelectorAll("#app-settings-tools-list input[data-tool-id]").forEach(function (el) {
            out[el.getAttribute("data-tool-id")] = !!el.checked;
        });
        TERMINAL_TOOL_UI.forEach(function (opt) {
            if (out[opt.id] === undefined) {
                out[opt.id] = true;
            }
        });
        return out;
    }

    function refreshTerminalToolSelector(settings) {
        const select = document.getElementById("toolSelector");
        if (!select || !settings) return;
        const visible = settings.terminal_tools_visible || {};
        const catalog = settings.available_tools || [];
        const previous = select.value;
        select.innerHTML = "";
        var added = 0;
        TERMINAL_TOOL_UI.forEach(function (opt) {
            if (visible[opt.id] === false) return;
            const meta = catalog.find(function (t) {
                return t.id === opt.id;
            });
            const option = document.createElement("option");
            option.value = opt.value;
            option.textContent = meta && meta.name ? meta.name : opt.label;
            select.appendChild(option);
            added += 1;
        });
        if (!added) {
            const placeholder = document.createElement("option");
            placeholder.value = "";
            placeholder.textContent = "No tools visible (App Settings → Tools)";
            placeholder.disabled = true;
            select.appendChild(placeholder);
            return;
        }
        var values = Array.prototype.map.call(select.options, function (o) {
            return o.value;
        });
        if (previous && values.indexOf(previous) >= 0) {
            select.value = previous;
        }
        if (select.classList.contains("queue-select")) {
            ["import", "export"].forEach(function (extra) {
                const option = document.createElement("option");
                option.value = extra;
                option.textContent = extra.charAt(0).toUpperCase() + extra.slice(1);
                select.appendChild(option);
            });
        }
    }

    window.refreshTerminalToolSelector = refreshTerminalToolSelector;

    function applyAppSettingsToForm(settings) {
        const roleSelect = $("app-settings-role-objective");
        if (roleSelect) {
            roleSelect.innerHTML = "";
            (settings.role_objective_options || []).forEach(function (name) {
                const option = document.createElement("option");
                option.value = name;
                option.textContent = name;
                roleSelect.appendChild(option);
            });
            roleSelect.value = settings.role_objective || "";
        }
        const rotateRolesToggle = $("app-settings-rotate-roles");
        if (rotateRolesToggle) {
            rotateRolesToggle.checked = !!Number(settings.rotate_role_objectives);
        }
        const sessionV2Toggle = $("app-settings-upgraded-session-v2");
        if (sessionV2Toggle) {
            sessionV2Toggle.checked = settings.upgraded_session_v2 !== 0;
        }
        const promptToggle = $("app-settings-show-prompts");
        if (promptToggle) {
            promptToggle.checked = !!Number(settings.debug);
        }
        const outputToggle = $("app-settings-history-outputs");
        if (outputToggle) {
            outputToggle.checked = !!Number(settings.history_include_outputs);
        }
        const outputCount = $("app-settings-history-output-count");
        if (outputCount) {
            outputCount.value = Number.isInteger(Number(settings.history_output_edge_count))
                ? String(Number(settings.history_output_edge_count))
                : "4";
            outputCount.disabled = !(outputToggle && outputToggle.checked);
        }
        const advancedToggle = $("app-settings-advanced-mode");
        if (advancedToggle) {
            advancedToggle.checked = !!Number(settings.advanced_mode);
        }
        renderTerminalToolsSettings(settings);
        refreshTerminalToolSelector(settings);
    }

    async function loadAppSettings() {
        showAppStatus("Loading…", false);
        const response = await fetch("/api/settings");
        if (!response.ok) {
            throw new Error("Failed to load settings (" + response.status + ")");
        }
        const settings = await response.json();
        applyAppSettingsToForm(settings);
        showAppStatus("Loaded", false);
    }

    async function saveAppSettings() {
        showAppStatus("Saving…", false);
        const promptToggle = $("app-settings-show-prompts");
        const roleSelect = $("app-settings-role-objective");
        const rotateRolesToggle = $("app-settings-rotate-roles");
        const sessionV2Toggle = $("app-settings-upgraded-session-v2");
        const outputToggle = $("app-settings-history-outputs");
        const outputCount = $("app-settings-history-output-count");
        const advancedToggle = $("app-settings-advanced-mode");
        const edgeCount = Number(outputCount ? outputCount.value : 4);
        if (!Number.isInteger(edgeCount) || edgeCount < 0 || edgeCount > 40) {
            throw new Error("History output count must be an integer from 0 to 40.");
        }
        const response = await fetch("/api/settings", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                role_objective: roleSelect ? roleSelect.value : "",
                rotate_role_objectives:
                    rotateRolesToggle && rotateRolesToggle.checked ? 1 : 0,
                upgraded_session_v2:
                    sessionV2Toggle && sessionV2Toggle.checked ? 1 : 0,
                debug: promptToggle && promptToggle.checked ? 1 : 0,
                history_include_outputs: outputToggle && outputToggle.checked ? 1 : 0,
                history_output_edge_count: edgeCount,
                advanced_mode: advancedToggle && advancedToggle.checked ? 1 : 0,
                terminal_tools_visible: collectTerminalToolsVisible(),
                persist: true,
            }),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Save failed");
        }
        applyAppSettingsToForm(data.settings || {});
        const historyStatus = outputToggle && outputToggle.checked
            ? (edgeCount === 0 ? "all history outputs included" : `first/last ${edgeCount} outputs included`)
            : "command-only history";
        showAppStatus(
            "Saved — "
                + (sessionV2Toggle && sessionV2Toggle.checked
                    ? "Upgraded Session v2 on; "
                    : "Upgraded Session v2 off; ")
                + (rotateRolesToggle && rotateRolesToggle.checked
                    ? "rotating roles; "
                    : (roleSelect ? roleSelect.value + "; " : ""))
                + historyStatus,
            false
        );
        if (window.BenchmarkUI && typeof window.BenchmarkUI.refresh === "function") {
            window.BenchmarkUI.refresh().catch(function () {});
        }
        refreshTerminalToolSelector(data.settings || {});
    }

    function openAppSettings() {
        closeSettings();
        const modal = $("app-settings-modal");
        if (!modal) return;
        showAppSettingsMainView();
        modal.classList.add("open");
        modal.setAttribute("aria-hidden", "false");
        loadAppSettings().catch((err) => showAppStatus(err.message, true));
    }

    function closeAppSettings() {
        const modal = $("app-settings-modal");
        if (!modal) return;
        modal.classList.remove("open");
        modal.setAttribute("aria-hidden", "true");
    }

    window.openSettings = openSettings;
    window.closeSettings = closeSettings;
    window.openAppSettings = openAppSettings;
    window.closeAppSettings = closeAppSettings;

    document.addEventListener("DOMContentLoaded", function () {
        const providerSelect = $("settings-provider");
        if (providerSelect) {
            providerSelect.addEventListener("change", function () {
                toggleProviderFields(providerSelect.value);
            });
        }

        const ollamaBase = $("settings-ollama-base-url");
        if (ollamaBase) {
            ollamaBase.addEventListener("change", function () {
                if (($("settings-provider") || {}).value === "ollama") {
                    refreshOllamaModels();
                }
            });
            ollamaBase.addEventListener("keydown", function (e) {
                if (e.key === "Enter") {
                    e.preventDefault();
                    refreshOllamaModels();
                }
            });
        }

        const refreshBtn = $("settings-ollama-refresh-models");
        if (refreshBtn) {
            refreshBtn.addEventListener("click", function () {
                refreshOllamaModels().catch((err) => showStatus(err.message, true));
            });
        }

        const modelSelect = $("settings-ollama-model");
        if (modelSelect) {
            modelSelect.addEventListener("change", function () {
                preferredOllamaModel = modelSelect.value;
            });
        }

        const openWebUIBase = $("settings-openwebui-base-url");
        if (openWebUIBase) {
            openWebUIBase.addEventListener("change", function () {
                if (($("settings-provider") || {}).value === "openwebui") {
                    refreshOpenWebUIModels();
                }
            });
            openWebUIBase.addEventListener("keydown", function (e) {
                if (e.key === "Enter") {
                    e.preventDefault();
                    refreshOpenWebUIModels();
                }
            });
        }

        const openWebUIApiKey = $("settings-openwebui-api-key");
        if (openWebUIApiKey) {
            openWebUIApiKey.addEventListener("change", function () {
                if (($("settings-provider") || {}).value === "openwebui") {
                    refreshOpenWebUIModels();
                }
            });
            openWebUIApiKey.addEventListener("keydown", function (e) {
                if (e.key === "Enter") {
                    e.preventDefault();
                    refreshOpenWebUIModels();
                }
            });
        }

        const openWebUIRefreshBtn = $("settings-openwebui-refresh-models");
        if (openWebUIRefreshBtn) {
            openWebUIRefreshBtn.addEventListener("click", function () {
                refreshOpenWebUIModels().catch((err) => showStatus(err.message, true));
            });
        }

        const openWebUIModelSelect = $("settings-openwebui-model");
        if (openWebUIModelSelect) {
            openWebUIModelSelect.addEventListener("change", function () {
                preferredOpenWebUIModel = openWebUIModelSelect.value;
            });
        }

        const cursorApiKey = $("settings-cursor-api-key");
        if (cursorApiKey) {
            cursorApiKey.addEventListener("change", function () {
                if (($("settings-provider") || {}).value === "cursor") {
                    refreshCursorModels();
                }
            });
            cursorApiKey.addEventListener("keydown", function (e) {
                if (e.key === "Enter") {
                    e.preventDefault();
                    refreshCursorModels();
                }
            });
        }

        const cursorRefreshBtn = $("settings-cursor-refresh-models");
        if (cursorRefreshBtn) {
            cursorRefreshBtn.addEventListener("click", function () {
                refreshCursorModels().catch((err) => showStatus(err.message, true));
            });
        }

        const cursorModelSelect = $("settings-cursor-model");
        if (cursorModelSelect) {
            cursorModelSelect.addEventListener("change", function () {
                preferredCursorModel = cursorModelSelect.value;
            });
        }

        const saveBtn = $("settings-save");
        if (saveBtn) {
            saveBtn.addEventListener("click", function () {
                saveSettings().catch((err) => showStatus(err.message, true));
            });
        }

        const reloadBtn = $("settings-reload");
        if (reloadBtn) {
            reloadBtn.addEventListener("click", function () {
                reloadFromEnv().catch((err) => showStatus(err.message, true));
            });
        }

        const testBtn = $("settings-test");
        if (testBtn) {
            testBtn.addEventListener("click", function () {
                testConnection().catch((err) => showStatus(err.message, true));
            });
        }

        const closeBtn = $("settings-close");
        if (closeBtn) {
            closeBtn.addEventListener("click", closeSettings);
        }

        const backdrop = $("settings-backdrop");
        if (backdrop) {
            backdrop.addEventListener("click", closeSettings);
        }

        const appSaveBtn = $("app-settings-save");
        if (appSaveBtn) {
            appSaveBtn.addEventListener("click", function () {
                saveAppSettings().catch((err) => showAppStatus(err.message, true));
            });
        }

        const appToolsOpenBtn = $("app-settings-tools-open");
        if (appToolsOpenBtn) {
            appToolsOpenBtn.addEventListener("click", function () {
                showAppSettingsToolsView();
            });
        }

        const appToolsBackBtn = $("app-settings-tools-back");
        if (appToolsBackBtn) {
            appToolsBackBtn.addEventListener("click", function () {
                showAppSettingsMainView();
            });
        }

        const historyOutputsToggle = $("app-settings-history-outputs");
        if (historyOutputsToggle) {
            historyOutputsToggle.addEventListener("change", function () {
                const count = $("app-settings-history-output-count");
                if (count) count.disabled = !historyOutputsToggle.checked;
            });
        }

        const appCloseBtn = $("app-settings-close");
        if (appCloseBtn) {
            appCloseBtn.addEventListener("click", closeAppSettings);
        }

        const appBackdrop = $("app-settings-backdrop");
        if (appBackdrop) {
            appBackdrop.addEventListener("click", closeAppSettings);
        }

        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape") {
                closeSettings();
                closeAppSettings();
            }
        });

        fetch("/api/settings")
            .then(function (r) {
                return r.ok ? r.json() : null;
            })
            .then(function (settings) {
                if (settings) {
                    refreshTerminalToolSelector(settings);
                }
            })
            .catch(function () {});
    });
})();
