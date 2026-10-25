(() => {
  "use strict";

  const boot = window.PIXI_BOOT || {};
  const csrf = boot.csrf || "";
  const state = {
    language: boot.language || "zh",
    theme: boot.theme || "light",
    messages: {},
    data: null,
    selectedPackage: null,
    activeJob: null,
    jobs: new Map(),
    pollTimer: null,
    activeTab: "overview",
    editorManifest: "",
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  function t(text, ...args) {
    let value = state.messages[text] || text;
    if (args.length) {
      let index = 0;
      value = value.replace(/\{\}/g, () => String(args[index++] ?? ""));
    }
    return value;
  }

  function toast(message, kind = "info") {
    const root = $("#toast-root");
    const node = document.createElement("div");
    node.className = "toast" + (kind === "error" ? " error" : "");
    node.textContent = message;
    root.appendChild(node);
    setTimeout(() => node.remove(), 4200);
  }

  async function api(path, options = {}) {
    const opts = { ...options, headers: { ...(options.headers || {}) } };
    if (opts.body && typeof opts.body !== "string") {
      opts.body = JSON.stringify(opts.body);
      opts.headers["Content-Type"] = "application/json";
    }
    if (opts.method && opts.method !== "GET") {
      opts.headers["X-CSRF-Token"] = csrf;
    }
    const response = await fetch(path, opts);
    if (response.status === 401) {
      window.location.href = "/login";
      throw new Error("Not authenticated");
    }
    let payload = null;
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) payload = await response.json();
    if (!response.ok) {
      throw new Error(payload?.error || `HTTP ${response.status}`);
    }
    return payload;
  }

  async function loadLanguage(language, persist = true) {
    state.language = language;
    try {
      const payload = await api(`/api/i18n/${encodeURIComponent(language)}`);
      state.messages = payload.messages || {};
    } catch {
      state.messages = {};
    }
    document.documentElement.lang = language;
    $$("[data-i18n]").forEach((node) => {
      node.textContent = t(node.dataset.i18n);
    });
    $$("[data-i18n-placeholder]").forEach((node) => {
      node.placeholder = t(node.dataset.i18nPlaceholder);
    });
    $("#language-select").value = language;
    applyTheme(state.theme, false);
    renderAll();
    if (persist) {
      try {
        await api("/api/settings", {
          method: "POST",
          body: { language },
        });
      } catch (error) {
        toast(error.message, "error");
      }
    }
  }

  function scopeLabel(scope) {
    if (!scope || scope === "transitive") return t("Transitive");
    if (scope === "base") return t("Base");
    if (scope.startsWith("feature:")) return `${t("feature:")} ${scope.slice(8)}`;
    if (scope.startsWith("env:")) return `${t("Environment:")} ${scope.slice(4)}`;
    return scope;
  }

  function typeLabel(kind) {
    return kind === "pypi" ? "PyPI" : "Conda";
  }

  function formatSize(bytes) {
    let value = Number(bytes || 0);
    if (!value) return "";
    const units = ["B", "KB", "MB", "GB"];
    let index = 0;
    while (value >= 1024 && index < units.length - 1) {
      value /= 1024;
      index += 1;
    }
    return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
  }

  function renderAll() {
    renderWorkspace();
    renderRecent();
    renderSidebarTasks();
    renderSidebarPython();
    renderOverview();
    renderPackages();
    renderTasks();
    renderEditorPath();
  }

  function renderWorkspace() {
    const data = state.data;
    const name = $("#workspace-name");
    const manifest = $("#workspace-manifest");
    const envSelect = $("#environment-select");
    if (!data?.opened) {
      name.textContent = t("No workspace");
      manifest.textContent = "";
      envSelect.innerHTML = "";
      return;
    }
    name.textContent = data.name || t("Workspace");
    manifest.textContent = data.manifest || "";
    $("#workspace-path").value = data.manifest || "";
    const options = [];
    if (data.base_mode) {
      options.push(`<option value="__base__" selected>${escapeHtml(t("Base dependencies"))}</option>`);
    } else {
      options.push(`<option value="__base__">${escapeHtml(t("Base dependencies"))}</option>`);
    }
    for (const env of data.envs || []) {
      const selected = !data.base_mode && env.name === data.environment ? " selected" : "";
      options.push(`<option value="${escapeAttr(env.name)}"${selected}>${escapeHtml(env.name)}</option>`);
    }
    envSelect.innerHTML = options.join("");
    envSelect.onchange = () => setEnvironment(envSelect.value);
    $("#pixi-version").textContent = data.pixi ? `Pixi ${data.pixi}` : "Pixi";
  }

  function renderRecent() {
    const select = $("#recent-workspaces");
    const recent = state.data?.recent || [];
    select.innerHTML = `<option value="">${escapeHtml(t("Recent workspaces"))}</option>` +
      recent.map((item) => `<option value="${escapeAttr(item.manifest)}" data-environment="${escapeAttr(item.environment || "")}">${escapeHtml(item.name || item.manifest)} [${escapeHtml(item.environment || "")}]</option>`).join("");
    if (state.data?.opened) {
      const match = recent.find((item) =>
        item.manifest === state.data.manifest &&
        String(item.environment || "") === String(state.data.environment || "")
      );
      if (match) select.value = match.manifest;
    }
    select.onchange = () => {
      const option = select.selectedOptions[0];
      if (select.value) {
        openWorkspace(select.value, option?.dataset.environment || "");
      }
    };
  }

  function renderSidebarTasks() {
    const root = $("#quick-tasks");
    const tasks = state.data?.tasks || [];
    $("#task-count").textContent = String(tasks.length);
    if (!tasks.length) {
      root.innerHTML = `<div class="muted">${escapeHtml(t("No tasks in this environment"))}</div>`;
      return;
    }
    root.innerHTML = tasks.map((task) => `
      <div class="quick-row">
        <button class="run-btn" data-task="${escapeAttr(task.name)}" data-terminal="0" title="${escapeAttr(t("Run"))}">▶</button>
        <button class="run-btn terminal" data-task="${escapeAttr(task.name)}" data-terminal="1" title="${escapeAttr(t("Run in Terminal"))}">&gt;_</button>
        <div class="quick-text">
          <div class="quick-name">${escapeHtml(task.name)}</div>
          <div class="quick-sub">${escapeHtml(task.cmd || "")}</div>
        </div>
      </div>`).join("");
    root.querySelectorAll("[data-task]").forEach((button) => {
      button.onclick = () => runTask(button.dataset.task, button.dataset.terminal === "1");
    });
  }

  function renderSidebarPython() {
    const root = $("#python-programs");
    const runs = state.data?.python_runs || [];
    $("#python-count").textContent = String(runs.length);
    if (!runs.length) {
      root.innerHTML = `<div class="muted">${escapeHtml(t("No Python programs in this environment"))}</div>`;
      return;
    }
    root.innerHTML = runs.map((run, index) => {
      const name = String(run.script || "").split(/[\\/]/).pop() || "";
      return `<div class="quick-row">
        <button class="run-btn" data-python="${index}" data-terminal="0" title="${escapeAttr(t("Run"))}">▶</button>
        <button class="run-btn terminal" data-python="${index}" data-terminal="1" title="${escapeAttr(t("Run in Terminal"))}">&gt;_</button>
        <div class="quick-text">
          <div class="quick-name">${escapeHtml(name)}</div>
          <div class="quick-sub">${escapeHtml(run.args || "")}</div>
        </div>
      </div>`;
    }).join("");
    root.querySelectorAll("[data-python]").forEach((button) => {
      button.onclick = () => {
        const run = runs[Number(button.dataset.python)];
        if (!run) return;
        $("#python-script").value = run.script || "";
        $("#python-args").value = run.args || "";
        $("#python-cwd").value = run.cwd || "";
        if (button.dataset.terminal === "1") runPython(true);
        else {
          setTab("python");
          $("#python-script").focus();
        }
      };
    });
  }

  function renderOverview() {
    const root = $("#overview-cards");
    const data = state.data;
    if (!data?.opened) {
      root.innerHTML = `<div class="stat-card"><div class="stat-label">${escapeHtml(t("Workspace"))}</div><div class="stat-value">${escapeHtml(t("No workspace"))}</div></div>`;
      $("#overview-environments").innerHTML = "";
      return;
    }
    const installed = (data.envs || []).filter((env) => env.installed).length;
    root.innerHTML = `
      <div class="stat-card"><div class="stat-label">${escapeHtml(t("Packages"))}</div><div class="stat-value">${data.package_count || 0}</div></div>
      <div class="stat-card"><div class="stat-label">${escapeHtml(t("Task"))}</div><div class="stat-value">${(data.tasks || []).length}</div></div>
      <div class="stat-card"><div class="stat-label">${escapeHtml(t("Environments"))}</div><div class="stat-value">${(data.envs || []).length}</div></div>
      <div class="stat-card"><div class="stat-label">${escapeHtml(t("Lock file"))}</div><div class="stat-value">${escapeHtml(data.lock_state || "")}</div></div>
      <div class="stat-card"><div class="stat-label">${escapeHtml(t("Platform"))}</div><div class="stat-value">${escapeHtml(data.platform || "")}</div></div>`;
    $("#overview-environments").innerHTML = (data.envs || []).map((env) => `
      <div class="env-card ${env.name === data.environment && !data.base_mode ? "current" : ""}">
        <strong>${escapeHtml(env.name)}</strong>
        <div class="muted">${escapeHtml((env.features || []).join(", "))}</div>
        <div class="muted">${env.installed ? escapeHtml(t("Installed")) : escapeHtml(t("Not installed"))} · ${escapeHtml(env.prefix || "")}</div>
      </div>`).join("");
  }

  function filteredPackages() {
    const data = state.data;
    if (!data?.opened) return [];
    const filter = document.querySelector('input[name="package-filter"]:checked')?.value || "user";
    const query = ($("#package-search").value || "").trim().toLowerCase();
    const kind = $("#package-kind").value;
    return (data.packages || []).filter((pkg) => {
      if (filter === "user" && !pkg.is_explicit) return false;
      if (kind && String(pkg.kind).toLowerCase() !== kind) return false;
      if (query) {
        const hay = `${pkg.name} ${pkg.version} ${pkg.requested_spec} ${pkg.source}`.toLowerCase();
        if (!hay.includes(query)) return false;
      }
      return true;
    });
  }

  function renderPackages() {
    const rows = $("#package-rows");
    const data = state.data;
    const packages = filteredPackages();
    if (!data?.opened) {
      rows.innerHTML = "";
      $("#package-status").textContent = t("Open a workspace first.");
      return;
    }
    const allCount = (data.packages || []).length;
    $("#package-status").textContent = `${packages.length} / ${allCount} · ${t("Explicit dependencies")}: ${(data.packages || []).filter((p) => p.is_explicit).length}`;
    rows.innerHTML = packages.map((pkg) => {
      const selected = state.selectedPackage === pkg.name ? " class=\"selected\"" : "";
      const tag = pkg.latest_error ? "error" : pkg.status_level === "update" ? "update" : pkg.status_level === "ok" ? "ok" : "";
      const scope = String(pkg.scope || "").split(":")[0];
      const status = pkg.installed === false
        ? t("Not installed")
        : pkg.latest_error
          ? pkg.latest_error
          : pkg.status_level === "update"
            ? t("Update available")
            : pkg.status_level === "ok"
              ? t("Up to date")
              : t("Not checked");
      return `<tr data-package="${escapeAttr(pkg.name)}"${selected}>
        <td><strong>${escapeHtml(pkg.name)}</strong></td>
        <td>${escapeHtml(pkg.version || "—")}</td>
        <td>${escapeHtml(pkg.latest || "")}</td>
        <td><span class="tag ${tag}">${escapeHtml(status)}</span></td>
        <td><span class="tag ${pkg.kind === "pypi" ? "pypi" : ""}">${escapeHtml(typeLabel(pkg.kind))}</span></td>
        <td><span class="scope-${escapeAttr(scope)}">${escapeHtml(scopeLabel(pkg.scope))}</span></td>
        <td>${escapeHtml(pkg.requested_spec || "")}</td>
        <td>${escapeHtml(pkg.source || "")}</td>
        <td class="num">${escapeHtml(formatSize(pkg.size))}</td>
      </tr>`;
    }).join("");
    rows.querySelectorAll("tr[data-package]").forEach((row) => {
      row.onclick = () => {
        state.selectedPackage = row.dataset.package;
        renderPackages();
      };
    });
  }

  function selectedPackage() {
    return (state.data?.packages || []).find((pkg) => pkg.name === state.selectedPackage);
  }

  async function setEnvironment(environment) {
    try {
      state.data = await api("/api/environment", { method: "POST", body: { environment } });
      state.selectedPackage = null;
      renderAll();
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function openWorkspace(path, environment = "") {
    if (!path) return;
    try {
      state.data = await api("/api/workspace/open", {
        method: "POST",
        body: { path, environment },
      });
      state.selectedPackage = null;
      state.editorManifest = "";
      $("#editor-text").value = "";
      renderAll();
      if (state.activeTab === "editor") loadEditor();
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function refreshWorkspace() {
    try {
      state.data = await api("/api/workspace/refresh", { method: "POST", body: {} });
      renderAll();
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function runTask(name, terminal) {
    try {
      const job = await api("/api/jobs", {
        method: "POST",
        body: { kind: "task", name, args: "", terminal },
      });
      if (terminal) toast(t("Terminal opened."));
      else addJob(job);
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function runPython(terminal) {
    const script = $("#python-script").value.trim();
    if (!script) {
      toast(t("Specify a script first."), "error");
      return;
    }
    try {
      const job = await api("/api/jobs", {
        method: "POST",
        body: {
          kind: "python",
          script,
          args: $("#python-args").value,
          cwd: $("#python-cwd").value,
          terminal,
        },
      });
      if (terminal) toast(t("Terminal opened."));
      else addJob(job);
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function runCommand(terminal) {
    const command = $("#manual-command").value.trim();
    if (!command) return;
    try {
      const job = await api("/api/jobs", {
        method: "POST",
        body: { kind: "command", command, terminal },
      });
      if (terminal) toast(t("Terminal opened."));
      else addJob(job);
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function installEnvironment() {
    try {
      addJob(await api("/api/jobs", { method: "POST", body: { kind: "install" } }));
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function queryLatest() {
    const pkg = selectedPackage();
    if (!pkg) {
      toast(t("Select a package first."), "error");
      return;
    }
    try {
      const updated = await api("/api/packages/latest", {
        method: "POST",
        body: { name: pkg.name },
      });
      const index = (state.data.packages || []).findIndex((item) => item.name === pkg.name);
      if (index >= 0) state.data.packages[index] = updated;
      renderPackages();
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function checkCompatible() {
    try {
      const result = await api("/api/packages/compatible", { method: "POST", body: {} });
      const count = Object.keys(result.updates || {}).length;
      state.data.packages = (state.data.packages || []).map((pkg) => ({
        ...pkg,
        compatible_to: result.updates[pkg.name] || null,
      }));
      renderPackages();
      toast(t("{} compatible updates found", count));
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function updateSelected(upgrade) {
    const pkg = selectedPackage();
    if (!pkg) {
      toast(t("Select a package first."), "error");
      return;
    }
    try {
      addJob(await api("/api/jobs", {
        method: "POST",
        body: { kind: "update", name: pkg.name, upgrade },
      }));
    } catch (error) {
      toast(error.message, "error");
    }
  }

  function openAddPackage() {
    const base = state.data?.base_mode;
    const modal = openModal(`
      <h2>${escapeHtml(t("Add Package"))}</h2>
      <div class="form-grid">
        <label>${escapeHtml(t("Package specification"))}</label>
        <input id="modal-specs" type="text" placeholder="numpy pandas">
        <label>${escapeHtml(t("Target"))}</label>
        <div>${escapeHtml(base ? t("Base dependencies") : state.data?.environment || "")}</div>
        <label>${escapeHtml(t("Feature"))}</label>
        <input id="modal-feature" type="text" placeholder="default">
        <label>${escapeHtml(t("Use PyPI"))}</label>
        <input id="modal-pypi" type="checkbox">
        <label>${escapeHtml(t("Only update manifest"))}</label>
        <input id="modal-no-install" type="checkbox">
      </div>
      <div class="modal-actions">
        <button class="button" data-close>${escapeHtml(t("Cancel"))}</button>
        <button class="button button-primary" id="modal-run">${escapeHtml(t("Run"))}</button>
      </div>`);
    $("#modal-run", modal).onclick = async () => {
      const specs = $("#modal-specs", modal).value.split(/\s+/).filter(Boolean);
      if (!specs.length) return;
      try {
        addJob(await api("/api/jobs", {
          method: "POST",
          body: {
            kind: "add",
            specs,
            pypi: $("#modal-pypi", modal).checked,
            feature: $("#modal-feature", modal).value.trim(),
            no_install: $("#modal-no-install", modal).checked,
            environment: base ? "" : (state.data?.environment || ""),
          },
        }));
        closeModal(modal);
      } catch (error) {
        toast(error.message, "error");
      }
    };
  }

  async function openSettings() {
    let settings = { terminal: "" };
    try {
      settings = await api("/api/settings");
    } catch {
      // Keep the modal usable even if the state file is temporarily unavailable.
    }
    const modal = openModal(`
      <h2>${escapeHtml(t("Settings"))}</h2>
      <div class="form-grid">
        <label>${escapeHtml(t("Terminal (optional)"))}</label>
        <input id="settings-terminal" type="text" value="${escapeAttr(settings.terminal || "")}" placeholder="powershell.exe / cmd.exe / wt.exe">
      </div>
      <p class="muted">${escapeHtml(t("Leave empty for PowerShell. HTTP Web UI has no TLS; use only on a trusted LAN."))}</p>
      <div class="modal-actions">
        <button class="button" data-close>${escapeHtml(t("Cancel"))}</button>
        <button class="button button-primary" id="settings-save">${escapeHtml(t("Save"))}</button>
      </div>`);
    $("#settings-save", modal).onclick = async () => {
      try {
        await api("/api/settings", {
          method: "POST",
          body: { terminal: $("#settings-terminal", modal).value },
        });
        toast(t("Saved"));
        closeModal(modal);
      } catch (error) {
        toast(error.message, "error");
      }
    };
  }

  async function openEnvironmentManager() {
    let features = [];
    try {
      features = (await api("/api/environments/features")).features || [];
    } catch {
      features = ["default"];
    }
    const current = state.data?.base_mode ? "" : (state.data?.environment || "");
    const canRemove = current && current !== "default";
    const modal = openModal(`
      <h2>${escapeHtml(t("Manage Environments"))}</h2>
      <div class="form-grid">
        <label>${escapeHtml(t("Environment name"))}</label>
        <input id="env-name" type="text">
        <label>${escapeHtml(t("Features"))}</label>
        <input id="env-features" type="text" placeholder="${escapeAttr((features || []).filter((x) => x !== "default").join(", "))}">
        <label>${escapeHtml(t("Solve group"))}</label>
        <input id="env-solve" type="text">
        <label>${escapeHtml(t("Include default feature"))}</label>
        <input id="env-default" type="checkbox" checked>
        <label>${escapeHtml(t("Install after creation"))}</label>
        <input id="env-install" type="checkbox" checked>
        <label>${escapeHtml(t("Clean environment directory"))}</label>
        <input id="env-cleanup" type="checkbox">
      </div>
      <div class="modal-actions">
        <button class="button button-danger" id="env-remove" ${canRemove ? "" : "disabled"}>${escapeHtml(t("Remove Current Environment"))}</button>
        <button class="button" data-close>${escapeHtml(t("Cancel"))}</button>
        <button class="button button-primary" id="env-add">${escapeHtml(t("Add Environment"))}</button>
      </div>`);
    $("#env-add", modal).onclick = async () => {
      try {
        const job = await api("/api/jobs", {
          method: "POST",
          body: {
            kind: "add_environment",
            name: $("#env-name", modal).value.trim(),
            features: $("#env-features", modal).value.split(/[,;\s]+/).filter(Boolean),
            solve_group: $("#env-solve", modal).value.trim(),
            use_default: $("#env-default", modal).checked,
            install: $("#env-install", modal).checked,
          },
        });
        addJob(job);
        closeModal(modal);
      } catch (error) {
        toast(error.message, "error");
      }
    };
    $("#env-remove", modal).onclick = async () => {
      if (!canRemove || !confirm(t("Remove environment {}?", current))) return;
      try {
        const job = await api("/api/jobs", {
          method: "POST",
          body: {
            kind: "remove_environment",
            name: current,
            cleanup: $("#env-cleanup", modal).checked,
          },
        });
        addJob(job);
        closeModal(modal);
      } catch (error) {
        toast(error.message, "error");
      }
    };
  }

  async function removeSelected() {
    const pkg = selectedPackage();
    if (!pkg) {
      toast(t("Select a package first."), "error");
      return;
    }
    let environment = "";
    let feature = "";
    if (String(pkg.scope).startsWith("env:")) environment = pkg.scope.slice(4);
    else if (String(pkg.scope).startsWith("feature:")) feature = pkg.scope.slice(8);
    else if (pkg.scope === "base") environment = "";
    else {
      toast(t("Transitive dependencies cannot be removed."), "error");
      return;
    }
    if (!confirm(t("Remove {}?", pkg.name))) return;
    try {
      addJob(await api("/api/jobs", {
        method: "POST",
        body: { kind: "remove", specs: [pkg.name], environment, feature },
      }));
    } catch (error) {
      toast(error.message, "error");
    }
  }

  function renderTasks() {
    const root = $("#task-list");
    const tasks = state.data?.tasks || [];
    $("#task-hint").textContent = state.data?.opened
      ? `${state.data.environment}`
      : t("Open a workspace first.");
    if (!tasks.length) {
      root.innerHTML = `<div class="muted">${escapeHtml(t("No tasks in this environment"))}</div>`;
      return;
    }
    root.innerHTML = tasks.map((task) => `
      <div class="task-card">
        <div class="task-main">
          <strong>${escapeHtml(task.name)}</strong>
          <code>${escapeHtml(task.cmd || "")}</code>
        </div>
        <div class="task-actions">
          <button class="button button-primary button-small" data-task="${escapeAttr(task.name)}" data-terminal="0">${escapeHtml(t("Run"))}</button>
          <button class="button button-small" data-args="${escapeAttr(task.name)}">${escapeHtml(t("Run with Arguments"))}</button>
          <button class="button button-small" data-task="${escapeAttr(task.name)}" data-terminal="1">${escapeHtml(t("Run in Terminal"))}</button>
        </div>
      </div>`).join("");
    root.querySelectorAll("[data-task]").forEach((button) => {
      button.onclick = () => runTask(button.dataset.task, button.dataset.terminal === "1");
    });
    root.querySelectorAll("[data-args]").forEach((button) => {
      button.onclick = () => openTaskArgs(button.dataset.args);
    });
  }

  function openTaskArgs(name) {
    const modal = openModal(`
      <h2>${escapeHtml(t("Run with Arguments"))}: ${escapeHtml(name)}</h2>
      <div class="form-grid">
        <label>${escapeHtml(t("Arguments"))}</label>
        <input id="task-args-input" type="text">
      </div>
      <div class="modal-actions">
        <button class="button" data-close>${escapeHtml(t("Cancel"))}</button>
        <button class="button button-primary" id="task-args-run">${escapeHtml(t("Run"))}</button>
      </div>`);
    $("#task-args-run", modal).onclick = async () => {
      try {
        addJob(await api("/api/jobs", {
          method: "POST",
          body: { kind: "task", name, args: $("#task-args-input", modal).value, terminal: false },
        }));
        closeModal(modal);
      } catch (error) {
        toast(error.message, "error");
      }
    };
  }

  function renderEditorPath() {
    $("#editor-path").textContent = state.data?.manifest || "pixi.toml";
  }

  async function loadEditor() {
    try {
      const result = await api("/api/editor");
      $("#editor-text").value = result.content || "";
      $("#editor-path").textContent = result.path || "pixi.toml";
      state.editorManifest = result.path || "";
      $("#editor-status").textContent = "";
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function saveEditor() {
    try {
      await api("/api/editor", {
        method: "PUT",
        body: { content: $("#editor-text").value },
      });
      $("#editor-status").textContent = t("Saved");
      toast(t("Saved"));
      await refreshWorkspace();
      state.editorManifest = state.data?.manifest || "";
    } catch (error) {
      toast(error.message, "error");
    }
  }

  function openNewWorkspace() {
    const initial = $("#workspace-path").value.trim();
    const modal = openModal(`
      <h2>${escapeHtml(t("New Workspace"))}</h2>
      <div class="form-grid">
        <label>${escapeHtml(t("Directory"))}</label>
        <input id="new-path" type="text" value="${escapeAttr(initial)}" placeholder="C:\\path\\to\\workspace">
        <label>${escapeHtml(t("Channels"))}</label>
        <input id="new-channels" type="text" value="conda-forge">
        <label>${escapeHtml(t("Platforms"))}</label>
        <input id="new-platforms" type="text" value="win-64">
      </div>
      <p class="muted">${escapeHtml(t("Creates only pixi.toml. The workspace opens in Base dependencies view."))}</p>
      <div class="modal-actions">
        <button class="button" data-close>${escapeHtml(t("Cancel"))}</button>
        <button class="button button-primary" id="new-create">${escapeHtml(t("Create"))}</button>
      </div>`);
    $("#new-create", modal).onclick = async () => {
      const path = $("#new-path", modal).value.trim();
      if (!path) return;
      try {
        const job = await api("/api/jobs", {
          method: "POST",
          body: {
            kind: "create_workspace",
            path,
            channels: $("#new-channels", modal).value.split(/[,;\s]+/).filter(Boolean),
            platforms: $("#new-platforms", modal).value.split(/[,;\s]+/).filter(Boolean),
          },
        });
        addJob(job);
        closeModal(modal);
      } catch (error) {
        toast(error.message, "error");
      }
    };
  }

  function addJob(job) {
    if (!job || !job.id) return;
    state.jobs.set(job.id, {
      id: job.id,
      title: job.title || `Job ${job.id}`,
      lines: [],
      offset: 0,
      done: false,
      returncode: null,
      createManifest: job.manifest || "",
    });
    state.activeJob = job.id;
    renderOutputTabs();
    selectOutput(job.id);
    if (!state.pollTimer) {
      state.pollTimer = setInterval(pollJobs, 500);
    }
  }

  async function pollJobs() {
    let active = false;
    for (const job of state.jobs.values()) {
      if (job.done) continue;
      active = true;
      try {
        const result = await api(`/api/jobs/${job.id}?offset=${job.offset}`);
        if (result.lines?.length) {
          job.lines.push(...result.lines);
          job.offset = result.next;
          if (state.activeJob === job.id) renderOutputLog();
        }
        if (result.done) {
          job.done = true;
          job.returncode = result.returncode;
          if (result.title) job.title = result.title;
          renderOutputTabs();
          if (result.returncode === 0 && job.createManifest) {
            await openWorkspace(job.createManifest);
          } else {
            await refreshWorkspace();
          }
        }
      } catch {
        job.done = true;
      }
    }
    if (!active) {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
  }

  function renderOutputTabs() {
    const root = $("#output-tabs");
    root.innerHTML = Array.from(state.jobs.values()).map((job) => `
      <button class="output-tab ${job.id === state.activeJob ? "active" : ""}" data-job="${job.id}">
        ${job.done ? (job.returncode === 0 ? "✓ " : "✗ ") : "● "}${escapeHtml(job.title)}
      </button>`).join("");
    root.querySelectorAll("[data-job]").forEach((button) => {
      button.onclick = () => selectOutput(Number(button.dataset.job));
    });
    $("#output-idle").textContent = Array.from(state.jobs.values()).some((job) => !job.done)
      ? t("Running")
      : t("Idle");
  }

  function selectOutput(jobId) {
    state.activeJob = jobId;
    renderOutputTabs();
    renderOutputLog();
  }

  function renderOutputLog() {
    const job = state.jobs.get(state.activeJob);
    const log = $("#output-log");
    log.textContent = job ? job.lines.join("\n") : "";
    log.scrollTop = log.scrollHeight;
  }

  async function stopActiveJob() {
    if (!state.activeJob) return;
    try {
      await api(`/api/jobs/${state.activeJob}/stop`, { method: "POST", body: {} });
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function stopAllJobs() {
    try {
      await api("/api/jobs/stop_all", { method: "POST", body: {} });
    } catch (error) {
      toast(error.message, "error");
    }
  }

  function closeFinished() {
    for (const [id, job] of state.jobs) {
      if (job.done) state.jobs.delete(id);
    }
    if (!state.jobs.has(state.activeJob)) state.activeJob = state.jobs.keys().next().value || null;
    renderOutputTabs();
    renderOutputLog();
  }

  function setTab(name) {
    state.activeTab = name;
    $$(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === name));
    $$(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.id === `tab-${name}`));
    if (
      name === "editor" &&
      state.data?.opened &&
      state.editorManifest !== state.data.manifest
    ) {
      loadEditor();
    }
  }

  function openModal(content) {
    const root = $("#modal-root");
    root.innerHTML = `<div class="modal">${content}</div>`;
    root.classList.add("open");
    $$("[data-close]", root).forEach((button) => {
      button.onclick = () => closeModal(root);
    });
    root.onclick = (event) => {
      if (event.target === root) closeModal(root);
    };
    return root;
  }

  function closeModal(root = $("#modal-root")) {
    root.classList.remove("open");
    root.innerHTML = "";
  }

  async function logout(event) {
    event.preventDefault();
    try {
      await fetch("/logout", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded", "X-CSRF-Token": csrf },
        body: "csrf=" + encodeURIComponent(csrf),
      });
    } finally {
      window.location.href = "/login";
    }
  }

  function applyTheme(theme, persist = true) {
    state.theme = theme === "dark" ? "dark" : "light";
    document.documentElement.dataset.theme = state.theme;
    $("#theme-label").textContent = t(state.theme === "dark" ? "Dark" : "Light");
    if (persist) {
      api("/api/settings", {
        method: "POST",
        body: { theme: state.theme },
      }).catch((error) => toast(error.message, "error"));
    }
  }

  function toggleTheme() {
    applyTheme(state.theme === "dark" ? "light" : "dark");
  }

  function toggleSidebar() {
    $("#app-shell").classList.toggle("sidebar-collapsed");
  }

  function toggleOutput() {
    $("#output-panel").classList.toggle("collapsed");
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function escapeAttr(value) {
    return escapeHtml(value).replaceAll("'", "&#39;");
  }

  async function init() {
    try {
      const session = await api("/api/session");
      state.language = session.language || state.language;
      state.theme = session.theme === "dark" ? "dark" : "light";
      applyTheme(state.theme, false);
      await loadLanguage(state.language, false);
      state.data = await api("/api/workspace");
      if (!state.data?.opened) {
        try {
          state.data = await api("/api/workspace/auto-open", {
            method: "POST",
            body: {},
          });
        } catch (error) {
          toast(error.message, "error");
        }
      }
      renderAll();
      if (state.data?.opened) loadEditor();
    } catch (error) {
      toast(error.message, "error");
    }

    $("#open-workspace").onclick = () => openWorkspace($("#workspace-path").value.trim());
    $("#new-workspace").onclick = openNewWorkspace;
    $("#workspace-path").addEventListener("keydown", (event) => {
      if (event.key === "Enter") openWorkspace($("#workspace-path").value.trim());
    });
    $("#refresh-workspace").onclick = refreshWorkspace;
    $("#manage-environments").onclick = openEnvironmentManager;
    $("#open-settings").onclick = openSettings;
    $("#theme-toggle").onclick = toggleTheme;
    $("#sidebar-collapse").onclick = toggleSidebar;
    $("#sidebar-handle").onclick = toggleSidebar;
    $("#toggle-output").onclick = toggleOutput;
    $("#language-select").onchange = (event) => loadLanguage(event.target.value);
    $("#logout-form").addEventListener("submit", logout);
    $("#install-env").onclick = installEnvironment;
    $("#query-latest").onclick = queryLatest;
    $("#check-compatible").onclick = checkCompatible;
    $("#add-package").onclick = openAddPackage;
    $("#remove-package").onclick = removeSelected;
    $("#update-package").onclick = () => updateSelected(false);
    $("#upgrade-package").onclick = () => updateSelected(true);
    $("#run-python").onclick = () => runPython(false);
    $("#run-python-terminal").onclick = () => runPython(true);
    $("#run-command").onclick = () => runCommand(false);
    $("#run-command-terminal").onclick = () => runCommand(true);
    $("#reload-editor").onclick = loadEditor;
    $("#save-editor").onclick = saveEditor;
    $("#stop-job").onclick = stopActiveJob;
    $("#stop-all").onclick = stopAllJobs;
    $("#close-finished").onclick = closeFinished;
    $$(".tab").forEach((tab) => {
      tab.onclick = () => setTab(tab.dataset.tab);
    });
    $$('input[name="package-filter"]').forEach((node) => {
      node.onchange = renderPackages;
    });
    $("#package-search").addEventListener("input", renderPackages);
    $("#package-kind").onchange = renderPackages;
    document.addEventListener("keydown", (event) => {
      if (!(event.ctrlKey || event.metaKey)) return;
      if (event.key.toLowerCase() === "b") {
        event.preventDefault();
        toggleSidebar();
      } else if (event.key.toLowerCase() === "j") {
        event.preventDefault();
        toggleOutput();
      }
    });
  }

  init();
})();
