# Tribal Wars Bot - Lista de Tarefas (TODO)

> **Regra de Manutenção:** Este ficheiro deve ser mantido atualizado a cada avanço no projeto. Sempre que uma funcionalidade for concluída ou modificada, marcar a respetiva caixa de seleção `[x]` e atualizar o registo em `PROJECT_STATE.md`.

---

## 📌 Fase 1: Fundação do Core Engine & Evasão de Rede
- [x] **Arquitetura Base & Configuração**
  - [x] Estrutura modular de pastas (`engine/core`, `engine/utils`, `engine/actions`, `engine/api`, `tests`).
  - [x] Definição de dependências em `pyproject.toml` e `requirements.txt`.
  - [x] Configuração de `.gitignore` para ignorar caches Python e ficheiros temporários.
- [x] **Camada de Rede & Mascaramento Criptográfico (TLS/JA3)**
  - [x] Cliente `TribalAccount` com `curl_cffi` (`AsyncSession` + `impersonate="chrome124"`).
  - [x] Headers móveis Android (`Sec-CH-UA-Mobile: ?1`, `Sec-CH-UA-Platform: "Android"`).
  - [x] Injeção dinâmica do cookie de sessão `sid`.
  - [x] Forçamento do parâmetro `page=mobile` em todas as rotas GET/POST.
  - [x] Tratamento de erros HTTP, rate limiting (HTTP 429) e manutenção de servidores (502/503).
- [x] **Deteção de Anti-Bot & Gestão de Sessão**
  - [x] Interceção de marcadores anti-bot (`id="bot_protect"`, `name="bot_check"`) disparando `BotProtectionError`.
  - [x] Deteção de expiração de sessão / ecrã de boas-vindas disparando `SessionExpiredError`.
- [x] **Temporização Humana & Micro-Jitters**
  - [x] Gerador de atrasos gaussianos truncados (`get_human_delay`).
  - [x] Micro-jitters mecânicos de toque em ecrã (`get_click_jitter`: 120ms a 380ms).
- [x] **Agendador de Tarefas com Fila de Prioridade**
  - [x] `TaskScheduler` assíncrono baseado em `asyncio.PriorityQueue`.
  - [x] Níveis de prioridade: `ALERT (0)` > `DEFENSE (10)` > `FARM (20)` > `SCAVENGE (30)` > `BUILD (40)` > `RECRUIT (50)` > `REFRESH (90)`.
  - [x] **Auto-pausa instantânea** perante alerta anti-bot com preservação da tarefa na fila.
  - [x] Suporte a preempção e retentativas com backoff exponencial.
- [x] **Testes do Core**
  - [x] 10 testes unitários cobrindo modelos, timing, parsers, account e scheduler.

---

## 📌 Fase 2: Módulos de Ações do Jogo (`game.php`)

### 2.1. Edifício Principal (`screen=main`)
- [x] Parsing de níveis de edifícios via `game_data.village.buildings` e fallback HTML.
- [x] Parsing da fila ativa de construção (`#buildqueue`) com extração de tempo e token de cancelamento.
- [x] Parsing de custos de melhoria, população e motivos de indisponibilidade (recursos, armazém, fazenda, requisitos).
- [x] Normalização de nomes de edifícios (português/inglês) e mapeamento canónico (`BuildingType`).
- [x] Árvore tecnológica de requisitos de edifícios (`BUILDING_REQUIREMENTS`).
- [x] Cálculo de **níveis virtuais** (`nível atual + construções pendentes na fila`).
- [x] Restrição de segurança de capacidade de fila (padrão de 2 construções sem custos extras).
- [x] Modelos de evolução pré-definidos (`RUSH_RESOURCES_TEMPLATE`, `BALANCED_TEMPLATE`, `MILITARY_RUSH_TEMPLATE`).
- [x] Controlador `MainBuildingManager` com disparo de `build` e `cancel` com token CSRF (`h`).
- [x] Rotina periódica contínua de auto-build com feedback imediato aos 5s e ciclos humanos (60s-90s).
- [x] Sistema de configuração flexível via `config.json` e `engine/config/settings.py` (suporte a templates e planos customizados).
- [x] Suíte de testes unitários dedicada (11 testes do Edifício Principal + 2 de configuração, total de 23 testes, 100% OK).


### 2.2. Praça de Reunião & Gestão de Tropas (`screen=place`)
- [x] Parsing da contagem de tropas disponíveis na aldeia ativa (`spear`, `sword`, `axe`, `archer`, `spy`, `light`, `marcher`, `heavy`, `ram`, `catapult`, `knight`, `snob`).
- [x] Leitura de comandos em curso (tropas a atacar, apoiar ou a regressar à aldeia).
- [x] Módulo de envio de comandos (Ataque / Apoio) em 2 etapas:
  - [x] Etapa 1: Envio do formulário inicial com coordenadas de destino (`target_x`, `target_y` ou ID da aldeia) e contagem de tropas.
  - [x] Etapa 2: Confirmação do comando (`action=command&h=...`) com extração da duração da marcha e tipo de ataque.
- [x] Suíte de testes unitários para a Praça de Reunião (10 testes dedicados, total de 33 testes, 100% OK).


### 2.3. Micro-Farming Automatizado
- [x] Suporte a Assistente de Farm (`screen=am_farm`):
  - [x] Leitura da tabela de aldeias bárbaras vizinhas (`#plunder_list`).
  - [x] Leitura do estado dos relatórios (verde, amarelo, vermelho) e nível de muralha.
  - [x] Disparo automatizado dos modelos A e B com atrasos humanos entre toques (200ms - 550ms).
- [x] Fallback para Farming via Praça de Reunião (`screen=place`):
  - [x] Lista configurável de aldeias bárbaras por coordenadas ou raio de distância.
  - [x] Envio automático de micro-grupos de saque (ex.: 5 lanceiros ou 2 cavalarias leves).
- [x] Critérios de segurança: paragem imediata do farm caso as tropas sofram baixas (`skip_losses`) ou a muralha inimiga suba (`skip_wall`).
- [x] Suíte de testes unitários para Micro-Farming (6 testes dedicados, total de 39 testes, 100% OK).


### 2.4. Coleta de Recursos / Scavenging (`screen=place&mode=scavenge`)
- [ ] Leitura do estado de desbloqueio das 4 categorias de coleta:
  - Categoria 1: Coleta Preguiçosa (*Lazy Scavenging* - 10%).
  - Categoria 2: Coleta Modesta (*Humble Scavenging* - 25%).
  - Categoria 3: Coleta Habilidosa (*Clever Scavenging* - 50%).
  - Categoria 4: Coleta Excelente (*Great Scavenging* - 75%).
- [ ] Parsing de grupos de coleta em andamento e contadores de tempo restante.
- [ ] **Algoritmo de Otimização de Coleta:**
  - [ ] Cálculo proporcional da distribuição de tropas para que as 4 categorias terminem ao mesmo tempo, maximizando o ganho por hora.
- [ ] Disparo automático com timer e agendamento para reenvio assim que as tropas regressam.

### 2.5. Recrutamento Militar (Quartel, Estábulo, Oficina)
- [x] Parsing do ecrã do Quartel (`screen=barracks`), Estábulo (`screen=stable`) e Oficina (`screen=garage`).
- [x] Leitura das filas de recrutamento ativas e tempo de conclusão.
- [x] Configuração de metas de exército (ex.: 1000 lanceiros, 1000 espadachins, 500 cavalarias leves).
- [x] Recrutamento inteligente em pequenos lotes contínuos para não esgotar recursos necessários à evolução da aldeia.
- [x] Validação de limite de população livre da Fazenda antes de recrutar (`min_free_pop`).
- [x] Suíte de testes unitários para Recrutamento Militar (5 testes dedicados, total de 44 testes, 100% OK).


### 2.6. Academia & Cunha de Moedas (`screen=snob`)
- [ ] Leitura de moedas cunhadas / pacotes acumulados.
- [ ] Cunha automática de moedas quando o armazém estiver prestes a encher (`wood/stone/iron >= 85% do storage_max`).
- [ ] Recrutamento automático de Nobres mediante configuração do utilizador.

### 2.7. Mercado & Balanceamento (`screen=market`)
- [ ] Leitura de mercadores disponíveis.
- [ ] Balanceamento automático de recursos entre aldeias da mesma conta.
- [ ] Criação de ofertas no mercado para trocar excedentes de recursos por recursos deficitários.

### 2.8. Sistema de Defesa & Alarme de Ataques (Prioridade 0 / Alertas)
- [ ] Monitorização em tempo real de ataques a chegar à aldeia (`incomings`).
- [ ] Deteção da velocidade da unidade mais lenta atacante para estimar o tipo de ataque (Nobre, Aríete, Cavalaria, etc.).
- [ ] **Rotina de Auto-Dodge (Desvio de Tropas e Recursos):**
  - [ ] Envio das tropas e recursos para uma aldeia bárbara próxima 30 segundos antes do impacto do ataque.
  - [ ] Cancelamento imediato do comando após o impacto para que as tropas regressem em segurança.
- [ ] Notificação sonora e visual de emergência.

---

## 📌 Fase 3: Camada Sidecar IPC & Gestão de Sessões (`engine/api/`)

- [x] **Servidor Local FastAPI & WebSockets**
  - [x] Execução em localhost com porta dinâmica e token efêmero de autenticação local (`.sidecar_auth.json`).
  - [x] Endpoints REST para comandos manuais, leitura de status, alteração de configurações e toggles de rotinas.
  - [x] Canal WebSocket bidirecional para streaming em tempo real:
    - [x] Logs do bot categorizados por severidade (`INFO`, `WARNING`, `CRITICAL`) via `WebSocketLogHandler`.
    - [x] Recursos, aldeias e estado das filas em tempo real (`INITIAL_STATE`, `STATUS_UPDATE`).
    - [x] Disparo de alerta de captcha anti-bot para o frontend (`CAPTCHA_ALERT`).
  - [x] Suíte de testes unitários para a API Sidecar (12 testes dedicados, total de 56 testes, 100% OK).
- [ ] **Gestor de Contas & Multi-Aldeia**
  - [ ] Persistência segura de perfis de conta (ficheiro JSON/SQLite encriptado).
  - [ ] Suporte a proxy dedicado ou residencial por conta (`http://user:pass@ip:port`).
  - [ ] Alternância fluida de contexto entre múltiplas aldeias (`village_id`).


---

## 📌 Fase 4: Shell Desktop & Frontend Nativo (`frontend/`)

- [x] **Interface Gráfica (UI/UX Premium Cockpit)**
  - [x] Dashboard com visual moderno (Dark Mode, Glassmorphism, Google Fonts Outfit & Inter, paleta Neon Cyber).
  - [x] Visão geral da aldeia: cartões de recursos em tempo real (Madeira, Argila, Ferro), capacidade do Armazém e População livre.
  - [x] Fila de construção em tempo real com contagem decrescente ativa e estimativa de custos para o próximo edifício.
  - [x] Painel de controlo de módulos com botões de ação imediata (Pausar/Retomar, Construir Agora, Farm Agora, Recrutar Agora).
  - [x] Consola de logs ao vivo via streaming WebSocket com busca por texto, filtros de severidade (`INFO`, `WARNING`, `CRITICAL`), auto-scroll e limpeza.
  - [x] Painel de configurações visuais com gravação instantânea e recarregamento a quente no `config.json`.
- [x] **Shell Desktop Nativa Edge WebView2 & Tauri v2 Ready**
  - [x] Execução como aplicação desktop nativa via Edge WebView2 (`engine/desktop_launcher.py` ou `python -m engine.main --gui`).
  - [x] Servidor Sidecar serve a interface web diretamente em `http://127.0.0.1:8000/` (`python -m engine.main --api`).
  - [x] Estrutura do frontend (`frontend/`) 100% isolada e compatível para build final via Tauri v2 (`tauri.conf.json`).
- [x] **Modal de Alerta & Resolução de Captchas Anti-Bot**
  - [x] Overlay modal de emergência ativado instantaneamente por evento WebSocket (`CAPTCHA_ALERT`) com aviso sonoro sintetizado.
  - [x] Botão para abertura direta da janela do jogo para resolução humana e botão para retoma automática do motor.
- [ ] **Notificações de Sistema & System Tray**
  - [ ] Notificações sonoras do sistema para ataques inimigos a chegar (`incomings`).
  - [ ] Minimizar para o System Tray com menu de contexto rápido.


---

## 📌 Fase 5: Empacotamento, Testes E2E & Release

- [ ] Empacotamento do executável Python isolado com PyInstaller ou PyStandalone.
- [ ] Build do instalador desktop nativo (`.msi` / `.exe`) via Tauri Bundler.
- [ ] Testes de robustez com reconexão automática em caso de quebra de internet.
- [ ] Documentação de utilização final e guia de configuração de proxies e templates.
