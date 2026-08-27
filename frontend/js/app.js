/**
 * TribalWars Bot - Controlador Principal da Aplicação Desktop / Web
 */

document.addEventListener("DOMContentLoaded", async () => {
  console.log("A inicializar TribalWars Bot Cockpit...");

  // Estado Local
  const state = {
    connected: false,
    schedulerRunning: true,
    captchaActive: false,
    village: null,
    resources: null,
    queue: [],
    army: {},
    logs: [],
    autoScrollLogs: true,
    logFilter: "ALL",
    logSearch: "",
  };

  // Referências DOM
  const elements = {
    // Top Bar
    badgeWorld: document.getElementById("badge-world"),
    badgeStatus: document.getElementById("badge-status"),
    statusText: document.getElementById("status-text"),
    btnToggleScheduler: document.getElementById("btn-toggle-scheduler"),
    btnRenewSession: document.getElementById("btn-renew-session"),
    btnBuildNow: document.getElementById("btn-build-now"),
    btnFarmNow: document.getElementById("btn-farm-now"),
    btnRecruitNow: document.getElementById("btn-recruit-now"),

    // Village Card
    villageName: document.getElementById("village-name"),
    villageCoords: document.getElementById("village-coords"),
    storageCapacity: document.getElementById("storage-capacity"),
    // Resources
    resWoodVal: document.getElementById("res-wood-val"),
    resWoodBar: document.getElementById("res-wood-bar"),
    resStoneVal: document.getElementById("res-stone-val"),
    resStoneBar: document.getElementById("res-stone-bar"),
    resIronVal: document.getElementById("res-iron-val"),
    resIronBar: document.getElementById("res-iron-bar"),
    resPopVal: document.getElementById("res-pop-val"),
    resPopBar: document.getElementById("res-pop-bar"),
    // Building Queue
    queueContainer: document.getElementById("queue-container"),
    queueCount: document.getElementById("queue-count"),
    nextTargetBox: document.getElementById("next-target-box"),
    nextTargetName: document.getElementById("next-target-name"),
    nextTargetCost: document.getElementById("next-target-cost"),
    // Army Matrix
    armySpear: document.getElementById("army-spear"),
    armySword: document.getElementById("army-sword"),
    armyAxe: document.getElementById("army-axe"),
    armySpy: document.getElementById("army-spy"),
    armyLight: document.getElementById("army-light"),
    // Terminal
    terminalLogs: document.getElementById("terminal-logs"),
    btnClearLogs: document.getElementById("btn-clear-logs"),
    btnAutoScroll: document.getElementById("btn-autoscroll"),
    inputSearchLogs: document.getElementById("search-logs"),
    selectLogFilter: document.getElementById("filter-log-level"),
    // Modals
    captchaModal: document.getElementById("captcha-modal"),
    btnResolveCaptcha: document.getElementById("btn-resolve-captcha"),
    btnOpenTwWindow: document.getElementById("btn-open-tw-window"),
    // Tabs
    navTabs: document.querySelectorAll(".nav-tab"),
    tabContents: document.querySelectorAll(".tab-content"),
    // Settings Form
    settingsForm: document.getElementById("settings-form"),
    btnSaveSettings: document.getElementById("btn-save-settings"),
  };

  // --- 1. Gestão de Abas / Navegação ---
  elements.navTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      elements.navTabs.forEach((t) => t.classList.remove("active"));
      elements.tabContents.forEach((c) => c.classList.remove("active"));

      tab.classList.add("active");
      const targetId = tab.getAttribute("data-tab");
      const targetContent = document.getElementById(targetId);
      if (targetContent) {
        targetContent.classList.add("active");
      }

      if (targetId === "tab-settings") {
        loadSettingsIntoForm();
      }
    });
  });

  // --- 2. Inicialização de Autenticação e WebSockets ---
  try {
    const token = await window.api.discoverAuth();
    if (!token) {
      addLogEntry("WARNING", "app", "Token não detetado automaticamente. A aguardar servidor Sidecar...");
    } else {
      addLogEntry("INFO", "app", `Sessão Sidecar descoberta com sucesso.`);
    }

    // Liga WebSocket
    window.wsClient.connect(window.api.baseUrl, token);
  } catch (err) {
    console.error("Erro na inicialização:", err);
    addLogEntry("CRITICAL", "app", `Falha ao conectar à API: ${err.message}`);
  }

  // --- 3. Escuta de Eventos WebSocket ---
  window.wsClient.on("status", ({ connected }) => {
    state.connected = connected;
    updateTopBar();
    if (connected) {
      addLogEntry("SUCCESS", "ws", "Canal de telemetria em tempo real ativado.");
      refreshStatus();
    } else {
      addLogEntry("WARNING", "ws", "Canal de telemetria desconectado. A tentar reconectar...");
    }
  });

  window.wsClient.on("log", (logData) => {
    addLogEntry(logData.level, logData.logger, logData.message);
  });

  window.wsClient.on("state", (stateData) => {
    applyStateData(stateData);
  });

  window.wsClient.on("captcha", (alertData) => {
    state.captchaActive = true;
    updateTopBar();
    elements.captchaModal.classList.add("active");
    addLogEntry("CRITICAL", "anti-bot", "ALERTA ANTI-BOT RECEBIDO! Resolução necessária!");
  });

  // --- 4. Renderização Reativa da Interface ---
  function updateTopBar() {
    if (state.captchaActive) {
      elements.badgeStatus.className = "badge badge-status alert";
      elements.statusText.textContent = "ALERTA ANTI-BOT";
    } else if (!state.connected) {
      elements.badgeStatus.className = "badge badge-status paused";
      elements.statusText.textContent = "DESCONECTADO";
    } else if (state.schedulerRunning) {
      elements.badgeStatus.className = "badge badge-status active";
      elements.statusText.textContent = "MOTOR ATIVO";
    } else {
      elements.badgeStatus.className = "badge badge-status paused";
      elements.statusText.textContent = "MOTOR PAUSADO";
    }

    elements.btnToggleScheduler.innerHTML = state.schedulerRunning
      ? "<span>⏸</span> Pausar"
      : "<span>▶</span> Retomar";
    elements.btnToggleScheduler.className = state.schedulerRunning
      ? "btn btn-warning"
      : "btn btn-primary";
  }

  function applyStateData(data) {
    if (!data) return;

    // Scheduler
    if (data.scheduler) {
      state.schedulerRunning = data.scheduler.running;
      updateTopBar();
    }

    // Conta / Aldeia
    if (data.account) {
      elements.badgeWorld.textContent = (data.account.world || "PT117").toUpperCase();
      const v = data.account.village || {};
      if (v.name || data.account.village_name) {
        elements.villageName.textContent = v.name || data.account.village_name;
      }
      if (v.coordinates) {
        elements.villageCoords.textContent = `(${v.coordinates})`;
      } else if (data.account.coordinates) {
        elements.villageCoords.textContent = `(${data.account.coordinates.x}|${data.account.coordinates.y})`;
      }

      // Seletor Multi-Aldeia
      const vSelect = document.getElementById("village-selector");
      if (vSelect && data.account.villages && data.account.villages.length > 1) {
        vSelect.style.display = "inline-block";
        const currentVId = v.id || data.account.current_village_id;
        vSelect.innerHTML = data.account.villages
          .map(
            (vill) =>
              `<option value="${vill.id}" ${vill.id === currentVId ? "selected" : ""}>${vill.name} (${vill.coordinates})</option>`
          )
          .join("");
      } else if (vSelect) {
        vSelect.style.display = "none";
      }
    }


    // Recursos
    if (data.resources) {
      const r = data.resources;
      const maxStorage = r.storage_max || 1000;
      elements.storageCapacity.textContent = maxStorage.toLocaleString();

      // Madeira
      const woodPct = Math.min(100, Math.round((r.wood / maxStorage) * 100));
      elements.resWoodVal.textContent = Math.floor(r.wood).toLocaleString();
      elements.resWoodBar.style.width = `${woodPct}%`;

      // Argila / Pedra
      const stonePct = Math.min(100, Math.round((r.stone / maxStorage) * 100));
      elements.resStoneVal.textContent = Math.floor(r.stone).toLocaleString();
      elements.resStoneBar.style.width = `${stonePct}%`;

      // Ferro
      const ironPct = Math.min(100, Math.round((r.iron / maxStorage) * 100));
      elements.resIronVal.textContent = Math.floor(r.iron).toLocaleString();
      elements.resIronBar.style.width = `${ironPct}%`;

      // População
      const maxPop = r.pop_max || 240;
      const popPct = Math.min(100, Math.round((r.pop / maxPop) * 100));
      elements.resPopVal.textContent = `${r.pop} / ${maxPop} (${r.free_pop} livres)`;
      elements.resPopBar.style.width = `${popPct}%`;
    }

    // Módulo de Construção
    if (data.modules && data.modules.building) {
      const bMod = data.modules.building;
      renderBuildQueue(bMod.queue || []);
    }
  }

  function renderBuildQueue(queue) {
    state.queue = queue;
    elements.queueCount.textContent = `(${queue.length}/2)`;

    if (!queue || queue.length === 0) {
      elements.queueContainer.innerHTML = `
        <div class="queue-empty-state">
          <span>Sem construções em fila. O bot avaliará novos edifícios no próximo ciclo.</span>
        </div>
      `;
      return;
    }

    elements.queueContainer.innerHTML = queue
      .map(
        (item) => `
        <div class="queue-item" data-order-id="${item.order_id}">
          <div class="queue-building-info">
            <div class="queue-icon">🏛</div>
            <div>
              <div class="queue-name">${item.building} (Nível ${item.target_level})</div>
              <div style="font-size: 0.75rem; color: var(--text-muted)">Ordem ID: ${item.order_id}</div>
            </div>
          </div>
          <div class="queue-timer" data-seconds="${parseTimerStringToSeconds(item.timer_str)}">
            ${item.timer_str || "A calcular..."}
          </div>
        </div>
      `
      )
      .join("");
  }

  function parseTimerStringToSeconds(timerStr) {
    if (!timerStr) return 0;
    const parts = timerStr.split(":").map(Number);
    if (parts.length === 3) {
      return parts[0] * 3600 + parts[1] * 60 + parts[2];
    } else if (parts.length === 2) {
      return parts[0] * 60 + parts[1];
    }
    return 0;
  }

  function formatSecondsToTimer(totalSeconds) {
    if (totalSeconds <= 0) return "0:00:00";
    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    const s = totalSeconds % 60;
    return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  }

  // Ticker decrescente de contagem de tempo da fila
  setInterval(() => {
    const timerEls = document.querySelectorAll(".queue-timer");
    timerEls.forEach((el) => {
      let secs = parseInt(el.getAttribute("data-seconds"), 10);
      if (secs > 0) {
        secs -= 1;
        el.setAttribute("data-seconds", secs);
        el.textContent = formatSecondsToTimer(secs);
      }
    });
  }, 1000);

  // --- 5. Terminal de Logs em Tempo Real ---
  function addLogEntry(level, loggerName, message) {
    const now = new Date();
    const timeStr = now.toTimeString().split(" ")[0];

    const entry = {
      level: level.toUpperCase(),
      logger: loggerName,
      message,
      time: timeStr,
    };

    state.logs.push(entry);
    if (state.logs.length > 500) {
      state.logs.shift();
    }

    renderLogEntry(entry);
  }

  function renderLogEntry(entry) {
    if (state.logFilter !== "ALL" && entry.level !== state.logFilter) {
      return;
    }
    if (state.logSearch && !entry.message.toLowerCase().includes(state.logSearch.toLowerCase())) {
      return;
    }

    const logEl = document.createElement("div");
    logEl.className = "log-entry";
    logEl.innerHTML = `
      <span class="log-time">${entry.time}</span>
      <span class="log-level ${entry.level}">${entry.level}</span>
      <span class="log-message">[${entry.logger}] ${escapeHtml(entry.message)}</span>
    `;

    elements.terminalLogs.appendChild(logEl);

    if (state.autoScrollLogs) {
      elements.terminalLogs.scrollTop = elements.terminalLogs.scrollHeight;
    }
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  // Controles do Terminal
  elements.btnClearLogs.addEventListener("click", () => {
    state.logs = [];
    elements.terminalLogs.innerHTML = "";
  });

  elements.btnAutoScroll.addEventListener("click", () => {
    state.autoScrollLogs = !state.autoScrollLogs;
    elements.btnAutoScroll.textContent = state.autoScrollLogs ? "Scroll: Ativo" : "Scroll: Pausado";
    elements.btnAutoScroll.className = state.autoScrollLogs ? "btn btn-secondary" : "btn btn-warning";
  });

  elements.selectLogFilter.addEventListener("change", (e) => {
    state.logFilter = e.target.value;
    refreshTerminalView();
  });

  elements.inputSearchLogs.addEventListener("input", (e) => {
    state.logSearch = e.target.value;
    refreshTerminalView();
  });

  function refreshTerminalView() {
    elements.terminalLogs.innerHTML = "";
    state.logs.forEach(renderLogEntry);
  }

  // --- 6. Ações Manuais e Botões da Barra Superior ---
  elements.btnToggleScheduler.addEventListener("click", async () => {
    try {
      if (state.schedulerRunning) {
        await window.api.pauseScheduler();
        addLogEntry("WARNING", "app", "Comando enviado: Motor de agendamento PAUSADO.");
      } else {
        await window.api.resumeScheduler();
        addLogEntry("SUCCESS", "app", "Comando enviado: Motor de agendamento RETOMADO.");
      }
      refreshStatus();
    } catch (e) {
      alert(`Falha ao alterar estado do motor: ${e.message}`);
    }
  });

  elements.btnRenewSession?.addEventListener("click", async () => {
    try {
      addLogEntry("INFO", "auth", "A abrir ecrã do Tribal Wars para login manual...");
      elements.btnRenewSession.disabled = true;
      elements.btnRenewSession.textContent = "A abrir...";
      const res = await window.api.renewSession();
      if (res.status === "success" || res.status === "ok") {
        addLogEntry("SUCCESS", "auth", res.message || "A navegar para a página de login...");
        await loadSettingsIntoForm();
        refreshStatus();
      } else {
        addLogEntry("WARNING", "auth", res.message || "Não foi possível abrir o ecrã de login.");
      }
    } catch (e) {
      addLogEntry("CRITICAL", "auth", `Erro: ${e.message}`);
    } finally {
      elements.btnRenewSession.disabled = false;
      elements.btnRenewSession.innerHTML = "<span>🔑</span> Entrar / Login";
    }
  });


  elements.btnBuildNow.addEventListener("click", async () => {
    try {
      addLogEntry("INFO", "app", "Disparo manual: A iniciar ciclo de construção...");
      const res = await window.api.triggerBuild();
      addLogEntry("SUCCESS", "app", res.message || "Ciclo de construção despachado!");
      refreshStatus();
    } catch (e) {
      alert(`Erro: ${e.message}`);
    }
  });

  elements.btnFarmNow.addEventListener("click", async () => {
    try {
      addLogEntry("INFO", "app", "Disparo manual: A iniciar onda de farm...");
      const res = await window.api.triggerFarm();
      addLogEntry("SUCCESS", "app", res.message || "Onda de farm disparada!");
    } catch (e) {
      alert(`Erro: ${e.message}`);
    }
  });

  elements.btnRecruitNow.addEventListener("click", async () => {
    try {
      addLogEntry("INFO", "app", "Disparo manual: A iniciar ciclo de recrutamento...");
      const res = await window.api.triggerRecruit();
      addLogEntry("SUCCESS", "app", res.message || "Ciclo de recrutamento despachado!");
    } catch (e) {
      alert(`Erro: ${e.message}`);
    }
  });

  // Modal Captcha
  elements.btnResolveCaptcha.addEventListener("click", async () => {
    try {
      await window.api.resumeBotProtection();
      state.captchaActive = false;
      elements.captchaModal.classList.remove("active");
      updateTopBar();
      addLogEntry("SUCCESS", "anti-bot", "Alerta anti-bot limpo pelo utilizador. Motor retomado.");
    } catch (e) {
      alert(`Erro ao retomar: ${e.message}`);
    }
  });

  elements.btnOpenTwWindow.addEventListener("click", () => {
    window.open("https://pt117.tribalwars.com.pt/game.php", "_blank");
  });

  // Seletor Multi-Aldeia
  document.getElementById("village-selector")?.addEventListener("change", async (e) => {
    const vId = e.target.value;
    try {
      addLogEntry("INFO", "account", `A alternar para a aldeia ${vId}...`);
      const res = await window.api.switchVillage(vId);
      if (res.status === "success") {
        addLogEntry("SUCCESS", "account", res.message || "Aldeia alternada!");
        refreshStatus();
      } else {
        addLogEntry("WARNING", "account", res.message || "Falha ao alternar aldeia.");
      }
    } catch (err) {
      addLogEntry("CRITICAL", "account", `Erro ao alternar aldeia: ${err.message}`);
    }
  });

  // Teste de Proxy
  document.getElementById("btn-test-proxy")?.addEventListener("click", async () => {
    const proxyVal = document.getElementById("cfg-proxy").value.trim();
    const resultSpan = document.getElementById("proxy-test-result");
    if (!proxyVal) {
      resultSpan.innerHTML = "<span style='color: var(--neon-crimson)'>Indique um proxy para testar.</span>";
      return;
    }
    resultSpan.innerHTML = "<span style='color: var(--neon-cyan)'>A testar conexão...</span>";
    try {
      const res = await window.api.testProxy(proxyVal);
      if (res.status === "online") {
        resultSpan.innerHTML = `<span style='color: var(--neon-emerald)'>✅ Online (IP: ${res.ip}, Latência: ${res.latency_ms}ms)</span>`;
      } else {
        resultSpan.innerHTML = `<span style='color: var(--neon-crimson)'>❌ Erro: ${res.error || res.status}</span>`;
      }
    } catch (err) {
      resultSpan.innerHTML = `<span style='color: var(--neon-crimson)'>❌ Falha: ${err.message}</span>`;
    }
  });

  // --- 7. Painel de Definições ---
  async function loadSettingsIntoForm() {
    try {
      const config = await window.api.getConfig();
      if (!config) return;

      document.getElementById("cfg-world").value = config.world || "pt117";
      document.getElementById("cfg-sid").value = config.sid || "";
      if (document.getElementById("cfg-proxy")) {
        document.getElementById("cfg-proxy").value = config.proxy || "";
      }
      if (config.auth) {
        document.getElementById("cfg-username").value = config.auth.username || "";
        document.getElementById("cfg-auto-login").checked = !!config.auth.auto_login;
        document.getElementById("cfg-keep-alive").checked = config.auth.keep_alive !== false;
      }
      if (config.building) {
        document.getElementById("cfg-building-template").value = config.building.template || "rush_resources";
        document.getElementById("cfg-max-queue").value = config.building.max_queue || 2;
        document.getElementById("cfg-build-interval").value = config.building.interval_seconds || 75;
      }
      if (config.farm) {
        document.getElementById("cfg-farm-enabled").checked = !!config.farm.enabled;
        document.getElementById("cfg-farm-interval").value = config.farm.interval_minutes || 5;
      }
    } catch (e) {
      console.warn("Falha ao carregar configurações:", e);
    }
  }

  elements.btnSaveSettings.addEventListener("click", async (e) => {
    e.preventDefault();
    try {
      const pwdVal = document.getElementById("cfg-password").value.trim();
      const proxyVal = document.getElementById("cfg-proxy") ? document.getElementById("cfg-proxy").value.trim() : "";
      const payload = {
        world: document.getElementById("cfg-world").value.trim(),
        sid: document.getElementById("cfg-sid").value.trim(),
        proxy: proxyVal || null,
        auth: {
          username: document.getElementById("cfg-username").value.trim(),
          auto_login: document.getElementById("cfg-auto-login").checked,
          keep_alive: document.getElementById("cfg-keep-alive").checked,
        },
        building: {
          template: document.getElementById("cfg-building-template").value,
          max_queue: parseInt(document.getElementById("cfg-max-queue").value, 10),
          interval_seconds: parseFloat(document.getElementById("cfg-build-interval").value),
        },
        farm: {
          enabled: document.getElementById("cfg-farm-enabled").checked,
          interval_minutes: parseFloat(document.getElementById("cfg-farm-interval").value),
        },
      };

      if (pwdVal) {
        payload.auth.password = pwdVal;
      }

      await window.api.updateConfig(payload);
      addLogEntry("SUCCESS", "settings", "Configurações gravadas com sucesso no config.json.");
      alert("Configurações atualizadas com sucesso!");
    } catch (err) {
      alert(`Falha ao gravar configurações: ${err.message}`);
    }
  });



  async function refreshStatus() {
    try {
      const statusData = await window.api.getStatus();
      applyStateData(statusData);
    } catch (e) {
      // Sidecar ainda pode estar a iniciar
    }
  }

  // Polling de segurança a cada 15 segundos para atualizar dados
  setInterval(refreshStatus, 15000);
});
