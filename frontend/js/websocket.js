/**
 * TribalWars Bot - Gestor de WebSockets em Tempo Real
 * Suporta auto-reconnect, streaming de logs, telemetria contínua e alarmes sonoros.
 */

class SidecarWebSocket {
  constructor() {
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 30;
    this.reconnectInterval = 2000;
    this.listeners = {
      log: [],
      state: [],
      captcha: [],
      status: [],
    };
    this.isConnected = false;
  }

  on(event, callback) {
    if (this.listeners[event]) {
      this.listeners[event].push(callback);
    }
  }

  emit(event, data) {
    if (this.listeners[event]) {
      this.listeners[event].forEach(cb => cb(data));
    }
  }

  connect(baseUrl, token) {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    let wsHost = window.location.host;
    if (!wsHost || wsHost === "null") {
      wsHost = "127.0.0.1:8000";
    }

    const wsUrl = `${wsProtocol}//${wsHost}/ws?token=${encodeURIComponent(token)}`;
    console.log(`[WS] A conectar a ${wsUrl.replace(token, token.slice(0, 6) + "...")}`);

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.emit("status", { connected: true });
        console.log("[WS] Conexão estabelecida com sucesso.");
      };

      this.ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          this.handleMessage(payload);
        } catch (err) {
          console.warn("[WS] Falha ao processar mensagem JSON:", event.data);
        }
      };

      this.ws.onclose = (event) => {
        this.isConnected = false;
        this.emit("status", { connected: false });
        console.warn(`[WS] Conexão encerrada (código ${event.code}). Tentando reconectar...`);
        this.scheduleReconnect(baseUrl, token);
      };

      this.ws.onerror = (err) => {
        console.error("[WS] Erro no socket:", err);
      };
    } catch (e) {
      console.error("[WS] Falha ao instanciar WebSocket:", e);
      this.scheduleReconnect(baseUrl, token);
    }
  }

  handleMessage(msg) {
    switch (msg.type) {
      case "LOG":
        this.emit("log", msg.data);
        break;
      case "INITIAL_STATE":
      case "STATUS_UPDATE":
        this.emit("state", msg.data);
        break;
      case "CAPTCHA_ALERT":
        this.playAlertSound();
        this.emit("captcha", msg.data);
        break;
      case "BUILDING_TEMPLATES_UPDATED":
        this.emit("building_templates_updated", msg.data);
        break;
      case "RECRUITMENT_MODELS_UPDATED":
        this.emit("recruitment_models_updated", msg.data);
        break;
      case "PONG":
        break;
      default:
        console.log("[WS] Mensagem recebida:", msg);
    }
  }

  scheduleReconnect(baseUrl, token) {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error("[WS] Número máximo de tentativas de reconexão atingido.");
      return;
    }

    const delay = Math.min(this.reconnectInterval * Math.pow(1.3, this.reconnectAttempts), 15000);
    this.reconnectAttempts++;
    setTimeout(() => {
      this.connect(baseUrl, token);
    }, delay);
  }

  send(action, data = {}) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action, ...data }));
    }
  }

  playAlertSound() {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();

      osc.type = "sine";
      osc.frequency.setValueAtTime(880, audioCtx.currentTime); // Nota Lá (A5)
      osc.frequency.exponentialRampToValueAtTime(440, audioCtx.currentTime + 0.4);

      gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.5);

      osc.connect(gain);
      gain.connect(audioCtx.destination);

      osc.start();
      osc.stop(audioCtx.currentTime + 0.5);
    } catch (e) {
      console.warn("AudioContext não disponível ou bloqueado:", e);
    }
  }
}

// Exporta instância global
window.wsClient = new SidecarWebSocket();
