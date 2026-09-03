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
    if (!msg || !msg.type) return;

    // Emite sempre pelo tipo exato (ex.: STATS_UPDATED, RECRUITMENT_UPDATED, RECRUITMENT_CYCLE_EXECUTED)
    this.emit(msg.type, msg.data);
    this.emit(msg.type.toLowerCase(), msg.data);

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
      case "INCOMING_ATTACK_ALERT":
        if (!window.emergencyAlarmMuted) {
          this.playEmergencyAlarm();
        }
        this.emit("incoming_attack_alert", msg.data);
        break;
      case "INCOMING_ATTACKS_CLEARED":
        this.emit("incoming_attacks_cleared", msg.data);
        break;
      case "DODGE_EXECUTED":
        this.emit("dodge_executed", msg.data);
        break;
      case "DODGE_CANCELLED":
        this.emit("dodge_cancelled", msg.data);
        break;
      case "COMBAT_OPERATION_SCHEDULED":
        this.emit("combat_operation_scheduled", msg.data);
        break;
      case "COMBAT_OPERATION_EXECUTED":
        this.emit("combat_operation_executed", msg.data);
        break;
      case "COMBAT_FAILSAFE_TRIGGERED":
        if (!window.emergencyAlarmMuted) {
          this.playEmergencyAlarm();
        }
        this.emit("combat_failsafe_triggered", msg.data);
        break;
      case "COMBAT_CLOCK_SYNCED":
        this.emit("combat_clock_synced", msg.data);
        break;
      case "PONG":
        break;
      default:
        break;
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

  playEmergencyAlarm() {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const now = audioCtx.currentTime;

      // Duplo pulso de alerta tático (alerta vermelho militar)
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();

      osc.type = "sawtooth";
      // Pulso 1: 520Hz -> 780Hz
      osc.frequency.setValueAtTime(520, now);
      osc.frequency.linearRampToValueAtTime(780, now + 0.25);
      // Pulso 2: 520Hz -> 880Hz
      osc.frequency.setValueAtTime(520, now + 0.35);
      osc.frequency.linearRampToValueAtTime(880, now + 0.65);

      gain.gain.setValueAtTime(0.0, now);
      gain.gain.linearRampToValueAtTime(0.25, now + 0.05);
      gain.gain.linearRampToValueAtTime(0.05, now + 0.28);
      gain.gain.linearRampToValueAtTime(0.3, now + 0.4);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.75);

      osc.connect(gain);
      gain.connect(audioCtx.destination);

      osc.start(now);
      osc.stop(now + 0.75);
    } catch (e) {
      console.warn("Falha ao reproduzir alarme de emergência:", e);
    }
  }
}

// Exporta instância global
window.wsClient = new SidecarWebSocket();
