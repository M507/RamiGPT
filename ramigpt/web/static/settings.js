/**
 * Settings modal — load / save / test AI provider configuration.
 */
(function () {
    const MASK_HINT = "...";
    const PROVIDER_GROUPS = ["openai", "ollama", "openwebui"];

    let preferredOllamaModel = "";
    let ollamaModelsFetchSeq = 0;

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

    function toggleProviderFields(provider) {
        PROVIDER_GROUPS.forEach((name) => {
            document.querySelectorAll("[data-provider-group='" + name + "']").forEach((el) => {
                el.style.display = provider === name ? "" : "none";
            });
        });
        if (provider === "ollama") {
            refreshOllamaModels();
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
        $("settings-openwebui-model").value = settings.openwebui_model || "";
        $("settings-openwebui-api-key").value = "";
        $("settings-openwebui-api-key").placeholder = settings.openwebui_api_key_set
            ? "•••••••• (leave blank to keep)"
            : "API key / JWT";

        $("settings-max-reqs").value = settings.openai_max_num_of_reqs;
        $("settings-debug").value = String(settings.debug);
        toggleProviderFields(settings.ai_provider || "ollama");
    }

    function collectFormPayload(persist) {
        const modelSelect = $("settings-ollama-model");
        const payload = {
            ai_provider: $("settings-provider").value,
            openai_model: $("settings-openai-model").value.trim(),
            openai_base_url: $("settings-openai-base-url").value.trim(),
            ollama_base_url: $("settings-ollama-base-url").value.trim(),
            ollama_model: (modelSelect && modelSelect.value || preferredOllamaModel || "").trim(),
            openwebui_base_url: $("settings-openwebui-base-url").value.trim(),
            openwebui_model: $("settings-openwebui-model").value.trim(),
            openai_max_num_of_reqs: parseInt($("settings-max-reqs").value, 10) || 10,
            debug: parseInt($("settings-debug").value, 10) || 0,
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
        showStatus("Loaded from server / .env", false);
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
        showStatus("Saved to .env", false);
    }

    async function reloadFromEnv() {
        showStatus("Reloading from .env…", false);
        const response = await fetch("/api/settings/reload", { method: "POST" });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Reload failed");
        }
        applySettingsToForm(data.settings);
        showStatus("Reloaded from .env", false);
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
    }

    window.openSettings = openSettings;
    window.closeSettings = closeSettings;

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

        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape") {
                closeSettings();
            }
        });
    });
})();
