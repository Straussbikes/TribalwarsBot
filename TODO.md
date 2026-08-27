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
- [ ] Suporte a Assistente de Farm (`screen=am_farm`):
  - [ ] Leitura da tabela de aldeias bárbaras vizinhas.
  - [ ] Leitura do estado dos relatórios (verde, amarelo, vermelho).
  - [ ] Disparo automatizado dos modelos A e B com atrasos humanos entre toques (150ms - 400ms).
- [ ] Fallback para Farming via Praça de Reunião (`screen=place`):
  - [ ] Lista configurável de aldeias bárbaras por coordenadas ou raio de distância.
  - [ ] Envio automático de micro-grupos de saque (ex.: 5 lanceiros ou 2 cavalarias leves).
- [ ] Critérios de segurança: paragem imediata do farm caso as tropas sofram baixas ou a muralha inimiga suba.

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
- [ ] Parsing do ecrã do Quartel (`screen=barracks`), Estábulo (`screen=stable`) e Oficina (`screen=garage`).
- [ ] Leitura das filas de recrutamento ativas e tempo de conclusão.
- [ ] Configuração de metas de exército (ex.: 1000 lanceiros, 1000 espadachins, 500 cavalarias leves).
- [ ] Recrutamento inteligente em pequenos lotes contínuos para não esgotar recursos necessários à evolução da aldeia.
- [ ] Validação de limite de população livre da Fazenda antes de recrutar.

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

- [ ] **Servidor Local FastAPI & WebSockets**
  - [ ] Execução em localhost com porta dinâmica e token efêmero de autenticação local.
  - [ ] Endpoints REST para comandos manuais, leitura de status, alteração de configurações e toggles de rotinas.
  - [ ] Canal WebSocket bidirecional para streaming em tempo real:
    - [ ] Logs do bot categorizados por severidade (`INFO`, `WARNING`, `CRITICAL`).
    - [ ] Recursos, aldeias e estado das filas em tempo real.
    - [ ] Disparo de alerta de captcha anti-bot para o frontend.
- [ ] **Gestor de Contas & Multi-Aldeia**
  - [ ] Persistência segura de perfis de conta (ficheiro JSON/SQLite encriptado).
  - [ ] Suporte a proxy dedicado ou residencial por conta (`http://user:pass@ip:port`).
  - [ ] Alternância fluida de contexto entre múltiplas aldeias (`village_id`).

---

## 📌 Fase 4: Shell Desktop Tauri v2 (Frontend Nativo)

- [ ] **Setup do Projeto Tauri v2**
  - [ ] Inicialização do shell desktop em Rust + HTML/CSS/JS (Vanilla ou framework leve).
  - [ ] Integração do sidecar Python com ciclo de vida controlado (start/stop automático com o aplicativo).
- [ ] **Interface Gráfica (UI/UX Premium)**
  - [ ] Dashboard com visual moderno (dark mode, glassmorphism, tipografia moderna).
  - [ ] Visão geral da aldeia: cartões de recursos, capacidade do armazém, fazenda e gráficos.
  - [ ] Painel de controlo de módulos com toggles individuais (Auto-Build, Auto-Farm, Scavenge, Recrutamento).
  - [ ] Consola de logs ao vivo com filtros de pesquisa e cores por severidade.
- [ ] **Janela Popup WebView para Resolução de Captchas**
  - [ ] Abertura automática de janela nativa isolada apontando para a URL do captcha do jogo quando surgir `BotProtectionError`.
  - [ ] Deteção do captcha resolvido pelo utilizador, fechamento do popup e retoma instantânea do agendador.
- [ ] **Notificações de Sistema**
  - [ ] Notificações no Windows para ataques inimigos recebidos e captchas pendentes.
  - [ ] Minimizar para o System Tray com menu de contexto rápido (Pausar/Retomar/Encerrar).

---

## 📌 Fase 5: Empacotamento, Testes E2E & Release

- [ ] Empacotamento do executável Python isolado com PyInstaller ou PyStandalone.
- [ ] Build do instalador desktop nativo (`.msi` / `.exe`) via Tauri Bundler.
- [ ] Testes de robustez com reconexão automática em caso de quebra de internet.
- [ ] Documentação de utilização final e guia de configuração de proxies e templates.
