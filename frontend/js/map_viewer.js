/**
 * TribalWars Bot - Visualizador de Mapa Interativo Integrado (Cockpit Map Viewer)
 * Renderizador de Canvas 60 FPS com Pan, Zoom, Destaque de Bárbaras e Ações Rápidas.
 */

class MapViewer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext("2d");

    // Estado da Câmara e Projeção
    this.centerX = 500;
    this.centerY = 500;
    this.tileSize = 38; // Pixels por campo de jogo
    this.minTileSize = 16;
    this.maxTileSize = 72;

    // Dados do Mapa
    this.villages = [];
    this.selectedVillage = null;
    this.hoveredVillage = null;
    this.farmRadius = 15;
    this.customTargets = new Set();
    this.ownVillageCoords = { x: 500, y: 500 };

    // Interações do Rato e Arrastar
    this.isDragging = false;
    this.dragStartX = 0;
    this.dragStartY = 0;
    this.cameraStartX = 0;
    this.cameraStartY = 0;
    this.hasMoved = false;

    // Animação e Pulso
    this.animationFrame = null;
    this.pulsePhase = 0;

    this.initEventListeners();
    this.resizeCanvas();
  }

  initEventListeners() {
    window.addEventListener("resize", () => this.resizeCanvas());

    this.canvas.addEventListener("mousedown", (e) => this.onMouseDown(e));
    window.addEventListener("mousemove", (e) => this.onMouseMove(e));
    window.addEventListener("mouseup", (e) => this.onMouseUp(e));
    this.canvas.addEventListener("wheel", (e) => this.onWheel(e), { passive: false });

    // Touch events
    this.canvas.addEventListener("touchstart", (e) => this.onTouchStart(e), { passive: false });
    this.canvas.addEventListener("touchmove", (e) => this.onTouchMove(e), { passive: false });
    this.canvas.addEventListener("touchend", (e) => this.onTouchEnd(e));

    // Botões de Zoom
    const btnIn = document.getElementById("btn-map-zoom-in");
    const btnOut = document.getElementById("btn-map-zoom-out");
    const btnReset = document.getElementById("btn-map-zoom-reset");
    const btnRecenter = document.getElementById("btn-map-recenter");
    const btnGo = document.getElementById("btn-map-go");
    const btnRefresh = document.getElementById("btn-map-refresh");
    const radiusSelector = document.getElementById("map-radius-selector");

    if (btnIn) btnIn.onclick = () => this.zoom(1.25);
    if (btnOut) btnOut.onclick = () => this.zoom(0.8);
    if (btnReset) btnReset.onclick = () => { this.tileSize = 38; this.render(); };
    if (btnRecenter) btnRecenter.onclick = () => this.recenterOnOwnVillage();
    if (btnRefresh) btnRefresh.onclick = () => this.loadMapData(true);

    if (btnGo) {
      btnGo.onclick = () => {
        const x = parseInt(document.getElementById("map-input-x")?.value, 10);
        const y = parseInt(document.getElementById("map-input-y")?.value, 10);
        if (!isNaN(x) && !isNaN(y)) {
          this.centerOn(x, y);
          this.loadMapData();
        }
      };
    }

    if (radiusSelector) {
      radiusSelector.onchange = (e) => {
        this.farmRadius = parseFloat(e.target.value) || 15;
        this.loadMapData();
      };
    }

    // Ações do Popover
    const popoverClose = document.getElementById("btn-popover-close");
    const popoverCopy = document.getElementById("btn-popover-copy-coords");

    if (popoverClose) popoverClose.onclick = () => this.closePopover();
    if (popoverCopy) popoverCopy.onclick = () => this.onPopoverCopyCoords();
  }

  resizeCanvas() {
    const parent = this.canvas.parentElement;
    if (!parent) return;
    this.canvas.width = parent.clientWidth;
    this.canvas.height = parent.clientHeight || 580;
    this.render();
  }

  startAnimationLoop() {
    if (this.animationFrame) return;
    const loop = () => {
      this.pulsePhase = (this.pulsePhase + 0.04) % (Math.PI * 2);
      this.render();
      this.animationFrame = requestAnimationFrame(loop);
    };
    this.animationFrame = requestAnimationFrame(loop);
  }

  stopAnimationLoop() {
    if (this.animationFrame) {
      cancelAnimationFrame(this.animationFrame);
      this.animationFrame = null;
    }
  }

  async loadMapData(forceRefresh = false) {
    try {
      const data = await window.api.getMapData(
        this.centerX,
        this.centerY,
        this.farmRadius,
        forceRefresh
      );

      if (data && data.status === "success") {
        this.villages = data.villages || [];
        this.updateStatsBadges(data.total_barbarians, data.total_players);
        this.render();
      }
    } catch (e) {
      console.warn("Erro ao carregar dados do mapa:", e);
    }
  }

  updateStatsBadges(barbs, players) {
    const elBarbs = document.getElementById("map-stat-barbs");
    const elPlayers = document.getElementById("map-stat-players");
    if (elBarbs) elBarbs.innerText = `🌿 ${barbs || 0} Bárbaras`;
    if (elPlayers) elPlayers.innerText = `🏰 ${players || 0} Jogadores`;
  }

  setOwnVillage(x, y) {
    this.ownVillageCoords = { x, y };
    this.centerX = x;
    this.centerY = y;
    const inpX = document.getElementById("map-input-x");
    const inpY = document.getElementById("map-input-y");
    if (inpX) inpX.value = x;
    if (inpY) inpY.value = y;
    this.render();
  }

  recenterOnOwnVillage() {
    this.centerOn(this.ownVillageCoords.x, this.ownVillageCoords.y);
  }

  centerOn(x, y) {
    this.centerX = x;
    this.centerY = y;
    const inpX = document.getElementById("map-input-x");
    const inpY = document.getElementById("map-input-y");
    if (inpX) inpX.value = x;
    if (inpY) inpY.value = y;
    this.render();
  }

  zoom(factor, mouseX = null, mouseY = null) {
    const prevSize = this.tileSize;
    const newSize = Math.max(this.minTileSize, Math.min(this.maxTileSize, this.tileSize * factor));
    if (newSize === prevSize) return;

    if (mouseX !== null && mouseY !== null) {
      const worldPos = this.screenToWorld(mouseX, mouseY);
      this.tileSize = newSize;
      const newWorldPos = this.screenToWorld(mouseX, mouseY);
      this.centerX += (worldPos.x - newWorldPos.x);
      this.centerY += (worldPos.y - newWorldPos.y);
    } else {
      this.tileSize = newSize;
    }
    this.render();
  }

  // --- Projeção de Coordenadas ---

  worldToScreen(wx, wy) {
    const cx = this.canvas.width / 2;
    const cy = this.canvas.height / 2;
    const sx = cx + (wx - this.centerX) * this.tileSize;
    const sy = cy + (wy - this.centerY) * this.tileSize;
    return { x: sx, y: sy };
  }

  screenToWorld(sx, sy) {
    const cx = this.canvas.width / 2;
    const cy = this.canvas.height / 2;
    const wx = this.centerX + (sx - cx) / this.tileSize;
    const wy = this.centerY + (sy - cy) / this.tileSize;
    return { x: wx, y: wy };
  }

  // --- Eventos de Rato e Toque ---

  onMouseDown(e) {
    if (e.button !== 0) return;
    this.isDragging = true;
    this.hasMoved = false;
    const rect = this.canvas.getBoundingClientRect();
    this.dragStartX = e.clientX - rect.left;
    this.dragStartY = e.clientY - rect.top;
    this.cameraStartX = this.centerX;
    this.cameraStartY = this.centerY;
  }

  onMouseMove(e) {
    const rect = this.canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    if (this.isDragging) {
      const dx = mx - this.dragStartX;
      const dy = my - this.dragStartY;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
        this.hasMoved = true;
      }
      this.centerX = this.cameraStartX - dx / this.tileSize;
      this.centerY = this.cameraStartY - dy / this.tileSize;
      this.render();
    } else {
      this.checkHover(mx, my);
    }
  }

  onMouseUp(e) {
    if (!this.isDragging) return;
    this.isDragging = false;
    if (!this.hasMoved) {
      const rect = this.canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      this.handleClick(mx, my);
    }
  }

  onWheel(e) {
    e.preventDefault();
    const rect = this.canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.15 : 0.85;
    this.zoom(factor, mx, my);
  }

  onTouchStart(e) {
    if (e.touches.length === 1) {
      this.isDragging = true;
      this.hasMoved = false;
      const rect = this.canvas.getBoundingClientRect();
      this.dragStartX = e.touches[0].clientX - rect.left;
      this.dragStartY = e.touches[0].clientY - rect.top;
      this.cameraStartX = this.centerX;
      this.cameraStartY = this.centerY;
    }
  }

  onTouchMove(e) {
    if (this.isDragging && e.touches.length === 1) {
      e.preventDefault();
      const rect = this.canvas.getBoundingClientRect();
      const mx = e.touches[0].clientX - rect.left;
      const my = e.touches[0].clientY - rect.top;
      const dx = mx - this.dragStartX;
      const dy = my - this.dragStartY;
      if (Math.abs(dx) > 4 || Math.abs(dy) > 4) this.hasMoved = true;
      this.centerX = this.cameraStartX - dx / this.tileSize;
      this.centerY = this.cameraStartY - dy / this.tileSize;
      this.render();
    }
  }

  onTouchEnd(e) {
    this.isDragging = false;
  }

  checkHover(mx, my) {
    const prevHovered = this.hoveredVillage;
    this.hoveredVillage = this.getVillageAtScreen(mx, my);

    if (this.hoveredVillage !== prevHovered) {
      this.canvas.style.cursor = this.hoveredVillage ? "pointer" : "crosshair";
      this.render();
    }
  }

  handleClick(mx, my) {
    const clicked = this.getVillageAtScreen(mx, my);
    if (clicked) {
      this.selectedVillage = clicked;
      this.openPopover(clicked, mx, my);
    } else {
      this.selectedVillage = null;
      this.closePopover();
    }
    this.render();
  }

  getVillageAtScreen(sx, sy) {
    const hitRadius = Math.max(14, this.tileSize * 0.45);
    for (const v of this.villages) {
      const pos = this.worldToScreen(v.x, v.y);
      const dist = Math.hypot(sx - pos.x, sy - pos.y);
      if (dist <= hitRadius) {
        return v;
      }
    }
    return null;
  }

  // --- Popover e Ações Rápidas ---

  openPopover(v, sx, sy) {
    const popover = document.getElementById("village-popover");
    if (!popover) return;

    document.getElementById("popover-title").innerText = `${v.name} (${v.x}|${v.y})`;
    document.getElementById("popover-player").innerText = v.is_barbarian ? "Aldeia Bárbara" : (v.player_name || "Jogador");
    document.getElementById("popover-points").innerText = `${v.points || 0} pts`;
    document.getElementById("popover-distance").innerText = `${v.distance || 0} campos`;

    // Cálculo estimado de tempo de marcha da Cavalaria Leve (10 min por campo)
    const marchMins = Math.round((v.distance || 0) * 10);
    const h = Math.floor(marchMins / 60);
    const m = marchMins % 60;
    const timeStr = h > 0 ? `${h}h ${m}m` : `${m}m`;
    document.getElementById("popover-time-cl").innerText = `~${timeStr} (CL)`;

    // Posição no canvas
    const wrapper = this.canvas.parentElement;
    const maxX = wrapper.clientWidth - 280;
    const maxY = wrapper.clientHeight - 220;
    popover.style.left = `${Math.min(maxX, Math.max(10, sx + 15))}px`;
    popover.style.top = `${Math.min(maxY, Math.max(10, sy - 40))}px`;
    popover.style.display = "block";
  }

  closePopover() {
    const popover = document.getElementById("village-popover");
    if (popover) popover.style.display = "none";
  }

  async onPopoverCopyCoords() {
    if (!this.selectedVillage) return;
    const v = this.selectedVillage;
    try {
      await navigator.clipboard.writeText(`${v.x}|${v.y}`);
      window.app?.addLog(`📋 Coordenadas (${v.x}|${v.y}) copiadas para a área de transferência.`, "info");
      this.closePopover();
    } catch (e) {
      window.app?.addLog(`Falha ao copiar coordenadas: ${e.message}`, "error");
    }
  }

  // --- Renderização Gráfica ---

  render() {
    const w = this.canvas.width;
    const h = this.canvas.height;
    const ctx = this.ctx;

    // 1. Limpar fundo (Espaço Cyber escuro)
    ctx.fillStyle = "#090d16";
    ctx.fillRect(0, 0, w, h);

    // 2. Desenhar Grelha de Coordenadas
    this.drawGrid(w, h);

    // 3. Desenhar Raio de Alcance do Farm
    this.drawFarmRadiusRing();

    // 4. Desenhar Aldeias
    this.drawVillages();

    // 5. Tooltip em Hover se houver
    if (this.hoveredVillage && !this.isDragging) {
      this.drawHoverTooltip(this.hoveredVillage);
    }
  }

  drawGrid(w, h) {
    const ctx = this.ctx;
    const bounds = {
      minW: this.screenToWorld(0, 0),
      maxW: this.screenToWorld(w, h),
    };

    const startX = Math.floor(bounds.minW.x);
    const endX = Math.ceil(bounds.maxW.x);
    const startY = Math.floor(bounds.minW.y);
    const endY = Math.ceil(bounds.maxW.y);

    ctx.lineWidth = 1;

    for (let x = startX; x <= endX; x++) {
      const screenPos = this.worldToScreen(x, this.centerY);
      ctx.strokeStyle = (x % 10 === 0) ? "rgba(0, 240, 255, 0.22)" : "rgba(30, 41, 59, 0.6)";
      ctx.beginPath();
      ctx.moveTo(screenPos.x, 0);
      ctx.lineTo(screenPos.x, h);
      ctx.stroke();

      // Rótulos de eixos a cada 5 ou 10 campos
      if (this.tileSize >= 22 || x % 5 === 0) {
        ctx.fillStyle = (x % 10 === 0) ? "#00f0ff" : "#64748b";
        ctx.font = "10px 'JetBrains Mono', monospace";
        ctx.fillText(`${x}`, screenPos.x + 3, 14);
      }
    }

    for (let y = startY; y <= endY; y++) {
      const screenPos = this.worldToScreen(this.centerX, y);
      ctx.strokeStyle = (y % 10 === 0) ? "rgba(0, 240, 255, 0.22)" : "rgba(30, 41, 59, 0.6)";
      ctx.beginPath();
      ctx.moveTo(0, screenPos.y);
      ctx.lineTo(w, screenPos.y);
      ctx.stroke();

      if (this.tileSize >= 22 || y % 5 === 0) {
        ctx.fillStyle = (y % 10 === 0) ? "#00f0ff" : "#64748b";
        ctx.font = "10px 'JetBrains Mono', monospace";
        ctx.fillText(`${y}`, 4, screenPos.y - 3);
      }
    }
  }

  drawFarmRadiusRing() {
    const ctx = this.ctx;
    const ownPos = this.worldToScreen(this.ownVillageCoords.x, this.ownVillageCoords.y);
    const radiusPixels = this.farmRadius * this.tileSize;

    ctx.save();
    ctx.beginPath();
    ctx.arc(ownPos.x, ownPos.y, radiusPixels, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(0, 240, 255, 0.35)";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([6, 6]);
    ctx.stroke();

    ctx.fillStyle = "rgba(0, 240, 255, 0.03)";
    ctx.fill();
    ctx.restore();
  }

  drawVillages() {
    const ctx = this.ctx;

    for (const v of this.villages) {
      const pos = this.worldToScreen(v.x, v.y);
      const isSelected = this.selectedVillage && this.selectedVillage.id === v.id;
      const isHovered = this.hoveredVillage && this.hoveredVillage.id === v.id;

      // Tamanho base do ícone da aldeia
      const size = Math.max(10, Math.min(24, this.tileSize * 0.38));

      ctx.save();

      if (v.is_own) {
        // Aldeia Ativa (Anel Pulsante Neon)
        const pulse = 4 + Math.sin(this.pulsePhase) * 3;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, size + pulse, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(0, 240, 255, 0.2)";
        ctx.fill();

        ctx.beginPath();
        ctx.arc(pos.x, pos.y, size, 0, Math.PI * 2);
        ctx.fillStyle = "#00f0ff";
        ctx.shadowColor = "#00f0ff";
        ctx.shadowBlur = 12;
        ctx.fill();

        ctx.fillStyle = "#090d16";
        ctx.font = "bold 11px Inter, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText("🏰", pos.x, pos.y);

      } else if (v.is_barbarian) {
        // Aldeia Bárbara (Verde Neon)
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, size, 0, Math.PI * 2);
        ctx.fillStyle = isHovered ? "#22c55e" : "rgba(34, 197, 94, 0.85)";
        ctx.shadowColor = "#22c55e";
        ctx.shadowBlur = isHovered ? 10 : 4;
        ctx.fill();

        ctx.fillStyle = "#ffffff";
        ctx.font = "10px Inter, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText("🌿", pos.x, pos.y);

      } else {
        // Aldeia de Jogador (Vermelho / Âmbar)
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, size, 0, Math.PI * 2);
        ctx.fillStyle = isHovered ? "#f43f5e" : "rgba(244, 63, 94, 0.85)";
        ctx.shadowColor = "#f43f5e";
        ctx.shadowBlur = isHovered ? 10 : 4;
        ctx.fill();

        ctx.fillStyle = "#ffffff";
        ctx.font = "10px Inter, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText("🛡", pos.x, pos.y);
      }

      // Destaque de Seleção
      if (isSelected) {
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, size + 6, 0, Math.PI * 2);
        ctx.strokeStyle = "#eab308";
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // Rótulo de Coordenadas se Zoom Suficiente
      if (this.tileSize >= 28) {
        ctx.fillStyle = "#cbd5e1";
        ctx.font = "10px 'JetBrains Mono', monospace";
        ctx.textAlign = "center";
        ctx.fillText(`(${v.x}|${v.y})`, pos.x, pos.y + size + 11);
      }

      ctx.restore();
    }
  }

  drawHoverTooltip(v) {
    const ctx = this.ctx;
    const pos = this.worldToScreen(v.x, v.y);

    const title = `${v.name} (${v.x}|${v.y})`;
    const sub = `${v.is_barbarian ? 'Bárbara' : (v.player_name || 'Jogador')} • ${v.distance || 0}c`;

    ctx.save();
    ctx.font = "bold 11px Inter, sans-serif";
    const textWidth = Math.max(ctx.measureText(title).width, ctx.measureText(sub).width);
    const boxW = textWidth + 18;
    const boxH = 40;
    const boxX = pos.x - boxW / 2;
    const boxY = pos.y - 52;

    ctx.fillStyle = "rgba(15, 23, 42, 0.94)";
    ctx.strokeStyle = "rgba(0, 240, 255, 0.5)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(boxX, boxY, boxW, boxH, 6);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = "#f8fafc";
    ctx.fillText(title, boxX + 9, boxY + 16);

    ctx.fillStyle = v.is_barbarian ? "#22c55e" : "#38bdf8";
    ctx.font = "10px Inter, sans-serif";
    ctx.fillText(sub, boxX + 9, boxY + 31);

    ctx.restore();
  }
}

// Exporta classe global
window.MapViewer = MapViewer;
