/**
 * Settings modal — load / save / test AI provider configuration.
 */
(function () {
    const MASK_HINT = "...";

    function $(id) {
        return document.getElementById(id);
    }

    function showStatus(message, isError) {
        const el = $("settings-status");
        if (!el) return;
        el.textContent = message;
        el.className = "settings-status" + (isError ? " error" : " success");
    }

    function toggleProviderFields(provider) {
        const openaiFields = document.querySelectorAll("[data-provider-group='openai']");
        const openwebuiFields = document.querySelectorAll("[data-provider-group='openwebui']");
        openaiFields.forEach((el) => {
            el.style.display = provider === "openai" ? "" : "none";
        });
        openwebuiFields.forEach((el) => {
            el.style.display = provider === "openwebui" ? "" : "none";
        });
    }

    function applySettingsToForm(settings) {
        $("settings-provider").value = settings.ai_provider || "openai";
        $("settings-openai-model").value = settings.openai_model || "";
        $("settings-openai-base-url").value = settings.openai_base_url || "";
        $("settings-openai-api-key").value = "";
        $("settings-openai-api-key").placeholder = settings.openai_api_key_set
            ? "•••••••• (leave blank to keep)"
            : "sk-...";
        $("settings-openwebui-base-url").value = settings.openwebui_base_url || "";
        $("settings-openwebui-model").value = settings.openwebui_model || "";
        $("settings-openwebui-api-key").value = "";
        $("settings-openwebui-api-key").placeholder = settings.openwebui_api_key_set
            ? "•••••••• (leave blank to keep)"
            : "API key / JWT";
        $("settings-max-reqs").value = settings.openai_max_num_of_reqs;
        $("settings-debug").value = String(settings.debug);
        toggleProviderFields(settings.ai_provider || "openai");
    }

    function collectFormPayload(persist) {
        const payload = {
            ai_provider: $("settings-provider").value,
            openai_model: $("settings-openai-model").value.trim(),
            openai_base_url: $("settings-openai-base-url").value.trim(),
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
