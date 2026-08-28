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

    // Mercado & Balanceamento de Recursos (Secção 2.7)
    marketVillageSelector: document.getElementById("market-village-selector"),
    btnMarketRefresh: document.getElementById("btn-market-refresh"),
    btnMarketBalanceNow: document.getElementById("btn-market-balance-now"),
    btnMarketExecPlan: document.getElementById("btn-market-exec-plan"),
    marketMerchantsAvail: document.getElementById("market-merchants-avail"),
    marketMerchantsTotal: document.getElementById("market-merchants-total"),
    marketMerchantsBar: document.getElementById("market-merchants-bar"),
    marketMerchantsTransit: document.getElementById("market-merchants-transit"),
    marketTransitLoad: document.getElementById("market-transit-load"),
    marketMaxCapacity: document.getElementById("market-max-capacity"),
    marketBalanceStatusBadge: document.getElementById("market-balance-status-badge"),
    marketPlannedCountBadge: document.getElementById("market-planned-count-badge"),
    marketDonorsChips: document.getElementById("market-donors-chips"),
    marketReceiversChips: document.getElementById("market-receivers-chips"),
    marketPlannedOrdersTbody: document.getElementById("market-planned-orders-tbody"),
    marketTransportsTbody: document.getElementById("market-transports-tbody"),
    marketTransportsCount: document.getElementById("market-transports-count"),
    marketOffersTbody: document.getElementById("market-offers-tbody"),
    marketOffersCount: document.getElementById("market-offers-count"),
    formSendMerchants: document.getElementById("form-send-merchants"),
    marketSendTargetVillage: document.getElementById("market-send-target-village"),
    marketSendTargetX: document.getElementById("market-send-target-x"),
    marketSendTargetY: document.getElementById("market-send-target-y"),
    marketSendWood: document.getElementById("market-send-wood"),
    marketSendStone: document.getElementById("market-send-stone"),
    marketSendIron: document.getElementById("market-send-iron"),
    marketSendReqMerchants: document.getElementById("market-send-req-merchants"),
    marketSendAvailMerchants: document.getElementById("market-send-avail-merchants"),
    formCreateMarketOffer: document.getElementById("form-create-market-offer"),
    marketOfferSellRes: document.getElementById("market-offer-sell-res"),
    marketOfferSellAmount: document.getElementById("market-offer-sell-amount"),
    marketOfferBuyRes: document.getElementById("market-offer-buy-res"),
    marketOfferBuyAmount: document.getElementById("market-offer-buy-amount"),
    marketOfferRatioDisplay: document.getElementById("market-offer-ratio-display"),
    marketOfferMaxTime: document.getElementById("market-offer-max-time"),
    marketOfferMulti: document.getElementById("market-offer-multi"),
    mktAvgWood: document.getElementById("mkt-avg-wood"),
    mktAvgStone: document.getElementById("mkt-avg-stone"),
    mktAvgIron: document.getElementById("mkt-avg-iron"),

    // Edifícios & Fila (Roadmap)
    btnRefreshBuildingTab: document.getElementById("btn-refresh-building-tab"),
    btnTriggerBuildTab: document.getElementById("btn-trigger-build-tab"),
    bldAutoToggle: document.getElementById("bld-auto-toggle"),
    bldBadgeStatus: document.getElementById("bld-badge-status"),
    bldIntervalSeconds: document.getElementById("bld-interval-seconds"),
    bldTemplateBadge: document.getElementById("bld-template-badge"),
    bldQueueCount: document.getElementById("bld-queue-count"),
    bldMaxQueue: document.getElementById("bld-max-queue"),
    bldQueueStatusText: document.getElementById("bld-queue-status-text"),
    bldNextTargetName: document.getElementById("bld-next-target-name"),
    bldNextTargetCost: document.getElementById("bld-next-target-cost"),
    bldProgressPct: document.getElementById("bld-progress-pct"),
    bldProgressCompleted: document.getElementById("bld-progress-completed"),
    bldProgressTotal: document.getElementById("bld-progress-total"),
    bldProgressBar: document.getElementById("bld-progress-bar"),
    bldActiveQueueBadge: document.getElementById("bld-active-queue-badge"),
    bldActiveQueueContainer: document.getElementById("bld-active-queue-container"),
    bldUpcomingCountBadge: document.getElementById("bld-upcoming-count-badge"),
    bldUpcomingTableBody: document.getElementById("bld-upcoming-table-body"),
    btnFilterPlanPending: document.getElementById("btn-filter-plan-pending"),
    btnFilterPlanAll: document.getElementById("btn-filter-plan-all"),
    bldVillageLevelsGrid: document.getElementById("bld-village-levels-grid"),

    // Recrutamento & Modelos de Tropas
    btnRefreshRecTab: document.getElementById("btn-refresh-rec-tab"),
    recActiveQueueBadge: document.getElementById("rec-active-queue-badge"),
    recActiveQueueContainer: document.getElementById("rec-active-queue-container"),

    // Mercado Switches
    marketToggleEnabled: document.getElementById("market-toggle-enabled"),
    marketToggleLabel: document.getElementById("market-toggle-label"),
    marketToggleAutobalance: document.getElementById("market-toggle-autobalance"),
    marketAutobalanceLabel: document.getElementById("market-autobalance-label"),
    marketDisabledAlert: document.getElementById("market-disabled-alert"),

    // Painel de Estatísticas & Rendimento
    btnDashboardViewStats: document.getElementById("btn-dashboard-view-stats"),
    dashLoot24h: document.getElementById("dash-loot-24h"),
    dashHourlyRate: document.getElementById("dash-hourly-rate"),
    dashSuccessRate: document.getElementById("dash-success-rate"),
    dashAttacks24h: document.getElementById("dash-attacks-24h"),
    btnRefreshStats: document.getElementById("btn-refresh-stats"),
    btnResetStats: document.getElementById("btn-reset-stats"),
    statsKpiLoot24h: document.getElementById("stats-kpi-loot-24h"),
    statsHourlyRateBadge: document.getElementById("stats-hourly-rate-badge"),
    statsKpiWood24h: document.getElementById("stats-kpi-wood-24h"),
    statsKpiStone24h: document.getElementById("stats-kpi-stone-24h"),
    statsKpiIron24h: document.getElementById("stats-kpi-iron-24h"),
    statsKpiLootAlltime: document.getElementById("stats-kpi-loot-alltime"),
    statsKpiVillagesFarmed: document.getElementById("stats-kpi-villages-farmed"),
    statsKpiVillages24h: document.getElementById("stats-kpi-villages-24h"),
    statsKpiLootPerVillage: document.getElementById("stats-kpi-loot-per-village"),
    statsKpiAttacksSent: document.getElementById("stats-kpi-attacks-sent"),
    statsSuccessRateBadge: document.getElementById("stats-success-rate-badge"),
    statsKpiAttacksSuccess: document.getElementById("stats-kpi-attacks-success"),
    statsKpiAttacksTotal: document.getElementById("stats-kpi-attacks-total"),
    statsKpiAttacks24h: document.getElementById("stats-kpi-attacks-24h"),
    statsKpiTroopsRecruited: document.getElementById("stats-kpi-troops-recruited"),
    statsKpiBuildingsCount: document.getElementById("stats-kpi-buildings-count"),
    statsActiveWorldText: document.getElementById("stats-active-world-text"),
    statsLootCanvas: document.getElementById("stats-loot-canvas"),
    statsChartTooltip: document.getElementById("stats-chart-tooltip"),
    statsChartSummaryText: document.getElementById("stats-chart-summary-text"),
    statsRecruitmentMatrix: document.getElementById("stats-recruitment-matrix"),
    statsRecentCountBadge: document.getElementById("stats-recent-count-badge"),
    statsRecentTbody: document.getElementById("stats-recent-tbody"),
    btnStatsRange24h: document.getElementById("btn-stats-range-24h"),
    btnStatsRange7d: document.getElementById("btn-stats-range-7d"),
    btnMetricTotal: document.getElementById("btn-metric-total"),
    btnMetricWood: document.getElementById("btn-metric-wood"),
    btnMetricStone: document.getElementById("btn-metric-stone"),
    btnMetricIron: document.getElementById("btn-metric-iron"),
  };

  // Estado do Mapa Tático
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

  // Inicializar MapViewer
  window.mapViewer = new MapViewer("tactical-map-canvas");

  // --- Relógio do Servidor de Alta Precisão (HH:MM:SS.uuuuuu) ---
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

      if (targetId === "tab-map") {
        if (window.mapViewer && window.mapViewer.canvas) {
          window.mapViewer.resizeCanvas();
          window.mapViewer.startAnimationLoop();
          window.mapViewer.loadMapData();
        }
      } else {
        if (window.mapViewer && window.mapViewer.canvas) {
          window.mapViewer.stopAnimationLoop();
        }
      }

      if (targetId === "tab-settings") {
        loadSettingsIntoForm();
      } else if (targetId === "tab-map") {
        loadMapGrid();
        loadMapBarbarians();
      } else if (targetId === "tab-military") {
        loadRecruitmentIntoForm();
      } else if (targetId === "tab-building") {
        loadBuildingData();
      } else if (targetId === "tab-villages") {
        if (elements.btnSyncAllVillages) elements.btnSyncAllVillages.click();
      } else if (targetId === "tab-market") {
        loadMarketData();
      } else if (targetId === "tab-stats") {
        loadAndRenderStats();
      }
    });
  });

  if (elements.btnDashboardViewStats) {
    elements.btnDashboardViewStats.addEventListener("click", () => {
      const statsTabBtn = document.getElementById("tab-btn-stats");
      if (statsTabBtn) statsTabBtn.click();
    });
  }

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

  window.wsClient.on("MARKET_RESOURCES_SENT", (data) => {
    addLogEntry("SUCCESS", "market", `🚚 Recursos enviados: ${data.wood} Madeira, ${data.stone} Argila, ${data.iron} Ferro.`);
    loadMarketData();
  });

  window.wsClient.on("MARKET_BALANCING_DONE", (data) => {
    addLogEntry("SUCCESS", "market", `⚖️ Ciclo de balanceamento global concluído: ${data.executed || 0} transferências executadas.`);
    loadMarketData();
  });

  window.wsClient.on("STATS_UPDATED", (statsData) => {
    updateDashboardStats(statsData);
    const statsTab = document.getElementById("tab-stats");
    if (statsTab && statsTab.classList.contains("active")) {
      loadAndRenderStats();
    }
  });

  window.wsClient.on("MODULE_TOGGLED", (data) => {
    if (data.module === "building") {
      loadBuildingData();
    } else if (data.module === "recruitment") {
      loadRecruitmentData();
    }
  });

  window.wsClient.on("BUILDING_CYCLE_EXECUTED", () => {
    loadBuildingData();
  });

  window.wsClient.on("RECRUITMENT_CYCLE_EXECUTED", () => {
    loadRecruitmentData();
  });

  // --- 4. Renderização Reativa da Interface ---
  function updateBuildingStatusBadge(enabled) {
    if (!elements.bldBadgeStatus) return;
    const isEnabled = enabled !== undefined ? !!enabled : (elements.bldAutoToggle ? elements.bldAutoToggle.checked : true);
    if (!isEnabled) {
      elements.bldBadgeStatus.textContent = "DESATIVADO";
      elements.bldBadgeStatus.style.background = "rgba(100,116,139,0.25)";
      elements.bldBadgeStatus.style.color = "#94a3b8";
    } else if (!state.schedulerRunning) {
      elements.bldBadgeStatus.textContent = "ATIVO (Motor Pausado)";
      elements.bldBadgeStatus.style.background = "rgba(245,158,11,0.2)";
      elements.bldBadgeStatus.style.color = "var(--neon-amber)";
    } else {
      elements.bldBadgeStatus.textContent = "ATIVO";
      elements.bldBadgeStatus.style.background = "rgba(16,185,129,0.2)";
      elements.bldBadgeStatus.style.color = "var(--neon-emerald)";
    }
  }

  function updateRecruitmentStatusBadge(enabled) {
    if (!elements.badgeRecStatus) return;
    const isEnabled = enabled !== undefined ? !!enabled : (elements.recEnabled ? elements.recEnabled.checked : false);
    if (!isEnabled) {
      elements.badgeRecStatus.textContent = "DESATIVADO";
      elements.badgeRecStatus.style.background = "rgba(100,116,139,0.25)";
      elements.badgeRecStatus.style.color = "#94a3b8";
    } else if (!state.schedulerRunning) {
      elements.badgeRecStatus.textContent = "ATIVO (Motor Pausado)";
      elements.badgeRecStatus.style.background = "rgba(245,158,11,0.2)";
      elements.badgeRecStatus.style.color = "var(--neon-amber)";
    } else {
      elements.badgeRecStatus.textContent = "ATIVO";
      elements.badgeRecStatus.style.background = "rgba(16,185,129,0.2)";
      elements.badgeRecStatus.style.color = "var(--neon-emerald)";
    }
  }

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

    updateBuildingStatusBadge();
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
        const parts = v.coordinates.split("|").map(Number);
        if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
          window.mapViewer?.setOwnVillage(parts[0], parts[1]);
        }
      } else if (data.account.coordinates) {
        elements.villageCoords.textContent = `(${data.account.coordinates.x}|${data.account.coordinates.y})`;
        window.mapViewer?.setOwnVillage(data.account.coordinates.x, data.account.coordinates.y);
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
    state.army = troops;
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

    // Atualiza switches e badges de status de Construção e Recrutamento
    if (data.modules && data.modules.building) {
      const bld = data.modules.building;
      if (elements.bldAutoToggle && bld.enabled !== undefined) elements.bldAutoToggle.checked = !!bld.enabled;
      updateBuildingStatusBadge(bld.enabled);
      if (elements.bldIntervalSeconds && bld.interval_seconds !== undefined && document.activeElement !== elements.bldIntervalSeconds) {
        elements.bldIntervalSeconds.value = bld.interval_seconds;
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

    // Atualiza mini-widget de estatísticas no dashboard
    if (data.stats) {
      updateDashboardStats(data.stats);
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

    // Apenas lista mundos registados/conectados e o mundo ativo
    const registeredWorldKeys = (worlds || []).map(w => (w.world || "").toLowerCase()).filter(Boolean);
    if (!registeredWorldKeys.includes(currentW)) {
      registeredWorldKeys.unshift(currentW);
    }
    const allWorldKeys = Array.from(new Set(registeredWorldKeys));

    elements.worldDropdownList.innerHTML = allWorldKeys.map(w => {
      const isCurrent = w === currentW;
      return `
        <div class="dropdown-world-item ${isCurrent ? 'active' : ''}" data-world="${w}" style="padding: 8px 14px; cursor: pointer; display: flex; align-items: center; justify-content: space-between; font-size: 0.82rem; transition: background 0.15s ease; color: ${isCurrent ? 'var(--neon-cyan)' : 'var(--text-main)'}; font-weight: ${isCurrent ? '700' : '500'}; background: ${isCurrent ? 'rgba(6,182,212,0.15)' : 'transparent'}; border-left: ${isCurrent ? '3px solid var(--neon-cyan)' : '3px solid transparent'};">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span>🌐</span>
            <span>${w.toUpperCase()}</span>
          </div>
          ${isCurrent ? '<span style="font-size: 0.65rem; background: var(--neon-cyan); color: #000; padding: 1px 6px; border-radius: 10px; font-weight: 700;">ATIVO</span>' : '<span style="font-size: 0.68rem; color: var(--neon-emerald); font-weight: 600;">Ligado</span>'}
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
            addLogEntry("INFO", "orchestrator", `A verificar e mudar para o mundo ${targetWorld.toUpperCase()}...`);
            const res = await window.api.switchWorld(targetWorld);
            if (res && res.status === "success") {
              if (elements.badgeWorldText) elements.badgeWorldText.textContent = targetWorld.toUpperCase();
              addLogEntry("SUCCESS", "orchestrator", res.message || `Mundo ${targetWorld.toUpperCase()} ativado.`);
              const status = await window.api.getStatus();
              updateDashboard(status);
            } else {
              const errMsg = (res && res.message) ? res.message : `Falha ao mudar para o mundo ${targetWorld}`;
              addLogEntry("ERROR", "orchestrator", errMsg);
              alert(errMsg);
            }
          } catch (err) {
            addLogEntry("ERROR", "orchestrator", `Falha ao mudar para o mundo ${targetWorld}: ${err.message}`);
            alert(`Falha ao mudar para o mundo ${targetWorld}: ${err.message}`);
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

    if (!state.villageCategories) state.villageCategories = {};

    elements.villagesTableBody.innerHTML = villages.map(v => {
      const r = v.resources || {};
      totWood += r.wood || 0;
      totStone += r.stone || 0;
      totIron += r.iron || 0;

      const maxStorage = r.storage_max || 1000;
      const storagePct = Math.min(100, Math.round(((r.wood + r.stone + r.iron) / (maxStorage * 3)) * 100));
      const cat = (state.villageCategories[v.id] || v.category || "balanced").toLowerCase().trim();

      // Monta opções dinâmicas com todos os modelos disponíveis (Ataque, Defesa, Balanceado + Customizados)
      const allModels = Object.keys(state.recruitmentModels || { attack: {}, defense: {} });
      let optionsHtml = `
        <option value="attack" ${cat === 'attack' ? 'selected' : ''}>⚔️ Ataque</option>
        <option value="defense" ${cat === 'defense' ? 'selected' : ''}>🛡️ Defesa</option>
        <option value="balanced" ${cat === 'balanced' ? 'selected' : ''}>⚖️ Balanceado</option>
      `;
      allModels.forEach(m => {
        const normM = m.toLowerCase().trim();
        if (normM !== 'attack' && normM !== 'defense' && normM !== 'balanced') {
          const capLabel = normM.charAt(0).toUpperCase() + normM.slice(1);
          optionsHtml += `<option value="${normM}" ${cat === normM ? 'selected' : ''}>✨ ${capLabel}</option>`;
        }
      });

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
            <select class="form-control village-cat-select" data-village-id="${v.id}" style="padding: 4px 8px; font-size: 0.8rem; width: auto; font-weight: 600; background: rgba(15,23,42,0.85); border: 1px solid var(--border-glass);">
              ${optionsHtml}
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
        const newCat = sel.value.toLowerCase().trim();
        state.villageCategories[vid] = newCat;
        const catLabel = newCat === "attack" ? "Ataque ⚔️" : (newCat === "defense" ? "Defesa 🛡️" : (newCat === "balanced" ? "Balanceado ⚖️" : `✨ ${newCat}`));
        try {
          console.log(`A alterar categoria da aldeia ${vid} para ${newCat}...`);
          sel.style.opacity = "0.6";
          await window.api.setVillageCategory(vid, newCat);
          sel.style.opacity = "1";
          sel.style.borderColor = "var(--neon-emerald)";
          setTimeout(() => { sel.style.borderColor = ""; }, 1500);
          addLogEntry("SUCCESS", "village", `Aldeia ${vid} configurada com modelo '${catLabel}'. Persistido no config.json.`);
        } catch (err) {
          sel.style.opacity = "1";
          sel.style.borderColor = "var(--neon-crimson)";
          addLogEntry("ERROR", "village", `Falha ao categorizar aldeia ${vid}: ${err.message}`);
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

  // --- 4.5. Gestão do Mercado & Balanceamento de Recursos (Secção 2.7) ---
  async function loadMarketData(villageId = null) {
    try {
      const villagesRes = await window.api.getAccountVillages();
      const villages = villagesRes?.villages || [];
      const currVillageId = villageId || (elements.marketVillageSelector && elements.marketVillageSelector.value) || (state.village && state.village.id);

      // Popula dropdown de aldeias para foco do mercado
      if (elements.marketVillageSelector && villages.length > 0) {
        elements.marketVillageSelector.innerHTML = villages.map(v => 
          `<option value="${v.id}" ${v.id == currVillageId ? 'selected' : ''}>${v.name} (${v.coordinates || `${v.x}|${v.y}`})</option>`
        ).join("");
      }

      // Popula dropdown de aldeia de destino no envio manual
      if (elements.marketSendTargetVillage && villages.length > 0) {
        const otherVillages = villages.filter(v => v.id != currVillageId);
        elements.marketSendTargetVillage.innerHTML = `
          <option value="">-- Selecionar Aldeia Própria --</option>
          ${otherVillages.map(v => `<option value="${v.id}" data-x="${v.x}" data-y="${v.y}">${v.name} (${v.coordinates || `${v.x}|${v.y}`})</option>`).join("")}
        `;
      }

      // Atualiza interruptores de desativação do mercado
      const configRes = await window.api.getConfig();
      const mCfg = configRes?.market || {};
      const mEnabled = mCfg.enabled !== false;
      const mAutoBalance = mCfg.auto_balance_enabled !== false;

      if (elements.marketToggleEnabled) {
        elements.marketToggleEnabled.checked = mEnabled;
      }
      if (elements.marketToggleLabel) {
        elements.marketToggleLabel.textContent = mEnabled ? "ATIVO" : "DESATIVADO";
        elements.marketToggleLabel.style.color = mEnabled ? "#34d399" : "#f87171";
      }

      if (elements.marketToggleAutobalance) {
        elements.marketToggleAutobalance.checked = mAutoBalance;
        elements.marketToggleAutobalance.disabled = !mEnabled;
      }
      if (elements.marketAutobalanceLabel) {
        elements.marketAutobalanceLabel.textContent = mAutoBalance ? "LIGADO" : "DESLIGADO";
        elements.marketAutobalanceLabel.style.color = (!mEnabled) ? "var(--text-muted)" : (mAutoBalance ? "#34d399" : "var(--text-muted)");
      }

      if (elements.marketDisabledAlert) {
        elements.marketDisabledAlert.style.display = mEnabled ? "none" : "flex";
      }

      if (elements.btnMarketBalanceNow) {
        elements.btnMarketBalanceNow.disabled = !mEnabled || !mAutoBalance;
        elements.btnMarketBalanceNow.style.opacity = (!mEnabled || !mAutoBalance) ? "0.45" : "1";
      }
      if (elements.btnMarketExecPlan) {
        elements.btnMarketExecPlan.disabled = !mEnabled;
        elements.btnMarketExecPlan.style.opacity = (!mEnabled) ? "0.45" : "1";
      }

      // Atualiza valor de transferência mínima da config
      const minTransfer = mCfg.min_transfer_amount || 100;
      const minTransferDisp = document.getElementById("market-min-transfer-disp");
      if (minTransferDisp) minTransferDisp.textContent = Number(minTransfer).toLocaleString("pt-PT");
      const minTransferInput = document.getElementById("market-min-transfer-input");
      if (minTransferInput && document.activeElement !== minTransferInput) {
        minTransferInput.value = minTransfer;
      }

      // 1. Obtém dados do mercado da aldeia
      const marketRes = await window.api.getMarketState(currVillageId);
      if (marketRes && marketRes.market) {
        const m = marketRes.market;
        const avail = m.merchants_available || 0;
        const total = m.merchants_total || 0;
        const transit = m.merchants_in_transit || 0;
        const pct = total > 0 ? Math.min(100, Math.round((avail / total) * 100)) : 0;

        if (elements.marketMerchantsAvail) elements.marketMerchantsAvail.textContent = avail.toString();
        if (elements.marketMerchantsTotal) elements.marketMerchantsTotal.textContent = total.toString();
        if (elements.marketMerchantsBar) elements.marketMerchantsBar.style.width = `${pct}%`;
        if (elements.marketMerchantsTransit) elements.marketMerchantsTransit.textContent = transit.toString();
        if (elements.marketMaxCapacity) elements.marketMaxCapacity.textContent = (avail * 1000).toLocaleString();
        if (elements.marketSendAvailMerchants) elements.marketSendAvailMerchants.textContent = avail.toString();

        // Transportes em trânsito
        const transports = m.transports || [];
        let totalTransitLoad = 0;
        if (elements.marketTransportsCount) elements.marketTransportsCount.textContent = transports.length.toString();
        
        if (elements.marketTransportsTbody) {
          if (transports.length === 0) {
            elements.marketTransportsTbody.innerHTML = `<tr><td colspan="5" style="padding: 12px; text-align: center; color: var(--text-muted);">Nenhum transporte de mercadores em trânsito.</td></tr>`;
          } else {
            elements.marketTransportsTbody.innerHTML = transports.map(t => {
              totalTransitLoad += t.total_resources || 0;
              const isOut = t.direction === "outgoing";
              return `
                <tr style="border-bottom: 1px solid var(--border-subtle);">
                  <td style="padding: 8px 10px;">
                    <span class="badge" style="background: ${isOut ? 'rgba(6,182,212,0.2)' : 'rgba(16,185,129,0.2)'}; color: ${isOut ? 'var(--neon-cyan)' : 'var(--neon-emerald)'}; font-size: 0.72rem;">
                      ${isOut ? '⬆ A Enviar' : '⬇ A Receber'}
                    </span>
                  </td>
                  <td style="padding: 8px 10px; font-weight: 600;">
                    ${t.village_name} <span style="color: var(--neon-cyan); font-family: var(--font-mono); font-size: 0.78rem;">(${t.coords ? `${t.coords[0]}|${t.coords[1]}` : ''})</span>
                  </td>
                  <td style="padding: 8px 10px; font-family: var(--font-mono); font-size: 0.78rem;">
                    <span style="color: #22c55e;">${(t.wood || 0).toLocaleString()}M</span> / 
                    <span style="color: #06b6d4;">${(t.stone || 0).toLocaleString()}A</span> / 
                    <span style="color: #cbd5e1;">${(t.iron || 0).toLocaleString()}F</span>
                  </td>
                  <td style="padding: 8px 10px; font-weight: 700; color: #fff;">${t.merchants_count || 1}</td>
                  <td style="padding: 8px 10px; color: var(--neon-amber); font-family: var(--font-mono);">${t.arrival_time || '-'}</td>
                </tr>
              `;
            }).join("");
          }
        }
        if (elements.marketTransitLoad) elements.marketTransitLoad.textContent = totalTransitLoad.toLocaleString();

        // Ofertas próprias
        const offers = m.own_offers || [];
        if (elements.marketOffersCount) elements.marketOffersCount.textContent = offers.length.toString();
        if (elements.marketOffersTbody) {
          if (offers.length === 0) {
            elements.marketOffersTbody.innerHTML = `<tr><td colspan="5" style="padding: 12px; text-align: center; color: var(--text-muted);">Nenhuma oferta própria ativa no mercado.</td></tr>`;
          } else {
            elements.marketOffersTbody.innerHTML = offers.map(o => `
              <tr style="border-bottom: 1px solid var(--border-subtle);">
                <td style="padding: 8px 10px; font-family: var(--font-mono); color: var(--text-muted);">#${o.id}</td>
                <td style="padding: 8px 10px;"><strong style="color: #22c55e;">${o.sell_amount}</strong> ${o.sell_res}</td>
                <td style="padding: 8px 10px;"><strong style="color: #06b6d4;">${o.buy_amount}</strong> ${o.buy_res}</td>
                <td style="padding: 8px 10px; font-family: var(--font-mono); color: var(--neon-cyan);">${o.ratio || '1.0'}</td>
                <td style="padding: 8px 10px; font-weight: 700;">${o.available_offers || 1}x</td>
              </tr>
            `).join("");
          }
        }
      }

      // 2. Obtém Plano de Balanceamento Global
      const planRes = await window.api.getMarketBalancingPlan();
      if (planRes && planRes.status === "success") {
        const summary = planRes.balance_summary || {};
        const avg = summary.averages || {};
        if (elements.mktAvgWood) elements.mktAvgWood.textContent = Math.floor(avg.wood || 0).toLocaleString();
        if (elements.mktAvgStone) elements.mktAvgStone.textContent = Math.floor(avg.stone || 0).toLocaleString();
        if (elements.mktAvgIron) elements.mktAvgIron.textContent = Math.floor(avg.iron || 0).toLocaleString();

        const donors = summary.donors || [];
        const receivers = summary.receivers || [];
        const orders = planRes.planned_orders || [];

        if (elements.marketBalanceStatusBadge) {
          if (orders.length === 0) {
            elements.marketBalanceStatusBadge.textContent = "CONTA EQUILIBRADA";
            elements.marketBalanceStatusBadge.style.background = "rgba(16,185,129,0.2)";
            elements.marketBalanceStatusBadge.style.color = "#34d399";
          } else {
            elements.marketBalanceStatusBadge.textContent = `${orders.length} TRANSFERÊNCIAS RECOMENDADAS`;
            elements.marketBalanceStatusBadge.style.background = "rgba(245,158,11,0.2)";
            elements.marketBalanceStatusBadge.style.color = "#fbbf24";
          }
        }

        if (elements.marketPlannedCountBadge) {
          elements.marketPlannedCountBadge.textContent = `${orders.length} ordens`;
        }

        // Render Doadoras
        if (elements.marketDonorsChips) {
          if (donors.length === 0) {
            elements.marketDonorsChips.innerHTML = `<span style="color: var(--text-muted);">Nenhuma doadora identificada.</span>`;
          } else {
            elements.marketDonorsChips.innerHTML = donors.map(d => `
              <span class="badge" style="background: rgba(16,185,129,0.15); color: #34d399; border: 1px solid rgba(16,185,129,0.3); padding: 4px 8px;">
                ${d.name} (${d.coordinates}) • Excedente: +${(d.diff_wood + d.diff_stone + d.diff_iron).toLocaleString()}
              </span>
            `).join("");
          }
        }

        // Render Recetoras
        if (elements.marketReceiversChips) {
          if (receivers.length === 0) {
            elements.marketReceiversChips.innerHTML = `<span style="color: var(--text-muted);">Nenhuma recetora com défice.</span>`;
          } else {
            elements.marketReceiversChips.innerHTML = receivers.map(r => `
              <span class="badge" style="background: rgba(245,158,11,0.15); color: #fbbf24; border: 1px solid rgba(245,158,11,0.3); padding: 4px 8px;">
                ${r.name} (${r.coordinates}) • Défice: ${(r.diff_wood + r.diff_stone + r.diff_iron).toLocaleString()}
              </span>
            `).join("");
          }
        }

        // Render Tabela de Ordens
        if (elements.marketPlannedOrdersTbody) {
          if (orders.length === 0) {
            elements.marketPlannedOrdersTbody.innerHTML = `<tr><td colspan="6" style="padding: 14px; text-align: center; color: #34d399; font-weight: 600;">✨ Todas as aldeias estão em equilíbrio de recursos! Nenhuma transferência pendente.</td></tr>`;
          } else {
            elements.marketPlannedOrdersTbody.innerHTML = orders.map(o => `
              <tr style="border-bottom: 1px solid var(--border-subtle);">
                <td style="padding: 8px 12px; font-weight: 600;">${o.source_name} <span style="color: var(--neon-cyan); font-family: var(--font-mono);">(${o.source_coords})</span></td>
                <td style="padding: 8px 12px; font-weight: 600;">${o.target_name} <span style="color: var(--neon-cyan); font-family: var(--font-mono);">(${o.target_coords})</span></td>
                <td style="padding: 8px 12px; font-family: var(--font-mono);">
                  ${o.wood > 0 ? `<span style="color: #22c55e; margin-right: 4px;">${o.wood.toLocaleString()} Madeira</span>` : ''}
                  ${o.stone > 0 ? `<span style="color: #06b6d4; margin-right: 4px;">${o.stone.toLocaleString()} Argila</span>` : ''}
                  ${o.iron > 0 ? `<span style="color: #cbd5e1;">${o.iron.toLocaleString()} Ferro</span>` : ''}
                </td>
                <td style="padding: 8px 12px; font-weight: 700; color: #fff;">${o.merchants_required}</td>
                <td style="padding: 8px 12px; font-size: 0.78rem; color: var(--text-muted);">${o.reason}</td>
                <td style="padding: 8px 12px; text-align: right;">
                  <button class="btn btn-primary btn-sm btn-exec-single-order" 
                    data-src="${o.source_village_id}" 
                    data-tgt="${o.target_village_id}" 
                    data-w="${o.wood}" 
                    data-s="${o.stone}" 
                    data-i="${o.iron}" 
                    style="padding: 2px 8px; font-size: 0.75rem;">
                    Despachar
                  </button>
                </td>
              </tr>
            `).join("");

            // Event listener nos botões de envio individual
            elements.marketPlannedOrdersTbody.querySelectorAll(".btn-exec-single-order").forEach(btn => {
              btn.addEventListener("click", async () => {
                const sId = btn.getAttribute("data-src");
                const tId = btn.getAttribute("data-tgt");
                const w = parseInt(btn.getAttribute("data-w"), 10) || 0;
                const s = parseInt(btn.getAttribute("data-s"), 10) || 0;
                const i = parseInt(btn.getAttribute("data-i"), 10) || 0;
                try {
                  btn.disabled = true;
                  btn.textContent = "A enviar...";
                  const res = await window.api.sendMarketResources(sId, tId, w, s, i);
                  if (res && res.status === "success") {
                    addLogEntry("SUCCESS", "market", res.message || "Recursos despachados.");
                    loadMarketData();
                  } else {
                    alert(`Erro: ${res?.message || 'Falha ao despachar'}`);
                    btn.disabled = false;
                    btn.textContent = "Despachar";
                  }
                } catch (err) {
                  alert(`Erro: ${err.message}`);
                  btn.disabled = false;
                  btn.textContent = "Despachar";
                }
              });
            });
          }
        }
      }
    } catch (err) {
      console.error("Erro ao carregar dados do mercado:", err);
    }
  }

  // --- Handlers de Ações do Mercado ---
  if (elements.marketVillageSelector) {
    elements.marketVillageSelector.addEventListener("change", () => {
      loadMarketData(elements.marketVillageSelector.value);
    });
  }

  if (elements.btnMarketRefresh) {
    elements.btnMarketRefresh.addEventListener("click", () => {
      loadMarketData();
    });
  }

  const minTransferInputEl = document.getElementById("market-min-transfer-input");
  if (minTransferInputEl) {
    minTransferInputEl.addEventListener("change", async (e) => {
      const val = parseInt(e.target.value, 10);
      if (val && val >= 10) {
        try {
          await window.api.updateConfig({ market: { min_transfer_amount: val } });
          const disp = document.getElementById("market-min-transfer-disp");
          if (disp) disp.textContent = val.toLocaleString("pt-PT");
          addLogEntry("SUCCESS", "market", `Valor de transferência mínima de mercado atualizado para ${val}.`);
        } catch (err) {
          console.error("Erro ao atualizar min_transfer_amount:", err);
        }
      }
    });
  }

  const triggerBalancingHandler = async () => {
    try {
      const btn = elements.btnMarketBalanceNow || elements.btnMarketExecPlan;
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span>⏳</span> A Balancear...`;
      }
      addLogEntry("INFO", "market", "A iniciar ciclo de balanceamento global de recursos...");
      const res = await window.api.triggerMarketBalancing();
      addLogEntry("SUCCESS", "market", `Ciclo concluído: ${res?.executed || 0} transferências executadas.`);
      await loadMarketData();
    } catch (err) {
      addLogEntry("ERROR", "market", `Falha no balanceamento: ${err.message}`);
    } finally {
      if (elements.btnMarketBalanceNow) {
        elements.btnMarketBalanceNow.disabled = false;
        elements.btnMarketBalanceNow.innerHTML = `<span>⚡</span> Balancear Recursos Globalmente`;
      }
      if (elements.btnMarketExecPlan) {
        elements.btnMarketExecPlan.disabled = false;
        elements.btnMarketExecPlan.innerHTML = `<span>🚀</span> Executar Plano Agora`;
      }
    }
  };

  if (elements.btnMarketBalanceNow) elements.btnMarketBalanceNow.addEventListener("click", triggerBalancingHandler);
  if (elements.btnMarketExecPlan) elements.btnMarketExecPlan.addEventListener("click", triggerBalancingHandler);

  // Preenchimento de coordenadas ao selecionar aldeia de destino
  if (elements.marketSendTargetVillage) {
    elements.marketSendTargetVillage.addEventListener("change", () => {
      const opt = elements.marketSendTargetVillage.selectedOptions[0];
      if (opt && opt.getAttribute("data-x") && opt.getAttribute("data-y")) {
        if (elements.marketSendTargetX) elements.marketSendTargetX.value = opt.getAttribute("data-x");
        if (elements.marketSendTargetY) elements.marketSendTargetY.value = opt.getAttribute("data-y");
      }
    });
  }

  // Atalhos rápidos nos recursos (+1k, +5k)
  document.querySelectorAll(".btn-quick-res").forEach(btn => {
    btn.addEventListener("click", () => {
      const targetInputId = btn.getAttribute("data-target");
      const addAmount = parseInt(btn.getAttribute("data-add"), 10) || 0;
      const inp = document.getElementById(targetInputId);
      if (inp) {
        inp.value = (parseInt(inp.value, 10) || 0) + addAmount;
        updateSendMerchantsSummary();
      }
    });
  });

  function updateSendMerchantsSummary() {
    const w = parseInt(elements.marketSendWood?.value, 10) || 0;
    const s = parseInt(elements.marketSendStone?.value, 10) || 0;
    const i = parseInt(elements.marketSendIron?.value, 10) || 0;
    const total = w + s + i;
    const req = Math.ceil(total / 1000);
    if (elements.marketSendReqMerchants) {
      elements.marketSendReqMerchants.textContent = req.toString();
    }
  }

  [elements.marketSendWood, elements.marketSendStone, elements.marketSendIron].forEach(inp => {
    inp?.addEventListener("input", updateSendMerchantsSummary);
  });

  // Envio Manual de Mercadores
  if (elements.formSendMerchants) {
    elements.formSendMerchants.addEventListener("submit", async (e) => {
      e.preventDefault();
      const srcId = elements.marketVillageSelector?.value || (state.village && state.village.id);
      let tgtId = elements.marketSendTargetVillage?.value;
      const w = parseInt(elements.marketSendWood?.value, 10) || 0;
      const s = parseInt(elements.marketSendStone?.value, 10) || 0;
      const i = parseInt(elements.marketSendIron?.value, 10) || 0;

      if (!tgtId && elements.marketSendTargetX?.value && elements.marketSendTargetY?.value) {
        const tx = parseInt(elements.marketSendTargetX.value, 10);
        const ty = parseInt(elements.marketSendTargetY.value, 10);
        const vRes = await window.api.getAccountVillages();
        const found = (vRes?.villages || []).find(v => v.x === tx && v.y === ty);
        if (found) tgtId = found.id;
      }

      if (!tgtId) {
        alert("Por favor selecione a aldeia de destino da sua conta.");
        return;
      }

      if (w + s + i <= 0) {
        alert("Indique pelo menos 1.000 unidades de recursos para enviar.");
        return;
      }

      try {
        const submitBtn = document.getElementById("btn-submit-send-merchants");
        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.textContent = "A despachar...";
        }
        const res = await window.api.sendMarketResources(srcId, tgtId, w, s, i);
        if (res && res.status === "success") {
          addLogEntry("SUCCESS", "market", res.message || "Recursos despachados com sucesso!");
          if (elements.marketSendWood) elements.marketSendWood.value = "0";
          if (elements.marketSendStone) elements.marketSendStone.value = "0";
          if (elements.marketSendIron) elements.marketSendIron.value = "0";
          updateSendMerchantsSummary();
          await loadMarketData();
        } else {
          alert(`Erro: ${res?.message || 'Falha ao despachar mercadores'}`);
        }
      } catch (err) {
        alert(`Erro: ${err.message}`);
      } finally {
        const submitBtn = document.getElementById("btn-submit-send-merchants");
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = `<span>🚀</span> Despachar Mercadores`;
        }
      }
    });
  }

  // Rácio de troca no formulário de ofertas
  function updateOfferRatioDisplay() {
    const sellAmt = parseFloat(elements.marketOfferSellAmount?.value) || 1000;
    const buyAmt = parseFloat(elements.marketOfferBuyAmount?.value) || 1000;
    const ratio = (buyAmt / sellAmt).toFixed(2);
    if (elements.marketOfferRatioDisplay) {
      elements.marketOfferRatioDisplay.value = ratio;
    }
  }

  elements.marketOfferSellAmount?.addEventListener("input", updateOfferRatioDisplay);
  elements.marketOfferBuyAmount?.addEventListener("input", updateOfferRatioDisplay);

  // Criar Oferta no Mercado
  if (elements.formCreateMarketOffer) {
    elements.formCreateMarketOffer.addEventListener("submit", async (e) => {
      e.preventDefault();
      const vId = elements.marketVillageSelector?.value || (state.village && state.village.id);
      const sellRes = elements.marketOfferSellRes?.value || "wood";
      const sellAmt = parseInt(elements.marketOfferSellAmount?.value, 10) || 1000;
      const buyRes = elements.marketOfferBuyRes?.value || "stone";
      const buyAmt = parseInt(elements.marketOfferBuyAmount?.value, 10) || 1000;
      const maxTime = parseInt(elements.marketOfferMaxTime?.value, 10) || 10;
      const multi = parseInt(elements.marketOfferMulti?.value, 10) || 1;

      if (sellRes === buyRes) {
        alert("Não é possível trocar um recurso por ele mesmo.");
        return;
      }

      try {
        const btn = document.getElementById("btn-submit-create-offer");
        if (btn) {
          btn.disabled = true;
          btn.textContent = "A publicar...";
        }
        const res = await window.api.createMarketOffer(vId, sellRes, sellAmt, buyRes, buyAmt, maxTime, multi);
        if (res && res.status === "success") {
          addLogEntry("SUCCESS", "market", res.message || "Oferta publicada!");
          await loadMarketData();
        } else {
          alert(`Erro: ${res?.message || 'Falha ao criar oferta'}`);
        }
      } catch (err) {
        alert(`Erro: ${err.message}`);
      } finally {
        const btn = document.getElementById("btn-submit-create-offer");
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = `<span>📢</span> Publicar Oferta no Mercado`;
        }
      }
    });
  }

  // --- Handlers de Ativação / Desativação do Mercado ---
  if (elements.marketToggleEnabled) {
    elements.marketToggleEnabled.addEventListener("change", async () => {
      const isChecked = elements.marketToggleEnabled.checked;
      try {
        await window.api.toggleMarket(isChecked, null);
        addLogEntry("INFO", "market", `Funcionalidades do Mercado: ${isChecked ? 'ATIVADAS' : 'DESATIVADAS'}.`);
        await loadMarketData();
      } catch (err) {
        alert(`Erro ao alterar estado do mercado: ${err.message}`);
        elements.marketToggleEnabled.checked = !isChecked;
      }
    });
  }

  if (elements.marketToggleAutobalance) {
    elements.marketToggleAutobalance.addEventListener("change", async () => {
      const isChecked = elements.marketToggleAutobalance.checked;
      try {
        await window.api.toggleMarket(null, isChecked);
        addLogEntry("INFO", "market", `Auto-Balanceamento Automático: ${isChecked ? 'LIGADO' : 'DESLIGADO'}.`);
        await loadMarketData();
      } catch (err) {
        alert(`Erro ao alterar auto-balanceamento: ${err.message}`);
        elements.marketToggleAutobalance.checked = !isChecked;
      }
    });
  }

  // --- 4.6. Gestão de Edifícios & Fila de Construção (Roadmap) ---
  const BUILDING_ICONS = {
    main: "🏛️",
    barracks: "🗡️",
    stable: "🐎",
    garage: "🚜",
    church: "⛪",
    church_f: "⛪",
    snob: "👑",
    smith: "🔨",
    place: "🚩",
    statue: "🗿",
    market: "⚖️",
    wood: "🌲",
    stone: "🧱",
    iron: "⛏️",
    farm: "🌾",
    storage: "📦",
    hide: "🕳️",
    wall: "🧱",
  };

  const BUILDING_PT_NAMES = {
    main: "Edifício Principal",
    barracks: "Quartel",
    stable: "Estábulo",
    garage: "Oficina",
    church: "Igreja",
    church_f: "Primeira Igreja",
    snob: "Academia",
    smith: "Ferreiro",
    place: "Praça de Reunião",
    statue: "Estátua",
    market: "Mercado",
    wood: "Bosque",
    stone: "Poço de Argila",
    iron: "Mina de Ferro",
    farm: "Fazenda",
    storage: "Armazém",
    hide: "Esconderijo",
    wall: "Muralha",
  };

  let buildingPlanFilter = "pending";
  let cachedBuildingState = null;

  async function loadBuildingData(villageId = null) {
    try {
      const vId = villageId || (state.village && state.village.id);
      const res = await window.api.getBuildingState(vId);
      if (!res || res.status !== "success") return;
      cachedBuildingState = res;
      renderBuildingData(res);
    } catch (err) {
      console.error("Erro ao carregar dados de edifícios:", err);
    }
  }

  function renderBuildingData(data) {
    if (!data) return;

    if (elements.bldAutoToggle && data.enabled !== undefined) {
      elements.bldAutoToggle.checked = !!data.enabled;
    }
    updateBuildingStatusBadge(data.enabled);
    if (elements.bldIntervalSeconds && data.interval_seconds !== undefined && document.activeElement !== elements.bldIntervalSeconds) {
      elements.bldIntervalSeconds.value = data.interval_seconds;
    }

    if (elements.bldTemplateBadge) {
      elements.bldTemplateBadge.textContent = (data.template || "custom").toUpperCase();
    }

    const queue = data.queue || [];
    const maxQ = data.max_queue || 2;
    if (elements.bldQueueCount) elements.bldQueueCount.textContent = queue.length.toString();
    if (elements.bldMaxQueue) elements.bldMaxQueue.textContent = maxQ.toString();
    if (elements.bldQueueStatusText) {
      elements.bldQueueStatusText.textContent = queue.length >= maxQ ? "Fila Cheia" : "Disponível";
      elements.bldQueueStatusText.style.color = queue.length >= maxQ ? "var(--neon-amber)" : "var(--neon-emerald)";
    }

    // Próximo Alvo
    if (data.next_target) {
      const nt = data.next_target;
      const icon = BUILDING_ICONS[nt.building] || "🏛️";
      if (elements.bldNextTargetName) {
        elements.bldNextTargetName.innerHTML = `${icon} ${nt.building_name} <span style="color: var(--neon-cyan); font-family: var(--font-mono); font-size: 0.85rem;">(Nível ${nt.target_level})</span>`;
      }
      if (elements.bldNextTargetCost) {
        const costStr = `${nt.wood ? nt.wood.toLocaleString() : 0} Madeira | ${nt.stone ? nt.stone.toLocaleString() : 0} Argila | ${nt.iron ? nt.iron.toLocaleString() : 0} Ferro`;
        elements.bldNextTargetCost.innerHTML = `
          Custo: <span style="color: #fff;">${costStr}</span>
          ${nt.can_afford ? '<span style="color: #34d399; margin-left: 6px;">✓ Pronta para construir</span>' : '<span style="color: var(--neon-amber); margin-left: 6px;">⏳ A aguardar recursos</span>'}
        `;
      }
    } else {
      if (elements.bldNextTargetName) elements.bldNextTargetName.textContent = "Todas as metas concluídas!";
      if (elements.bldNextTargetCost) elements.bldNextTargetCost.textContent = "Nenhum edifício pendente no plano ativo.";
    }

    // Progresso do Plano
    const total = data.plan_total || 0;
    const completed = data.completed_count || 0;
    const pct = total > 0 ? Math.min(100, Math.round((completed / total) * 100)) : 100;
    if (elements.bldProgressPct) elements.bldProgressPct.textContent = `${pct}%`;
    if (elements.bldProgressCompleted) elements.bldProgressCompleted.textContent = completed.toString();
    if (elements.bldProgressTotal) elements.bldProgressTotal.textContent = total.toString();
    if (elements.bldProgressBar) elements.bldProgressBar.style.width = `${pct}%`;

    // Fila em Andamento
    if (elements.bldActiveQueueBadge) elements.bldActiveQueueBadge.textContent = queue.length.toString();
    if (elements.bldActiveQueueContainer) {
      if (queue.length === 0) {
        elements.bldActiveQueueContainer.innerHTML = `
          <div style="text-align: center; padding: 16px; color: var(--text-muted); font-size: 0.85rem;">
            Sem ordens em execução na fila. O bot avaliará o próximo edifício no próximo ciclo.
          </div>
        `;
      } else {
        elements.bldActiveQueueContainer.innerHTML = queue.map(q => {
          const icon = BUILDING_ICONS[q.building] || "🏛️";
          return `
            <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(15,23,42,0.65); padding: 10px 14px; border-radius: 8px; border: 1px solid var(--border-glass);">
              <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.3rem;">${icon}</span>
                <div>
                  <div style="font-weight: 700; color: #fff; font-size: 0.9rem;">
                    ${q.building_name} <span style="color: var(--neon-cyan); font-family: var(--font-mono);">(Nível ${q.target_level})</span>
                  </div>
                  <div style="font-size: 0.75rem; color: var(--text-muted);">Ordem ID: ${q.order_id}</div>
                </div>
              </div>
              <div style="display: flex; align-items: center; gap: 12px;">
                <div class="queue-timer" data-seconds="${parseTimerStringToSeconds(q.timer_str)}" style="font-family: var(--font-mono); color: var(--neon-amber); font-weight: 700; font-size: 0.95rem;">
                  ${q.timer_str || "A calcular..."}
                </div>
                <button class="btn btn-secondary btn-sm btn-cancel-bld-order" data-order-id="${q.order_id}" style="color: #f87171; border-color: rgba(239,68,68,0.35); padding: 3px 8px; font-size: 0.72rem;">
                  ✕ Cancelar
                </button>
              </div>
            </div>
          `;
        }).join("");

        elements.bldActiveQueueContainer.querySelectorAll(".btn-cancel-bld-order").forEach(btn => {
          btn.addEventListener("click", async () => {
            const oId = btn.getAttribute("data-order-id");
            if (confirm(`Tem a certeza que deseja cancelar a ordem de construção #${oId}?`)) {
              try {
                btn.disabled = true;
                btn.textContent = "A cancelar...";
                await window.api.cancelBuildingOrder(oId);
                await loadBuildingData();
              } catch (err) {
                alert(`Falha ao cancelar: ${err.message}`);
              }
            }
          });
        });
      }
    }

    // Tabela de Próximos Edifícios a Serem Upados
    const upcoming = data.upcoming || [];
    const filteredUpcoming = buildingPlanFilter === "pending"
      ? upcoming.filter(item => item.status !== "completed")
      : upcoming;

    if (elements.bldUpcomingCountBadge) {
      elements.bldUpcomingCountBadge.textContent = `${filteredUpcoming.length} passos`;
    }

    if (elements.bldUpcomingTableBody) {
      if (filteredUpcoming.length === 0) {
        elements.bldUpcomingTableBody.innerHTML = `
          <tr>
            <td colspan="5" style="padding: 24px; text-align: center; color: #34d399; font-weight: 600;">
              ✨ Todas as metas do plano de construção foram atingidas!
            </td>
          </tr>
        `;
      } else {
        elements.bldUpcomingTableBody.innerHTML = filteredUpcoming.map(item => {
          const icon = BUILDING_ICONS[item.building] || "🏛️";
          let statusBadge = "";
          if (item.status === "completed") {
            statusBadge = `<span class="bld-status-badge bld-status-completed">✓ Concluído</span>`;
          } else if (item.status === "in_progress") {
            statusBadge = `<span class="bld-status-badge bld-status-inprogress">⏳ Em Fila</span>`;
          } else if (item.status === "next") {
            statusBadge = `<span class="bld-status-badge bld-status-next">⚡ Próximo Alvo</span>`;
          } else if (item.status === "blocked") {
            statusBadge = `<span class="bld-status-badge bld-status-blocked" title="Falta: ${item.missing_requirements.join(', ')}">🔒 Requisitos</span>`;
          } else {
            statusBadge = `<span class="bld-status-badge bld-status-pending">🕒 Pendente</span>`;
          }

          const costStr = (item.wood > 0 || item.stone > 0 || item.iron > 0)
            ? `<span style="color: #22c55e;">${item.wood.toLocaleString()}M</span> / <span style="color: #06b6d4;">${item.stone.toLocaleString()}A</span> / <span style="color: #cbd5e1;">${item.iron.toLocaleString()}F</span>`
            : `<span style="color: var(--text-muted);">-</span>`;

          const isNext = item.status === "next";
          const rowBg = isNext ? "rgba(245, 158, 11, 0.08)" : (item.status === "in_progress" ? "rgba(6, 182, 212, 0.06)" : "transparent");

          return `
            <tr style="border-bottom: 1px solid var(--border-subtle); background: ${rowBg}; transition: background 0.15s ease;">
              <td style="padding: 9px 12px; font-family: var(--font-mono); color: var(--text-muted); font-size: 0.78rem;">#${item.step}</td>
              <td style="padding: 9px 12px; font-weight: 600;">
                <span style="margin-right: 6px;">${icon}</span>
                ${item.building_name}
                <span style="color: var(--text-muted); font-size: 0.75rem; font-weight: normal;">(${item.building})</span>
              </td>
              <td style="padding: 9px 12px; font-family: var(--font-mono);">
                <span style="color: var(--text-muted);">${item.current_level}</span>
                <span style="color: var(--neon-cyan); margin: 0 4px;">➔</span>
                <strong style="color: #fff;">Nível ${item.target_level}</strong>
              </td>
              <td style="padding: 9px 12px; font-family: var(--font-mono); font-size: 0.8rem;">
                ${costStr}
              </td>
              <td style="padding: 9px 12px; text-align: center;">
                ${statusBadge}
              </td>
            </tr>
          `;
        }).join("");
      }
    }

    // Grelha de Níveis Atuais dos Edifícios da Aldeia
    if (elements.bldVillageLevelsGrid && data.buildings) {
      const bEntries = Object.entries(data.buildings);
      elements.bldVillageLevelsGrid.innerHTML = bEntries.map(([bId, lvl]) => {
        const icon = BUILDING_ICONS[bId] || "🏛️";
        const bName = BUILDING_PT_NAMES[bId] || bId;
        const virt = data.virtual_levels ? data.virtual_levels[bId] : lvl;
        const hasQueued = virt > lvl;
        return `
          <div class="village-bld-card">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 1.1rem;">${icon}</span>
              <div>
                <div style="font-size: 0.78rem; font-weight: 600; color: #fff;">${bName}</div>
                <div style="font-size: 0.7rem; color: var(--text-muted);">${bId}</div>
              </div>
            </div>
            <div style="font-family: var(--font-mono); font-size: 0.88rem; font-weight: 700; color: ${hasQueued ? 'var(--neon-cyan)' : '#fff'};">
              Nvl ${lvl}${hasQueued ? ` <span style="font-size: 0.72rem; color: var(--neon-amber);" title="Na fila: Nível ${virt}">(+${virt - lvl})</span>` : ''}
            </div>
          </div>
        `;
      }).join("");
    }
  }

  // Filtros do Plano de Construção
  if (elements.btnFilterPlanPending) {
    elements.btnFilterPlanPending.addEventListener("click", () => {
      buildingPlanFilter = "pending";
      elements.btnFilterPlanPending.style.background = "rgba(6,182,212,0.2)";
      elements.btnFilterPlanPending.style.color = "var(--neon-cyan)";
      if (elements.btnFilterPlanAll) {
        elements.btnFilterPlanAll.style.background = "";
        elements.btnFilterPlanAll.style.color = "";
      }
      if (cachedBuildingState) renderBuildingData(cachedBuildingState);
    });
  }

  if (elements.btnFilterPlanAll) {
    elements.btnFilterPlanAll.addEventListener("click", () => {
      buildingPlanFilter = "all";
      elements.btnFilterPlanAll.style.background = "rgba(6,182,212,0.2)";
      elements.btnFilterPlanAll.style.color = "var(--neon-cyan)";
      if (elements.btnFilterPlanPending) {
        elements.btnFilterPlanPending.style.background = "";
        elements.btnFilterPlanPending.style.color = "";
      }
      if (cachedBuildingState) renderBuildingData(cachedBuildingState);
    });
  }

  if (elements.btnRefreshBuildingTab) {
    elements.btnRefreshBuildingTab.addEventListener("click", async () => {
      try {
        elements.btnRefreshBuildingTab.disabled = true;
        elements.btnRefreshBuildingTab.innerHTML = "<span>⏳</span> A ler...";
        addLogEntry("INFO", "building", "A atualizar dados do Edifício Principal e fila de construção...");
        await window.api.refreshVillage();
        await loadBuildingData();
        addLogEntry("SUCCESS", "building", "Edifício Principal e fila de construção atualizados com sucesso!");
      } catch (err) {
        addLogEntry("WARNING", "building", `Falha ao atualizar dados de edifícios: ${err.message}`);
      } finally {
        elements.btnRefreshBuildingTab.disabled = false;
        elements.btnRefreshBuildingTab.innerHTML = "<span>🔄</span> Atualizar";
      }
    });
  }

  if (elements.bldAutoToggle) {
    elements.bldAutoToggle.addEventListener("change", async () => {
      const isEnabled = elements.bldAutoToggle.checked;
      updateBuildingStatusBadge(isEnabled);
      try {
        const intervalSec = parseFloat(elements.bldIntervalSeconds?.value) || 75;
        await window.api.toggleBuilding(isEnabled, intervalSec);
        addLogEntry("INFO", "building", `Construção Automática ${isEnabled ? 'ATIVADA' : 'DESATIVADA'}.`);
      } catch (err) {
        addLogEntry("ERROR", "building", `Erro ao alternar auto-construção: ${err.message}`);
      }
    });
  }

  if (elements.bldIntervalSeconds) {
    elements.bldIntervalSeconds.addEventListener("change", async () => {
      const intervalSec = parseFloat(elements.bldIntervalSeconds.value) || 75;
      const isEnabled = elements.bldAutoToggle ? elements.bldAutoToggle.checked : true;
      try {
        await window.api.toggleBuilding(isEnabled, intervalSec);
        addLogEntry("INFO", "building", `Intervalo de auto-construção atualizado para ${intervalSec}s.`);
      } catch (err) {
        console.error(err);
      }
    });
  }

  if (elements.btnTriggerBuildTab) {
    elements.btnTriggerBuildTab.addEventListener("click", async () => {
      try {
        elements.btnTriggerBuildTab.disabled = true;
        elements.btnTriggerBuildTab.textContent = "A construir...";
        const res = await window.api.triggerBuild();
        addLogEntry("INFO", "building", `Ciclo de construção disparado! ${res?.message || ''}`);
        await loadBuildingData();
      } catch (err) {
        addLogEntry("ERROR", "building", `Erro ao forçar construção: ${err.message}`);
      } finally {
        elements.btnTriggerBuildTab.disabled = false;
        elements.btnTriggerBuildTab.innerHTML = `<span>🔨</span> Construir Agora`;
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
      addLogEntry("INFO", "account", "A atualizar recursos, tropas e estado da aldeia...");
      const res = await window.api.refreshVillage();
      if (res && res.data) {
        applyStateData(res.data);
      }
      await loadBuildingData();
      await loadRecruitmentData();
      checkQuestStatus();
      addLogEntry("SUCCESS", "account", "Recursos, tropas e filas atualizados com sucesso!");
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

  // --- 9. Painel de Recrutamento: Modelos de Tropas (Ataque, Defesa & Customizados) & Fila Ativa ---
  const REC_UNITS_METADATA = [
    { id: "spear", name: "Lanceiro", icon: "🗡️", pop: 1, type: "defense" },
    { id: "sword", name: "Espadachim", icon: "🛡️", pop: 1, type: "defense" },
    { id: "axe", name: "Bárbaro / Viking", icon: "🪓", pop: 1, type: "attack" },
    { id: "archer", name: "Arqueiro", icon: "🏹", pop: 1, type: "defense" },
    { id: "spy", name: "Espião / Batedor", icon: "👁️", pop: 2, type: "utility" },
    { id: "light", name: "Cavalaria Leve", icon: "🐎", pop: 4, type: "attack" },
    { id: "marcher", name: "Arqueiro a Cavalo", icon: "🏹🐎", pop: 5, type: "attack" },
    { id: "heavy", name: "Cavalaria Pesada", icon: "🛡️🐎", pop: 6, type: "defense" },
    { id: "ram", name: "Aríete", icon: "🚪", pop: 5, type: "attack" },
    { id: "catapult", name: "Catapulta", icon: "🪨", pop: 8, type: "utility" },
  ];

  state.activeRecModelTab = "attack";
  state.recruitmentModels = {
    attack: { spear: 0, sword: 0, axe: 6000, archer: 0, spy: 50, light: 3000, marcher: 0, heavy: 0, ram: 250, catapult: 10 },
    defense: { spear: 7000, sword: 7000, axe: 0, archer: 0, spy: 50, light: 0, marcher: 0, heavy: 1000, ram: 0, catapult: 0 },
  };

  function calculateModelPopulation(modelKey) {
    const model = state.recruitmentModels[modelKey] || {};
    let totalPop = 0;
    for (const u of REC_UNITS_METADATA) {
      const count = parseInt(model[u.id], 10) || 0;
      totalPop += count * u.pop;
    }
    return totalPop;
  }

  function updateModelTotalPopDisplay() {
    const pop = calculateModelPopulation(state.activeRecModelTab);
    const popEl = document.getElementById("rec-model-total-pop");
    if (popEl) {
      popEl.textContent = `${pop.toLocaleString("pt-PT")} pop`;
    }
  }

  function renderModelTabs() {
    const container = document.getElementById("rec-models-tabs-container");
    if (!container) return;

    const allKeys = Object.keys(state.recruitmentModels || { attack: {}, defense: {} });
    if (!allKeys.includes("attack")) allKeys.unshift("attack");
    if (!allKeys.includes("defense")) allKeys.splice(1, 0, "defense");

    container.innerHTML = allKeys.map(key => {
      const isActive = key === state.activeRecModelTab;
      let label = "";
      let activeStyle = "";
      let inactiveStyle = "";

      if (key === "attack") {
        label = "<span>⚔️</span> Ataque";
        activeStyle = "border: 1px solid rgba(239, 68, 68, 0.7); background: rgba(239, 68, 68, 0.25); color: #fca5a5;";
        inactiveStyle = "border: 1px solid rgba(239, 68, 68, 0.3); background: rgba(239, 68, 68, 0.08); color: #fca5a5;";
      } else if (key === "defense") {
        label = "<span>🛡️</span> Defesa";
        activeStyle = "border: 1px solid rgba(59, 130, 246, 0.7); background: rgba(59, 130, 246, 0.25); color: #93c5fd;";
        inactiveStyle = "border: 1px solid rgba(59, 130, 246, 0.3); background: rgba(59, 130, 246, 0.08); color: #93c5fd;";
      } else {
        const cap = key.charAt(0).toUpperCase() + key.slice(1);
        label = `<span>✨</span> ${cap}`;
        activeStyle = "border: 1px solid rgba(245, 158, 11, 0.7); background: rgba(245, 158, 11, 0.25); color: #fde68a;";
        inactiveStyle = "border: 1px solid rgba(245, 158, 11, 0.3); background: rgba(245, 158, 11, 0.08); color: #fde68a;";
      }

      return `
        <button type="button" class="btn btn-secondary rec-model-tab-btn" data-model="${key}" style="padding: 6px 14px; font-weight: 700; font-size: 0.85rem; border-radius: 6px; cursor: pointer; transition: all 0.2s ease; ${isActive ? activeStyle : inactiveStyle}">
          ${label}
        </button>
      `;
    }).join("");

    container.querySelectorAll(".rec-model-tab-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const targetModel = btn.getAttribute("data-model");
        switchRecModelTab(targetModel);
      });
    });
  }

  function renderActiveModelUnits() {
    const gridContainer = document.getElementById("grid-model-active-units");
    if (!gridContainer) return;

    const activeKey = state.activeRecModelTab || "attack";
    const activeModel = state.recruitmentModels[activeKey] || {};

    gridContainer.innerHTML = REC_UNITS_METADATA.map(u => {
      const val = activeModel[u.id] !== undefined ? activeModel[u.id] : 0;
      return `
        <div class="unit-model-card" style="flex: 1 1 200px; max-width: 320px; background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border-subtle); border-radius: 8px; padding: 12px 14px; display: flex; flex-direction: column; gap: 8px; transition: border-color 0.2s ease;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 1.3rem;">${u.icon}</span>
              <div>
                <strong style="font-size: 0.88rem; color: #fff;">${u.name}</strong>
                <div style="font-size: 0.72rem; color: var(--text-muted);">${u.pop} pop / unid.</div>
              </div>
            </div>
          </div>
          <div>
            <label style="font-size: 0.75rem; color: var(--text-muted); display: block; margin-bottom: 4px;">Alvo de Tropas:</label>
            <input type="number" class="form-control model-rec-input" data-model="${activeKey}" data-unit="${u.id}" value="${val}" min="0" style="width: 100%; font-family: var(--font-mono); font-size: 0.9rem; text-align: right; padding: 6px 10px; background: rgba(0,0,0,0.3); border: 1px solid var(--border-subtle); color: #fff; border-radius: 6px;">
          </div>
        </div>
      `;
    }).join("");

    // Adiciona listener para recalcular população ao digitar
    gridContainer.querySelectorAll(".model-rec-input").forEach(inp => {
      inp.addEventListener("input", (e) => {
        const model = e.target.dataset.model;
        const unit = e.target.dataset.unit;
        const count = parseInt(e.target.value, 10) || 0;
        if (!state.recruitmentModels[model]) state.recruitmentModels[model] = {};
        state.recruitmentModels[model][unit] = count;
        updateModelTotalPopDisplay();
      });
    });

    updateModelTotalPopDisplay();
  }

  function switchRecModelTab(tabKey) {
    state.activeRecModelTab = tabKey;
    const banner = document.getElementById("rec-model-info-banner");
    const btnDelete = document.getElementById("btn-delete-active-model");

    if (banner) {
      if (tabKey === "attack") {
        banner.style.background = "rgba(239, 68, 68, 0.08)";
        banner.style.borderLeftColor = "#ef4444";
        banner.style.color = "#fca5a5";
        banner.innerHTML = `<strong>⚔️ Modelo de Aldeia de Ataque:</strong> Foco em poder de destruição (Viking/Bárbaro, Cavalaria Leve, Aríetes). Estas metas serão seguidas em todas as aldeias marcadas como <em>Ataque</em> na página de Multi-Aldeias.`;
      } else if (tabKey === "defense") {
        banner.style.background = "rgba(59, 130, 246, 0.08)";
        banner.style.borderLeftColor = "#3b82f6";
        banner.style.color = "#93c5fd";
        banner.innerHTML = `<strong>🛡️ Modelo de Aldeia de Defesa:</strong> Foco em sustentação e apoio rápido (Lanceiros, Espadachins, Cavalaria Pesada). Estas metas serão seguidas em todas as aldeias marcadas como <em>Defesa</em> na página de Multi-Aldeias.`;
      } else {
        const cap = tabKey.charAt(0).toUpperCase() + tabKey.slice(1);
        banner.style.background = "rgba(245, 158, 11, 0.08)";
        banner.style.borderLeftColor = "#f59e0b";
        banner.style.color = "#fde68a";
        banner.innerHTML = `<strong>✨ Modelo Customizado '${cap}':</strong> Modelo personalizado para atribuição direta em aldeias conquistadas no Mundo 117.`;
      }
    }

    if (btnDelete) {
      btnDelete.style.display = (tabKey !== "attack" && tabKey !== "defense") ? "inline-flex" : "none";
    }

    renderModelTabs();
    renderActiveModelUnits();
    updateModelTotalPopDisplay();
  }

  // Botão: Adicionar Modelo Customizado
  document.getElementById("btn-add-custom-model")?.addEventListener("click", () => {
    const rawName = prompt("Introduza o nome do novo modelo de tropas (ex: Nuke, Farm, Apoio_Rapido):");
    if (!rawName) return;
    const name = rawName.toLowerCase().replace(/[^a-z0-9_]/g, "_").trim();
    if (!name) {
      alert("Nome inválido!");
      return;
    }
    if (state.recruitmentModels[name]) {
      alert(`O modelo '${name}' já existe!`);
      switchRecModelTab(name);
      return;
    }

    // Cria novo modelo com valores zerados
    const newModel = {};
    REC_UNITS_METADATA.forEach(u => { newModel[u.id] = 0; });
    state.recruitmentModels[name] = newModel;

    switchRecModelTab(name);
    addLogEntry("INFO", "recruitment", `Novo modelo de tropas '${name}' criado. Ajuste os alvos e clique em 'Guardar Modelos'.`);
  });

  // Botão: Eliminar Modelo Ativo
  document.getElementById("btn-delete-active-model")?.addEventListener("click", async () => {
    const targetModel = state.activeRecModelTab;
    if (targetModel === "attack" || targetModel === "defense") {
      alert("Não é possível eliminar os modelos padrão Ataque e Defesa.");
      return;
    }

    if (!confirm(`Tem a certeza que deseja eliminar o modelo '${targetModel}'?`)) return;

    try {
      await window.api.deleteRecruitmentModel(targetModel);
      delete state.recruitmentModels[targetModel];
      addLogEntry("SUCCESS", "recruitment", `Modelo '${targetModel}' removido com sucesso.`);
      switchRecModelTab("attack");
      
      // Atualiza dropdown de categorias no multi-aldeia
      if (state.account?.villages) {
        renderVillagesOverview(state.account.villages, state.resource_balance);
      }
    } catch (err) {
      alert(`Falha ao eliminar modelo: ${err.message}`);
    }
  });

  async function loadRecruitmentIntoForm() {
    await loadRecruitmentData();
  }

  async function loadRecruitmentData(villageId = null) {
    try {
      const vId = villageId || (state.village && state.village.id);
      
      // Carrega modelos de tropas
      const modelsRes = await window.api.getRecruitmentModels();
      if (modelsRes && modelsRes.models) {
        state.recruitmentModels = { ...state.recruitmentModels, ...modelsRes.models };
        renderModelTabs();
        renderActiveModelUnits();
      }

      // Carrega estado de recrutamento e filas ativas
      const res = await window.api.getRecruitmentState(vId);
      if (res && res.status === "success") {
        renderRecruitmentData(res);
      }
    } catch (e) {
      console.warn("Falha ao carregar dados de recrutamento:", e);
    }
  }

  function renderRecruitmentData(data) {
    if (!data) return;

    // 1. Modelos de Tropas
    if (data.models) {
      state.recruitmentModels = { ...state.recruitmentModels, ...data.models };
      renderModelTabs();
      renderActiveModelUnits();
    }

    // 2. Filas Ativas de Recrutamento em Andamento
    const activeOrders = data.active_orders || [];
    const badge = document.getElementById("rec-active-queue-badge");
    const container = document.getElementById("rec-active-queue-container");

    if (badge) {
      badge.textContent = `${activeOrders.length} ordens`;
    }

    if (container) {
      if (activeOrders.length === 0) {
        container.innerHTML = `
          <div style="text-align: center; padding: 18px; color: var(--text-muted); font-size: 0.85rem;">
            Nenhuma tropa a ser produzida no momento.
          </div>
        `;
      } else {
        container.innerHTML = activeOrders.map(ord => {
          const uMeta = REC_UNITS_METADATA.find(m => m.id === ord.unit);
          const uIcon = uMeta ? uMeta.icon : (UNIT_ICONS[ord.unit] || "🪖");
          const uName = uMeta ? uMeta.name : (ord.unit_name || ord.unit);
          const bldName = ord.building === "barracks" ? "Quartel" : (ord.building === "stable" ? "Estábulo" : "Oficina");
          return `
            <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(15,23,42,0.65); padding: 10px 14px; border-radius: 8px; border: 1px solid var(--border-glass);">
              <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.3rem;">${uIcon}</span>
                <div>
                  <div style="font-weight: 700; color: #fff; font-size: 0.9rem;">
                    ${ord.count}x ${uName}
                    <span style="color: var(--neon-cyan); font-size: 0.75rem; margin-left: 6px;">(${bldName})</span>
                  </div>
                  <div style="font-size: 0.75rem; color: var(--text-muted);">
                    ${ord.finish_time ? `Conclusão: ${ord.finish_time}` : 'Em produção no momento'}
                  </div>
                </div>
              </div>
              <div style="display: flex; align-items: center; gap: 12px;">
                <div class="queue-timer" data-seconds="${parseTimerStringToSeconds(ord.timer_str)}" style="font-family: var(--font-mono); color: var(--neon-amber); font-weight: 700; font-size: 0.95rem;">
                  ${ord.timer_str || "A produzir..."}
                </div>
              </div>
            </div>
          `;
        }).join("");
      }
    }
  }

  async function saveRecruitmentModelsHandler() {
    const btnTop = document.getElementById("btn-save-recruitment");
    const btnBottom = document.getElementById("btn-save-recruitment-bottom");
    if (btnTop) { btnTop.disabled = true; btnTop.textContent = "A guardar..."; }
    if (btnBottom) { btnBottom.disabled = true; btnBottom.textContent = "A guardar..."; }

    try {
      // Coleta valores do modelo atualmente visível
      const activeKey = state.activeRecModelTab;
      if (!state.recruitmentModels[activeKey]) state.recruitmentModels[activeKey] = {};
      
      document.querySelectorAll(".model-rec-input").forEach(inp => {
        const model = inp.dataset.model;
        const unit = inp.dataset.unit;
        const count = parseInt(inp.value, 10) || 0;
        if (!state.recruitmentModels[model]) state.recruitmentModels[model] = {};
        state.recruitmentModels[model][unit] = count;
      });

      await window.api.saveRecruitmentModels(null, null, state.recruitmentModels);
      addLogEntry("SUCCESS", "recruitment", "Todos os modelos de tropas (Ataque, Defesa e Customizados) foram guardados e persistidos no config.json.");
      alert("Modelos de tropas guardados e persistidos com sucesso!");
      
      // Atualiza lista de modelos na interface e nos dropdowns de multi-aldeia
      renderModelTabs();
      renderActiveModelUnits();
      if (state.account?.villages) {
        renderVillagesOverview(state.account.villages, state.resource_balance);
      }
    } catch (err) {
      addLogEntry("ERROR", "recruitment", `Erro ao guardar modelos: ${err.message}`);
      alert(`Falha ao guardar modelos: ${err.message}`);
    } finally {
      if (btnTop) { btnTop.disabled = false; btnTop.innerHTML = "<span>💾</span> Guardar Modelos"; }
      if (btnBottom) { btnBottom.disabled = false; btnBottom.innerHTML = "<span>💾</span> Guardar Modelos"; }
    }
  }

  document.getElementById("btn-save-recruitment")?.addEventListener("click", saveRecruitmentModelsHandler);
  document.getElementById("btn-save-recruitment-bottom")?.addEventListener("click", saveRecruitmentModelsHandler);

  document.getElementById("btn-refresh-rec-tab")?.addEventListener("click", async () => {
    const btn = document.getElementById("btn-refresh-rec-tab");
    try {
      if (btn) { btn.disabled = true; btn.innerHTML = "<span>⏳</span> A ler..."; }
      addLogEntry("INFO", "recruitment", "A atualizar filas de produção e tropas...");
      await window.api.refreshVillage();
      await loadRecruitmentData();
      addLogEntry("SUCCESS", "recruitment", "Dados militares e produção atualizados com sucesso!");
    } catch (err) {
      addLogEntry("WARNING", "recruitment", `Falha ao atualizar recrutamento: ${err.message}`);
    } finally {
      if (btn) { btn.disabled = false; btn.innerHTML = "<span>🔄</span> Atualizar"; }
    }
  });

  // Inicialização do painel de modelos de tropas
  renderModelTabs();
  renderActiveModelUnits();
  loadRecruitmentData();

  // --- 8. Gestão e Renderização de Estatísticas & Métricas ---
  state.statsRange = "24";
  state.statsMetric = "total";
  state.statsSummaryData = null;
  state.statsHistoryData = null;

  function updateDashboardStats(summary) {
    if (!summary) return;
    const l24 = summary.last_24h || {};
    const tot = summary.totals_all_time || {};
    if (elements.dashLoot24h) {
      elements.dashLoot24h.textContent = (l24.total || 0).toLocaleString("pt-PT");
    }
    if (elements.dashHourlyRate) {
      elements.dashHourlyRate.textContent = `+${(l24.hourly_rate || 0).toLocaleString("pt-PT")} / hora`;
    }
    if (elements.dashSuccessRate) {
      elements.dashSuccessRate.textContent = `${tot.success_rate || 100}%`;
    }
    if (elements.dashAttacks24h) {
      elements.dashAttacks24h.textContent = l24.attacks_sent || 0;
    }
  }

  async function loadAndRenderStats() {
    try {
      const hours = parseInt(state.statsRange, 10) || 24;
      const [sumRes, histRes] = await Promise.all([
        window.api.getStatsSummary(),
        window.api.getStatsHistory(hours, 7),
      ]);

      if (sumRes?.summary) {
        state.statsSummaryData = sumRes.summary;
        renderStatsKpis(sumRes.summary);
        updateDashboardStats(sumRes.summary);
        renderRecruitmentMatrix(sumRes.summary.recruitment_by_unit || {});
      }

      if (histRes?.history) {
        state.statsHistoryData = histRes.history;
        renderStatsChart(histRes.history);
        renderRecentActivityTable(histRes.history.recent_loot || [], histRes.history.recent_commands || []);
      }
    } catch (err) {
      console.error("Erro ao carregar estatísticas:", err);
    }
  }

  function renderStatsKpis(summary) {
    const l24 = summary.last_24h || {};
    const tot = summary.totals_all_time || {};

    if (elements.statsKpiLoot24h) elements.statsKpiLoot24h.textContent = (l24.total || 0).toLocaleString("pt-PT");
    if (elements.statsHourlyRateBadge) elements.statsHourlyRateBadge.textContent = `⚡ +${(l24.hourly_rate || 0).toLocaleString("pt-PT")} / h`;
    if (elements.statsKpiWood24h) elements.statsKpiWood24h.textContent = (l24.wood || 0).toLocaleString("pt-PT");
    if (elements.statsKpiStone24h) elements.statsKpiStone24h.textContent = (l24.stone || 0).toLocaleString("pt-PT");
    if (elements.statsKpiIron24h) elements.statsKpiIron24h.textContent = (l24.iron || 0).toLocaleString("pt-PT");
    if (elements.statsKpiLootAlltime) elements.statsKpiLootAlltime.textContent = (tot.total || 0).toLocaleString("pt-PT");

    if (elements.statsKpiVillagesFarmed) elements.statsKpiVillagesFarmed.textContent = (tot.villages_farmed || 0).toLocaleString("pt-PT");
    if (elements.statsKpiVillages24h) elements.statsKpiVillages24h.textContent = (l24.villages_farmed || 0).toLocaleString("pt-PT");
    
    const perVillage = tot.villages_farmed > 0 ? Math.round(tot.total / tot.villages_farmed) : 0;
    if (elements.statsKpiLootPerVillage) elements.statsKpiLootPerVillage.textContent = perVillage.toLocaleString("pt-PT");

    if (elements.statsKpiAttacksSent) elements.statsKpiAttacksSent.textContent = (tot.attacks_sent || 0).toLocaleString("pt-PT");
    if (elements.statsSuccessRateBadge) {
      elements.statsSuccessRateBadge.textContent = `${tot.success_rate || 100}% OK`;
      elements.statsSuccessRateBadge.style.color = (tot.success_rate || 100) >= 90 ? "var(--neon-emerald)" : "var(--neon-amber)";
    }
    if (elements.statsKpiAttacksSuccess) elements.statsKpiAttacksSuccess.textContent = (tot.attacks_successful || 0).toLocaleString("pt-PT");
    if (elements.statsKpiAttacksTotal) elements.statsKpiAttacksTotal.textContent = (tot.attacks_sent || 0).toLocaleString("pt-PT");
    if (elements.statsKpiAttacks24h) elements.statsKpiAttacks24h.textContent = (l24.attacks_sent || 0).toLocaleString("pt-PT");

    if (elements.statsKpiTroopsRecruited) elements.statsKpiTroopsRecruited.textContent = (tot.troops_recruited || 0).toLocaleString("pt-PT");
    if (elements.statsKpiBuildingsCount) elements.statsKpiBuildingsCount.textContent = (tot.buildings_constructed || 0).toLocaleString("pt-PT");
    if (elements.statsActiveWorldText) elements.statsActiveWorldText.textContent = summary.world || state.currentWorld || "pt117";
  }

  function renderStatsChart(history) {
    const canvas = elements.statsLootCanvas;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const isDaily = state.statsRange === "168";
    const series = isDaily ? (history.daily || []) : (history.hourly || []);
    if (!series || series.length === 0) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }

    const metric = state.statsMetric || "total";
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = rect.height;
    const paddingLeft = 50;
    const paddingRight = 20;
    const paddingTop = 20;
    const paddingBottom = 30;
    const chartW = w - paddingLeft - paddingRight;
    const chartH = h - paddingTop - paddingBottom;

    ctx.clearRect(0, 0, w, h);

    const values = series.map((item) => item[metric] || 0);
    const maxVal = Math.max(...values, 100);
    const gridMax = Math.ceil(maxVal * 1.15);

    // Linhas horizontais de grade
    ctx.strokeStyle = "rgba(255, 255, 255, 0.07)";
    ctx.lineWidth = 1;
    ctx.font = "10px Inter, sans-serif";
    ctx.fillStyle = "#64748b";
    ctx.textAlign = "right";

    const gridSteps = 4;
    for (let i = 0; i <= gridSteps; i++) {
      const y = paddingTop + chartH - (i / gridSteps) * chartH;
      const v = Math.round((i / gridSteps) * gridMax);
      ctx.beginPath();
      ctx.moveTo(paddingLeft, y);
      ctx.lineTo(w - paddingRight, y);
      ctx.stroke();
      ctx.fillText(v >= 1000 ? `${Math.round(v / 1000)}k` : String(v), paddingLeft - 8, y + 3);
    }

    // Cores conforme a métrica
    let barColor = "rgba(139, 92, 246, 0.9)";
    let gradTop = "rgba(139, 92, 246, 0.5)";
    let gradBot = "rgba(139, 92, 246, 0.05)";

    if (metric === "wood") {
      barColor = "#10b981";
      gradTop = "rgba(16, 185, 129, 0.5)";
      gradBot = "rgba(16, 185, 129, 0.05)";
    } else if (metric === "stone") {
      barColor = "#06b6d4";
      gradTop = "rgba(6, 182, 212, 0.5)";
      gradBot = "rgba(6, 182, 212, 0.05)";
    } else if (metric === "iron") {
      barColor = "#cbd5e1";
      gradTop = "rgba(203, 213, 225, 0.4)";
      gradBot = "rgba(203, 213, 225, 0.05)";
    }

    const n = series.length;
    const barWidth = Math.max(4, (chartW / n) * 0.65);
    const stepX = chartW / n;

    ctx.textAlign = "center";
    ctx.fillStyle = "#64748b";

    // Desenha barras
    series.forEach((item, idx) => {
      const val = item[metric] || 0;
      const barH = (val / gridMax) * chartH;
      const x = paddingLeft + (idx * stepX) + (stepX - barWidth) / 2;
      const y = paddingTop + chartH - barH;

      // Gradiente da barra
      const grad = ctx.createLinearGradient(0, y, 0, paddingTop + chartH);
      grad.addColorStop(0, gradTop);
      grad.addColorStop(1, gradBot);

      ctx.fillStyle = grad;
      ctx.fillRect(x, y, barWidth, barH);

      // Borda superior da barra
      ctx.fillStyle = barColor;
      ctx.fillRect(x, y, barWidth, Math.min(2, barH));

      // Labels no eixo X
      if (isDaily || idx % 3 === 0 || idx === n - 1) {
        const labelText = isDaily ? (item.label || item.date) : (item.hour || "");
        ctx.fillStyle = "#64748b";
        ctx.fillText(labelText, x + barWidth / 2, paddingTop + chartH + 18);
      }
    });

    // Linha de Média Móvel
    const totalSum = values.reduce((a, b) => a + b, 0);
    const avgVal = totalSum / n;
    const avgY = paddingTop + chartH - (avgVal / gridMax) * chartH;

    ctx.strokeStyle = "rgba(6, 182, 212, 0.7)";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(paddingLeft, avgY);
    ctx.lineTo(w - paddingRight, avgY);
    ctx.stroke();
    ctx.setLineDash([]);

    if (elements.statsChartSummaryText) {
      elements.statsChartSummaryText.textContent = `Total no Período: ${totalSum.toLocaleString("pt-PT")} | Média: ${Math.round(avgVal).toLocaleString("pt-PT")} / balde`;
    }
  }

  function renderRecruitmentMatrix(recMap) {
    const container = elements.statsRecruitmentMatrix;
    if (!container) return;

    const unitIcons = {
      spear: "🗡️ Lanceiro",
      sword: "🛡️ Espadachim",
      axe: "🪓 Viking",
      archer: "🏹 Arqueiro",
      spy: "🐎 Explorador",
      light: "⚡ Cav. Leve",
      marcher: "🏹 Cav. Arqueiro",
      heavy: "🛡️ Cav. Pesada",
      ram: "🪵 Aríete",
      catapult: "☄️ Catapulta",
      knight: "👑 Paladino",
      snob: "📜 Nobre",
    };

    const entries = Object.entries(recMap).filter(([_, count]) => count > 0);
    if (entries.length === 0) {
      container.innerHTML = `<div style="padding: 12px; text-align: center; color: var(--text-muted); font-size: 0.8rem; grid-column: 1 / -1;">Nenhuma tropa recrutada nesta sessão ainda.</div>`;
      return;
    }

    container.innerHTML = entries
      .map(([unit, count]) => {
        const label = unitIcons[unit] || unit;
        return `
          <div class="stats-unit-card">
            <div style="flex: 1;">
              <div style="font-size: 0.75rem; color: var(--text-muted);">${label}</div>
              <div style="font-size: 1.05rem; font-weight: 700; color: #fff; font-family: var(--font-mono); margin-top: 2px;">
                ${count.toLocaleString("pt-PT")}
              </div>
            </div>
            <span class="badge" style="background: rgba(245,158,11,0.15); color: var(--neon-amber); font-size: 0.7rem; font-weight: 700;">+${count}</span>
          </div>
        `;
      })
      .join("");
  }

  function renderRecentActivityTable(recentLoot, recentCommands) {
    const tbody = elements.statsRecentTbody;
    if (!tbody) return;

    const combined = [];
    (recentLoot || []).forEach(l => {
      combined.push({
        type: "farm_loot",
        timestamp: l.timestamp,
        coords: `${l.target_x}|${l.target_y}`,
        details: `+${(l.total || 0).toLocaleString("pt-PT")} (🌲${l.wood} 🧱${l.stone} ⛏${l.iron})`,
        status: l.losses ? "losses" : "ok",
      });
    });

    (recentCommands || []).forEach(c => {
      const unitStr = Object.entries(c.units || {}).map(([u, q]) => `${q} ${u}`).join(", ");
      combined.push({
        type: c.command_type || "command",
        timestamp: c.timestamp,
        coords: c.target_coords || "---",
        details: unitStr || c.details || "Ataque enviado",
        status: c.success ? "ok" : "fail",
      });
    });

    combined.sort((a, b) => b.timestamp - a.timestamp);

    if (elements.statsRecentCountBadge) {
      elements.statsRecentCountBadge.textContent = `${combined.length} eventos`;
    }

    if (combined.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="padding: 12px; text-align: center; color: var(--text-muted);">Nenhum comando ou saque registado ainda.</td></tr>`;
      return;
    }

    tbody.innerHTML = combined.slice(0, 30).map(ev => {
      const dt = new Date(ev.timestamp * 1000);
      const timeStr = `${String(dt.getHours()).padStart(2, "0")}:${String(dt.getMinutes()).padStart(2, "0")}:${String(dt.getSeconds()).padStart(2, "0")}`;
      const typeBadge = ev.type === "farm_loot" 
        ? `<span class="badge" style="background: rgba(16,185,129,0.15); color: var(--neon-emerald); font-size: 0.7rem;">🌾 Saque</span>`
        : `<span class="badge" style="background: rgba(6,182,212,0.15); color: var(--neon-cyan); font-size: 0.7rem;">⚔️ Ataque</span>`;
      
      const statusBadge = ev.status === "ok"
        ? `<span class="stats-status-ok">Sucesso</span>`
        : `<span class="stats-status-fail">Perdas / Falha</span>`;

      return `
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.04);">
          <td style="padding: 6px 8px; font-family: var(--font-mono); color: var(--text-muted);">${timeStr}</td>
          <td style="padding: 6px 8px;">${typeBadge}</td>
          <td style="padding: 6px 8px; font-family: var(--font-mono); color: var(--neon-cyan);">${ev.coords}</td>
          <td style="padding: 6px 8px; font-size: 0.76rem; color: #e2e8f0;">${ev.details}</td>
          <td style="padding: 6px 8px;">${statusBadge}</td>
        </tr>
      `;
    }).join("");
  }

  // Listeners dos Botões de Estatísticas
  elements.btnRefreshStats?.addEventListener("click", loadAndRenderStats);

  elements.btnResetStats?.addEventListener("click", async () => {
    if (confirm("Tem a certeza de que deseja reiniciar todas as estatísticas e histórico deste mundo?")) {
      try {
        await window.api.resetStats();
        addLogEntry("INFO", "stats", "🗑️ Estatísticas reiniciadas com sucesso.");
        loadAndRenderStats();
      } catch (err) {
        alert(`Erro ao reiniciar estatísticas: ${err.message}`);
      }
    }
  });

  // Toggle de Intervalo (24h / 7d)
  function setStatsRange(range) {
    state.statsRange = range;
    if (elements.btnStatsRange24h) elements.btnStatsRange24h.className = range === "24" ? "btn btn-sm btn-stats-range active" : "btn btn-sm btn-stats-range";
    if (elements.btnStatsRange7d) elements.btnStatsRange7d.className = range === "168" ? "btn btn-sm btn-stats-range active" : "btn btn-sm btn-stats-range";
    if (state.statsHistoryData) renderStatsChart(state.statsHistoryData);
  }

  elements.btnStatsRange24h?.addEventListener("click", () => setStatsRange("24"));
  elements.btnStatsRange7d?.addEventListener("click", () => setStatsRange("168"));

  // Toggle de Métrica (Total / Madeira / Argila / Ferro)
  function setStatsMetric(metric) {
    state.statsMetric = metric;
    const metricBtns = [
      { el: elements.btnMetricTotal, m: "total" },
      { el: elements.btnMetricWood, m: "wood" },
      { el: elements.btnMetricStone, m: "stone" },
      { el: elements.btnMetricIron, m: "iron" },
    ];
    metricBtns.forEach(({ el, m }) => {
      if (el) el.className = m === metric ? "btn btn-sm btn-stats-metric active" : "btn btn-sm btn-stats-metric";
    });
    if (state.statsHistoryData) renderStatsChart(state.statsHistoryData);
  }

  elements.btnMetricTotal?.addEventListener("click", () => setStatsMetric("total"));
  elements.btnMetricWood?.addEventListener("click", () => setStatsMetric("wood"));
  elements.btnMetricStone?.addEventListener("click", () => setStatsMetric("stone"));
  elements.btnMetricIron?.addEventListener("click", () => setStatsMetric("iron"));

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

