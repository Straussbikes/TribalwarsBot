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

  async getConfig() {
    return await this.request("/api/config");
  }

  async updateConfig(configData) {
    return await this.request("/api/config", {
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

  async triggerFarm() {
    return await this.request("/api/actions/farm/trigger", { method: "POST" });
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

  async addFarmTarget(x, y) {
    return await this.request("/api/map/farm-target", {
      method: "POST",
      body: JSON.stringify({ x: parseInt(x, 10), y: parseInt(y, 10) }),
    });
  }

  async sendQuickAttack(targetX, targetY, troops = {}) {
    return await this.request("/api/map/quick-attack", {
      method: "POST",
      body: JSON.stringify({
        target_x: parseInt(targetX, 10),
        target_y: parseInt(targetY, 10),
        spear: troops.spear || 0,
        sword: troops.sword || 0,
        axe: troops.axe || 0,
        spy: troops.spy || 0,
        light: troops.light || 0,
      }),
    });
  }
}


// Exporta instância global
window.api = new SidecarApi();
