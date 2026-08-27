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
    // Top Bar & World Dropdown
    badgeWorld: document.getElementById("badge-world"),
    badgeWorldText: document.getElementById("badge-world-text"),
    btnWorldDropdown: document.getElementById("btn-world-dropdown"),
    worldDropdownMenu: document.getElementById("world-dropdown-menu"),
    worldDropdownList: document.getElementById("world-dropdown-list"),
    btnDropdownAddWorld: document.getElementById("btn-dropdown-add-world"),
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
    // Quick Actions & Quests
    btnRefreshData: document.getElementById("btn-refresh-data"),
    btnClaimQuests: document.getElementById("btn-claim-quests"),
    badgeQuestCount: document.getElementById("badge-quest-count"),
    // Army Matrix (12 Unidades Oficiais)
    armySpear: document.getElementById("army-spear"),
    armySword: document.getElementById("army-sword"),
    armyAxe: document.getElementById("army-axe"),
    armyArcher: document.getElementById("army-archer"),
    armySpy: document.getElementById("army-spy"),
    armyLight: document.getElementById("army-light"),
    armyMarcher: document.getElementById("army-marcher"),
    armyHeavy: document.getElementById("army-heavy"),
    armyRam: document.getElementById("army-ram"),
    armyCatapult: document.getElementById("army-catapult"),
    armyKnight: document.getElementById("army-knight"),
    armySnob: document.getElementById("army-snob"),
    // Tactical Map
    mapCenterX: document.getElementById("map-center-x"),
    mapCenterY: document.getElementById("map-center-y"),
    mapRadius: document.getElementById("map-radius"),
    btnMapMyVillage: document.getElementById("btn-map-my-village"),
    btnMapScan: document.getElementById("btn-map-scan"),
    btnMapFarmNearby: document.getElementById("btn-map-farm-nearby"),
    btnRefreshBarbs: document.getElementById("btn-refresh-barbs"),
    tacticalMapCanvas: document.getElementById("tactical-map-canvas"),
    mapTooltip: document.getElementById("map-tooltip"),
    mapStatsText: document.getElementById("map-stats-text"),
    barbCountBadge: document.getElementById("barb-count-badge"),
    barbariansTableBody: document.getElementById("barbarians-table-body"),
    // Map Navigator HUD
    btnNavN: document.getElementById("btn-nav-n"),
    btnNavS: document.getElementById("btn-nav-s"),
    btnNavW: document.getElementById("btn-nav-w"),
    btnNavE: document.getElementById("btn-nav-e"),
    btnNavCenter: document.getElementById("btn-nav-center"),
    btnZoomIn: document.getElementById("btn-zoom-in"),
    btnZoomOut: document.getElementById("btn-zoom-out"),
    // Selected Village Card
    selectedVillageCard: document.getElementById("selected-village-card"),
    selectedVillageIcon: document.getElementById("selected-village-icon"),
    selectedVillageName: document.getElementById("selected-village-name"),
    selectedVillageCoords: document.getElementById("selected-village-coords"),
    selectedVillageBonus: document.getElementById("selected-village-bonus"),
    selectedVillageDist: document.getElementById("selected-village-dist"),
    selectedVillagePts: document.getElementById("selected-village-pts"),
    selectedVillagePlayer: document.getElementById("selected-village-player"),
    btnSelectedAttack: document.getElementById("btn-selected-attack"),
    btnSelectedCenter: document.getElementById("btn-selected-center"),
    btnSelectedCopy: document.getElementById("btn-selected-copy"),
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
    // Multi-World Orchestrator
    worldTabsContainer: document.getElementById("world-tabs-container"),
    btnAddWorld: document.getElementById("btn-add-world"),
    addWorldModal: document.getElementById("add-world-modal"),
    btnCancelAddWorld: document.getElementById("btn-cancel-add-world"),
    btnConfirmAddWorld: document.getElementById("btn-confirm-add-world"),
    inputWorldId: document.getElementById("input-world-id"),
    inputWorldSid: document.getElementById("input-world-sid"),
    inputWorldDomain: document.getElementById("input-world-domain"),
    inputWorldProxy: document.getElementById("input-world-proxy"),
    // Multi-Village & Categorization
    btnSyncAllVillages: document.getElementById("btn-sync-all-villages"),
    btnRunAllCycle: document.getElementById("btn-run-all-cycle"),
    villagesTableBody: document.getElementById("villages-table-body"),
    balanceAnalysisContainer: document.getElementById("balance-analysis-container"),
    aggWood: document.getElementById("agg-wood"),
    aggStone: document.getElementById("agg-stone"),
    aggIron: document.getElementById("agg-iron"),
    aggVillagesCount: document.getElementById("agg-villages-count"),
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
      } else if (targetId === "tab-map") {
        loadMapGrid();
        loadMapBarbarians();
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

  window.wsClient.on("VILLAGE_UPDATED", (stateData) => {
    applyStateData(stateData);
  });

  window.wsClient.on("captcha", (alertData) => {
    state.captchaActive = true;
    updateTopBar();
    elements.captchaModal.classList.add("active");
    addLogEntry("CRITICAL", "anti-bot", "ALERTA ANTI-BOT RECEBIDO! Resolução necessária!");
  });

  window.wsClient.on("WORLDS_UPDATED", (data) => {
    if (data.worlds) renderWorldTabs(data.worlds, data.active_world || state.currentWorld);
  });

  window.wsClient.on("WORLD_SWITCHED", (data) => {
    if (data.status) updateDashboard(data.status);
    addLogEntry("INFO", "orchestrator", `Mundo focado alterado para '${data.active_world}'.`);
  });

  window.wsClient.on("VILLAGE_CATEGORY_UPDATED", (data) => {
    addLogEntry("INFO", "village", `Aldeia ${data.village_id} reclassificada como '${data.category}'.`);
  });

  window.wsClient.on("ALL_VILLAGES_CYCLE_DONE", (data) => {
    addLogEntry("SUCCESS", "village", `Ciclo global concluído: ${data.building_actions || 0} construções e ${data.recruitment_actions || 0} recrutamentos.`);
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
      ? "btn btn-warning btn-sm"
      : "btn btn-primary btn-sm";
  }

  const updateDashboard = (data) => applyStateData(data);

  function applyStateData(data) {
    if (!data) return;

    // Scheduler
    if (data.scheduler) {
      state.schedulerRunning = data.scheduler.running;
      updateTopBar();
    }

    // Conta / Aldeia
    if (data.account) {
      const activeW = (data.active_world || (data.account && data.account.world) || "pt117").toUpperCase();
      if (elements.badgeWorldText) {
        elements.badgeWorldText.textContent = activeW;
      } else if (elements.badgeWorld) {
        elements.badgeWorld.textContent = activeW;
      }
      renderWorldDropdown(data.worlds, activeW.toLowerCase());
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
    const r = data.resources || (data.account && data.account.village && data.account.village.resources);
    if (r) {
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
      elements.resPopVal.textContent = `${r.pop} / ${maxPop} (${r.free_pop || 0} livres)`;
      elements.resPopBar.style.width = `${popPct}%`;
    }

    // Tropas Disponíveis na Aldeia (12 Unidades)
    const troops = data.troops || (data.account && data.account.village && data.account.village.troops) || {};
    const unitMap = {
      spear: elements.armySpear,
      sword: elements.armySword,
      axe: elements.armyAxe,
      archer: elements.armyArcher,
      spy: elements.armySpy,
      light: elements.armyLight,
      marcher: elements.armyMarcher,
      heavy: elements.armyHeavy,
      ram: elements.armyRam,
      catapult: elements.armyCatapult,
      knight: elements.armyKnight,
      snob: elements.armySnob,
    };
    for (const [uKey, el] of Object.entries(unitMap)) {
      if (el) {
        const count = troops[uKey] || 0;
        el.textContent = count.toLocaleString();
        el.style.color = count > 0 ? "var(--neon-cyan)" : "var(--text-muted)";
      }
    }

    // Coordenadas padrão para o Mapa Tático
    const villObj = data.account?.village || {};
    if (villObj.x && villObj.y) {
      if (elements.mapCenterX && !elements.mapCenterX.value) {
        elements.mapCenterX.value = villObj.x;
      }
      if (elements.mapCenterY && !elements.mapCenterY.value) {
        elements.mapCenterY.value = villObj.y;
      }
      if (mapState.centerX === null) {
        mapState.centerX = villObj.x;
        mapState.centerY = villObj.y;
      }
    }

    // Módulo de Construção
    if (data.modules && data.modules.building) {
      const bMod = data.modules.building;
      renderBuildQueue(bMod.queue || []);
    }

    // Renderiza abas do Orquestrador Multi-Mundo
    if (data.worlds && elements.worldTabsContainer) {
      renderWorldTabs(data.worlds, data.active_world || (data.account && data.account.world));
    }

    // Renderiza Painel Multi-Aldeia e Balanceamento de Recursos
    if (data.account && data.account.villages) {
      renderVillagesOverview(data.account.villages, data.resource_balance);
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

  // --- Funções de Renderização Multi-Mundo & Dropdown ---
  const COMMON_WORLDS = ["pt114", "pt115", "pt116", "pt117", "pt118"];

  function renderWorldDropdown(worlds, activeWorld) {
    if (!elements.worldDropdownList) return;
    const currentW = (activeWorld || "pt117").toLowerCase();

    // Combina mundos registrados com mundos comuns (pt114, pt115, etc.)
    const registeredWorldKeys = (worlds || []).map(w => (w.world || "").toLowerCase());
    const allWorldKeys = Array.from(new Set([...registeredWorldKeys, ...COMMON_WORLDS]));

    elements.worldDropdownList.innerHTML = allWorldKeys.map(w => {
      const isCurrent = w === currentW;
      const isReg = registeredWorldKeys.includes(w);
      return `
        <div class="dropdown-world-item ${isCurrent ? 'active' : ''}" data-world="${w}" style="padding: 8px 14px; cursor: pointer; display: flex; align-items: center; justify-content: space-between; font-size: 0.82rem; transition: background 0.15s ease; color: ${isCurrent ? 'var(--neon-cyan)' : 'var(--text-main)'}; font-weight: ${isCurrent ? '700' : '500'}; background: ${isCurrent ? 'rgba(6,182,212,0.15)' : 'transparent'}; border-left: ${isCurrent ? '3px solid var(--neon-cyan)' : '3px solid transparent'};">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span>🌐</span>
            <span>${w.toUpperCase()}</span>
          </div>
          ${isCurrent ? '<span style="font-size: 0.65rem; background: var(--neon-cyan); color: #000; padding: 1px 6px; border-radius: 10px; font-weight: 700;">ATIVO</span>' : (isReg ? '<span style="font-size: 0.68rem; color: var(--neon-emerald); font-weight: 600;">Ligado</span>' : '<span style="font-size: 0.68rem; color: var(--text-muted);">Disponível</span>')}
        </div>
      `;
    }).join("");

    elements.worldDropdownList.querySelectorAll(".dropdown-world-item").forEach(item => {
      item.addEventListener("mouseenter", () => {
        if (!item.classList.contains("active")) item.style.background = "rgba(30, 41, 59, 0.7)";
      });
      item.addEventListener("mouseleave", () => {
        if (!item.classList.contains("active")) item.style.background = "transparent";
      });
      item.addEventListener("click", async () => {
        const targetWorld = item.getAttribute("data-world");
        if (elements.worldDropdownMenu) elements.worldDropdownMenu.style.display = "none";
        if (targetWorld && targetWorld !== currentW) {
          try {
            addLogEntry("INFO", "orchestrator", `A mudar para o mundo ${targetWorld.toUpperCase()}...`);
            if (elements.badgeWorldText) elements.badgeWorldText.textContent = targetWorld.toUpperCase();
            const res = await window.api.switchWorld(targetWorld);
            addLogEntry("SUCCESS", "orchestrator", res.message || `Mundo ${targetWorld.toUpperCase()} ativado.`);
            const status = await window.api.getStatus();
            updateDashboard(status);
          } catch (err) {
            addLogEntry("ERROR", "orchestrator", `Falha ao mudar para o mundo ${targetWorld}: ${err.message}`);
          }
        }
      });
    });
  }

  function renderWorldTabs(worlds, activeWorld) {
    if (!elements.worldTabsContainer) return;
    if (!worlds || worlds.length === 0) {
      elements.worldTabsContainer.innerHTML = `<span class="world-chip active">🌐 ${(activeWorld || 'pt117').toUpperCase()}</span>`;
      return;
    }

    elements.worldTabsContainer.innerHTML = worlds.map(w => {
      const isActive = w.world === activeWorld;
      return `
        <button class="world-chip ${isActive ? 'active' : ''}" data-world="${w.world}" title="Clique para focar no mundo ${w.world.toUpperCase()}">
          <span>🌐</span> ${w.world.toUpperCase()}
          ${w.villages_count ? `<span style="font-size:0.68rem; opacity:0.8;">(${w.villages_count} aldeias)</span>` : ''}
        </button>
      `;
    }).join("");

    elements.worldTabsContainer.querySelectorAll(".world-chip").forEach(btn => {
      btn.addEventListener("click", async () => {
        const targetWorld = btn.getAttribute("data-world");
        if (targetWorld && targetWorld !== activeWorld) {
          try {
            console.log(`A alternar para o mundo ${targetWorld}...`);
            await window.api.switchWorld(targetWorld);
            const status = await window.api.getStatus();
            updateDashboard(status);
          } catch (err) {
            console.error("Erro ao alternar mundo:", err);
          }
        }
      });
    });
  }

  // --- Funções de Renderização Multi-Aldeia & Categorização ---
  function renderVillagesOverview(villages, balance) {
    if (!elements.villagesTableBody) return;

    let totWood = 0;
    let totStone = 0;
    let totIron = 0;

    if (!villages || villages.length === 0) {
      elements.villagesTableBody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; padding: 24px; color: var(--text-muted);">
            Nenhuma aldeia carregada. Verifique se o bot está conectado ao jogo.
          </td>
        </tr>
      `;
      if (elements.aggVillagesCount) elements.aggVillagesCount.textContent = "0";
      return;
    }

    if (elements.aggVillagesCount) {
      elements.aggVillagesCount.textContent = villages.length.toString();
    }

    elements.villagesTableBody.innerHTML = villages.map(v => {
      const r = v.resources || {};
      totWood += r.wood || 0;
      totStone += r.stone || 0;
      totIron += r.iron || 0;

      const maxStorage = r.storage_max || 1000;
      const storagePct = Math.min(100, Math.round(((r.wood + r.stone + r.iron) / (maxStorage * 3)) * 100));
      const cat = v.category || "balanced";

      return `
        <tr style="border-bottom: 1px solid var(--border-subtle); transition: background 0.15s ease;" onmouseover="this.style.background='rgba(30,41,59,0.5)'" onmouseout="this.style.background='transparent'">
          <td style="padding: 10px 14px; font-weight: 600;">
            ${v.name || 'Aldeia'}
            ${state.village && state.village.id === v.id ? '<span style="color: var(--neon-cyan); font-size: 0.75rem; margin-left: 6px;">(Ativa)</span>' : ''}
          </td>
          <td style="padding: 10px 14px; font-family: var(--font-mono); color: var(--neon-cyan);">
            ${v.coordinates || `${v.x}|${v.y}`}
          </td>
          <td style="padding: 10px 14px;">
            <select class="form-control village-cat-select" data-village-id="${v.id}" style="padding: 3px 8px; font-size: 0.78rem; width: auto; font-weight: 600;">
              <option value="attack" ${cat === 'attack' ? 'selected' : ''}>⚔️ Ataque</option>
              <option value="defense" ${cat === 'defense' ? 'selected' : ''}>🛡️ Defesa</option>
              <option value="balanced" ${cat === 'balanced' ? 'selected' : ''}>⚖️ Balanceado</option>
            </select>
          </td>
          <td style="padding: 10px 14px; font-family: var(--font-mono);">
            <span style="color: #22c55e;">${Math.floor(r.wood || 0).toLocaleString()}</span> / 
            <span style="color: #06b6d4;">${Math.floor(r.stone || 0).toLocaleString()}</span> / 
            <span style="color: #cbd5e1;">${Math.floor(r.iron || 0).toLocaleString()}</span>
          </td>
          <td style="padding: 10px 14px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <div style="flex: 1; height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden; min-width: 60px;">
                <div style="width: ${storagePct}%; height: 100%; background: ${storagePct > 90 ? 'var(--neon-crimson)' : 'var(--neon-emerald)'};"></div>
              </div>
              <span style="font-size: 0.75rem; font-family: var(--font-mono); color: var(--text-muted);">${storagePct}%</span>
            </div>
          </td>
          <td style="padding: 10px 14px; font-family: var(--font-mono); color: var(--neon-gold);">
            ${r.free_pop !== undefined ? r.free_pop : '-'}
          </td>
          <td style="padding: 10px 14px; text-align: right;">
            <button class="btn btn-secondary btn-switch-v" data-village-id="${v.id}" style="padding: 3px 8px; font-size: 0.75rem;">
              Alternar
            </button>
          </td>
        </tr>
      `;
    }).join("");

    if (elements.aggWood) elements.aggWood.textContent = Math.floor(totWood).toLocaleString();
    if (elements.aggStone) elements.aggStone.textContent = Math.floor(totStone).toLocaleString();
    if (elements.aggIron) elements.aggIron.textContent = Math.floor(totIron).toLocaleString();

    elements.villagesTableBody.querySelectorAll(".village-cat-select").forEach(sel => {
      sel.addEventListener("change", async () => {
        const vid = sel.getAttribute("data-village-id");
        const newCat = sel.value;
        try {
          console.log(`A alterar categoria da aldeia ${vid} para ${newCat}...`);
          await window.api.setVillageCategory(vid, newCat);
        } catch (err) {
          console.error("Erro ao alterar categoria:", err);
        }
      });
    });

    elements.villagesTableBody.querySelectorAll(".btn-switch-v").forEach(btn => {
      btn.addEventListener("click", async () => {
        const vid = btn.getAttribute("data-village-id");
        try {
          await window.api.switchVillage(vid);
          const status = await window.api.getStatus();
          updateDashboard(status);
        } catch (err) {
          console.error("Erro ao alternar aldeia:", err);
        }
      });
    });

    if (elements.balanceAnalysisContainer) {
      if (!balance || !balance.averages) {
        elements.balanceAnalysisContainer.innerHTML = "<em>Sem dados suficientes de múltiplas aldeias para cálculo de desvio de recursos.</em>";
      } else {
        const donorsHtml = (balance.donors || []).map(d => `
          <div style="background: rgba(34,197,94,0.1); border: 1px solid rgba(34,197,94,0.3); border-radius: 6px; padding: 6px 10px; margin-top: 4px;">
            <strong>${d.name} (${d.coordinates})</strong>: Excedente de 
            <span style="color: #22c55e;">+${d.diff_wood} Madeira</span>, 
            <span style="color: #06b6d4;">+${d.diff_stone} Argila</span>, 
            <span style="color: #cbd5e1;">+${d.diff_iron} Ferro</span>
          </div>
        `).join("") || "<em>Nenhuma aldeia com excedente expressivo.</em>";

        const receiversHtml = (balance.receivers || []).map(r => `
          <div style="background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3); border-radius: 6px; padding: 6px 10px; margin-top: 4px;">
            <strong>${r.name} (${r.coordinates})</strong>: Défice de 
            <span style="color: #f87171;">${r.diff_wood} Madeira</span>, 
            <span style="color: #f87171;">${r.diff_stone} Argila</span>, 
            <span style="color: #f87171;">${r.diff_iron} Ferro</span>
          </div>
        `).join("") || "<em>Nenhuma aldeia em défice crítico.</em>";

        elements.balanceAnalysisContainer.innerHTML = `
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
            <div>
              <div style="font-weight: 700; color: #22c55e; margin-bottom: 6px;">📦 Aldeias Doadoras (Excedente / Armazém Cheio):</div>
              ${donorsHtml}
            </div>
            <div>
              <div style="font-weight: 700; color: #f87171; margin-bottom: 6px;">📥 Aldeias Recetoras (Défice de Recursos):</div>
              ${receiversHtml}
            </div>
          </div>
        `;
      }
    }
  }

  // --- Handlers de Ações Multi-Mundo & Multi-Aldeia ---
  if (elements.btnWorldDropdown && elements.worldDropdownMenu) {
    elements.btnWorldDropdown.addEventListener("click", (e) => {
      e.stopPropagation();
      const isVisible = elements.worldDropdownMenu.style.display === "block";
      elements.worldDropdownMenu.style.display = isVisible ? "none" : "block";
    });

    document.addEventListener("click", (e) => {
      if (elements.worldDropdownMenu && !elements.worldDropdownMenu.contains(e.target) && e.target !== elements.btnWorldDropdown) {
        elements.worldDropdownMenu.style.display = "none";
      }
    });
  }

  if (elements.btnDropdownAddWorld && elements.addWorldModal) {
    elements.btnDropdownAddWorld.addEventListener("click", () => {
      if (elements.worldDropdownMenu) elements.worldDropdownMenu.style.display = "none";
      elements.addWorldModal.style.display = "flex";
    });
  }

  // Chips Rápidos de Seleção de Mundo no Modal (ex: pt114, pt115, etc.)
  document.querySelectorAll(".btn-quick-world").forEach(btn => {
    btn.addEventListener("click", () => {
      const w = btn.getAttribute("data-world");
      if (elements.inputWorldId && w) {
        elements.inputWorldId.value = w;
        document.querySelectorAll(".btn-quick-world").forEach(b => {
          b.style.borderColor = "var(--border-glass)";
          b.style.color = "var(--text-muted)";
          b.style.background = "rgba(30,41,59,0.7)";
        });
        btn.style.borderColor = "var(--neon-cyan)";
        btn.style.color = "var(--neon-cyan)";
        btn.style.background = "rgba(6,182,212,0.15)";
      }
    });
  });

  if (elements.btnAddWorld && elements.addWorldModal) {
    elements.btnAddWorld.addEventListener("click", () => {
      elements.addWorldModal.style.display = "flex";
    });
  }

  if (elements.btnCancelAddWorld && elements.addWorldModal) {
    elements.btnCancelAddWorld.addEventListener("click", () => {
      elements.addWorldModal.style.display = "none";
    });
  }

  if (elements.btnConfirmAddWorld) {
    elements.btnConfirmAddWorld.addEventListener("click", async () => {
      const world = elements.inputWorldId.value.trim().toLowerCase();
      const sid = elements.inputWorldSid.value.trim();
      const domain = (elements.inputWorldDomain && elements.inputWorldDomain.value.trim()) || "tribalwars.com.pt";
      const proxy = (elements.inputWorldProxy && elements.inputWorldProxy.value.trim()) || null;

      if (!world) {
        alert("Por favor indique o identificador do mundo (ex: pt118).");
        return;
      }
      try {
        console.log(`A adicionar mundo ${world}...`);
        await window.api.registerWorld(world, sid, domain, proxy);
        elements.addWorldModal.style.display = "none";
        const status = await window.api.getStatus();
        updateDashboard(status);
      } catch (err) {
        alert(`Falha ao conectar novo mundo: ${err.message}`);
      }
    });
  }

  if (elements.btnSyncAllVillages) {
    elements.btnSyncAllVillages.addEventListener("click", async () => {
      try {
        console.log("A sincronizar todas as aldeias...");
        const res = await window.api.getAccountVillages();
        if (res && res.villages) {
          renderVillagesOverview(res.villages, res.balance);
        }
      } catch (err) {
        console.error("Erro ao sincronizar aldeias:", err);
      }
    });
  }

  if (elements.btnRunAllCycle) {
    elements.btnRunAllCycle.addEventListener("click", async () => {
      try {
        console.log("A disparar ciclo coordenado em todas as aldeias...");
        await window.api.triggerAllVillagesCycle();
        const status = await window.api.getStatus();
        updateDashboard(status);
      } catch (err) {
        console.error("Erro ao executar ciclo multi-aldeia:", err);
      }
    });
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

  elements.btnRefreshData?.addEventListener("click", async () => {
    try {
      elements.btnRefreshData.disabled = true;
      elements.btnRefreshData.innerHTML = "<span>⏳</span> A ler...";
      addLogEntry("INFO", "account", "A atualizar recursos e tropas disponíveis na aldeia...");
      const res = await window.api.refreshVillage();
      if (res && res.data) {
        applyStateData(res.data);
        addLogEntry("SUCCESS", "account", "Recursos e tropas atualizados com sucesso!");
      } else {
        await refreshStatus();
      }
      checkQuestStatus();
    } catch (err) {
      addLogEntry("WARNING", "account", `Falha ao atualizar dados: ${err.message}`);
    } finally {
      elements.btnRefreshData.disabled = false;
      elements.btnRefreshData.innerHTML = "<span>🔄</span> Atualizar";
    }
  });

  elements.btnClaimQuests?.addEventListener("click", async () => {
    try {
      elements.btnClaimQuests.disabled = true;
      elements.btnClaimQuests.innerHTML = "<span>⏳</span> A resgatar...";
      addLogEntry("INFO", "quest", "A resgatar recompensas de missões concluídas com salvaguarda de armazém...");
      const res = await window.api.claimAllQuests();
      if (res.status === "success") {
        const claimed = res.claimed_count || 0;
        const skipped = res.skipped_count || 0;
        addLogEntry("SUCCESS", "quest", `${claimed} recompensas resgatadas! (${skipped} ignoradas por segurança de armazém/pop)`);
        if (res.data) applyStateData(res.data);
        checkQuestStatus();
      } else {
        addLogEntry("WARNING", "quest", res.message || "Nenhuma missão pronta para resgate.");
      }
    } catch (err) {
      addLogEntry("WARNING", "quest", `Erro ao resgatar missões: ${err.message}`);
    } finally {
      elements.btnClaimQuests.disabled = false;
      elements.btnClaimQuests.innerHTML = `<span>🎁</span> Missões <span id="badge-quest-count" class="badge" style="display:none; background:var(--neon-emerald); color:#000; padding:1px 6px; border-radius:10px; font-size:0.7rem; margin-left:4px; font-weight:700;">0</span>`;
      checkQuestStatus();
    }
  });

  async function checkQuestStatus() {
    try {
      const qRes = await window.api.getQuestStatus();
      const badge = document.getElementById("badge-quest-count");
      if (badge && qRes && qRes.finishable_count !== undefined) {
        if (qRes.finishable_count > 0) {
          badge.textContent = qRes.finishable_count;
          badge.style.display = "inline-block";
        } else {
          badge.style.display = "none";
        }
      }
    } catch (e) {
      // Ignora erro silencioso de polling
    }
  }

  // --- 7. Motor do Mapa Tático Geográfico (screen=map) ---
  const mapState = {
    villages: [],
    barbarians: [],
    villageMap: new Map(),
    centerX: null,
    centerY: null,
    radius: 15,
    zoomTileSize: 34,
    selectedVillage: null,
    isDragging: false,
    dragStartMouseX: 0,
    dragStartMouseY: 0,
    dragStartCx: 0,
    dragStartCy: 0,
    hasDragged: false,
    initializedCenter: false,
  };

  async function loadMapGrid(centerX, centerY, radius) {
    try {
      let cx = centerX !== undefined ? centerX : (mapState.centerX !== null ? mapState.centerX : parseInt(elements.mapCenterX?.value, 10));
      let cy = centerY !== undefined ? centerY : (mapState.centerY !== null ? mapState.centerY : parseInt(elements.mapCenterY?.value, 10));

      if (isNaN(cx) || isNaN(cy) || (cx === 500 && cy === 500 && !mapState.initializedCenter)) {
        const rawCoords = elements.villageCoords?.textContent?.replace(/[()]/g, "") || "";
        const parts = rawCoords.split("|");
        if (parts.length === 2 && !isNaN(parseInt(parts[0])) && !isNaN(parseInt(parts[1]))) {
          cx = parseInt(parts[0], 10);
          cy = parseInt(parts[1], 10);
          mapState.initializedCenter = true;
        } else {
          cx = cx || 500;
          cy = cy || 500;
        }
      }

      if (elements.mapCenterX) elements.mapCenterX.value = cx;
      if (elements.mapCenterY) elements.mapCenterY.value = cy;

      const r = radius !== undefined ? radius : (parseInt(elements.mapRadius?.value, 10) || 15);

      mapState.centerX = cx;
      mapState.centerY = cy;
      mapState.radius = r;

      if (elements.mapStatsText) {
        elements.mapStatsText.textContent = "A carregar mapa...";
      }

      const res = await window.api.getMapGrid(cx, cy, r);
      if (res && res.villages) {
        mapState.villages = res.villages;
        mapState.villageMap = new Map();
        res.villages.forEach((v) => {
          mapState.villageMap.set(`${v.x}|${v.y}`, v);
        });

        // Se tiver aldeia selecionada previamente, mantém a referência atualizada
        if (mapState.selectedVillage) {
          const updated = mapState.villageMap.get(`${mapState.selectedVillage.x}|${mapState.selectedVillage.y}`);
          if (updated) mapState.selectedVillage = updated;
        }

        if (elements.mapStatsText) {
          elements.mapStatsText.textContent = `${res.count || res.villages.length} aldeias mapeadas no raio de ${r} campos`;
        }
        try {
          renderTacticalMap();
        } catch (renderErr) {
          console.error("Erro na renderização tática do mapa:", renderErr);
        }
      } else {
        const errMsg = (res && res.message) ? res.message : "Não foi possível carregar a grelha de aldeias.";
        if (elements.mapStatsText) {
          elements.mapStatsText.textContent = `Erro: ${errMsg}`;
        }
      }
    } catch (err) {
      console.error("Erro ao carregar grelha do mapa:", err);
      if (elements.mapStatsText) {
        elements.mapStatsText.textContent = `Erro ao carregar mapa: ${err.message || err}`;
      }
    }
  }

  async function loadMapBarbarians(radius) {
    try {
      const r = radius !== undefined ? radius : (parseInt(elements.mapRadius?.value, 10) || 15);
      const res = await window.api.getMapBarbarians(r, true);
      if (res && res.barbarians) {
        mapState.barbarians = res.barbarians;
        // Integra bárbaras ao mapa se ainda não existirem
        res.barbarians.forEach((b) => {
          if (!mapState.villageMap.has(`${b.x}|${b.y}`)) {
            mapState.villageMap.set(`${b.x}|${b.y}`, b);
          }
        });
        if (elements.barbCountBadge) {
          elements.barbCountBadge.textContent = res.barbarians.length;
        }
        renderBarbariansTable(res.barbarians);
        try {
          renderTacticalMap();
        } catch (renderErr) {
          console.error("Erro ao redesenhar bárbaras no mapa:", renderErr);
        }
      }
    } catch (err) {
      console.error("Erro ao carregar bárbaras:", err);
    }
  }

  function renderBarbariansTable(barbs) {
    if (!elements.barbariansTableBody) return;
    if (!barbs || barbs.length === 0) {
      elements.barbariansTableBody.innerHTML = `
        <tr>
          <td colspan="6" style="padding: 16px; text-align: center; color: var(--text-muted);">
            Nenhuma aldeia bárbara mapeada neste raio. Clique em "Scan Ativo" para varrer o mapa.
          </td>
        </tr>
      `;
      return;
    }

    elements.barbariansTableBody.innerHTML = barbs
      .map(
        (b) => `
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.05); transition: background 0.15s ease;" onmouseenter="this.style.background='rgba(255,255,255,0.04)'" onmouseleave="this.style.background='transparent'">
          <td style="padding: 8px 12px; font-family: var(--font-mono); color: var(--neon-cyan); font-weight: 600; cursor: pointer;" onclick="window.focusMapCoord(${b.x}, ${b.y})" title="Centralizar mapa">${b.coordinates}</td>
          <td style="padding: 8px 12px; font-family: var(--font-mono);">${b.distance.toFixed(1)} camp.</td>
          <td style="padding: 8px 12px; font-weight: 500;">${b.name}</td>
          <td style="padding: 8px 12px; font-family: var(--font-mono);">${b.points ? b.points.toLocaleString() : "-"}</td>
          <td style="padding: 8px 12px;">
            ${b.is_bonus ? '<span class="badge" style="background: rgba(168,85,247,0.2); color: #c084fc; border: 1px solid rgba(168,85,247,0.4); font-size: 0.7rem;">BÓNUS</span>' : '<span style="color: var(--text-muted); font-size: 0.75rem;">Normal</span>'}
          </td>
          <td style="padding: 8px 12px; text-align: right;">
            <button class="btn btn-secondary" style="padding: 3px 10px; font-size: 0.75rem;" onclick="window.farmTargetCoords('${b.coordinates}')" title="Disparar ataque para esta bárbara">
              ⚔ Atacar
            </button>
          </td>
        </tr>
      `
      )
      .join("");
  }

  // Helper para focar coordenada vinda da tabela
  window.focusMapCoord = function(x, y) {
    if (elements.mapCenterX) elements.mapCenterX.value = x;
    if (elements.mapCenterY) elements.mapCenterY.value = y;
    loadMapGrid(x, y);
  };

  // Quick Farm Target Helper
  window.farmTargetCoords = async function(coords) {
    try {
      addLogEntry("INFO", "map", `A disparar onda de saque para bárbaras próximas incluindo ${coords}...`);
      const res = await window.api.triggerMapFarm();
      if (res && res.status === "scheduled") {
        addLogEntry("SUCCESS", "map", `Onda de ataque agendada via Praça de Reunião!`);
      }
    } catch (e) {
      alert(`Falha ao enviar ataque: ${e.message}`);
    }
  };

  // --- Renderizador Cartográfico Geográfico Réplica do Tribal Wars ---
  // Helper seguro para desenhar retângulos arredondados compatível com todos os WebViews (Safari, Cocoa WebKit, Chrome)
  function drawTileBox(ctx, x, y, w, h, r = 4) {
    ctx.beginPath();
    if (typeof ctx.roundRect === "function") {
      ctx.roundRect(x, y, w, h, r);
    } else {
      const radius = Math.min(r, Math.abs(w) / 2, Math.abs(h) / 2);
      ctx.moveTo(x + radius, y);
      ctx.lineTo(x + w - radius, y);
      ctx.arcTo(x + w, y, x + w, y + radius, radius);
      ctx.lineTo(x + w, y + h - radius);
      ctx.arcTo(x + w, y + h, x + w - radius, y + h, radius);
      ctx.lineTo(x + radius, y + h);
      ctx.arcTo(x, y + h, x, y + h - radius, radius);
      ctx.lineTo(x, y + radius);
      ctx.arcTo(x, y, x + radius, y, radius);
      ctx.closePath();
    }
  }

  function renderTacticalMap() {
    const canvas = elements.tacticalMapCanvas;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const width = Math.max(600, rect.width || canvas.parentElement?.clientWidth || 900);
    const height = Math.max(400, rect.height || canvas.parentElement?.clientHeight || 520);
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, width, height);

    // Dimensões das réguas de eixos
    const gutterW = 46; // Régua do eixo Y (esquerda)
    const headerH = 28; // Régua do eixo X (topo)
    const viewW = width - gutterW;
    const viewH = height - headerH;

    const cx = mapState.centerX !== null ? mapState.centerX : 500;
    const cy = mapState.centerY !== null ? mapState.centerY : 500;
    const radius = mapState.radius || 15;

    // Tamanho do tile em pixels (com zoom persistente e dinâmico)
    let tileSize = mapState.zoomTileSize;
    if (!tileSize) {
      tileSize = Math.max(26, Math.min(64, Math.floor(Math.min(viewW, viewH) / (radius * 2 + 1))));
      mapState.zoomTileSize = tileSize;
    }

    const viewCenterX = gutterW + viewW / 2;
    const viewCenterY = headerH + viewH / 2;

    const minCol = Math.floor(cx - (viewCenterX - gutterW + tileSize) / tileSize);
    const maxCol = Math.ceil(cx + (width - viewCenterX + tileSize) / tileSize);
    const minRow = Math.floor(cy - (viewCenterY - headerH + tileSize) / tileSize);
    const maxRow = Math.ceil(cy + (height - viewCenterY + tileSize) / tileSize);

    // 1. Renderiza células geográficas dentro do viewport
    ctx.save();
    ctx.beginPath();
    ctx.rect(gutterW, headerH, viewW, viewH);
    ctx.clip();

    const currVCoords = elements.villageCoords?.textContent?.replace(/[()]/g, "") || "";

    for (let x = minCol; x <= maxCol; x++) {
      for (let y = minRow; y <= maxRow; y++) {
        const tileX = Math.round(viewCenterX + (x - cx) * tileSize - tileSize / 2);
        const tileY = Math.round(viewCenterY + (y - cy) * tileSize - tileSize / 2);

        // Textura xadrez de terreno
        const isEven = (x + y) % 2 === 0;
        ctx.fillStyle = isEven ? "#0a111e" : "#0d1627";
        ctx.fillRect(tileX, tileY, tileSize, tileSize);

        // Linha sutil de limite de campo
        ctx.strokeStyle = "rgba(255, 255, 255, 0.035)";
        ctx.lineWidth = 1;
        ctx.strokeRect(tileX, tileY, tileSize, tileSize);

        // Fronteira de Setor (a cada 20 campos)
        if (x % 20 === 0) {
          ctx.strokeStyle = "rgba(6, 182, 212, 0.35)";
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.moveTo(tileX, tileY);
          ctx.lineTo(tileX, tileY + tileSize);
          ctx.stroke();
        }
        if (y % 20 === 0) {
          ctx.strokeStyle = "rgba(6, 182, 212, 0.35)";
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.moveTo(tileX, tileY);
          ctx.lineTo(tileX + tileSize, tileY);
          ctx.stroke();
        }

        // Fronteira de Continente (a cada 100 campos)
        if (x % 100 === 0) {
          ctx.strokeStyle = "rgba(234, 179, 8, 0.6)";
          ctx.lineWidth = 2.5;
          ctx.beginPath();
          ctx.moveTo(tileX, tileY);
          ctx.lineTo(tileX, tileY + tileSize);
          ctx.stroke();
        }
        if (y % 100 === 0) {
          ctx.strokeStyle = "rgba(234, 179, 8, 0.6)";
          ctx.lineWidth = 2.5;
          ctx.beginPath();
          ctx.moveTo(tileX, tileY);
          ctx.lineTo(tileX + tileSize, tileY);
          ctx.stroke();
        }

        // Renderiza Aldeia se existir exatamente nesta coordenada
        const v = mapState.villageMap.get(`${x}|${y}`);
        if (v) {
          const pad = Math.max(2, Math.floor(tileSize * 0.06));
          const vx = tileX + pad;
          const vy = tileY + pad;
          const vw = tileSize - pad * 2;
          const vh = tileSize - pad * 2;

          const isCurrent = v.coordinates === currVCoords || (v.x === cx && v.y === cy);
          const isBarb = v.is_barbarian;
          const isBonus = v.is_bonus;
          const isSelected = mapState.selectedVillage && mapState.selectedVillage.id === v.id;

          // Cores oficiais de aldeias
          if (isCurrent) {
            ctx.fillStyle = "rgba(234, 179, 8, 0.28)";
            ctx.strokeStyle = "#eab308";
            ctx.lineWidth = 2;
          } else if (isBonus) {
            ctx.fillStyle = "rgba(168, 85, 247, 0.25)";
            ctx.strokeStyle = "#c084fc";
            ctx.lineWidth = 1.5;
          } else if (isBarb) {
            ctx.fillStyle = "rgba(100, 116, 139, 0.2)";
            ctx.strokeStyle = "#64748b";
            ctx.lineWidth = 1;
          } else {
            ctx.fillStyle = "rgba(6, 182, 212, 0.22)";
            ctx.strokeStyle = "#38bdf8";
            ctx.lineWidth = 1.5;
          }

          drawTileBox(ctx, vx, vy, vw, vh, 4);
          ctx.fill();
          ctx.stroke();

          // Destaque de seleção
          if (isSelected) {
            ctx.strokeStyle = "#4ade80";
            ctx.lineWidth = 2.5;
            drawTileBox(ctx, vx, vy, vw, vh, 4);
            ctx.stroke();
          }

          // Ícone temático da aldeia
          const iconSize = Math.max(10, Math.floor(tileSize * 0.38));
          ctx.font = `${iconSize}px 'Segoe UI Emoji', sans-serif`;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          const icon = isCurrent ? "🏰" : (isBonus ? "⭐" : (isBarb ? "🛖" : "🛡️"));
          const iconOffsetY = tileSize >= 36 ? -tileSize * 0.12 : 0;
          ctx.fillText(icon, vx + vw / 2, vy + vh / 2 + iconOffsetY);

          // Rótulo de pontos (se o zoom permitir)
          if (tileSize >= 28) {
            ctx.fillStyle = isCurrent ? "#fef08a" : (isBonus ? "#e9d5ff" : "#cbd5e1");
            ctx.font = "bold 9px 'JetBrains Mono', monospace";
            ctx.textAlign = "center";
            ctx.textBaseline = "bottom";
            const ptsText = v.points ? `${v.points > 999 ? (v.points / 1000).toFixed(1) + 'k' : v.points}` : '';
            if (ptsText) {
              ctx.fillText(ptsText, vx + vw / 2, vy + vh - 2);
            }
          }

          // Nome resumido da aldeia (com zoom elevado)
          if (tileSize >= 52) {
            ctx.fillStyle = "#ffffff";
            ctx.font = "500 8.5px Inter, sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "top";
            const shortName = v.name.length > 8 ? v.name.slice(0, 7) + '…' : v.name;
            ctx.fillText(shortName, vx + vw / 2, vy + 3);
          }
        }
      }
    }

    // Anel indicador de raio tático
    ctx.strokeStyle = "rgba(6, 182, 212, 0.28)";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.arc(viewCenterX, viewCenterY, radius * tileSize, 0, 2 * Math.PI);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.restore();

    // 2. Régua do Eixo X (Cabeçalho do Topo)
    ctx.fillStyle = "#060b14";
    ctx.fillRect(gutterW, 0, viewW, headerH);
    ctx.strokeStyle = "rgba(6, 182, 212, 0.4)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(gutterW, headerH);
    ctx.lineTo(width, headerH);
    ctx.stroke();

    for (let x = minCol; x <= maxCol; x++) {
      const tileLeft = viewCenterX + (x - cx) * tileSize - tileSize / 2;
      const tileCenter = tileLeft + tileSize / 2;
      if (tileCenter >= gutterW && tileCenter <= width) {
        // Marcação na régua
        ctx.strokeStyle = "rgba(255, 255, 255, 0.2)";
        ctx.beginPath();
        ctx.moveTo(tileCenter, headerH - 5);
        ctx.lineTo(tileCenter, headerH);
        ctx.stroke();

        // Rótulo da coordenada X
        const isCurrentX = (x === cx);
        ctx.fillStyle = isCurrentX ? "#eab308" : (x % 10 === 0 ? "#38bdf8" : "#94a3b8");
        ctx.font = isCurrentX ? "bold 10px 'JetBrains Mono', monospace" : "9px 'JetBrains Mono', monospace";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(x.toString(), tileCenter, headerH / 2 - 1);
      }
    }

    // 3. Régua do Eixo Y (Coluna da Esquerda)
    ctx.fillStyle = "#060b14";
    ctx.fillRect(0, headerH, gutterW, viewH);
    ctx.strokeStyle = "rgba(6, 182, 212, 0.4)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(gutterW, headerH);
    ctx.lineTo(gutterW, height);
    ctx.stroke();

    for (let y = minRow; y <= maxRow; y++) {
      const tileTop = viewCenterY + (y - cy) * tileSize - tileSize / 2;
      const tileCenter = tileTop + tileSize / 2;
      if (tileCenter >= headerH && tileCenter <= height) {
        // Marcação na régua
        ctx.strokeStyle = "rgba(255, 255, 255, 0.2)";
        ctx.beginPath();
        ctx.moveTo(gutterW - 5, tileCenter);
        ctx.lineTo(gutterW, tileCenter);
        ctx.stroke();

        // Rótulo da coordenada Y
        const isCurrentY = (y === cy);
        ctx.fillStyle = isCurrentY ? "#eab308" : (y % 10 === 0 ? "#38bdf8" : "#94a3b8");
        ctx.font = isCurrentY ? "bold 10px 'JetBrains Mono', monospace" : "9px 'JetBrains Mono', monospace";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(y.toString(), gutterW / 2, tileCenter);
      }
    }

    // 4. Caixa de Canto: Continente (K45, K55 etc.)
    ctx.fillStyle = "#03060c";
    ctx.fillRect(0, 0, gutterW, headerH);
    ctx.strokeStyle = "rgba(6, 182, 212, 0.6)";
    ctx.lineWidth = 1;
    ctx.strokeRect(0, 0, gutterW, headerH);

    const contY = Math.floor(cy / 100);
    const contX = Math.floor(cx / 100);
    const kNum = contY * 10 + contX;

    ctx.fillStyle = "#38bdf8";
    ctx.font = "bold 11px 'JetBrains Mono', monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(`K${kNum}`, gutterW / 2, headerH / 2);
  }

  // Atualiza painel com detalhes da aldeia selecionada
  function updateSelectedVillageCard(v) {
    if (!elements.selectedVillageCard) return;
    elements.selectedVillageCard.style.display = "flex";

    const currCoords = elements.villageCoords?.textContent?.replace(/[()]/g, "") || "";
    const isCurrent = v.coordinates === currCoords || (v.x === mapState.centerX && v.y === mapState.centerY);
    const icon = isCurrent ? "🏰" : (v.is_bonus ? "⭐" : (v.is_barbarian ? "🛖" : "🛡️"));
    const iconBg = isCurrent ? "rgba(234, 179, 8, 0.2)" : (v.is_bonus ? "rgba(168, 85, 247, 0.2)" : (v.is_barbarian ? "rgba(100, 116, 139, 0.2)" : "rgba(6, 182, 212, 0.2)"));
    const iconBorder = isCurrent ? "#eab308" : (v.is_bonus ? "#c084fc" : (v.is_barbarian ? "#64748b" : "#06b6d4"));

    if (elements.selectedVillageIcon) {
      elements.selectedVillageIcon.textContent = icon;
      elements.selectedVillageIcon.style.background = iconBg;
      elements.selectedVillageIcon.style.borderColor = iconBorder;
    }
    if (elements.selectedVillageName) elements.selectedVillageName.textContent = v.name;
    if (elements.selectedVillageCoords) elements.selectedVillageCoords.textContent = `(${v.x}|${v.y})`;
    if (elements.selectedVillageDist) elements.selectedVillageDist.textContent = `${v.distance != null ? v.distance.toFixed(1) : '-'} camp.`;
    if (elements.selectedVillagePts) elements.selectedVillagePts.textContent = v.points ? v.points.toLocaleString() : "-";
    if (elements.selectedVillagePlayer) {
      elements.selectedVillagePlayer.textContent = v.player_name ? `${v.player_name} ${v.tribe_tag ? '[' + v.tribe_tag + ']' : ''}` : (v.is_barbarian ? "Bárbara / Abandonada" : "-");
    }
    if (elements.selectedVillageBonus) {
      elements.selectedVillageBonus.style.display = v.is_bonus ? "inline-block" : "none";
    }
  }

  // --- Eventos Interativos do Canvas: Arrasto (Pan), Zoom e Clique ---
  elements.tacticalMapCanvas?.addEventListener("mousedown", (e) => {
    const canvas = elements.tacticalMapCanvas;
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    // Apenas inicia arrasto se clicar dentro do viewport (fora das réguas)
    if (mouseX >= 46 && mouseY >= 28) {
      mapState.isDragging = true;
      mapState.hasDragged = false;
      mapState.dragStartMouseX = e.clientX;
      mapState.dragStartMouseY = e.clientY;
      mapState.dragStartCx = mapState.centerX || 500;
      mapState.dragStartCy = mapState.centerY || 500;
      canvas.style.cursor = "grabbing";
    }
  });

  elements.tacticalMapCanvas?.addEventListener("mousemove", (e) => {
    const canvas = elements.tacticalMapCanvas;
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const gutterW = 46;
    const headerH = 28;
    const tileSize = mapState.zoomTileSize || 34;
    const viewW = rect.width - gutterW;
    const viewH = rect.height - headerH;
    const viewCenterX = gutterW + viewW / 2;
    const viewCenterY = headerH + viewH / 2;

    if (mapState.isDragging) {
      const deltaX = e.clientX - mapState.dragStartMouseX;
      const deltaY = e.clientY - mapState.dragStartMouseY;

      if (Math.abs(deltaX) > 4 || Math.abs(deltaY) > 4) {
        mapState.hasDragged = true;
      }

      const shiftX = Math.round(deltaX / tileSize);
      const shiftY = Math.round(deltaY / tileSize);

      mapState.centerX = mapState.dragStartCx - shiftX;
      mapState.centerY = mapState.dragStartCy - shiftY;

      if (elements.mapCenterX) elements.mapCenterX.value = mapState.centerX;
      if (elements.mapCenterY) elements.mapCenterY.value = mapState.centerY;

      renderTacticalMap();
      if (elements.mapTooltip) elements.mapTooltip.style.display = "none";
      return;
    }

    // Tooltip Geográfico
    if (mouseX >= gutterW && mouseY >= headerH) {
      const fieldX = Math.floor((mouseX - viewCenterX + tileSize / 2) / tileSize) + (mapState.centerX || 500);
      const fieldY = Math.floor((mouseY - viewCenterY + tileSize / 2) / tileSize) + (mapState.centerY || 500);

      const found = mapState.villageMap.get(`${fieldX}|${fieldY}`);
      if (found && elements.mapTooltip) {
        elements.mapTooltip.style.display = "block";
        elements.mapTooltip.style.left = `${Math.min(rect.width - 220, mouseX + 15)}px`;
        elements.mapTooltip.style.top = `${Math.min(rect.height - 120, mouseY + 15)}px`;
        elements.mapTooltip.innerHTML = `
          <div style="font-weight:700; color:${found.is_barbarian ? '#cbd5e1' : '#38bdf8'}; font-size:0.9rem;">${found.name}</div>
          <div style="font-family:var(--font-mono); color:var(--neon-cyan); margin:2px 0;">(${found.coordinates}) • Dist: ${found.distance ? found.distance.toFixed(1) : '-'} camp.</div>
          <div style="color:var(--text-muted);">Pontos: <strong style="color:var(--text-main);">${found.points ? found.points.toLocaleString() : '-'}</strong></div>
          ${found.player_name ? `<div style="color:var(--text-muted);">Jogador: <strong style="color:#fff;">${found.player_name}</strong> ${found.tribe_tag ? `[${found.tribe_tag}]` : ''}</div>` : '<div style="color:#94a3b8; font-style:italic;">Aldeia Bárbara / Abandonada</div>'}
          ${found.is_bonus ? '<div style="color:#c084fc; font-weight:600; margin-top:2px;">✨ Aldeia com Bónus</div>' : ''}
        `;
      } else if (elements.mapTooltip) {
        elements.mapTooltip.style.display = "none";
      }
    } else if (elements.mapTooltip) {
      elements.mapTooltip.style.display = "none";
    }
  });

  const stopDragging = () => {
    if (mapState.isDragging) {
      mapState.isDragging = false;
      if (elements.tacticalMapCanvas) {
        elements.tacticalMapCanvas.style.cursor = "crosshair";
      }
      if (mapState.hasDragged) {
        loadMapGrid(mapState.centerX, mapState.centerY, mapState.radius);
      }
    }
  };

  elements.tacticalMapCanvas?.addEventListener("mouseup", stopDragging);
  elements.tacticalMapCanvas?.addEventListener("mouseleave", () => {
    stopDragging();
    if (elements.mapTooltip) elements.mapTooltip.style.display = "none";
  });

  // Seleção de aldeia com clique
  elements.tacticalMapCanvas?.addEventListener("click", (e) => {
    if (mapState.hasDragged) {
      mapState.hasDragged = false;
      return;
    }
    const canvas = elements.tacticalMapCanvas;
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const gutterW = 46;
    const headerH = 28;
    if (mouseX < gutterW || mouseY < headerH) return;

    const tileSize = mapState.zoomTileSize || 34;
    const viewW = rect.width - gutterW;
    const viewH = rect.height - headerH;
    const viewCenterX = gutterW + viewW / 2;
    const viewCenterY = headerH + viewH / 2;

    const clickedX = Math.floor((mouseX - viewCenterX + tileSize / 2) / tileSize) + (mapState.centerX || 500);
    const clickedY = Math.floor((mouseY - viewCenterY + tileSize / 2) / tileSize) + (mapState.centerY || 500);

    const v = mapState.villageMap.get(`${clickedX}|${clickedY}`);
    if (v) {
      mapState.selectedVillage = v;
      updateSelectedVillageCard(v);
    } else {
      mapState.selectedVillage = null;
      if (elements.selectedVillageCard) elements.selectedVillageCard.style.display = "none";
    }
    renderTacticalMap();
  });

  // Zoom suave com a roda do rato
  elements.tacticalMapCanvas?.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault();
      const delta = e.deltaY < 0 ? 4 : -4;
      mapState.zoomTileSize = Math.max(22, Math.min(68, (mapState.zoomTileSize || 34) + delta));
      renderTacticalMap();
    },
    { passive: false }
  );

  // Botões do HUD de Navegação Tática Direcional
  elements.btnNavN?.addEventListener("click", () => {
    mapState.centerY = (mapState.centerY || 500) - 3;
    if (elements.mapCenterY) elements.mapCenterY.value = mapState.centerY;
    renderTacticalMap();
    loadMapGrid(mapState.centerX, mapState.centerY, mapState.radius);
  });

  elements.btnNavS?.addEventListener("click", () => {
    mapState.centerY = (mapState.centerY || 500) + 3;
    if (elements.mapCenterY) elements.mapCenterY.value = mapState.centerY;
    renderTacticalMap();
    loadMapGrid(mapState.centerX, mapState.centerY, mapState.radius);
  });

  elements.btnNavW?.addEventListener("click", () => {
    mapState.centerX = (mapState.centerX || 500) - 3;
    if (elements.mapCenterX) elements.mapCenterX.value = mapState.centerX;
    renderTacticalMap();
    loadMapGrid(mapState.centerX, mapState.centerY, mapState.radius);
  });

  elements.btnNavE?.addEventListener("click", () => {
    mapState.centerX = (mapState.centerX || 500) + 3;
    if (elements.mapCenterX) elements.mapCenterX.value = mapState.centerX;
    renderTacticalMap();
    loadMapGrid(mapState.centerX, mapState.centerY, mapState.radius);
  });

  elements.btnNavCenter?.addEventListener("click", () => {
    const raw = elements.villageCoords?.textContent?.replace(/[()]/g, "") || "";
    const parts = raw.split("|");
    if (parts.length === 2) {
      const vx = parseInt(parts[0], 10);
      const vy = parseInt(parts[1], 10);
      mapState.centerX = vx;
      mapState.centerY = vy;
      if (elements.mapCenterX) elements.mapCenterX.value = vx;
      if (elements.mapCenterY) elements.mapCenterY.value = vy;
      loadMapGrid(vx, vy);
      loadMapBarbarians();
    }
  });

  elements.btnZoomIn?.addEventListener("click", () => {
    mapState.zoomTileSize = Math.min(68, (mapState.zoomTileSize || 34) + 6);
    renderTacticalMap();
  });

  elements.btnZoomOut?.addEventListener("click", () => {
    mapState.zoomTileSize = Math.max(22, (mapState.zoomTileSize || 34) - 6);
    renderTacticalMap();
  });

  // Botões de Ação da Aldeia Selecionada
  elements.btnSelectedAttack?.addEventListener("click", () => {
    if (mapState.selectedVillage) {
      window.farmTargetCoords(`${mapState.selectedVillage.x}|${mapState.selectedVillage.y}`);
    }
  });

  elements.btnSelectedCenter?.addEventListener("click", () => {
    if (mapState.selectedVillage) {
      const vx = mapState.selectedVillage.x;
      const vy = mapState.selectedVillage.y;
      if (elements.mapCenterX) elements.mapCenterX.value = vx;
      if (elements.mapCenterY) elements.mapCenterY.value = vy;
      loadMapGrid(vx, vy);
    }
  });

  elements.btnSelectedCopy?.addEventListener("click", () => {
    if (mapState.selectedVillage) {
      const coordStr = `${mapState.selectedVillage.x}|${mapState.selectedVillage.y}`;
      navigator.clipboard.writeText(coordStr).then(() => {
        addLogEntry("SUCCESS", "map", `Coordenadas ${coordStr} copiadas para a área de transferência!`);
      });
    }
  });

  // Botões Principais da Barra de Ferramentas
  elements.btnMapMyVillage?.addEventListener("click", () => {
    const raw = elements.villageCoords?.textContent?.replace(/[()]/g, "") || "";
    const parts = raw.split("|");
    if (parts.length === 2) {
      const vx = parseInt(parts[0], 10);
      const vy = parseInt(parts[1], 10);
      if (elements.mapCenterX) elements.mapCenterX.value = vx;
      if (elements.mapCenterY) elements.mapCenterY.value = vy;
      loadMapGrid(vx, vy);
      loadMapBarbarians();
    }
  });

  elements.btnMapScan?.addEventListener("click", async () => {
    try {
      elements.btnMapScan.disabled = true;
      elements.btnMapScan.innerHTML = "<span>⏳</span> A varrer...";
      const r = parseInt(elements.mapRadius?.value, 10) || 15;
      addLogEntry("INFO", "map", `A forçar varredura ativa do mapa oficial no raio de ${r} campos...`);
      const res = await window.api.scanMap(r);
      if (res && res.status === "success") {
        addLogEntry("SUCCESS", "map", `Varredura concluída! ${res.barbarians_count || 0} bárbaras catalogadas.`);
        await loadMapGrid();
        await loadMapBarbarians();
      } else {
        addLogEntry("WARNING", "map", res.message || "Não foi possível concluir a varredura.");
      }
    } catch (e) {
      addLogEntry("CRITICAL", "map", `Erro na varredura do mapa: ${e.message}`);
    } finally {
      elements.btnMapScan.disabled = false;
      elements.btnMapScan.innerHTML = "<span>🔍</span> Scan Ativo";
    }
  });

  elements.btnMapFarmNearby?.addEventListener("click", async () => {
    try {
      addLogEntry("INFO", "map", "A disparar onda de saques contra as bárbaras mais próximas...");
      const res = await window.api.triggerMapFarm();
      if (res && res.status === "scheduled") {
        addLogEntry("SUCCESS", "map", "Onda de farm baseada no mapa agendada com sucesso!");
      } else {
        addLogEntry("WARNING", "map", res.message || "Nenhuma bárbara disponível ou sem tropas.");
      }
    } catch (e) {
      alert(`Erro: ${e.message}`);
    }
  });

  elements.btnRefreshBarbs?.addEventListener("click", () => {
    loadMapBarbarians();
  });

  elements.mapRadius?.addEventListener("change", () => {
    loadMapGrid();
    loadMapBarbarians();
  });

  elements.mapCenterX?.addEventListener("change", () => {
    loadMapGrid();
  });

  elements.mapCenterY?.addEventListener("change", () => {
    loadMapGrid();
  });

  // Checa missões ao carregar
  setTimeout(checkQuestStatus, 2000);

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

  // --- 8. Relógio do Servidor de Alta Precisão (HH:MM:SS.uuuuuu) ---
  const clockHmsEl = document.getElementById("clock-hms");
  const clockMsEl = document.getElementById("clock-ms");

  function startHighPrecisionClock() {
    function tick() {
      const now = new Date();
      const h = String(now.getHours()).padStart(2, "0");
      const m = String(now.getMinutes()).padStart(2, "0");
      const s = String(now.getSeconds()).padStart(2, "0");
      
      const ms = now.getMilliseconds();
      const frac = Math.floor((performance.now() % 1) * 1000);
      const micros = String(ms * 1000 + frac).padStart(6, "0");

      if (clockHmsEl) {
        clockHmsEl.textContent = `${h}:${m}:${s}`;
      }
      if (clockMsEl) {
        clockMsEl.textContent = `.${micros}`;
      }

      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  startHighPrecisionClock();
});

