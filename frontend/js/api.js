/**
 * TribalWars Bot - Camada de Comunicação REST com o Sidecar Local
 */

class SidecarApi {
  constructor() {
    this.baseUrl = window.location.origin;
    // Se aberto via file:// ou porta externa, fallback para 127.0.0.1:8000
    if (!this.baseUrl || this.baseUrl === "null" || this.baseUrl.startsWith("file:")) {
      this.baseUrl = "http://127.0.0.1:8000";
    }
    this.token = this.extractInitialToken();
  }

  extractInitialToken() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get("token") || localStorage.getItem("tw_sidecar_token") || "";
  }

  async discoverAuth() {
    // 1. Se já tem token, testa status
    if (this.token) {
      try {
        const res = await this.request("/api/health");
        if (res && res.status === "ok") return this.token;
      } catch (e) {
        // Token pode ser inválido
      }
    }

    // 2. Tenta obter token automático local via /api/auth-info
    try {
      const resp = await fetch(`${this.baseUrl}/api/auth-info`);
      if (resp.ok) {
        const data = await resp.json();
        if (data.token) {
          this.token = data.token;
          localStorage.setItem("tw_sidecar_token", this.token);
          return this.token;
        }
      }
    } catch (e) {
      console.warn("Falha na descoberta automática de auth:", e);
    }

    return this.token;
  }

  async request(endpoint, options = {}) {
    const headers = {
      "Content-Type": "application/json",
      "X-Engine-Token": this.token,
      ...(options.headers || {}),
    };

    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      throw new Error("UNAUTHORIZED: Token do Sidecar inválido ou expirado.");
    }

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Erro na API (${response.status}): ${errorText}`);
    }

    return await response.json();
  }

  async getStatus() {
    return await this.request("/api/status");
  }

  async getConfig(world) {
    const qs = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/config${qs}`);
  }

  async updateConfig(configData, world) {
    const qs = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/config${qs}`, {
      method: "POST",
      body: JSON.stringify(configData),
    });
  }

  async pauseScheduler() {
    return await this.request("/api/scheduler/pause", { method: "POST" });
  }

  async resumeScheduler() {
    return await this.request("/api/scheduler/resume", { method: "POST" });
  }

  async triggerBuild() {
    return await this.request("/api/actions/build/trigger", { method: "POST" });
  }

  async triggerRecruit() {
    return await this.request("/api/actions/recruit/trigger", { method: "POST" });
  }

  async resumeBotProtection() {
    return await this.request("/api/bot-protect/resume", { method: "POST" });
  }

  async renewSession() {
    return await this.request("/api/auth/renew", { method: "POST" });
  }

  async getVillages() {
    return await this.request("/api/account/villages");
  }

  async switchVillage(villageId) {
    return await this.request("/api/account/switch-village", {
      method: "POST",
      body: JSON.stringify({ village_id: parseInt(villageId, 10) }),
    });
  }

  async getProfiles() {
    return await this.request("/api/profiles");
  }

  async switchProfile(profileId) {
    return await this.request("/api/profiles/switch", {
      method: "POST",
      body: JSON.stringify({ profile_id: profileId }),
    });
  }

  async testProxy(proxyUrl) {
    return await this.request("/api/proxy/test", {
      method: "POST",
      body: JSON.stringify({ proxy: proxyUrl }),
    });
  }

  async getMapData(x = null, y = null, radius = 15, refresh = false) {
    let query = `?radius=${radius}`;
    if (x !== null && x !== undefined && !isNaN(x)) query += `&x=${x}`;
    if (y !== null && y !== undefined && !isNaN(y)) query += `&y=${y}`;
    if (refresh) query += `&refresh=true`;
    return await this.request(`/api/map/data${query}`);
  }

  async refreshVillage() {
    return await this.request("/api/account/refresh", { method: "POST" });
  }

  async claimAllQuests() {
    return await this.request("/api/quest/claim-all", { method: "POST" });
  }

  async getQuestStatus() {
    return await this.request("/api/quest/status");
  }

  async getMapGrid(x, y, radius = 15) {
    const params = new URLSearchParams();
    if (x !== undefined && x !== null) params.set("x", x);
    if (y !== undefined && y !== null) params.set("y", y);
    if (radius) params.set("radius", radius);
    return await this.request(`/api/map/grid?${params.toString()}`);
  }

  async getMapBarbarians(radius = 15, useCache = true) {
    const params = new URLSearchParams({ radius, use_cache: useCache });
    return await this.request(`/api/map/barbarians?${params.toString()}`);
  }

  async scanMap(radius = 15) {
    return await this.request(`/api/map/scan?radius=${radius}`, { method: "POST" });
  }

  // --- Gestão de Perfis de Conta & Bloqueio Monousuário (Account Manager) ---
  async getAccounts() {
    return await this.request("/api/accounts");
  }

  async getAccount(accountId) {
    return await this.request(`/api/accounts/${accountId}`);
  }

  async createAccount(data) {
    return await this.request("/api/accounts", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async updateAccount(accountId, data) {
    return await this.request(`/api/accounts/${accountId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async deleteAccount(accountId) {
    return await this.request(`/api/accounts/${accountId}`, {
      method: "DELETE",
    });
  }

  async activateAccount(accountId) {
    return await this.request(`/api/accounts/${accountId}/activate`, {
      method: "POST",
    });
  }

  async disconnectAccount() {
    return await this.request("/api/accounts/disconnect", {
      method: "POST",
    });
  }

  // Aliases de compatibilidade
  async getProfiles() {
    return await this.getAccounts();
  }

  async switchProfile(profileId) {
    return await this.activateAccount(profileId);
  }

  // --- Multi-Mundo Simultâneo ---
  async getWorlds() {
    return await this.request("/api/worlds");
  }

  async discoverWorlds() {
    return await this.request("/api/worlds/discover");
  }

  async registerWorld(world, sid, domain = "tribalwars.com.pt", proxy = null) {
    return await this.request("/api/worlds/register", {
      method: "POST",
      body: JSON.stringify({ world, sid, domain, proxy }),
    });
  }

  async switchWorld(world) {
    return await this.request("/api/worlds/switch", {
      method: "POST",
      body: JSON.stringify({ world }),
    });
  }

  // --- Multi-Aldeia & Categorização ---
  async getAccountVillages() {
    return await this.request("/api/account/villages");
  }

  async setVillageCategory(villageId, category) {
    return await this.request("/api/account/village/category", {
      method: "POST",
      body: JSON.stringify({ village_id: parseInt(villageId, 10), category }),
    });
  }

  async triggerAllVillagesCycle() {
    return await this.request("/api/account/villages/cycle", { method: "POST" });
  }

  async getVillageBalance() {
    return await this.request("/api/account/villages/balance");
  }

  // --- Mercado & Balanceamento de Recursos ---
  async getMarketState(villageId = null) {
    const url = villageId ? `/api/market/state?village_id=${villageId}` : "/api/market/state";
    return await this.request(url);
  }

  async sendMarketResources(sourceVillageId, targetVillageId, wood = 0, stone = 0, iron = 0) {
    return await this.request("/api/market/send", {
      method: "POST",
      body: JSON.stringify({
        source_village_id: parseInt(sourceVillageId, 10),
        target_village_id: parseInt(targetVillageId, 10),
        wood: parseInt(wood, 10),
        stone: parseInt(stone, 10),
        iron: parseInt(iron, 10),
      }),
    });
  }

  async getMarketBalancingPlan() {
    return await this.request("/api/market/balance/plan");
  }

  async triggerMarketBalancing() {
    return await this.request("/api/market/balance/trigger", { method: "POST" });
  }

  async createMarketOffer(villageId, sellRes, sellAmount, buyRes, buyAmount, maxTime = 10, multi = 1) {
    return await this.request("/api/market/offer", {
      method: "POST",
      body: JSON.stringify({
        village_id: parseInt(villageId, 10),
        sell_res: sellRes,
        sell_amount: parseInt(sellAmount, 10),
        buy_res: buyRes,
        buy_amount: parseInt(buyAmount, 10),
        max_time: parseInt(maxTime, 10),
        multi: parseInt(multi, 10),
      }),
    });
  }

  async toggleMarket(enabled = null, autoBalanceEnabled = null) {
    const payload = {};
    if (enabled !== null) payload.enabled = enabled;
    if (autoBalanceEnabled !== null) payload.auto_balance_enabled = autoBalanceEnabled;
    return await this.request("/api/market/toggle", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async getBuildingState(villageId = null) {
    const url = villageId ? `/api/building/state?village_id=${villageId}` : "/api/building/state";
    return await this.request(url);
  }

  async cancelBuildingOrder(orderId, villageId = null) {
    const url = villageId ? `/api/building/cancel/${orderId}?village_id=${villageId}` : `/api/building/cancel/${orderId}`;
    return await this.request(url, { method: "POST" });
  }

  async toggleBuilding(enabled = null, intervalSeconds = null, maxQueue = null, autoFarmPriority = null, farmThresholdPop = null) {
    const payload = {};
    if (enabled !== null) payload.enabled = enabled;
    if (intervalSeconds !== null) payload.interval_seconds = parseFloat(intervalSeconds);
    if (maxQueue !== null) payload.max_queue = parseInt(maxQueue, 10);
    if (autoFarmPriority !== null) payload.auto_farm_priority = autoFarmPriority;
    if (farmThresholdPop !== null) payload.farm_threshold_pop = parseInt(farmThresholdPop, 10);
    return await this.request("/api/building/toggle", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async getRecruitmentState(villageId = null) {
    const url = villageId ? `/api/recruitment/state?village_id=${villageId}` : "/api/recruitment/state";
    return await this.request(url);
  }

  async getRecruitmentModels() {
    return await this.request("/api/recruitment/models");
  }

  async saveRecruitmentModels(attack = null, defense = null, models = null, batchSizes = null) {
    const payload = {};
    if (attack !== null) payload.attack = attack;
    if (defense !== null) payload.defense = defense;
    if (models !== null) payload.models = models;
    if (batchSizes !== null) payload.batch_sizes = batchSizes;
    return await this.request("/api/recruitment/models", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async deleteRecruitmentModel(modelName) {
    return await this.request(`/api/recruitment/models/${encodeURIComponent(modelName)}`, {
      method: "DELETE",
    });
  }

  async toggleRecruitment(enabled = null, intervalMinutes = null, minFreePop = null, maxQueueElements = null) {
    const payload = {};
    if (enabled !== null) payload.enabled = enabled;
    if (intervalMinutes !== null) payload.interval_minutes = parseFloat(intervalMinutes);
    if (minFreePop !== null) payload.min_free_pop = parseInt(minFreePop, 10);
    if (maxQueueElements !== null) payload.max_queue_elements = parseInt(maxQueueElements, 10);
    return await this.request("/api/recruitment/toggle", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  // --- Estatísticas & Métricas ---

  async getStatsSummary(world = null) {
    const url = world ? `/api/stats/summary?world=${encodeURIComponent(world)}` : "/api/stats/summary";
    return await this.request(url);
  }

  async getStatsHistory(hours = 24, days = 7, world = null) {
    let url = `/api/stats/history?hours=${hours}&days=${days}`;
    if (world) {
      url += `&world=${encodeURIComponent(world)}`;
    }
    return await this.request(url);
  }

  async resetStats(world = null) {
    const url = world ? `/api/stats/reset?world=${encodeURIComponent(world)}` : "/api/stats/reset";
    return await this.request(url, { method: "POST" });
  }

  // --- Gestão de Contas & Multi-Conta Monousuário ---

  async getAccounts() {
    return await this.request("/api/accounts");
  }

  async createAccount(accountData) {
    return await this.request("/api/accounts", {
      method: "POST",
      body: JSON.stringify(accountData),
    });
  }

  async updateAccount(accountId, accountData) {
    return await this.request(`/api/accounts/${accountId}`, {
      method: "PUT",
      body: JSON.stringify(accountData),
    });
  }

  async deleteAccount(accountId) {
    return await this.request(`/api/accounts/${accountId}`, {
      method: "DELETE",
    });
  }

  async activateAccount(accountId) {
    return await this.request(`/api/accounts/${accountId}/activate`, {
      method: "POST",
    });
  }

  async autoLoginAccount(accountId) {
    return await this.request(`/api/accounts/${encodeURIComponent(accountId)}/auto-login`, {
      method: "POST",
    });
  }

  async disconnectAccount() {
    return await this.request("/api/accounts/disconnect", {
      method: "POST",
    });
  }

  async refreshVillage() {
    return await this.request("/api/village/refresh", {
      method: "POST",
    });
  }

  // --- Gestão de Modelos de Construção (Building Templates - SQLite) ---
  async getBuildingTemplates(accountId = null) {
    const query = accountId ? `?account_id=${encodeURIComponent(accountId)}` : "";
    return await this.request(`/api/templates/building${query}`);
  }

  async getBuildingTemplate(templateId) {
    return await this.request(`/api/templates/building/${encodeURIComponent(templateId)}`);
  }

  async createBuildingTemplate(data) {
    return await this.request("/api/templates/building", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async updateBuildingTemplate(templateId, data) {
    return await this.request(`/api/templates/building/${encodeURIComponent(templateId)}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async cloneBuildingTemplate(templateId, newName = null, accountId = null) {
    return await this.request(`/api/templates/building/${encodeURIComponent(templateId)}/clone`, {
      method: "POST",
      body: JSON.stringify({ new_name: newName, account_id: accountId }),
    });
  }

  async deleteBuildingTemplate(templateId) {
    return await this.request(`/api/templates/building/${encodeURIComponent(templateId)}`, {
      method: "DELETE",
    });
  }

  // --- Gestão de Modelos de Recrutamento (Recruitment Models - SQLite) ---
  async getRecruitmentTemplates(accountId = null) {
    const query = accountId ? `?account_id=${encodeURIComponent(accountId)}` : "";
    return await this.request(`/api/templates/recruitment${query}`);
  }

  async getRecruitmentTemplate(modelId) {
    return await this.request(`/api/templates/recruitment/${encodeURIComponent(modelId)}`);
  }

  async createRecruitmentTemplate(data) {
    return await this.request("/api/templates/recruitment", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async updateRecruitmentTemplate(modelId, data) {
    return await this.request(`/api/templates/recruitment/${encodeURIComponent(modelId)}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async cloneRecruitmentTemplate(modelId, newName = null, accountId = null) {
    return await this.request(`/api/templates/recruitment/${encodeURIComponent(modelId)}/clone`, {
      method: "POST",
      body: JSON.stringify({ new_name: newName, account_id: accountId }),
    });
  }

  async deleteRecruitmentTemplate(modelId) {
    return await this.request(`/api/templates/recruitment/${encodeURIComponent(modelId)}`, {
      method: "DELETE",
    });
  }

  // --- Assistente de Saque & Farm (/api/farm/*) ---
  async getFarmStatus(world = null) {
    const q = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/farm/status${q}`);
  }

  async toggleFarm(enabled, world = null) {
    return await this.request("/api/farm/toggle", {
      method: "POST",
      body: JSON.stringify({ enabled, world }),
    });
  }

  async triggerFarmWave(force = true, villageId = null, world = null) {
    return await this.request("/api/farm/trigger", {
      method: "POST",
      body: JSON.stringify({ force, village_id: villageId, world }),
    });
  }

  async updateFarmConfig(configData) {
    return await this.request("/api/farm/config", {
      method: "POST",
      body: JSON.stringify(configData),
    });
  }

  async getFarmTargets(radius = null, limit = 100, villageId = null, world = null) {
    const params = new URLSearchParams();
    if (radius) params.append("radius", radius);
    if (limit) params.append("limit", limit);
    if (villageId) params.append("village_id", villageId);
    if (world) params.append("world", world);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return await this.request(`/api/farm/targets${qs}`);
  }

  async updateFarmTemplate(template, units, villageId = null, world = null) {
    return await this.request("/api/farm/templates", {
      method: "POST",
      body: JSON.stringify({
        template,
        units,
        village_id: villageId,
        world,
      }),
    });
  }

  // --- Radar de Inativos & Inno-Farming (/api/radar/*) ---
  async getRadarInactives(filters = {}) {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(filters)) {
      if (v !== undefined && v !== null) params.append(k, v);
    }
    const qs = params.toString() ? `?${params.toString()}` : "";
    return await this.request(`/api/radar/inactives${qs}`);
  }

  async syncWorldData(world = null, force = false) {
    return await this.request("/api/radar/sync", {
      method: "POST",
      body: JSON.stringify({ world, force }),
    });
  }

  async getRadarSyncStatus(world = null) {
    const q = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/radar/sync-status${q}`);
  }

  async addRadarTargetToFarm(coords, world = null) {
    return await this.request("/api/radar/targets/add", {
      method: "POST",
      body: JSON.stringify({ coords, world }),
    });
  }

  async getRadarPlayersRadius(params = {}) {
    const usp = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "") usp.append(k, v);
    }
    const qs = usp.toString() ? `?${usp.toString()}` : "";
    return await this.request(`/api/radar/players-radius${qs}`);
  }

  async getPlayerHistory(playerId, world = null, limit = 30) {
    const usp = new URLSearchParams();
    if (world) usp.append("world", world);
    if (limit) usp.append("limit", limit);
    const qs = usp.toString() ? `?${usp.toString()}` : "";
    return await this.request(`/api/radar/player-history/${playerId}${qs}`);
  }

  // --- Módulo de Defesa & Alarme de Ataques (Ponto 2.8) ---

  async getDefenseStatus(world = null) {
    const qs = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/defense/incomings${qs}`);
  }

  async checkDefenseIncomings(world = null) {
    const qs = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/defense/check${qs}`, { method: "POST" });
  }

  async toggleAutoDodge(payload, world = null) {
    const qs = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/defense/dodge/toggle${qs}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async triggerManualDodge(payload = {}, world = null) {
    const qs = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/defense/dodge/trigger${qs}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async cancelDefenseCommand(commandId, villageId = null, world = null) {
    const qs = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/defense/command/cancel${qs}`, {
      method: "POST",
      body: JSON.stringify({ command_id: commandId, village_id: villageId }),
    });
  }

  async updateDefenseConfig(payload, world = null) {
    const qs = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/defense/config${qs}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  // --- Módulo de Táticas de Combate & Sincronização ao Milissegundo (Ponto 2.9) ---

  async getCombatStatus(world = null) {
    const qs = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/combat/status${qs}`);
  }

  async pingClockSync(world = null) {
    const qs = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/combat/sync/ping${qs}`, { method: "POST" });
  }

  async launchNobleTrain(payload, world = null) {
    const qs = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/combat/noble-train${qs}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async calculateBacktime(payload, world = null) {
    const qs = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/combat/backtime/calculate${qs}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async scheduleBacktime(payload, world = null) {
    const qs = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/combat/backtime/schedule${qs}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async analyzeSnipes(villageId = null, world = null) {
    const qs = new URLSearchParams();
    if (villageId) qs.append("village_id", villageId);
    if (world) qs.append("world", world);
    const qsStr = qs.toString() ? `?${qs.toString()}` : "";
    return await this.request(`/api/combat/snipe/analyze${qsStr}`, { method: "POST" });
  }

  async cancelTacticalOperation(operationId) {
    return await this.request("/api/combat/operation/cancel", {
      method: "POST",
      body: JSON.stringify({ operation_id: operationId }),
    });
  }

  async updateCombatConfig(payload, world = null) {
    const qs = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/combat/config${qs}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  // --- Módulo de Coleta de Recursos / Scavenging (Ponto 2.4 & Fase 4) ---

  async getScavengeStatus(villageId = null, world = null) {
    const qs = new URLSearchParams();
    if (villageId) qs.append("village_id", villageId);
    if (world) qs.append("world", world);
    const qsStr = qs.toString() ? `?${qs.toString()}` : "";
    return await this.request(`/api/scavenge/status${qsStr}`);
  }

  async toggleScavengeModule(payload, world = null) {
    const qs = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/scavenge/toggle${qs}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async triggerScavengeCycle(payload = {}, world = null) {
    const qs = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/scavenge/trigger${qs}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async unlockScavengeOption(optionId, villageId = null, world = null) {
    const qs = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/scavenge/unlock${qs}`, {
      method: "POST",
      body: JSON.stringify({ option_id: optionId, village_id: villageId }),
    });
  }

  // --- Módulo da Academia & Moedas (Ponto 2.6 & Fase 4) ---

  async getSnobStatus(villageId = null, world = null) {
    const qs = new URLSearchParams();
    if (villageId) qs.append("village_id", villageId);
    if (world) qs.append("world", world);
    const qsStr = qs.toString() ? `?${qs.toString()}` : "";
    return await this.request(`/api/snob/status${qsStr}`);
  }

  async mintSnobCoins(count = 1, villageId = null, world = null) {
    const qs = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/snob/mint${qs}`, {
      method: "POST",
      body: JSON.stringify({ count: count, village_id: villageId }),
    });
  }

  async recruitSnobNobleman(villageId = null, world = null) {
    const qs = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/snob/recruit${qs}`, {
      method: "POST",
      body: JSON.stringify({ village_id: villageId }),
    });
  }

  async updateSnobConfig(payload, world = null) {
    const qs = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/snob/config${qs}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  // --- Módulo do Inventário (Ponto 2.10 & Fase 4) ---

  async getInventoryItems(forceRefresh = false, world = null) {
    const qs = new URLSearchParams();
    if (forceRefresh) qs.append("force_refresh", "true");
    if (world) qs.append("world", world);
    const qsStr = qs.toString() ? `?${qs.toString()}` : "";
    return await this.request(`/api/inventory/items${qsStr}`);
  }

  async useInventoryItem(itemId, villageId = null, world = null) {
    const qs = world ? `?world=${encodeURIComponent(world)}` : "";
    return await this.request(`/api/inventory/use${qs}`, {
      method: "POST",
      body: JSON.stringify({ item_id: itemId, village_id: villageId }),
    });
  }

  // --- Cloud SQL / Multi-Account & Multi-World APIs ---

  async registerAppUser(email, password, licenseType = "standard") {
    return await this.request("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, license_type: licenseType }),
    });
  }

  async loginAppUser(email, password) {
    return await this.request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  }

  async getCurrentAppUser() {
    return await this.request("/api/auth/me");
  }

  async logoutAppUser() {
    return await this.request("/api/auth/logout", { method: "POST" });
  }

  async switchGameAccount(gameUsername, accountId = null) {
    return await this.request("/api/accounts/switch", {
      method: "POST",
      body: JSON.stringify({ game_username: gameUsername, account_id: accountId }),
    });
  }

  async getActiveAccountStatus() {
    return await this.request("/api/accounts/active");
  }

  async getGameWorlds(accountId = null) {
    const qs = accountId ? `?account_id=${encodeURIComponent(accountId)}` : "";
    return await this.request(`/api/worlds${qs}`);
  }

  async addGameWorld(worldCode, isActive = true) {
    return await this.request("/api/worlds", {
      method: "POST",
      body: JSON.stringify({ world_code: worldCode, is_active: isActive }),
    });
  }

  async toggleGameWorld(worldCode, isActive) {
    return await this.request(`/api/worlds/${encodeURIComponent(worldCode)}/toggle`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: isActive }),
    });
  }

  async getWorldVillages(worldCode) {
    return await this.request(`/api/worlds/${encodeURIComponent(worldCode)}/villages`);
  }

  async getAvailableWorldsToAdd() {
    return await this.request("/api/worlds/available-to-add");
  }

  async activateGameWorld(world, sid = null, domain = null, proxy = null) {
    return await this.request("/api/worlds/activate", {
      method: "POST",
      body: JSON.stringify({ world, sid, domain, proxy }),
    });
  }

  async toggleAccountWorld(accountId, worldCode, isActive) {
    return await this.request(`/api/accounts/${encodeURIComponent(accountId)}/worlds/${encodeURIComponent(worldCode)}/toggle`, {
      method: "POST",
      body: JSON.stringify({ is_active: isActive }),
    });
  }

  async updateVillageModel(villageId, activeBuildModelId) {
    return await this.request(`/api/villages/${encodeURIComponent(villageId)}/model`, {
      method: "PATCH",
      body: JSON.stringify({ active_build_model_id: activeBuildModelId }),
    });
  }
}

// Exporta instância global
window.api = new SidecarApi();

