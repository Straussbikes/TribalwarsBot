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
  - [x] Injeção dinâmica do cookie de sessão `sid` nos domínios do mundo e raiz.
  - [x] Forçamento do parâmetro `page=mobile` em todas as rotas GET/POST.
  - [x] Tratamento de erros HTTP, rate limiting (HTTP 429) e manutenção de servidores (502/503).
  - [x] Método `account.update_sid(new_sid)` para encerramento limpo e reconstrução atómica de sessão.
- [x] **Deteção de Anti-Bot & Gestão de Sessão**
  - [x] Interceção de marcadores anti-bot (`id="bot_protect"`, `name="bot_check"`) disparando `BotProtectionError`.
  - [x] Deteção de expiração de sessão / ecrã de boas-vindas disparando `SessionExpiredError`.
  - [x] **Autenticação Manual & Interceção de Rede (`sid`)**
    - [x] Intercetor de tráfego HTTP em tempo real (`request_sent` / `response_received`) no WebView2 para captura imediata de cookies `sid` (incluindo `HttpOnly`).
    - [x] Auto-persistência atómica do cookie `sid` no `config.json` perante rotação do servidor (`save_config_sid`).
    - [x] Rotina periódica suave de **Keep-Alive** no `TaskScheduler` (~15 min) para impedir expiração por inatividade.
    - [x] Botão rápido "🔑 Entrar / Login" no Cockpit para abertura da janela nativa.
    - [x] Banner informativo injetado no ecrã de login com botão interativo `[Entrei no Jogo →]`.
    - [x] Suíte de testes unitários dedicada (`tests/test_auth.py` com 7 testes).
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
- [x] Rotina periódica contínua de auto-build com feedback imediato e ciclos humanos.
- [x] Sistema de configuração flexível via `config.json` e propriedade compatível `effective_building_plan`.
- [x] Suíte de testes unitários dedicada (12 testes do Edifício Principal + 2 de configuração).

### 2.2. Praça de Reunião & Gestão de Tropas (`screen=place`)
- [x] Parsing da contagem de tropas disponíveis na aldeia ativa (`spear`, `sword`, `axe`, `archer`, `spy`, `light`, `marcher`, `heavy`, `ram`, `catapult`, `knight`, `snob`).
- [x] Leitura de comandos em curso (tropas a atacar, apoiar ou a regressar à aldeia).
- [x] Módulo de envio de comandos (Ataque / Apoio) em 2 etapas:
  - [x] Etapa 1: Envio do formulário inicial com coordenadas de destino (`target_x`, `target_y` ou ID da aldeia) e contagem de tropas.
  - [x] Etapa 2: Confirmação do comando (`action=command&h=...`) com extração da duração da marcha e tipo de ataque.
- [x] Suíte de testes unitários para a Praça de Reunião (10 testes dedicados).

### 2.3. Micro-Farming Automatizado & Radar de Bárbaras
- [x] Suporte a Assistente de Farm (`screen=am_farm`):
  - [x] Leitura da tabela de aldeias bárbaras vizinhas (`#plunder_list`).
  - [x] Leitura do estado dos relatórios (verde, amarelo, vermelho) e nível de muralha.
  - [x] Disparo automatizado dos modelos A e B com atrasos humanos entre toques (200ms - 550ms).
- [x] Fallback para Farming via Praça de Reunião (`screen=place`):
  - [x] Lista configurável de aldeias bárbaras por coordenadas ou raio de distância.
  - [x] Envio automático de micro-grupos de saque (ex.: 5 lanceiros ou 2 cavalarias leves).
- [x] Critérios de segurança: paragem imediata do farm caso as tropas sofram baixas (`skip_losses`) ou a muralha inimiga suba (`skip_wall`).
- [x] Suíte de testes unitários para Micro-Farming (6 testes dedicados).
- [ ] **Radar de Bárbaras & Saque Recorrente Contínuo:**
  - [ ] Auto-descoberta de aldeias bárbaras num determinado raio através da leitura do mapa (`screen=map` ou dados de mapa).
  - [ ] Cálculo e ordenação automática por distância euclidiana/manhattan.
  - [ ] Agendamento em loop contínuo para manter as micro-tropas sempre a saquear com alocação dinâmica de unidades disponíveis.

### 2.4. Coleta de Recursos / Scavenging (`screen=place&mode=scavenge`)
- [ ] Leitura do estado de desbloqueio das 4 categorias de coleta (Lazy, Humble, Clever, Great).
- [ ] Parsing de grupos de coleta em andamento e contadores de tempo restante.
- [ ] **Algoritmo de Otimização de Coleta:** Cálculo proporcional da distribuição de tropas para retorno simultâneo.
- [ ] Disparo automático com timer e agendamento para reenvio.

### 2.5. Recrutamento Militar (Quartel, Estábulo, Oficina)
- [x] Parsing do ecrã do Quartel (`screen=barracks`), Estábulo (`screen=stable`) e Oficina (`screen=garage`).
- [x] Leitura das filas de recrutamento ativas e tempo de conclusão.
- [x] Configuração de metas de exército (ex.: lanceiros, espadachins, cavalaria leve).
- [x] Recrutamento inteligente em pequenos lotes contínuos para preservação de recursos.
- [x] Validação de limite de população livre da Fazenda antes de recrutar (`min_free_pop`).
- [x] Suíte de testes unitários para Recrutamento Militar (5 testes dedicados).

### 2.6. Academia & Cunha de Moedas (`screen=snob`)
- [ ] Leitura de moedas cunhadas / pacotes acumulados.
- [ ] Cunha automática de moedas quando o armazém estiver prestes a encher.
- [ ] Recrutamento automático de Nobres mediante configuração do utilizador.

### 2.7. Mercado & Balanceamento (`screen=market`)
- [ ] Leitura de mercadores disponíveis.
- [ ] Balanceamento automático de recursos entre aldeias da mesma conta.
- [ ] Criação de ofertas no mercado para troca de excedentes.

### 2.8. Sistema de Defesa & Alarme de Ataques (Prioridade 0 / Alertas)
- [ ] Monitorização em tempo real de ataques a chegar à aldeia (`incomings`).
- [ ] Deteção da velocidade da unidade mais lenta atacante (estimativa de Nobre / Aríete).
- [ ] **Rotina de Auto-Dodge (Desvio de Tropas e Recursos):** Envio para aldeia bárbara 30s antes do impacto e cancelamento pós-impacto.
- [ ] Notificação sonora e visual de emergência.

### 2.9. Algoritmo de Decisão Inteligente & Perfis de Aldeia (Evolução vs. Tropas)
- [ ] **Classificação e Especialização de Aldeias:**
  - [ ] Definição de perfil por aldeia: **Ofensiva** (Ataque / Nuke) vs. **Defensiva** (Defesa / Bunker).
  - [ ] Templates e modelos de tropas personalizáveis por perfil (ex.: Full Ataque: Machado + CL + Aríete / Full Defesa: Lança + Espada + Pesada/Arco).
- [ ] **Algoritmo de Priorização Dinâmica (Edifícios vs. Recrutamento):**
  - [ ] Co-design e definição do algoritmo de arbitragem de recursos: quando gastar em edifícios vs. manter as filas de recrutamento 100% ativas.
  - [ ] Regras de reserva de recursos (buffer de segurança) para nunca bloquear a evolução de edifícios vitais ou o treino contínuo.
  - [ ] Adaptação às fases do jogo (Early Game: foco em minas/fazenda/farm vs. Mid/Late Game: foco em exército contínuo e nobres).

### 2.10. Sistema de Missões & Recompensas de Edifícios (`quests`)
- [ ] Leitura de missões concluídas e recompensas pendentes de edifícios finalizados.
- [ ] Resgate automático de recompensas com verificação de espaço livre no armazém para evitar desperdício de recursos.

---

## 📌 Fase 3: Camada Sidecar IPC & Gestão Concorrente (`engine/api/`)

- [x] **Servidor Local FastAPI & WebSockets**
  - [x] Execução em localhost com porta dinâmica e token efêmero de autenticação local (`.sidecar_auth.json`).
  - [x] Endpoints REST para comandos manuais, leitura de status, alteração de configurações e toggles de rotinas.
  - [x] Canal WebSocket bidirecional para streaming em tempo real de logs e status.
  - [x] Disparo de alerta de captcha anti-bot para o frontend (`CAPTCHA_ALERT`).
  - [x] Suíte de testes unitários para a API Sidecar (14 testes dedicados).
- [ ] **Gestão Concorrente Multi-Aldeia (Mesmo Mundo)**
  - [x] Extração de todas as aldeias da conta a partir do `game_data` (`extract_all_villages`).
  - [x] Alternância fluida de contexto entre múltiplas aldeias (`account.switch_village` e `POST /api/account/switch-village`).
  - [ ] Execução de rotinas e agendamento concorrente/round-robin para múltiplas aldeias na mesma sessão sem conflito de requests.
  - [ ] Configuração individualizada por aldeia no `config.json` (perfil Ofensivo/Defensivo, templates de tropas e edifícios).
- [ ] **Gestão Simultânea Multi-Mundo (2+ Mundos Concorrentes)**
  - [ ] Orquestrador de instâncias para execução simultânea de múltiplos mundos (ex: pt117 e pt118 ao mesmo tempo).
  - [ ] Isolamento de sessões de rede `TribalAccount`, schedulers e ficheiros de cookies/configuração por mundo.
  - [ ] Suporte a instâncias em abas ou seletor de mundo em tempo real no Dashboard Frontend.
- [x] **Gestor de Perfis & Proxies**
  - [x] Persistência segura de perfis de conta com ofuscação/encriptação (`ProfileManager` em `profiles.json`).
  - [x] Suporte a proxy dedicado ou residencial por conta com diagnóstico ativo (`test_proxy_connection`).
  - [x] Suíte de testes unitários dedicada (9 testes cobrindo perfis, multi-aldeia e proxies).

---

## 📌 Fase 4: Shell Desktop & Frontend Nativo (`frontend/`)

- [x] **Interface Gráfica (UI/UX Premium Cockpit)**
  - [x] Dashboard com visual moderno (Dark Mode, Glassmorphism, Google Fonts Outfit & Inter, paleta Neon Cyber).
  - [x] **HUD Timer de Alta Precisão:** Relógio digital no topo da aplicação exibindo horas, minutos, segundos e microssegundos (`HH:MM:SS.uuuuuu`) a 60 FPS com `requestAnimationFrame`.
  - [x] Visão geral da aldeia: cartões de recursos em tempo real, capacidade do Armazém e População livre.
  - [x] Fila de construção em tempo real com contagem decrescente ativa e estimativa de custos para o próximo edifício.
  - [x] Painel de controlo de módulos com botões de ação imediata (Pausar/Retomar, Construir Agora, Farm Agora, Recrutar Agora).
  - [x] Consola de logs ao vivo via streaming WebSocket com busca por texto, filtros de severidade, auto-scroll e limpeza.
  - [x] Painel de configurações visuais com gravação instantânea e recarregamento a quente no `config.json`.
- [ ] **Visualizador de Mapa Interativo Integrado (Embedded Game Map)**
  - [ ] Renderização do mapa do mundo/continente com suporte a zoom e arrasto direto no Cockpit.
  - [ ] Destaque de aldeias próprias, bárbaras no raio de farm e aldeias de jogadores vizinhos.
  - [ ] Ações rápidas de clique no mapa para envio de saque ou marcação de alvos.
- [x] **Shell Desktop Nativa Edge WebView2**
  - [x] Execução como aplicação desktop nativa via Edge WebView2 (`engine/desktop_launcher.py` ou `python -m engine.main --gui`).
  - [x] Servidor Sidecar serve a interface web diretamente em `http://127.0.0.1:8000/` (`python -m engine.main --api`).
  - [x] Estrutura do frontend (`frontend/`) 100% isolada e compatível para build final.
- [x] **Modal de Alerta & Resolução de Captchas Anti-Bot**
  - [x] Overlay modal de emergência ativado instantaneamente por evento WebSocket (`CAPTCHA_ALERT`) com aviso sonoro sintetizado.
  - [x] Botão para abertura direta da janela do jogo para resolução humana e botão para retoma automática do motor.

---

## 📌 Fase 5: Empacotamento, Testes E2E & Release

- [ ] Empacotamento do executável Python isolado com PyInstaller.
- [ ] Build do instalador desktop nativo (`.msi` / `.exe`).
- [ ] Testes de robustez com reconexão automática em caso de quebra de rede.
- [ ] Documentação de utilização final e guia de configuração.
