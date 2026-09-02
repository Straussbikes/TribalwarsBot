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

    // Account Hub & Modais de Gestão de Contas
    accountHubView: document.getElementById("account-hub-view"),
    accountsGrid: document.getElementById("accounts-grid"),
    hubHeaderActions: document.getElementById("hub-header-actions"),
    btnHubAddAccount: document.getElementById("btn-hub-add-account"),
    btnSwitchAccount: document.getElementById("btn-switch-account"),
    accountModal: document.getElementById("account-modal"),
    btnCancelAccountModal: document.getElementById("btn-cancel-account-modal"),
    btnSaveAccountModal: document.getElementById("btn-save-account-modal"),
    inputAccId: document.getElementById("input-acc-id"),
    inputAccName: document.getElementById("input-acc-name"),
    inputAccWorldDomain: document.getElementById("input-acc-world-domain"),
    inputAccSid: document.getElementById("input-acc-sid"),
    inputAccVillageId: document.getElementById("input-acc-village-id"),
    inputAccProxy: document.getElementById("input-acc-proxy"),
    inputAccTemplate: document.getElementById("input-acc-template"),

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
    bldTemplateSelect: document.getElementById("bld-template-select"),
    btnManageBuildingTemplates: document.getElementById("btn-manage-building-templates"),
    buildingTemplateModal: document.getElementById("building-template-modal"),
    btnCloseBuildingTemplateModal: document.getElementById("btn-close-building-template-modal"),
    btnModalNewBldTemplate: document.getElementById("btn-modal-new-bld-template"),
    bldTemplatesListContainer: document.getElementById("bld-templates-list-container"),
    inputBldTemplateId: document.getElementById("input-bld-template-id"),
    inputBldTemplateName: document.getElementById("input-bld-template-name"),
    btnModalCloneBldTemplate: document.getElementById("btn-modal-clone-bld-template"),
    btnModalDeleteBldTemplate: document.getElementById("btn-modal-delete-bld-template"),
    bldTemplateStepsCount: document.getElementById("bld-template-steps-count"),
    selectAddBldType: document.getElementById("select-add-bld-type"),
    inputAddBldLevel: document.getElementById("input-add-bld-level"),
    btnAddBldStep: document.getElementById("btn-add-bld-step"),
    bldTemplateStepsTbody: document.getElementById("bld-template-steps-tbody"),
    btnCancelEditBldTemplate: document.getElementById("btn-cancel-edit-bld-template"),
    btnSaveEditBldTemplate: document.getElementById("btn-save-edit-bld-template"),
    bldTemplateSaveMsg: document.getElementById("bld-template-save-msg"),
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
    btnCloneRecModel: document.getElementById("btn-clone-rec-model"),

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
    btnMetricTotal: document.getElementById("btn-metric-total"),
    btnMetricWood: document.getElementById("btn-metric-wood"),
    btnMetricStone: document.getElementById("btn-metric-stone"),
    btnMetricIron: document.getElementById("btn-metric-iron"),

    // Account Hub & Modals (Single-Active Session)
    accountHubView: document.getElementById("account-hub-view"),
    mainWorkspace: document.querySelector(".main-workspace"),
    accountsGrid: document.getElementById("accounts-grid"),
    btnHubAddAccount: document.getElementById("btn-hub-add-account"),
    btnSwitchAccount: document.getElementById("btn-switch-account"),
    accountModal: document.getElementById("account-modal"),
    accountModalTitle: document.getElementById("account-modal-title"),
    formAccountModal: document.getElementById("form-account-modal"),
    inputAccId: document.getElementById("input-acc-id"),
    inputAccName: document.getElementById("input-acc-name"),
    inputAccWorldDomain: document.getElementById("input-acc-world-domain"),
    inputAccSid: document.getElementById("input-acc-sid"),
    inputAccVillageId: document.getElementById("input-acc-village-id"),
    inputAccProxy: document.getElementById("input-acc-proxy"),
    inputAccTemplate: document.getElementById("input-acc-template"),
    btnCancelAccountModal: document.getElementById("btn-cancel-account-modal"),
    btnSaveAccountModal: document.getElementById("btn-save-account-modal"),
    btnLogout: document.getElementById("btn-logout"),
    worldTabsContainer: document.getElementById("world-tabs-container"),
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
      } else if (targetId === "tab-troop-models") {
        loadRecruitmentData();
      } else if (targetId === "tab-recruitment") {
        loadRecruitmentData();
      } else if (targetId === "tab-building") {
        loadBuildingData();
      } else if (targetId === "tab-villages") {
        if (elements.btnSyncAllVillages) elements.btnSyncAllVillages.click();
      } else if (targetId === "tab-market") {
        loadMarketData();
      } else if (targetId === "tab-farm-assistant") {
        refreshFarmAssistantTab();
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
    const raw = data.category ? String(data.category).toLowerCase().trim() : "attack";
    const norm = raw.startsWith("def") ? "defense" : "attack";
    if (!state.villageCategories) state.villageCategories = {};
    state.villageCategories[data.village_id] = norm;
    if (state.village && state.village.id === parseInt(data.village_id, 10)) {
      state.village.category = norm;
      loadRecruitmentData();
    }
    const label = norm === "attack" ? "Ataque ⚔️ (Modelo Ataque Full)" : "Defesa 🛡️ (Modelo Defesa Full)";
    addLogEntry("INFO", "village", `Aldeia ${data.village_id} reclassificada como '${label}'.`);
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

  window.wsClient.on("RECRUITMENT_CYCLE_EXECUTED", (data) => {
    if (data && data.active_orders !== undefined) {
      renderRecruitmentData(data);
    } else {
      loadRecruitmentData();
    }
  });

  window.wsClient.on("RECRUITMENT_UPDATED", (data) => {
    if (data && data.active_orders !== undefined) {
      renderRecruitmentData(data);
    } else {
      loadRecruitmentData();
    }
  });

  // Som Sintetizado de Emergência para Alertas Anti-Bot (Web Audio API nativa)
  function playEmergencyCaptchaSound() {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.4);
      gain.gain.setValueAtTime(0.3, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.4);
    } catch (e) {
      console.debug("Áudio não disponível:", e);
    }
  }

  // Interceção de Alerta Anti-Bot (Captcha Triggered)
  window.wsClient.on("CAPTCHA_ALERT", (data) => {
    state.captchaActive = true;
    state.schedulerRunning = false;
    updateTopBar();
    playEmergencyCaptchaSound();

    const modal = document.getElementById("captcha-modal");
    const worldEl = document.getElementById("captcha-world-id");
    const timeEl = document.getElementById("captcha-detected-time");
    if (worldEl) worldEl.textContent = (data?.world || "PT117").toUpperCase();
    if (timeEl) timeEl.textContent = new Date().toLocaleTimeString("pt-PT");
    if (modal) modal.style.display = "flex";

    addLogEntry("ERROR", "security", "⚠️ ALERTA DE SEGURANÇA: Desafio Anti-Bot detetado! O motor foi pausado automaticamente.");
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

      // Seletor Multi-Aldeia no cabeçalho do Dashboard
      const vSelect = document.getElementById("village-selector");
      if (vSelect && data.account.villages && data.account.villages.length > 1) {
        vSelect.style.display = "inline-block";
        const currentVId = v.id || data.account.current_village_id;
        vSelect.innerHTML = data.account.villages
          .map(
            (vill) =>
              `<option value="${vill.id}" ${vill.id === currentVId ? "selected" : ""}>${vill.name} (${vill.coordinates || `${vill.x}|${vill.y}`})</option>`
          )
          .join("");
      } else if (vSelect) {
        vSelect.style.display = "none";
      }
    }


    // Recursos (Soma de Todas as Aldeias no Painel Geral)
    const r = data.total_resources || data.resources || (data.account && data.account.village && data.account.village.resources);
    if (data.account) state.account = data.account;
    if (data.account && data.account.village) state.village = data.account.village;
    if (r) state.resources = r;
    if (data.resource_balance) state.resource_balance = data.resource_balance;

    if (r) {
      const maxStorage = r.storage_max || 1000;
      const isMulti = Boolean(data.account?.villages && data.account.villages.length > 1);
      elements.storageCapacity.textContent = `${maxStorage.toLocaleString()}${isMulti ? ' (Total)' : ''}`;

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
      elements.resPopVal.textContent = `${r.pop.toLocaleString()} / ${maxPop.toLocaleString()} (${(r.free_pop || 0).toLocaleString()} livres)`;
      elements.resPopBar.style.width = `${popPct}%`;
    }

    // Tropas Disponíveis (Soma de Todas as Aldeias no Painel Geral)
    const troops = data.total_troops || data.troops || (data.account && data.account.village && data.account.village.troops) || {};
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
      if (!state.villageCategories) state.villageCategories = {};
      data.account.villages.forEach(v => {
        if (v.id) {
          const vCat = v.category ? String(v.category).toLowerCase().trim() : "attack";
          state.villageCategories[v.id] = vCat.startsWith("def") ? "defense" : "attack";
        }
      });
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

  // --- Funções de Gestão de Contas (Account Hub / Single Active Session) ---
  function showAccountHub() {
    if (elements.accountHubView) elements.accountHubView.style.display = "block";
    if (elements.mainWorkspace) elements.mainWorkspace.style.display = "none";
    loadAndRenderAccounts();
  }

  function showDashboard() {
    if (elements.accountHubView) elements.accountHubView.style.display = "none";
    if (elements.mainWorkspace) elements.mainWorkspace.style.display = "flex";
  }

  async function loadAndRenderAccounts() {
    try {
      const res = await window.api.getAccounts();
      const accounts = res?.accounts || [];
      const status = await window.api.getStatus();
      renderAccountsHub(accounts, status?.active_profile_id);
    } catch (e) {
      console.error("Erro ao carregar contas:", e);
    }
  }

  function renderAccountsHub(accounts, activeAccountId) {
    if (!elements.accountsGrid) return;

    if (!accounts || accounts.length === 0) {
      elements.accountsGrid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 48px; background: rgba(15,23,42,0.6); border-radius: 12px; border: 1px dashed var(--border-glass);">
          <div style="font-size: 2.5rem; margin-bottom: 12px;">🛡️</div>
          <h3 style="color: #fff; font-size: 1.1rem; margin-bottom: 8px;">Nenhuma conta configurada</h3>
          <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 16px;">Adicione o seu primeiro perfil de jogo para iniciar a automação.</p>
          <button class="btn btn-primary" id="btn-empty-add-account" style="background: var(--gradient-primary); padding: 8px 18px;">
            <span>➕</span> Criar Primeira Conta
          </button>
        </div>
      `;
      document.getElementById("btn-empty-add-account")?.addEventListener("click", openAddAccountModal);
      return;
    }

    elements.accountsGrid.innerHTML = accounts.map(acc => {
      const isActive = acc.id === activeAccountId || acc.is_active;
      const worldName = (acc.world || "PT117").toUpperCase();
      const lastUsedStr = acc.last_used ? new Date(acc.last_used).toLocaleString("pt-PT") : "Nunca";
      const hasSid = Boolean(acc.session_cookie || acc.sid);

      return `
        <div class="account-card ${isActive ? 'active' : ''}" style="background: rgba(15,23,42,0.85); border: 1px solid ${isActive ? 'var(--neon-purple)' : 'var(--border-glass)'}; border-radius: 12px; padding: 20px; box-shadow: ${isActive ? '0 8px 24px rgba(168,85,247,0.2)' : 'none'}; position: relative; display: flex; flex-direction: column; justify-content: space-between; transition: all 0.2s ease;">
          <div>
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
              <div style="display: flex; align-items: center; gap: 10px;">
                <div style="width: 40px; height: 40px; border-radius: 10px; background: ${isActive ? 'rgba(168,85,247,0.2)' : 'rgba(30,41,59,0.7)'}; border: 1px solid ${isActive ? 'var(--neon-purple)' : 'var(--border-glass)'}; display: flex; align-items: center; justify-content: center; font-size: 1.2rem;">
                  👤
                </div>
                <div>
                  <h4 style="color: #fff; font-size: 1.05rem; font-weight: 700; margin: 0;">${acc.name || 'Conta Tribal'}</h4>
                  <span style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-muted);">${acc.world_domain || `${acc.world}.${acc.domain}`}</span>
                </div>
              </div>
              <span style="font-size: 0.7rem; font-weight: 700; padding: 2px 8px; border-radius: 8px; ${isActive ? 'background: var(--neon-purple); color: #000;' : (hasSid ? 'background: rgba(34,197,94,0.15); color: var(--neon-emerald);' : 'background: rgba(239,68,68,0.15); color: var(--neon-crimson);')}">
                ${isActive ? 'ATIVO' : (hasSid ? 'PRONTA' : 'SEM SID')}
              </span>
            </div>

            <div style="display: flex; flex-direction: column; gap: 6px; font-size: 0.78rem; color: var(--text-muted); margin-bottom: 18px; padding: 10px; background: rgba(0,0,0,0.2); border-radius: 8px;">
              <div style="display: flex; justify-content: space-between;">
                <span>🌐 Mundo:</span>
                <span style="font-weight: 600; color: var(--neon-cyan);">${worldName}</span>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span>🏰 Aldeia Principal:</span>
                <span style="font-family: var(--font-mono); color: #e2e8f0;">${acc.village_id || 'Auto-detetada'}</span>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span>🔒 Proxy:</span>
                <span style="font-family: var(--font-mono); color: ${acc.proxy ? 'var(--neon-emerald)' : 'var(--text-muted)'};">${acc.proxy ? 'Ativo' : 'Nenhum'}</span>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span>⏳ Último Acesso:</span>
                <span style="color: #cbd5e1;">${lastUsedStr}</span>
              </div>
            </div>
          </div>

          <div style="display: flex; gap: 8px; align-items: center; border-top: 1px solid var(--border-subtle); padding-top: 14px;">
            <button class="btn btn-primary btn-activate-acc" data-id="${acc.id}" style="flex: 1; padding: 6px 12px; font-size: 0.82rem; font-weight: 700; ${isActive ? 'background: var(--neon-purple);' : 'background: var(--gradient-primary);'}">
              ${isActive ? '✅ Entrar no Dashboard' : '🚀 Entrar'}
            </button>
            <button class="btn btn-secondary btn-edit-acc" data-id="${acc.id}" title="Editar Definições da Conta" style="padding: 6px 10px; font-size: 0.82rem;">
              ✏️
            </button>
            <button class="btn btn-secondary btn-delete-acc" data-id="${acc.id}" title="Eliminar Conta" style="padding: 6px 10px; font-size: 0.82rem; color: var(--neon-crimson);">
              🗑️
            </button>
          </div>
        </div>
      `;
    }).join("");

    // Wire Card Events
    elements.accountsGrid.querySelectorAll(".btn-activate-acc").forEach(btn => {
      btn.addEventListener("click", async () => {
        const accId = btn.getAttribute("data-id");
        try {
          btn.disabled = true;
          btn.innerHTML = "<span>⏳</span> A carregar...";
          addLogEntry("INFO", "account", `A carregar perfil de conta ${accId}...`);
          const res = await window.api.activateAccount(accId);
          if (res && res.status === "success") {
            addLogEntry("SUCCESS", "account", res.message || "Conta ativada com sucesso.");
            showDashboard();
            const status = await window.api.getStatus();
            updateDashboard(status);
          } else {
            alert(res?.message || "Erro ao ativar conta.");
          }
        } catch (err) {
          alert(`Falha ao ativar conta: ${err.message}`);
        } finally {
          btn.disabled = false;
        }
      });
    });

    elements.accountsGrid.querySelectorAll(".btn-edit-acc").forEach(btn => {
      btn.addEventListener("click", async () => {
        const accId = btn.getAttribute("data-id");
        openEditAccountModal(accId);
      });
    });

    elements.accountsGrid.querySelectorAll(".btn-delete-acc").forEach(btn => {
      btn.addEventListener("click", async () => {
        const accId = btn.getAttribute("data-id");
        if (confirm("Tem a certeza de que deseja eliminar esta conta?")) {
          try {
            await window.api.deleteAccount(accId);
            addLogEntry("INFO", "account", "Conta eliminada com sucesso.");
            loadAndRenderAccounts();
          } catch (err) {
            alert(`Erro ao eliminar conta: ${err.message}`);
          }
        }
      });
    });
  }

  function openAddAccountModal() {
    if (!elements.accountModal) return;
    if (elements.accountModalTitle) elements.accountModalTitle.textContent = "Nova Conta de Jogo";
    if (elements.inputAccId) elements.inputAccId.value = "";
    if (elements.inputAccName) elements.inputAccName.value = "";
    if (elements.inputAccWorldDomain) elements.inputAccWorldDomain.value = "pt117";
    if (elements.inputAccSid) elements.inputAccSid.value = "";
    if (elements.inputAccVillageId) elements.inputAccVillageId.value = "";
    if (elements.inputAccProxy) elements.inputAccProxy.value = "";
    if (elements.inputAccTemplate) elements.inputAccTemplate.value = "default_plan";
    elements.accountModal.style.display = "flex";
  }

  async function openEditAccountModal(accId) {
    if (!elements.accountModal) return;
    try {
      const acc = await window.api.getAccount(accId);
      if (!acc) return;
      if (elements.accountModalTitle) elements.accountModalTitle.textContent = `Editar: ${acc.name}`;
      if (elements.inputAccId) elements.inputAccId.value = acc.id || accId;
      if (elements.inputAccName) elements.inputAccName.value = acc.name || "";
      if (elements.inputAccWorldDomain) elements.inputAccWorldDomain.value = acc.world_domain || acc.world || "pt117";
      if (elements.inputAccSid) elements.inputAccSid.value = acc.session_cookie || acc.sid || "";
      if (elements.inputAccVillageId) elements.inputAccVillageId.value = acc.village_id || "";
      if (elements.inputAccProxy) elements.inputAccProxy.value = acc.proxy || "";
      if (elements.inputAccTemplate) elements.inputAccTemplate.value = acc.build_order_strategy || acc.building_template || "default_plan";
      elements.accountModal.style.display = "flex";
    } catch (err) {
      alert(`Erro ao carregar detalhes da conta: ${err.message}`);
    }
  }

  // --- Funções de Renderização Multi-Mundo & Dropdown ---
  let cachedDiscoveredWorlds = [];

  async function refreshDiscoveredWorlds() {
    try {
      const res = await window.api.discoverWorlds();
      if (res && res.status === "success" && res.worlds) {
        cachedDiscoveredWorlds = res.worlds.map(w => w.toLowerCase());
        const status = await window.api.getStatus();
        if (status && status.worlds) {
          renderWorldDropdown(status.worlds, status.active_world);
          renderWorldTabs(status.worlds, status.active_world);
        }
      }
    } catch (e) {
      console.debug("Falha suave ao descobrir mundos:", e);
    }
  }

  function renderWorldDropdown(worlds, activeWorld) {
    if (!elements.worldDropdownList) return;
    const currentW = (activeWorld || "pt117").toLowerCase();

    // Apenas lista mundos onde o utilizador tem aldeia criada / conta ativa
    const registeredWorldKeys = (worlds || []).map(w => (w.world || "").toLowerCase()).filter(Boolean);
    const allWorldKeys = Array.from(new Set([currentW, ...registeredWorldKeys, ...cachedDiscoveredWorlds]));

    elements.worldDropdownList.innerHTML = allWorldKeys.map(w => {
      const isCurrent = w === currentW;
      return `
        <div class="dropdown-world-item ${isCurrent ? 'active' : ''}" data-world="${w}" style="padding: 8px 14px; cursor: pointer; display: flex; align-items: center; justify-content: space-between; font-size: 0.82rem; transition: background 0.15s ease; color: ${isCurrent ? 'var(--neon-cyan)' : 'var(--text-main)'}; font-weight: ${isCurrent ? '700' : '500'}; background: ${isCurrent ? 'rgba(6,182,212,0.15)' : 'transparent'}; border-left: ${isCurrent ? '3px solid var(--neon-cyan)' : '3px solid transparent'};">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span>🌐</span>
            <span>${w.toUpperCase()}</span>
          </div>
          ${isCurrent ? '<span style="font-size: 0.65rem; background: var(--neon-cyan); color: #000; padding: 1px 6px; border-radius: 10px; font-weight: 700;">ATIVO</span>' : '<span style="font-size: 0.68rem; color: var(--neon-emerald); font-weight: 600;">Aldeia Criada</span>'}
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
    const currentW = (activeWorld || "pt117").toLowerCase();
    const registeredWorldKeys = (worlds || []).map(w => (w.world || "").toLowerCase()).filter(Boolean);
    const combinedKeys = Array.from(new Set([currentW, ...registeredWorldKeys, ...cachedDiscoveredWorlds]));

    if (combinedKeys.length === 0) {
      elements.worldTabsContainer.innerHTML = `<span class="world-chip active">🌐 ${currentW.toUpperCase()}</span>`;
      return;
    }

    elements.worldTabsContainer.innerHTML = combinedKeys.map(w => {
      const isActive = w === currentW;
      const wObj = (worlds || []).find(item => (item.world || "").toLowerCase() === w);
      const vCount = wObj?.villages_count;
      return `
        <button class="world-chip ${isActive ? 'active' : ''}" data-world="${w}" title="Clique para focar no mundo ${w.toUpperCase()}">
          <span>🌐</span> ${w.toUpperCase()}
          ${vCount ? `<span style="font-size:0.68rem; opacity:0.8;">(${vCount}v)</span>` : ''}
        </button>
      `;
    }).join("");

    elements.worldTabsContainer.querySelectorAll(".world-chip").forEach(btn => {
      btn.addEventListener("click", async () => {
        const targetWorld = btn.getAttribute("data-world");
        if (targetWorld && targetWorld !== currentW) {
          try {
            btn.innerHTML = `<span>⏳</span> ${targetWorld.toUpperCase()}`;
            addLogEntry("INFO", "orchestrator", `A mudar para o mundo ${targetWorld.toUpperCase()}...`);
            const res = await window.api.switchWorld(targetWorld);
            if (res && res.status === "success") {
              addLogEntry("SUCCESS", "orchestrator", `Mundo alternado para ${targetWorld.toUpperCase()} com sucesso.`);
            } else if (res && res.message) {
              alert(res.message);
            }
            const status = await window.api.getStatus();
            updateDashboard(status);
          } catch (err) {
            console.error("Erro ao alternar mundo:", err);
            addLogEntry("ERROR", "orchestrator", `Falha ao mudar para o mundo ${targetWorld}: ${err.message}`);
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

    const validVillages = (villages || []).filter(v => v && v.id > 0 && !(v.x === 0 && v.y === 0 && (v.name || "").toLowerCase().includes("farm")));

    if (!validVillages || validVillages.length === 0) {
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
      elements.aggVillagesCount.textContent = validVillages.length.toString();
    }

    if (!state.villageCategories) state.villageCategories = {};

    elements.villagesTableBody.innerHTML = validVillages.map(v => {
      const isCurr = state.village && state.village.id === v.id;
      // Garante que a aldeia ativa reflete com exatidão os recursos mais recentes sincronizados
      const r = (isCurr && state.resources) ? state.resources : (v.resources || {});
      totWood += r.wood || 0;
      totStone += r.stone || 0;
      totIron += r.iron || 0;

      const maxStorage = r.storage_max || 1000;
      const storagePct = Math.min(100, Math.round(((r.wood + r.stone + r.iron) / (maxStorage * 3)) * 100));
      const rawCat = (state.villageCategories[v.id] || v.category || "attack").toLowerCase().trim();
      const cat = rawCat.startsWith("def") ? "defense" : "attack";

      const optionsHtml = `
        <option value="attack" ${cat === 'attack' ? 'selected' : ''}>⚔️ Ataque (Modelo Ataque Full)</option>
        <option value="defense" ${cat === 'defense' ? 'selected' : ''}>🛡️ Defesa (Modelo Defesa Full)</option>
      `;

      return `
        <tr style="border-bottom: 1px solid var(--border-subtle); transition: background 0.15s ease;" onmouseover="this.style.background='rgba(30,41,59,0.5)'" onmouseout="this.style.background='transparent'">
          <td style="padding: 10px 14px; font-weight: 600;">
            ${v.name || 'Aldeia'}
            ${isCurr ? '<span style="color: var(--neon-cyan); font-size: 0.75rem; margin-left: 6px; font-weight: 700;">(Ativa)</span>' : ''}
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
        const rawValue = sel.value.toLowerCase().trim();
        const newCat = rawValue.startsWith("def") ? "defense" : "attack";
        state.villageCategories[vid] = newCat;
        const catLabel = newCat === "attack" ? "Ataque ⚔️ (Modelo Ataque Full)" : "Defesa 🛡️ (Modelo Defesa Full)";
        try {
          console.log(`A alterar tipo da aldeia ${vid} para ${newCat}...`);
          sel.style.opacity = "0.6";
          await window.api.setVillageCategory(vid, newCat);
          sel.style.opacity = "1";
          sel.style.borderColor = "var(--neon-emerald)";
          setTimeout(() => { sel.style.borderColor = ""; }, 1500);
          addLogEntry("SUCCESS", "village", `Aldeia ${vid} configurada com modelo '${catLabel}'. Persistido no SQLite.`);
          if (state.village && state.village.id === parseInt(vid, 10)) {
            state.village.category = newCat;
            loadRecruitmentData();
          }
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

  // --- Gestão do Hub de Contas (Single-Active Session) & Acesso Restrito ---
  async function showAccountHub() {
    const hubView = document.getElementById("account-hub-view");
    const mainWorkspace = document.querySelector(".main-workspace");
    if (hubView) hubView.style.display = "block";
    if (mainWorkspace) mainWorkspace.style.display = "none";

    // Oculta controlos in-game na Topbar
    if (elements.btnLogout) elements.btnLogout.style.display = "none";
    if (elements.btnRefreshData) elements.btnRefreshData.style.display = "none";
    if (elements.btnClaimQuests) elements.btnClaimQuests.style.display = "none";
    if (elements.btnToggleScheduler) elements.btnToggleScheduler.style.display = "none";
    if (elements.btnFarmNow) elements.btnFarmNow.style.display = "none";
    if (elements.worldTabsContainer) elements.worldTabsContainer.style.display = "none";

    await loadAndRenderAccounts();
  }

  function hideAccountHub() {
    const hubView = document.getElementById("account-hub-view");
    const mainWorkspace = document.querySelector(".main-workspace");
    if (hubView) hubView.style.display = "none";
    if (mainWorkspace) mainWorkspace.style.display = "flex";

    // Mostra controlos in-game na Topbar
    if (elements.btnLogout) elements.btnLogout.style.display = "inline-flex";
    if (elements.btnRefreshData) elements.btnRefreshData.style.display = "inline-flex";
    if (elements.btnClaimQuests) elements.btnClaimQuests.style.display = "inline-flex";
    if (elements.btnToggleScheduler) elements.btnToggleScheduler.style.display = "inline-flex";
    if (elements.btnFarmNow) elements.btnFarmNow.style.display = "inline-flex";
    if (elements.worldTabsContainer) elements.worldTabsContainer.style.display = "inline-flex";
  }

  function openAddAccountModal() {
    if (!elements.accountModal) return;
    const titleEl = document.getElementById("account-modal-title");
    if (titleEl) titleEl.textContent = "Nova Conta de Jogo";
    if (elements.inputAccId) elements.inputAccId.value = "";
    if (elements.inputAccName) elements.inputAccName.value = "";
    if (elements.inputAccWorldDomain) elements.inputAccWorldDomain.value = state.account?.world || "pt117";
    if (elements.inputAccSid) elements.inputAccSid.value = "";
    if (elements.inputAccVillageId) elements.inputAccVillageId.value = "";
    if (elements.inputAccProxy) elements.inputAccProxy.value = "";
    if (elements.inputAccTemplate) elements.inputAccTemplate.value = "default_plan";
    elements.accountModal.style.display = "flex";
  }

  function openEditAccountModal(acc) {
    if (!elements.accountModal) return;
    const titleEl = document.getElementById("account-modal-title");
    if (titleEl) titleEl.textContent = `Editar Conta: ${acc.name}`;
    if (elements.inputAccId) elements.inputAccId.value = acc.id || "";
    if (elements.inputAccName) elements.inputAccName.value = acc.name || "";
    if (elements.inputAccWorldDomain) elements.inputAccWorldDomain.value = acc.world_domain || acc.world || "pt117";
    if (elements.inputAccSid) elements.inputAccSid.value = acc.session_cookie || acc.sid || "";
    if (elements.inputAccVillageId) elements.inputAccVillageId.value = acc.village_id || "";
    if (elements.inputAccProxy) elements.inputAccProxy.value = acc.proxy || "";
    if (elements.inputAccTemplate) elements.inputAccTemplate.value = acc.build_order_strategy || "default_plan";
    elements.accountModal.style.display = "flex";
  }

  async function loadAndRenderAccounts() {
    const grid = document.getElementById("accounts-grid");
    if (!grid) return;
    try {
      grid.innerHTML = `<div style="color: var(--text-muted); font-size: 0.85rem; padding: 20px;"><span>⏳</span> A carregar contas guardadas...</div>`;
      const res = await window.api.getAccounts();
      const accounts = res?.accounts || [];
      const activeId = res?.active_id || state.activeProfileId;

      if (!accounts.length) {
        // Oculta o botão superior de adicionar quando não há contas
        if (elements.hubHeaderActions) elements.hubHeaderActions.style.display = "none";
        if (elements.btnHubAddAccount) elements.btnHubAddAccount.style.display = "none";

        grid.innerHTML = `
          <div style="grid-column: 1 / -1; text-align: center; padding: 48px 24px; background: rgba(15,23,42,0.6); border: 1px dashed var(--border-glass); border-radius: 16px; max-width: 580px; margin: 20px auto; box-shadow: 0 10px 30px rgba(0,0,0,0.3);">
            <div style="font-size: 3rem; margin-bottom: 12px;">🛡️</div>
            <h3 style="color: #fff; font-family: var(--font-title); font-size: 1.25rem; margin-bottom: 8px; font-weight: 700;">Nenhuma Conta Configurada</h3>
            <p style="color: var(--text-muted); font-size: 0.88rem; line-height: 1.5; margin-bottom: 24px;">
              Faz login diretamente no Tribal Wars pelo navegador integrado para capturar a sessão automaticamente, ou adiciona os dados da tua conta manualmente.
            </p>
            <div style="display: flex; gap: 12px; justify-content: center; flex-wrap: wrap;">
              <button class="btn btn-primary" id="btn-hub-login-direct" style="background: var(--gradient-primary); padding: 10px 20px; font-size: 0.9rem; font-weight: 700; box-shadow: 0 4px 16px rgba(168,85,247,0.4); display: flex; align-items: center; gap: 8px;">
                <span>🔑</span> Fazer Login no Tribos
              </button>
              <button class="btn btn-secondary" id="btn-hub-create-manual" style="padding: 10px 18px; font-size: 0.88rem; font-weight: 600; display: flex; align-items: center; gap: 6px;">
                <span>⚙️</span> Adicionar Manualmente
              </button>
            </div>
          </div>
        `;
        const btnLoginDirect = document.getElementById("btn-hub-login-direct");
        if (btnLoginDirect) {
          btnLoginDirect.addEventListener("click", async () => {
            try {
              btnLoginDirect.disabled = true;
              btnLoginDirect.innerHTML = "<span>⏳</span> A abrir Tribal Wars...";
              addLogEntry("INFO", "account", "A abrir ecrã de autenticação do Tribal Wars...");
              await window.api.renewSession();
            } catch (err) {
              alert(`Erro ao abrir login: ${err.message}`);
            } finally {
              btnLoginDirect.disabled = false;
              btnLoginDirect.innerHTML = "<span>🔑</span> Fazer Login no Tribos";
            }
          });
        }
        const btnManual = document.getElementById("btn-hub-create-manual");
        if (btnManual) {
          btnManual.addEventListener("click", openAddAccountModal);
        }
        return;
      }

      // Mostra o botão superior de adicionar quando já existem contas
      if (elements.hubHeaderActions) elements.hubHeaderActions.style.display = "flex";
      if (elements.btnHubAddAccount) elements.btnHubAddAccount.style.display = "inline-flex";

      grid.innerHTML = accounts.map(acc => {
        const isActive = acc.id === activeId && Boolean(state.activeProfileId);
        const hasSid = Boolean(acc.session_cookie || acc.sid);
        const lastUsedStr = acc.last_used ? new Date(acc.last_used * 1000).toLocaleString("pt-PT") : "Nunca";
        return `
          <div class="account-card" style="background: rgba(30, 41, 59, 0.7); border: 1px solid ${isActive ? 'var(--neon-cyan)' : 'var(--border-glass)'}; border-radius: 12px; padding: 18px; position: relative; box-shadow: ${isActive ? '0 0 20px rgba(6,182,212,0.2)' : 'none'}; display: flex; flex-direction: column; justify-content: space-between; gap: 14px;">
            <div>
              <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                <div>
                  <h4 style="color: #fff; font-family: var(--font-title); font-size: 1.05rem; margin: 0; font-weight: 700;">${acc.name || 'Conta sem nome'}</h4>
                  <span style="font-size: 0.72rem; color: var(--neon-cyan); font-weight: 600; font-family: var(--font-mono);">🌐 ${(acc.world || acc.world_domain || 'PT117').toUpperCase()}</span>
                </div>
                ${isActive 
                  ? `<span style="background: rgba(16,185,129,0.2); color: var(--neon-emerald); border: 1px solid var(--neon-emerald); border-radius: 6px; padding: 2px 8px; font-size: 0.68rem; font-weight: 700;">🟢 ONLINE</span>`
                  : `<span style="background: rgba(100,116,139,0.2); color: #94a3b8; border: 1px solid rgba(148,163,184,0.3); border-radius: 6px; padding: 2px 8px; font-size: 0.68rem; font-weight: 600;">⚪ OFFLINE</span>`
                }
              </div>
              <div style="font-size: 0.75rem; color: var(--text-muted); display: flex; flex-direction: column; gap: 4px;">
                <div><strong>Sessão:</strong> ${hasSid ? '<span style="color:var(--neon-emerald)">🟢 Guardada</span>' : '<span style="color:var(--neon-amber)">🟡 Sem SID</span>'}</div>
                <div><strong>Aldeia:</strong> ${acc.village_id || 'Automática'}</div>
                <div><strong>Estratégia:</strong> ${acc.build_order_strategy || 'default_plan'}</div>
                <div><strong>Último Acesso:</strong> ${lastUsedStr}</div>
              </div>
            </div>
            <div style="display: flex; gap: 8px; flex-wrap: wrap; border-top: 1px solid var(--border-glass); padding-top: 12px;">
              <button class="btn btn-primary btn-sm btn-activate-acc" data-id="${acc.id}" style="flex: 1; min-width: 110px; background: var(--gradient-primary); font-weight: 600;">
                <span>▶</span> ${isActive ? 'Focar Painel' : 'Conectar'}
              </button>
              <button class="btn btn-secondary btn-sm btn-login-acc" data-id="${acc.id}" title="Abrir ecrã do jogo para autenticar" style="padding: 4px 8px;">
                <span>🔑</span> Login
              </button>
              <button class="btn btn-secondary btn-sm btn-edit-acc" data-id="${acc.id}" title="Editar Definições" style="padding: 4px 8px;">
                <span>✏️</span>
              </button>
              <button class="btn btn-danger btn-sm btn-del-acc" data-id="${acc.id}" title="Eliminar Conta" style="padding: 4px 8px;">
                <span>🗑️</span>
              </button>
            </div>
          </div>
        `;
      }).join("");

      // Event listeners dos botões dos cards de conta
      grid.querySelectorAll(".btn-activate-acc").forEach(btn => {
        btn.addEventListener("click", async () => {
          const accId = btn.getAttribute("data-id");
          try {
            btn.disabled = true;
            btn.innerHTML = "<span>⏳</span> A iniciar...";
            addLogEntry("INFO", "account", `A ativar perfil de conta ${accId}...`);
            const res = await window.api.activateAccount(accId);
            if (res && res.status === "success") {
              state.activeProfileId = accId;
              addLogEntry("SUCCESS", "account", `Conta ativada com sucesso: ${res.account?.name || accId}`);
              hideAccountHub();
              const status = await window.api.getStatus();
              updateDashboard(status);
            } else {
              alert(res?.message || "Falha ao ativar conta.");
            }
          } catch (err) {
            alert(`Erro ao ativar conta: ${err.message}`);
          } finally {
            btn.disabled = false;
            btn.innerHTML = "<span>▶</span> Conectar";
          }
        });
      });

      grid.querySelectorAll(".btn-login-acc").forEach(btn => {
        btn.addEventListener("click", async () => {
          const accId = btn.getAttribute("data-id");
          try {
            await window.api.activateAccount(accId);
            state.activeProfileId = accId;
            hideAccountHub();
            await window.api.renewSession();
          } catch (err) {
            alert(`Erro ao abrir login: ${err.message}`);
          }
        });
      });

      grid.querySelectorAll(".btn-edit-acc").forEach(btn => {
        btn.addEventListener("click", () => {
          const accId = btn.getAttribute("data-id");
          const acc = accounts.find(a => a.id === accId);
          if (acc) openEditAccountModal(acc);
        });
      });

      grid.querySelectorAll(".btn-del-acc").forEach(btn => {
        btn.addEventListener("click", async () => {
          const accId = btn.getAttribute("data-id");
          const acc = accounts.find(a => a.id === accId);
          if (confirm(`Tem a certeza que deseja eliminar a conta '${acc?.name || accId}'?`)) {
            try {
              btn.disabled = true;
              await window.api.deleteAccount(accId);
              if (state.activeProfileId === accId) {
                state.activeProfileId = null;
              }
              addLogEntry("INFO", "account", `Conta '${acc?.name || accId}' eliminada.`);
              await loadAndRenderAccounts();
            } catch (err) {
              alert(`Erro ao eliminar conta: ${err.message}`);
            }
          }
        });
      });
    } catch (e) {
      console.error("Erro ao carregar contas:", e);
      grid.innerHTML = `<div style="color: var(--neon-rose); font-size: 0.82rem; padding: 20px;">Falha ao carregar contas: ${e.message}</div>`;
    }
  }

  // Handlers do Botão Refresh da Aldeia Ativa
  if (elements.btnRefreshData) {
    elements.btnRefreshData.addEventListener("click", async () => {
      try {
        elements.btnRefreshData.disabled = true;
        addLogEntry("INFO", "orchestrator", "A atualizar dados da aldeia, recursos e tropas...");
        const res = await window.api.refreshVillage();
        if (res && res.status === "success" && res.data) {
          updateDashboard(res.data);
          addLogEntry("SUCCESS", "orchestrator", "Recursos e tropas da aldeia atualizados com sucesso.");
        } else {
          const status = await window.api.getStatus();
          updateDashboard(status);
          addLogEntry("SUCCESS", "orchestrator", "Estado do jogo atualizado.");
        }
      } catch (err) {
        console.error("Erro ao atualizar dados:", err);
        addLogEntry("ERROR", "orchestrator", `Falha ao atualizar dados: ${err.message}`);
      } finally {
        elements.btnRefreshData.disabled = false;
      }
    });
  }

  // Handlers do Account Hub, Modal & Logout
  if (elements.btnLogout) {
    elements.btnLogout.addEventListener("click", async () => {
      if (confirm("Deseja terminar a sessão atual da conta e regressar ao Gestor de Contas?")) {
        try {
          elements.btnLogout.disabled = true;
          await window.api.disconnectAccount();
          state.activeProfileId = null;
          showAccountHub();
        } catch (err) {
          console.error("Erro ao efetuar logout:", err);
          showAccountHub();
        } finally {
          elements.btnLogout.disabled = false;
        }
      }
    });
  }

  // Handlers do Modal de Captcha Anti-Bot
  const captchaModal = document.getElementById("captcha-modal");
  const btnOpenCaptcha = document.getElementById("btn-open-captcha-browser");
  const btnResumeCaptcha = document.getElementById("btn-resume-after-captcha");

  if (btnOpenCaptcha) {
    btnOpenCaptcha.addEventListener("click", async () => {
      try {
        await window.api.renewSession();
      } catch (err) {
        console.error("Erro ao abrir sessão para captcha:", err);
      }
    });
  }

  if (btnResumeCaptcha) {
    btnResumeCaptcha.addEventListener("click", async () => {
      try {
        btnResumeCaptcha.disabled = true;
        await window.api.resumeScheduler();
        if (captchaModal) captchaModal.style.display = "none";
        state.captchaActive = false;
        state.schedulerRunning = true;
        updateTopBar();
        addLogEntry("SUCCESS", "security", "Automação retomada com sucesso após resolução de captcha.");
        const status = await window.api.getStatus();
        updateDashboard(status);
      } catch (err) {
        alert(`Falha ao retomar: ${err.message}`);
      } finally {
        btnResumeCaptcha.disabled = false;
      }
    });
  }

  if (elements.btnSwitchAccount) {
    elements.btnSwitchAccount.addEventListener("click", () => {
      showAccountHub();
    });
  }

  if (elements.btnHubAddAccount) {
    elements.btnHubAddAccount.addEventListener("click", openAddAccountModal);
  }

  if (elements.btnCancelAccountModal && elements.accountModal) {
    elements.btnCancelAccountModal.addEventListener("click", () => {
      elements.accountModal.style.display = "none";
    });
  }

  if (elements.btnSaveAccountModal) {
    elements.btnSaveAccountModal.addEventListener("click", async () => {
      const accId = elements.inputAccId.value.trim();
      const name = elements.inputAccName.value.trim();
      const worldDomain = elements.inputAccWorldDomain.value.trim();
      const sid = elements.inputAccSid.value.trim();
      const villageIdStr = elements.inputAccVillageId.value.trim();
      const proxy = elements.inputAccProxy.value.trim() || null;
      const template = elements.inputAccTemplate.value;

      if (!name) {
        alert("Por favor indique um nome para a conta.");
        return;
      }
      if (!worldDomain) {
        alert("Por favor indique o mundo ou subdomínio (ex: pt117).");
        return;
      }

      const payload = {
        name,
        world_domain: worldDomain,
        session_cookie: sid,
        sid: sid,
        village_id: villageIdStr ? parseInt(villageIdStr, 10) : null,
        proxy,
        build_order_strategy: template,
      };

      try {
        elements.btnSaveAccountModal.disabled = true;
        elements.btnSaveAccountModal.innerHTML = "<span>⏳</span> A guardar...";
        if (accId) {
          await window.api.updateAccount(accId, payload);
          addLogEntry("SUCCESS", "account", `Conta '${name}' atualizada.`);
        } else {
          await window.api.createAccount(payload);
          addLogEntry("SUCCESS", "account", `Conta '${name}' criada.`);
        }
        elements.accountModal.style.display = "none";
        loadAndRenderAccounts();
      } catch (err) {
        alert(`Erro ao guardar conta: ${err.message}`);
      } finally {
        elements.btnSaveAccountModal.disabled = false;
        elements.btnSaveAccountModal.innerHTML = "Guardar Perfil";
      }
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

  // Seletor de Aldeia Ativa no Dashboard
  const vSelectElem = document.getElementById("village-selector");
  if (vSelectElem) {
    vSelectElem.addEventListener("change", async () => {
      const vid = parseInt(vSelectElem.value, 10);
      if (vid && (!state.village || state.village.id !== vid)) {
        try {
          addLogEntry("INFO", "village", `A alternar para a aldeia ${vid}...`);
          vSelectElem.disabled = true;
          await window.api.switchVillage(vid);
          const status = await window.api.getStatus();
          updateDashboard(status);
        } catch (err) {
          console.error("Erro ao alternar aldeia via seletor:", err);
          addLogEntry("ERROR", "village", `Falha ao alternar aldeia: ${err.message}`);
        } finally {
          vSelectElem.disabled = false;
        }
      }
    });
  }

  if (elements.btnSyncAllVillages) {
    elements.btnSyncAllVillages.addEventListener("click", async () => {
      try {
        console.log("A sincronizar todas as aldeias...");
        elements.btnSyncAllVillages.disabled = true;
        elements.btnSyncAllVillages.innerHTML = "<span>⏳</span> A sincronizar...";
        addLogEntry("INFO", "village", "A consultar todas as aldeias e recursos no servidor do jogo...");
        const res = await window.api.getAccountVillages();
        if (res && res.villages) {
          renderVillagesOverview(res.villages, res.balance);
          addLogEntry("SUCCESS", "village", `Sincronizadas ${res.villages.length} aldeias com sucesso!`);
        }
        const status = await window.api.getStatus();
        updateDashboard(status);
      } catch (err) {
        console.error("Erro ao sincronizar aldeias:", err);
        addLogEntry("ERROR", "village", `Falha ao sincronizar aldeias: ${err.message}`);
      } finally {
        elements.btnSyncAllVillages.disabled = false;
        elements.btnSyncAllVillages.innerHTML = "<span>🔄</span> Sincronizar Aldeias";
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
    if (elements.bldTemplateSelect && data.template) {
      elements.bldTemplateSelect.value = data.template;
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

  // --- Gestão de Templates de Construção no SQLite ---
  let cachedBuildingTemplates = [];
  let currentEditingTemplate = null;
  let currentEditingSteps = [];

  async function loadBuildingTemplatesList(selectedId = null) {
    try {
      const res = await window.api.getBuildingTemplates();
      if (res && res.templates) {
        cachedBuildingTemplates = res.templates;
        
        // Atualiza Dropdown da Aba de Edifícios
        if (elements.bldTemplateSelect) {
          const currentVal = selectedId || elements.bldTemplateSelect.value || "default_plan";
          elements.bldTemplateSelect.innerHTML = cachedBuildingTemplates.map(t => {
            const label = t.name + (t.is_default ? " (Padrão)" : "");
            return `<option value="${t.id}">${label}</option>`;
          }).join("");
          if (cachedBuildingTemplates.some(t => t.id === currentVal)) {
            elements.bldTemplateSelect.value = currentVal;
          }
        }

        // Atualiza Dropdown do Modal de Contas
        if (elements.inputAccTemplate) {
          elements.inputAccTemplate.innerHTML = cachedBuildingTemplates.map(t => {
            const label = t.name + (t.is_default ? " (Padrão)" : "");
            return `<option value="${t.id}">${label}</option>`;
          }).join("");
        }
      }
    } catch (err) {
      console.warn("Falha ao carregar templates de construção:", err);
    }
  }

  if (elements.bldTemplateSelect) {
    elements.bldTemplateSelect.addEventListener("change", async () => {
      const targetTmpl = elements.bldTemplateSelect.value;
      try {
        addLogEntry("INFO", "building", `A alterar estratégia de construção ativa para '${targetTmpl}'...`);
        await window.api.updateConfig({ building: { template: targetTmpl } });
        addLogEntry("SUCCESS", "building", `Estratégia de construção alterada para '${targetTmpl}'.`);
        await loadBuildingData();
      } catch (err) {
        addLogEntry("ERROR", "building", `Falha ao alternar template de construção: ${err.message}`);
      }
    });
  }

  // Abertura e Gestão do Modal de Templates de Construção
  if (elements.btnManageBuildingTemplates) {
    elements.btnManageBuildingTemplates.addEventListener("click", () => {
      openBuildingTemplateModal();
    });
  }

  if (elements.btnCloseBuildingTemplateModal) {
    elements.btnCloseBuildingTemplateModal.addEventListener("click", closeBuildingTemplateModal);
  }
  if (elements.btnCancelEditBldTemplate) {
    elements.btnCancelEditBldTemplate.addEventListener("click", closeBuildingTemplateModal);
  }

  function openBuildingTemplateModal() {
    if (!elements.buildingTemplateModal) return;
    elements.buildingTemplateModal.style.display = "flex";
    elements.buildingTemplateModal.classList.add("active");
    renderBuildingTemplatesModalList();
    const activeId = elements.bldTemplateSelect?.value || cachedBuildingTemplates[0]?.id;
    const found = cachedBuildingTemplates.find(t => t.id === activeId) || cachedBuildingTemplates[0];
    if (found) {
      selectTemplateForEditing(found);
    } else {
      createNewTemplateInEditor();
    }
  }

  function closeBuildingTemplateModal() {
    if (elements.buildingTemplateModal) {
      elements.buildingTemplateModal.style.display = "none";
      elements.buildingTemplateModal.classList.remove("active");
    }
    if (elements.bldTemplateSaveMsg) elements.bldTemplateSaveMsg.textContent = "";
  }

  function renderBuildingTemplatesModalList() {
    if (!elements.bldTemplatesListContainer) return;
    elements.bldTemplatesListContainer.innerHTML = cachedBuildingTemplates.map(t => {
      const isSelected = currentEditingTemplate && currentEditingTemplate.id === t.id;
      const badge = t.is_default 
        ? `<span style="font-size:0.65rem; background:rgba(6,182,212,0.2); color:var(--neon-cyan); padding:1px 5px; border-radius:4px;">Padrão</span>`
        : `<span style="font-size:0.65rem; background:rgba(245,158,11,0.2); color:var(--neon-amber); padding:1px 5px; border-radius:4px;">Custom</span>`;
      return `
        <div class="bld-tmpl-list-item ${isSelected ? 'active' : ''}" data-id="${t.id}" style="padding: 8px 10px; border-radius: 6px; cursor: pointer; background: ${isSelected ? 'rgba(6,182,212,0.15)' : 'rgba(15,23,42,0.5)'}; border: 1px solid ${isSelected ? 'var(--neon-cyan)' : 'var(--border-subtle)'}; display: flex; justify-content: space-between; align-items: center;">
          <div>
            <div style="font-size: 0.82rem; font-weight: 700; color: ${isSelected ? 'var(--neon-cyan)' : '#fff'};">${t.name}</div>
            <div style="font-size: 0.7rem; color: var(--text-muted);">${(t.priority_list || []).length} passos</div>
          </div>
          ${badge}
        </div>
      `;
    }).join("");

    elements.bldTemplatesListContainer.querySelectorAll(".bld-tmpl-list-item").forEach(el => {
      el.addEventListener("click", () => {
        const id = el.getAttribute("data-id");
        const tmpl = cachedBuildingTemplates.find(t => t.id === id);
        if (tmpl) selectTemplateForEditing(tmpl);
      });
    });
  }

  function selectTemplateForEditing(tmpl) {
    currentEditingTemplate = tmpl;
    currentEditingSteps = JSON.parse(JSON.stringify(tmpl.priority_list || []));
    if (elements.inputBldTemplateId) elements.inputBldTemplateId.value = tmpl.id;
    if (elements.inputBldTemplateName) elements.inputBldTemplateName.value = tmpl.name;
    if (elements.bldTemplateSaveMsg) elements.bldTemplateSaveMsg.textContent = "";

    if (elements.btnModalDeleteBldTemplate) {
      elements.btnModalDeleteBldTemplate.style.display = tmpl.is_default ? "none" : "inline-block";
    }

    renderBuildingTemplatesModalList();
    renderEditingStepsTable();
  }

  function createNewTemplateInEditor() {
    currentEditingTemplate = {
      id: null,
      name: "Novo Modelo Personalizado",
      priority_list: [],
      is_default: false,
    };
    currentEditingSteps = [];
    if (elements.inputBldTemplateId) elements.inputBldTemplateId.value = "";
    if (elements.inputBldTemplateName) elements.inputBldTemplateName.value = "Novo Modelo Personalizado";
    if (elements.btnModalDeleteBldTemplate) elements.btnModalDeleteBldTemplate.style.display = "none";
    if (elements.bldTemplateSaveMsg) elements.bldTemplateSaveMsg.textContent = "";

    renderBuildingTemplatesModalList();
    renderEditingStepsTable();
  }

  if (elements.btnModalNewBldTemplate) {
    elements.btnModalNewBldTemplate.addEventListener("click", createNewTemplateInEditor);
  }

  function renderEditingStepsTable() {
    if (elements.bldTemplateStepsCount) {
      elements.bldTemplateStepsCount.textContent = currentEditingSteps.length.toString();
    }
    if (!elements.bldTemplateStepsTbody) return;

    if (currentEditingSteps.length === 0) {
      elements.bldTemplateStepsTbody.innerHTML = `
        <tr>
          <td colspan="4" style="padding: 18px; text-align: center; color: var(--text-muted);">
            Nenhum passo definido. Use o formulário acima para adicionar passos de construção.
          </td>
        </tr>
      `;
      return;
    }

    elements.bldTemplateStepsTbody.innerHTML = currentEditingSteps.map((step, idx) => {
      const bldId = Array.isArray(step) ? step[0] : step.building;
      const lvl = Array.isArray(step) ? step[1] : step.level;
      const icon = BUILDING_ICONS[bldId] || "🏛️";
      const bName = BUILDING_PT_NAMES[bldId] || bldId;

      return `
        <tr style="border-bottom: 1px solid var(--border-subtle);">
          <td style="padding: 6px 10px; font-family: var(--font-mono); color: var(--text-muted);">${idx + 1}</td>
          <td style="padding: 6px 10px; font-weight: 600; color: #fff;">${icon} ${bName} <span style="font-size:0.7rem; color:var(--text-muted);">(${bldId})</span></td>
          <td style="padding: 6px 10px; font-family: var(--font-mono); color: var(--neon-cyan); font-weight: 700;">Nível ${lvl}</td>
          <td style="padding: 6px 10px; text-align: right;">
            <button type="button" class="btn btn-secondary btn-sm btn-step-up" data-idx="${idx}" style="padding: 1px 5px; font-size: 0.7rem;" title="Mover para cima" ${idx === 0 ? 'disabled' : ''}>▲</button>
            <button type="button" class="btn btn-secondary btn-sm btn-step-down" data-idx="${idx}" style="padding: 1px 5px; font-size: 0.7rem;" title="Mover para baixo" ${idx === currentEditingSteps.length - 1 ? 'disabled' : ''}>▼</button>
            <button type="button" class="btn btn-outline btn-sm btn-step-del" data-idx="${idx}" style="padding: 1px 5px; font-size: 0.7rem; color: #f87171; border-color: rgba(239,68,68,0.4);" title="Remover passo">✕</button>
          </td>
        </tr>
      `;
    }).join("");

    elements.bldTemplateStepsTbody.querySelectorAll(".btn-step-up").forEach(btn => {
      btn.addEventListener("click", () => {
        const i = parseInt(btn.getAttribute("data-idx"), 10);
        if (i > 0) {
          const temp = currentEditingSteps[i];
          currentEditingSteps[i] = currentEditingSteps[i - 1];
          currentEditingSteps[i - 1] = temp;
          renderEditingStepsTable();
        }
      });
    });

    elements.bldTemplateStepsTbody.querySelectorAll(".btn-step-down").forEach(btn => {
      btn.addEventListener("click", () => {
        const i = parseInt(btn.getAttribute("data-idx"), 10);
        if (i < currentEditingSteps.length - 1) {
          const temp = currentEditingSteps[i];
          currentEditingSteps[i] = currentEditingSteps[i + 1];
          currentEditingSteps[i + 1] = temp;
          renderEditingStepsTable();
        }
      });
    });

    elements.bldTemplateStepsTbody.querySelectorAll(".btn-step-del").forEach(btn => {
      btn.addEventListener("click", () => {
        const i = parseInt(btn.getAttribute("data-idx"), 10);
        currentEditingSteps.splice(i, 1);
        renderEditingStepsTable();
      });
    });
  }

  if (elements.btnAddBldStep) {
    elements.btnAddBldStep.addEventListener("click", () => {
      const bld = elements.selectAddBldType?.value || "wood";
      const lvl = parseInt(elements.inputAddBldLevel?.value, 10) || 1;
      currentEditingSteps.push([bld, lvl]);
      renderEditingStepsTable();
    });
  }

  if (elements.btnSaveEditBldTemplate) {
    elements.btnSaveEditBldTemplate.addEventListener("click", async () => {
      const name = elements.inputBldTemplateName?.value?.trim();
      if (!name) {
        alert("Por favor indique um nome para o modelo de construção.");
        return;
      }
      if (currentEditingSteps.length === 0) {
        alert("Adicione pelo menos um passo de evolução ao modelo.");
        return;
      }

      try {
        elements.btnSaveEditBldTemplate.disabled = true;
        elements.btnSaveEditBldTemplate.textContent = "A gravar no SQLite...";

        const templateId = elements.inputBldTemplateId?.value || null;
        const payload = {
          name,
          priority_list: currentEditingSteps,
          target_levels: {},
        };

        if (templateId) {
          await window.api.updateBuildingTemplate(templateId, payload);
          addLogEntry("SUCCESS", "building", `Modelo de construção '${name}' atualizado no SQLite.`);
        } else {
          const res = await window.api.createBuildingTemplate(payload);
          addLogEntry("SUCCESS", "building", `Novo modelo de construção '${name}' criado no SQLite.`);
        }

        if (elements.bldTemplateSaveMsg) {
          elements.bldTemplateSaveMsg.textContent = "✓ Guardado no SQLite com sucesso!";
        }

        await loadBuildingTemplatesList(templateId);
        renderBuildingTemplatesModalList();
      } catch (err) {
        alert(`Falha ao guardar modelo no SQLite: ${err.message}`);
      } finally {
        elements.btnSaveEditBldTemplate.disabled = false;
        elements.btnSaveEditBldTemplate.textContent = "💾 Guardar no SQLite";
      }
    });
  }

  if (elements.btnModalCloneBldTemplate) {
    elements.btnModalCloneBldTemplate.addEventListener("click", async () => {
      if (!currentEditingTemplate || !currentEditingTemplate.id) {
        alert("Selecione um modelo existente para clonar.");
        return;
      }
      const newName = prompt(`Introduza o nome da cópia de '${currentEditingTemplate.name}':`, `${currentEditingTemplate.name} (Cópia)`);
      if (!newName) return;

      try {
        const res = await window.api.cloneBuildingTemplate(currentEditingTemplate.id, newName);
        if (res && res.template) {
          addLogEntry("SUCCESS", "building", `Modelo '${newName}' clonado no SQLite com sucesso.`);
          await loadBuildingTemplatesList(res.template.id);
          selectTemplateForEditing(res.template);
        }
      } catch (err) {
        alert(`Falha ao clonar modelo: ${err.message}`);
      }
    });
  }

  if (elements.btnModalDeleteBldTemplate) {
    elements.btnModalDeleteBldTemplate.addEventListener("click", async () => {
      if (!currentEditingTemplate || !currentEditingTemplate.id) return;
      if (currentEditingTemplate.is_default) {
        alert("Não é possível eliminar modelos padrão do sistema.");
        return;
      }

      if (confirm(`Tem a certeza que deseja eliminar o modelo '${currentEditingTemplate.name}' do SQLite?`)) {
        try {
          await window.api.deleteBuildingTemplate(currentEditingTemplate.id);
          addLogEntry("SUCCESS", "building", `Modelo '${currentEditingTemplate.name}' removido do SQLite.`);
          await loadBuildingTemplatesList();
          createNewTemplateInEditor();
        } catch (err) {
          alert(`Falha ao eliminar modelo: ${err.message}`);
        }
      }
    });
  }

  // Carrega templates de construção na inicialização
  loadBuildingTemplatesList();

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

  function showToast(type, message, duration = 3500) {
    const logLevel = type === "error" ? "ERROR" : type === "success" ? "SUCCESS" : "INFO";
    addLogEntry(logLevel, "ui", message);

    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      container.style.cssText = "position: fixed; bottom: 24px; right: 24px; z-index: 9999; display: flex; flex-direction: column; gap: 8px; pointer-events: none; max-width: 380px;";
      document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    const bg = type === "error" ? "rgba(239, 68, 68, 0.95)" : type === "success" ? "rgba(16, 185, 129, 0.95)" : "rgba(30, 41, 59, 0.95)";
    const border = type === "error" ? "var(--neon-rose)" : type === "success" ? "var(--neon-emerald)" : "var(--neon-cyan)";
    const icon = type === "error" ? "❌" : type === "success" ? "✅" : "ℹ️";

    toast.style.cssText = `background: ${bg}; border: 1px solid ${border}; color: #fff; padding: 10px 16px; border-radius: 8px; font-size: 0.82rem; box-shadow: 0 8px 24px rgba(0,0,0,0.5); backdrop-filter: blur(8px); display: flex; align-items: center; gap: 8px; pointer-events: auto; transition: all 0.3s ease;`;
    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(10px)";
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }
  window.showToast = showToast;

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
  elements.btnClearLogs?.addEventListener("click", () => {
    state.logs = [];
    if (elements.terminalLogs) elements.terminalLogs.innerHTML = "";
  });

  elements.btnAutoScroll?.addEventListener("click", () => {
    state.autoScrollLogs = !state.autoScrollLogs;
    if (elements.btnAutoScroll) {
      elements.btnAutoScroll.textContent = state.autoScrollLogs ? "Scroll: Ativo" : "Scroll: Pausado";
      elements.btnAutoScroll.className = state.autoScrollLogs ? "btn btn-secondary" : "btn btn-warning";
    }
  });

  elements.selectLogFilter?.addEventListener("change", (e) => {
    state.logFilter = e.target.value;
    refreshTerminalView();
  });

  elements.inputSearchLogs?.addEventListener("input", (e) => {
    state.logSearch = e.target.value;
    refreshTerminalView();
  });

  function refreshTerminalView() {
    if (elements.terminalLogs) {
      elements.terminalLogs.innerHTML = "";
      state.logs.forEach(renderLogEntry);
    }
  }

  // --- 6. Ações Manuais e Botões da Barra Superior ---
  elements.btnToggleScheduler?.addEventListener("click", async () => {
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
      if (elements.btnRenewSession) {
        elements.btnRenewSession.disabled = false;
        elements.btnRenewSession.innerHTML = "<span>🔑</span> Entrar / Login";
      }
    }
  });

  elements.btnBuildNow?.addEventListener("click", async () => {
    try {
      addLogEntry("INFO", "app", "Disparo manual: A iniciar ciclo de construção...");
      const res = await window.api.triggerBuild();
      addLogEntry("SUCCESS", "app", res.message || "Ciclo de construção despachado!");
      refreshStatus();
    } catch (e) {
      alert(`Erro: ${e.message}`);
    }
  });

  elements.btnRecruitNow?.addEventListener("click", async () => {
    try {
      addLogEntry("INFO", "app", "Disparo manual: A iniciar ciclo de recrutamento...");
      const res = await window.api.triggerRecruit();
      addLogEntry("SUCCESS", "app", res.message || "Ciclo de recrutamento despachado!");
    } catch (e) {
      alert(`Erro: ${e.message}`);
    }
  });

  // Modal Captcha
  const handleResumeCaptcha = async () => {
    try {
      await window.api.resumeBotProtection();
      state.captchaActive = false;
      elements.captchaModal?.classList.remove("active");
      updateTopBar();
      addLogEntry("SUCCESS", "anti-bot", "Alerta anti-bot limpo pelo utilizador. Motor retomado.");
    } catch (e) {
      alert(`Erro ao retomar: ${e.message}`);
    }
  };

  elements.btnResolveCaptcha?.addEventListener("click", handleResumeCaptcha);
  document.getElementById("btn-resume-captcha")?.addEventListener("click", handleResumeCaptcha);

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
            <button class="btn btn-secondary" style="padding: 3px 10px; font-size: 0.75rem;" onclick="window.focusMapCoord(${b.x}, ${b.y})" title="Centrar mapa nesta aldeia">
              🎯 Ver
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
        document.getElementById("cfg-building-template").value = config.building.template || "default_plan";
        document.getElementById("cfg-max-queue").value = config.building.max_queue || 2;
        document.getElementById("cfg-build-interval").value = config.building.interval_seconds || 75;
      }
    } catch (e) {
      console.warn("Falha ao carregar configurações:", e);
    }
  }

  elements.btnSaveSettings?.addEventListener("click", async (e) => {
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
      };

      if (pwdVal) {
        payload.auth.password = pwdVal;
      }

      await window.api.updateConfig(payload);
      addLogEntry("SUCCESS", "settings", "Configurações gravadas com sucesso no SQLite para a conta ativa.");
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

  state.recruitmentBatchSizes = {
    attack: { spear: 10, sword: 10, axe: 10, archer: 5, spy: 5, light: 5, marcher: 5, heavy: 5, ram: 2, catapult: 2 },
    defense: { spear: 10, sword: 10, axe: 10, archer: 5, spy: 5, light: 5, marcher: 5, heavy: 5, ram: 2, catapult: 2 },
  };

  function renderActiveModelUnits() {
    const gridContainer = document.getElementById("grid-model-active-units");
    if (!gridContainer) return;

    const activeKey = state.activeRecModelTab || "attack";
    const activeModel = state.recruitmentModels[activeKey] || {};
    const activeBatch = (state.recruitmentBatchSizes && state.recruitmentBatchSizes[activeKey]) || {};

    gridContainer.innerHTML = REC_UNITS_METADATA.map(u => {
      const targetVal = activeModel[u.id] !== undefined ? activeModel[u.id] : 0;
      const batchVal = activeBatch[u.id] !== undefined ? activeBatch[u.id] : (u.id === "spear" || u.id === "sword" || u.id === "axe" ? 10 : (u.id === "light" ? 5 : 1));
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
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
            <div>
              <label style="font-size: 0.73rem; color: var(--text-muted); display: block; margin-bottom: 4px;">Alvo Total:</label>
              <input type="number" class="form-control model-rec-input" data-model="${activeKey}" data-unit="${u.id}" value="${targetVal}" min="0" style="width: 100%; font-family: var(--font-mono); font-size: 0.88rem; text-align: right; padding: 5px 8px; background: rgba(0,0,0,0.3); border: 1px solid var(--border-subtle); color: #fff; border-radius: 6px;">
            </div>
            <div>
              <label style="font-size: 0.73rem; color: var(--text-muted); display: block; margin-bottom: 4px;">Lote Treino:</label>
              <input type="number" class="form-control model-batch-input" data-model="${activeKey}" data-unit="${u.id}" value="${batchVal}" min="1" style="width: 100%; font-family: var(--font-mono); font-size: 0.88rem; text-align: right; padding: 5px 8px; background: rgba(0,0,0,0.3); border: 1px solid var(--border-subtle); color: var(--neon-cyan); border-radius: 6px;">
            </div>
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

    gridContainer.querySelectorAll(".model-batch-input").forEach(inp => {
      inp.addEventListener("input", (e) => {
        const model = e.target.dataset.model;
        const unit = e.target.dataset.unit;
        const count = parseInt(e.target.value, 10) || 1;
        if (!state.recruitmentBatchSizes) state.recruitmentBatchSizes = {};
        if (!state.recruitmentBatchSizes[model]) state.recruitmentBatchSizes[model] = {};
        state.recruitmentBatchSizes[model][unit] = count;
      });
    });

    updateModelTotalPopDisplay();
  }

  function switchRecModelTab(tabKey) {
    state.activeRecModelTab = tabKey || "attack";
    const banner = document.getElementById("rec-model-info-banner");
    const btnDelete = document.getElementById("btn-delete-active-model");

    if (banner) {
      if (tabKey === "attack") {
        banner.style.background = "rgba(239, 68, 68, 0.08)";
        banner.style.borderLeftColor = "#ef4444";
        banner.style.color = "#fca5a5";
        banner.innerHTML = `<strong>⚔️ Modelo de Aldeia de Ataque (Full):</strong> Foco em poder de destruição (Viking/Bárbaro, Cavalaria Leve, Aríetes). Estas metas serão seguidas em todas as aldeias marcadas como <em>Ataque</em> na página de Multi-Aldeias.`;
      } else if (tabKey === "defense") {
        banner.style.background = "rgba(59, 130, 246, 0.08)";
        banner.style.borderLeftColor = "#3b82f6";
        banner.style.color = "#93c5fd";
        banner.innerHTML = `<strong>🛡️ Modelo de Aldeia de Defesa (Full):</strong> Foco em sustentação e apoio rápido (Lanceiros, Espadachins, Cavalaria Pesada). Estas metas serão seguidas em todas as aldeias marcadas como <em>Defesa</em> na página de Multi-Aldeias.`;
      } else {
        const cap = tabKey.charAt(0).toUpperCase() + tabKey.slice(1);
        banner.style.background = "rgba(245, 158, 11, 0.08)";
        banner.style.borderLeftColor = "#f59e0b";
        banner.style.color = "#fde68a";
        banner.innerHTML = `<strong>✨ Modelo Customizado '${cap}':</strong> Modelo personalizado salvo no SQLite para atribuição direta em aldeias no Mundo ativo.`;
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
  document.getElementById("btn-add-custom-model")?.addEventListener("click", async () => {
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

    // Cria novo modelo no SQLite
    const newUnits = {};
    const newBatches = {};
    REC_UNITS_METADATA.forEach(u => {
      newUnits[u.id] = 0;
      newBatches[u.id] = u.id === "spear" || u.id === "sword" || u.id === "axe" ? 10 : (u.id === "light" ? 5 : 1);
    });

    try {
      await window.api.createRecruitmentTemplate({
        id: name,
        name: rawName,
        units: newUnits,
        batch_sizes: newBatches,
      });

      state.recruitmentModels[name] = newUnits;
      if (!state.recruitmentBatchSizes) state.recruitmentBatchSizes = {};
      state.recruitmentBatchSizes[name] = newBatches;

      switchRecModelTab(name);
      addLogEntry("SUCCESS", "recruitment", `Novo modelo de tropas '${rawName}' criado e guardado no SQLite. Ajuste as quantidades e guarde.`);
    } catch (err) {
      alert(`Falha ao criar modelo no SQLite: ${err.message}`);
    }
  });

  // Botão: Clonar Modelo Ativo
  document.getElementById("btn-clone-rec-model")?.addEventListener("click", async () => {
    const activeKey = state.activeRecModelTab || "attack";
    const rawName = prompt(`Introduza o nome da cópia do modelo '${activeKey}':`, `${activeKey}_copia`);
    if (!rawName) return;
    const name = rawName.toLowerCase().replace(/[^a-z0-9_]/g, "_").trim();
    if (!name) {
      alert("Nome inválido!");
      return;
    }

    try {
      const res = await window.api.cloneRecruitmentTemplate(activeKey, rawName);
      if (res && res.model) {
        addLogEntry("SUCCESS", "recruitment", `Modelo de recrutamento '${rawName}' clonado no SQLite com sucesso.`);
        await loadRecruitmentData();
        switchRecModelTab(res.model.id || name);
      }
    } catch (err) {
      alert(`Falha ao clonar modelo no SQLite: ${err.message}`);
    }
  });

  // Botão: Eliminar Modelo Ativo
  document.getElementById("btn-delete-active-model")?.addEventListener("click", async () => {
    const targetModel = state.activeRecModelTab;
    if (targetModel === "attack" || targetModel === "defense") {
      alert("Não é possível eliminar os modelos padrão Ataque e Defesa.");
      return;
    }

    if (!confirm(`Tem a certeza que deseja eliminar o modelo '${targetModel}' do SQLite?`)) return;

    try {
      await window.api.deleteRecruitmentTemplate(targetModel);
      delete state.recruitmentModels[targetModel];
      if (state.recruitmentBatchSizes) delete state.recruitmentBatchSizes[targetModel];
      addLogEntry("SUCCESS", "recruitment", `Modelo '${targetModel}' removido do SQLite com sucesso.`);
      await loadRecruitmentData();
      switchRecModelTab("attack");
      
      // Atualiza dropdown de categorias no multi-aldeia
      if (state.account?.villages) {
        renderVillagesOverview(state.account.villages, state.resource_balance);
      }
    } catch (err) {
      alert(`Falha ao eliminar modelo do SQLite: ${err.message}`);
    }
  });

  async function loadRecruitmentIntoForm() {
    await loadRecruitmentData();
  }

  async function loadRecruitmentData(villageId = null) {
    try {
      const vId = villageId || (state.village && state.village.id);
      
      // Carrega modelos de tropas do SQLite
      try {
        const resTemplates = await window.api.getRecruitmentTemplates();
        if (resTemplates && resTemplates.models && Array.isArray(resTemplates.models)) {
          if (!state.recruitmentBatchSizes) state.recruitmentBatchSizes = {};
          resTemplates.models.forEach(m => {
            if (m && m.id) {
              state.recruitmentModels[m.id] = m.units || {};
              state.recruitmentBatchSizes[m.id] = m.batch_sizes || {};
            }
          });
        }
      } catch (errTmpl) {
        console.warn("Aviso ao carregar modelos de recrutamento do SQLite:", errTmpl);
      }

      // Garante renderização consistente da aba ativa
      if (!state.recruitmentModels[state.activeRecModelTab]) {
        state.activeRecModelTab = "attack";
      }
      switchRecModelTab(state.activeRecModelTab);

      // Carrega estado de recrutamento e filas ativas da aldeia
      if (vId) {
        const res = await window.api.getRecruitmentState(vId);
        if (res && res.status === "success") {
          renderRecruitmentData(res);
        }
      }
    } catch (e) {
      console.warn("Falha ao carregar dados de recrutamento:", e);
    }
  }

  function renderRecruitmentData(data) {
    if (!data) return;

    // 1. Modelos de Tropas se vierem no estado
    if (data.models && typeof data.models === "object") {
      Object.entries(data.models).forEach(([mKey, mUnits]) => {
        if (mUnits && typeof mUnits === "object") {
          state.recruitmentModels[mKey] = { ...(state.recruitmentModels[mKey] || {}), ...mUnits };
        }
      });
      renderModelTabs();
      renderActiveModelUnits();
    }

    // 2. Filas Ativas de Recrutamento em Andamento (Quartel, Estábulo, Oficina)
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
          const uIcon = uMeta ? uMeta.icon : "🪖";
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

    // 3. Comparativo de Tropas Presentes vs Meta do Modelo Selecionado para a Aldeia
    const vId = (state.village && state.village.id) || null;
    const vCat = (vId && state.villageCategories && state.villageCategories[vId]) || (state.village && state.village.category) || "attack";
    const vModelKey = (typeof vCat === "string" && vCat.toLowerCase().startsWith("def")) ? "defense" : "attack";
    const activeTargetModel = (state.recruitmentModels && state.recruitmentModels[vModelKey]) || (state.recruitmentModels && state.recruitmentModels["attack"]) || {};

    const modelNameBadge = document.getElementById("rec-active-village-model-name");
    if (modelNameBadge) {
      const displayLabel = vModelKey === "attack" ? "Modelo: ⚔️ Ataque Full" : "Modelo: 🛡️ Defesa Full";
      modelNameBadge.textContent = displayLabel;
    }

    const progressGrid = document.getElementById("rec-village-troops-progress-grid");
    if (progressGrid) {
      if (data.troops_home && typeof data.troops_home === "object") {
        state.army = { ...(state.army || {}), ...data.troops_home };
      }
      progressGrid.innerHTML = REC_UNITS_METADATA.map(u => {
        const cur = (data.troops_home && data.troops_home[u.id] !== undefined)
          ? data.troops_home[u.id]
          : ((state.army && state.army[u.id]) || 0);
        const tgt = activeTargetModel[u.id] || 0;
        const pct = tgt > 0 ? Math.min(100, Math.round((cur / tgt) * 100)) : (cur > 0 ? 100 : 0);
        const isDone = tgt > 0 ? cur >= tgt : (tgt === 0);
        const barColor = isDone ? "var(--neon-emerald)" : "var(--neon-cyan)";
        return `
          <div style="background: rgba(15,23,42,0.6); border: 1px solid var(--border-subtle); border-radius: 8px; padding: 10px 12px; display: flex; flex-direction: column; gap: 6px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <div style="display: flex; align-items: center; gap: 6px;">
                <span style="font-size: 1.1rem;">${u.icon}</span>
                <span style="font-size: 0.82rem; font-weight: 600; color: #fff;">${u.name}</span>
              </div>
              <span style="font-size: 0.75rem; font-family: var(--font-mono); font-weight: 700; color: ${isDone ? '#34d399' : '#fff'};">
                ${cur.toLocaleString()} / ${tgt.toLocaleString()}
              </span>
            </div>
            <div style="height: 6px; background: rgba(255,255,255,0.08); border-radius: 3px; overflow: hidden;">
              <div style="width: ${pct}%; height: 100%; background: ${barColor}; transition: width 0.3s ease;"></div>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.7rem; color: var(--text-muted);">
              <span>${pct}% atingido</span>
              <span>${isDone && tgt > 0 ? '✓ Completo' : (tgt > 0 ? `Falta ${Math.max(0, tgt - cur)}` : 'Sem meta')}</span>
            </div>
          </div>
        `;
      }).join("");
    }
  }

  async function saveRecruitmentModelsHandler() {
    const btnTop = document.getElementById("btn-save-troop-models");
    const btnBottom = document.getElementById("btn-save-troop-models-bottom");
    if (btnTop) { btnTop.disabled = true; btnTop.textContent = "A gravar no SQLite..."; }
    if (btnBottom) { btnBottom.disabled = true; btnBottom.textContent = "A gravar no SQLite..."; }
    state._isSavingRecruitment = true;

    try {
      // Coleta valores do modelo atualmente visível
      const activeKey = state.activeRecModelTab || "attack";
      if (!state.recruitmentModels[activeKey]) state.recruitmentModels[activeKey] = {};
      if (!state.recruitmentBatchSizes) state.recruitmentBatchSizes = {};
      if (!state.recruitmentBatchSizes[activeKey]) state.recruitmentBatchSizes[activeKey] = {};
      
      document.querySelectorAll(".model-rec-input").forEach(inp => {
        const model = inp.dataset.model;
        const unit = inp.dataset.unit;
        const count = parseInt(inp.value, 10) || 0;
        if (!state.recruitmentModels[model]) state.recruitmentModels[model] = {};
        state.recruitmentModels[model][unit] = count;
      });

      document.querySelectorAll(".model-batch-input").forEach(inp => {
        const model = inp.dataset.model;
        const unit = inp.dataset.unit;
        const count = parseInt(inp.value, 10) || 1;
        if (!state.recruitmentBatchSizes[model]) state.recruitmentBatchSizes[model] = {};
        state.recruitmentBatchSizes[model][unit] = count;
      });

      // Grava diretamente no SQLite para cada modelo
      for (const [mId, uTargets] of Object.entries(state.recruitmentModels)) {
        const bSizes = state.recruitmentBatchSizes[mId] || {};
        const isDef = mId === "attack" || mId === "defense";
        const mName = mId === "attack" ? "Ataque Full" : (mId === "defense" ? "Defesa Full" : (mId.charAt(0).toUpperCase() + mId.slice(1)));
        await window.api.updateRecruitmentTemplate(mId, {
          name: mName,
          units: uTargets,
          batch_sizes: bSizes,
          is_default: isDef,
        });
      }

      await window.api.saveRecruitmentModels(null, null, state.recruitmentModels);
      addLogEntry("SUCCESS", "recruitment", "Todos os modelos de tropas e lotes foram salvos e persistidos no SQLite (`data/accounts.db`).");
      alert("Modelos de tropas guardados e persistidos no SQLite com sucesso!");
      
      // Atualiza lista de modelos na interface e nos dropdowns de multi-aldeia
      switchRecModelTab(state.activeRecModelTab);
      if (state.account?.villages) {
        renderVillagesOverview(state.account.villages, state.resource_balance);
      }
      loadRecruitmentData();
    } catch (err) {
      addLogEntry("ERROR", "recruitment", `Erro ao guardar modelos: ${err.message}`);
      alert(`Falha ao guardar modelos no SQLite: ${err.message}`);
    } finally {
      state._isSavingRecruitment = false;
      if (btnTop) { btnTop.disabled = false; btnTop.innerHTML = "<span>💾</span> Guardar Alterações na BD"; }
      if (btnBottom) { btnBottom.disabled = false; btnBottom.innerHTML = "<span>💾</span> Guardar Alterações na BD"; }
    }
  }

  // Listeners de Gravação de Modelos de Tropas
  document.getElementById("btn-save-troop-models")?.addEventListener("click", saveRecruitmentModelsHandler);
  document.getElementById("btn-save-troop-models-bottom")?.addEventListener("click", saveRecruitmentModelsHandler);

  // Botão Atualizar Modelos de Tropas
  document.getElementById("btn-refresh-troop-models-tab")?.addEventListener("click", async () => {
    const btn = document.getElementById("btn-refresh-troop-models-tab");
    try {
      if (btn) { btn.disabled = true; btn.innerHTML = "<span>⏳</span> A ler..."; }
      addLogEntry("INFO", "recruitment", "A recarregar modelos de tropas do SQLite...");
      await loadRecruitmentData();
      addLogEntry("SUCCESS", "recruitment", "Modelos de tropas sincronizados do SQLite com sucesso!");
    } catch (err) {
      addLogEntry("WARNING", "recruitment", `Falha ao sincronizar modelos: ${err.message}`);
    } finally {
      if (btn) { btn.disabled = false; btn.innerHTML = "<span>🔄</span> Atualizar Modelos"; }
    }
  });

  // Listeners da Aba de Recrutamento Ativo
  document.getElementById("btn-refresh-recruitment-queue")?.addEventListener("click", async () => {
    const btn = document.getElementById("btn-refresh-recruitment-queue");
    try {
      if (btn) { btn.disabled = true; btn.innerHTML = "<span>⏳</span> A ler..."; }
      addLogEntry("INFO", "recruitment", "A ler filas de produção militar da aldeia ativa...");
      await window.api.refreshVillage();
      await loadRecruitmentData();
      addLogEntry("SUCCESS", "recruitment", "Filas militares e tropas atualizadas!");
    } catch (err) {
      addLogEntry("WARNING", "recruitment", `Falha ao atualizar filas militares: ${err.message}`);
    } finally {
      if (btn) { btn.disabled = false; btn.innerHTML = "<span>🔄</span> Atualizar"; }
    }
  });

  document.getElementById("btn-trigger-recruit-now")?.addEventListener("click", async () => {
    const btn = document.getElementById("btn-trigger-recruit-now");
    try {
      if (btn) { btn.disabled = true; btn.innerHTML = "<span>⏳</span> A recrutar..."; }
      addLogEntry("INFO", "recruitment", "Disparo manual: A iniciar ciclo de recrutamento para a aldeia ativa...");
      const res = await window.api.triggerRecruit();
      addLogEntry("SUCCESS", "recruitment", res.message || "Ciclo de recrutamento despachado com sucesso!");
      await loadRecruitmentData();
    } catch (err) {
      addLogEntry("ERROR", "recruitment", `Erro ao recrutar: ${err.message}`);
      alert(`Falha ao disparar recrutamento: ${err.message}`);
    } finally {
      if (btn) { btn.disabled = false; btn.innerHTML = "<span>⚔️</span> Recrutar Agora"; }
    }
  });

  // Toggle e configurações de Auto-Recrutamento
  const recAutoToggle = document.getElementById("rec-auto-toggle");
  const recBadgeStatus = document.getElementById("rec-badge-status");
  const recIntervalInput = document.getElementById("rec-interval-minutes");
  const recMinPopInput = document.getElementById("rec-min-free-pop");

  async function syncRecruitmentSettings() {
    if (!recAutoToggle) return;
    const isEn = recAutoToggle.checked;
    if (recBadgeStatus) {
      recBadgeStatus.textContent = isEn ? "ATIVO" : "PAUSADO";
      recBadgeStatus.style.background = isEn ? "rgba(16,185,129,0.2)" : "rgba(245,158,11,0.2)";
      recBadgeStatus.style.color = isEn ? "var(--neon-emerald)" : "var(--neon-amber)";
    }
    const intervalMin = recIntervalInput ? parseFloat(recIntervalInput.value) : 1.5;
    const minPop = recMinPopInput ? parseInt(recMinPopInput.value, 10) : 5;
    try {
      await window.api.toggleRecruitment(isEn, intervalMin, minPop);
      addLogEntry("INFO", "recruitment", `Configuração de auto-recrutamento atualizada: ${isEn ? 'Ativo' : 'Pausado'} (${intervalMin} min, pop min: ${minPop}).`);
    } catch (err) {
      console.warn("Falha ao sincronizar toggle de recrutamento:", err);
    }
  }

  recAutoToggle?.addEventListener("change", syncRecruitmentSettings);
  recIntervalInput?.addEventListener("change", syncRecruitmentSettings);
  recMinPopInput?.addEventListener("change", syncRecruitmentSettings);

  // Listeners de WebSocket para templates em tempo real
  if (window.wsClient) {
    window.wsClient.on("building_templates_updated", () => {
      addLogEntry("INFO", "building", "Notificação WebSocket: Modelos de construção atualizados no SQLite.");
      loadBuildingTemplatesList();
      if (elements.buildingTemplateModal && elements.buildingTemplateModal.style.display !== "none") {
        renderBuildingTemplatesModalList();
      }
    });

    window.wsClient.on("recruitment_models_updated", () => {
      if (state._isSavingRecruitment) return;
      addLogEntry("INFO", "recruitment", "Notificação WebSocket: Modelos de recrutamento atualizados no SQLite.");
      loadRecruitmentData();
    });
  }

  // Inicialização imediata dos modelos de tropas para que nunca fiquem vazios
  switchRecModelTab("attack");
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

  // =========================================================================
  // --- MÓDULO 4: ASSISTENTE DE SAQUE & FARM + RADAR DE INATIVOS (Fase 4) ---
  // =========================================================================

  let activeFarmSubtab = "am-farm";

  function switchFarmSubtab(subtab) {
    activeFarmSubtab = subtab;
    const btnAm = document.getElementById("btn-subtab-am-farm");
    const btnRadar = document.getElementById("btn-subtab-radar-inactives");
    const viewAm = document.getElementById("subtab-view-am-farm");
    const viewRadar = document.getElementById("subtab-view-radar-inactives");

    if (btnAm) btnAm.className = subtab === "am-farm" ? "farm-subtab-btn active" : "farm-subtab-btn";
    if (btnRadar) btnRadar.className = subtab === "radar-inactives" ? "farm-subtab-btn active" : "farm-subtab-btn";
    if (viewAm) viewAm.style.display = subtab === "am-farm" ? "flex" : "none";
    if (viewRadar) viewRadar.style.display = subtab === "radar-inactives" ? "flex" : "none";

    if (subtab === "am-farm") {
      loadAmFarmView();
    } else {
      loadRadarInactivesView();
    }
  }
  window.switchFarmSubtab = switchFarmSubtab;

  async function refreshFarmAssistantTab() {
    if (activeFarmSubtab === "am-farm") {
      await loadAmFarmView();
    } else {
      await loadRadarInactivesView();
    }
  }

  async function loadAmFarmView() {
    try {
      const statusRes = await window.api.getFarmStatus();
      if (statusRes && statusRes.status === "success") {
        // Toggle Master
        const toggleMaster = document.getElementById("toggle-farm-master");
        if (toggleMaster) toggleMaster.checked = !!statusRes.enabled;

        // Village Badge
        const vCoordsBadge = document.getElementById("farm-village-coords-badge");
        if (vCoordsBadge) vCoordsBadge.textContent = `(${statusRes.village_coords || "0|0"})`;

        // Available Troops Grid
        const troopsGrid = document.getElementById("farm-available-troops-grid");
        if (troopsGrid) {
          const troops = statusRes.available_troops || {};
          const unitIcons = {
            spear: "🗡️ Lanceiros",
            sword: "🛡️ Espadachins",
            axe: "🪓 Vikings",
            spy: "👁️ Espiões",
            light: "🐎 Cavalaria Leve",
            heavy: "🛡️ Cav. Pesada",
          };
          let html = "";
          for (const [u, label] of Object.entries(unitIcons)) {
            const count = troops[u] || 0;
            const highlight = count > 0 ? "color: var(--neon-cyan); font-weight: 700;" : "color: var(--text-muted);";
            html += `<div style="background: rgba(30, 41, 59, 0.5); padding: 4px 8px; border-radius: 6px; border: 1px solid var(--border-subtle);">
              ${label}: <span style="${highlight}">${count}</span>
            </div>`;
          }
          troopsGrid.innerHTML = html;
        }

        // Config Inputs
        const defTemp = document.getElementById("farm-cfg-default-template");
        if (defTemp) defTemp.value = statusRes.default_template || "A";
        const maxDist = document.getElementById("farm-cfg-max-distance");
        if (maxDist) maxDist.value = statusRes.max_distance || 25;
        const minInt = document.getElementById("farm-cfg-min-interval");
        if (minInt) minInt.value = statusRes.min_interval_seconds || 45;
        const maxInt = document.getElementById("farm-cfg-max-interval");
        if (maxInt) maxInt.value = statusRes.max_interval_seconds || 90;
        const avoidConc = document.getElementById("farm-cfg-avoid-concurrent");
        if (avoidConc) avoidConc.checked = statusRes.avoid_concurrent_attacks !== false;
        const bootUnl = document.getElementById("farm-cfg-bootstrap-unlisted");
        if (bootUnl) bootUnl.checked = statusRes.bootstrap_unlisted_barbarians !== false;
        const stopLoss = document.getElementById("farm-cfg-stop-on-losses");
        if (stopLoss) stopLoss.checked = statusRes.stop_on_losses !== false;
      }

      // Carregar Alvos de Farm
      const targetsRes = await window.api.getFarmTargets();
      const tbody = document.getElementById("farm-targets-table-body");
      const templateASum = document.getElementById("farm-template-a-summary");
      const templateBSum = document.getElementById("farm-template-b-summary");
      const totalBarbsEl = document.getElementById("farm-stats-total-targets");
      const inTransitEl = document.getElementById("farm-stats-in-transit");

      function formatTemplateTroops(tObj) {
        if (!tObj || typeof tObj !== "object") return "Não configurado";
        const unitLabels = {
          spear: "🗡️",
          sword: "🛡️",
          axe: "🪓",
          archer: "🏹",
          spy: "👁️",
          light: "🐎",
          marcher: "🏹🐎",
          heavy: "🛡️🐎",
          ram: "🚪",
          catapult: "☄️",
          knight: "👑",
          snob: "🎩",
        };
        const parts = [];
        for (const [u, qty] of Object.entries(tObj)) {
          const n = parseInt(qty, 10) || 0;
          if (n > 0) {
            const icon = unitLabels[u] || u;
            parts.push(`${icon} ${n}`);
          }
        }
        return parts.length > 0 ? parts.join(" &bull; ") : "Vazio (0 tropas)";
      }

      if (targetsRes && targetsRes.status === "success") {
        if (targetsRes.template_a) farmModalTemplatesData.A = { ...farmModalTemplatesData.A, ...targetsRes.template_a };
        if (targetsRes.template_b) farmModalTemplatesData.B = { ...farmModalTemplatesData.B, ...targetsRes.template_b };

        if (templateASum) {
          templateASum.innerHTML = formatTemplateTroops(targetsRes.template_a);
        }
        if (templateBSum) {
          templateBSum.innerHTML = formatTemplateTroops(targetsRes.template_b);
        }

        const targets = targetsRes.targets || [];
        if (totalBarbsEl) totalBarbsEl.textContent = targets.length;
        const inTransitCount = targets.filter(t => t.has_attack_in_transit).length;
        if (inTransitEl) inTransitEl.textContent = inTransitCount;

        if (tbody) {
          if (targets.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 24px;">Nenhuma aldeia bárbara encontrada no raio configurado.</td></tr>`;
          } else {
            let html = "";
            for (const t of targets) {
              const colorClass = `farm-report-${t.last_report_color || 'none'}`;
              const lootBadge = t.loot_status === "full"
                ? `<span style="background: rgba(245, 158, 11, 0.2); color: #fbbf24; padding: 2px 6px; border-radius: 4px; font-weight: 700; font-size: 0.72rem;">Cheio</span>`
                : t.loot_status === "partial"
                ? `<span style="background: rgba(6, 182, 212, 0.2); color: var(--neon-cyan); padding: 2px 6px; border-radius: 4px; font-size: 0.72rem;">Parcial</span>`
                : `<span style="color: var(--text-muted); font-size: 0.72rem;">-</span>`;
              const transitBadge = t.has_attack_in_transit
                ? `<span style="color: var(--neon-amber); font-weight: 700;">⚔️ A Caminho</span>`
                : `<span style="color: var(--neon-emerald);">Livre</span>`;
              const sourceBadge = !t.is_in_am_farm
                ? `<span style="background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); padding: 1px 5px; border-radius: 4px; font-size: 0.68rem; margin-left: 6px;">Mapa</span>`
                : "";
              const reportHtml = t.is_in_am_farm
                ? `<span class="farm-report-dot ${colorClass}" title="Relatório: ${t.last_report_color}"></span>`
                : `<span title="Descoberta no Mapa (aguarda 1º saque)" style="font-size: 0.72rem; color: #c084fc; font-weight: 600;">✨ Novo</span>`;

              html += `<tr>
                <td><strong>${escapeHtml(t.name)}</strong>${sourceBadge}</td>
                <td><span style="font-family: var(--font-mono); color: var(--neon-cyan);">${t.coordinates}</span></td>
                <td>${t.distance.toFixed(1)} camp.</td>
                <td><span style="font-family: var(--font-mono); font-size: 0.78rem;">${t.travel_time_cl_str || '-'}</span></td>
                <td>${reportHtml}</td>
                <td>${t.wall_level !== null ? `Nv. ${t.wall_level}` : '?'}</td>
                <td>${lootBadge} ${transitBadge}</td>
                <td style="text-align: right;">
                  <button class="btn btn-secondary btn-sm" onclick="triggerManualFarm('${t.village_id}', 'A')" style="padding: 2px 8px; font-size: 0.75rem; margin-right: 4px;" title="Atacar com Modelo A">⚔️ A</button>
                  <button class="btn btn-secondary btn-sm" onclick="triggerManualFarm('${t.village_id}', 'B')" style="padding: 2px 8px; font-size: 0.75rem;" title="Atacar com Modelo B">⚔️ B</button>
                </td>
              </tr>`;
            }
            tbody.innerHTML = html;
          }
        }
      }
    } catch (err) {
      console.error("Erro ao carregar AM Farm:", err);
    }
  }

  window.triggerManualFarm = async function(villageId, template) {
    try {
      showToast("info", `A enviar ataque modelo ${template}...`);
      await window.api.triggerFarmWave(true, villageId);
      showToast("success", `Comando enviado para o alvo.`);
      await loadAmFarmView();
    } catch (e) {
      showToast("error", `Falha ao enviar saque: ${e.message}`);
    }
  };

  async function loadRadarInactivesView() {
    try {
      // Status de sincronização
      const syncStatus = await window.api.getRadarSyncStatus();
      const badgeSync = document.getElementById("radar-sync-status-badge");
      if (badgeSync && syncStatus) {
        badgeSync.textContent = syncStatus.has_snapshot
          ? `✓ Atualizado (${syncStatus.last_sync_human_str} | ${syncStatus.total_villages.toLocaleString()} aldeias)`
          : "⚠️ Base não sincronizada";
      }

      // Parâmetros de filtro
      const maxDist = parseFloat(document.getElementById("radar-filter-max-distance")?.value || "25");
      const days = parseInt(document.getElementById("radar-filter-days-window")?.value || "7", 10);
      const minPts = parseInt(document.getElementById("radar-filter-min-points")?.value || "200", 10);
      const maxPts = parseInt(document.getElementById("radar-filter-max-points")?.value || "5000", 10);
      const maxGrowth = parseInt(document.getElementById("radar-filter-max-growth")?.value || "30", 10);
      const onlyTribeless = !!document.getElementById("radar-filter-only-tribeless")?.checked;
      const singleTribe = !!document.getElementById("radar-filter-single-tribe")?.checked;
      const includeBarbs = !!document.getElementById("radar-filter-barbarians")?.checked;
      const searchQuery = document.getElementById("radar-search-query")?.value || "";

      const filters = {
        max_distance: maxDist,
        days_window: days,
        min_points: minPts,
        max_points: maxPts,
        max_points_growth: maxGrowth,
        only_tribeless: onlyTribeless,
        include_single_member_tribes: singleTribe,
        include_barbarians: includeBarbs,
        search_query: searchQuery,
      };

      const inactRes = await window.api.getRadarInactives(filters);
      const tbody = document.getElementById("radar-inactives-table-body");
      const countStagnant = document.getElementById("radar-count-stagnant");
      const countRegressive = document.getElementById("radar-count-regressive");
      const countResidual = document.getElementById("radar-count-residual");
      const countTotal = document.getElementById("radar-count-total");

      if (inactRes && inactRes.status === "success") {
        if (countStagnant) countStagnant.textContent = inactRes.stagnant_count || 0;
        if (countRegressive) countRegressive.textContent = inactRes.regressive_count || 0;
        if (countResidual) countResidual.textContent = inactRes.residual_count || 0;
        if (countTotal) countTotal.textContent = inactRes.total_targets_found || 0;

        const targets = inactRes.targets || [];
        if (tbody) {
          if (targets.length === 0) {
            tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--text-muted); padding: 24px;">Nenhum alvo inativo encontrado com os filtros atuais. Experimente aumentar o raio de busca ou sincronizar os dados do mundo.</td></tr>`;
          } else {
            let html = "";
            for (const t of targets) {
              const deltaClass = t.delta_points < 0 ? "delta-regressive" : (t.delta_points === 0 ? "delta-stagnant" : "delta-residual");
              const deltaPrefix = t.delta_points > 0 ? `+${t.delta_points}` : `${t.delta_points}`;
              const farmBtnText = t.is_in_farm_list ? "✓ Na Lista" : "➕ Add Farm";
              const farmBtnDisabled = t.is_in_farm_list ? "disabled style='opacity: 0.6; padding: 3px 8px; font-size: 0.75rem;'" : "style='padding: 3px 8px; font-size: 0.75rem;'";

              html += `<tr>
                <td><strong>${escapeHtml(t.player_name)}</strong></td>
                <td><span style="color: var(--neon-purple); font-weight: 600;">${t.tribe_tag ? escapeHtml(t.tribe_tag) : '-'}</span></td>
                <td>${escapeHtml(t.village_name)}</td>
                <td><span style="font-family: var(--font-mono); color: var(--neon-cyan);">${t.coordinates}</span></td>
                <td>${t.current_points.toLocaleString()} pts</td>
                <td><span class="delta-tag ${deltaClass}">${deltaPrefix} pts</span></td>
                <td>${t.distance.toFixed(1)} camp.</td>
                <td><span style="font-family: var(--font-mono); font-size: 0.78rem;">${t.light_travel_time_str}</span> <small style="color: var(--text-muted);">(${t.eta_lc_str})</small></td>
                <td><span style="font-family: var(--font-mono); font-size: 0.78rem;">${t.spy_travel_time_str}</span></td>
                <td style="text-align: right;">
                  <button class="btn btn-secondary btn-sm" onclick="addRadarTarget('${t.coordinates}')" ${farmBtnDisabled}>${farmBtnText}</button>
                </td>
              </tr>`;
            }
            tbody.innerHTML = html;
          }
        }
      }
    } catch (err) {
      console.error("Erro ao carregar Radar de Inativos:", err);
    }
  }

  window.addRadarTarget = async function(coords) {
    try {
      const res = await window.api.addRadarTargetToFarm(coords);
      showToast("success", res.message || `Coordenada ${coords} adicionada à lista de farm.`);
      await loadRadarInactivesView();
    } catch (e) {
      showToast("error", `Falha ao adicionar alvo: ${e.message}`);
    }
  };

  // Event Listeners da Aba Farm
  document.getElementById("toggle-farm-master")?.addEventListener("change", async (e) => {
    try {
      await window.api.toggleFarm(e.target.checked);
      showToast("info", `Auto-Farm ${e.target.checked ? "ativado" : "desativado"}.`);
    } catch (err) {
      showToast("error", `Falha ao alternar farm: ${err.message}`);
    }
  });

  document.getElementById("btn-trigger-farm-wave")?.addEventListener("click", async () => {
    try {
      showToast("info", "A disparar ronda de saques do Assistente de Saque...");
      const res = await window.api.triggerFarmWave(true);
      showToast("success", res.message || "Ronda de farm concluída com sucesso!");
      await loadAmFarmView();
    } catch (err) {
      showToast("error", `Erro ao disparar saques: ${err.message}`);
    }
  });

  document.getElementById("btn-save-farm-settings")?.addEventListener("click", async () => {
    try {
      const payload = {
        default_template: document.getElementById("farm-cfg-default-template")?.value || "A",
        max_distance: parseFloat(document.getElementById("farm-cfg-max-distance")?.value || "25"),
        min_interval_seconds: parseFloat(document.getElementById("farm-cfg-min-interval")?.value || "45"),
        max_interval_seconds: parseFloat(document.getElementById("farm-cfg-max-interval")?.value || "90"),
        min_delay_per_attack_ms: parseInt(document.getElementById("farm-cfg-min-delay")?.value || "250", 10),
        max_delay_per_attack_ms: parseInt(document.getElementById("farm-cfg-max-delay")?.value || "650", 10),
        avoid_concurrent_attacks: !!document.getElementById("farm-cfg-avoid-concurrent")?.checked,
        bootstrap_unlisted_barbarians: !!document.getElementById("farm-cfg-bootstrap-unlisted")?.checked,
        stop_on_losses: !!document.getElementById("farm-cfg-stop-on-losses")?.checked,
      };
      await window.api.updateFarmConfig(payload);
      showToast("success", "Configurações de farm guardadas com sucesso!");
    } catch (err) {
      showToast("error", `Falha ao guardar configurações: ${err.message}`);
    }
  });

  document.getElementById("btn-refresh-farm-targets-list")?.addEventListener("click", loadAmFarmView);

  document.getElementById("btn-radar-sync-world")?.addEventListener("click", async () => {
    try {
      showToast("info", "A sincronizar dados oficiais do mundo (village.txt, player.txt)...");
      const res = await window.api.syncWorldData(null, true);
      showToast("success", `Sincronização concluída: ${res.villages_count} aldeias carregadas.`);
      await loadRadarInactivesView();
    } catch (err) {
      showToast("error", `Erro na sincronização: ${err.message}`);
    }
  });

  document.getElementById("btn-apply-radar-filters")?.addEventListener("click", loadRadarInactivesView);

  let radarSearchTimer = null;
  document.getElementById("radar-search-query")?.addEventListener("input", () => {
    clearTimeout(radarSearchTimer);
    radarSearchTimer = setTimeout(loadRadarInactivesView, 350);
  });

  // =========================================================================
  // --- MÓDULO 4.2: EVOLUÇÃO E MONITORIZAÇÃO DE JOGADORES NO RAIO X ---
  // =========================================================================

  let currentRadarMode = "inactives";

  function switchRadarMode(mode) {
    currentRadarMode = mode;
    const btnInact = document.getElementById("btn-radar-view-inactives");
    const btnEvo = document.getElementById("btn-radar-view-evolution");
    const viewInact = document.getElementById("radar-mode-inactives");
    const viewEvo = document.getElementById("radar-mode-evolution");

    if (btnInact) {
      btnInact.className = mode === "inactives" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm";
      btnInact.style.background = mode === "inactives" ? "" : "rgba(30,41,59,0.5)";
      btnInact.style.color = mode === "inactives" ? "" : "var(--text-muted)";
    }
    if (btnEvo) {
      btnEvo.className = mode === "evolution" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm";
      btnEvo.style.background = mode === "evolution" ? "" : "rgba(30,41,59,0.5)";
      btnEvo.style.color = mode === "evolution" ? "" : "var(--text-muted)";
    }

    if (viewInact) viewInact.style.display = mode === "inactives" ? "flex" : "none";
    if (viewEvo) viewEvo.style.display = mode === "evolution" ? "flex" : "none";

    if (mode === "evolution") {
      loadRadarPlayersEvolutionView();
    } else {
      loadRadarInactivesView();
    }
  }
  window.switchRadarMode = switchRadarMode;

  async function loadRadarPlayersEvolutionView() {
    try {
      const radiusInput = document.getElementById("radar-evo-radius");
      const radius = radiusInput ? parseFloat(radiusInput.value) || 25 : 25;
      const searchInput = document.getElementById("radar-evo-search-query");
      const query = searchInput ? searchInput.value.trim() : "";

      const tbody = document.getElementById("radar-evolution-table-body");
      if (tbody) {
        tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--text-muted); padding: 24px;">A varrer jogadores e calcular séries temporais no raio de ${radius} campos...</td></tr>`;
      }

      const res = await window.api.getRadarPlayersRadius({
        max_distance: radius,
        search_query: query,
        limit: 150,
      });

      if (res && res.status === "success") {
        const counts = res.counts || {};
        const countAcc = document.getElementById("radar-evo-count-accelerating");
        const countGrow = document.getElementById("radar-evo-count-growing");
        const countStag = document.getElementById("radar-evo-count-stagnant");
        const countReg = document.getElementById("radar-evo-count-regressive");
        const countTot = document.getElementById("radar-evo-count-total");

        if (countAcc) countAcc.textContent = counts.accelerating || 0;
        if (countGrow) countGrow.textContent = counts.growing || 0;
        if (countStag) countStag.textContent = (counts.stagnant || 0) + (counts.inactive || 0);
        if (countReg) countReg.textContent = counts.regressive || 0;
        if (countTot) countTot.textContent = res.total_players_found || 0;

        const players = res.players || [];
        if (tbody) {
          if (players.length === 0) {
            tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--text-muted); padding: 24px;">Nenhum jogador encontrado no raio de ${radius} campos. Experimente aumentar o raio ou sincronizar novos snapshots.</td></tr>`;
          } else {
            let html = "";
            for (const p of players) {
              const delta24Prefix = p.delta_24h > 0 ? `+${p.delta_24h}` : `${p.delta_24h}`;
              const delta24Class = p.delta_24h > 0 ? "color: var(--neon-emerald);" : (p.delta_24h < 0 ? "color: var(--neon-rose);" : "color: var(--text-muted);");

              const delta7dPrefix = p.delta_7d > 0 ? `+${p.delta_7d}` : `${p.delta_7d}`;
              const delta7dClass = p.delta_7d > 0 ? "color: var(--neon-emerald);" : (p.delta_7d < 0 ? "color: var(--neon-rose);" : "color: var(--text-muted);");

              const trendBadge = `<span class="badge" style="background: rgba(255,255,255,0.05); color: ${p.trend_color}; border: 1px solid ${p.trend_color}; font-size: 0.72rem; padding: 2px 8px;">${escapeHtml(p.trend_label)}</span>`;

              const safePName = escapeHtml(p.player_name || "").replace(/'/g, "\\'");
              const safeAlly = escapeHtml(p.ally_tag || "").replace(/'/g, "\\'");

              html += `<tr>
                <td><strong>${escapeHtml(p.player_name)}</strong></td>
                <td><span style="color: var(--neon-purple); font-weight: 600;">${p.ally_tag ? escapeHtml(p.ally_tag) : '-'}</span></td>
                <td>
                  <div>${escapeHtml(p.nearest_village_name)}</div>
                  <span style="font-family: var(--font-mono); color: var(--neon-cyan); font-size: 0.75rem;">(${p.nearest_coords})</span>
                </td>
                <td><span style="font-weight: 600;">${p.nearest_distance.toFixed(1)}</span> camp.</td>
                <td><strong>${(p.player_points || 0).toLocaleString()}</strong> pts</td>
                <td><span class="badge" style="background: rgba(30,41,59,0.8);">${p.villages_count || 1}</span></td>
                <td><span style="${delta24Class} font-family: var(--font-mono); font-weight: 700;">${delta24Prefix} pts</span></td>
                <td><span style="${delta7dClass} font-family: var(--font-mono); font-weight: 700;">${delta7dPrefix} pts</span></td>
                <td>${trendBadge}</td>
                <td style="text-align: right; white-space: nowrap;">
                  <button type="button" class="btn btn-secondary btn-sm" onclick="openPlayerHistoryModal(${p.player_id}, '${safePName}', '${safeAlly}', ${p.player_points})" style="padding: 2px 8px; font-size: 0.75rem;">
                    <span>📊</span> Histórico
                  </button>
                  <button type="button" class="btn btn-outline btn-sm" onclick="addRadarTarget('${p.nearest_coords}')" style="padding: 2px 8px; font-size: 0.75rem; border-color: rgba(6,182,212,0.4); color: var(--neon-cyan); margin-left: 4px;">
                    <span>➕</span> Farm
                  </button>
                </td>
              </tr>`;
            }
            tbody.innerHTML = html;
          }
        }
      }
    } catch (err) {
      console.error("Erro ao carregar evolução dos jogadores:", err);
      showToast("error", `Erro ao carregar jogadores no raio: ${err.message}`);
    }
  }
  window.loadRadarPlayersEvolutionView = loadRadarPlayersEvolutionView;

  async function triggerRadarSyncEvo() {
    try {
      showToast("info", "A recolher novo snapshot oficial do mundo...");
      const res = await window.api.syncWorldData(null, true);
      showToast("success", `Snapshot recolhido: ${res.villages_count} aldeias e ${res.players_count} jogadores sincronizados.`);
      await loadRadarPlayersEvolutionView();
    } catch (err) {
      showToast("error", `Erro ao sincronizar snapshot: ${err.message}`);
    }
  }
  window.triggerRadarSyncEvo = triggerRadarSyncEvo;

  let radarEvoSearchTimer = null;
  document.getElementById("radar-evo-search-query")?.addEventListener("input", () => {
    clearTimeout(radarEvoSearchTimer);
    radarEvoSearchTimer = setTimeout(loadRadarPlayersEvolutionView, 350);
  });

  async function openPlayerHistoryModal(playerId, playerName, allyTag, currentPoints) {
    const modal = document.getElementById("player-history-modal");
    if (!modal) return;

    const titleEl = document.getElementById("player-history-modal-title");
    if (titleEl) {
      titleEl.innerHTML = `<span>📈</span> Evolução Temporal: <span style="color: var(--neon-cyan);">${escapeHtml(playerName || "Jogador")}</span>`;
    }

    const metaBar = document.getElementById("player-history-meta-bar");
    if (metaBar) {
      metaBar.innerHTML = `
        <div><strong>ID:</strong> <span style="font-family: var(--font-mono);">${playerId}</span></div>
        <div><strong>Tribo:</strong> <span style="color: var(--neon-purple); font-weight: 600;">${allyTag || 'Sem Tribo'}</span></div>
        <div><strong>Pontos Atuais:</strong> <span style="color: var(--neon-emerald); font-weight: 700;">${(currentPoints || 0).toLocaleString()} pts</span></div>
      `;
    }

    const tbody = document.getElementById("player-history-table-body");
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 16px;">A recuperar medições no histórico SQLite...</td></tr>`;
    }

    modal.style.display = "flex";

    try {
      const res = await window.api.getPlayerHistory(playerId);
      if (res && res.status === "success") {
        const timeline = res.timeline || [];
        if (tbody) {
          if (timeline.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 16px;">Apenas 1 medição disponível. O bot continuará a registrar novos snapshots periodicamente.</td></tr>`;
          } else {
            let html = "";
            for (const row of timeline) {
              const deltaPrefix = row.delta > 0 ? `+${row.delta}` : `${row.delta}`;
              const deltaColor = row.delta > 0 ? "color: var(--neon-emerald);" : (row.delta < 0 ? "color: var(--neon-rose);" : "color: var(--text-muted);");

              html += `<tr>
                <td><span style="font-family: var(--font-mono);">${row.date_human}</span> <small style="color: var(--text-muted);">(${row.hours_diff > 0 ? '+' + row.hours_diff + 'h' : 'base'})</small></td>
                <td><strong>${row.points.toLocaleString()}</strong></td>
                <td><span style="${deltaColor} font-family: var(--font-mono); font-weight: 700;">${deltaPrefix}</span></td>
                <td>${row.villages_count}</td>
                <td>#${row.rank || '-'}</td>
                <td><span style="color: var(--neon-purple);">${row.ally_tag || '-'}</span></td>
              </tr>`;
            }
            tbody.innerHTML = html;
          }
        }
      }
    } catch (e) {
      if (tbody) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--neon-rose); padding: 16px;">Erro ao obter histórico: ${e.message}</td></tr>`;
      }
    }
  }
  window.openPlayerHistoryModal = openPlayerHistoryModal;

  function closePlayerHistoryModal() {
    const modal = document.getElementById("player-history-modal");
    if (modal) modal.style.display = "none";
  }
  window.closePlayerHistoryModal = closePlayerHistoryModal;

  // --- Gestor Modal de Modelos de Saque (AM Farm) ---
  const UNIT_HAUL_CAPACITIES = {
    spear: 25,
    sword: 15,
    axe: 10,
    archer: 10,
    spy: 0,
    light: 80,
    marcher: 50,
    heavy: 50,
    ram: 0,
    catapult: 0,
    knight: 100,
    snob: 0,
  };

  const UNIT_METADATA = [
    { key: "spear", name: "Lanceiro", icon: "🗡️" },
    { key: "sword", name: "Espadachim", icon: "🛡️" },
    { key: "axe", name: "Viking", icon: "🪓" },
    { key: "archer", name: "Arqueiro", icon: "🏹" },
    { key: "spy", name: "Espião", icon: "👁️" },
    { key: "light", name: "Cavalaria Leve", icon: "🐎" },
    { key: "marcher", name: "Arq. a Cavalo", icon: "🏹🐎" },
    { key: "heavy", name: "Cav. Pesada", icon: "🛡️🐎" },
    { key: "ram", name: "Aríete", icon: "🚪" },
    { key: "catapult", name: "Catapulta", icon: "☄️" },
    { key: "knight", name: "Paladino", icon: "👑" },
    { key: "snob", name: "Nobre", icon: "🎩" },
  ];

  let farmModalActiveTmpl = "A";
  let farmModalTemplatesData = {
    A: { spear: 0, sword: 0, axe: 0, archer: 0, spy: 0, light: 5, marcher: 0, heavy: 0, ram: 0, catapult: 0, knight: 0, snob: 0 },
    B: { spear: 0, sword: 0, axe: 0, archer: 0, spy: 0, light: 10, marcher: 0, heavy: 0, ram: 0, catapult: 0, knight: 0, snob: 0 },
  };

  function openFarmTemplatesModal() {
    const modal = document.getElementById("farm-templates-modal");
    if (modal) {
      modal.style.display = "flex";
      modal.classList.add("active");
    }
    selectFarmModalTemplate(farmModalActiveTmpl);
  }

  function closeFarmTemplatesModal() {
    const modal = document.getElementById("farm-templates-modal");
    if (modal) {
      modal.style.display = "none";
      modal.classList.remove("active");
    }
    const msg = document.getElementById("farm-tmpl-save-status-msg");
    if (msg) msg.textContent = "";
  }

  function selectFarmModalTemplate(tmpl) {
    farmModalActiveTmpl = tmpl.toUpperCase();
    const btnA = document.getElementById("btn-tab-farm-tmpl-a");
    const btnB = document.getElementById("btn-tab-farm-tmpl-b");
    if (btnA) {
      btnA.className = farmModalActiveTmpl === "A" ? "btn btn-primary" : "btn btn-secondary";
      btnA.style.background = farmModalActiveTmpl === "A" ? "var(--gradient-primary)" : "rgba(30,41,59,0.5)";
      btnA.style.color = farmModalActiveTmpl === "A" ? "#fff" : "var(--text-muted)";
    }
    if (btnB) {
      btnB.className = farmModalActiveTmpl === "B" ? "btn btn-primary" : "btn btn-secondary";
      btnB.style.background = farmModalActiveTmpl === "B" ? "var(--gradient-primary)" : "rgba(30,41,59,0.5)";
      btnB.style.color = farmModalActiveTmpl === "B" ? "#fff" : "var(--text-muted)";
    }
    renderFarmTemplateUnitsGrid();
    calcAndRenderHaulCapacity();
  }

  function renderFarmTemplateUnitsGrid() {
    const grid = document.getElementById("farm-tmpl-units-grid");
    if (!grid) return;
    const currentUnits = farmModalTemplatesData[farmModalActiveTmpl] || {};

    let html = "";
    for (const u of UNIT_METADATA) {
      const qty = currentUnits[u.key] || 0;
      html += `
        <div style="background: rgba(30, 41, 59, 0.6); padding: 8px 10px; border-radius: 8px; border: 1px solid var(--border-subtle); display: flex; flex-direction: column; gap: 6px;">
          <div style="font-size: 0.75rem; font-weight: 600; color: var(--text-main); display: flex; align-items: center; justify-content: space-between;">
            <span>${u.icon} ${u.name}</span>
            <small style="color: var(--text-muted); font-size: 0.68rem;">(${UNIT_HAUL_CAPACITIES[u.key] || 0} cap)</small>
          </div>
          <div style="display: flex; align-items: center; gap: 4px;">
            <button type="button" class="btn btn-secondary btn-sm" onclick="adjustFarmUnit('${u.key}', -1)" style="padding: 2px 7px; font-size: 0.72rem;">-</button>
            <input type="number" id="input-farm-unit-${u.key}" value="${qty}" min="0" max="10000" style="width: 100%; text-align: center; font-family: var(--font-mono); font-size: 0.8rem; background: rgba(0,0,0,0.3); border: 1px solid var(--border-subtle); color: #fff; border-radius: 4px; padding: 2px 4px;" oninput="onFarmUnitInput('${u.key}', this.value)">
            <button type="button" class="btn btn-secondary btn-sm" onclick="adjustFarmUnit('${u.key}', 1)" style="padding: 2px 7px; font-size: 0.72rem;">+</button>
          </div>
        </div>
      `;
    }
    grid.innerHTML = html;
  }

  window.adjustFarmUnit = function(unitKey, delta) {
    const curr = farmModalTemplatesData[farmModalActiveTmpl] = farmModalTemplatesData[farmModalActiveTmpl] || {};
    const val = Math.max(0, (curr[unitKey] || 0) + delta);
    curr[unitKey] = val;
    const input = document.getElementById(`input-farm-unit-${unitKey}`);
    if (input) input.value = val;
    calcAndRenderHaulCapacity();
  };

  window.onFarmUnitInput = function(unitKey, valStr) {
    const curr = farmModalTemplatesData[farmModalActiveTmpl] = farmModalTemplatesData[farmModalActiveTmpl] || {};
    const n = Math.max(0, parseInt(valStr, 10) || 0);
    curr[unitKey] = n;
    calcAndRenderHaulCapacity();
  };

  function calcAndRenderHaulCapacity() {
    const curr = farmModalTemplatesData[farmModalActiveTmpl] || {};
    let totalCap = 0;
    for (const [u, qty] of Object.entries(curr)) {
      totalCap += (parseInt(qty, 10) || 0) * (UNIT_HAUL_CAPACITIES[u] || 0);
    }
    const capEl = document.getElementById("farm-tmpl-haul-capacity");
    if (capEl) capEl.textContent = totalCap.toLocaleString();
  }

  window.applyFarmPreset = function(presetKey) {
    const curr = farmModalTemplatesData[farmModalActiveTmpl] = {
      spear: 0, sword: 0, axe: 0, archer: 0, spy: 0, light: 0, marcher: 0, heavy: 0, ram: 0, catapult: 0, knight: 0, snob: 0
    };
    if (presetKey === "micro_2lc") {
      curr.light = 2;
    } else if (presetKey === "std_4lc_1spy") {
      curr.light = 4;
      curr.spy = 1;
    } else if (presetKey === "infantry_early") {
      curr.spear = 10;
      curr.sword = 10;
    } else if (presetKey === "heavy_10lc") {
      curr.light = 10;
      curr.spy = 2;
    }
    renderFarmTemplateUnitsGrid();
    calcAndRenderHaulCapacity();
  };

  async function saveFarmTemplateToGame() {
    const msgEl = document.getElementById("farm-tmpl-save-status-msg");
    try {
      if (msgEl) msgEl.textContent = "A gravar modelo no servidor do jogo...";
      const tmpl = farmModalActiveTmpl.toLowerCase();
      const units = farmModalTemplatesData[farmModalActiveTmpl] || {};
      const res = await window.api.updateFarmTemplate(tmpl, units);
      if (res && res.status === "success") {
        showToast("success", `Modelo ${farmModalActiveTmpl} guardado com sucesso no jogo!`);
        if (msgEl) msgEl.textContent = `✓ Modelo ${farmModalActiveTmpl} gravado!`;
        setTimeout(closeFarmTemplatesModal, 800);
        await loadAmFarmView();
      } else {
        throw new Error(res.message || "Falha ao gravar.");
      }
    } catch (err) {
      if (msgEl) msgEl.textContent = `Erro: ${err.message}`;
      showToast("error", `Falha ao gravar modelo: ${err.message}`);
    }
  }

  // Listeners do Modal de Modelos
  window.openFarmTemplatesModal = openFarmTemplatesModal;
  window.closeFarmTemplatesModal = closeFarmTemplatesModal;
  window.selectFarmModalTemplate = selectFarmModalTemplate;
  document.getElementById("btn-open-farm-templates-modal")?.addEventListener("click", openFarmTemplatesModal);
  document.getElementById("btn-close-farm-templates-modal")?.addEventListener("click", closeFarmTemplatesModal);
  document.getElementById("btn-cancel-farm-templates-modal")?.addEventListener("click", closeFarmTemplatesModal);
  document.getElementById("btn-tab-farm-tmpl-a")?.addEventListener("click", () => selectFarmModalTemplate("A"));
  document.getElementById("btn-tab-farm-tmpl-b")?.addEventListener("click", () => selectFarmModalTemplate("B"));
  document.getElementById("btn-save-farm-template-to-game")?.addEventListener("click", saveFarmTemplateToGame);

  let initialLoaded = false;

  async function refreshStatus() {
    try {
      const statusData = await window.api.getStatus();
      applyStateData(statusData);
      refreshDiscoveredWorlds();
      if (!initialLoaded) {
        initialLoaded = true;
        // O bot arranca SEMPRE no Gestor de Contas (Hub) com todas as contas Offline
        showAccountHub();
      }
    } catch (e) {
      // Sidecar ainda pode estar a iniciar
    }
  }

  // Descoberta inicial de mundos e polling de segurança a cada 15 segundos
  refreshDiscoveredWorlds();
  refreshStatus();
  setInterval(refreshStatus, 15000);
});

